"""OCR local do PDF escaneado. Sem custo variável, sem rede, sem modelo.

Cerca de 10% dos currículos que o recrutador recebe chegam digitalizados — papel
impresso e passado no scanner. Sem isto, esses candidatos simplesmente não são
avaliados.

O texto que sai daqui é pior que o de um PDF com texto embutido, e o módulo diz
isso em vez de fingir: `confianca` é 'baixa' quando o Tesseract não teve certeza,
e essa marca acompanha o currículo até a tela e até o bloco entregue ao conector.

Uma coisa que este módulo nunca faz: devolver a imagem. A página rasterizada
existe só dentro desta função, o tempo de rodar o OCR. Mandar a imagem do
currículo para o conector devolveria nome, foto e endereço para quem pontua — é
a garantia central do produto, e ela vive aqui.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Optional

from .config import (
    MAX_PAGINAS_PDF,
    OCR_CONFIANCA_MINIMA,
    OCR_DPI,
    OCR_IDIOMA,
    OCR_MIN_PALAVRAS,
)

log = logging.getLogger(__name__)


@dataclass
class ResultadoOCR:
    texto: str = ""
    confianca: str = "baixa"          # 'alta' | 'baixa'
    confianca_media: float = 0.0      # 0 a 100, como o Tesseract reporta
    palavras: int = 0
    paginas: int = 0
    avisos: list[str] = field(default_factory=list)


class OcrIndisponivel(RuntimeError):
    """Falta o Tesseract, o idioma português ou uma das bibliotecas."""


def disponivel() -> tuple[bool, str]:
    """(dá para rodar OCR, motivo quando não dá). Nunca levanta exceção.

    A interface usa isto para explicar a ausência em vez de deixar o recrutador
    achando que o arquivo dele é que estava ruim.
    """
    try:
        import pytesseract
    except ImportError:
        return False, "o pacote pytesseract não está instalado"

    try:
        pytesseract.get_tesseract_version()
    except Exception:                                          # noqa: BLE001
        return False, (
            "o programa Tesseract não está instalado neste servidor; "
            "PDF escaneado não pode ser lido"
        )

    try:
        idiomas = set(pytesseract.get_languages(config=""))
    except Exception:                                          # noqa: BLE001
        idiomas = set()
    if idiomas and OCR_IDIOMA.split("+")[0] not in idiomas:
        return False, (
            f"o Tesseract está instalado mas sem o idioma '{OCR_IDIOMA}' "
            "(instale o pacote tesseract-ocr-por)"
        )

    try:
        import fitz                                            # noqa: F401
    except ImportError:
        try:
            import pymupdf                                     # noqa: F401
        except ImportError:
            return False, "o pacote pymupdf não está instalado"

    return True, ""


def _abrir_pdf(dados: bytes):
    try:
        import pymupdf
        return pymupdf.open(stream=dados, filetype="pdf")
    except ImportError:
        import fitz
        return fitz.open(stream=dados, filetype="pdf")


def ler_pdf(dados: bytes, max_paginas: Optional[int] = None) -> ResultadoOCR:
    """Rasteriza cada página e passa no Tesseract. A imagem morre aqui dentro."""
    ok, motivo = disponivel()
    if not ok:
        raise OcrIndisponivel(motivo)

    import pytesseract
    from PIL import Image

    limite = max_paginas or MAX_PAGINAS_PDF
    resultado = ResultadoOCR()
    partes: list[str] = []
    confiancas: list[float] = []

    documento = _abrir_pdf(dados)
    try:
        resultado.paginas = min(len(documento), limite)
        for numero in range(resultado.paginas):
            pagina = documento[numero]
            # `dpi` no lugar de zoom: o Tesseract trabalha melhor perto de 300.
            pixmap = pagina.get_pixmap(dpi=OCR_DPI)
            imagem = Image.open(io.BytesIO(pixmap.tobytes("png")))
            try:
                dados_ocr = pytesseract.image_to_data(
                    imagem, lang=OCR_IDIOMA,
                    output_type=pytesseract.Output.DICT,
                )
            finally:
                imagem.close()

            linha: list[str] = []
            for texto, confianca in zip(dados_ocr["text"], dados_ocr["conf"]):
                texto = (texto or "").strip()
                try:
                    confianca = float(confianca)
                except (TypeError, ValueError):
                    continue
                # -1 é o que o Tesseract devolve para bloco sem palavra nenhuma.
                if not texto or confianca < 0:
                    continue
                linha.append(texto)
                confiancas.append(confianca)
            if linha:
                partes.append(" ".join(linha))
    finally:
        documento.close()

    resultado.texto = "\n".join(partes).strip()
    resultado.palavras = len(confiancas)
    resultado.confianca_media = (
        round(sum(confiancas) / len(confiancas), 1) if confiancas else 0.0
    )

    # Duas maneiras de o OCR ser ruim: ler pouco, ou ler inseguro. As duas contam.
    if resultado.palavras < OCR_MIN_PALAVRAS:
        resultado.confianca = "baixa"
        resultado.avisos.append(
            f"o OCR extraiu só {resultado.palavras} palavra(s) deste documento"
        )
    elif resultado.confianca_media < OCR_CONFIANCA_MINIMA:
        resultado.confianca = "baixa"
        resultado.avisos.append(
            f"texto extraído por OCR com confiança média de "
            f"{resultado.confianca_media:.0f}%; a leitura pode ter falhas"
        )
    else:
        resultado.confianca = "alta"

    return resultado
