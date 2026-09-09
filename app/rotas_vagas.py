"""Vagas, currículos, resultados e o que o recrutador leva para a reunião.

Não há execução de triagem aqui, e é de propósito: quem avalia é o Claude do
próprio recrutador, pelo conector MCP. Estas rotas preparam o material e leem o
que já foi registrado.
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

from . import fila_ocr, storage
from .config import ALLOWED_EXTENSIONS, APP_NOME, MAX_ARQUIVOS_POR_LOTE, MAX_UPLOAD_MB
from .deps import auditar, usuario_atual, vaga_da_org
from .extraction import conferir_assinatura, extrair
from .models import DecisaoRecrutador, NovaVaga, Rubrica
from .pontuacao import numerar_exibicao, posicoes, vizinhanca
from .relatorio import montar_relatorio
from .shortlist import montar_shortlist

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vagas", tags=["triagem"])

TIPOS = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".rtf": "application/rtf",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


# ---------- Vagas ----------

@router.get("")
async def listar(incluir_arquivadas: bool = False, usuario: dict = Depends(usuario_atual)):
    return storage.listar_vagas(usuario["org_id"], incluir_arquivadas)


@router.post("", status_code=201)
async def criar(dados: NovaVaga, request: Request,
                usuario: dict = Depends(usuario_atual)):
    """Abre a vaga. A rubrica vem depois, escrita pelo recrutador ou proposta
    pelo Claude dele pelo conector — e, dos dois jeitos, aprovada por ele."""
    vaga_id = storage.criar_vaga(
        usuario["org_id"], dados.titulo.strip(), dados.descricao.strip(),
        usuario["usuario_id"],
    )
    auditar(request, usuario, "vaga.criada", "vaga", vaga_id, {"titulo": dados.titulo})
    return {"vaga_id": vaga_id, "rubrica": None}


@router.get("/{vaga_id}")
async def buscar(vaga_id: str, usuario: dict = Depends(usuario_atual)):
    vaga = vaga_da_org(vaga_id, usuario)
    vaga["curriculos"] = storage.contar_curriculos_da_vaga(usuario["org_id"], vaga_id)
    return vaga


@router.put("/{vaga_id}/rubrica")
async def aprovar_rubrica(vaga_id: str, rubrica: Rubrica, request: Request,
                          usuario: dict = Depends(usuario_atual)):
    """Sem esta aprovação, nada é avaliado. É a trava que dá o controle ao recrutador."""
    vaga_da_org(vaga_id, usuario)
    if not rubrica.criterios:
        raise HTTPException(400, "a rubrica precisa de pelo menos um critério pontuado")
    if len(rubrica.criterios) > 12:
        raise HTTPException(400, "no máximo 12 critérios — acima disso o peso de cada um some")

    rubrica.normalizar_pesos()
    storage.salvar_rubrica(usuario["org_id"], vaga_id, rubrica.model_dump(), aprovada=True)
    storage.atualizar_vaga(vaga_id, status="pronta")
    auditar(request, usuario, "rubrica.aprovada", "vaga", vaga_id,
            {"criterios": [c.id for c in rubrica.criterios]})
    return {"ok": True, "rubrica": rubrica.model_dump()}


@router.post("/{vaga_id}/arquivar")
async def arquivar(vaga_id: str, request: Request, arquivada: bool = True,
                   usuario: dict = Depends(usuario_atual)):
    vaga_da_org(vaga_id, usuario)
    storage.atualizar_vaga(vaga_id, arquivada=int(arquivada))
    auditar(request, usuario, "vaga.arquivada" if arquivada else "vaga.reaberta",
            "vaga", vaga_id)
    return {"ok": True}


@router.delete("/{vaga_id}")
async def remover(vaga_id: str, request: Request, usuario: dict = Depends(usuario_atual)):
    vaga = vaga_da_org(vaga_id, usuario)
    storage.remover_vaga(usuario["org_id"], vaga_id)
    auditar(request, usuario, "vaga.removida", "vaga", vaga_id, {"titulo": vaga["titulo"]})
    return {"ok": True}


# ---------- Upload ----------

@router.post("/{vaga_id}/curriculos")
async def enviar_curriculos(vaga_id: str, request: Request,
                            arquivos: list[UploadFile] = File(...),
                            usuario: dict = Depends(usuario_atual)):
    vaga_da_org(vaga_id, usuario)
    if len(arquivos) > MAX_ARQUIVOS_POR_LOTE:
        raise HTTPException(
            413, f"envie no máximo {MAX_ARQUIVOS_POR_LOTE} arquivos por vez"
        )

    org_id = usuario["org_id"]
    novos, repetidos, rejeitados = 0, 0, []
    por_ocr: list[dict] = []
    teto = MAX_UPLOAD_MB * 1024 * 1024

    for arquivo in arquivos:
        nome = Path(arquivo.filename or "sem-nome").name       # corta caminho do cliente
        ext = Path(nome).suffix.lower()

        if ext not in ALLOWED_EXTENSIONS:
            rejeitados.append({"arquivo": nome, "motivo": f"formato {ext or '?'} não aceito"})
            continue

        dados = await arquivo.read()
        if not dados:
            rejeitados.append({"arquivo": nome, "motivo": "arquivo vazio"})
            continue
        if len(dados) > teto:
            rejeitados.append({"arquivo": nome, "motivo": f"acima de {MAX_UPLOAD_MB} MB"})
            continue

        problema = conferir_assinatura(dados, ext)
        if problema:
            rejeitados.append({"arquivo": nome, "motivo": problema})
            continue

        try:
            documentos = await asyncio.to_thread(extrair, dados, nome)
        except Exception as exc:                               # noqa: BLE001
            rejeitados.append({"arquivo": nome, "motivo": str(exc)[:200]})
            continue

        if not documentos:
            rejeitados.append({"arquivo": nome, "motivo": "nenhum candidato encontrado"})
            continue

        # O original fica guardado: é o que sustenta o OCR do PDF escaneado e o
        # que o recrutador abre para conferir a evidência.
        guardado = False
        for doc in documentos:
            if not doc.texto.strip() and not doc.escaneado:
                motivo = doc.avisos[-1] if doc.avisos else "nenhum texto extraído"
                rejeitados.append({"arquivo": doc.arquivo, "motivo": motivo})
                continue
            if not guardado:
                await asyncio.to_thread(_guardar_original, org_id, doc, dados)
                guardado = True
            if storage.salvar_curriculo(org_id, doc):
                novos += 1
                if doc.estado_extracao == "pendente":
                    # A leitura acontece fora da requisição. O recrutador recebe
                    # a resposta agora e acompanha o progresso na tela.
                    fila_ocr.enfileirar(org_id, doc.candidato_id)
                    por_ocr.append({
                        "arquivo": doc.arquivo,
                        "estado": "na fila",
                        "confianca": None,
                        "retido": False,
                        "motivo": "",
                    })
            else:
                repetidos += 1
            storage.vincular(vaga_id, doc.candidato_id)

    total = storage.contar_curriculos_da_vaga(org_id, vaga_id)
    auditar(request, usuario, "curriculos.enviados", "vaga", vaga_id,
            {"novos": novos, "repetidos": repetidos, "rejeitados": len(rejeitados)})
    return {
        "novos": novos,
        "ja_conhecidos": repetidos,
        "rejeitados": rejeitados,
        "por_ocr": por_ocr,
        "total_na_vaga": total,
    }


def _guardar_original(org_id: str, doc, dados: bytes) -> None:
    destino = storage.pasta_org(org_id) / f"{doc.origem_hash}{doc.extensao}"
    if not destino.exists():
        destino.write_bytes(dados)


@router.delete("/{vaga_id}/curriculos/{candidato_id}")
async def remover_curriculo(vaga_id: str, candidato_id: str, request: Request,
                            usuario: dict = Depends(usuario_atual)):
    """Tira o candidato desta vaga. O currículo continua na base para outras."""
    vaga_da_org(vaga_id, usuario)
    storage.desvincular(vaga_id, candidato_id)
    auditar(request, usuario, "curriculo.desvinculado", "vaga", vaga_id,
            {"candidato_id": candidato_id})
    return {"ok": True}


@router.get("/{vaga_id}/curriculos/{candidato_id}/arquivo")
async def baixar_original(vaga_id: str, candidato_id: str, request: Request,
                          usuario: dict = Depends(usuario_atual)):
    """O currículo como ele chegou. Cada abertura fica registrada na auditoria."""
    vaga_da_org(vaga_id, usuario)
    caminho = storage.caminho_arquivo(usuario["org_id"], candidato_id)
    if not caminho:
        raise HTTPException(404, "o arquivo original não está mais disponível")

    curriculo = storage.buscar_curriculo(usuario["org_id"], candidato_id)
    auditar(request, usuario, "curriculo.aberto", "candidato", candidato_id,
            {"vaga_id": vaga_id})
    return FileResponse(
        caminho,
        media_type=TIPOS.get(curriculo.get("extensao", ""), "application/octet-stream"),
        filename=Path(curriculo["arquivo"]).name,
        content_disposition_type="inline",
    )


# ---------- Execução ----------

@router.get("/{vaga_id}/status")
async def status(vaga_id: str, usuario: dict = Depends(usuario_atual)):
    """Quanto da vaga já foi avaliado. Tudo contado na hora, nada guardado.

    Não existe `rodando`: nenhum processo nosso roda. O que diz se o Claude do
    recrutador ainda está trabalhando é `ultimo_registro_em` — o carimbo da
    última avaliação que chegou pelo conector.
    """
    vaga = vaga_da_org(vaga_id, usuario)
    resumo = storage.resumo_da_vaga(usuario["org_id"], vaga_id)
    resumo["status"] = vaga["status"]
    resumo["rubrica_ok"] = vaga["rubrica_ok"]
    return resumo


# ---------- Resultados ----------

@router.get("/{vaga_id}/resultados")
async def resultados(vaga_id: str,
                     recomendacao: Optional[str] = None,
                     decisao: Optional[str] = None,
                     busca: Optional[str] = Query(default=None, max_length=80),
                     usuario: dict = Depends(usuario_atual)):
    vaga = vaga_da_org(vaga_id, usuario)
    linhas = storage.ranking(usuario["org_id"], vaga_id)

    # A vizinhança é calculada AQUI, no servidor, e não no app.js: a nota é
    # calculada em Python, então a decomposição dela também. O navegador tem
    # todos os ingredientes (notas por critério e pesos), e é justamente por
    # isso que a regra precisa estar escrita — calcular no JS colocaria a mesma
    # aritmética em duas linguagens, que é onde as duas começam a divergir.
    #
    # Sobre a lista COMPLETA, antes de qualquer filtro: o vizinho é o do
    # ranking geral, senão o recorte inflaria as distâncias.
    try:
        rubrica_vaga = Rubrica.model_validate(vaga["rubrica"]) if vaga.get("rubrica") else None
    except Exception:                                          # noqa: BLE001
        rubrica_vaga = None
    posicao_de = posicoes(linhas)
    for linha in linhas:
        linha["vizinhanca"] = vizinhanca(linha, linhas, posicao_de, rubrica_vaga)

    if recomendacao:
        linhas = [l for l in linhas if l["recomendacao"] == recomendacao]
    if decisao:
        linhas = [l for l in linhas if l["decisao"] == decisao]
    if busca:
        alvo = busca.strip().lower()
        linhas = [
            l for l in linhas
            if alvo in (l["nome"] or "").lower() or alvo in (l["arquivo"] or "").lower()
        ]
    return linhas


@router.put("/{vaga_id}/candidatos/{candidato_id}/decisao")
async def decidir(vaga_id: str, candidato_id: str, dados: DecisaoRecrutador,
                  request: Request, usuario: dict = Depends(usuario_atual)):
    """A decisão é do recrutador. O sistema pontua; quem escolhe é a pessoa."""
    vaga_da_org(vaga_id, usuario)
    if not storage.buscar_curriculo(usuario["org_id"], candidato_id):
        raise HTTPException(404, "candidato não encontrado")

    storage.salvar_decisao(vaga_id, candidato_id, dados.decisao,
                           dados.anotacao.strip(), usuario["usuario_id"])
    auditar(request, usuario, "decisao.registrada", "candidato", candidato_id,
            {"vaga_id": vaga_id, "decisao": dados.decisao})
    return {"ok": True}


# ---------- Saídas para o recrutador ----------

# Excel e LibreOffice interpretam célula que começa com um destes como fórmula.
# O nome sai do currículo e a anotação sai do teclado do recrutador — nenhum dos
# dois é nosso, e um "=HYPERLINK(...)" ali vira fórmula executada na máquina de
# quem abre o arquivo, que é como esse tipo de planilha exfiltra dado. A aspa
# simples à frente força leitura como texto e não aparece na célula.
INICIAIS_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r", "\n")


def _texto_para_planilha(valor) -> str:
    """Só para coluna de texto: prefixar número o transformaria em texto e
    quebraria a soma que o recrutador faz em cima do Score."""
    texto = "" if valor is None else str(valor)
    return f"'{texto}" if texto.startswith(INICIAIS_DE_FORMULA) else texto

@router.get("/{vaga_id}/export.csv")
async def exportar_csv(vaga_id: str, request: Request,
                       usuario: dict = Depends(usuario_atual)):
    vaga = vaga_da_org(vaga_id, usuario)
    rubrica = Rubrica.model_validate(vaga["rubrica"]) if vaga["rubrica"] else None
    criterios = rubrica.criterios if rubrica else []

    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";")                # ; é o que o Excel-BR espera
    escritor.writerow([
        "Posição", "Nome", "E-mail", "Telefone", "Score", "Recomendação",
        "Decisão", "Confiança", "Resumo", "Pontos fortes", "Atenção",
        # O nome do critério vem da rubrica, que o recrutador escreve: é texto de
        # fora, e passa pela mesma trava que as células.
        *[_texto_para_planilha(c.nome) for c in criterios], "Anotação", "Arquivo",
    ])

    linhas = storage.ranking(usuario["org_id"], vaga_id)
    # Célula vazia, não traço: quem não ocupa lugar no ranking não recebe número
    # de colocação, e vazio é o que a planilha do recrutador sabe ignorar.
    for posicao, linha in zip(numerar_exibicao(linhas, vazio=""), linhas):
        resultado = linha["resultado"] or {}
        notas = {n["criterio_id"]: n["nota"] for n in resultado.get("criterios", [])}
        contato = linha["contato"] or {}
        escritor.writerow([
            # Posição, Score e as notas por critério ficam crus: são números que o
            # recrutador soma e ordena na planilha, e nós é que os geramos.
            posicao,
            _texto_para_planilha(linha["nome"]),
            _texto_para_planilha(contato.get("email", "")),
            _texto_para_planilha(contato.get("telefone", "")),
            linha["score_final"] if linha["score_final"] is not None else "",
            _texto_para_planilha(linha["recomendacao"] or linha["estagio"]),
            _texto_para_planilha(linha["decisao"]),
            _texto_para_planilha(linha["confianca"] or ""),
            _texto_para_planilha(resultado.get("resumo") or resultado.get("motivo", "")),
            _texto_para_planilha(" | ".join(resultado.get("pontos_fortes", []))),
            _texto_para_planilha(" | ".join(resultado.get("red_flags", []))),
            *[notas.get(c.id, "") for c in criterios],
            _texto_para_planilha(linha["anotacao"]),
            _texto_para_planilha(linha["arquivo"]),
        ])

    auditar(request, usuario, "resultados.exportados", "vaga", vaga_id,
            {"formato": "csv", "linhas": len(linhas)})

    slug = "".join(ch if ch.isalnum() else "-" for ch in vaga["titulo"][:40]).strip("-")
    nome = f"triagem-{slug or 'vaga'}-{datetime.now():%Y-%m-%d}.csv"
    return StreamingResponse(
        iter([buffer.getvalue().encode("utf-8-sig")]),          # BOM: acentos no Excel
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.get("/{vaga_id}/shortlist", response_class=HTMLResponse)
async def shortlist(vaga_id: str, request: Request,
                    candidatos: Optional[str] = Query(default=None, max_length=800),
                    usuario: dict = Depends(usuario_atual)):
    """O documento que o recrutador entrega ao cliente dele.

    Por padrão traz quem ele marcou como "entrevistar" — a marcação que ele já
    faz para decidir. `candidatos` permite um recorte pontual; são hashes de
    conteúdo, não dado pessoal, então podem viajar na query string.
    """
    vaga = vaga_da_org(vaga_id, usuario)
    linhas = storage.ranking(usuario["org_id"], vaga_id)

    if candidatos:
        escolhidos = {c.strip() for c in candidatos.split(",") if c.strip()}
        linhas = [l for l in linhas if l["candidato_id"] in escolhidos]
    else:
        linhas = [l for l in linhas if l["decisao"] == "entrevistar"]

    # Um shortlist só existe de quem foi avaliado: eliminado e erro não entram.
    linhas = [l for l in linhas if l["estagio"] == "avaliado"]

    org = storage.buscar_organizacao(usuario["org_id"])
    auditar(request, usuario, "shortlist.gerado", "vaga", vaga_id,
            {"candidatos": len(linhas)})
    return HTMLResponse(montar_shortlist(org, vaga, linhas, usuario))


@router.get("/{vaga_id}/relatorio", response_class=HTMLResponse)
async def relatorio(vaga_id: str, request: Request,
                    somente: Optional[str] = None,
                    usuario: dict = Depends(usuario_atual)):
    """Página pronta para imprimir ou salvar em PDF. É o anexo da ata da reunião."""
    vaga = vaga_da_org(vaga_id, usuario)
    linhas = storage.ranking(usuario["org_id"], vaga_id)
    if somente:
        alvos = {s.strip() for s in somente.split(",") if s.strip()}
        linhas = [l for l in linhas if l["recomendacao"] in alvos or l["decisao"] in alvos]

    org = storage.buscar_organizacao(usuario["org_id"])
    auditar(request, usuario, "relatorio.gerado", "vaga", vaga_id,
            {"candidatos": len(linhas)})
    return HTMLResponse(montar_relatorio(APP_NOME, org, vaga, linhas, usuario))
