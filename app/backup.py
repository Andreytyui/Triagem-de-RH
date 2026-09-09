"""Backup e restauração de `data/`.

    python -m app.backup criar
    python -m app.backup listar
    python -m app.backup restaurar caminho/do/arquivo.triagem

O que está em jogo aqui é o pior cenário do produto: um servidor hospedando
currículo de várias empresas e perdendo o banco. É perda de dado pessoal de
terceiros, com a multa do lado do cliente e a reputação do lado de quem vendeu.

Três decisões que explicam o formato:

**O SQLite não é copiado com `cp`.** Com WAL ligado e o servidor escrevendo, uma
cópia de arquivo pega um instantâneo rasgado — meio commit dentro, o resto no
`-wal` que ficou de fora. Aqui é a API de backup online do próprio SQLite, que
tira um instantâneo consistente **sem parar o servidor**.

**O artefato é cifrado.** Ele carrega o banco com currículos de várias empresas
e o `.secret` que assina as sessões. Uma cópia em claro num disco qualquer é o
comprometimento total do sistema, não um inconveniente. A chave vem de uma senha
por scrypt, e o sal viaja no cabeçalho.

**Mandar para fora é comando de quem opera.** Backup que mora no mesmo disco do
banco não é backup. Mas escolher provedor por você seria acoplar o produto a um;
então `BACKUP_COMANDO_ENVIO` recebe um comando com `{arquivo}` dentro — rclone,
scp, aws s3, o que o operador usar.
"""
from __future__ import annotations

import io
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import (
    BACKUP_COMANDO_ENVIO,
    BACKUP_DIARIOS,
    BACKUP_DIR,
    BACKUP_SEMANAIS,
    BACKUP_SENHA,
    DATA_DIR,
    DB_PATH,
)

log = logging.getLogger(__name__)

EXTENSAO = ".triagem"
ASSINATURA = b"TRIAGEM-BACKUP-1\n"
SAL_BYTES = 16


class BackupErro(RuntimeError):
    """Falha que o operador precisa ler, não um traceback."""


# ---------- Cifra ----------

def _fernet(senha: str, sal: bytes):
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:                                 # pragma: no cover
        raise BackupErro(
            "o backup cifrado exige o pacote 'cryptography' (pip install cryptography)"
        ) from exc

    import base64
    import hashlib

    # scrypt em vez de PBKDF2: aqui o atacante teria o arquivo na mão e tempo de
    # sobra, e o custo de memória do scrypt é o que encarece o ataque em GPU.
    #
    # `maxmem` precisa ser explícito: com n=2^15 e r=8 a derivação pede ~32 MB, e
    # o padrão do OpenSSL é bem menor — sem isto o backup falha na hora de cifrar.
    derivada = hashlib.scrypt(
        senha.encode("utf-8"), salt=sal, n=2 ** 15, r=8, p=1, dklen=32,
        maxmem=64 * 1024 * 1024,
    )
    return Fernet(base64.urlsafe_b64encode(derivada))


def _senha_ou_erro(senha: Optional[str]) -> str:
    senha = senha or BACKUP_SENHA
    if not senha:
        raise BackupErro(
            "defina BACKUP_SENHA no ambiente (ou passe --senha). Sem ela o backup "
            "sairia em claro, com o banco de currículos de todas as contas dentro"
        )
    if len(senha) < 12:
        raise BackupErro("a senha do backup precisa de pelo menos 12 caracteres")
    return senha


# ---------- Criar ----------

def _snapshot_do_banco(destino: Path) -> None:
    """Instantâneo consistente do SQLite, com o servidor rodando.

    `Connection.backup()` é a API oficial para isto: ela lê página a página
    segurando o que precisa, e o resultado nunca é um arquivo pela metade.
    """
    origem = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30)
    try:
        copia = sqlite3.connect(destino)
        try:
            origem.backup(copia)
        finally:
            copia.close()
    finally:
        origem.close()


