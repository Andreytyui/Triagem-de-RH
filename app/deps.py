"""Dependências de acesso: quem é o usuário, de qual organização, com que papel.

Toda rota de dados exige `usuario_atual`. É essa função que amarra a organização
na requisição — e é por ela que o isolamento entre clientes não depende de o
programador lembrar de filtrar.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request

from . import storage
from .config import COOKIE_SESSAO
from .security import hash_token


def ip_do(request: Request) -> str:
    """Atrás de proxy, o IP real vem no cabeçalho — e só confiamos no primeiro salto."""
    encaminhado = request.headers.get("x-forwarded-for", "")
    if encaminhado:
        return encaminhado.split(",")[0].strip()[:45]
    return request.client.host if request.client else ""


def sessao_opcional(request: Request) -> Optional[dict]:
    token = request.cookies.get(COOKIE_SESSAO)
    if not token:
        return None
    sessao = storage.buscar_sessao(hash_token(token))
    if not sessao or not sessao.get("ativo"):
        return None
    return sessao


def usuario_atual(request: Request) -> dict:
    sessao = sessao_opcional(request)
    if not sessao:
        raise HTTPException(401, "sessão expirada; entre de novo")
    request.state.sessao = sessao
    return sessao


def admin_atual(usuario: dict = Depends(usuario_atual)) -> dict:
    if usuario.get("papel") != "admin":
        raise HTTPException(403, "esta ação é do administrador da conta")
    return usuario


def organizacao_atual(usuario: dict = Depends(usuario_atual)) -> dict:
    org = storage.buscar_organizacao(usuario["org_id"])
    if not org:
        raise HTTPException(401, "organização não encontrada")
    if not org.get("ativa"):
        raise HTTPException(403, "esta conta está suspensa")
    return org


def auditar(request: Request, usuario: dict, acao: str, entidade: str = "",
            entidade_id: str = "", detalhe=None) -> None:
    storage.registrar_auditoria(
        org_id=usuario.get("org_id"),
        usuario_id=usuario.get("usuario_id"),
        acao=acao,
        entidade=entidade,
        entidade_id=entidade_id,
        detalhe=detalhe,
        ip=ip_do(request),
    )


def vaga_da_org(vaga_id: str, usuario: dict) -> dict:
    """Busca a vaga já filtrada pela organização. 404 se for de outra conta —
    de propósito: 403 confirmaria que a vaga existe em algum lugar."""
    vaga = storage.buscar_vaga(usuario["org_id"], vaga_id)
    if not vaga:
        raise HTTPException(404, "vaga não encontrada")
    return vaga
