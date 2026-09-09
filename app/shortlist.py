"""O shortlist: o documento que o recrutador entrega ao cliente dele.

Isto não é uma tela do sistema com menos coisas. É outro documento, com outro
leitor. Quem lê é a empresa que contratou o recrutador, e ela quer saber por que
estes nomes — não como a lista foi produzida.

Por isso não aparecem aqui: candidatos descartados, contagem total de inscritos,
custo, progresso, nem qualquer menção a inteligência artificial, modelo ou
processamento. O trabalho apresentado é o do recrutador. A ferramenta some.

O que aparece: os critérios que a vaga combinou, e para cada candidato a nota de
cada critério com o trecho do currículo que a sustenta.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Optional

from . import estilo, pontuacao
from .models import ResultadoScore, Rubrica

ESTILO = """
*,*::before,*::after { box-sizing:border-box; }
body {
  margin:0; padding:3.5rem 2rem 5rem; background:var(--papel); color:var(--tinta);
  font-family:var(--sans); font-size:15px; line-height:1.55;
  -webkit-font-smoothing:antialiased;
}
.folha {
  max-width:46rem; margin:0 auto; background:var(--papel);
  border:1px solid var(--regua); padding:3.5rem 3.25rem;
}
h1,h2,h3 { font-weight:600; letter-spacing:-0.018em; margin:0; line-height:1.25; }
p { margin:0 0 .75rem; }

.cabeca { padding-bottom:1.5rem; border-bottom:2px solid var(--tinta); margin-bottom:2rem; }
.cabeca h1 { font-size:1.75rem; letter-spacing:-0.025em; }
.cabeca-quem {
  display:flex; flex-wrap:wrap; gap:.25rem 1.25rem;
  color:var(--fraca); font-size:.875rem; margin:.5rem 0 0;
}
.cabeca-frase { color:var(--media); margin:1rem 0 0; max-width:34rem; }

.criterios { margin-bottom:2.75rem; }
.criterios h2 { font-size:1rem; margin-bottom:.25rem; }
.criterios-nota { color:var(--fraca); font-size:.875rem; margin-bottom:1rem; }
.criterio-regra {
  display:grid; grid-template-columns:3rem minmax(0,1fr); gap:1rem;
  padding:.6875rem 0; border-top:1px solid var(--regua);
}
.criterio-regra:last-child { border-bottom:1px solid var(--regua); }
.regra-peso {
  font-variant-numeric:tabular-nums; color:var(--petroleo); font-weight:600;
  text-align:right;
}
.regra-nome { display:block; font-weight:500; }
.regra-desc { display:block; color:var(--media); font-size:.9375rem; margin-top:.125rem; }

.cand {
  padding-top:2rem; margin-top:2rem; border-top:1px solid var(--regua-forte);
  break-inside:avoid; page-break-inside:avoid;
}
.cand:first-of-type { border-top:none; margin-top:0; }
.cand-topo {
  display:flex; align-items:flex-start; justify-content:space-between;
  gap:1.5rem; margin-bottom:.25rem;
}
.cand-nome { font-size:1.375rem; letter-spacing:-0.02em; }
.cand-nota {
  font-family:var(--serif); font-size:2.5rem; line-height:.9; color:var(--petroleo);
  font-variant-numeric:tabular-nums; flex-shrink:0; text-align:right;
}
.cand-nota small {
  display:block; font-family:var(--sans); font-size:.6875rem; color:var(--fraca);
  letter-spacing:0;
}
.cand-contato { color:var(--fraca); font-size:.875rem; margin:0 0 1rem; }
.cand-contato span { margin-right:1.25rem; }
.cand-resumo { color:var(--media); font-size:1.0625rem; margin-bottom:1.25rem; }

.nota-linha { padding:1rem 0; border-top:1px solid var(--regua); }
.nota-topo {
  display:flex; justify-content:space-between; align-items:baseline; gap:1rem;
}
.nota-nome { font-weight:500; }
.nota-peso { color:var(--fraca); font-size:.8125rem; font-weight:400; display:block; }
.nota-valor {
  font-family:var(--serif); font-size:1.375rem; line-height:1;
  font-variant-numeric:tabular-nums; flex-shrink:0;
}
.nota-valor small { font-family:var(--sans); font-size:.6875rem; color:var(--fraca); }
.trilho { height:3px; margin:.5rem 0 .8125rem; background:var(--papel-fundo); border-radius:2px; }
.trilho div { height:100%; background:var(--petroleo); border-radius:2px; }

.evidencia {
  position:relative; font-family:var(--serif); font-size:1.125rem; line-height:1.5;
  margin:0; padding-left:1.5rem;
}
.evidencia::before {
  content:"\\201C"; position:absolute; left:-.05rem; top:-.35rem;
  font-family:var(--serif); font-size:2.375rem; line-height:1; color:var(--petroleo-md);
}
.evidencia-ausente {
  font-family:var(--sans); font-size:.875rem; color:var(--fraca);
  padding-left:.875rem; border-left:1px dashed var(--regua-forte);
}
.evidencia-ausente::before { content:none; }

