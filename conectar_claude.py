"""Liga a Triagem ao Claude instalado nesta máquina.

Gera um token de conexão e escreve a configuração do Claude Desktop e/ou do
Claude Code. Foi feito para o comprador rodar sozinho: pergunta o e-mail e a
senha da Triagem, e faz o resto.

    python conectar_claude.py

Não mexe em servidor nenhum na internet — o Claude passa a rodar a Triagem como
um processo aqui na máquina, e os currículos não saem daqui.
"""
from __future__ import annotations

import getpass
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def _configs_do_desktop() -> list[Path]:
    """Onde o Claude Desktop guarda a configuração.

    No Windows há dois casos. Instalado pela Microsoft Store, o app roda em
    contêiner e o AppData dele fica redirecionado para dentro de `Packages`;
    escrever no `%APPDATA%\\Claude` clássico não teria efeito nenhum — o app nem
    olha lá. Instalado pelo instalador normal, é o caminho clássico. Devolvemos
    os que existirem, para acertar nos dois.
    """
    if sys.platform == "win32":
        achados: list[Path] = []
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        for pacote in sorted((local / "Packages").glob("Claude_*")):
            alvo = pacote / "LocalCache" / "Roaming" / "Claude"
            if alvo.is_dir():
                achados.append(alvo / "claude_desktop_config.json")
        classico = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
        if (classico / "Claude").is_dir():
            achados.append(classico / "Claude" / "claude_desktop_config.json")
        return achados or [classico / "Claude" / "claude_desktop_config.json"]

    if sys.platform == "darwin":
        return [Path.home() /
                "Library/Application Support/Claude/claude_desktop_config.json"]
    return [Path.home() / ".config/Claude/claude_desktop_config.json"]


def _python_desta_instalacao() -> str:
    """O interpretador do .venv, que é onde as dependências moram."""
    venv = RAIZ / (".venv/Scripts/python.exe" if sys.platform == "win32"
                   else ".venv/bin/python")
    return str(venv if venv.exists() else Path(sys.executable))


def _entrada(rotulo: str, padrao: str = "") -> str:
    sufixo = f" [{padrao}]" if padrao else ""
    resposta = input(f"  {rotulo}{sufixo}: ").strip()
    return resposta or padrao


def _bloco_do_servidor(token: str) -> dict:
    return {
        "command": _python_desta_instalacao().replace("\\", "/"),
        "args": [str(RAIZ / "mcp_local.py").replace("\\", "/")],
        "env": {"TRIAGEM_MCP_TOKEN": token},
    }


def _escrever_json(caminho: Path, dados: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _mesclar(caminho: Path, token: str, rotulo: str) -> str:
    """Preserva o que já estiver configurado; só acrescenta ou troca 'triagem'."""
    atual: dict = {}
    if caminho.exists():
        try:
            atual = json.loads(caminho.read_text(encoding="utf-8")) or {}
        except json.JSONDecodeError:
            reserva = caminho.with_suffix(
                f".quebrado-{datetime.now():%Y%m%d-%H%M%S}.json"
            )
            shutil.copy2(caminho, reserva)
            print(f"  ! {rotulo}: o arquivo estava ilegível; guardei uma cópia em"
                  f"\n    {reserva}\n    e vou escrever um novo.")
            atual = {}
        else:
            reserva = caminho.with_suffix(
                f".backup-{datetime.now():%Y%m%d-%H%M%S}.json"
            )
            shutil.copy2(caminho, reserva)

    servidores = atual.setdefault("mcpServers", {})
    ja_existia = "triagem" in servidores
    servidores["triagem"] = _bloco_do_servidor(token)
    _escrever_json(caminho, atual)

    outros = [n for n in servidores if n != "triagem"]
    detalhe = f"; mantive {len(outros)} outro(s) conector(es)" if outros else ""
    return f"{'atualizado' if ja_existia else 'configurado'}{detalhe}"


def main() -> int:
    print("\n  Conectar a Triagem ao Claude")
    print("  " + "-" * 40)

    from app import storage
    from app.mcp_oauth import criar_token_pessoal
    from app.security import conferir_senha

    storage.iniciar()

    conn = storage.conexao()
    quantos = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    if not quantos:
        print("\n  Nenhuma conta cadastrada ainda.")
        print("  Abra a Triagem no navegador (http://127.0.0.1:8000), crie sua")
        print("  conta e rode este programa de novo.\n")
        return 1

    print("\n  Entre com a conta que você usa na Triagem.\n")
    for tentativa in range(3):
        email = _entrada("E-mail")
        senha = getpass.getpass("  Senha: ")
        usuario = storage.buscar_usuario_por_email(email)
        if usuario and usuario["ativo"] and conferir_senha(senha, usuario["senha_hash"]):
            break
        restam = 2 - tentativa
        print(f"  E-mail ou senha incorretos."
              f"{f' Restam {restam} tentativa(s).' if restam else ''}\n")
    else:
        print("\n  Não consegui confirmar a conta. Nada foi alterado.\n")
        return 1

    token = criar_token_pessoal(usuario["id"], "Claude nesta máquina")
    org = storage.buscar_organizacao(usuario["org_id"])
    print(f"\n  Conta confirmada: {usuario['nome']} — {org['nome'] if org else ''}")

    alvos: list[tuple[str, Path]] = [
        ("Claude Desktop", caminho) for caminho in _configs_do_desktop()
    ]
    # O Claude Code lê um .mcp.json na pasta do projeto.
    alvos.append(("Claude Code (nesta pasta)", RAIZ / ".mcp.json"))

    print("\n  Escrevendo a configuração:\n")
    escreveu = False
    for rotulo, caminho in alvos:
        if rotulo.startswith("Claude Desktop") and not caminho.parent.exists():
            print(f"  - {rotulo}: não encontrado nesta máquina (pulado)")
            print("    Se instalar depois, rode este programa de novo.")
            continue
        try:
            estado = _mesclar(caminho, token, rotulo)
            print(f"  - {rotulo}: {estado}")
            print(f"    {caminho}")
            escreveu = True
        except OSError as exc:
            print(f"  - {rotulo}: não consegui escrever ({exc})")

    if not escreveu:
        print("\n  Nenhum Claude encontrado. Instale o Claude Desktop em")
        print("  https://claude.ai/download e rode este programa de novo.\n")
        return 1

    print("\n  " + "-" * 40)
    print("  Pronto. Feche e abra o Claude para ele carregar a Triagem.")
    print("  Depois é só pedir, no chat: \"liste minhas vagas na Triagem\".")
    print("\n  O Claude fala com o banco direto, então isso funciona mesmo com a")
    print("  Triagem fechada. Abra o atalho iniciar quando precisar enviar")
    print("  currículos, ver o relatório ou usar a tela normal.\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Cancelado. Nada foi alterado.\n")
        sys.exit(1)
