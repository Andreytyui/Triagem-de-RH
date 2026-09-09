"""Relatório imprimível de uma triagem.

É o documento que sai da ferramenta e entra na reunião: cada nota acompanhada do
trecho do currículo que a sustenta, mais a rubrica que o próprio recrutador
aprovou. Sem isso, a triagem é uma opinião; com isso, é uma decisão auditável.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Optional

from . import estilo
from .models import Rubrica
from .pontuacao import numerar_exibicao

ESTILO = """
* { box-sizing:border-box; }
body { margin:0; padding:2.5rem 3rem; background:var(--papel); color:var(--tinta);
       font:14px/1.55 "Instrument Sans", ui-sans-serif, system-ui, sans-serif; }
h1 { font-size:1.55rem; margin:0 0 .2rem; letter-spacing:-.02em; }
h2 { font-size:1.05rem; margin:0 0 .4rem; letter-spacing:-.01em; }
h3 { font-size:.82rem; margin:1rem 0 .35rem; text-transform:uppercase;
     letter-spacing:.07em; color:var(--fraca); font-weight:600; }
p  { margin:0 0 .55rem; }
a  { color:inherit; }

.cabeca { border-bottom:2px solid var(--tinta); padding-bottom:1rem; margin-bottom:1.5rem; }
.cabeca-meta { color:var(--fraca); font-size:.85rem; }
.selo-org { float:right; text-align:right; color:var(--fraca); font-size:.8rem; }

.rubrica { background:var(--papel-realce); border:1px solid var(--regua); padding:1rem 1.2rem;
           margin-bottom:2rem; break-inside:avoid; }
.rubrica ul { margin:.3rem 0 .8rem; padding-left:1.1rem; }
.rubrica li { margin-bottom:.2rem; }
.peso { color:var(--petroleo); font-weight:600; }

.resumo-linha { display:flex; gap:2.5rem; flex-wrap:wrap; margin-bottom:2rem;
                padding:.9rem 0; border-top:1px solid var(--regua);
                border-bottom:1px solid var(--regua); }
.resumo-linha div { display:flex; flex-direction:column; }
.resumo-valor { font-size:1.5rem; font-weight:600; letter-spacing:-.02em; }
.resumo-rotulo { font-size:.78rem; color:var(--fraca); text-transform:uppercase;
                 letter-spacing:.06em; }

.cand { border:1px solid var(--regua); padding:1.2rem 1.4rem; margin-bottom:1rem;
        break-inside:avoid; page-break-inside:avoid; }
.cand-topo { display:flex; justify-content:space-between; align-items:baseline;
             gap:1rem; margin-bottom:.15rem; }
.cand-nome { font-size:1.1rem; font-weight:600; letter-spacing:-.01em; }
.cand-score { font-size:1.6rem; font-weight:600; letter-spacing:-.03em;
              font-variant-numeric:tabular-nums; }
.cand-contato { color:var(--fraca); font-size:.85rem; margin-bottom:.6rem; }
.cand-resumo { margin-bottom:.8rem; }

.etiqueta { display:inline-block; font-size:.72rem; text-transform:uppercase;
            letter-spacing:.06em; font-weight:600; padding:.12rem .45rem;
            border:1px solid currentColor; margin-right:.35rem; }
.e-chamar   { color:var(--petroleo); }
.e-talvez   { color:var(--ocre); }
.e-descartar{ color:var(--fraca); }
.e-entrevistar { color:var(--petroleo); }
.e-arquivado   { color:var(--fraca); }
.e-baixa    { color:var(--tijolo); }

.criterio { margin-bottom:.7rem; padding-left:.7rem; border-left:2px solid var(--regua); }
.criterio-topo { display:flex; justify-content:space-between; gap:1rem;
                 font-size:.9rem; font-weight:500; }
.criterio-nota { font-variant-numeric:tabular-nums; color:var(--petroleo);
                 font-weight:600; }
.evidencia { font-size:.87rem; color:var(--tinta-media); margin:.15rem 0 0; font-style:italic; }
.evidencia-ausente { color:var(--tijolo); font-style:normal; }

.listas { display:flex; gap:2rem; flex-wrap:wrap; margin-top:.7rem; }
.listas > div { flex:1 1 14rem; }
.listas ul { margin:.2rem 0; padding-left:1.05rem; font-size:.88rem; }
.aviso { background:var(--ocre-cl); border-left:3px solid var(--ocre); padding:.5rem .7rem;
         font-size:.85rem; margin-top:.6rem; }

.rodape { margin-top:2.5rem; padding-top:1rem; border-top:1px solid var(--regua);
          color:var(--fraca); font-size:.8rem; }
.vazio { color:var(--fraca); font-style:italic; }

