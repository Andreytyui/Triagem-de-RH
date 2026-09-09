"""Diagnóstico comparativo: a conta tem de fechar.

A frase comparativa só se sustenta por uma coisa — o recrutador poder conferir
de olho que os números somam a diferença de nota que ele já está vendo. Se não
somarem, a frase perde a razão de existir. Estes testes são sobre isso, e sobre
os dois casos em que a aritmética mentiria se ninguém dissesse nada.
"""
from __future__ import annotations

import random

from .comum import Placar


def rodar(placar: Placar) -> None:
    from app.models import ResultadoScore, Rubrica
    from app.pontuacao import calcular_score, decompor_diferenca

    print("\nDiagnóstico comparativo")

    def rubrica_de(*pesos: int) -> Rubrica:
        return Rubrica.model_validate({
            "cargo": "Analista", "senioridade": "pleno",
            "criterios": [
                {"id": f"c{i}", "nome": f"Critério {i}", "peso": p,
                 "descricao": "d"}
                for i, p in enumerate(pesos, start=1)
            ],
        })

    def resultado_de(*notas) -> ResultadoScore:
        return ResultadoScore.model_validate({
            "criterios": [{"criterio_id": f"c{i}", "nota": n, "evidencia": "e"}
                          for i, n in enumerate(notas, start=1)
                          if n is not None],
            "resumo": "resumo de teste",
            "recomendacao": "chamar",
        })

    def soma_fecha_no_caso_da_spec():
        # O exemplo da spec: os deltas exibidos somam a diferença de nota.
        r = rubrica_de(40, 35, 25)
        a = resultado_de(9, 9, 6)
        b = resultado_de(8, 6, 8)
        d = decompor_diferenca(a, b, r)
        exibido = round(sum(c["delta"] for c in d["criterios"])
                        + (d["resto"]["delta"] if d["resto"] else 0), 1)
        assert exibido == d["diferenca"], (
            f"exibido {exibido} != diferença {d['diferenca']}")
        return f"diferença {d['diferenca']} = {exibido}"

    placar.rodar("Os deltas exibidos somam a diferença de nota",
                 soma_fecha_no_caso_da_spec)

    def soma_fecha_sempre():
        # A propriedade não pode valer só no exemplo bonito: 400 rubricas e
        # notas aleatórias, incluindo critério ausente e pesos desiguais.
        rng = random.Random(20260909)
        for _ in range(400):
            n = rng.randint(2, 6)
            pesos = [rng.randint(1, 40) for _ in range(n)]
            # normalizar como o app faz antes de gravar
            total = sum(pesos)
            pesos = [round(p * 100 / total) for p in pesos]
            pesos[0] += 100 - sum(pesos)
            if pesos[0] <= 0:
                continue
            r = rubrica_de(*pesos)
            a = resultado_de(*[rng.choice([None, *range(11)]) for _ in range(n)])
            b = resultado_de(*[rng.choice([None, *range(11)]) for _ in range(n)])
            d = decompor_diferenca(a, b, r)
            exibido = round(sum(c["delta"] for c in d["criterios"])
                            + (d["resto"]["delta"] if d["resto"] else 0), 1)
            assert exibido == d["diferenca"], (
                f"pesos={pesos} exibido={exibido} diferença={d['diferenca']}")
        return "400 combinações aleatórias, a conta fecha em todas"

    placar.rodar("A conta fecha para qualquer rubrica e qualquer nota",
                 soma_fecha_sempre)

    def rotulo_do_resto_nao_mente():
        # Dois critérios, os dois nomeados: o que sobra é resíduo, não "outros".
        r = rubrica_de(50, 50)
        a = resultado_de(9, 4)
        b = resultado_de(4, 9)
        d = decompor_diferenca(a, b, r)
        if d["resto"]:
            assert d["resto"]["rotulo"] == "arredondamento", (
                "com todos os critérios nomeados o resto é resíduo, não 'outros'")
        # Três critérios com um fora dos nomeados: aí é "outros" de verdade.
        r3 = rubrica_de(40, 35, 25)
        d3 = decompor_diferenca(resultado_de(9, 9, 9), resultado_de(2, 2, 2), r3)
        assert d3["resto"] and d3["resto"]["rotulo"] == "outros", (
            f"esperava 'outros', veio {d3['resto']}")
        return "'outros' só quando há critério não nomeado"

    placar.rodar("O rótulo do resto diz o que aquilo é", rotulo_do_resto_nao_mente)

    def unidade_e_ponto_de_nota_final():
        # A armadilha da spec: o número é em pontos da nota final (0-100), não
        # em pontos de nota por critério (0-10).
        r = rubrica_de(40, 35, 25)
        a = resultado_de(10, 0, 0)
        b = resultado_de(0, 0, 0)
        d = decompor_diferenca(a, b, r)
        assert d["diferenca"] == 40.0, d["diferenca"]
        assert d["criterios"][0]["delta"] == 40.0, (
            f"delta veio {d['criterios'][0]['delta']}; se veio 10, está em nota "
            "por critério e não em pontos da nota final")
        return "10 pontos num critério de peso 40 valem 40 na nota final"

    placar.rodar("Os números saem em pontos da nota final, não de 0 a 10",
                 unidade_e_ponto_de_nota_final)

    def criterio_ausente_e_reportado():
        # Uma coisa é o candidato ser pior; outra é não termos a resposta.
        r = rubrica_de(40, 35, 25)
        a = resultado_de(9, 9, 9)
        b = resultado_de(9, None, 9)
        d = decompor_diferenca(a, b, r)
        assert "Critério 2" in d["faltantes_b"], d["faltantes_b"]
        assert not d["faltantes_a"], d["faltantes_a"]
        return "a lacuna aparece separada da diferença"

    placar.rodar("Critério não respondido é reportado, não escondido no número",
                 criterio_ausente_e_reportado)

    def empate_e_praticamente_identicos():
        r = rubrica_de(50, 50)
        # Mesma nota por caminhos diferentes: diferença 0, critérios nomeados.
        d = decompor_diferenca(resultado_de(9, 3), resultado_de(3, 9), r)
        assert d["diferenca"] == 0.0, d["diferenca"]
        assert d["criterios"], "empate com caminhos diferentes deve nomear critérios"
        # Iguais em tudo: nada a dizer.
        igual = decompor_diferenca(resultado_de(7, 7), resultado_de(7, 7), r)
        assert igual["identicos"], igual
        assert not igual["criterios"] and not igual["resto"], igual
        return "empate nomeia critérios; idênticos não dizem nada"

    placar.rodar("Empate e 'praticamente idênticos' são casos diferentes",
                 empate_e_praticamente_identicos)

    def posicao_exibida_e_local_frase_e_global():
        """Decisão do dono do produto: a posição EXIBIDA é a sequencial local,
        sem buracos, em todo lugar onde já existe. O número global vive só
        dentro da frase, e sempre qualificado por extenso — nunca solto, para
        não ser confundido com a posição ao lado."""
        from app import mcp_servidor as ms
        from app.pontuacao import posicoes

        r = rubrica_de(60, 40)

        def cand(cid, n1, n2):
            # score sai da própria rubrica, para a diferença ser real e não
            # um número que eu escrevi à mão do lado das notas.
            res = resultado_de(n1, n2)
            from app.pontuacao import calcular_score
            return {"candidato_id": cid, "score_final": calcular_score(res, r),
                    "estagio": "avaliado", "confianca": "alta",
                    "origem_texto": "direto", "decisao": "sem_decisao",
                    "resultado": res.model_dump()}

        # Gaps pequenos de propósito: acima de COMPARACAO_LIMIAR a linha
        # não sai, e o teste mediria a regra de fragilidade em vez da frase.
        todas = [cand("a", 9, 9), cand("b", 8, 8), cand("c", 8, 6), cand("d", 7, 6)]
        mapa = posicoes(todas)
        assert mapa == {"a": 1, "b": 2, "c": 3, "d": 4}, mapa

        # Sem filtro: o vizinho geral de "d" é "c", que é a linha logo acima
        # na saída. Forma curta.
        curta = ms._linha_comparativa(todas[3], todas, mapa, r,
                                      anterior_visivel="c",
                                      visiveis={"a", "b", "c", "d"})
        assert "do anterior" in curta, f"esperava forma curta: {curta!r}"
        assert "fora deste filtro" not in curta, curta

        # Visão filtrada escondendo "c": o vizinho continua sendo "c" (é sempre
        # o do ranking geral, nunca o do recorte), mas agora a frase precisa
        # avisar que o filtro o escondeu.
        # "c" fora do conjunto visível: o filtro realmente o escondeu.
        longa = ms._linha_comparativa(todas[3], todas, mapa, r,
                                      anterior_visivel="a", visiveis={"a", "d"})
        assert "fora deste filtro" in longa, f"esperava forma qualificada: {longa!r}"
        assert "ranking geral" in longa, longa

        # Terceiro caso, achado pelo Chave: eliminado é gravado com
        # score_final=0.0 (não NULL), ordena junto dos pontuados e pode cair
        # ENTRE dois deles. Aí o vizinho não é a linha de cima, mas nenhum
        # filtro escondeu ninguém — a frase não pode alegar filtro.
        intercalado = ms._linha_comparativa(
            todas[3], todas, mapa, r, anterior_visivel="elim",
            visiveis={"a", "b", "c", "d", "elim"})
        assert "ranking geral" in intercalado, intercalado
        assert "fora deste filtro" not in intercalado, (
            "alegou filtro onde o que separa é uma linha sem posição: "
            f"{intercalado!r}")

        # Nenhuma das três entrega identidade de quem o filtro escondeu, e
        # nenhuma usa número solto que se confunda com a posição local.
        for frase in (curta, longa, intercalado):
            assert "#" not in frase, f"número solto com #: {frase!r}"
            for oculto in ("a", "b", "c"):
                assert f"candidato {oculto}" not in frase, frase
        return "curta, qualificada, e sem alegar filtro onde não há"

    placar.rodar("Referência do vizinho: curta quando visível, qualificada quando não",
                 posicao_exibida_e_local_frase_e_global)

    def vizinhanca_nao_entrega_identidade():
        """Regra não negociável da spec: o vizinho é sempre o nº da posição,
        nunca nome nem candidato_id — inclusive quando a chamada veio com
        incluir_contato=True. O contato pedido é de UM candidato; a comparação
        não pode ser a porta lateral que entrega a identidade de outro."""
        from app import mcp_servidor as ms
        from app.pontuacao import posicoes

        r = rubrica_de(60, 40)

        def cand(cid, nome, n1, n2, estagio="avaliado"):
            res = resultado_de(n1, n2)
            from app.pontuacao import calcular_score
            return {"candidato_id": cid, "nome": nome, "estagio": estagio,
                    "score_final": calcular_score(res, r), "confianca": "alta",
                    "origem_texto": "direto", "decisao": "sem_decisao",
                    "contato": {"email": f"{cid}@exemplo.com"},
                    "resultado": res.model_dump()}

        todas = [cand("aaa111", "Ana Souza", 9, 9),
                 cand("bbb222", "Bruno Martins", 8, 8),
                 cand("ccc333", "Carla Nogueira", 8, 6)]
        mapa = posicoes(todas)
        bloco = ms._bloco_vizinhanca(todas[1], todas, mapa, r)

        assert "Vizinhança no ranking geral" in bloco, bloco
        assert "nº 2" in bloco, f"não disse a própria posição: {bloco!r}"
        # Os dois lados, e a distância decomposta em cada um.
        assert "à frente" in bloco and "atrás" in bloco, bloco
        # Nada que identifique os vizinhos.
        for proibido in ("aaa111", "ccc333", "Ana", "Souza", "Carla",
                         "Nogueira", "@exemplo.com"):
            assert proibido not in bloco, (
                f"'{proibido}' vazou na vizinhança: {bloco!r}")
        return "vizinhos só por nº; nenhum nome, id ou contato atravessa"

    placar.rodar("A vizinhança não entrega a identidade de ninguém",
                 vizinhanca_nao_entrega_identidade)

    def vizinhanca_nos_extremos_e_fora_do_ranking():
        from app import mcp_servidor as ms
        from app.pontuacao import calcular_score, posicoes

        r = rubrica_de(60, 40)

        def cand(cid, n1, n2, estagio="avaliado", score=None):
            res = resultado_de(n1, n2)
            return {"candidato_id": cid, "nome": "x", "estagio": estagio,
                    "score_final": score if score is not None
                    else calcular_score(res, r),
                    "confianca": "alta", "origem_texto": "direto",
                    "decisao": "sem_decisao", "contato": {},
                    "resultado": res.model_dump()}

        todas = [cand("a", 9, 9), cand("b", 8, 8)]
        mapa = posicoes(todas)
        topo = ms._bloco_vizinhanca(todas[0], todas, mapa, r)
        assert "atrás" in topo and "à frente" not in topo, (
            f"o nº 1 não tem ninguém à frente: {topo!r}")

        # Um candidato só: não há vizinhança, e isso não é erro.
        sozinho = [cand("z", 7, 7)]
        assert ms._bloco_vizinhanca(sozinho[0], sozinho, posicoes(sozinho), r) == ""

        # Cortado no eliminatório: não ocupa lugar, logo não tem vizinhança.
        elim = cand("e", 0, 0, estagio="eliminado", score=0.0)
        lista = [cand("a", 9, 9), elim]
        assert ms._bloco_vizinhanca(elim, lista, posicoes(lista), r) == "", (
            "eliminado não deveria receber vizinhança")
        return "topo só olha para trás; sozinho e eliminado não têm vizinhança"

    placar.rodar("Extremos, candidato único e eliminado",
                 vizinhanca_nos_extremos_e_fora_do_ranking)

    def calculo_no_servidor_nunca_no_javascript():
        """Regra da spec: a nota é calculada em Python, então a decomposição
        dela também. O servidor manda tudo pronto — número, sinal e rótulo — e
        o app.js só desenha. Se aparecer aritmética de nota no JS, a mesma
        conta passa a existir em duas linguagens e um dia elas divergem."""
        from pathlib import Path
        js = (Path(__file__).resolve().parent.parent
              / "static" / "app.js").read_text(encoding="utf-8")
        i = js.find("function blocoVizinhanca")
        assert i != -1, "o bloco de vizinhança sumiu do app.js"
        corpo = js[i:js.find(chr(10) + "}", i)]
        for proibido in ("score_final", "peso", "Math.round", "Math.abs",
                         "toFixed", " - ", " * ", " / "):
            assert proibido not in corpo, (
                f"conta de nota no JavaScript ({proibido!r}) — isso é do servidor")
        # E o servidor tem de mandar os números já formatados como texto.
        r = rubrica_de(60, 40)
        from app.pontuacao import calcular_score, posicoes, vizinhanca

        def cand(cid, n1, n2):
            res = resultado_de(n1, n2)
            return {"candidato_id": cid, "estagio": "avaliado",
                    "score_final": calcular_score(res, r), "confianca": "alta",
                    "origem_texto": "direto", "resultado": res.model_dump()}

        todas = [cand("a", 9, 9), cand("b", 8, 8)]
        v = vizinhanca(todas[1], todas, posicoes(todas), r)
        assert isinstance(v["lados"][0]["gap"], str), "gap deveria vir pronto"
        assert v["lados"][0]["criterios"][0]["delta"].startswith(("+", "−")), (
            "o sinal deveria vir do servidor, não ser montado no JS")
        return "servidor manda pronto; o JS não faz conta de nota"

    placar.rodar("A decomposição é calculada no servidor, não no JavaScript",
                 calculo_no_servidor_nunca_no_javascript)

    def csv_nao_recebe_comparacao():
        """A spec deixa o CSV de fora de propósito: é exportação bruta, sem a
        moldura de critérios acordados que torna a frase defensável. Sem esta
        asserção, o campo entra de carona no dia em que alguém montar o CSV a
        partir de outra fonte."""
        from pathlib import Path
        rotas = (Path(__file__).resolve().parent.parent
                 / "app" / "rotas_vagas.py").read_text(encoding="utf-8")
        ini = rotas.find("async def exportar_csv")
        fim = rotas.find("@router.get", ini)
        corpo = rotas[ini:fim if fim > ini else len(rotas)]
        assert "vizinhanca" not in corpo, (
            "a comparação vazou para o CSV, que a spec mantém fora de propósito")
        return "exportar_csv não menciona vizinhança"

    placar.rodar("O CSV continua fora da comparação", csv_nao_recebe_comparacao)

    def documento_nunca_cita_quem_ficou_de_fora():
        """A amarra 2 da spec, e a razão de o documento ter cálculo próprio.

        O vizinho de alguém no ranking COMPLETO pode ter sido descartado. O
        documento do cliente não menciona descartado nenhum — citar aquele
        vizinho vazaria a existência dos excluídos para dentro dele. Aqui a
        lista entregue pula o segundo colocado de propósito.
        """
        from app.shortlist import montar_shortlist

        r = rubrica_de(60, 40)

        def cand(cid, nome, n1, n2):
            from app.pontuacao import calcular_score
            res = resultado_de(n1, n2)
            return {"candidato_id": cid, "nome": nome, "estagio": "avaliado",
                    "score_final": calcular_score(res, r), "confianca": "alta",
                    "origem_texto": "direto", "decisao": "entrevistar",
                    "anotacao": "", "contato": {}, "arquivo": f"{cid}.pdf",
                    "resultado": res.model_dump()}

        # cortado só existe no ranking completo; NÃO entra no documento.
        cortado = cand("cortado999", "Fulano Cortado", 8, 8)
        entregues = [cand("aaa", "Ana Souza", 9, 9),
                     cand("ccc", "Carla Nogueira", 7, 7)]

        vaga = {"titulo": "Analista", "rubrica": r.model_dump()}
        html = montar_shortlist({"nome": "Empresa"}, vaga, entregues,
                                {"nome": "Recrutador"})

        assert "Diferença para o anterior da lista" in html, (
            "a comparação não saiu no documento")
        for proibido in ("cortado999", "Fulano", "Cortado"):
            assert proibido not in html, (
                f"'{proibido}' vazou para o documento do cliente")

        # A comparação é contra o anterior DA LISTA (Ana), não contra quem o
        # ranking completo teria posto no meio.
        from app.shortlist import _comparacoes
        comp = _comparacoes(entregues, r)
        assert "ccc" in comp and "aaa" not in comp, comp
        # Ana 9/9 contra Carla 7/7: 12 + 8 = 20 pontos de diferença.
        assert "+12" in comp["ccc"] and "+8" in comp["ccc"], comp["ccc"]
        return "compara dentro da lista; quem ficou de fora não aparece"

    placar.rodar("O documento de entrega nunca cita quem ficou de fora",
                 documento_nunca_cita_quem_ficou_de_fora)

    def documento_nao_avalia_a_pessoa():
        """Amarra 1: só delta de critério, nenhuma palavra avaliativa sobre a
        pessoa. Numa peça que vai à mesa do cliente do recrutador, "mais forte"
        é juízo; "Active Directory (+12)" é a rubrica que ele aprovou."""
        from app.shortlist import _comparacoes

        r = rubrica_de(60, 40)

        def cand(cid, n1, n2):
            from app.pontuacao import calcular_score
            res = resultado_de(n1, n2)
            return {"candidato_id": cid, "score_final": calcular_score(res, r),
                    "estagio": "avaliado", "resultado": res.model_dump()}

        comp = _comparacoes([cand("a", 9, 9), cand("b", 7, 8)], r)
        texto = " ".join(comp.values()).lower()
        for juizo in ("melhor", "pior", "mais forte", "mais fraco", "supera",
                      "à frente", "atrás", "abaixo", "acima", "vence"):
            assert juizo not in texto, (
                f"palavra avaliativa '{juizo}' no documento do cliente: {texto!r}")
        return "só nome de critério e delta; nenhum juízo sobre a pessoa"

    placar.rodar("O documento não emite juízo sobre a pessoa",
                 documento_nao_avalia_a_pessoa)
