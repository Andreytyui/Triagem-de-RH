"""Suíte de testes da Triagem.

    python testar.py

A suíte é offline por construção: não há chamada de rede a fazer, porque quem
avalia é o Claude do próprio recrutador. Cada corrida usa um banco temporário
novo, então não encosta nos dados de produção.
"""
from __future__ import annotations

import shutil
import sys
import time

from tests.comum import Placar, preparar_ambiente

MODULOS = [
    ("Extração", "tests.test_extracao", True),      # True = precisa do reportlab
    ("Anonimização", "tests.test_anonimizacao", False),
    ("Pontuação e migração", "tests.test_pontuacao", True),
    ("Segurança", "tests.test_seguranca", False),
    ("Recuperação de senha", "tests.test_recuperacao", False),
    ("LGPD", "tests.test_lgpd", False),
    ("Conector MCP", "tests.test_mcp", False),
    ("Identidade visual", "tests.test_identidade", False),
    ("Mensagens de erro", "tests.test_mensagens", False),
    ("Diagnóstico comparativo", "tests.test_comparacao", False),
    ("Backup", "tests.test_backup", False),
    ("OCR", "tests.test_ocr", True),
]


def main() -> int:
    pasta = preparar_ambiente()
    placar = Placar()
    inicio = time.monotonic()

    print(f"Triagem — suíte de testes\nbanco temporário em {pasta}")

    tem_reportlab = True
    try:
        import reportlab                                       # noqa: F401
    except ImportError:
        tem_reportlab = False

    pulados = []
    for nome, caminho, precisa_pdf in MODULOS:
        if precisa_pdf and not tem_reportlab:
            pulados.append(nome)
            continue
        modulo = __import__(caminho, fromlist=["rodar"])
        modulo.rodar(placar)

    duracao = time.monotonic() - inicio
    print("\n" + "-" * 60)

    if pulados:
        print(f"PULADOS: {', '.join(pulados)} — instale as dependências de teste:")
        print("  pip install -r requirements-dev.txt")

    if placar.falhou:
        print(f"{len(placar.falhou)} FALHA(S), {placar.passou} passaram em {duracao:.1f}s\n")
        for falha in placar.falhou:
            print(f"  · {falha}")
        return 1

    print(f"TODOS OS {placar.passou} TESTES PASSARAM em {duracao:.1f}s")
    if pulados:
        print("(mas há grupos pulados acima)")
        return 1
    return 0


if __name__ == "__main__":
    codigo = 1
    try:
        codigo = main()
    finally:
        import os
        temporario = os.environ.get("TRIAGEM_DATA_DIR", "")
        if "triagem-teste-" in temporario:
            shutil.rmtree(temporario, ignore_errors=True)
    sys.exit(codigo)