@media print {
  body { padding:0; font-size:11.5pt; }
  .naoimprime { display:none !important; }
  .cand { border-color:var(--regua-forte); }
  @page { margin:1.6cm; }
}
.barra { position:sticky; top:0; background:var(--tinta); color:var(--tinta-reversa); padding:.6rem 1rem;
         margin:-2.5rem -3rem 2rem; display:flex; justify-content:space-between;
         align-items:center; gap:1rem; }
.barra button { font:inherit; background:var(--painel); color:var(--tinta); border:0;
                padding:.4rem .9rem; cursor:pointer; }
"""

ROTULO_DECISAO = {
    "entrevistar": "Chamar para entrevista",
    "reserva": "Manter em reserva",
    "arquivado": "Arquivado",
    "sem_decisao": "",
}


def _e(valor) -> str:
    return escape(str(valor if valor is not None else ""))


def _data_br(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return iso[:10]


def _bloco_rubrica(rubrica: Optional[Rubrica]) -> str:
    if not rubrica:
        return ""
    partes = ["<div class='rubrica'>", "<h2>Critérios aprovados para esta vaga</h2>",
              "<p class='cabeca-meta'>Esta rubrica foi revisada e aprovada pelo "
              "recrutador antes de qualquer avaliação.</p>"]

    if rubrica.eliminatorios:
        partes.append("<h3>Eliminatórios</h3><ul>")
        partes += [f"<li>{_e(r.descricao)}</li>" for r in rubrica.eliminatorios]
        partes.append("</ul>")

    partes.append("<h3>Critérios pontuados</h3><ul>")
    for c in rubrica.criterios:
        partes.append(
            f"<li><span class='peso'>{c.peso}%</span> — <strong>{_e(c.nome)}</strong>: "
            f"{_e(c.descricao)}</li>"
        )
    partes.append("</ul>")

    if rubrica.observacoes:
        partes.append(f"<h3>Observações</h3><p>{_e(rubrica.observacoes)}</p>")
    partes.append("</div>")
    return "".join(partes)


def _lista(titulo: str, itens: list) -> str:
    if not itens:
        return ""
    li = "".join(f"<li>{_e(i)}</li>" for i in itens)
    return f"<div><h3>{titulo}</h3><ul>{li}</ul></div>"


def _bloco_candidato(posicao: str, linha: dict, pesos: dict) -> str:
    resultado = linha.get("resultado") or {}
    contato = linha.get("contato") or {}
    estagio = linha.get("estagio")

    score = linha.get("score_final")
    score_txt = f"{score:.0f}" if isinstance(score, (int, float)) else "—"

    etiquetas = []
    recomendacao = linha.get("recomendacao")
    if recomendacao:
        etiquetas.append(
            f"<span class='etiqueta e-{_e(recomendacao)}'>{_e(recomendacao)}</span>"
        )
    decisao = linha.get("decisao")
    if decisao and decisao != "sem_decisao":
        etiquetas.append(
            f"<span class='etiqueta e-{_e(decisao)}'>{_e(ROTULO_DECISAO.get(decisao, decisao))}</span>"
        )
    if linha.get("confianca") == "baixa":
        etiquetas.append("<span class='etiqueta e-baixa'>confiança baixa</span>")

    contatos = " · ".join(
        _e(v) for v in (contato.get("email"), contato.get("telefone"), contato.get("cidade")) if v
    ) or "contato não identificado no currículo"

    corpo = [
        "<div class='cand'>",
        "<div class='cand-topo'>",
        f"<span class='cand-nome'>{_e(posicao)}{'. ' if posicao.isdigit() else ' '}"
        f"{_e(linha.get('nome') or '—')}</span>",
        f"<span class='cand-score'>{score_txt}</span>",
        "</div>",
        f"<p class='cand-contato'>{contatos}</p>",
        "".join(etiquetas),
    ]

    if estagio == "eliminado":
        corpo.append(
            "<p class='cand-resumo'>Cortado no requisito eliminatório: "
            f"{_e(resultado.get('motivo') or 'requisito não atendido')}</p>"
        )
    elif estagio == "erro":
        corpo.append(
            f"<p class='cand-resumo vazio'>Não foi possível avaliar: "
            f"{_e(linha.get('erro') or 'erro desconhecido')}</p>"
        )
    else:
        if resultado.get("resumo"):
            corpo.append(f"<p class='cand-resumo'>{_e(resultado['resumo'])}</p>")

        for nota in resultado.get("criterios", []):
            meta = pesos.get(nota.get("criterio_id"), {})
            evidencia = nota.get("evidencia") or ""
            ausente = "sem evid" in evidencia.lower()
            corpo.append(
                "<div class='criterio'><div class='criterio-topo'>"
                f"<span>{_e(meta.get('nome') or nota.get('criterio_id'))}"
                f" <span class='cabeca-meta'>peso {meta.get('peso', 0)}%</span></span>"
                f"<span class='criterio-nota'>{_e(nota.get('nota'))}/10</span>"
                "</div>"
                f"<p class='evidencia{' evidencia-ausente' if ausente else ''}'>"
                f"{_e(evidencia)}</p></div>"
            )

        listas = _lista("Pontos fortes", resultado.get("pontos_fortes") or []) + \
            _lista("Atenção", resultado.get("red_flags") or [])
        if listas:
            corpo.append(f"<div class='listas'>{listas}</div>")

        if resultado.get("divergencia"):
            corpo.append(f"<p class='aviso'>{_e(resultado['divergencia'])}</p>")
        if resultado.get("criterios_sem_resposta"):
            faltantes = ", ".join(resultado["criterios_sem_resposta"])
            corpo.append(
                f"<p class='aviso'>Sem avaliação para: {_e(faltantes)} — "
                "contaram como zero na nota final.</p>"
            )

    if linha.get("anotacao"):
        corpo.append(
            f"<div class='listas'><div><h3>Anotação do recrutador</h3>"
            f"<p>{_e(linha['anotacao'])}</p></div></div>"
        )
    corpo.append("</div>")
    return "".join(corpo)


def montar_relatorio(app_nome: str, org: Optional[dict], vaga: dict,
                     linhas: list[dict], usuario: dict) -> str:
    try:
        rubrica = Rubrica.model_validate(vaga["rubrica"]) if vaga.get("rubrica") else None
    except Exception:                                          # noqa: BLE001
        rubrica = None
    pesos = {c.id: {"nome": c.nome, "peso": c.peso} for c in (rubrica.criterios if rubrica else [])}

    chamar = sum(1 for l in linhas if l.get("recomendacao") == "chamar")
    entrevistar = sum(1 for l in linhas if l.get("decisao") == "entrevistar")
    eliminados = sum(1 for l in linhas if l.get("estagio") == "eliminado")

    corpo = "".join(
        _bloco_candidato(p, l, pesos)
        for p, l in zip(numerar_exibicao(linhas), linhas)
    ) or "<p class='vazio'>Nenhum candidato nesta seleção.</p>"

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Triagem — {_e(vaga.get('titulo'))}</title>
<style>{estilo.folha(documento=True)}{ESTILO}</style>
<script src="/static/imprimir.js" defer></script></head><body>

<div class="barra naoimprime">
  <span>Relatório pronto. Use <strong>Imprimir → Salvar como PDF</strong>.</span>
  <button id="imprimir">Imprimir</button>
</div>

<div class="cabeca">
  <div class="selo-org">{_e(org.get('nome') if org else '')}<br>{_e(app_nome)}</div>
  <h1>{_e(vaga.get('titulo'))}</h1>
  <p class="cabeca-meta">
    Relatório de triagem · {len(linhas)} candidato(s) ·
    gerado em {datetime.now():%d/%m/%Y às %H:%M} por {_e(usuario.get('nome'))} ·
    vaga aberta em {_data_br(vaga.get('criada_em'))}
  </p>
</div>

<div class="resumo-linha">
  <div><span class="resumo-valor">{len(linhas)}</span>
       <span class="resumo-rotulo">avaliados</span></div>
  <div><span class="resumo-valor">{chamar}</span>
       <span class="resumo-rotulo">recomendados</span></div>
  <div><span class="resumo-valor">{entrevistar}</span>
       <span class="resumo-rotulo">marcados p/ entrevista</span></div>
  <div><span class="resumo-valor">{eliminados}</span>
       <span class="resumo-rotulo">cortados no eliminatório</span></div>
</div>

{_bloco_rubrica(rubrica)}

<h2>Ranking</h2>
<p class="cabeca-meta" style="margin-bottom:1.2rem">
  A nota é a média ponderada das notas por critério, calculada fora do modelo.
  Cada nota vem acompanhada do trecho do currículo que a sustenta.
</p>
{corpo}

<div class="rodape">
  <p><strong>Como ler este documento.</strong> As notas foram atribuídas por um
  modelo de linguagem contra a rubrica acima, sem acesso a nome, idade, endereço,
  foto ou contato dos candidatos — esses dados foram separados antes da avaliação.
  A recomendação é um apoio à decisão, não a decisão: a escolha final é do
  recrutador.</p>
  <p>Dado pessoal tratado conforme a LGPD (Lei 13.709/2018). Retenção configurada:
  {_e(org.get('retencao_dias') if org else '—')} dias. Este relatório contém dados
  pessoais — trate-o como documento confidencial.</p>
</div>

</body></html>"""
