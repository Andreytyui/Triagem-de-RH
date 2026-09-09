"""Estágio 0: transformar arquivo em texto. Sem IA, sem custo, sem rede."""
from __future__ import annotations

from .comum import Placar, pdf_com_texto, pdf_sem_texto


def rodar(placar: Placar) -> None:
    from app import extraction
    from app.config import MAX_CHARS_CURRICULO, MIN_CHARS_TEXTO_UTIL

    print("\nExtração")

    # ---- PDF com texto ----
    def pdf_normal():
        # Texto de um currículo real de uma página. Abaixo de 220 caracteres o
        # sistema conclui, com razão, que o PDF é escaneado.
        dados = pdf_com_texto([
            "Maria Souza",
            "maria@exemplo.com | (81) 99999-0000 | Recife, PE",
            "",
            "ANALISTA DE SUPORTE PLENO",
            "Sete anos atendendo infraestrutura corporativa em ambiente Microsoft.",
            "",
            "EXPERIENCIA",
            "Analista de suporte N2 - Empresa Alfa - 2021 ate hoje",
            "  Atendimento de chamados com SLA de 4 horas, media de 40 por semana.",
            "  Administracao de Active Directory, GPO e VPN para 300 usuarios.",
            "  Reduzi o tempo medio de resolucao de 9h para 3h em doze meses.",
            "Analista de suporte N1 - Empresa Beta - 2018 a 2021",
            "  Primeiro atendimento, triagem e escalonamento no Zendesk.",
            "",
            "FORMACAO",
            "Tecnologo em Redes de Computadores - Faculdade Gama - 2021",
            "",
            "IDIOMAS: ingles tecnico para leitura de documentacao",
        ])
        docs = extraction.extrair(dados, "maria.pdf")
        assert len(docs) == 1, f"esperava 1 documento, veio {len(docs)}"
        assert "Maria Souza" in docs[0].texto, docs[0].texto[:200]
        assert not docs[0].escaneado, "PDF com texto não deveria ser marcado como escaneado"
        assert docs[0].origem_hash, "o hash do arquivo não foi preenchido"
        assert docs[0].extensao == ".pdf"
        return f"{len(docs[0].texto)} caracteres lidos"

    placar.rodar("PDF com texto é lido direto", pdf_normal)

    # ---- PDF escaneado: o bug que quebrava o produto ----
    def pdf_escaneado():
        docs = extraction.extrair(pdf_sem_texto(), "escaneado.pdf")
        doc = docs[0]
        assert len(doc.texto) < MIN_CHARS_TEXTO_UTIL, (
            f"o PDF de teste tinha texto demais ({len(doc.texto)})"
        )
        assert doc.escaneado, "PDF sem texto tem de ser marcado como escaneado"
        assert doc.origem_hash, "sem o hash não dá para reencontrar o arquivo no disco"
        return "marcado para visão"

    placar.rodar("PDF escaneado é marcado para OCR", pdf_escaneado)

    # ---- Planilha de ATS ----
    def planilha():
        csv_bytes = (
            "Nome;Email;Cargo atual;Resumo\n"
            "Joao Lima;joao@ex.com;Analista N1;Suporte ha 3 anos\n"
            "Ana Reis;ana@ex.com;Analista N2;Redes e VPN\n"
        ).encode()
        docs = extraction.extrair(csv_bytes, "export_ats.csv")
        assert len(docs) == 2, f"esperava 2 candidatos, veio {len(docs)}"
        assert all(d.origem == "planilha" for d in docs)
        assert "Joao Lima" in docs[0].arquivo, docs[0].arquivo
        assert len({d.candidato_id for d in docs}) == 2, "as duas linhas viraram o mesmo id"
        return f"{len(docs)} candidatos"

    placar.rodar("Planilha vira um candidato por linha", planilha)

    # ---- Deduplicação ----
    def dedup():
        dados = pdf_com_texto(["Carlos Dias", "carlos@ex.com", "Analista de dados senior"])
        a = extraction.extrair(dados, "carlos.pdf")[0]
        b = extraction.extrair(dados, "copia-do-carlos.pdf")[0]
        assert a.candidato_id == b.candidato_id, "o mesmo arquivo gerou ids diferentes"

        outro = extraction.extrair(pdf_com_texto(["Outra pessoa"]), "carlos.pdf")[0]
        assert outro.candidato_id != a.candidato_id, "arquivos diferentes colidiram no id"
        return "id vem do conteúdo, não do nome do arquivo"

    placar.rodar("Arquivo repetido é reconhecido pelo conteúdo", dedup)

    # ---- Assinatura de arquivo ----
    def assinatura():
        assert extraction.conferir_assinatura(b"%PDF-1.7 ...", ".pdf") is None
        problema = extraction.conferir_assinatura(b"MZ\x90\x00programa", ".pdf")
        assert problema, "executável renomeado para .pdf passou na conferência"
        assert extraction.conferir_assinatura(b"PK\x03\x04zip", ".docx") is None
        assert extraction.conferir_assinatura(b"qualquer coisa", ".txt") is None
        return "executável disfarçado de PDF é barrado"

    placar.rodar("Extensão trocada é detectada pela assinatura", assinatura)

    # ---- Truncamento avisado ----
    def truncar():
        avisos: list[str] = []
        gigante = "linha de curriculo muito repetida. " * 3000
        texto = extraction._limpar(gigante, avisos)
        assert len(texto) == MAX_CHARS_CURRICULO, len(texto)
        assert avisos, "cortou o currículo sem avisar ninguém"
        assert "muito longo" in avisos[0]
        return f"cortado em {MAX_CHARS_CURRICULO} com aviso"

    placar.rodar("Currículo longo demais é cortado com aviso", truncar)

    # ---- Texto puro e acentuação ----
    def acentos():
        docs = extraction.extrair(
            "Gestão de operações — atuação em três estados".encode("cp1252"),
            "curriculo.txt",
        )
        assert "Gest" in docs[0].texto, docs[0].texto
        assert "operaç" in docs[0].texto or "opera" in docs[0].texto
        return "cp1252 decodificado"

    placar.rodar("Arquivo com acento em codificação antiga é lido", acentos)

    _doc_legado(placar)


