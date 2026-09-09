"""Redefine a senha de um usuário pela linha de comando.

    python -m app.senha alguem@empresa.com

É o caminho de volta na instalação local — aquela em que o recrutador roda a
Triagem na própria máquina e liga o Claude Desktop por stdio. Ali não há e-mail
para mandar, nem precisa haver: quem esqueceu a senha é dono do computador onde
o banco está.

No modo hospedado este comando continua existindo e serve para o suporte, mas o
caminho normal do cliente é o link por e-mail — ele não tem shell no servidor.

O efeito é exatamente o mesmo do link: a senha troca, os pedidos de recuperação
pendentes morrem, as sessões abertas caem e os tokens do conector são revogados.
"""
from __future__ import annotations

import getpass
import sys

from . import storage
from .security import criticar_senha, hash_senha


def redefinir(email: str, senha: str) -> tuple[bool, str]:
    """Aplica a senha nova. Devolve (deu certo, mensagem)."""
    usuario = storage.buscar_usuario_por_email(email)
    if not usuario:
        return False, f"não existe conta com o e-mail {email}"

    problema = criticar_senha(senha)
    if problema:
        return False, problema

    storage.atualizar_usuario(usuario["id"], senha_hash=hash_senha(senha))
    storage.invalidar_recuperacoes_do_usuario(usuario["id"])
    storage.encerrar_sessoes_do_usuario(usuario["id"])
    revogados = storage.mcp_revogar_do_usuario(usuario["id"])
    storage.registrar_auditoria(
        usuario["org_id"], usuario["id"], "senha.redefinida",
        detalhe={"por": "linha de comando"},
    )

    aviso = (
        f" {revogados} conexão(ões) do Claude foram revogadas; "
        "reconecte o conector."
        if revogados else ""
    )
    return True, f"senha de {usuario['nome']} <{email}> redefinida.{aviso}"


def main(argumentos: list[str]) -> int:
    if len(argumentos) != 1 or argumentos[0] in {"-h", "--help"}:
        print(__doc__.strip())
        return 1

    email = argumentos[0].strip().lower()
    storage.iniciar()

    if not storage.buscar_usuario_por_email(email):
        # Aqui não há motivo para esconder: quem roda isto já está dentro da
        # máquina e tem o banco na mão.
        print(f"não existe conta com o e-mail {email}", file=sys.stderr)
        return 1

    try:
        senha = getpass.getpass("Senha nova (não aparece na tela): ")
        repetida = getpass.getpass("Repita a senha: ")
    except (EOFError, KeyboardInterrupt):
        print("\ncancelado", file=sys.stderr)
        return 1

    if senha != repetida:
        print("as duas senhas não conferem", file=sys.stderr)
        return 1

    ok, mensagem = redefinir(email, senha)
    print(mensagem, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
