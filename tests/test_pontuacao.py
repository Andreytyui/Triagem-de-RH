"""O cálculo da nota, o cache de parse, o painel de status e a migração v3 para v4.

O que este módulo protege é o princípio 2: a nota é calculada em Python, e dá
para recalculá-la à mão com a rubrica na frente. Nada aqui depende de modelo.
"""
from __future__ import annotations

import sqlite3

from .comum import Placar, pdf_sem_texto


def _rubrica():
    from app.models import Criterio, RequisitoEliminatorio, Rubrica
    return Rubrica(
        cargo="Analista de suporte", senioridade="pleno",
        eliminatorios=[RequisitoEliminatorio(
            id="ensino_superior", descricao="Superior completo em TI")],
        criterios=[
            Criterio(id="suporte", nome="Experiência em suporte",
                     descricao="mesa de ajuda, SLA", peso=40),
            Criterio(id="redes", nome="Redes e infraestrutura",
                     descricao="TCP/IP, VPN", peso=35),
            Criterio(id="ingles", nome="Inglês técnico",
                     descricao="documentação", peso=25),
        ],
    )


def rodar(placar: Placar) -> None:
    from app import extraction, pontuacao, storage
    from app.models import Criterio, NotaCriterio, ResultadoScore, Rubrica

    print("\nPontuação e migração")
    storage.iniciar()

    org_id = storage.criar_organizacao("Empresa de teste")
    usuario_id = storage.criar_usuario(org_id, "chefe@teste.com", "Chefe", "hash-falso", "admin")
    rubrica = _rubrica()

    # ---- média ponderada ----
    def media():
        resultado = ResultadoScore(
            criterios=[NotaCriterio(criterio_id="suporte", nota=10, evidencia="x"),
                       NotaCriterio(criterio_id="redes", nota=0,
                                    evidencia="sem evidência no currículo"),
                       NotaCriterio(criterio_id="ingles", nota=10, evidencia="y")],
            resumo="r", recomendacao="talvez")
        obtido = pontuacao.calcular_score(resultado, rubrica)
        esperado = round((10 * 40 + 0 * 35 + 10 * 25) * 10 / 100, 1)
        assert obtido == esperado == 65.0, f"obtido {obtido}, esperado {esperado}"
        return f"{obtido}/100"

    placar.rodar("Média ponderada é calculada em Python, não pelo modelo", media)

    # ---- critério não respondido conta como zero ----
    def faltante():
        resultado = ResultadoScore(
            criterios=[NotaCriterio(criterio_id="suporte", nota=10, evidencia="x")],
            resumo="r", recomendacao="chamar")
        assert pontuacao.calcular_score(resultado, rubrica) == 40.0
        faltantes = pontuacao.criterios_faltantes(resultado, rubrica)
        assert len(faltantes) == 2, faltantes
        assert "Redes e infraestrutura" in faltantes
        return "lacuna vira nota zero e fica registrada"

    placar.rodar("Critério sem resposta conta zero e é sinalizado", faltante)

    # ---- normalização de pesos ----
    def pesos():
        r = Rubrica(cargo="x", senioridade="y",
                    criterios=[Criterio(id="a", nome="A", descricao="d", peso=30),
                               Criterio(id="b", nome="B", descricao="d", peso=30)])
        r.normalizar_pesos()
        assert r.peso_total() == 100, r.peso_total()

        zerada = Rubrica(cargo="x", senioridade="y",
                         criterios=[Criterio(id="a", nome="A", descricao="d", peso=0),
                                    Criterio(id="b", nome="B", descricao="d", peso=0),
                                    Criterio(id="c", nome="C", descricao="d", peso=0)])
        zerada.normalizar_pesos()
        assert zerada.peso_total() == 100, zerada.peso_total()
        return f"{[c.peso for c in r.criterios]} e {[c.peso for c in zerada.criterios]}"

    placar.rodar("Pesos são normalizados para somar 100", pesos)

    # ---- ids repetidos não colidem ----
    def ids():
        r = Rubrica(cargo="x", senioridade="y",
                    criterios=[Criterio(id="mesmo", nome="A", descricao="d", peso=50),
                               Criterio(id="mesmo", nome="B", descricao="d", peso=50)])
        assert r.criterios[0].id != r.criterios[1].id, "dois critérios com o mesmo id"
        return f"{[c.id for c in r.criterios]}"

    placar.rodar("Critérios com id repetido são desambiguados", ids)

    # ---- conciliação nota x recomendação ----
    def conciliar():
        final, aviso = pontuacao.conciliar(85.0, "chamar")
        assert final == "chamar" and aviso is None, (final, aviso)

        final, aviso = pontuacao.conciliar(85.0, "descartar")
        assert final == "chamar", f"nota 85 com 'descartar' deveria valer a nota, veio {final}"
        assert aviso and "nota" in aviso, aviso

        final, aviso = pontuacao.conciliar(62.0, "chamar")
        assert final == "chamar" and aviso is None, "uma faixa de diferença é normal"
        return "divergência de duas faixas vale a nota e avisa"

    placar.rodar("Nota e recomendação divergentes são conciliadas", conciliar)

    # ---- cache de parse: o currículo é separado uma vez só ----
    contexto: dict = {}

    def cache_de_parse():
        from app.mcp_servidor import _garantir_parse

        vaga_id = storage.criar_vaga(org_id, "Analista de suporte",
                                     "descrição da vaga " * 10, usuario_id)
        storage.salvar_rubrica(org_id, vaga_id, rubrica.model_dump(), aprovada=True)
        contexto["vaga_id"] = vaga_id

        doc = extraction.Documento(
            candidato_id="cand000000000001", arquivo="cv_1.pdf",
            texto="Joana Ribeiro\njoana@exemplo.com\nAnalista de suporte N2 com SLA de 4h.",
        )
        storage.salvar_curriculo(org_id, doc)
        storage.vincular(vaga_id, doc.candidato_id)

        curriculo = storage.buscar_curriculo(org_id, doc.candidato_id)
        assert not curriculo.get("parse"), "o currículo já nasceu parseado"

        primeiro = _garantir_parse(org_id, curriculo)
        assert primeiro, "a separação de dado pessoal não aconteceu"

        # Na segunda vez o parse vem do banco: a separação não roda de novo.
        guardado = storage.buscar_curriculo(org_id, doc.candidato_id)
        assert guardado["parse"], "o parse não foi guardado"
        segundo = _garantir_parse(org_id, guardado)
        assert segundo == guardado["parse"], "o cache devolveu coisa diferente"
        return "separado uma vez, reaproveitado depois"

    placar.rodar("Currículo já separado vem do cache, sem refazer o trabalho", cache_de_parse)

    # ---- o painel de status fecha a conta ----
    def status_fecha():
        vaga_id = contexto["vaga_id"]

        # um avaliado, um eliminado, um sem texto (que nunca poderá ser avaliado)
        storage.salvar_avaliacao(vaga_id, "cand000000000001", estagio="avaliado",
                                 score_final=72.0, recomendacao="chamar", confianca="alta")

        cortado = extraction.Documento(candidato_id="cand000000000002",
                                       arquivo="cv_2.pdf", texto="texto do segundo")
        storage.salvar_curriculo(org_id, cortado)
        storage.vincular(vaga_id, cortado.candidato_id)
        storage.salvar_avaliacao(vaga_id, cortado.candidato_id, estagio="eliminado",
                                 score_final=0.0, recomendacao="descartar")

        # escaneado e o OCR não produziu nada: nunca poderá ser avaliado
        quebrado = extraction.Documento(candidato_id="cand000000000003",
                                        arquivo="cv_3.pdf", texto="", escaneado=True)
        storage.salvar_curriculo(org_id, quebrado)
        storage.vincular(vaga_id, quebrado.candidato_id)

        # escaneado, lido por OCR, com texto: conta em por_ocr e segue avaliável
        lido_por_ocr = extraction.Documento(
            candidato_id="cand000000000005", arquivo="cv_5.pdf",
            texto="Analista de suporte com SLA de 4 horas.",
            escaneado=True, origem_texto="ocr", ocr_confianca="baixa")
        storage.salvar_curriculo(org_id, lido_por_ocr)
        storage.vincular(vaga_id, lido_por_ocr.candidato_id)

        pendente = extraction.Documento(candidato_id="cand000000000004",
                                        arquivo="cv_4.pdf", texto="texto do quarto")
        storage.salvar_curriculo(org_id, pendente)
        storage.vincular(vaga_id, pendente.candidato_id)

        r = storage.resumo_da_vaga(org_id, vaga_id)
        assert r["total"] == 5, r
        assert r["avaliados"] == 1, r
        assert r["eliminados"] == 1, r
        assert r["erros"] == 1, f"o currículo sem texto tinha de contar como erro: {r}"
        assert r["pendentes"] == 2, r
        assert r["por_ocr"] == 1, (
            f"por_ocr conta texto vindo de OCR, não PDF escaneado sem texto: {r}"
        )
        assert r["ultimo_registro_em"], "faltou o carimbo da última avaliação"

        soma = r["avaliados"] + r["eliminados"] + r["erros"] + r["pendentes"]
        assert soma == r["total"], f"a conta não fecha: {soma} != {r['total']}"
        return f"{r['avaliados']}+{r['eliminados']}+{r['erros']}+{r['pendentes']} = {r['total']}"

    placar.rodar("Status fecha a conta e o currículo ilegível não fica pendente eterno",
                 status_fecha)

    # ---- lista e detalhe contam a mesma coisa ----
    def contagem_unica():
        """Achado do Vitral: `avaliados` tinha uma definição na lista de vagas e
        outra no detalhe. Batiam por coincidência do dado de teste e divergiriam
        na frente do cliente na primeira eliminação."""
        vaga_id = contexto["vaga_id"]

        detalhe = storage.resumo_da_vaga(org_id, vaga_id)
        lista = {v["id"]: v for v in storage.listar_vagas(org_id)}[vaga_id]

        for campo in ("total", "avaliados", "eliminados", "erros", "pendentes",
                      "com_veredito", "por_ocr", "ultimo_registro_em"):
            assert lista[campo] == detalhe[campo], (
                f"a lista e o detalhe discordam em '{campo}': "
                f"{lista[campo]} != {detalhe[campo]}"
            )

        assert detalhe["com_veredito"] == (
            detalhe["avaliados"] + detalhe["eliminados"] + detalhe["erros"]
        ), detalhe
        # A vaga tem eliminado e erro: é justamente o caso em que as duas
        # definições antigas divergiriam.
        assert detalhe["eliminados"] > 0 and detalhe["erros"] > 0, detalhe
        return (f"{detalhe['com_veredito']} com veredito nos dois lugares "
                f"(={detalhe['avaliados']}+{detalhe['eliminados']}+{detalhe['erros']})")

    placar.rodar("Lista de vagas e detalhe da vaga contam do mesmo jeito",
                 contagem_unica)

    # ---- o currículo que não pôde ser avaliado não some ----
    def ilegivel_aparece():
        """Achado do Vitral: o painel contava '3 com falha' e o recrutador não
        tinha nome nem arquivo para saber de quem era. O pedido original é
        explícito: 'não quero que sumam'."""
        vaga_id = contexto["vaga_id"]
        linhas = storage.ranking(org_id, vaga_id)

        com_erro = [l for l in linhas if l["estagio"] == "erro"]
        assert com_erro, (
            "o currículo sem texto não apareceu no ranking; o recrutador vê a "
            "contagem de falhas e não tem como saber quem é"
        )
        for linha in com_erro:
            assert linha["arquivo"], "candidato com falha sem nome de arquivo"
            assert linha["erro"], "candidato com falha sem motivo escrito"

        # E o que está só esperando avaliação não vira falha nem entulha a tela.
        ids = {l["candidato_id"] for l in linhas}
        assert "cand000000000004" not in ids, (
            "candidato apenas pendente apareceu no ranking como resultado"
        )
        return f"{len(com_erro)} com falha, com arquivo e motivo visíveis"

    placar.rodar("Currículo que não pôde ser avaliado aparece com nome e motivo",
                 ilegivel_aparece)

    # ---- avaliação herdada do modo API não some da conta ----
    def estagio_legado_conta():
        """Achado do Vitral: banco migrado do modo API pode ter `avaliacoes` com
        `estagio='erro'`, que o pipeline antigo gravava. Elas apareciam no
        ranking mas caíam em `pendentes` no painel — o recrutador via um a menos
        com veredito do que a tela listava."""
        vaga_id = contexto["vaga_id"]

        herdado = extraction.Documento(candidato_id="cand000000000009",
                                       arquivo="cv_legado.pdf",
                                       texto="texto que o pipeline antigo leu")
        storage.salvar_curriculo(org_id, herdado)
        storage.vincular(vaga_id, herdado.candidato_id)
        storage.salvar_avaliacao(vaga_id, herdado.candidato_id, estagio="erro",
                                 erro="a chave da API expirou no meio da corrida")

        r = storage.resumo_da_vaga(org_id, vaga_id)
        soma = r["avaliados"] + r["eliminados"] + r["erros"] + r["pendentes"]
        assert soma == r["total"], f"a conta não fecha: {soma} != {r['total']}"

        linhas = storage.ranking(org_id, vaga_id)
        no_ranking = [l for l in linhas if l["candidato_id"] == herdado.candidato_id]
        assert no_ranking, "o candidato herdado sumiu do ranking"
        assert no_ranking[0]["estagio"] == "erro", no_ranking[0]["estagio"]

        # O que o painel conta como falha tem de bater com o que a tela lista.
        falhas_na_tela = sum(1 for l in linhas if l["estagio"] == "erro")
        assert r["erros"] == falhas_na_tela, (
            f"painel diz {r['erros']} falha(s), a tela lista {falhas_na_tela}"
        )
        return f"{r['erros']} falha(s) no painel e na tela, com a conta fechando"

    placar.rodar("Avaliação herdada do modo API conta como falha, não como pendente",
                 estagio_legado_conta)

    # ---- PDF escaneado continua sendo reconhecido ----
    def escaneado():
        docs = extraction.extrair(pdf_sem_texto(), "digitalizado.pdf")
        doc = docs[0]
        assert doc.escaneado, "o PDF sem texto não foi marcado como escaneado"
        assert any("escaneado" in a for a in doc.avisos), doc.avisos
        assert not any("visão" in a for a in doc.avisos), (
            f"o aviso ainda promete leitura por visão, que não existe mais: {doc.avisos}"
        )
        return "marcado como escaneado, sem prometer leitura por visão"

    placar.rodar("PDF escaneado é marcado para OCR, não para visão", escaneado)

    # ---- migração v3 para v4 preserva os dados ----
    def migracao():
        import tempfile
        from pathlib import Path

        caminho = Path(tempfile.mkdtemp(prefix="triagem-v3-")) / "antigo.db"
        conn = sqlite3.connect(caminho)
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE organizacoes (
                id TEXT PRIMARY KEY, nome TEXT NOT NULL, retencao_dias INTEGER NOT NULL,
                limite_mensal_usd REAL NOT NULL DEFAULT 0, api_key_cifrada TEXT,
                api_key_mascara TEXT, ativa INTEGER NOT NULL DEFAULT 1,
                criada_em TEXT NOT NULL);
            CREATE TABLE vagas (
                id TEXT PRIMARY KEY, org_id TEXT NOT NULL, titulo TEXT NOT NULL,
                descricao TEXT NOT NULL, rubrica TEXT, rubrica_ok INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'rascunho', progresso TEXT, uso TEXT,
                erro TEXT, arquivada INTEGER NOT NULL DEFAULT 0, criada_por TEXT,
                criada_em TEXT NOT NULL, atualizada_em TEXT);
            CREATE TABLE curriculos (
                org_id TEXT NOT NULL, candidato_id TEXT NOT NULL, arquivo TEXT NOT NULL,
                origem TEXT NOT NULL DEFAULT 'arquivo', origem_hash TEXT, extensao TEXT,
                precisa_visao INTEGER NOT NULL DEFAULT 0, texto TEXT, parse TEXT,
                avisos TEXT, criado_em TEXT NOT NULL,
                PRIMARY KEY (org_id, candidato_id));
            CREATE TABLE gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, org_id TEXT NOT NULL, vaga_id TEXT,
                custo_usd REAL NOT NULL, detalhe TEXT, em TEXT NOT NULL);
            CREATE TABLE avaliacoes (
                vaga_id TEXT NOT NULL, candidato_id TEXT NOT NULL, estagio TEXT NOT NULL,
                score_final REAL, recomendacao TEXT, confianca TEXT, resultado TEXT,
                erro TEXT, avaliado_em TEXT NOT NULL,
                PRIMARY KEY (vaga_id, candidato_id));
            INSERT INTO organizacoes VALUES ('o1','Empresa',180,50.0,'cifrado','sk-…1234',1,'2026-01-01');
            INSERT INTO vagas VALUES ('v1','o1','Suporte','desc',NULL,1,'processando',
                                      '{"feitos":3}','{"custo_usd":2.1}',NULL,0,'u1','2026-01-01',NULL);
            INSERT INTO curriculos VALUES ('o1','c1','cv.pdf','arquivo','hash','.pdf',1,
                                           'texto do curriculo',NULL,NULL,'2026-01-01');
            INSERT INTO gastos VALUES (1,'o1','v1',2.10,NULL,'2026-01-01');
            INSERT INTO avaliacoes VALUES ('v1','c1','avaliado',88.0,'chamar','alta',
                                           NULL,NULL,'2026-01-02');
        """)
        conn.execute("PRAGMA user_version=3")
        conn.commit()
        conn.close()

        # Aplica a migração do jeito que o servidor aplica, no banco antigo.
        conn = sqlite3.connect(caminho)
        conn.row_factory = sqlite3.Row
        conn.executescript(storage.ESQUEMA)
        storage._migrar_v4(conn)
        conn.execute("PRAGMA user_version=4")
        conn.commit()

        colunas_org = {c["name"] for c in conn.execute("PRAGMA table_info(organizacoes)")}
        colunas_vagas = {c["name"] for c in conn.execute("PRAGMA table_info(vagas)")}
        colunas_curr = {c["name"] for c in conn.execute("PRAGMA table_info(curriculos)")}
        tabelas = {t["name"] for t in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}

        assert "gastos" not in tabelas, "a tabela de gastos sobreviveu"
        assert not {"limite_mensal_usd", "api_key_cifrada", "api_key_mascara"} & colunas_org
        assert not {"progresso", "uso"} & colunas_vagas
        assert "escaneado" in colunas_curr and "precisa_visao" not in colunas_curr

        # E, o que importa de verdade: nada de dado do cliente se perdeu.
        vaga = conn.execute("SELECT * FROM vagas WHERE id='v1'").fetchone()
        curriculo = conn.execute("SELECT * FROM curriculos WHERE candidato_id='c1'").fetchone()
        avaliacao = conn.execute("SELECT * FROM avaliacoes WHERE candidato_id='c1'").fetchone()
        assert vaga["titulo"] == "Suporte", "a vaga se perdeu na migração"
        assert vaga["status"] == "pronta", f"status de corrida morta ficou '{vaga['status']}'"
        assert curriculo["texto"] == "texto do curriculo", "o currículo se perdeu"
        assert curriculo["escaneado"] == 1, "a marca de escaneado não sobreviveu ao rename"
        assert avaliacao["score_final"] == 88.0, "a avaliação se perdeu"
        conn.close()
        return "gastos e colunas do modo API somem; vaga, currículo e avaliação ficam"

    placar.rodar("Migração v3 para v4 apaga o modo API sem perder dado do cliente",
                 migracao)

    # ---- eliminado não recebe número de colocação ----
    def sem_colocacao_para_quem_nao_disputa():
        """Bug pré-existente: `enumerate` sobre o ranking cru dava número de
        colocação a eliminado e erro, que não têm nota que os coloque em lugar
        nenhum. Um cortado no eliminatório aparecia como '47.' no relatório e 47
        na coluna Posição do CSV, indistinguível de quem ficou em 47º de verdade.

        A decisão do dono do produto sobre "Posição" continua valendo e é o que
        este teste também protege: os pontuados seguem 1..N sequenciais, sem
        buracos. O que muda é só quem não está no páreo."""
        linhas = storage.ranking(org_id, contexto["vaga_id"])
        rotulos = pontuacao.numerar_exibicao(linhas)

        assert len(rotulos) == len(linhas), "um rótulo por linha, na mesma ordem"

        numerados = [(r, l) for r, l in zip(rotulos, linhas) if r != "—"]
        assert numerados, "nenhum candidato pontuado recebeu número"

        for rotulo, linha in zip(rotulos, linhas):
            if pontuacao.ocupa_lugar(linha):
                assert rotulo.isdigit(), f"pontuado sem número: {rotulo!r}"
            else:
                assert rotulo == "—", (
                    f"{linha['estagio']} recebeu '{rotulo}' como colocação — "
                    "quem não tem nota não ocupa lugar no ranking"
                )

        # Sequencial e sem buracos: é a regra que o dono do produto fixou.
        assert [int(r) for r, _ in numerados] == list(range(1, len(numerados) + 1)), (
            f"a numeração dos pontuados saiu com buraco: {[r for r, _ in numerados]}"
        )

        # Vazio em vez de traço é o que a planilha do recrutador sabe ignorar.
        assert pontuacao.numerar_exibicao(linhas, vazio="") == [
            "" if r == "—" else r for r in rotulos
        ], "o rótulo de ausência do CSV não acompanhou o do relatório"

        return (f"{len(numerados)} pontuado(s) numerado(s) 1..{len(numerados)}, "
                f"{len(linhas) - len(numerados)} sem colocação")

    placar.rodar("Eliminado e erro não recebem número de colocação",
                 sem_colocacao_para_quem_nao_disputa)

    # ---- e a regra chega às duas superfícies que tinham o defeito ----
    def superficies_nao_numeram_eliminado():
        """O relatório interno e o CSV eram os dois lugares com o defeito. Testar
        só o helper deixaria o call site livre para voltar a usar `enumerate`."""
        import asyncio
        import csv as csv_mod
        import io as io_mod
        from html import escape

        from starlette.requests import Request

        from app.relatorio import montar_relatorio
        from app.rotas_vagas import exportar_csv

        vaga = storage.buscar_vaga(org_id, contexto["vaga_id"])
        linhas = storage.ranking(org_id, contexto["vaga_id"])
        cortados = [l for l in linhas if not pontuacao.ocupa_lugar(l)]
        assert cortados, "a vaga de teste precisa ter alguém sem nota"

        html = montar_relatorio("Triagem", None, dict(vaga), linhas,
                                {"nome": "Chefe"})
        for linha in cortados:
            nome = escape(linha.get("nome") or "—")
            assert f". {nome}</span>" not in html, (
                f"o relatório deu número de colocação a {linha['estagio']}: {nome}"
            )
            # A negativa acima passaria de graça se o markup mudasse; a positiva
            # abaixo prende o par ao formato que o relatório gera de fato.
            assert f"cand-nome'>— {nome}</span>" in html, (
                f"{linha['estagio']} não saiu com traço no lugar da colocação: {nome}"
            )

        # A rota de exportação de verdade, não uma reprodução dela aqui: é o
        # call site que voltaria a usar `enumerate` numa distração futura.
        requisicao = Request({"type": "http", "method": "GET", "path": "/",
                              "query_string": b"", "headers": [],
                              "client": ("127.0.0.1", 0)})
        usuario = {"org_id": org_id, "usuario_id": usuario_id, "nome": "Chefe"}

        async def baixar() -> bytes:
            resposta = await exportar_csv(contexto["vaga_id"], requisicao, usuario)
            return b"".join([p async for p in resposta.body_iterator])

        texto = asyncio.run(baixar()).decode("utf-8-sig")
        tabela = list(csv_mod.reader(io_mod.StringIO(texto), delimiter=";"))
        cabecalho, corpo = tabela[0], tabela[1:]
        coluna = cabecalho.index("Posição")
        assert len(corpo) == len(linhas), f"{len(corpo)} linhas para {len(linhas)}"

        for celula, linha in zip((l[coluna] for l in corpo), linhas):
            if pontuacao.ocupa_lugar(linha):
                assert celula.isdigit(), f"pontuado sem Posição no CSV: {celula!r}"
            else:
                assert celula == "", (
                    f"coluna Posição do CSV trouxe '{celula}' para {linha['estagio']}"
                )
        return "relatório e CSV deixam a posição em branco para quem não disputa"

    placar.rodar("Relatório interno e CSV não numeram quem não tem nota",
                 superficies_nao_numeram_eliminado)
