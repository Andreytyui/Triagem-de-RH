"""Apoio dos testes: ambiente isolado e PDFs de mentira.

A suíte é inteiramente offline — não existe mais nenhuma chamada de rede para
dublar, porque quem avalia é o Claude do recrutador, fora do servidor.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def preparar_ambiente() -> Path:
    """Precisa rodar ANTES de importar app.config — é ele que fixa os caminhos."""
    pasta = Path(tempfile.mkdtemp(prefix="triagem-teste-"))
    os.environ["TRIAGEM_DATA_DIR"] = str(pasta)
    os.environ["TRIAGEM_SECRET_KEY"] = "segredo-de-teste-nao-use-em-producao-0123456789"
    os.environ["PERMITIR_CADASTRO"] = "true"
    os.environ["CODIGO_CONVITE"] = ""
    os.environ["EXPURGO_INTERVALO_H"] = "24"
    os.environ["LOG_NIVEL"] = "ERROR"
    return pasta


# ---------- Contadores de teste ----------

class Placar:
    def __init__(self) -> None:
        self.passou = 0
        self.falhou: list[str] = []

    def ok(self, mensagem: str) -> None:
        self.passou += 1
        print(f"  [ok] {mensagem}")

    def erro(self, titulo: str, detalhe: str) -> None:
        self.falhou.append(f"{titulo}: {detalhe}")
        print(f"  [FALHOU] {titulo}\n           {detalhe}")

    def rodar(self, titulo: str, funcao) -> None:
        try:
            resultado = funcao()
            self.ok(f"{titulo}{f' — {resultado}' if resultado else ''}")
        except AssertionError as exc:
            self.erro(titulo, str(exc) or "asserção falhou")
        except Exception as exc:                               # noqa: BLE001
            import traceback
            linha = traceback.format_exc().strip().splitlines()[-1]
            self.erro(titulo, f"{type(exc).__name__}: {exc} ({linha})")


# ---------- PDFs de mentira ----------

def pdf_com_texto(linhas: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    for i, linha in enumerate(linhas):
        c.drawString(60, 780 - i * 22, linha)
    c.save()
    return buffer.getvalue()


def pdf_sem_texto() -> bytes:
    """Imita currículo escaneado: só desenho, nada que o pdfplumber leia."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.rect(60, 600, 400, 150, fill=1)
    c.circle(300, 400, 80, fill=1)
    c.save()
    return buffer.getvalue()
