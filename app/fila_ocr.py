"""Fila de OCR: o upload responde na hora, a leitura acontece depois.

O problema que isto resolve é de produção, e só existe no modo hospedado. O OCR
leva de 2 a 6 segundos por página, e o recrutador do documento fundacional
arrasta os 150 currículos de uma vez — uns 15 escaneados. Fazendo o OCR dentro
da requisição de upload, ela ficaria de um a três minutos no ar, o que estoura
o tempo limite de qualquer proxy na frente do servidor. O recrutador veria um
erro de rede depois de esperar, sem saber se os arquivos entraram ou não.

A alternativa mais simples seria limitar quantos escaneados cabem por remessa.
Foi descartada por um motivo de produto: o recrutador já disse o que acontece
quando a ferramenta o obriga a separar arquivos — *"se a ferramenta recusar
metade dos arquivos, eu vou ter mais trabalho, não menos"*. Ele arrasta a pasta
inteira, e essa é a interação que precisa continuar existindo.

Então o escaneado entra no banco imediatamente, marcado como `pendente`, e um
trabalhador em segundo plano faz o OCR, a anonimização e a decisão de retenção —
exatamente as mesmas, no mesmo código. O que muda é só quando acontece.

Duas garantias que valem registrar:

**Nada é perdido no meio do caminho.** O que ficou pendente é reenfileirado no
boot seguinte; se o servidor cair no meio de uma leitura, o currículo volta para
a fila em vez de ficar preso para sempre.

**Pendente não é erro.** Enquanto o OCR não rodou, o currículo conta como
pendente no painel — não como falha. Falha é o que já foi tentado e não deu.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from . import storage
from .anonimizacao import parse_deterministico
from .config import OCR_ATIVO, OCR_TRABALHADORES

log = logging.getLogger(__name__)

_fila: Optional[asyncio.Queue] = None
_semaforo: Optional[asyncio.Semaphore] = None


def _garantir_fila() -> asyncio.Queue:
    global _fila, _semaforo
    if _fila is None:
        _fila = asyncio.Queue()
    if _semaforo is None:
        # O OCR é preso a CPU. Mais trabalhadores que núcleos úteis só faz a
        # máquina brigar consigo mesma e atrapalhar quem está navegando na tela.
        _semaforo = asyncio.Semaphore(max(1, OCR_TRABALHADORES))
    return _fila


def enfileirar(org_id: str, candidato_id: str) -> None:
    """Marca o currículo para leitura. Chamado de dentro da rota de upload."""
    try:
        _garantir_fila().put_nowait((org_id, candidato_id))
    except RuntimeError:                                       # pragma: no cover
        # Sem laço de eventos rodando (script, teste síncrono): não enfileira, e
        # o boot seguinte recolhe pelo estado no banco.
        log.debug("sem laço de eventos; %s fica para o próximo boot", candidato_id)


def processar(org_id: str, candidato_id: str) -> dict:
    """Faz o OCR de um currículo e grava o resultado. Síncrono, roda em thread.

    Devolve o que aconteceu, para o log e para os testes. Nunca levanta exceção:
    falha aqui vira estado `falhou` com motivo, que o recrutador lê na tela.
    """
    curriculo = storage.buscar_curriculo(org_id, candidato_id)
    if not curriculo:
        return {"estado": "sumiu", "motivo": "currículo não existe mais"}
    if curriculo.get("estado_extracao") != "pendente":
        return {"estado": curriculo.get("estado_extracao") or "pronto",
                "motivo": "já havia sido processado"}

    caminho = storage.caminho_arquivo(org_id, candidato_id)
    if not caminho:
        storage.atualizar_curriculo(
            org_id, candidato_id, estado_extracao="falhou",
            avisos=(curriculo.get("avisos") or []) + [
                "o arquivo original não está mais no disco para ser lido por OCR"
            ],
        )
        return {"estado": "falhou", "motivo": "arquivo original ausente"}

    avisos = list(curriculo.get("avisos") or [])
    from .ocr import OcrIndisponivel, ler_pdf

    if not OCR_ATIVO:
        storage.atualizar_curriculo(
            org_id, candidato_id, estado_extracao="falhou",
            avisos=avisos + ["PDF escaneado; o OCR está desligado neste servidor"])
        return {"estado": "falhou", "motivo": "OCR desligado"}

    try:
        resultado = ler_pdf(caminho.read_bytes())
    except OcrIndisponivel as exc:
        log.warning("OCR indisponível para %s: %s", candidato_id, exc)
        storage.atualizar_curriculo(
            org_id, candidato_id, estado_extracao="falhou",
            # O motivo técnico ("instale o pacote tesseract-ocr-por") é do
            # operador do servidor, não do recrutador: ele não pode fazer nada
            # com isso, e é o jargão que a regra da Pigmento proíbe na tela.
            # Vai para o log; o aviso guarda só o que dá para agir.
            avisos=avisos + ["não foi possível extrair o texto deste PDF escaneado"])
        return {"estado": "falhou", "motivo": str(exc)}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("OCR falhou em %s: %s", candidato_id, exc)
        storage.atualizar_curriculo(
            org_id, candidato_id, estado_extracao="falhou",
            avisos=avisos + [f"PDF escaneado; o OCR não conseguiu ler: {exc}"])
        return {"estado": "falhou", "motivo": str(exc)}

    if not resultado.texto.strip():
        storage.atualizar_curriculo(
            org_id, candidato_id, estado_extracao="falhou",
            avisos=avisos + ["PDF escaneado; o OCR não encontrou texto no documento"])
        return {"estado": "falhou", "motivo": "OCR não encontrou texto"}

    from .extraction import _limpar

    avisos.append("PDF escaneado; texto extraído por OCR")
    avisos.extend(resultado.avisos)
    texto = _limpar(resultado.texto, avisos)

    # A mesma anonimização e a mesma decisão de retenção que rodariam no upload.
    # O que mudou foi o momento, não a regra.
    parse, separacao = parse_deterministico(texto, de_ocr=True)
    storage.atualizar_curriculo(
        org_id, candidato_id,
        texto=texto, origem_texto="ocr", ocr_confianca=resultado.confianca,
        estado_extracao="pronto", avisos=avisos, parse=parse,
    )
    log.info("OCR concluído para %s (confiança %s)", candidato_id, resultado.confianca)
    return {
        "estado": "pronto",
        "confianca": resultado.confianca,
        "retido": separacao.retido,
        "motivo": separacao.motivo_retencao,
    }


async def _trabalhar() -> None:
    fila = _garantir_fila()
    while True:
        org_id, candidato_id = await fila.get()
        try:
            async with _semaforo:
                await asyncio.to_thread(processar, org_id, candidato_id)
        except asyncio.CancelledError:
            raise
        except Exception:                                      # noqa: BLE001
            log.exception("falha ao processar OCR de %s", candidato_id)
        finally:
            fila.task_done()


async def rodar() -> None:
    """Trabalhador da fila. Recolhe o que ficou pendente e fica escutando."""
    fila = _garantir_fila()

    # Se o servidor caiu no meio de uma leitura, o currículo ficou 'pendente' e
    # ninguém mais o pegaria. Recolher no boot é o que evita o currículo preso.
    try:
        pendentes = await asyncio.to_thread(storage.curriculos_pendentes_de_ocr)
    except Exception:                                          # noqa: BLE001
        log.exception("não foi possível recolher os currículos pendentes de OCR")
        pendentes = []
    if pendentes:
        log.info("%d currículo(s) pendente(s) de OCR recolhido(s) do boot anterior",
                 len(pendentes))
        for pendente in pendentes:
            fila.put_nowait((pendente["org_id"], pendente["candidato_id"]))

    await _trabalhar()
