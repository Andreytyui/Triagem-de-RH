"""O cálculo da nota. Python puro, sem modelo, sem rede.

Este módulo existe separado de propósito. O conector devolve nota por critério e
uma recomendação; a média ponderada, o ranking e o desempate saem daqui — e é
isso que sustenta o princípio de que a nota é auditável: dá para recalcular à
mão, com a rubrica na frente, sem perguntar nada a ninguém.
"""
from __future__ import annotations

from typing import Optional

from .models import PerfilAnonimo, ResultadoScore, Rubrica


def perfil_para_texto(perfil: PerfilAnonimo) -> str:
    """Serialização enxuta do perfil. É o que o conector enxerga — sem dado
    pessoal, por construção, porque a separação já aconteceu antes."""
    linhas = [f"Resumo: {perfil.resumo}"]
    if perfil.anos_experiencia_total:
        linhas.append(f"Anos de experiência: {perfil.anos_experiencia_total}")

    if perfil.experiencias:
        linhas.append("\nExperiências:")
        for e in perfil.experiencias:
            periodo = f"{e.inicio or '?'} a {e.fim or '?'}"
            linhas.append(f"- {e.cargo} · {e.empresa or 'empresa não informada'} ({periodo})")
            if e.descricao:
                linhas.append(f"  {e.descricao}")

    if perfil.formacoes:
        linhas.append("\nFormação:")
        for f in perfil.formacoes:
            detalhe = " · ".join(x for x in (f.nivel, f.situacao, f.conclusao) if x)
            linhas.append(
                f"- {f.curso} · {f.instituicao or 'instituição não informada'}"
                + (f" ({detalhe})" if detalhe else "")
            )

    for rotulo, valores in (
        ("Habilidades", perfil.habilidades),
        ("Idiomas", perfil.idiomas),
        ("Certificações", perfil.certificacoes),
    ):
        if valores:
            linhas.append(f"\n{rotulo}: {', '.join(valores)}")

    if perfil.trecho_bruto:
        linhas.append(f"\nCurrículo na íntegra (anonimizado):\n{perfil.trecho_bruto}")

    return "\n".join(linhas)


def calcular_score(resultado: ResultadoScore, rubrica: Rubrica) -> float:
    """Média ponderada 0-100. O ranking sai daqui, não do modelo.

    Critério que o modelo deixou de responder conta como zero: é o resultado
    conservador, e a lacuna aparece em `criterios_faltantes`.
    """
    pesos = {c.id: c.peso for c in rubrica.criterios}
    total_peso = sum(pesos.values()) or 1
    soma = sum(
        n.nota * pesos.get(n.criterio_id, 0)
        for n in resultado.criterios
        if n.criterio_id in pesos
    )
    return round(soma * 10 / total_peso, 1)


def criterios_faltantes(resultado: ResultadoScore, rubrica: Rubrica) -> list[str]:
    respondidos = {n.criterio_id for n in resultado.criterios}
    return [c.nome for c in rubrica.criterios if c.id not in respondidos]


def faixa_do_score(score: float) -> str:
    if score >= 70:
        return "chamar"
    if score >= 50:
        return "talvez"
    return "descartar"


_ORDEM = {"descartar": 0, "talvez": 1, "chamar": 2}


def conciliar(score: float, recomendacao: str) -> tuple[str, Optional[str]]:
    """Nota e recomendação vêm de lugares diferentes e podem brigar.

    Divergência de uma faixa é normal — o modelo pesa o conjunto, a nota pesa a
    rubrica. Divergência de duas faixas é erro: vale a nota, que é auditável, e
    o recrutador é avisado.
    """
    faixa = faixa_do_score(score)
    distancia = abs(_ORDEM[faixa] - _ORDEM.get(recomendacao, _ORDEM[faixa]))
    if distancia >= 2:
        return faixa, (
            f"a recomendação do modelo foi '{recomendacao}', mas a nota ponderada "
            f"({score:.0f}/100) fica na faixa '{faixa}'; vale a nota"
        )
    return recomendacao, None

