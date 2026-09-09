"""Prepara a amostra da validação de julgamento e imprime os lotes do conector.

A amostra cobre as três fatias do gabarito, os cinco subtipos de dúvida e a
injeção de prompt. O banco fica num diretório fixo para o segundo script (o que
registra as avaliações) continuar de onde este parou.
"""
import json
import os
import sys
from pathlib import Path

# Caminho curto de proposito: o nome do arquivo guardado e o sha256 (64
# caracteres), e um diretorio profundo estoura o MAX_PATH do Windows.
PASTA_DB = Path(r"C:/tmp-amostra")
PASTA_DB.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, ".")
os.environ["TRIAGEM_DATA_DIR"] = str(PASTA_DB)
os.environ["TRIAGEM_SECRET_KEY"] = "segredo-da-amostra-0123456789abcd"
os.environ["LOG_NIVEL"] = "ERROR"
os.environ["BACKUP_ATIVO"] = "false"

from app import extraction, mcp_servidor, storage                # noqa: E402

PASTA = Path("dataset-piloto")
gab = json.loads((PASTA / "gabarito.json").read_text(encoding="utf-8"))

# ---- escolhe a amostra: representativa, e determinística
qualificados, eliminados, duvidas, injecoes = [], [], [], []
por_subtipo = {}
for cand in gab["candidatos"]:
    if cand["formato"] == "pdf_escaneado":
        continue                                   # sem Tesseract, não carrega
    if cand.get("injecao_de_prompt"):
        injecoes.append(cand)
        continue
    if cand["classe"] == "qualificado" and len(qualificados) < 8:
        qualificados.append(cand)
    elif cand["classe"] == "eliminado" and len(eliminados) < 6:
        eliminados.append(cand)
    elif cand["classe"] == "duvida":
        sub = cand.get("subtipo", "?")
        if len(por_subtipo.get(sub, [])) < 2:
            por_subtipo.setdefault(sub, []).append(cand)
            duvidas.append(cand)

amostra = qualificados + eliminados + duvidas + injecoes
arquivos_amostra = {c["arquivo"] for c in amostra if "linha_planilha" not in c}
linhas_amostra = {c["linha_planilha"] for c in amostra if "linha_planilha" in c}

print(f"AMOSTRA: {len(amostra)} currículos")
print(f"  qualificados: {len(qualificados)}")
print(f"  eliminados:   {len(eliminados)}")
print(f"  dúvida:       {len(duvidas)} — subtipos: "
      f"{ {k: len(v) for k, v in por_subtipo.items()} }")
print(f"  com injeção:  {len(injecoes)} — {[c['arquivo'] for c in injecoes]}")
escaneados_com_injecao = [c for c in gab["candidatos"]
                          if c.get("injecao_de_prompt") and c["formato"] == "pdf_escaneado"]
if escaneados_com_injecao:
    print(f"  (fora: {len(escaneados_com_injecao)} injeção em PDF escaneado, "
          f"que precisa de Tesseract)")

# ---- monta a vaga
storage.iniciar()
org = storage.criar_organizacao("Agência Piloto — amostra")
usr = storage.criar_usuario(org, "recrutador@amostra.com", "Recrutador", "h", "admin")
vaga = storage.criar_vaga(
    org, "Analista de Suporte Técnico Pleno",
    "Atendimento N2 com SLA de 4h, Active Directory, Windows Server, M365, VPN.", usr)

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
storage.salvar_rubrica(org, vaga, rubrica, aprovada=True)

# ---- carrega só os arquivos da amostra
mapa = {}
for arq in sorted(PASTA.iterdir()):
    if arq.name == "gabarito.json":
        continue
    if arq.name not in arquivos_amostra and arq.name != "inscritos-ats.xlsx":
        continue
    dados = arq.read_bytes()
    for doc in extraction.extrair(dados, arq.name):
        if doc.origem == "planilha":
            numero = int(doc.arquivo.split(" · linha ")[1].split(" ")[0])
            if numero not in linhas_amostra:
                continue
            chave = f"{arq.name}#{numero}"
        else:
            chave = arq.name
        if not doc.texto.strip():
            continue
        storage.salvar_curriculo(org, doc)
        storage.vincular(vaga, doc.candidato_id)
        (storage.pasta_org(org) / f"{doc.origem_hash}{doc.extensao}").write_bytes(dados)
        mapa[doc.candidato_id] = chave

(PASTA_DB / "contexto.json").write_text(json.dumps(
    {"org": org, "usuario": usr, "vaga": vaga, "mapa": mapa},
    ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\ncarregados: {len(mapa)} currículos na vaga {vaga}\n")

# ---- e imprime os lotes exatamente como o conector entrega
mcp_servidor.definir_contexto_local(
    {"org_id": org, "usuario_id": usr, "email": "recrutador@amostra.com", "ip": "local"})

lote = 0
while True:
    saida = mcp_servidor.proximos_curriculos(vaga_id=vaga, quantidade=5)
    if "<curriculo>" not in saida:
        print(saida.splitlines()[0])
        break
    lote += 1
    print("=" * 78)
    print(f"LOTE {lote}")
    print("=" * 78)
    print(saida if lote == 1 else saida.split("=" * 60, 1)[1])
    # marca provisoriamente para o próximo lote andar; as notas de verdade
    # vêm no segundo script
    for linha in saida.splitlines():
        if "candidato_id:" in linha:
            cid = linha.split("candidato_id: ")[1].strip()
            storage.salvar_avaliacao(vaga, cid, estagio="provisorio")

print(f"\nTOTAL: {lote} chamadas de proximos_curriculos")
storage.limpar_avaliacoes(vaga)
print("marcações provisórias limpas — a vaga está pronta para as avaliações reais")
