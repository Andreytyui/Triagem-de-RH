"""As mensagens de erro de validação que o usuário lê.

O 422 do Pydantic é uma lista de objetos em inglês. Antes daqui, só o caso de
e-mail tinha tradução — todo o resto vazava para a tela em inglês, e no formato
`campo: msg` misturado com frase completa quando havia mais de um erro.
"""
from __future__ import annotations

from .comum import Placar

# Trechos que só aparecem se a mensagem crua do Pydantic escapar para a tela.
# Conferidos empiricamente contra o Pydantic instalado (ver `versao_conferida`
# abaixo, que imprime a versão junto do resultado): se um upgrade mudar a
# redação da biblioteca, esta lista para de pegar e o teste passa de graça —
# a versão no relatório é a primeira pista de por quê.
INGLES = ("String should", "Input should", "Field required", "valid email",
          "at least", "at most", "unable to parse", "special-use")


def _erros(modelo, dados: dict) -> list[dict]:
    from pydantic import ValidationError
    try:
        modelo(**dados)
    except ValidationError as exc:
        return exc.errors()
    raise AssertionError(f"{modelo.__name__} aceitou dados inválidos: {dados}")


def rodar(placar: Placar) -> None:
    from app.main import FRASES_DE_VALIDACAO, _frase_de_validacao
    from app.models import (ConfigOrganizacao, Criterio, DecisaoRecrutador,
                            NovaConta, NovaVaga, Rubrica)

    print("\nMensagens de erro")

    # Um caso real por tipo de erro que os nossos modelos conseguem produzir.
    CASOS = [
        ("e-mail sem @", NovaConta,
         {"organizacao": "Empresa", "nome": "Fulano", "email": "nao-e-email", "senha": "x"}),
        ("e-mail de domínio reservado", NovaConta,
         {"organizacao": "Empresa", "nome": "Fulano", "email": "a@conferencia.local", "senha": "x"}),
        ("curto demais", NovaConta,
         {"organizacao": "E", "nome": "F", "email": "a@b.com", "senha": "x"}),
        ("campo faltando", NovaConta, {}),
        ("longo demais", NovaVaga, {"titulo": "t" * 200, "descricao": "d" * 50}),
        ("fora da lista", DecisaoRecrutador, {"decisao": "talvez"}),
        ("não é número", ConfigOrganizacao, {"retencao_dias": "muitos"}),
        ("tipo errado", NovaVaga, {"titulo": 123, "descricao": None}),
        ("acima do máximo", Criterio,
         {"id": "x", "nome": "n", "descricao": "d", "peso": 500}),
        # Item aninhado numa lista: chega pela rota real de aprovar rubrica, e o
        # `loc` vem como ('criterios', 0, 'id') — foi por aqui que passou o campo
        # `id` sem rótulo, achado pela Lupa.
        ("item de lista incompleto", Rubrica,
         {"cargo": "x", "senioridade": "y",
          "criterios": [{"nome": "n", "descricao": "d", "peso": 50}]}),
    ]

    def nada_em_ingles():
        """O defeito principal: 'String should have at least 2 characters' na tela."""
        vistos = set()
        for rotulo, modelo, dados in CASOS:
            for erro in _erros(modelo, dados):
                frase = _frase_de_validacao(erro)
                vistos.add(erro["type"])
                for trecho in INGLES:
                    assert trecho not in frase, (
                        f"[{rotulo}] mensagem do Pydantic vazou para a tela: {frase!r}"
                    )
                assert frase.endswith("."), f"[{rotulo}] não é frase: {frase!r}"
                assert ": " not in frase, (
                    f"[{rotulo}] saiu no formato cru 'campo: msg': {frase!r}"
                )
                assert "{" not in frase, (
                    f"[{rotulo}] sobrou marcador de template não substituído: {frase!r}"
                )
        return f"{len(vistos)} tipos de erro do Pydantic, todos em português"

    placar.rodar("Nenhuma mensagem de validação chega ao usuário em inglês",
                 nada_em_ingles)

    def contexto_ausente_nao_derruba():
        """Uma versão nova do Pydantic pode renomear as chaves de contexto. Frase
        pior é aceitável; 500 dentro do próprio tratador de erro não é."""
        for tipo in FRASES_DE_VALIDACAO:
            frase = _frase_de_validacao({"type": tipo, "loc": ("body", "nome"), "ctx": {}})
            assert frase and "{" not in frase, f"{tipo} quebrou sem contexto: {frase!r}"

        # E um tipo que ainda não existe cai na rede de segurança, não numa exceção.
        desconhecido = _frase_de_validacao(
            {"type": "tipo_que_ainda_nao_existe", "loc": ("body", "email")})
        assert "e-mail" in desconhecido, desconhecido
        return f"{len(FRASES_DE_VALIDACAO)} frases + tipo desconhecido, nenhuma exceção"

    placar.rodar("Tipo ou contexto inesperado do Pydantic não derruba o tratador",
                 contexto_ausente_nao_derruba)

    def todo_campo_tem_rotulo():
        """Sem rótulo, a frase sai com o nome cru do campo ("Falta preencher id.")
        — o mesmo defeito de outra cara. A Lupa achou `id` faltando por inspeção;
        isto varre os modelos para o próximo não depender de alguém reparar."""
        import typing

        from pydantic import BaseModel

        from app.main import CAMPOS_EM_PORTUGUES
        from app.models import (Credenciais, NovoUsuario, PedidoRecuperacao,
                                RedefinicaoSenha, TrocaSenha)
        from app.rotas_mcp import NovoTokenMCP

        # Tudo que um cliente consegue mandar no corpo de uma requisição.
        raizes = [NovaConta, Credenciais, TrocaSenha, PedidoRecuperacao,
                  RedefinicaoSenha, NovoUsuario, ConfigOrganizacao, NovaVaga,
                  DecisaoRecrutador, Rubrica, NovoTokenMCP]

        vistos: set = set()
        campos: dict[str, set[str]] = {}

        def andar(modelo) -> None:
            if modelo in vistos:
                return
            vistos.add(modelo)
            for nome, campo in modelo.model_fields.items():
                campos.setdefault(nome, set()).add(modelo.__name__)
                for arg in (campo.annotation, *typing.get_args(campo.annotation)):
                    if isinstance(arg, type) and issubclass(arg, BaseModel):
                        andar(arg)

        for modelo in raizes:
            andar(modelo)

        sem_rotulo = {n: sorted(m) for n, m in campos.items()
                      if n not in CAMPOS_EM_PORTUGUES}
        assert not sem_rotulo, (
            f"campos que sairiam com o nome cru na tela: {sem_rotulo}"
        )
        return f"{len(campos)} campos em {len(vistos)} modelos, todos com rótulo"

    placar.rodar("Todo campo que o cliente pode enviar tem rótulo em português",
                 todo_campo_tem_rotulo)

    def versao_conferida():
        """A lista INGLES foi conferida contra uma versão específica do Pydantic."""
        import pydantic
        return f"trechos em inglês conferidos contra Pydantic {pydantic.VERSION}"

    placar.rodar("Versão do Pydantic contra a qual a tradução foi conferida",
                 versao_conferida)

    def frase_unica_pela_http():
        """A camada que o navegador realmente vê: várias falhas viram frases
        emendadas, não a lista crua nem `campo: msg` separado por ponto e vírgula."""
        import contextlib

        from fastapi.testclient import TestClient

        from app.main import app

        # Sem `with`: abrir o lifespan de novo estoura no gerenciador de sessão
        # do MCP, que só roda uma vez por processo. A rota de validação não
        # depende de startup.
        with contextlib.nullcontext(TestClient(app)) as cliente:
            resp = cliente.post("/api/auth/registrar", json={
                "organizacao": "E", "nome": "F", "email": "nao-e-email", "senha": "x",
            })
            assert resp.status_code == 422, resp.status_code
            detalhe = resp.json()["detail"]
            assert isinstance(detalhe, str), f"veio {type(detalhe)}, não frase"
            for trecho in INGLES:
                assert trecho not in detalhe, detalhe
            assert ";" not in detalhe, f"ainda emenda com ponto e vírgula: {detalhe}"
            assert "Esse e-mail não foi aceito" in detalhe, detalhe
            assert "pelo menos 2 caracteres" in detalhe, detalhe
        return detalhe

    placar.rodar("Erro de validação chega à tela como frase, pela rota real",
                 frase_unica_pela_http)