def criar(senha: Optional[str] = None, destino: Optional[Path] = None) -> Path:
    """Gera um artefato cifrado com banco, uploads e segredo. Devolve o caminho."""
    senha = _senha_ou_erro(senha)
    pasta = Path(destino or BACKUP_DIR)
    pasta.mkdir(parents=True, exist_ok=True)

    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    arquivo = pasta / f"triagem-{carimbo}{EXTENSAO}"

    with tempfile.TemporaryDirectory(prefix="triagem-backup-") as tmp:
        tmp = Path(tmp)
        banco = tmp / "triagem.db"
        _snapshot_do_banco(banco)

        pacote = io.BytesIO()
        with tarfile.open(fileobj=pacote, mode="w:gz") as tar:
            tar.add(banco, arcname="triagem.db")

            uploads = DATA_DIR / "uploads"
            if uploads.is_dir():
                # Sem os arquivos originais o ranking sobrevive, mas a evidência
                # não: o recrutador não consegue mais abrir o currículo que
                # sustenta a nota. Backup sem isso não restaura o produto.
                tar.add(uploads, arcname="uploads")

            segredo = DATA_DIR / ".secret"
            if segredo.exists():
                tar.add(segredo, arcname=".secret")

            manifesto = json.dumps({
                "criado_em": datetime.now(timezone.utc).isoformat(),
                "banco_bytes": banco.stat().st_size,
                "uploads": sum(1 for _ in uploads.rglob("*")) if uploads.is_dir() else 0,
            }, ensure_ascii=False).encode("utf-8")
            info = tarfile.TarInfo("manifesto.json")
            info.size = len(manifesto)
            tar.addfile(info, io.BytesIO(manifesto))

        sal = os.urandom(SAL_BYTES)
        cifrado = _fernet(senha, sal).encrypt(pacote.getvalue())
        arquivo.write_bytes(ASSINATURA + sal + cifrado)

    try:
        arquivo.chmod(0o600)
    except OSError:                                            # pragma: no cover
        pass

    log.info("backup criado: %s (%.1f MB)", arquivo, arquivo.stat().st_size / 1e6)
    _enviar_para_fora(arquivo)
    expurgar(pasta)
    return arquivo


def _enviar_para_fora(arquivo: Path) -> bool:
    """Backup no mesmo disco do banco não é backup. Quem escolhe o destino é
    quem opera; aqui só se executa o comando que ele configurou."""
    if not BACKUP_COMANDO_ENVIO:
        log.warning(
            "BACKUP_COMANDO_ENVIO não configurado: o backup ficou só em %s, "
            "no mesmo servidor que ele deveria proteger", arquivo.parent
        )
        return False
    comando = BACKUP_COMANDO_ENVIO.format(arquivo=str(arquivo))
    try:
        resultado = subprocess.run(comando, shell=True, capture_output=True,
                                   timeout=1800, text=True)
    except subprocess.TimeoutExpired:
        log.error("o envio do backup para fora estourou o tempo")
        return False
    if resultado.returncode != 0:
        log.error("o envio do backup falhou (%s): %s",
                  resultado.returncode, (resultado.stderr or "")[:400])
        return False
    log.info("backup enviado para fora da máquina")
    return True


# ---------- Retenção ----------

def _data_do_nome(arquivo: Path) -> Optional[datetime]:
    """`triagem-20260108T030000Z.triagem` -> a data. None se o nome não for nosso.

    Nome que não dá para ler é nome que não se apaga: pode ser backup de alguém,
    guardado nessa pasta de propósito.
    """
    nome = arquivo.name
    prefixo = "triagem-"
    if not nome.startswith(prefixo):
        return None
    try:
        return datetime.strptime(nome[len(prefixo):len(prefixo) + 8], "%Y%m%d")
    except ValueError:
        return None