def _doc_legado(placar) -> None:
    """`.doc` e `.rtf` antigos, o formato que o recrutador citou como certo de
    aparecer ("o .doc velho de gente que usa Office 2010").

    Só roda onde o LibreOffice existe. O que este teste protege é a busca pelo
    binário: o instalador do Windows não põe o `soffice` no PATH, e com
    `shutil.which` sozinho uma máquina com LibreOffice instalado recusaria todo
    `.doc` com uma mensagem dizendo que ele não está instalado.
    """
    from app import extraction

    binario = extraction.achar_libreoffice()
    if not binario:
        print("  [pulado] .doc legado — LibreOffice não está instalado neste servidor")
        return

    def rtf_vira_texto():
        corpo = "\\par\n".join([
            "Joana Ribeiro Martins",
            "joana.martins@exemplo.com",
            "RESUMO PROFISSIONAL",
            "Analista de suporte tecnico N2 com SLA de 4 horas.",
            "Administracao de Active Directory: contas e GPO.",
        ])
        rtf = ("{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Arial;}}\\fs20\n"
               + corpo + "\n}").encode("latin-1")

        docs = extraction.extrair(rtf, "curriculo-antigo.doc")
        assert len(docs) == 1, docs
        doc = docs[0]
        assert not any("LibreOffice" in a for a in doc.avisos), (
            f"recusou um .doc com LibreOffice instalado: {doc.avisos}"
        )
        assert "Active Directory" in doc.texto, doc.texto[:200]
        assert "SLA de 4 horas" in doc.texto, doc.texto[:200]
        return f"convertido por {binario.rsplit(chr(92), 1)[-1]}"

    placar.rodar("Currículo .doc antigo é convertido e lido", rtf_vira_texto)