# ---------- Diagnóstico comparativo entre vizinhos ----------
#
# A decomposição sai da MESMA expressão da nota, não de uma reescrita dela: a
# contribuição de um critério é `nota × peso × 10 / Σpeso`, que é o termo do
# somatório de `calcular_score`. Se alguém mexer lá, isto acompanha em vez de
# divergir calado — e é isso que sustenta a promessa da frase, que é os números
# somarem a diferença que o recrutador já vê na tela.
#
# Nada aqui vira texto: cada superfície escreve a sua frase, porque a linguagem
# do documento de entrega é mais dura que a das ferramentas do conector.

# Abaixo disto o critério não é nomeado: é ruído de arredondamento, não diferença.
PISO_DELTA = 1.0
# Quantos critérios a frase nomeia antes de agrupar o resto.
MAX_CRITERIOS_NOMEADOS = 2


def contribuicoes(resultado: ResultadoScore, rubrica: Rubrica) -> dict[str, float]:
    """Quanto cada critério vale, em pontos da nota final (0-100).

    Critério ausente vale zero — é a mesma conta de `calcular_score`, e a lacuna
    é reportada à parte por `criterios_faltantes`, para a frase poder dizer que
    parte da diferença é lacuna nossa e não do candidato.
    """
    pesos = {c.id: c.peso for c in rubrica.criterios}
    total_peso = sum(pesos.values()) or 1
    notas = {n.criterio_id: n.nota for n in resultado.criterios}
    return {
        cid: notas.get(cid, 0) * peso * 10 / total_peso
        for cid, peso in pesos.items()
    }


def decompor_diferenca(
    resultado_a: ResultadoScore,
    resultado_b: ResultadoScore,
    rubrica: Rubrica,
) -> dict:
    """Por que A está acima (ou abaixo) de B, em pontos da nota final.

    Devolve estrutura, não frase. `diferenca` é a diferença das notas como o
    recrutador as vê — arredondadas — e a soma de `criterios` mais `resto`
    reproduz esse número exatamente, por construção: `resto` é calculado como o
    que falta, não como o que sobrou.
    """
    ca = contribuicoes(resultado_a, rubrica)
    cb = contribuicoes(resultado_b, rubrica)
    nomes = {c.id: c.nome for c in rubrica.criterios}

    # A diferença exibida é a das notas exibidas: é o número que está na tela.
    diferenca = round(calcular_score(resultado_a, rubrica)
                      - calcular_score(resultado_b, rubrica), 1)

    deltas = sorted(
        ((cid, round(ca[cid] - cb[cid], 1)) for cid in ca),
        key=lambda par: (-abs(par[1]), nomes.get(par[0], par[0])),
    )
    nomeados = [(cid, d) for cid, d in deltas
                if abs(d) >= PISO_DELTA][:MAX_CRITERIOS_NOMEADOS]

    soma_nomeada = round(sum(d for _, d in nomeados), 1)
    resto = round(diferenca - soma_nomeada, 1)

    # O rótulo tem de dizer o que aquilo é. Se sobrou critério de verdade, é
    # "outros"; se todos já foram nomeados, chamar o resíduo de "outros" seria
    # inventar um critério que não existe — numa frase que só vale por ser
    # honesta, isso sai caro por 0.1 ponto.
    faltou_criterio = any(
        cid not in {c for c, _ in nomeados} and abs(d) > 0
        for cid, d in deltas
    )
    termo_resto = None
    if resto:
        termo_resto = {
            "rotulo": "outros" if faltou_criterio else "arredondamento",
            "delta": resto,
        }

    return {
        "diferenca": diferenca,
        "criterios": [{"id": cid, "nome": nomes.get(cid, cid), "delta": d}
                      for cid, d in nomeados],
        "resto": termo_resto,
        "identicos": not nomeados and not resto,
        "faltantes_a": criterios_faltantes(resultado_a, rubrica),
        "faltantes_b": criterios_faltantes(resultado_b, rubrica),
    }

