"""Conector MCP em modo local, por stdio.

É o caminho para o Claude Desktop e o Claude Code, que rodam o servidor como um
processo filho na sua máquina. Para o claude.ai, use o modo remoto: suba o
servidor web e aponte o conector para https://SEU-ENDERECO/mcp.

Configuração no Claude Desktop (arquivo claude_desktop_config.json):

    {
      "mcpServers": {
        "triagem": {
          "command": "C:/caminho/para/triagem/.venv/Scripts/python.exe",
          "args": ["C:/caminho/para/triagem/mcp_local.py"],
          "env": { "TRIAGEM_MCP_TOKEN": "cole-o-token-aqui" }
        }
      }
    }

O token sai de Configurações → Conector do Claude, dentro da Triagem.

Não há login neste modo: quem roda o processo já está na máquina do usuário. O
token é o que diz de qual conta e de qual organização são os dados — sem ele, o
servidor recusa tudo, para não haver como abrir a conta errada por engano.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def main() -> int:
    token = (os.getenv("TRIAGEM_MCP_TOKEN") or "").strip()
    if not token:
        print(
            "TRIAGEM_MCP_TOKEN não definido.\n\n"
            "Gere um token em Configurações → Conector do Claude, na Triagem, e\n"
            "coloque-o no campo 'env' da configuração do Claude Desktop.",
            file=sys.stderr,
        )
        return 1

    from app import storage
    from app.mcp_oauth import contexto_do_token
    from app.mcp_servidor import definir_contexto_local, mcp

    storage.iniciar()
    contexto = contexto_do_token(token)
    if not contexto:
        print(
            "Token inválido, vencido ou revogado.\n"
            "Gere outro em Configurações → Conector do Claude.",
            file=sys.stderr,
        )
        return 1

    definir_contexto_local(contexto)
    # stderr, nunca stdout: no stdio, a saída padrão é o canal do protocolo.
    print(
        f"Triagem conectada como {contexto['nome']} "
        f"(organização {contexto['org_id']}).",
        file=sys.stderr,
    )
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
