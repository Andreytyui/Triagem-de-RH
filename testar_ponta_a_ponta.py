"""Ponta a ponta da vaga piloto.

    python gerar_dataset_piloto.py     # gera os 150 currículos e o gabarito
    python testar_ponta_a_ponta.py     # roda o funil inteiro contra eles

O que este teste prova e o que ele NÃO prova, dito antes para não haver
confusão na leitura do resultado:

**Prova** tudo que é responsabilidade do servidor: extração dos formatos,
anonimização antes da fronteira, entrega pelo conector, cálculo da nota em
Python, ordenação do pódio, o documento de entrega e o tempo de máquina.

**Prova também uma coisa que só aparece em escala:** se o texto anonimizado
ainda carrega sinal profissional suficiente para diferenciar candidato. O
avaliador deste script lê **apenas o texto anonimizado**, sem nunca olhar o
gabarito. Se o pódio dele bater com o gabarito, é porque a anonimização tirou a
identidade sem levar junto a evidência — que é exatamente a aposta do produto.

**Não prova** a qualidade de julgamento do Claude de verdade. O avaliador aqui é
determinístico, por palavra-chave; ele ocupa o lugar do Claude no fluxo, não a
inteligência dele. Julgamento real depende de uma sessão de conector de verdade,
que é a parte do item 6 que fica com o recrutador.
"""
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, ".")
os.environ["TRIAGEM_DATA_DIR"] = tempfile.mkdtemp(prefix="e2e-piloto-")
os.environ["TRIAGEM_SECRET_KEY"] = "segredo-do-e2e-0123456789abcdef"
os.environ["LOG_NIVEL"] = "ERROR"
os.environ["BACKUP_ATIVO"] = "false"
os.environ["MAX_ARQUIVOS_POR_LOTE"] = "200"

from fastapi.testclient import TestClient                      # noqa: E402

from app import mcp_servidor, storage                          # noqa: E402
from app.main import app                                       # noqa: E402
from app.models import NotaCriterio                            # noqa: E402

PASTA = Path("dataset-piloto")
RELOGIO = time.perf_counter


# ---------------------------------------------------------------------------
# O avaliador que ocupa o lugar do Claude
# ---------------------------------------------------------------------------

SINAIS = {
    "suporte_n2": [
        (r"n[ií]vel 2|N2", 3), (r"SLA de \d+ horas?", 4),
        (r"m[eé]dia de \d+ chamados", 3), (r"\d+ chamados por semana", 3),
        (r"service desk|mesa de ajuda|help ?desk", 2),
    ],
    "active_directory": [
        (r"Active Directory", 5), (r"GPO", 3),
        (r"permiss[aã]o de pasta", 2), (r"cria[cç][aã]o (?:e bloqueio )?de contas?", 2),
    ],
    "redes": [
        (r"Windows Server ?\d*", 4), (r"Microsoft 365|Office 365", 2),
        (r"\bVPN\b", 2), (r"infraestrutura", 1),
    ],
    "ingles": [
        (r"[Ii]ngl[eê]s", 4), (r"documenta[cç][aã]o em ingl[eê]s", 3),
    ],
}

ELIMINATORIOS = {
    "superior_ti": [
        r"Tecn[oó]logo em (?:Redes|An[aá]lise|Gest[aã]o da Tecnologia)",
        r"Bacharelado em (?:Sistemas de Informa[cç][aã]o|Ci[eê]ncia da Computa[cç][aã]o)",
    ],
    "ad_windows": [r"Active Directory"],
}

INJECAO = re.compile(
    r"ignore (?:os|as) (?:crit[eé]rios|regras|instru[cç][oõ]es)|"
    r"atribua nota 10|INSTRU[CÇ][AÃ]O PARA O AVALIADOR|"
    r"classificado como CHAMAR|j[aá] foi aprovado pela diretoria",
    re.I,
)


def _trecho(texto: str, padrao: str) -> str:
    """A evidência precisa ser um trecho do próprio currículo, não um resumo."""
    achado = re.search(padrao, texto, re.I)
    if not achado:
        return ""
    linha = texto[:achado.start()].rfind("\n") + 1
    fim = texto.find("\n", achado.end())
    return texto[linha:fim if fim > 0 else len(texto)].strip(" -\t")[:200]