def ocupa_lugar(linha: dict) -> bool:
    """Quem tem lugar no ranking: só quem tem nota que o coloque em algum.

    Eliminado, erro e ainda-avaliando não ocupam lugar — não é que percam a
    disputa, é que não estão nela. Definição única de propósito: o predicado
    já estava escrito duas vezes aqui, e cada cópia nova é uma chance de as
    superfícies discordarem sobre quem conta.
    """
    return linha.get("estagio") == "avaliado" and linha.get("score_final") is not None


def _ordenados(linhas: list[dict]) -> list[dict]:
    return sorted((l for l in linhas if ocupa_lugar(l)),
                  key=lambda l: -l["score_final"])


def posicoes(linhas: list[dict]) -> dict[str, int]:
    """Mapa candidato_id -> posição no ranking completo da vaga. USO INTERNO.

    Isto NÃO é a posição exibida em lugar nenhum. A coluna "Posição" da tela, do
    relatório, do CSV e a numeração das listagens seguem sendo a ordem sequencial
    local daquela lista, sem buracos, exatamente como sempre foram — decisão do
    dono do produto, e nada aqui as altera.

    O mapa existe só para a frase comparativa achar o vizinho de verdade no
    ranking completo quando a visão está filtrada. Quando esse número aparece no
    texto, aparece sempre qualificado por extenso — "o número 3 do ranking geral"
    — nunca solto, justamente para não ser confundido com a posição local
    mostrada ao lado.

    Ordena por nota e ignora quem não tem: eliminado, erro e ainda-avaliando não
    ocupam lugar no ranking porque não têm nota que os coloque em algum.
    """
    return {l["candidato_id"]: i for i, l in enumerate(_ordenados(linhas), start=1)}


def vizinhos(linhas: list[dict], candidato_id: str) -> tuple[Optional[dict], Optional[dict]]:
    """O pontuado imediatamente acima e o imediatamente abaixo.

    Sobre a lista recebida — quem chama decide o conjunto. É o que permite o
    documento de entrega comparar dentro do próprio shortlist sem nunca alcançar
    quem ficou de fora: a função não tem como citar o que não recebeu.
    """
    pontuados = _ordenados(linhas)
    for i, l in enumerate(pontuados):
        if l["candidato_id"] == candidato_id:
            return (pontuados[i - 1] if i > 0 else None,
                    pontuados[i + 1] if i + 1 < len(pontuados) else None)
    return (None, None)

def formatar_deltas(decomposicao: dict) -> str:
    """`Active Directory (−12), SLA (+5)` — os números, sem a frase em volta.

    Só formatação: a frase que envolve isto é de cada superfície, porque a
    linguagem do documento de entrega é mais dura que a das ferramentas.
    """
    partes = [f"{c['nome']} ({_sinal(c['delta'])})" for c in decomposicao["criterios"]]
    resto = decomposicao.get("resto")
    if resto:
        partes.append(f"{resto['rotulo']} ({_sinal(resto['delta'])})")
    return ", ".join(partes)


def _sinal(valor: float) -> str:
    """Sinal explícito e menos tipográfico: o `+`/`−` é que carrega a direção,
    já que a spec proíbe cor semântica aqui."""
    inteiro = int(valor) if float(valor).is_integer() else valor
    return f"+{inteiro}" if valor > 0 else f"−{abs(inteiro)}" if valor < 0 else "0"


