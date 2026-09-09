"""Expurgo por retenção.

Currículo é dado pessoal. A LGPD manda eliminar quando acaba a finalidade — aqui
isso vira um prazo por organização, aplicado sozinho, sem depender de alguém
lembrar. O que sai do banco sai também do disco.
"""
from __future__ import annotations

import asyncio
import logging

from . import storage
from .config import EXPURGO_INTERVALO_H, RETENCAO_DIAS_PADRAO

log = logging.getLogger(__name__)


def expurgar_organizacao(org: dict) -> int:
    dias = int(org.get("retencao_dias") or RETENCAO_DIAS_PADRAO)
    vencidos = storage.candidatos_vencidos(org["id"], dias)
    apagados = 0
    for candidato_id in vencidos:
        if storage.apagar_candidato(org["id"], candidato_id):
            apagados += 1
    if apagados:
        storage.registrar_auditoria(
            org["id"], None, "retencao.expurgo", "organizacao", org["id"],
            {"apagados": apagados, "retencao_dias": dias},
        )
        log.info("expurgo: %d currículo(s) apagado(s) na organização %s (%d dias)",
                 apagados, org["nome"], dias)
    return apagados


def expurgar_tudo() -> dict:
    """Uma passada em todas as organizações. Devolve o que apagou, por conta."""
    resultado: dict[str, int] = {}
    for org in storage.organizacoes_ativas():
        try:
            resultado[org["id"]] = expurgar_organizacao(org)
        except Exception:                                      # noqa: BLE001
            log.exception("falha no expurgo da organização %s", org["id"])
            resultado[org["id"]] = -1
    storage.limpar_sessoes_vencidas()
    storage.limpar_auditoria_antiga()
    return resultado


async def rodar_periodicamente() -> None:
    """Laço de manutenção do servidor. Roda no boot e depois no intervalo."""
    while True:
        try:
            await asyncio.to_thread(expurgar_tudo)
        except asyncio.CancelledError:
            raise
        except Exception:                                      # noqa: BLE001
            log.exception("falha no ciclo de expurgo")
        await asyncio.sleep(max(EXPURGO_INTERVALO_H, 1) * 3600)