.comparacao {
  margin:.75rem 0 0; padding-top:.6875rem; border-top:1px solid var(--regua);
  font-size:.8125rem; color:var(--media); font-variant-numeric:tabular-nums;
}
.listas { display:flex; gap:2.5rem; flex-wrap:wrap; margin-top:1.25rem; }
.listas > div { flex:1 1 15rem; }
.listas h3 { font-size:.875rem; margin-bottom:.375rem; }
.listas ul { margin:0; padding-left:1.05rem; font-size:.9375rem; color:var(--media); }
.listas li { margin-bottom:.1875rem; }

.anotacao {
  margin-top:1.25rem; padding:.875rem 1rem; background:var(--papel-realce);
  border-left:2px solid var(--petroleo-md); font-size:.9375rem; color:var(--media);
}
.anotacao strong { color:var(--tinta); font-weight:600; }

.rodape {
  margin-top:3rem; padding-top:1.25rem; border-top:1px solid var(--regua);
  color:var(--fraca); font-size:.8125rem;
}
.vazio { color:var(--fraca); }

.barra {
  position:sticky; top:0; z-index:5; max-width:46rem; margin:0 auto 1rem;
  display:flex; justify-content:space-between; align-items:center; gap:1rem;
  padding:.6875rem 1rem; background:var(--tinta); color:var(--tinta-reversa); font-size:.875rem;
}
.barra button {
  font:inherit; font-weight:500; background:var(--painel); color:var(--tinta);
  border:0; padding:.4375rem 1rem; cursor:pointer; border-radius:3px;
}
.barra button:hover { background:var(--petroleo-cl); }

@media (max-width:40rem) {
  body { padding:1.5rem 1rem 3rem; }
  .folha { padding:2rem 1.375rem; }
  .cand-nota { font-size:2rem; }
  .evidencia { font-size:1.0625rem; }
}

@media print {
  body { padding:0; background:var(--papel-documento); font-size:11pt; }
  .folha { max-width:none; border:none; padding:0; }
  .naoimprime { display:none !important; }
  .cand { border-top-color:var(--regua-forte); }
  a { text-decoration:none; color:inherit; }
  @page { margin:1.7cm; }
}

