"""Onde a cor pode morar.

Regra da Pigmento, escrita como teste porque três vezes em duas conversas um
sítio de cor apareceu por inspeção manual — e nas três o escopo estava certo e
a varredura, incompleta. Regra que depende de alguém lembrar não é regra.

Hoje existe UM arquivo onde a cor pode ser escrita: `static/tokens.css`. Todo o
resto — `styles.css`, o JavaScript e as três folhas embutidas nos documentos
Python — consome de lá por `var()`. A dívida das paletas paralelas, que estes
testes seguravam para não crescer, foi paga: os tetos agora são zero.
"""
from __future__ import annotations

import re
from pathlib import Path

from .comum import Placar

RAIZ = Path(__file__).resolve().parent.parent
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")

# Eram 40 hexes digitados à mão em três paletas paralelas. Zero é o estado
# correto, e o teto existe agora para nenhuma delas voltar.
DIVIDA_PYTHON = {
    "app/shortlist.py": 0,
    "app/relatorio.py": 0,
    "app/rotas_mcp.py": 0,
}


def _hexes(caminho: Path) -> list[tuple[int, str]]:
    achados = []
    for n, linha in enumerate(caminho.read_text(encoding="utf-8").split("\n"), 1):
        if HEX.search(linha):
            achados.append((n, linha.strip()))
    return achados