def ressalvas_da_comparacao(decomposicao: dict, a: dict, b: dict) -> list[str]:
    """As duas ressalvas obrigatórias, quando cabem.

    A primeira separa o candidato da nossa extração: critério não respondido
    conta zero no `calcular_score`, e deixar isso escondido atrás do número
    diria "ele é pior" onde a verdade é "nós não temos a resposta".
    """
    avisos = []
    nomeados = {c["nome"] for c in decomposicao["criterios"]}
    for lado, faltantes in (("dele", decomposicao["faltantes_b"]),
                            ("dele", decomposicao["faltantes_a"])):
        for nome in faltantes:
            if nome in nomeados:
                avisos.append(
                    f"{nome} não foi respondido no currículo {lado} e conta como "
                    "zero — parte dessa diferença é lacuna nossa, não dele."
                )
    if any(l.get("confianca") == "baixa" for l in (a, b)):
        avisos.append("um dos dois tem confiança baixa: a diferença pode ser "
                      "ruído de avaliação.")
    if any(l.get("origem_texto") == "ocr" for l in (a, b)):
        avisos.append("um dos dois foi lido por OCR: a diferença pode ser ruído "
                      "de extração.")
    return avisos



def numerar_exibicao(linhas: list[dict], vazio: str = "—") -> list[str]:
    """Rótulo de posição para EXIBIR, na ordem em que as linhas chegam.

    Sequencial local, sem buracos, como o dono do produto fixou — mas quem não
    ocupa lugar recebe `vazio`, nunca um número: eliminado numerado lê como
    colocação, e não é. Não confundir com `posicoes`, que é uso interno e numera
    o ranking geral só para a frase comparativa achar o vizinho certo.
    """
    saida, lugar = [], 0
    for linha in linhas:
        if ocupa_lugar(linha):
            lugar += 1
            saida.append(str(lugar))
        else:
            saida.append(vazio)
    return saida

def _seco(valor: float) -> str:
    return str(int(valor)) if float(valor).is_integer() else str(valor)


def vizinhanca(linha: dict, todas: list[dict], posicao_de: dict,
               rubrica: Optional[Rubrica]) -> Optional[dict]:
    """Os dois vizinhos, já decompostos, como ESTRUTURA — nunca como frase.

    É a fonte única do bloco de vizinhança nas duas superfícies que o mostram:
    o texto do `ver_candidato` e o `.detalhe` da web. Cada uma escreve a sua
    apresentação; o que não pode é cada uma decidir por conta quem lidera, qual
    é a distância e quais critérios a explicam — aí as duas divergiriam sobre o
    mesmo par, e o recrutador veria contas diferentes lado a lado.

    Cada lado é montado A FAVOR DE QUEM ESTÁ NA FRENTE, para os deltas somarem
    a distância como número positivo nos dois casos.
    """
    if rubrica is None or not ocupa_lugar(linha):
        return None
    acima, abaixo = vizinhos(todas, linha["candidato_id"])
    if not acima and not abaixo:
        return None

    lados, avisos = [], []
    for vizinho, a, b, rotulo in ((acima, acima, linha, "à frente"),
                                  (abaixo, linha, abaixo, "atrás")):
        if not vizinho:
            continue
        try:
            dec = decompor_diferenca(
                ResultadoScore.model_validate(a["resultado"] or {}),
                ResultadoScore.model_validate(b["resultado"] or {}),
                rubrica,
            )
        except Exception:                                      # noqa: BLE001
            continue
        criterios = [{"nome": c["nome"], "delta": _sinal(c["delta"])}
                     for c in dec["criterios"]]
        if dec["resto"]:
            criterios.append({"nome": dec["resto"]["rotulo"],
                              "delta": _sinal(dec["resto"]["delta"])})
        lados.append({
            "posicao": posicao_de.get(vizinho["candidato_id"]),
            "score": vizinho["score_final"],
            "gap": _seco(abs(round(a["score_final"] - b["score_final"], 1))),
            "rotulo": rotulo,
            "identicos": dec["identicos"],
            "criterios": criterios,
        })
        avisos.extend(ressalvas_da_comparacao(dec, a, b))

    if not lados:
        return None
    return {
        "posicao": posicao_de.get(linha["candidato_id"]),
        "lados": lados,
        "ressalvas": list(dict.fromkeys(avisos)),
    }