def expurgar(pasta: Optional[Path] = None) -> list[Path]:
    """Guarda os N diários mais recentes e um por semana depois disso.

    Disco cheio de backup antigo acaba virando backup nenhum, porque a rotina
    começa a falhar em silêncio.
    """
    pasta = Path(pasta or BACKUP_DIR)
    if not pasta.is_dir():
        return []

    arquivos = sorted(pasta.glob(f"*{EXTENSAO}"), key=lambda p: p.name, reverse=True)
    guardar = set(arquivos[:BACKUP_DIARIOS])

    semanas_vistas: set[str] = set()
    for arquivo in arquivos[BACKUP_DIARIOS:]:
        data = _data_do_nome(arquivo)
        if data is None:
            guardar.add(arquivo)                               # nome estranho: não apaga
            continue
        semana = f"{data.isocalendar().year}-{data.isocalendar().week}"
        if semana not in semanas_vistas and len(semanas_vistas) < BACKUP_SEMANAIS:
            semanas_vistas.add(semana)
            guardar.add(arquivo)

    apagados = []
    for arquivo in arquivos:
        if arquivo not in guardar:
            arquivo.unlink(missing_ok=True)
            apagados.append(arquivo)
    if apagados:
        log.info("expurgo de backup: %d arquivo(s) antigos apagados", len(apagados))
    return apagados


# ---------- Restaurar ----------

def inspecionar(arquivo: Path, senha: Optional[str] = None) -> dict:
    """Abre o artefato e devolve o manifesto, sem escrever nada em lugar nenhum."""
    senha = _senha_ou_erro(senha)
    bruto = Path(arquivo).read_bytes()
    if not bruto.startswith(ASSINATURA):
        raise BackupErro(f"{arquivo} não parece um backup da Triagem")

    corpo = bruto[len(ASSINATURA):]
    sal, cifrado = corpo[:SAL_BYTES], corpo[SAL_BYTES:]
    try:
        pacote = _fernet(senha, sal).decrypt(cifrado)
    except BackupErro:
        raise
    except Exception as exc:                                   # noqa: BLE001
        raise BackupErro(
            "não foi possível abrir o backup: a senha está errada, ou o arquivo "
            "foi corrompido"
        ) from exc

    with tarfile.open(fileobj=io.BytesIO(pacote), mode="r:gz") as tar:
        membro = tar.extractfile("manifesto.json")
        return json.loads(membro.read().decode("utf-8")) if membro else {}


def restaurar(arquivo: Path, destino: Optional[Path] = None,
              senha: Optional[str] = None) -> Path:
    """Escreve banco, uploads e segredo em `destino`. Não mexe no servidor vivo.

    A restauração é feita numa pasta de dados escolhida por quem restaura, e não
    por cima da que está em uso. Restaurar por baixo de um processo rodando é
    como se troca um pneu com o carro andando.
    """
    senha = _senha_ou_erro(senha)
    destino = Path(destino or DATA_DIR)

    bruto = Path(arquivo).read_bytes()
    if not bruto.startswith(ASSINATURA):
        raise BackupErro(f"{arquivo} não parece um backup da Triagem")
    corpo = bruto[len(ASSINATURA):]
    sal, cifrado = corpo[:SAL_BYTES], corpo[SAL_BYTES:]
    try:
        pacote = _fernet(senha, sal).decrypt(cifrado)
    except BackupErro:
        raise
    except Exception as exc:                                   # noqa: BLE001
        raise BackupErro(
            "não foi possível abrir o backup: a senha está errada, ou o arquivo "
            "foi corrompido"
        ) from exc

    if destino.exists() and any(destino.iterdir()):
        if (destino / "triagem.db").exists():
            reserva = destino / f"triagem.db.antes-da-restauracao-{int(time.time())}"
            shutil.move(str(destino / "triagem.db"), str(reserva))
            log.warning("banco anterior preservado em %s", reserva)
        shutil.rmtree(destino / "uploads", ignore_errors=True)
    destino.mkdir(parents=True, exist_ok=True)

    with tarfile.open(fileobj=io.BytesIO(pacote), mode="r:gz") as tar:
        for membro in tar.getmembers():
            # Um tar carrega o caminho que quiser; sem esta trava, um artefato
            # adulterado escreveria fora da pasta de destino.
            alvo = (destino / membro.name).resolve()
            if not str(alvo).startswith(str(destino.resolve())):
                raise BackupErro(f"caminho suspeito dentro do backup: {membro.name}")
        # `filter='data'` é a segunda trava, do próprio Python: recusa link
        # simbólico, caminho absoluto e permissão estranha vinda do arquivo.
        try:
            tar.extractall(destino, filter="data")
        except TypeError:                                      # pragma: no cover
            tar.extractall(destino)                            # Python sem o filtro

    segredo = destino / ".secret"
    if segredo.exists():
        try:
            segredo.chmod(0o600)
        except OSError:                                        # pragma: no cover
            pass

    log.info("backup restaurado em %s", destino)
    return destino