@media (prefers-reduced-motion:reduce) {
  * { transition-duration:.01ms !important; animation-duration:.01ms !important; }
}
"""


def _e(valor) -> str:
    return escape(str(valor if valor is not None else ""))


def _data_br(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return iso[:10]


def _bloco_criterios(rubrica: Rubrica) -> str:
    if not rubrica or not rubrica.criterios:
        return ""
    regras = "".join(
        f"<div class='criterio-regra'>"
        f"<span class='regra-peso'>{c.peso}%</span>"
        f"<span><span class='regra-nome'>{_e(c.nome)}</span>"
        f"<span class='regra-desc'>{_e(c.descricao)}</span></span></div>"
        for c in rubrica.criterios
    )
    return (
        "<section class='criterios'><h2>Como estes nomes foram avaliados</h2>"
        "<p class='criterios-nota'>Os critérios e os pesos foram definidos para esta "
        "vaga antes de qualquer análise. Cada nota abaixo cita o trecho do currículo "
        "que a sustenta.</p>"
        f"{regras}</section>"
    )


def _lista(titulo: str, itens: list) -> str:
    if not itens:
        return ""
    li = "".join(f"<li>{_e(i)}</li>" for i in itens)
    return f"<div><h3>{titulo}</h3><ul>{li}</ul></div>"


def _comparacoes(linhas: list[dict], rubrica: Optional[Rubrica]) -> dict:
    """Diferença de cada candidato para o ANTERIOR DESTA LISTA.

    A amarra que sustenta o documento: o cálculo é sobre `linhas`, que já chega
    filtrada — só quem entra no shortlist. O vizinho de alguém no ranking
    completo pode ter sido descartado, e o documento não menciona descartado
    nenhum; citar aquele vizinho vazaria a existência dos excluídos para dentro
    do documento do cliente. Como esta função só recebe a lista, ela é
    estruturalmente incapaz de nomear quem ficou de fora.

    Mesma aritmética do conector, conjunto diferente — e por isso outro código.
    Aqui não há regra de fragilidade: são 3 a 5 nomes, e todos levam a linha.
    """
    if rubrica is None:
        return {}
    saida = {}
    for i, linha in enumerate(linhas):
        if i == 0:
            continue
        anterior = linhas[i - 1]
        try:
            dec = pontuacao.decompor_diferenca(
                ResultadoScore.model_validate(anterior.get("resultado") or {}),
                ResultadoScore.model_validate(linha.get("resultado") or {}),
                rubrica,
            )
        except Exception:                                      # noqa: BLE001
            continue
        saida[linha["candidato_id"]] = (
            "praticamente idênticos nos critérios" if dec["identicos"]
            else pontuacao.formatar_deltas(dec)
        )
    return saida


def _bloco_candidato(linha: dict, pesos: dict, comparacao: str = "") -> str:
    resultado = linha.get("resultado") or {}
    contato = linha.get("contato") or {}
    score = linha.get("score_final")

    partes = ["<article class='cand'>", "<div class='cand-topo'>",
              f"<h2 class='cand-nome'>{_e(linha.get('nome') or '—')}</h2>"]
    if isinstance(score, (int, float)):
        partes.append(
            f"<span class='cand-nota'>{score:.0f}<small>de 100</small></span>"
        )
    partes.append("</div>")

    contatos = "".join(
        f"<span>{_e(v)}</span>"
        for v in (contato.get("email"), contato.get("telefone"), contato.get("cidade"))
        if v
    )
    if contatos:
        partes.append(f"<p class='cand-contato'>{contatos}</p>")
    if resultado.get("resumo"):
        partes.append(f"<p class='cand-resumo'>{_e(resultado['resumo'])}</p>")

    for nota in resultado.get("criterios", []):
        meta = pesos.get(nota.get("criterio_id"), {})
        evidencia = nota.get("evidencia") or ""
        ausente = "sem evid" in evidencia.lower()
        valor = nota.get("nota") or 0
        partes.append(
            "<div class='nota-linha'><div class='nota-topo'>"
            f"<span><span class='nota-nome'>{_e(meta.get('nome') or nota.get('criterio_id'))}"
            f"</span><span class='nota-peso'>peso {meta.get('peso', 0)}% do total</span></span>"
            f"<span class='nota-valor'>{_e(valor)}<small>/10</small></span></div>"
            f"<div class='trilho'><div style='width:{int(valor) * 10}%'></div></div>"
            f"<p class='evidencia{' evidencia-ausente' if ausente else ''}'>{_e(evidencia)}</p>"
            "</div>"
        )

    # Só delta de critério. Nenhuma palavra avaliativa sobre a pessoa — "mais
    # forte", "melhor", "mais preparado" não entram em lugar nenhum deste
    # documento. O que a decomposição acrescenta não é a comparação (essa já
    # está na ordem da lista), é o MOTIVO dela — e o motivo são os critérios
    # que o próprio cliente aprovou.
    if comparacao:
        partes.append(
            "<p class='comparacao'>Diferença para o anterior da lista: "
            f"{_e(comparacao)}</p>"
        )

    listas = _lista("Pontos fortes", resultado.get("pontos_fortes") or []) + \
        _lista("Pontos de atenção", resultado.get("red_flags") or [])
    if listas:
        partes.append(f"<div class='listas'>{listas}</div>")

    if linha.get("anotacao"):
        partes.append(
            f"<p class='anotacao'><strong>Observação:</strong> {_e(linha['anotacao'])}</p>"
        )
    partes.append("</article>")
    return "".join(partes)


def montar_shortlist(org: Optional[dict], vaga: dict, linhas: list[dict],
                     usuario: dict) -> str:
    """Monta a página. `linhas` já vem filtrada: só quem entra no shortlist."""
    try:
        rubrica = Rubrica.model_validate(vaga["rubrica"]) if vaga.get("rubrica") else None
    except Exception:                                          # noqa: BLE001
        rubrica = None
    pesos = {c.id: {"nome": c.nome, "peso": c.peso}
             for c in (rubrica.criterios if rubrica else [])}

    quantos = len(linhas)
    frase = {
        0: "Nenhum candidato foi selecionado para este shortlist.",
        1: "Abaixo, o candidato selecionado para esta vaga, com a avaliação "
           "de cada critério.",
    }.get(quantos,
          f"Abaixo, os {quantos} candidatos selecionados para esta vaga, "
          "em ordem de aderência aos critérios combinados.")

    comparacoes = _comparacoes(linhas, rubrica)
    corpo = "".join(
        _bloco_candidato(l, pesos, comparacoes.get(l["candidato_id"], ""))
        for l in linhas
    ) or \
        "<p class='vazio'>Nenhum candidato selecionado.</p>"

    responsavel = _e(usuario.get("nome"))
    empresa = _e(org.get("nome") if org else "")

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="same-origin">
<title>{_e(vaga.get('titulo'))} — candidatos selecionados</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..600&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<style>{estilo.folha(documento=True)}{ESTILO}</style>
<script src="/static/imprimir.js" defer></script>
</head><body>

<div class="barra naoimprime">
  <span>Pronto para enviar. Use <strong>Imprimir → Salvar como PDF</strong>.</span>
  <button id="imprimir">Imprimir</button>
</div>

<div class="folha">
  <header class="cabeca">
    <h1>{_e(vaga.get('titulo'))}</h1>
    <p class="cabeca-quem">
      <span>Seleção de {responsavel or 'candidatos'}</span>
      {f'<span>{empresa}</span>' if empresa else ''}
      <span>{_data_br(datetime.now().isoformat())}</span>
    </p>
    <p class="cabeca-frase">{frase}</p>
  </header>

  {_bloco_criterios(rubrica)}

  <section>{corpo}</section>

  <footer class="rodape">
    As notas seguem os critérios acordados para esta vaga, e cada uma cita o trecho
    do currículo que a sustenta. A recomendação final de contratação é da empresa.
    Este documento contém dados pessoais dos candidatos — trate-o como confidencial.
  </footer>
</div>

</body></html>"""
