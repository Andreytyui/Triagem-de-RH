"""O conector do Claude: ferramentas, isolamento entre contas e OAuth.

O que mais importa aqui é a primeira asserção do bloco de anonimização: se o
nome do candidato sair por `proximos_curriculos`, o avaliador passa a enxergar
quem é a pessoa, e a proteção contra viés — que é metade do que se vende — cai.
"""
from __future__ import annotations

import asyncio

from .comum import Placar


def rodar(placar: Placar) -> None:
    from mcp.server.mcpserver.exceptions import ToolError

    from app import mcp_servidor as ms
    from app import storage
    from app.extraction import Documento
    from app.mcp_oauth import contexto_do_token, criar_token_pessoal
    from app.security import hash_senha

    print("\nConector MCP")
    storage.iniciar()

    org_id = storage.criar_organizacao("Empresa do conector")
    usuario_id = storage.criar_usuario(
        org_id, "conector@teste.com", "Recrutador", hash_senha("cafe com pao"), "admin"
    )
    ctx = {"usuario_id": usuario_id, "org_id": org_id,
           "nome": "Recrutador", "papel": "admin"}
    ms.definir_contexto_local(ctx)

    CURRICULO = (
        "Mariana Coelho Vasques\n"
        "mariana.vasques@exemplo.com | (81) 98812-4477 | Recife, PE\n\n"
        "ANALISTA DE SUPORTE N3\n"
        "Nove anos em suporte de infraestrutura corporativa.\n\n"
        "EXPERIENCIA\n"
        "Analista de Suporte N3 - Nexora Tecnologia (03/2021 - atual)\n"
        "  Atendimento de chamados com SLA de 4 horas.\n"
        "  Administracao de Active Directory para 900 usuarios.\n"
        "FORMACAO\n"
        "Tecnologo em Redes - Faculdade Ateneu - 2019\n"
    )

    contexto: dict = {}

    def ferramentas_registradas():
        nomes = {t.name for t in ms.mcp._tool_manager.list_tools()}
        for esperada in ("listar_vagas", "criar_vaga", "definir_criterios",
                         "proximos_curriculos", "registrar_avaliacao",
                         "registrar_eliminacao", "ver_ranking", "ver_candidato",
                         "registrar_decisao", "buscar_titular",
                         "apagar_dados_do_candidato"):
            assert esperada in nomes, f"ferramenta '{esperada}' não registrada"
        return f"{len(nomes)} ferramentas"

    placar.rodar("Todas as ferramentas do fluxo estão registradas", ferramentas_registradas)

    def sem_autenticacao():
        ms.definir_contexto_local(None)
        try:
            ms.listar_vagas()
            raise AssertionError("a ferramenta respondeu sem autenticação")
        except ms.NaoAutenticado as exc:
            # ToolError faz a mensagem chegar ao Claude; ValueError seria engolida.
            assert isinstance(exc, ToolError), "o erro não chegaria ao modelo"
        finally:
            ms.definir_contexto_local(ctx)
        return "sem token, nada responde"

    placar.rodar("Ferramenta sem autenticação é recusada", sem_autenticacao)

    def criar_e_definir():
        saida = ms.criar_vaga(
            titulo="Analista de Suporte Pleno",
            descricao="Atendimento N2 com SLA de 4 horas, Active Directory e VPN. " * 3,
        )
        assert "criada" in saida, saida[:120]
        assert "9.029" in saida, "não lembrou o limite legal ao propor critérios"
        vaga_id = saida.split("id: ")[1].split(")")[0]
        contexto["vaga_id"] = vaga_id

        saida = ms.definir_criterios(
            vaga_id=vaga_id, cargo="Analista de Suporte", senioridade="pleno",
            criterios=[
                {"id": "suporte", "nome": "Suporte N2", "descricao": "mesa de ajuda", "peso": 30},
                {"id": "ad", "nome": "Active Directory", "descricao": "contas e GPO", "peso": 30},
            ],
            eliminatorios=[{"id": "superior", "descricao": "Superior completo"}],
        )
        assert "Critérios gravados" in saida, saida[:120]
        # 30 + 30 tem de virar 50 + 50
        assert "peso 50%" in saida, f"pesos não foram normalizados: {saida[:200]}"
        return "vaga criada e rubrica normalizada"

    placar.rodar("Vaga e critérios são criados pelo conector", criar_e_definir)

    def anonimizacao_no_conector():
        """A asserção que sustenta o produto: o avaliador não vê quem é a pessoa."""
        vaga_id = contexto["vaga_id"]
        doc = Documento(candidato_id="mcpcand0001", arquivo="mariana.pdf",
                        texto=CURRICULO, origem="mcp")
        storage.salvar_curriculo(org_id, doc)
        storage.vincular(vaga_id, doc.candidato_id)

        lote = ms.proximos_curriculos(vaga_id=vaga_id, quantidade=3)
        for proibido in ("Mariana", "Coelho", "Vasques", "mariana.vasques",
                         "@exemplo.com", "98812-4477"):
            assert proibido not in lote, f"'{proibido}' vazou pelo conector"
        assert "Active Directory" in lote, "a anonimização comeu o conteúdo profissional"
        assert "Nexora Tecnologia" in lote, "o nome da empresa deveria sobreviver"
        assert "Critérios pontuados" in lote, "a rubrica não veio junto com o lote"
        assert "mcpcand0001" in lote, "o candidato_id não veio no lote"
        return "nome, e-mail e telefone não saem; o profissional sai"

    placar.rodar("Currículo sai anonimizado pelo conector", anonimizacao_no_conector)

    def avaliacao_calculada_aqui():
        vaga_id = contexto["vaga_id"]
        saida = ms.registrar_avaliacao(
            vaga_id=vaga_id, candidato_id="mcpcand0001",
            notas=[{"criterio_id": "suporte", "nota": 8, "evidencia": "SLA de 4 horas"},
                   {"criterio_id": "ad", "nota": 10, "evidencia": "Active Directory"}],
            resumo="Sólida em suporte.", recomendacao="chamar",
        )
        esperado = round((8 * 50 + 10 * 50) / 10, 1)          # 90.0
        assert f"{esperado}/100" in saida, f"nota errada: {saida[:120]}"

        rank = storage.ranking(org_id, vaga_id)
        assert rank[0]["score_final"] == esperado, rank[0]["score_final"]
        assert rank[0]["resultado"]["avaliado_por"] == "conector Claude"
        return f"{esperado}/100 calculado em Python, não pelo modelo"

    placar.rodar("A nota final é calculada pelo servidor", avaliacao_calculada_aqui)

    def criterio_invalido():
        """O Claude precisa da mensagem para se corrigir; erro genérico não serve."""
        try:
            ms.registrar_avaliacao(
                vaga_id=contexto["vaga_id"], candidato_id="mcpcand0001",
                notas=[{"criterio_id": "nao_existe", "nota": 10, "evidencia": "x"}],
                resumo="r", recomendacao="chamar",
            )
            raise AssertionError("aceitou critério fora da rubrica")
        except ToolError as exc:
            assert "não existem na rubrica" in str(exc), str(exc)
            assert "suporte" in str(exc), "não disse quais critérios são válidos"
        return "recusa e diz quais critérios valem"

    placar.rodar("Critério fora da rubrica é recusado com explicação", criterio_invalido)

    def divergencia():
        vaga_id = contexto["vaga_id"]
        doc = Documento(candidato_id="mcpcand0002", arquivo="outro.txt",
                        texto=CURRICULO.replace("Mariana Coelho Vasques", "Joao Pedro Silva"),
                        origem="mcp")
        storage.salvar_curriculo(org_id, doc)
        storage.vincular(vaga_id, doc.candidato_id)
        saida = ms.registrar_avaliacao(
            vaga_id=vaga_id, candidato_id="mcpcand0002",
            notas=[{"criterio_id": "suporte", "nota": 9, "evidencia": "e"},
                   {"criterio_id": "ad", "nota": 9, "evidencia": "e"}],
            resumo="r", recomendacao="descartar",
        )
        assert "Atenção" in saida, f"não sinalizou a divergência: {saida[:150]}"
        return "nota 90 com 'descartar' vira aviso, e vale a nota"

    placar.rodar("Divergência entre nota e recomendação é sinalizada", divergencia)

    def contato_so_quando_pedido():
        vaga_id = contexto["vaga_id"]
        sem = ms.ver_candidato(vaga_id=vaga_id, candidato_id="mcpcand0001")
        assert "@exemplo.com" not in sem, "o contato saiu sem ser pedido"
        com = ms.ver_candidato(vaga_id=vaga_id, candidato_id="mcpcand0001",
                               incluir_contato=True)
        assert "@exemplo.com" in com, "o contato não saiu nem quando pedido"

        acoes = [a["acao"] for a in storage.listar_auditoria(org_id, 50)]
        assert "curriculo.contato_consultado" in acoes, "a consulta não foi auditada"
        return "sai só com incluir_contato=True, e fica registrado"

    placar.rodar("Contato do candidato exige pedido explícito", contato_so_quando_pedido)

    # ---- o ranking não identifica ninguém ----
    def ranking_sem_nome():
        """Decisão do Product Manager (opção 1): nome e contato só saem por
        `ver_candidato`, sob pedido explícito.

        O risco era de correlação: na mesma conversa, o Claude via
        `candidato_id -> nome` no ranking e `candidato_id -> currículo
        anonimizado` em `proximos_curriculos`. Para quem já foi pontuado isso não
        muda nota; numa reavaliação com pesos novos, o avaliador saberia de quem
        era cada currículo.
        """
        vaga_id = contexto["vaga_id"]
        saida = ms.ver_ranking(vaga_id=vaga_id)

        curriculo = storage.buscar_curriculo(org_id, "mcpcand0001")
        identificacao = (curriculo.get("parse") or {}).get("identificacao") or {}
        nome = identificacao.get("nome") or ""
        assert nome, "o teste precisa de um candidato com nome guardado"

        assert nome not in saida, (
            f"o ranking do conector mostrou o nome {nome!r}; ele só pode sair "
            "por ver_candidato, sob pedido explícito"
        )
        for parte in nome.split():
            if len(parte) > 3:
                assert parte not in saida, f"sobrou {parte!r} no ranking do conector"
        if identificacao.get("email"):
            assert identificacao["email"] not in saida, "e-mail no ranking"
        if identificacao.get("telefone"):
            assert identificacao["telefone"] not in saida, "telefone no ranking"

        # E o que o recrutador precisa continua lá: id e nota.
        assert "mcpcand0001" in saida, "o ranking perdeu o candidato_id"
        assert "/100" in saida, "o ranking perdeu a nota"

        # O caminho legítimo continua funcionando, e só sob pedido.
        detalhe = ms.ver_candidato(vaga_id=vaga_id, candidato_id="mcpcand0001",
                                   incluir_contato=True)
        assert nome in detalhe, (
            "ver_candidato com incluir_contato=True precisa devolver o nome — "
            "é assim que o recrutador liga para a pessoa"
        )
        return "ranking sai por candidato_id; o nome só por ver_candidato"

    placar.rodar("Ranking do conector não identifica candidato", ranking_sem_nome)

    def isolamento():
        outra_org = storage.criar_organizacao("Empresa vizinha")
        outro_usuario = storage.criar_usuario(
            outra_org, "vizinho@teste.com", "Vizinho", hash_senha("cafe com pao"), "admin"
        )
        ms.definir_contexto_local({"usuario_id": outro_usuario, "org_id": outra_org,
                                   "nome": "Vizinho", "papel": "admin"})
        try:
            ms.ver_criterios(vaga_id=contexto["vaga_id"])
            raise AssertionError("o conector de outra conta enxergou a vaga")
        except ToolError as exc:
            assert "não encontrada" in str(exc), str(exc)
        finally:
            ms.definir_contexto_local(ctx)
        return "vaga de outra conta não existe para o conector"

    placar.rodar("Conector não atravessa a fronteira entre contas", isolamento)

    def exclusao_pede_confirmacao():
        previa = ms.apagar_dados_do_candidato(candidato_id="mcpcand0002")
        assert "Seria apagado" in previa, previa[:120]
        assert storage.buscar_curriculo(org_id, "mcpcand0002") is not None, (
            "apagou sem confirmação"
        )
        ms.apagar_dados_do_candidato(candidato_id="mcpcand0002", confirmar=True)
        assert storage.buscar_curriculo(org_id, "mcpcand0002") is None
        acoes = [a["acao"] for a in storage.listar_auditoria(org_id, 80)]
        assert "lgpd.exclusao" in acoes, "a exclusão não foi auditada"
        return "sem confirmar só mostra; com confirmar apaga e registra"

    placar.rodar("Exclusão pelo conector exige confirmação", exclusao_pede_confirmacao)

    # ---------- Tokens e OAuth ----------

    def token_pessoal():
        token = criar_token_pessoal(usuario_id, "notebook do teste")
        achado = contexto_do_token(token)
        assert achado and achado["org_id"] == org_id, str(achado)
        assert contexto_do_token("token-inventado") is None
        assert contexto_do_token("") is None

        listados = storage.mcp_listar_tokens(usuario_id, "pessoal")
        assert len(listados) == 1
        assert "token" not in listados[0], "o token em texto ficou guardado no banco"
        assert token[:12] not in str(listados[0]), "o banco guardou o token, não o hash"

        storage.mcp_apagar_token(listados[0]["token_hash"])
        assert contexto_do_token(token) is None, "o token revogado continuou valendo"
        return "vale enquanto existe, some ao revogar, e o banco só guarda o hash"

    placar.rodar("Token pessoal autentica e pode ser revogado", token_pessoal)

    def usuario_desativado():
        token = criar_token_pessoal(usuario_id, "temporario")
        assert contexto_do_token(token) is not None
        storage.atualizar_usuario(usuario_id, ativo=0)
        try:
            assert contexto_do_token(token) is None, (
                "token de usuário desativado continuou funcionando"
            )
        finally:
            storage.atualizar_usuario(usuario_id, ativo=1)
        return "desativar a pessoa corta o conector dela"

    placar.rodar("Token de usuário desativado para de valer", usuario_desativado)

    def fluxo_oauth():
        """O caminho que o claude.ai percorre: registro, autorização, troca."""
        from mcp.server.auth.provider import AuthorizationParams
        from mcp.shared.auth import OAuthClientInformationFull

        from app.mcp_oauth import AutorizadorTriagem

        autorizador = AutorizadorTriagem()
        cliente = OAuthClientInformationFull(
            client_id="cliente-de-teste",
            redirect_uris=["https://claude.ai/api/mcp/auth_callback"],
            client_name="Claude (teste)",
        )
        asyncio.run(autorizador.register_client(cliente))
        assert asyncio.run(autorizador.get_client("cliente-de-teste")) is not None
        assert asyncio.run(autorizador.get_client("nao-existe")) is None

        destino = asyncio.run(autorizador.authorize(cliente, AuthorizationParams(
            state="xyz", scopes=["triagem"], code_challenge="desafio-pkce",
            redirect_uri="https://claude.ai/api/mcp/auth_callback",
            redirect_uri_provided_explicitly=True, resource=None,
        )))
        assert "/mcp/consentir?pedido=" in destino, destino
        pedido_id = destino.split("pedido=")[1]
        pedido = storage.mcp_buscar_pedido(pedido_id)
        assert pedido and pedido["state"] == "xyz", str(pedido)

        # A tela de consentimento cria o código depois que a pessoa autoriza.
        storage.mcp_criar_codigo(
            codigo="codigo-de-teste", client_id=cliente.client_id,
            usuario_id=usuario_id, redirect_uri=pedido["redirect_uri"],
            redirect_explicito=True, code_challenge=pedido["code_challenge"],
            scopes=pedido["scopes"], recurso=None,
        )
        codigo = asyncio.run(
            autorizador.load_authorization_code(cliente, "codigo-de-teste")
        )
        assert codigo and codigo.subject == usuario_id

        emitido = asyncio.run(
            autorizador.exchange_authorization_code(cliente, codigo)
        )
        assert emitido.access_token and emitido.refresh_token

        acesso = asyncio.run(autorizador.load_access_token(emitido.access_token))
        assert acesso and acesso.subject == usuario_id
        assert (acesso.claims or {}).get("org_id") == org_id, str(acesso.claims)

        # Código de autorização é de uso único.
        assert asyncio.run(
            autorizador.load_authorization_code(cliente, "codigo-de-teste")
        ) is None, "o código de autorização foi aceito duas vezes"

        # Renovação rotaciona o refresh.
        refresh = asyncio.run(
            autorizador.load_refresh_token(cliente, emitido.refresh_token)
        )
        assert refresh is not None
        renovado = asyncio.run(
            autorizador.exchange_refresh_token(cliente, refresh, ["triagem"])
        )
        assert renovado.access_token != emitido.access_token
        assert asyncio.run(
            autorizador.load_refresh_token(cliente, emitido.refresh_token)
        ) is None, "o refresh antigo continuou valendo depois de usado"
        return "registro, consentimento, troca, rotação e uso único"

    placar.rodar("Fluxo OAuth completo do conector funciona", fluxo_oauth)

    # ---------- Transporte HTTP ----------

    def transporte_libera_o_dominio_de_producao():
        """Regressão: o SDK auto-liga proteção contra DNS rebinding com uma lista
        que só tem localhost, e devolvia 421 em qualquer domínio real — o /mcp
        funcionava na máquina do dev e quebrava no primeiro deploy."""
        from mcp.server.transport_security import TransportSecurityMiddleware

        cfg = ms._seguranca_de_transporte("https://triagem.exemplo.com")
        assert cfg.enable_dns_rebinding_protection,             "a proteção contra DNS rebinding foi desligada"

        porteiro = TransportSecurityMiddleware(cfg)
        assert porteiro._validate_host("triagem.exemplo.com"),             "o domínio de produção foi recusado — é exatamente o 421 de volta"
        assert porteiro._validate_host("triagem.exemplo.com:443"),             "Host com a porta padrão explícita, como um proxy manda, foi recusado"
        assert porteiro._validate_host("127.0.0.1:8000"),             "o desenvolvimento local deixou de funcionar"
        assert not porteiro._validate_host("atacante.exemplo.com"),             "um host qualquer foi aceito; a proteção virou enfeite"
        assert porteiro._validate_origin("https://triagem.exemplo.com"),             "a origem do próprio domínio foi recusada"
        return "domínio real entra, localhost continua, host estranho não"

    placar.rodar("Conector HTTP aceita o domínio de produção, não só localhost",
                 transporte_libera_o_dominio_de_producao)

    def transporte_normaliza_e_avisa():
        """Duas armadilhas de configuração: BASE_URL com maiúscula (o SDK compara
        string exata) e BASE_URL sem esquema (urlparse devolve netloc vazio, e o
        421 voltaria calado)."""
        from mcp.server.transport_security import TransportSecurityMiddleware

        cfg = ms._seguranca_de_transporte("https://Triagem.Exemplo.COM")
        porteiro = TransportSecurityMiddleware(cfg)
        assert porteiro._validate_host("triagem.exemplo.com"),             "BASE_URL com maiúscula recusou o Host minúsculo que o cliente manda"

        sem_esquema = ms._seguranca_de_transporte("triagem.exemplo.com")
        assert sem_esquema.enable_dns_rebinding_protection,             "BASE_URL malformado desligou a proteção"
        guarda = TransportSecurityMiddleware(sem_esquema)
        assert guarda._validate_host("127.0.0.1:8000"),             "BASE_URL malformado derrubou até o acesso local"
        assert not guarda._validate_host("triagem.exemplo.com"),             "host sem esquema foi aceito por acidente, mascarando o erro de config"
        return "maiúscula normalizada; sem esquema, cai para local e loga erro"

    placar.rodar("Configuração torta de BASE_URL não passa despercebida",
                 transporte_normaliza_e_avisa)
