"""OCR do PDF escaneado, e o que ele faz com a anonimização.

O grupo tem duas metades, de propósito:

- A **anonimização sobre ruído de OCR** roda sempre, porque o ruído é simulado
  de forma determinística. É a metade que protege o princípio: texto sujo não
  pode fazer o nome do candidato vazar para quem pontua.
- A **leitura de verdade** só roda onde há Tesseract instalado. Sem o binário o
  grupo é pulado, do mesmo jeito que a extração é pulada sem o reportlab.
"""
from __future__ import annotations

from .comum import Placar, pdf_sem_texto

# Trocas que o Tesseract comete em papel digitalizado. Servem para simular o
# ruído sem depender do binário, e são as mesmas que os padrões toleram.
RUIDO = str.maketrans({"1": "l", "0": "O", "5": "S", "8": "B", "2": "Z"})


def _sujar(texto: str) -> str:
    return texto.translate(RUIDO)


CURRICULO = """Mariana Vasques Andrade
mariana.vasques@exemplo.com
(81) 98812-4477
CPF: 123.456.789-00
Recife, PE - CEP 52020-030
Nascimento: 14/03/1990

Analista de suporte tecnico N2 desde 2019.
Atendimento de chamados criticos com SLA de 4 horas; media de 55 por semana.
Administracao de Active Directory: criacao de conta, GPO e permissao de pasta.
Suporte a Windows Server 2019, Microsoft 365 e VPN.
Tecnologo em Redes de Computadores, concluido em 2018.
"""

PESSOAIS = ["Mariana", "Vasques", "mariana.vasques@exemplo.com",
            "98812-4477", "123.456.789-00", "52020-030"]