def avaliar(texto: str) -> dict:
    """Lê só o texto anonimizado. Nunca vê o gabarito."""
    notas, evidencias = {}, {}
    for criterio, sinais in SINAIS.items():
        pontos, melhor = 0, ""
        for padrao, peso in sinais:
            if re.search(padrao, texto, re.I):
                pontos += peso
                if not melhor:
                    melhor = _trecho(texto, padrao)
        notas[criterio] = min(10, pontos)
        evidencias[criterio] = melhor or "sem evidência no currículo"

    faltam = [
        eid for eid, padroes in ELIMINATORIOS.items()
        if not any(re.search(p, texto, re.I) for p in padroes)
    ]
    # Formação em andamento não é formação completa: o obrigatório pede completa.
    if re.search(r"Cursando", texto, re.I) and "superior_ti" not in faltam:
        faltam.append("superior_ti")

    return {
        "notas": notas,
        "evidencias": evidencias,
        "eliminatorios_falhos": faltam,
        "injecao": bool(INJECAO.search(texto)),
        # Currículo curto e genérico não dá base para avaliação segura.
        "confianca": "baixa" if len(texto) < 400 else "alta",
    }


# ---------------------------------------------------------------------------
def main() -> int:
    inicio_total = RELOGIO()
    gab = json.loads((PASTA / "gabarito.json").read_text(encoding="utf-8"))
    # As 14 linhas do export de ATS compartilham o nome do arquivo, então a
    # chave precisa do número da linha para não colapsar a fatia inteira em uma.
    esperado = {}
    for cand in gab["candidatos"]:
        chave = (cand["arquivo"] if "linha_planilha" not in cand
                 else f"{cand['arquivo']}#{cand['linha_planilha']}")
        esperado[chave] = cand

    storage.iniciar()
    # ATENÇÃO ao `__enter__`: o trabalhador que faz o OCR é iniciado no lifespan
    # do app (main.py:77, asyncio.create_task), e o TestClient só roda o
    # lifespan quando é usado como gerenciador de contexto. Com `TestClient(app)`
    # solto, os PDFs digitalizados entravam na fila e ficavam lá para sempre —
    # os 15 "pendentes" que este teste reportou por muito tempo não eram falta
    # do Tesseract, eram o trabalhador que nunca subiu.
    c = TestClient(app)
    c.__enter__()

    print("=" * 70)
    print("PONTA A PONTA — Analista de Suporte Técnico Pleno")
    print("=" * 70)

    # ---- 1. conta e vaga
    c.post("/api/auth/registrar", json={
        "organizacao": "Agência Piloto", "nome": "Recrutador",
        "email": "recrutador@piloto.com", "senha": "cafe com pao na chuva"})
    H = {"X-CSRF-Token": c.cookies.get("triagem_csrf")}

    vaga = c.post("/api/vagas", headers=H, json={
        "titulo": "Analista de Suporte Técnico Pleno",
        "descricao": ("Atendimento de chamados N2 com SLA de 4 horas para prioridade "
                      "alta, 40 a 60 por semana. Administrar Active Directory: conta, "
                      "GPO, permissão de pasta. Suporte a Windows Server, Microsoft "
                      "365 e VPN. Documentar procedimento e escalar para infra."),
    }).json()["vaga_id"]

    # ---- 2. rubrica: escrita e aprovada por humano, antes de qualquer avaliação
    rubrica = {
        "cargo": "Analista de Suporte Técnico", "senioridade": "pleno",
        "eliminatorios": [
            {"id": "superior_ti", "descricao": "Superior completo em área de tecnologia"},
            {"id": "ad_windows",
             "descricao": "Experiência comprovada com Active Directory e Windows Server"},
        ],
        "criterios": [
            {"id": "suporte_n2", "nome": "Experiência em suporte N2",
             "descricao": "mesa de ajuda com prazo acordado", "peso": 35},
            {"id": "active_directory", "nome": "Active Directory",
             "descricao": "contas, GPO, permissões", "peso": 30},
            {"id": "redes", "nome": "Redes e infraestrutura",
             "descricao": "Windows Server, VPN, Microsoft 365", "peso": 20},
            {"id": "ingles", "nome": "Inglês técnico",
             "descricao": "leitura de documentação", "peso": 15},
        ],
    }
    r = c.put(f"/api/vagas/{vaga}/rubrica", headers=H, json=rubrica)
    assert r.status_code == 200, r.text
    print(f"\n[1] Rubrica aprovada por humano antes de avaliar: "
          f"{len(rubrica['criterios'])} critérios, {len(rubrica['eliminatorios'])} eliminatórios")

    # ---- 3. upload de tudo
    t0 = RELOGIO()
    arquivos, enviados = [], 0
    for arq in sorted(PASTA.iterdir()):
        if arq.name == "gabarito.json":
            continue
        arquivos.append(("arquivos", (arq.name, arq.read_bytes(), "application/octet-stream")))
        enviados += 1
    resp = c.post(f"/api/vagas/{vaga}/curriculos", headers=H, files=arquivos).json()
    t_upload = RELOGIO() - t0

    # O upload devolve na hora e o OCR corre atrás, em fila. Aqui esperamos a
    # fila secar: sem isso o digitalizado nunca chega ao conector, e 10% do
    # dataset — a fatia que só o OCR lê — ficaria fora do teste em silêncio.
    limite_ocr = RELOGIO() + 300
    while RELOGIO() < limite_ocr:
        st = c.get(f"/api/vagas/{vaga}/status").json()
        if not st.get("lendo") and not st.get("pendentes"):
            break
        time.sleep(2)
    t_ocr = RELOGIO() - t0 - t_upload

    print(f"\n[2] Upload de {enviados} arquivos em {t_upload:.1f}s")
    print(f"    fila de OCR drenada em {t_ocr:.1f}s")
    print(f"    aceitos: {resp['novos']} · rejeitados: {len(resp['rejeitados'])}")
    motivos = {}
    for rej in resp["rejeitados"]:
        chave = ("LibreOffice ausente" if "LibreOffice" in rej["motivo"]
                 else "Tesseract ausente" if "Tesseract" in rej["motivo"]
                 else rej["motivo"][:60])
        motivos[chave] = motivos.get(chave, 0) + 1
    for motivo, quantos in motivos.items():
        print(f"      - {quantos}x {motivo}")

    # ---- 4. avaliação pelo conector
    usuario = storage.buscar_usuario_por_email("recrutador@piloto.com")
    mcp_servidor.definir_contexto_local({
        "org_id": usuario["org_id"], "usuario_id": usuario["id"],
        "email": usuario["email"], "ip": "local"})

    pessoais = set()
    for cand in gab["candidatos"]:
        pessoais.update({cand["nome"], cand["email"], cand["telefone"]})

    t0 = RELOGIO()
    lotes = avaliados = eliminados = 0
    vazamentos, injecoes_vistas = [], []
    evidencias_para_auditar = []

    while True:
        lote = mcp_servidor.proximos_curriculos(vaga_id=vaga, quantidade=5)
        if "<curriculo>" not in lote:
            break
        lotes += 1

        for pessoal in pessoais:
            if len(pessoal) > 8 and pessoal in lote:
                vazamentos.append(pessoal)

        for bloco in lote.split("### candidato_id: ")[1:]:
            cid = bloco.split("\n")[0].strip()
            texto = bloco.split("<curriculo>")[1].split("</curriculo>")[0].strip()
            julgamento = avaliar(texto)

            if julgamento["injecao"]:
                injecoes_vistas.append(cid)

            if julgamento["eliminatorios_falhos"]:
                mcp_servidor.registrar_eliminacao(
                    vaga, cid,
                    "não atende requisito obrigatório: "
                    + ", ".join(julgamento["eliminatorios_falhos"]),
                    julgamento["eliminatorios_falhos"])
                eliminados += 1
                continue

            notas = [NotaCriterio(criterio_id=k, nota=v,
                                  evidencia=julgamento["evidencias"][k])
                     for k, v in julgamento["notas"].items()]
            mcp_servidor.registrar_avaliacao(
                vaga, cid, notas=notas,
                resumo="Perfil de suporte técnico avaliado contra a rubrica.",
                recomendacao="chamar" if sum(julgamento["notas"].values()) >= 24 else "talvez",
                red_flags=(["o currículo contém texto tentando instruir o avaliador"]
                           if julgamento["injecao"] else []),
                confianca=julgamento["confianca"])
            avaliados += 1
            evidencias_para_auditar.append((cid, texto, julgamento["evidencias"]))

    t_avaliacao = RELOGIO() - t0
    print(f"\n[3] Avaliação pelo conector: {lotes} lotes, "
          f"{avaliados} avaliados e {eliminados} eliminados em {t_avaliacao:.1f}s")
    print(f"    VAZAMENTO de dado pessoal: "
          f"{'NENHUM' if not vazamentos else sorted(set(vazamentos))[:5]}")
    print(f"    tentativas de injeção detectadas e registradas: {len(injecoes_vistas)}")

    # ---- 5. evidência auditada: tem de estar literalmente no currículo
    conferidas = com_evidencia = literais = 0
    for cid, texto, evidencias in evidencias_para_auditar[:10]:
        for criterio, evidencia in evidencias.items():
            conferidas += 1
            if evidencia == "sem evidência no currículo":
                continue
            com_evidencia += 1
            if evidencia in texto:
                literais += 1
            else:
                print(f"    !! evidência não encontrada no currículo {cid}: {evidencia[:60]!r}")
    print(f"\n[4] Auditoria de evidência em 10 candidatos: {conferidas} notas, "
          f"{com_evidencia} com citação, {literais} conferidas literalmente no texto")
    assert literais == com_evidencia, "há evidência citada que não está no currículo"

    # ---- 6. o pódio
    status = c.get(f"/api/vagas/{vaga}/status").json()
    ranking = c.get(f"/api/vagas/{vaga}/resultados").json()
    podio = [l for l in ranking if l["estagio"] == "avaliado"][:10]

    print(f"\n[5] Status: {status['com_veredito']} de {status['total']} com veredito "
          f"({status['avaliados']} avaliados, {status['eliminados']} eliminados, "
          f"{status['erros']} com falha, {status['pendentes']} pendentes)")
    assert (status["avaliados"] + status["eliminados"] + status["erros"]
            + status["pendentes"] == status["total"]), status

    def chave_de(linha) -> str:
        """O rótulo guardado é 'inscritos-ats.xlsx · linha 7 · Fulano' para a
        planilha, e o nome do arquivo para o resto."""
        arquivo = linha["arquivo"] or ""
        achado = re.search(r"^(.+?) · linha (\d+)", arquivo)
        return f"{achado.group(1)}#{achado.group(2)}" if achado else arquivo

    def classe_de(linha):
        cand = esperado.get(chave_de(linha))
        return cand["classe"] if cand else "?"

    print(f"\n[6] Pódio (10 primeiros, nota calculada em Python):")
    for i, l in enumerate(podio, start=1):
        classe = classe_de(l)
        print(f"    {i:2}. {l['nome'][:28]:28} {l['score_final']:5.1f}  "
              f"[gabarito: {classe}]")

    # ---- 7. o pódio contra o gabarito
    classes_podio = [classe_de(l) for l in podio]
    qualificados_no_podio = classes_podio.count("qualificado")

    eliminados_reais = [l for l in ranking if l["estagio"] == "eliminado"]
    falsos_cortes = [l for l in eliminados_reais if classe_de(l) == "qualificado"]

    print(f"\n[7] Pódio contra o gabarito:")
    print(f"    qualificados no top 10: {qualificados_no_podio}/10")
    print(f"    qualificados cortados no eliminatório (falso corte): {len(falsos_cortes)}")

    from collections import Counter

    matriz = Counter()
    for linha in ranking:
        matriz[(classe_de(linha), linha["estagio"])] += 1
    print("\n    gabarito x resultado:")
    print(f"    {'':14} {'avaliado':>9} {'eliminado':>10} {'erro':>6}")
    for classe in ("qualificado", "duvida", "eliminado"):
        print(f"    {classe:14} {matriz[(classe, 'avaliado')]:>9} "
              f"{matriz[(classe, 'eliminado')]:>10} {matriz[(classe, 'erro')]:>6}")

    notas_por_classe = {}
    for linha in ranking:
        if linha["estagio"] == "avaliado" and linha["score_final"] is not None:
            notas_por_classe.setdefault(classe_de(linha), []).append(linha["score_final"])
    print("\n    nota media de quem passou o eliminatorio:")
    for classe, notas in sorted(notas_por_classe.items()):
        print(f"    {classe:14} {sum(notas) / len(notas):5.1f}  (n={len(notas)})")

    # ---- 8. documento de entrega
    shortlist = c.get(f"/api/vagas/{vaga}/shortlist")
    assert shortlist.status_code == 200, shortlist.status_code
    texto_doc = shortlist.text
    # Com limite de palavra: sem isso, "IA " casa dentro de "experiência " e o
    # documento pareceria reprovado por um termo que não está lá.
    proibidos = ["intelig[êe]ncia artificial", r"\bIA\b", r"\brob[ôo]\b", r"\bClaude\b",
                 "modelo de linguagem", "processamento", r"\bdescartad[oa]s?\b",
                 r"\beliminad[oa]s?\b"]
    encontrados = [p for p in proibidos if re.search(p, texto_doc, re.I)]
    print(f"\n[8] Documento de entrega: {len(texto_doc)} caracteres")
    print(f"    termos proibidos encontrados: {encontrados or 'nenhum'}")

    candidatos_no_doc = texto_doc.count("class='cand-nome'")
    print(f"    candidatos dentro do documento: {candidatos_no_doc}")

    # ---- 9. diagnóstico comparativo (item 3) — no pódio e no documento
    #
    # O shortlist entrega, por padrão, quem foi marcado como "entrevistar". Num
    # piloto sem nenhuma decisão registrada, esse recorte é vazio — e aí a
    # conferência de termos proibidos acima passaria sobre um documento sem
    # candidato nenhum, o que não prova nada. Marcamos os três primeiros para o
    # documento ter conteúdo, que é o estado em que o recrutador o entrega.
    for linha in podio[:3]:
        c.put(f"/api/vagas/{vaga}/candidatos/{linha['candidato_id']}/decisao",
              headers=H, json={"decisao": "entrevistar", "anotacao": ""})
    doc = c.get(f"/api/vagas/{vaga}/shortlist").text
    no_doc = doc.count("class='cand-nome'")
    comparacoes_doc = doc.count("Diferença para o anterior da lista")

    com_vizinhanca = [l for l in podio if l.get("vizinhanca")]
    fechadas, empatadas, quebradas = 0, 0, []
    for linha in com_vizinhanca:
        for lado in linha["vizinhanca"]["lados"]:
            if lado["identicos"]:
                empatadas += 1
                continue
            soma = 0.0
            for criterio in lado["criterios"]:
                soma += float(criterio["delta"].replace("−", "-").replace("+", ""))
            if abs(round(soma, 1)) != abs(float(lado["gap"])):
                quebradas.append(
                    f"{linha['candidato_id']} vs nº{lado['posicao']}: "
                    f"deltas somam {soma:.1f}, distância é {lado['gap']}")
            else:
                fechadas += 1

    print("\n[9] Diagnóstico comparativo (item 3):")
    print(f"    candidatos do pódio com vizinhança: {len(com_vizinhanca)}/{len(podio)}")
    print(f"    comparações: {fechadas} com a conta fechada, "
          f"{empatadas} empate técnico"
          + (f" · QUEBRADAS: {quebradas}" if quebradas else ""))
    if fechadas == 0 and empatadas:
        print("    (o avaliador determinístico do piloto empata o topo inteiro,"
              " então a aritmética não é exercitada aqui — quem cobre isso são"
              " as 400 rubricas aleatórias do tests/test_comparacao.py)")
    print(f"    documento com decisões: {no_doc} candidatos, "
          f"{comparacoes_doc} linha(s) de comparação")
    proibidos_doc = [p for p in proibidos if re.search(p, doc, re.I)]
    print(f"    termos proibidos no documento preenchido: {proibidos_doc or 'nenhum'}")

    falhas_item3 = []
    if not com_vizinhanca:
        falhas_item3.append("nenhum candidato do pódio recebeu vizinhança")
    if quebradas:
        falhas_item3.append(f"{len(quebradas)} comparações não fecham a conta")
    if no_doc < 3:
        falhas_item3.append(f"documento saiu com {no_doc} candidatos, esperava 3")
    if no_doc >= 2 and comparacoes_doc == 0:
        falhas_item3.append("documento com 2+ candidatos e nenhuma comparação")
    if proibidos_doc:
        falhas_item3.append(f"termo proibido no documento: {proibidos_doc}")

    total = RELOGIO() - inicio_total
    print(f"\n[9] Tempo total de máquina: {total:.1f}s "
          f"(upload {t_upload:.1f}s + avaliação {t_avaliacao:.1f}s)")
    print("=" * 70)
    c.__exit__(None, None, None)
    problemas = list(vazamentos) + list(encontrados) + falhas_item3
    if problemas:
        print("\nFALHOU:")
        for p in problemas:
            print(f"  · {p}")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