# ---------- Rotina do servidor ----------

async def rodar_periodicamente() -> None:
    """Laço do backup automático. Roda no boot e depois no intervalo."""
    import asyncio

    from .config import BACKUP_ATIVO, BACKUP_INTERVALO_H

    if not BACKUP_ATIVO:
        log.warning("backup automático desligado (BACKUP_ATIVO=false)")
        return
    if not BACKUP_SENHA:
        log.error(
            "backup automático ligado mas sem BACKUP_SENHA: nada será feito. "
            "Defina a senha ou desligue com BACKUP_ATIVO=false"
        )
        return

    while True:
        try:
            await asyncio.to_thread(criar)
        except asyncio.CancelledError:
            raise
        except Exception:                                      # noqa: BLE001
            log.exception("falha no ciclo de backup")
        await asyncio.sleep(max(BACKUP_INTERVALO_H, 1) * 3600)


# ---------- Linha de comando ----------

def main(argumentos: list[str]) -> int:
    from . import config

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not argumentos or argumentos[0] in {"-h", "--help"}:
        print(__doc__.strip())
        return 1

    acao = argumentos[0]
    resto = argumentos[1:]
    senha = None
    if "--senha" in resto:
        i = resto.index("--senha")
        senha = resto[i + 1] if len(resto) > i + 1 else None
        resto = resto[:i] + resto[i + 2:]

    try:
        if acao == "criar":
            arquivo = criar(senha)
            print(f"backup criado: {arquivo}")
            return 0

        if acao == "listar":
            pasta = Path(BACKUP_DIR)
            arquivos = sorted(pasta.glob(f"*{EXTENSAO}"), reverse=True) if pasta.is_dir() else []
            if not arquivos:
                print(f"nenhum backup em {pasta}")
                return 0
            for arquivo in arquivos:
                print(f"{arquivo.name}  {arquivo.stat().st_size / 1e6:7.1f} MB")
            return 0

        if acao in {"restaurar", "inspecionar"}:
            if not resto:
                print(f"uso: python -m app.backup {acao} caminho/do/arquivo{EXTENSAO}",
                      file=sys.stderr)
                return 1
            arquivo = Path(resto[0])
            if not arquivo.exists():
                print(f"arquivo não encontrado: {arquivo}", file=sys.stderr)
                return 1

            if acao == "inspecionar":
                print(json.dumps(inspecionar(arquivo, senha), indent=2, ensure_ascii=False))
                return 0

            destino = Path(resto[1]) if len(resto) > 1 else config.DATA_DIR
            print(f"restaurando {arquivo.name} em {destino}")
            print("PARE o servidor antes de continuar, se ele estiver rodando.")
            restaurar(arquivo, destino, senha)
            print("pronto. Suba o servidor e confira o ranking de uma vaga conhecida.")
            return 0

        print(f"ação desconhecida: {acao}", file=sys.stderr)
        return 1

    except BackupErro as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
