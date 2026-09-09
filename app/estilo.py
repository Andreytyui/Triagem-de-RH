"""A paleta, lida do arquivo que a identidade visual edita.

Os documentos que este servidor gera — shortlist, relatório e a tela de
consentimento do conector — são HTML com CSS embutido, e cada um tinha a sua
própria cópia da paleta digitada à mão. Quatro cópias do mesmo valor é uma
garantia de que um dia elas discordam, e trocar a paleta virava caçada.

Aqui a folha canônica é lida de `static/tokens.css` e embutida nos documentos.
Embutida, e não referenciada por `<link>`: o shortlist é salvo e reenviado por
e-mail, e precisa continuar correto fora do nosso servidor.

Sem etapa de build: o arquivo é CSS puro, editável por quem cuida da
identidade, e é lido uma vez quando o processo sobe.
"""
from __future__ import annotations

from functools import lru_cache

from .config import BASE_DIR

TOKENS = BASE_DIR / "static" / "tokens.css"

# As folhas dos documentos foram escritas com nomes curtos e com `--papel`
# valendo branco. Em vez de reescrever o corpo delas — muitas linhas, num
# documento que vai à mesa de um cliente —, os nomes antigos apontam para os
# tokens canônicos. Nenhum valor é redigitado; se a identidade quiser convergir
# os nomes, este bloco desaparece numa troca mecânica.
APELIDOS_DE_DOCUMENTO = """
:root {
  --papel: var(--papel-documento);
  --media: var(--tinta-media);
  --fraca: var(--tinta-fraca);
}
"""


@lru_cache(maxsize=2)
def folha(documento: bool = False) -> str:
    """O conteúdo de tokens.css, pronto para entrar num `<style>`.

    `documento=True` acrescenta os apelidos das folhas impressas.
    """
    css = TOKENS.read_text(encoding="utf-8")
    return css + APELIDOS_DE_DOCUMENTO if documento else css
