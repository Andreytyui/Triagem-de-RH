"""Recuperação de senha: o fluxo por e-mail e o comando da instalação local.

O que este grupo protege, além do fluxo funcionar: que a rota não diga quem tem
conta neste servidor. Currículo é dado sensível, e saber que uma agência é
cliente já é informação sobre o negócio dela — o login inteiro foi escrito com
esse cuidado, e uma rota nova de senha seria o furo óbvio.
"""
from __future__ import annotations

import contextlib
import time

from .comum import Placar

SENHA_BOA = "cafe com pao na chuva"
SENHA_NOVA = "outra frase inteira aqui"


def rodar(placar: Placar) -> None:
    from fastapi.testclient import TestClient

    from app import correio, storage
    from app.config import RECUPERACAO_MAX_PEDIDOS
    from app.main import app
    from app.security import conferir_senha, hash_senha, hash_token

    print("\nRecuperação de senha")
    storage.iniciar()

    enviados: list[dict] = []

    def correio_falso(destino: str, assunto: str, corpo: str) -> bool:
        enviados.append({"destino": destino, "assunto": assunto, "corpo": corpo})
        return True

    original = correio.enviar
    correio.enviar = correio_falso

    org_id = storage.criar_organizacao("Agência da recuperação")
    email = "recrutador@recuperacao.com"
    usuario_id = storage.criar_usuario(org_id, email, "Recrutador",
                                       hash_senha(SENHA_BOA), "admin")

    def token_do_ultimo_email() -> str:
        assert enviados, "nenhum e-mail foi enviado"
        corpo = enviados[-1]["corpo"]
        marca = "?recuperar="
        assert marca in corpo, f"o e-mail não trouxe link: {corpo[:200]}"
        return corpo.split(marca, 1)[1].split()[0].strip()

    try:
        # Cliente sem o ciclo de vida do app: o gerenciador de sessão do MCP só
        # aceita rodar uma vez por processo, e o grupo de segurança já o subiu.
        # Estas rotas não dependem dele — o banco já foi iniciado acima.
        with contextlib.nullcontext(TestClient(app)) as c:
            # ---- fluxo feliz ----
            def fluxo_feliz():
                enviados.clear()
                storage.limpar_tentativas(f"recuperar|{email}|testclient")
                r = c.post("/api/auth/recuperar", json={"email": email})
                assert r.status_code == 204, (r.status_code, r.text)
                assert len(enviados) == 1, f"esperava 1 e-mail, saíram {len(enviados)}"
                assert enviados[0]["destino"] == email

                token = token_do_ultimo_email()
                # o banco guarda só o hash: o token em claro não pode estar lá
                assert storage.buscar_recuperacao(token) is None, (
                    "o token foi guardado em claro no banco"
                )
                assert storage.buscar_recuperacao(hash_token(token)), (
                    "o pedido não foi gravado pelo hash"
                )

                r = c.post("/api/auth/redefinir", json={"token": token, "senha": SENHA_NOVA})
                assert r.status_code == 204, (r.status_code, r.text)

                registro = storage.buscar_usuario(usuario_id)
                assert conferir_senha(SENHA_NOVA, registro["senha_hash"]), "a senha não trocou"
                assert not conferir_senha(SENHA_BOA, registro["senha_hash"]), (
                    "a senha antiga continua valendo"
                )
                return "link chega, troca a senha e a antiga morre"

            placar.rodar("Link do e-mail redefine a senha", fluxo_feliz)

            # ---- uso único ----
            def uso_unico():
                enviados.clear()
                storage.limpar_tentativas(f"recuperar|{email}|testclient")
                c.post("/api/auth/recuperar", json={"email": email})
                token = token_do_ultimo_email()

                primeira = c.post("/api/auth/redefinir",
                                  json={"token": token, "senha": "uma senha bem diferente"})
                assert primeira.status_code == 204, primeira.text

                segunda = c.post("/api/auth/redefinir",
                                 json={"token": token, "senha": "mais outra senha ainda"})
                assert segunda.status_code == 400, (
                    f"o mesmo link funcionou duas vezes: {segunda.status_code}"
                )
                assert "token_invalido" in segunda.text, segunda.text
                return "o segundo uso do mesmo link é recusado"

            placar.rodar("Link serve uma vez só", uso_unico)

            # ---- expiração ----
            def expirado():
                enviados.clear()
                storage.limpar_tentativas(f"recuperar|{email}|testclient")
                c.post("/api/auth/recuperar", json={"email": email})
                token = token_do_ultimo_email()

                # envelhece o pedido à mão, sem esperar meia hora
                storage._executar(
                    "UPDATE recuperacoes SET expira_em=? WHERE token_hash=?",
                    ("2020-01-01T00:00:00+00:00", hash_token(token)),
                )
                r = c.post("/api/auth/redefinir",
                           json={"token": token, "senha": "senha que nao vai valer"})
                assert r.status_code == 400, r.status_code
                assert "token_expirado" in r.text, r.text
                assert storage.buscar_recuperacao(hash_token(token)) is None, (
                    "o pedido vencido continuou no banco"
                )
                return "link vencido é recusado com código próprio"

            placar.rodar("Link vencido não redefine nada", expirado)

            # ---- senha curta ----
            def senha_curta():
                enviados.clear()
                storage.limpar_tentativas(f"recuperar|{email}|testclient")
                c.post("/api/auth/recuperar", json={"email": email})
                token = token_do_ultimo_email()

                r = c.post("/api/auth/redefinir", json={"token": token, "senha": "curta"})
                assert r.status_code == 400, r.status_code
                assert "senha_curta" in r.text, r.text
                # e o link continua valendo, para a pessoa tentar de novo
                r = c.post("/api/auth/redefinir",
                           json={"token": token, "senha": "agora sim uma frase boa"})
                assert r.status_code == 204, "o link morreu por causa de uma senha fraca"
                return "recusa a senha fraca sem queimar o link"

            placar.rodar("Senha fraca é recusada com código próprio", senha_curta)

            # ---- a rota não revela quem tem conta ----
            def nao_revela():
                storage.limpar_tentativas(f"recuperar|{email}|testclient")
                storage.limpar_tentativas("recuperar|desconhecido@exemplo.com|testclient")

                def medir(alvo: str) -> tuple[int, str, float]:
                    inicio = time.perf_counter()
                    r = c.post("/api/auth/recuperar", json={"email": alvo})
                    return r.status_code, r.text, time.perf_counter() - inicio

                existe = medir(email)
                nao_existe = medir("desconhecido@exemplo.com")

                assert existe[0] == nao_existe[0] == 204, (existe[0], nao_existe[0])
                assert existe[1] == nao_existe[1] == "", (
                    f"as respostas diferem no corpo: {existe[1]!r} vs {nao_existe[1]!r}"
                )
                # O envio vai para segundo plano justamente para o tempo não contar
                # quem existe. Margem folgada: o que não pode é ordem de grandeza.
                diferenca = abs(existe[2] - nao_existe[2])
                assert diferenca < 0.25, (
                    f"a resposta demora {diferenca:.3f}s a mais para quem tem conta"
                )
                return f"mesmo status, mesmo corpo, {diferenca * 1000:.0f}ms de diferença"

            placar.rodar("Recuperar não diz se o e-mail tem conta", nao_revela)

            # ---- freio de tentativas ----
            def freio():
                alvo = "alvo-de-bombardeio@exemplo.com"
                storage.criar_usuario(org_id, alvo, "Alvo", hash_senha(SENHA_BOA))
                storage.limpar_tentativas(f"recuperar|{alvo}|testclient")
                enviados.clear()

                for _ in range(RECUPERACAO_MAX_PEDIDOS + 3):
                    r = c.post("/api/auth/recuperar", json={"email": alvo})
                    assert r.status_code == 204, "o freio mudou a resposta e entregou o jogo"

                assert len(enviados) <= RECUPERACAO_MAX_PEDIDOS, (
                    f"saíram {len(enviados)} e-mails para o mesmo endereço; "
                    f"o teto é {RECUPERACAO_MAX_PEDIDOS}"
                )
                return f"{len(enviados)} e-mails em {RECUPERACAO_MAX_PEDIDOS + 3} pedidos"

            placar.rodar("Pedidos demais param de virar e-mail, sem mudar a resposta", freio)

            # ---- redefinir derruba sessão e conector ----
            def corta_o_que_a_senha_sustentava():
                storage.limpar_tentativas(f"recuperar|{email}|testclient")
                enviados.clear()

                registro = storage.buscar_usuario(usuario_id)
                storage.atualizar_usuario(usuario_id, senha_hash=hash_senha(SENHA_BOA))

                entrada = c.post("/api/auth/login", json={"email": email, "senha": SENHA_BOA})
                assert entrada.status_code == 200, entrada.text
                assert c.get("/api/auth/eu").status_code == 200, "a sessão não abriu"

                storage.mcp_criar_token(hash_token("token-do-conector"), "pessoal",
                                        usuario_id, rotulo="Claude Desktop")
                assert storage.mcp_listar_tokens(usuario_id, "pessoal"), "token não criado"

                c.post("/api/auth/recuperar", json={"email": email})
                token = token_do_ultimo_email()
                r = c.post("/api/auth/redefinir",
                           json={"token": token, "senha": "senha nova depois do reset"})
                assert r.status_code == 204, r.text

                assert not storage.mcp_listar_tokens(usuario_id, "pessoal"), (
                    "o token do conector sobreviveu à redefinição de senha"
                )
                assert c.get("/api/auth/eu").status_code == 401, (
                    "a sessão antiga continuou de pé depois de trocar a senha"
                )
                del registro
                return "sessão cai e conector é revogado"

            placar.rodar("Redefinir corta sessões abertas e tokens do conector",
                         corta_o_que_a_senha_sustentava)

        # ---- o comando da instalação local ----
        def comando_local():
            from app.senha import redefinir as redefinir_por_comando

            alvo = "instalacao-local@exemplo.com"
            local_id = storage.criar_usuario(org_id, alvo, "Solo", hash_senha(SENHA_BOA))
            storage.mcp_criar_token(hash_token("conector-local"), "pessoal", local_id)

            ok, mensagem = redefinir_por_comando(alvo, "senha nova por linha de comando")
            assert ok, mensagem
            registro = storage.buscar_usuario(local_id)
            assert conferir_senha("senha nova por linha de comando", registro["senha_hash"])
            assert not storage.mcp_listar_tokens(local_id, "pessoal"), (
                "o comando local não revogou o conector"
            )

            ok, mensagem = redefinir_por_comando(alvo, "curta")
            assert not ok and "10 caracteres" in mensagem, mensagem

            ok, mensagem = redefinir_por_comando("nao-existe@exemplo.com", SENHA_NOVA)
            assert not ok, "aceitou redefinir conta inexistente"
            return "mesmo efeito do link, sem depender de e-mail"

        placar.rodar("Comando de linha redefine a senha na instalação local", comando_local)

        # ---- sem SMTP, o link vai para o log e o fluxo continua ----
        def sem_relay():
            correio.enviar = original
            assert not correio.configurado(), (
                "o ambiente de teste não deveria ter SMTP configurado"
            )
            # `enviar` sem relay não levanta exceção: escreve no log e devolve False.
            assert correio.enviar("alguem@exemplo.com", "assunto", "corpo") is False
            return "sem relay o envio vira log, e nada quebra"

        placar.rodar("Sem SMTP configurado, o fluxo não trava", sem_relay)

    finally:
        correio.enviar = original