def rodar(placar: Placar) -> None:
    from app import ocr
    from app.anonimizacao import separar
    from app.config import MCP_MAX_CHARS_CURRICULO

    print("\nOCR")

    # ---- o texto sujo não pode deixar dado pessoal passar ----
    def anonimiza_ruido():
        sujo = _sujar(CURRICULO)
        sep = separar(sujo, de_ocr=True)

        assert sep.nome, "o nome não foi reconhecido no texto sujo de OCR"
        vazados = [p for p in PESSOAIS if _sujar(p) in sep.texto_anonimo]
        assert not vazados, f"vazou dado pessoal do texto de OCR: {vazados}"

        # o conteúdo profissional tem de sobreviver, senão não há o que avaliar
        assert "Active Directory" in sep.texto_anonimo
        assert "SLA de 4 horas" in sep.texto_anonimo
        return "nome, e-mail, telefone, CPF, CEP e nascimento saem mesmo sujos"

    placar.rodar("Ruído de OCR não faz dado pessoal escapar", anonimiza_ruido)

    # ---- sem OCR, os padrões tolerantes ficam desligados ----
    def sem_falso_positivo():
        limpo = separar(CURRICULO, de_ocr=False)
        assert not limpo.retido, "currículo com texto limpo não deve ser retido"
        # Texto profissional cheio de número não pode virar [cpf]/[telefone].
        tecnico = separar(
            "Joao Pedro Martins\nWindows Server 2019 e Office 365.\n"
            "Reduziu o tempo medio de 9h para 2h40 em 2021.\n"
            "Atendeu 1200 chamados com SLA de 4 horas.",
            de_ocr=False,
        )
        for marca in ("[cpf]", "[telefone]", "[cep]"):
            assert marca not in tecnico.texto_anonimo, (
                f"{marca} apareceu em texto técnico legítimo: {tecnico.texto_anonimo}"
            )
        return "número de versão e volume não viram dado pessoal"

    placar.rodar("Padrão tolerante não dispara em texto limpo", sem_falso_positivo)

    # ---- sem nome confiável, o currículo é retido ----
    def retencao():
        anonimo = _sujar(
            "||| documento digitalizado 4rqu1v0 |||\n"
            "CPF: 123.456.789-00\n"
            "Analista de suporte tecnico N2 com SLA de 4 horas.\n"
        )
        sep = separar(anonimo, de_ocr=True)
        assert not sep.nome, "achou nome onde não havia"
        assert sep.retido, (
            "sem nome identificado, o currículo de OCR tinha de ser retido — "
            "entregá-lo poderia mandar o nome junto"
        )
        assert sep.motivo_retencao, "reteve sem dizer o motivo ao recrutador"

        # O mesmo texto, com texto embutido, segue — ali o risco é outro.
        limpo = separar(anonimo, de_ocr=False)
        assert not limpo.retido, "retenção não deve valer para texto não-OCR"
        return "retém no OCR, segue no texto direto"

    placar.rodar("Currículo de OCR sem nome confiável não é entregue", retencao)

    # ---- o conector não recebe currículo retido ----
    def conector_nao_recebe_retido():
        from app import extraction, storage
        from app.mcp_servidor import definir_contexto_local, proximos_curriculos
        from app.models import Criterio, Rubrica

        org_id = storage.criar_organizacao("Empresa do OCR")
        usuario_id = storage.criar_usuario(org_id, "ocr@teste.com", "Chefe", "h", "admin")
        vaga_id = storage.criar_vaga(org_id, "Suporte", "descricao " * 12, usuario_id)
        rubrica = Rubrica(cargo="Suporte", senioridade="pleno",
                          criterios=[Criterio(id="suporte", nome="Suporte",
                                              descricao="mesa de ajuda", peso=100)])
        storage.salvar_rubrica(org_id, vaga_id, rubrica.model_dump(), aprovada=True)

        ilegivel = _sujar("||| digitalizado |||\nCPF: 123.456.789-00\n"
                          "Analista de suporte N2 com SLA de 4 horas.\n")
        doc = extraction.Documento(
            candidato_id="ocrretido00001", arquivo="escaneado.pdf", texto=ilegivel,
            escaneado=True, origem_texto="ocr", ocr_confianca="baixa")
        storage.salvar_curriculo(org_id, doc)
        storage.vincular(vaga_id, doc.candidato_id)

        definir_contexto_local({"org_id": org_id, "usuario_id": usuario_id,
                                "email": "ocr@teste.com", "ip": "local"})
        saida = proximos_curriculos(vaga_id=vaga_id, quantidade=5)
        assert "<curriculo>" not in saida, "o currículo retido foi entregue ao conector"
        assert "anonimizada com segurança" in saida or "anonimizado com segurança" in saida, saida

        resumo = storage.resumo_da_vaga(org_id, vaga_id)
        assert resumo["erros"] == 1, f"o retido tinha de contar como erro: {resumo}"
        assert resumo["pendentes"] == 0, (
            f"o retido não pode ficar pendente para sempre: {resumo}"
        )
        return "retido não atravessa, e a vaga não fica presa por causa dele"

    placar.rodar("Conector não recebe currículo retido, e o status fecha",
                 conector_nao_recebe_retido)

    # ---- o rótulo do arquivo não pode entregar a pessoa ----
    def rotulo_nao_vaza():
        """Descoberto carregando o dataset piloto: o texto ia limpo, mas o nome
        do arquivo ia junto. Currículo chega como "Ana Paula Souza - CV.pdf", e
        linha de planilha de ATS ganha rótulo com o nome dentro para o recrutador
        se achar na tela. Os dois entregavam a identidade a quem pontua."""
        from app import extraction, storage
        from app.mcp_servidor import definir_contexto_local, proximos_curriculos
        from app.models import Criterio, Rubrica

        org_id = storage.criar_organizacao("Empresa do rótulo")
        usuario_id = storage.criar_usuario(org_id, "rotulo@teste.com", "Chefe", "h", "admin")
        vaga_id = storage.criar_vaga(org_id, "Suporte", "descricao " * 12, usuario_id)
        storage.salvar_rubrica(
            org_id, vaga_id,
            Rubrica(cargo="Suporte", senioridade="pleno",
                    criterios=[Criterio(id="suporte", nome="Suporte",
                                        descricao="mesa de ajuda", peso=100)]).model_dump(),
            aprovada=True)

        # 1. o nome no próprio nome do arquivo
        arquivo = extraction.Documento(
            candidato_id="rotuloarquivo01",
            arquivo="Ana Paula Souza - Curriculo 2026.pdf",
            texto="Ana Paula Souza\nana.souza@exemplo.com\n"
                  "Analista de suporte N2 com SLA de 4 horas.")
        # 2. o nome no rótulo da linha de planilha de ATS
        planilha = extraction.Documento(
            candidato_id="rotuloplanilha1", origem="planilha",
            arquivo="inscritos-ats.xlsx · linha 7 · Bruno Tavares Quintela",
            texto="Nome: Bruno Tavares Quintela\nExperiência: suporte N2 com SLA.")

        for doc in (arquivo, planilha):
            storage.salvar_curriculo(org_id, doc)
            storage.vincular(vaga_id, doc.candidato_id)

        definir_contexto_local({"org_id": org_id, "usuario_id": usuario_id,
                                "email": "rotulo@teste.com", "ip": "local"})
        saida = proximos_curriculos(vaga_id=vaga_id, quantidade=5)

        for vazamento in ("Ana Paula Souza", "Ana Paula", "ana.souza@exemplo.com",
                          "Bruno Tavares Quintela", "Bruno Tavares",
                          "Curriculo 2026.pdf", "inscritos-ats.xlsx"):
            assert vazamento not in saida, (
                f"{vazamento!r} atravessou para quem pontua, pelo rótulo do arquivo"
            )
        # e o conteúdo profissional continua chegando
        assert "SLA" in saida, "o currículo não chegou ao avaliador"
        return "nem nome de arquivo, nem rótulo de planilha atravessam"

    placar.rodar("Rótulo do arquivo não entrega a identidade ao avaliador",
                 rotulo_nao_vaza)

    # ---- teto de texto por currículo entregue ----
    def teto_de_contexto():
        from app import extraction, storage
        from app.mcp_servidor import definir_contexto_local, proximos_curriculos
        from app.models import Criterio, Rubrica

        org_id = storage.criar_organizacao("Empresa do teto")
        usuario_id = storage.criar_usuario(org_id, "teto@teste.com", "Chefe", "h", "admin")
        vaga_id = storage.criar_vaga(org_id, "Suporte", "descricao " * 12, usuario_id)
        rubrica = Rubrica(cargo="Suporte", senioridade="pleno",
                          criterios=[Criterio(id="suporte", nome="Suporte",
                                              descricao="mesa de ajuda", peso=100)])
        storage.salvar_rubrica(org_id, vaga_id, rubrica.model_dump(), aprovada=True)

        longo = ("Carlos Eduardo Nogueira\n"
                 + "Atendimento de chamados com SLA de 4 horas. " * 900)
        doc = extraction.Documento(candidato_id="curriculolongo1",
                                   arquivo="longo.pdf", texto=longo)
        storage.salvar_curriculo(org_id, doc)
        storage.vincular(vaga_id, doc.candidato_id)

        definir_contexto_local({"org_id": org_id, "usuario_id": usuario_id,
                                "email": "teto@teste.com", "ip": "local"})
        saida = proximos_curriculos(vaga_id=vaga_id, quantidade=5)
        corpo = saida.split("<curriculo>")[1].split("</curriculo>")[0]
        assert len(corpo) <= MCP_MAX_CHARS_CURRICULO + 10, (
            f"o currículo saiu com {len(corpo)} caracteres, acima do teto "
            f"de {MCP_MAX_CHARS_CURRICULO}"
        )
        assert "currículo longo" in saida, "cortou o texto sem avisar o avaliador"

        # o banco continua com o currículo inteiro
        guardado = storage.buscar_curriculo(org_id, doc.candidato_id)
        assert len(guardado["texto"]) > MCP_MAX_CHARS_CURRICULO, (
            "o corte para o conector não pode encurtar o que está guardado"
        )
        return f"entregue com {len(corpo)} de {len(guardado['texto'])} caracteres"

    placar.rodar("Currículo longo é cortado para o conector, não no banco",
                 teto_de_contexto)

    # ---- a fila: o upload não pode ficar esperando o OCR ----
    def upload_nao_espera_ocr():
        """R4 do plano: o OCR leva de 2 a 6 segundos por página, e o recrutador
        arrasta a pasta inteira. Feito dentro da requisição, o upload ficaria
        minutos no ar e o proxy derrubaria a conexão."""
        from app import extraction, fila_ocr, storage
        from app.models import Criterio, Rubrica

        org_id = storage.criar_organizacao("Empresa da fila")
        usuario_id = storage.criar_usuario(org_id, "fila@teste.com", "Chefe", "h", "admin")
        vaga_id = storage.criar_vaga(org_id, "Suporte", "descricao " * 12, usuario_id)
        storage.salvar_rubrica(
            org_id, vaga_id,
            Rubrica(cargo="S", senioridade="pleno",
                    criterios=[Criterio(id="s", nome="S", descricao="d",
                                        peso=100)]).model_dump(),
            aprovada=True)

        doc = extraction.extrair(pdf_sem_texto(), "digitalizado.pdf")[0]
        assert doc.estado_extracao == "pendente", (
            "o PDF escaneado tem de sair do upload pendente, não lido"
        )
        assert not doc.texto.strip(), "o upload não pode ter feito OCR"

        storage.salvar_curriculo(org_id, doc)
        storage.vincular(vaga_id, doc.candidato_id)

        # Enquanto está na fila, é espera — não falha.
        resumo = storage.resumo_da_vaga(org_id, vaga_id)
        assert resumo["lendo"] == 1, f"não contou como leitura em andamento: {resumo}"
        assert resumo["erros"] == 0, (
            f"currículo na fila foi contado como falha: {resumo}"
        )
        assert resumo["pendentes"] == 1, resumo
        assert not storage.ranking(org_id, vaga_id), (
            "currículo ainda na fila apareceu no ranking como falha"
        )

        # E o que ficou pendente é recolhido no boot seguinte.
        pendentes = storage.curriculos_pendentes_de_ocr()
        assert any(p["candidato_id"] == doc.candidato_id for p in pendentes), (
            "o pendente não seria recolhido depois de uma queda do servidor"
        )

        # Sem Tesseract, a fila marca falha com motivo — e aí vira erro de verdade.
        estado = fila_ocr.processar(org_id, doc.candidato_id)
        depois = storage.resumo_da_vaga(org_id, vaga_id)
        if estado["estado"] == "falhou":
            assert depois["lendo"] == 0 and depois["erros"] == 1, depois
            linhas = storage.ranking(org_id, vaga_id)
            assert linhas and linhas[0]["estagio"] == "erro", (
                "depois de falhar, o currículo tem de aparecer com o motivo"
            )
            assert linhas[0]["erro"], "falhou sem dizer o motivo ao recrutador"
        return f"upload devolve na hora; a fila resolve depois ({estado['estado']})"

    placar.rodar("Upload não espera o OCR, e o pendente não vira falha",
                 upload_nao_espera_ocr)

    # ---- daqui para baixo, só com o Tesseract instalado ----
    disponivel, motivo = ocr.disponivel()
    if not disponivel:
        print(f"  [pulado] leitura real por OCR — {motivo}")
        return

    def le_pdf_escaneado():
        from app import extraction

        linhas = ["Mariana Vasques Andrade",
                  "Analista de suporte tecnico N2 desde 2019",
                  "Atendimento com SLA de 4 horas",
                  "Active Directory, Windows Server e VPN"]
        dados = _pdf_escaneado(linhas)
        resultado = ocr.ler_pdf(dados)

        esperado = " ".join(linhas)
        acerto = _semelhanca(esperado, resultado.texto)
        assert acerto >= 0.85, (
            f"OCR acertou só {acerto:.0%} dos caracteres; esperado 85% ou mais.\n"
            f"lido: {resultado.texto[:200]!r}"
        )

        # E o caminho de verdade: upload marca como pendente, a fila lê depois.
        from app import fila_ocr, storage

        org_id = storage.criar_organizacao("Empresa do OCR real")
        doc = extraction.extrair(dados, "digitalizado.pdf")[0]
        assert doc.escaneado and doc.estado_extracao == "pendente", (
            "o upload não deve fazer OCR; ele marca e a fila lê"
        )
        assert not doc.texto.strip(), "o texto não pode vir do upload"

        storage.salvar_curriculo(org_id, doc)
        (storage.pasta_org(org_id) / f"{doc.origem_hash}{doc.extensao}").write_bytes(dados)

        estado = fila_ocr.processar(org_id, doc.candidato_id)
        assert estado["estado"] == "pronto", estado

        guardado = storage.buscar_curriculo(org_id, doc.candidato_id)
        assert guardado["origem_texto"] == "ocr", guardado["origem_texto"]
        assert guardado["ocr_confianca"] in ("alta", "baixa"), guardado["ocr_confianca"]
        assert guardado["estado_extracao"] == "pronto", guardado["estado_extracao"]
        assert "Directory" in (guardado["texto"] or ""), (guardado["texto"] or "")[:200]
        assert guardado["parse"], "a fila tinha de anonimizar junto com a leitura"
        return f"{acerto:.0%} de acerto, confiança {guardado['ocr_confianca']}"

    placar.rodar("PDF escaneado é lido por OCR com 85% de acerto ou mais",
                 le_pdf_escaneado)

    def dado_pessoal_de_ocr_real():
        from app import extraction, fila_ocr, storage

        dados = _pdf_escaneado([l for l in CURRICULO.splitlines() if l.strip()])
        org_id = storage.criar_organizacao("Empresa do OCR pessoal")
        doc = extraction.extrair(dados, "escaneado.pdf")[0]
        storage.salvar_curriculo(org_id, doc)
        (storage.pasta_org(org_id) / f"{doc.origem_hash}{doc.extensao}").write_bytes(dados)
        fila_ocr.processar(org_id, doc.candidato_id)

        guardado = storage.buscar_curriculo(org_id, doc.candidato_id)
        assert guardado["origem_texto"] == "ocr", "o documento não passou por OCR"

        sep = separar(guardado["texto"], de_ocr=True)
        if sep.retido:
            return "não deu para garantir a anonimização; currículo retido, como manda"
        vazados = [p for p in PESSOAIS if p in sep.texto_anonimo]
        assert not vazados, f"vazou dado pessoal de OCR real: {vazados}"
        return "nada de pessoal sobrou no texto lido do papel"

    placar.rodar("Dado pessoal não sobrevive ao OCR real", dado_pessoal_de_ocr_real)


