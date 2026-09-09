"""Backup e restauração de `data/`.

O teste que importa aqui é o último: um backup que nunca foi restaurado é uma
crença, não um backup. Então a suíte restaura de verdade, num diretório limpo, a
partir só do artefato cifrado, e confere que o ranking, a evidência de cada nota
e os arquivos originais voltaram idênticos.
"""
from __future__ import annotations

import sqlite3
import tempfile
import threading
from pathlib import Path

from .comum import Placar

SENHA = "senha-de-backup-para-teste-0123456789"


def rodar(placar: Placar) -> None:
    from app import backup, storage
    from app.models import Criterio, Rubrica

    print("\nBackup")
    storage.iniciar()

    org_id = storage.criar_organizacao("Agência do backup")
    usuario_id = storage.criar_usuario(org_id, "backup@teste.com", "Chefe", "h", "admin")
    vaga_id = storage.criar_vaga(org_id, "Analista de Suporte", "descrição " * 12, usuario_id)
    rubrica = Rubrica(cargo="Suporte", senioridade="pleno",
                      criterios=[Criterio(id="suporte", nome="Suporte N2",
                                          descricao="mesa de ajuda e SLA", peso=100)])
    storage.salvar_rubrica(org_id, vaga_id, rubrica.model_dump(), aprovada=True)

    from app import extraction

    doc = extraction.Documento(
        candidato_id="backupcand0001", arquivo="curriculo.pdf", origem_hash="hashdobackup",
        extensao=".pdf", texto="Analista de suporte N2 com SLA de 4 horas.")
    storage.salvar_curriculo(org_id, doc)
    storage.vincular(vaga_id, doc.candidato_id)
    storage.salvar_avaliacao(
        vaga_id, doc.candidato_id, estagio="avaliado", score_final=87.0,
        recomendacao="chamar", confianca="alta",
        resultado={"criterios": [{"criterio_id": "suporte", "nota": 9,
                                  "evidencia": "chamados com SLA de 4 horas"}],
                   "resumo": "Analista N2 experiente."})

    # O arquivo original: é o que sustenta a evidência quando o recrutador quer
    # conferir. Backup que perde isto restaura número sem prova.
    conteudo_original = b"%PDF-1.4 conteudo do curriculo original do candidato"
    (storage.pasta_org(org_id) / "hashdobackup.pdf").write_bytes(conteudo_original)

    # Na suíte a chave vem por variável de ambiente, então o `.secret` não chega a
    # ser escrito. Em produção ele existe e é o que assina sessão e CSRF: perdê-lo
    # derruba todo mundo e mata os tokens do conector. Aqui ele é criado à mão
    # para o backup ter o que carregar.
    from app.config import DATA_DIR

    segredo = "segredo-do-servidor-que-precisa-voltar"
    (DATA_DIR / ".secret").write_text(segredo, encoding="utf-8")

    contexto: dict = {}

    # ---- criar, com escrita acontecendo ao mesmo tempo ----
    def cria_com_escrita_concorrente():
        pasta = Path(tempfile.mkdtemp(prefix="triagem-bkp-"))
        parar = threading.Event()
        falhas: list[str] = []

        def escrevendo():
            i = 0
            while not parar.is_set():
                try:
                    storage.registrar_auditoria(org_id, usuario_id, f"ruido.{i}")
                    i += 1
                except Exception as exc:                       # noqa: BLE001
                    falhas.append(str(exc))
                    return

        escritor = threading.Thread(target=escrevendo, daemon=True)
        escritor.start()
        try:
            arquivo = backup.criar(SENHA, pasta)
        finally:
            parar.set()
            escritor.join(timeout=5)

        assert not falhas, f"a escrita no banco quebrou durante o backup: {falhas[:2]}"
        assert arquivo.exists() and arquivo.stat().st_size > 0, "artefato vazio"
        contexto["arquivo"] = arquivo
        contexto["pasta"] = pasta

        manifesto = backup.inspecionar(arquivo, SENHA)
        assert manifesto["banco_bytes"] > 0, manifesto
        return f"{arquivo.stat().st_size / 1024:.0f} KB com o servidor escrevendo"

    placar.rodar("Backup roda sem parar o servidor e sem travar a escrita",
                 cria_com_escrita_concorrente)

    # ---- o artefato não pode ser legível ----
    def cifrado_em_repouso():
        bruto = contexto["arquivo"].read_bytes()
        for vazamento in (b"Analista de suporte", b"backup@teste.com",
                          b"SQLite format 3", b"chamados com SLA"):
            assert vazamento not in bruto, (
                f"o backup tem {vazamento!r} legível — cópia em claro do banco"
            )

        senha_errada = False
        try:
            backup.inspecionar(contexto["arquivo"], "senha-errada-mas-com-tamanho")
        except backup.BackupErro:
            senha_errada = True
        assert senha_errada, "o backup abriu com a senha errada"
        return "nada legível no arquivo, e senha errada não abre"

    placar.rodar("Artefato de backup é cifrado em repouso", cifrado_em_repouso)

    # ---- restauração num diretório limpo, só com o artefato ----
    def restaura_limpo():
        destino = Path(tempfile.mkdtemp(prefix="triagem-restaurado-"))
        backup.restaurar(contexto["arquivo"], destino, SENHA)

        banco = destino / "triagem.db"
        assert banco.exists(), "o banco não voltou"
        arquivo_segredo = destino / ".secret"
        assert arquivo_segredo.exists(), (
            "o .secret não voltou; sem ele as sessões e os tokens do conector morrem"
        )
        assert arquivo_segredo.read_text(encoding="utf-8") == segredo, (
            "o .secret voltou diferente"
        )

        # O arquivo original tem de voltar byte a byte: é a prova da evidência.
        restaurado = destino / "uploads" / org_id / "hashdobackup.pdf"
        assert restaurado.exists(), "o currículo original não voltou"
        assert restaurado.read_bytes() == conteudo_original, (
            "o arquivo original voltou diferente do que entrou"
        )

        # E o conteúdo do banco: ranking, nota e a evidência citada.
        conn = sqlite3.connect(banco)
        conn.row_factory = sqlite3.Row
        try:
            vaga = conn.execute("SELECT * FROM vagas WHERE id=?", (vaga_id,)).fetchone()
            avaliacao = conn.execute(
                "SELECT * FROM avaliacoes WHERE vaga_id=? AND candidato_id=?",
                (vaga_id, doc.candidato_id)).fetchone()
            usuario = conn.execute(
                "SELECT * FROM usuarios WHERE id=?", (usuario_id,)).fetchone()
        finally:
            conn.close()

        assert vaga and vaga["titulo"] == "Analista de Suporte", "a vaga não voltou"
        assert vaga["rubrica_ok"] == 1, "a aprovação da rubrica se perdeu"
        assert avaliacao and avaliacao["score_final"] == 87.0, "a nota não voltou"
        assert "SLA de 4 horas" in (avaliacao["resultado"] or ""), (
            "a evidência que sustenta a nota não voltou"
        )
        assert usuario and usuario["senha_hash"] == "h", (
            "o usuário não voltou; ninguém conseguiria entrar depois de restaurar"
        )
        contexto["destino"] = destino
        return "banco, evidência, arquivo original e segredo, idênticos"

    placar.rodar("Restauração em diretório limpo devolve tudo que sustenta o ranking",
                 restaura_limpo)

    # ---- artefato corrompido não passa por restauração pela metade ----
    def corrompido():
        arquivo = contexto["arquivo"]
        estragado = arquivo.parent / "estragado.triagem"
        bruto = bytearray(arquivo.read_bytes())
        bruto[-40] ^= 0xFF                                     # um bit no meio do corpo
        estragado.write_bytes(bytes(bruto))

        destino = Path(tempfile.mkdtemp(prefix="triagem-corrompido-"))
        recusou = False
        try:
            backup.restaurar(estragado, destino, SENHA)
        except backup.BackupErro:
            recusou = True
        assert recusou, "o backup corrompido foi aceito"
        assert not (destino / "triagem.db").exists(), (
            "escreveu um banco a partir de um artefato corrompido"
        )
        return "recusa antes de escrever qualquer coisa"

    placar.rodar("Backup corrompido é recusado, não restaurado pela metade", corrompido)

    # ---- sem senha, o código recusa em vez de gravar em claro ----
    def exige_senha():
        recusou = False
        try:
            backup.criar("", contexto["pasta"])
        except backup.BackupErro as exc:
            recusou = "BACKUP_SENHA" in str(exc)
        assert recusou, "gerou backup sem senha"

        curta = False
        try:
            backup.criar("curta", contexto["pasta"])
        except backup.BackupErro:
            curta = True
        assert curta, "aceitou senha curta demais para proteger o artefato"
        return "sem senha não há artefato"

    placar.rodar("Backup sem senha é recusado, não gerado em claro", exige_senha)

    # ---- retenção: diários recentes mais um por semana ----
    def retencao():
        from datetime import datetime, timedelta

        pasta = Path(tempfile.mkdtemp(prefix="triagem-retencao-"))
        # 40 dias seguidos de backup, um por dia
        primeiro = datetime(2026, 1, 1)
        for dia in range(40):
            carimbo = (primeiro + timedelta(days=dia)).strftime("%Y%m%d")
            (pasta / f"triagem-{carimbo}T030000Z.triagem").write_bytes(b"x")
        antes = len(list(pasta.glob("*.triagem")))

        backup.expurgar(pasta)
        restantes = sorted(p.name for p in pasta.glob("*.triagem"))

        from app.config import BACKUP_DIARIOS, BACKUP_SEMANAIS
        assert len(restantes) <= BACKUP_DIARIOS + BACKUP_SEMANAIS, (
            f"sobraram {len(restantes)} backups; o teto é "
            f"{BACKUP_DIARIOS} diários mais {BACKUP_SEMANAIS} semanais"
        )
        assert len(restantes) >= BACKUP_DIARIOS, (
            f"o expurgo comeu os diários recentes: sobraram {len(restantes)}"
        )
        # O mais novo nunca pode sumir.
        mais_novo = (primeiro + timedelta(days=39)).strftime("%Y%m%d")
        assert f"triagem-{mais_novo}T030000Z.triagem" in restantes, (
            f"o backup mais recente foi apagado: {restantes}"
        )
        return f"de {antes} para {len(restantes)} arquivos"

    placar.rodar("Expurgo guarda os diários recentes e um por semana", retencao)

    # ---- o servidor sobe com o que foi restaurado ----
    def sobe_do_restaurado():
        import os
        import subprocess
        import sys

        destino = contexto["destino"]
        codigo = (
            "import os, sys;"
            "sys.path.insert(0, r'.');"
            "from app import storage;"
            "storage.iniciar();"
            f"linhas = storage.ranking('{org_id}', '{vaga_id}');"
            "print(len(linhas), linhas[0]['score_final'] if linhas else '-')"
        )
        ambiente = {**os.environ, "TRIAGEM_DATA_DIR": str(destino),
                    "LOG_NIVEL": "ERROR", "BACKUP_ATIVO": "false"}
        saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True,
                               text=True, env=ambiente, cwd=os.getcwd(), timeout=120)
        assert saida.returncode == 0, f"o app não subiu do banco restaurado: {saida.stderr[-400:]}"
        assert saida.stdout.split() == ["1", "87.0"], (
            f"o ranking não bateu depois de restaurar: {saida.stdout!r}"
        )
        return "processo novo lê o banco restaurado e devolve o mesmo ranking"

    placar.rodar("Servidor sobe do backup restaurado e mostra o mesmo ranking",
                 sobe_do_restaurado)