def rodar(placar: Placar) -> None:
    print("\nIdentidade visual")

    def so_o_tokens_tem_cor():
        fora = []
        for css in sorted((RAIZ / "static").glob("*.css")):
            if css.name == "tokens.css":
                continue
            fora += [f"{css.name}:{n}: {t}" for n, t in _hexes(css)]
        assert not fora, (
            "hex fora do tokens.css — a próxima troca de paleta vira caçada:\n  "
            + "\n  ".join(fora))
        # E o tokens.css tem de ser carregado ANTES do styles.css: sem isso as
        # variáveis não existem quando as regras que as usam são lidas.
        html = (RAIZ / "static" / "index.html").read_text(encoding="utf-8")
        assert -1 < html.find("tokens.css") < html.find("styles.css"), (
            "tokens.css precisa vir antes do styles.css no index.html")
        return "toda cor de static/ mora no tokens.css"

    placar.rodar("Só o tokens.css guarda cor", so_o_tokens_tem_cor)

    def js_sem_cor():
        achados = []
        for js in sorted((RAIZ / "static").glob("*.js")):
            achados += [f"{js.name}:{n}: {t}" for n, t in _hexes(js)]
        assert not achados, (
            "cor em JavaScript — quem troca tom não deveria precisar abrir JS:\n  "
            + "\n  ".join(achados))
        return "nenhum hex em static/*.js"

    placar.rodar("JavaScript não carrega cor", js_sem_cor)

    def rampa_no_css():
        tokens = (RAIZ / "static" / "tokens.css").read_text(encoding="utf-8")
        estilos = (RAIZ / "static" / "styles.css").read_text(encoding="utf-8")
        for n in range(1, 8):
            assert f"--petroleo-{n}:" in tokens, f"--petroleo-{n} sumiu do tokens.css"
            assert f'[data-tom="{n}"]' in estilos, f'nenhuma regra para data-tom="{n}"'
        js = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")
        assert "tomDe" in js, "o JS deveria calcular o índice do tom"
        return "os sete tons vivem no tokens.css; o JS só numera"

    placar.rodar("A rampa mora no CSS, não no JavaScript", rampa_no_css)

    def documentos_consomem_a_folha_canonica():
        """Os três documentos EMBUTEM o tokens.css — embutem, não referenciam
        por <link>: o shortlist é salvo e reenviado por e-mail, e precisa
        continuar correto fora do nosso servidor."""
        from app import estilo

        for arquivo in ("shortlist.py", "relatorio.py", "rotas_mcp.py"):
            fonte = (RAIZ / "app" / arquivo).read_text(encoding="utf-8")
            assert "estilo.folha" in fonte, f"{arquivo} não embute a folha canônica"

        folha = estilo.folha(documento=True)
        assert "--petroleo-1:" in folha, "a rampa não chegou ao documento"
        assert "--papel-documento:" in folha, "falta a superfície do impresso"
        assert "--papel: var(--papel-documento)" in folha, "faltam os apelidos"
        # A tela usa a superfície da tela, não a do papel.
        assert "--papel: var(--papel-documento)" not in estilo.folha(), (
            "a folha de tela não deveria trazer os apelidos do impresso")
        return "tokens embutidos, não linkados"

    placar.rodar("Os documentos consomem a folha canônica",
                 documentos_consomem_a_folha_canonica)

    def divida_python_nao_volta():
        cresceu = []
        for rel, teto in DIVIDA_PYTHON.items():
            achados = _hexes(RAIZ / rel)
            if len(achados) > teto:
                cresceu.append(
                    f"{rel}: {len(achados)} hexes, o teto é {teto} — "
                    + "; ".join(f"linha {n}" for n, _ in achados[:4]))
        assert not cresceu, (
            "paleta digitada à mão voltou a um documento:\n  " + "\n  ".join(cresceu))
        return "zero hexes nos três documentos, e o teto não deixa voltar"

    placar.rodar("A paleta não volta para dentro dos documentos",
                 divida_python_nao_volta)

    def nenhum_token_indefinido():
        """Todo var(--x) tem de estar definido na folha que AQUELE documento
        recebe.

        Este é o modo real de quebrar uma consolidação de paleta, e ele é
        silencioso: quando um token some, `color: var(--sumido)` não vira erro
        nem some da tela — é inválido no valor computado, e `color` é herdada,
        então o texto cai para a cor do pai. Nada desaparece; a HIERARQUIA é
        que colapsa, e num consentimento isso muda o peso relativo entre
        aceitar e recusar.

        Aconteceu de verdade: ao tirar o :root do rotas_mcp.py sobraram quatro
        `var(--fraca)` sem dono, e a suíte inteira passou verde por cima disso.
        Foi a Vitral que achou, conferindo à mão.
        """
        import re

        from app import estilo, relatorio, rotas_mcp, shortlist

        # (nome, folha do documento, recebe os apelidos do impresso?)
        superficies = [
            ("shortlist", shortlist.ESTILO, True),
            ("relatorio", relatorio.ESTILO, True),
            ("rotas_mcp", rotas_mcp.ESTILO, False),
            ("tela", (RAIZ / "static" / "styles.css").read_text(encoding="utf-8"), False),
        ]
        quebrados = []
        for nome, folha_local, documento in superficies:
            css = estilo.folha(documento=documento) + folha_local
            definidos = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
            usados = set(re.findall(r"var\((--[a-z0-9-]+)", css))
            faltando = sorted(usados - definidos)
            if faltando:
                quebrados.append(f"{nome}: {', '.join(faltando)}")
        assert not quebrados, (
            "token usado e não definido — o texto vai herdar a cor do pai em "
            "silêncio:\n  " + "\n  ".join(quebrados))
        return f"{len(superficies)} superfícies, nenhum var() órfão"

    placar.rodar("Nenhuma superfície usa token que não recebe",
                 nenhum_token_indefinido)

    def contorno_e_regua_nao_trocam_de_papel():
        """A regra do item 7, que até agora só existia em prosa.

        `--regua-forte` é separação decorativa e não tem piso de contraste.
        `--contorno` é o limite de um controle e tem piso de 3:1 (WCAG 1.4.11).
        Os dois são cinzas parecidos, e a diferença entre eles é de SENTIDO —
        que é exatamente o tipo de regra que um teste de "onde a cor mora" não
        alcança: o valor está no lugar certo, usado com o significado errado.

        O alvo é estreito de propósito: os seletores em que a borda é a única
        coisa dizendo onde o controle começa. Se um deles voltar para o
        `--regua-forte`, o contraste cai de 3.96:1 para 1.85:1 contra o painel
        e a 1.4.11 deixa de ser cumprida, sem nada quebrar na tela.
        """
        import re

        CONTROLES = ["input", "textarea", "select", ".btn-secundario",
                     ".solta", ".filtro", ".decisao-btn"]
        css = (RAIZ / "static" / "styles.css").read_text(encoding="utf-8")
        # Sem tirar os comentários, o pedaço capturado como "seletor" começa no
        # `}` anterior e traz o comentário de seção junto — e aí `.solta` deixa
        # de casar por estar precedido de `/* ---------- upload ---------- */`.
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

        def e_controle(parte: str) -> str | None:
            parte = parte.strip()
            for ctrl in CONTROLES:
                if re.match(re.escape(ctrl) + r"(?![\w-])", parte):
                    return ctrl
            return None

        erradas, com_contorno = [], set()
        for seletor, corpo in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            atingidos = {c for p in seletor.split(",") if (c := e_controle(p))}
            if not atingidos:
                continue
            if "--regua-forte" in corpo:
                erradas.append(f"{seletor.strip()[:60]}: usa --regua-forte")
            if "--contorno" in corpo:
                com_contorno |= atingidos

        assert not erradas, (
            "limite de controle desenhado com separador decorativo — o "
            "contraste cai de 3.96:1 para 1.85:1 e ninguém vê quebrar:\n  "
            + "\n  ".join(erradas))
        faltando = sorted(set(CONTROLES) - com_contorno)
        assert not faltando, (
            f"controle sem --contorno em regra nenhuma: {faltando}")
        return f"{len(CONTROLES)} controles com borda de limite, nenhum com separador"

    placar.rodar("Limite de controle e separador não trocam de papel",
                 contorno_e_regua_nao_trocam_de_papel)

    def retido_e_ilegivel_nao_se_misturam():
        """As três amarras da Vitral, numa asserção cada.

        1. o servidor manda o booleano `retido` junto do `erro`;
        2. a tela separa pelo BOOLEANO, nunca por substring do motivo — a frase
           é microcopy da Pigmento e vai ser reescrita;
        3. faixa serve ao filtro, ao agrupamento E às contagens; partir `erro`
           em dois obriga a conferir os três, senão "o chip diz 8 e o grupo
           mostra 3" — que é o mesmo bug com outra roupa.
        """
        import re

        js = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")

        i = js.find("function faixaDe")
        corpo = js[i:js.find(chr(10) + "}", i)]
        assert "r.retido" in corpo, "faixaDe deveria separar pelo booleano"
        for texto in ("erro.includes", "indexOf", "match(", "Para você ler",
                      "Peça o currículo"):
            assert texto not in corpo, (
                f"faixaDe está olhando texto ({texto!r}) em vez do booleano")

        # Os dois grupos existem, e "Para você ler" vem antes.
        assert js.find('"Para você ler"') != -1, "falta o grupo dos retidos"
        assert js.find('"Peça o currículo"') != -1, "falta o grupo de quem não tem currículo"
        assert js.find('"Não foi possível ler"') == -1, (
            "rótulo antigo: ele mente no caso de texto insuficiente, onde a "
            "extração funcionou e o que faltou era currículo")
        assert js.find('["retido"') < js.find('["erro"'), (
            "'Para você ler' precisa vir antes de 'Não foi possível ler'")

        # A métrica é condicional: sem retido, ela não existe.
        assert 'faixaDe(r) === "retido"' in js, "a métrica não conta pela faixa"
        assert "paraLer ?" in js, "a métrica deveria ser condicional"

        # E o servidor precisa mandar o campo.
        storage = (RAIZ / "app" / "storage.py").read_text(encoding="utf-8")
        assert 'd["retido"] = bool(parse.get("retido"))' in storage, (
            "ranking() não expõe o booleano")
        return "booleano no servidor, faixa dividida, grupos e métrica de acordo"

    placar.rodar("Retido e ilegível não caem no mesmo balde",
                 retido_e_ilegivel_nao_se_misturam)