# ---------- apoio ----------

def _pdf_escaneado(linhas: list[str]) -> bytes:
    """Imita papel digitalizado: o texto vira imagem e a imagem vira PDF.

    É o que o recrutador recebe quando alguém imprime o currículo, assina e passa
    no scanner — não há texto embutido, só pixels.
    """
    import io

    from PIL import Image, ImageDraw
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    largura, altura = 1240, 1754                               # A4 a 150 DPI
    imagem = Image.new("RGB", (largura, altura), "white")
    desenho = ImageDraw.Draw(imagem)
    for i, linha in enumerate(linhas):
        # sem fonte declarada o Pillow usa a embutida, que é pequena; o texto é
        # desenhado grande o bastante para o Tesseract ter chance.
        desenho.text((80, 120 + i * 60), linha, fill="black")

    buffer_imagem = io.BytesIO()
    imagem.save(buffer_imagem, format="PNG")
    buffer_imagem.seek(0)

    buffer_pdf = io.BytesIO()
    c = canvas.Canvas(buffer_pdf, pagesize=A4)
    c.drawImage(ImageReader(buffer_imagem), 0, 0, width=A4[0], height=A4[1])
    c.save()
    return buffer_pdf.getvalue()


def _semelhanca(esperado: str, obtido: str) -> float:
    """Quanto do texto original o OCR recuperou, de 0 a 1."""
    from difflib import SequenceMatcher

    def normalizar(t: str) -> str:
        return " ".join(t.split()).lower()

    return SequenceMatcher(None, normalizar(esperado), normalizar(obtido)).ratio()
