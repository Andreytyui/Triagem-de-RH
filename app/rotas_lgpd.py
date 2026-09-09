"""LGPD: o que responde a um pedido de titular e o que prova o que foi feito.

Um candidato tem direito a saber o que a empresa guarda sobre ele, a receber
uma cópia e a pedir exclusão. Estas rotas existem para o recrutador atender esse
pedido em minutos, e para deixar registrado que atendeu.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from . import retencao, storage
from .config import AUDITORIA_RETENCAO_DIAS
from .deps import admin_atual, auditar, organizacao_atual, usuario_atual

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/lgpd", tags=["lgpd"])


@router.get("/resumo")
async def resumo(org: dict = Depends(organizacao_atual)):
    """O painel de conformidade: o que está guardado e por quanto tempo."""
    conn = storage.conexao()
    curriculos = conn.execute(
        "SELECT COUNT(*) FROM curriculos WHERE org_id=?", (org["id"],)
    ).fetchone()[0]
    vagas = conn.execute(
        "SELECT COUNT(*) FROM vagas WHERE org_id=?", (org["id"],)
    ).fetchone()[0]
    mais_antigo = conn.execute(
        "SELECT MIN(criado_em) FROM curriculos WHERE org_id=?", (org["id"],)
    ).fetchone()[0]
    vencidos = len(storage.candidatos_vencidos(org["id"], org["retencao_dias"]))

    return {
        "curriculos_guardados": curriculos,
        "vagas": vagas,
        "curriculo_mais_antigo": mais_antigo,
        "retencao_dias": org["retencao_dias"],
        "a_expurgar": vencidos,
        "auditoria_retencao_dias": AUDITORIA_RETENCAO_DIAS,
        "base_legal": "legítimo interesse em processo seletivo (art. 7º, IX, LGPD)",
    }


@router.get("/buscar")
async def buscar(termo: str = Query(min_length=3, max_length=120),
                 request: Request = None,
                 usuario: dict = Depends(usuario_atual)):
    """Acha o titular por nome, e-mail ou telefone para atender o pedido dele."""
    achados = storage.procurar_candidatos(usuario["org_id"], termo)
    auditar(request, usuario, "lgpd.busca", detalhe={"termo": termo, "achados": len(achados)})
    return achados


@router.get("/candidato/{candidato_id}")
async def exportar(candidato_id: str, request: Request,
                   usuario: dict = Depends(usuario_atual)):
    """Cópia de tudo que a organização guarda sobre a pessoa, em JSON."""
    dados = storage.exportar_candidato(usuario["org_id"], candidato_id)
    if not dados:
        raise HTTPException(404, "candidato não encontrado nesta organização")

    auditar(request, usuario, "lgpd.exportacao", "candidato", candidato_id)
    conteudo = json.dumps(dados, ensure_ascii=False, indent=2, default=str)
    return StreamingResponse(
        iter([conteudo.encode("utf-8")]),
        media_type="application/json",
        headers={
            "Content-Disposition":
                f'attachment; filename="dados-candidato-{candidato_id}.json"'
        },
    )


@router.delete("/candidato/{candidato_id}")
async def apagar(candidato_id: str, request: Request,
                 usuario: dict = Depends(usuario_atual)):
    """Direito à eliminação. Some o currículo, as avaliações e o arquivo original."""
    dados = storage.exportar_candidato(usuario["org_id"], candidato_id)
    if not dados:
        raise HTTPException(404, "candidato não encontrado nesta organização")

    identificacao = (dados["curriculo"].get("parse") or {}).get("identificacao") or {}
    storage.apagar_candidato(usuario["org_id"], candidato_id)
    # O registro fica; o dado pessoal não. É assim que se prova o atendimento.
    auditar(request, usuario, "lgpd.exclusao", "candidato", candidato_id,
            {"arquivo": dados["curriculo"].get("arquivo"),
             "tinha_email": bool(identificacao.get("email")),
             "avaliacoes_removidas": len(dados["avaliacoes"])})
    return {"ok": True, "candidato_id": candidato_id}


@router.post("/expurgo")
async def expurgar_agora(request: Request, admin: dict = Depends(admin_atual),
                         org: dict = Depends(organizacao_atual)):
    """Aplica a retenção na hora, sem esperar o ciclo automático."""
    apagados = retencao.expurgar_organizacao(org)
    auditar(request, admin, "lgpd.expurgo_manual", "organizacao", org["id"],
            {"apagados": apagados})
    return {"ok": True, "apagados": apagados}


@router.get("/auditoria")
async def auditoria(limite: int = Query(default=200, ge=1, le=1000),
                    admin: dict = Depends(admin_atual)):
    """Quem fez o quê. É o que se mostra numa auditoria ou num incidente."""
    return storage.listar_auditoria(admin["org_id"], limite)
