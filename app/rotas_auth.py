"""Contas, sessão e configurações da organização."""
from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from . import correio, storage
from .config import (
    BASE_URL,
    CODIGO_CONVITE,
    COOKIE_CSRF,
    COOKIE_SEGURO,
    COOKIE_SESSAO,
    LOGIN_JANELA_MIN,
    LOGIN_MAX_TENTATIVAS,
    PERMITIR_CADASTRO,
    RECUPERACAO_JANELA_MIN,
    RECUPERACAO_MAX_PEDIDOS,
    RECUPERACAO_MINUTOS,
    RECUPERACAO_MODO,
    RETENCAO_DIAS_MAX,
    RETENCAO_DIAS_MIN,
    SESSAO_HORAS,
)
from .deps import admin_atual, auditar, ip_do, organizacao_atual, usuario_atual
from .models import (
    ConfigOrganizacao,
    Credenciais,
    NovaConta,
    NovoUsuario,
    PedidoRecuperacao,
    RedefinicaoSenha,
    TrocaSenha,
)
from .security import (
    conferir_senha,
    criticar_senha,
    hash_senha,
    hash_token,
    novo_token,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["conta"])


def _abrir_sessao(response: Response, request: Request, usuario_id: str) -> None:
    token = novo_token()
    csrf = novo_token()
    storage.criar_sessao(
        usuario_id, hash_token(token), csrf, SESSAO_HORAS,
        ip=ip_do(request), agente=request.headers.get("user-agent", ""),
    )
    comum = {
        "max_age": SESSAO_HORAS * 3600,
        "secure": COOKIE_SEGURO,
        "samesite": "lax",
        "path": "/",
    }
    # O de sessão é HttpOnly: script na página não alcança o token.
    response.set_cookie(COOKIE_SESSAO, token, httponly=True, **comum)
    # O de CSRF precisa ser legível pelo JS para voltar no cabeçalho.
    response.set_cookie(COOKIE_CSRF, csrf, httponly=False, **comum)


def _fechar_sessao(response: Response) -> None:
    for nome in (COOKIE_SESSAO, COOKIE_CSRF):
        response.delete_cookie(nome, path="/")


def _publico(usuario: dict, org: dict) -> dict:
    return {
        "usuario": {
            "id": usuario["usuario_id"],
            "nome": usuario["nome"],
            "email": usuario["email"],
            "papel": usuario["papel"],
        },
        "organizacao": {
            "id": org["id"],
            "nome": org["nome"],
            "retencao_dias": org["retencao_dias"],
        },
    }


# ---------- Cadastro e login ----------

@router.post("/auth/registrar", status_code=201)
async def registrar(dados: NovaConta, request: Request, response: Response):
    """Cria a organização e o primeiro usuário, que já entra como administrador."""
    if not PERMITIR_CADASTRO:
        raise HTTPException(403, "o cadastro está fechado neste servidor")
    if CODIGO_CONVITE and dados.convite.strip() != CODIGO_CONVITE:
        raise HTTPException(403, "código de convite inválido")

    problema = criticar_senha(dados.senha)
    if problema:
        raise HTTPException(400, problema)
    if storage.buscar_usuario_por_email(dados.email):
        raise HTTPException(409, "já existe uma conta com esse e-mail")

    org_id = storage.criar_organizacao(dados.organizacao.strip())
    usuario_id = storage.criar_usuario(
        org_id, dados.email, dados.nome.strip(), hash_senha(dados.senha), papel="admin"
    )
    storage.registrar_auditoria(org_id, usuario_id, "conta.criada",
                                "organizacao", org_id, ip=ip_do(request))
    _abrir_sessao(response, request, usuario_id)

    usuario = storage.buscar_usuario(usuario_id)
    return _publico(
        {**usuario, "usuario_id": usuario_id}, storage.buscar_organizacao(org_id)
    )


@router.post("/auth/login")
async def login(dados: Credenciais, request: Request, response: Response):
    chave = f"{dados.email.strip().lower()}|{ip_do(request)}"
    if storage.contar_tentativas(chave, LOGIN_JANELA_MIN) >= LOGIN_MAX_TENTATIVAS:
        raise HTTPException(
            429, f"tentativas demais; espere {LOGIN_JANELA_MIN} minutos e tente de novo"
        )

    usuario = storage.buscar_usuario_por_email(dados.email)
    # Confere a senha mesmo sem usuário: o tempo de resposta não conta quem existe.
    referencia = usuario["senha_hash"] if usuario else _HASH_FALSO
    senha_ok = conferir_senha(dados.senha, referencia)

    if not usuario or not senha_ok or not usuario["ativo"]:
        storage.registrar_tentativa(chave)
        raise HTTPException(401, "e-mail ou senha incorretos")

    storage.limpar_tentativas(chave)
    storage.atualizar_usuario(usuario["id"], ultimo_acesso=storage.agora())
    _abrir_sessao(response, request, usuario["id"])
    storage.registrar_auditoria(usuario["org_id"], usuario["id"], "sessao.aberta",
                                ip=ip_do(request))

    org = storage.buscar_organizacao(usuario["org_id"])
    if not org or not org.get("ativa"):
        _fechar_sessao(response)
        raise HTTPException(403, "esta conta está suspensa")
    return _publico({**usuario, "usuario_id": usuario["id"]}, org)


# Hash descartável, com o mesmo custo de um real: sem ele, o login responderia
# mais rápido para e-mail inexistente e isso revelaria quem tem conta.
_HASH_FALSO = hash_senha("nao-existe-este-usuario")


@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_SESSAO)
    if token:
        storage.encerrar_sessao(hash_token(token))
    _fechar_sessao(response)
    return {"ok": True}


@router.get("/auth/eu")
async def eu(usuario: dict = Depends(usuario_atual),
             org: dict = Depends(organizacao_atual)):
    return _publico(usuario, org)


@router.post("/auth/senha")
async def trocar_senha(dados: TrocaSenha, request: Request, response: Response,
                       usuario: dict = Depends(usuario_atual)):
    registro = storage.buscar_usuario(usuario["usuario_id"])
    if not registro or not conferir_senha(dados.senha_atual, registro["senha_hash"]):
        raise HTTPException(403, "a senha atual não confere")
    problema = criticar_senha(dados.senha_nova)
    if problema:
        raise HTTPException(400, problema)

    storage.atualizar_usuario(usuario["usuario_id"], senha_hash=hash_senha(dados.senha_nova))
    # Trocar a senha derruba as outras sessões; a atual é reaberta na hora.
    storage.encerrar_sessoes_do_usuario(usuario["usuario_id"])
    _abrir_sessao(response, request, usuario["usuario_id"])
    auditar(request, usuario, "senha.alterada")
    return {"ok": True}


# ---------- Recuperação de senha ----------
#
# A regra que atravessa as duas rotas: nada aqui pode dizer se um e-mail tem
# conta neste servidor. Não é preciosismo — currículo é dado sensível, e saber
# que uma agência é cliente já é informação sobre o negócio dela. O login já
# gasta o mesmo tempo com e-mail inexistente; estas rotas fazem o mesmo.


def _sem_recuperacao_por_email() -> None:
    """No modo local a rota não existe. O que não existe não é atacado."""
    if RECUPERACAO_MODO != "email":
        raise HTTPException(404, "esta instalação redefine a senha por linha de comando")


def _mensagem_de_recuperacao(nome: str, link: str) -> str:
    return (
        f"Olá, {nome}.\n\n"
        "Alguém pediu para redefinir a senha da sua conta. Se foi você, use o "
        f"link abaixo:\n\n{link}\n\n"
        f"O link vale por {RECUPERACAO_MINUTOS} minutos e serve uma vez só.\n\n"
        "Se não foi você, ignore esta mensagem: a senha atual continua valendo e "
        "ninguém entrou na sua conta.\n"
    )


@router.post("/auth/recuperar", status_code=status.HTTP_204_NO_CONTENT)
async def recuperar(dados: PedidoRecuperacao, request: Request,
                    tarefas: BackgroundTasks) -> Response:
    """Pede o link de redefinição. Responde 204 sempre, exista ou não a conta.

    O envio vai para segundo plano de propósito: assim o tempo de resposta não
    depende de ter havido e-mail para mandar, que seria justamente o vazamento
    que esta rota existe para evitar.
    """
    _sem_recuperacao_por_email()

    email = dados.email.strip().lower()
    chave = f"recuperar|{email}|{ip_do(request)}"
    if storage.contar_tentativas(chave, RECUPERACAO_JANELA_MIN) >= RECUPERACAO_MAX_PEDIDOS:
        # Mesmo aqui a resposta é 204: um 429 diria que este e-mail é interessante.
        log.warning("pedidos de recuperação demais para %s", chave)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    storage.registrar_tentativa(chave)

    usuario = storage.buscar_usuario_por_email(email)
    # O token é gerado dos dois lados: gerar só quando existe conta faria a rota
    # responder mais rápido para quem não tem, e isso é a resposta que se quer
    # esconder.
    token = novo_token()
    if usuario and usuario["ativo"]:
        storage.criar_recuperacao(
            usuario["id"], hash_token(token), RECUPERACAO_MINUTOS, ip_do(request)
        )
        link = f"{BASE_URL}/?recuperar={token}"
        tarefas.add_task(
            correio.enviar, email, "Redefinir sua senha",
            _mensagem_de_recuperacao(usuario["nome"], link),
        )
        storage.registrar_auditoria(usuario["org_id"], usuario["id"],
                                    "senha.recuperacao_pedida", ip=ip_do(request))

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/redefinir", status_code=status.HTTP_204_NO_CONTENT)
async def redefinir(dados: RedefinicaoSenha, request: Request) -> Response:
    """Troca a senha pelo token do e-mail.

    Aqui, diferente da rota acima, o erro é específico: quem chegou com um token
    na mão precisa saber se ele expirou ou se já foi usado, senão fica tentando
    o mesmo link para sempre. E o token não diz de quem é a conta.
    """
    _sem_recuperacao_por_email()

    pedido = storage.buscar_recuperacao(hash_token(dados.token))
    if not pedido:
        raise HTTPException(400, {"codigo": "token_invalido",
                                  "mensagem": "este link não é válido"})
    if pedido["expira_em"] < storage.agora():
        storage.consumir_recuperacao(pedido["token_hash"])
        raise HTTPException(400, {"codigo": "token_expirado",
                                  "mensagem": "este link expirou"})

    problema = criticar_senha(dados.senha)
    if problema:
        raise HTTPException(400, {"codigo": "senha_curta", "mensagem": problema})

    usuario = storage.buscar_usuario(pedido["usuario_id"])
    if not usuario or not usuario["ativo"]:
        storage.consumir_recuperacao(pedido["token_hash"])
        raise HTTPException(400, {"codigo": "token_invalido",
                                  "mensagem": "este link não é válido"})

    _aplicar_senha_nova(usuario["id"], dados.senha)
    storage.registrar_auditoria(usuario["org_id"], usuario["id"],
                                "senha.redefinida", ip=ip_do(request))
    storage.limpar_tentativas(f"recuperar|{usuario['email']}|{ip_do(request)}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _aplicar_senha_nova(usuario_id: str, senha: str) -> None:
    """Troca a senha e corta tudo que a senha antiga sustentava.

    Quem redefine a senha ou esqueceu dela, ou desconfia que alguém a tem. Nos
    dois casos, deixar de pé uma sessão aberta ou um token do conector seria
    deixar a porta que se está tentando fechar.
    """
    storage.atualizar_usuario(usuario_id, senha_hash=hash_senha(senha))
    storage.invalidar_recuperacoes_do_usuario(usuario_id)
    storage.encerrar_sessoes_do_usuario(usuario_id)
    storage.mcp_revogar_do_usuario(usuario_id)


# ---------- Usuários da organização ----------

@router.get("/org/usuarios")
async def listar_usuarios(usuario: dict = Depends(usuario_atual)):
    return storage.listar_usuarios(usuario["org_id"])


@router.post("/org/usuarios", status_code=201)
async def criar_usuario(dados: NovoUsuario, request: Request,
                        admin: dict = Depends(admin_atual)):
    problema = criticar_senha(dados.senha)
    if problema:
        raise HTTPException(400, problema)
    if storage.buscar_usuario_por_email(dados.email):
        raise HTTPException(409, "já existe uma conta com esse e-mail")

    novo_id = storage.criar_usuario(
        admin["org_id"], dados.email, dados.nome.strip(),
        hash_senha(dados.senha), papel=dados.papel,
    )
    auditar(request, admin, "usuario.criado", "usuario", novo_id,
            {"email": dados.email, "papel": dados.papel})
    return {"id": novo_id, "email": dados.email.lower(), "nome": dados.nome,
            "papel": dados.papel, "ativo": 1}


@router.delete("/org/usuarios/{usuario_id}")
async def remover_usuario(usuario_id: str, request: Request,
                          admin: dict = Depends(admin_atual)):
    if usuario_id == admin["usuario_id"]:
        raise HTTPException(400, "você não pode remover a si mesmo")

    alvo = storage.buscar_usuario(usuario_id)
    if not alvo or alvo["org_id"] != admin["org_id"]:
        raise HTTPException(404, "usuário não encontrado")
    if alvo["papel"] == "admin" and storage.contar_admins(admin["org_id"]) <= 1:
        raise HTTPException(400, "a conta precisa de pelo menos um administrador")

    storage.encerrar_sessoes_do_usuario(usuario_id)
    storage.remover_usuario(admin["org_id"], usuario_id)
    auditar(request, admin, "usuario.removido", "usuario", usuario_id,
            {"email": alvo["email"]})
    return {"ok": True}


# ---------- Configurações da organização ----------

@router.get("/org/configuracoes")
async def ver_configuracoes(org: dict = Depends(organizacao_atual)):
    return {
        "nome": org["nome"],
        "retencao_dias": org["retencao_dias"],
        "retencao_min": RETENCAO_DIAS_MIN,
        "retencao_max": RETENCAO_DIAS_MAX,
    }


@router.put("/org/configuracoes")
async def salvar_configuracoes(dados: ConfigOrganizacao, request: Request,
                               admin: dict = Depends(admin_atual)):
    campos: dict = {}
    mudou: list[str] = []

    if dados.nome and dados.nome.strip():
        campos["nome"] = dados.nome.strip()
        mudou.append("nome")

    if dados.retencao_dias is not None:
        if not RETENCAO_DIAS_MIN <= dados.retencao_dias <= RETENCAO_DIAS_MAX:
            raise HTTPException(
                400,
                f"a retenção precisa ficar entre {RETENCAO_DIAS_MIN} e "
                f"{RETENCAO_DIAS_MAX} dias",
            )
        campos["retencao_dias"] = dados.retencao_dias
        mudou.append("retencao_dias")

    if campos:
        storage.atualizar_organizacao(admin["org_id"], **campos)
        auditar(request, admin, "organizacao.configurada", "organizacao",
                admin["org_id"], {"campos": mudou})

    org = storage.buscar_organizacao(admin["org_id"])
    return await ver_configuracoes(org)


@router.get("/org/conector")
async def conector(usuario: dict = Depends(usuario_atual)):
    """Se este usuário já ligou o Claude dele na conta.

    Não existe mais escolha de modo de avaliação: o conector é o único caminho.
    A interface usa isto só para decidir entre mostrar as instruções de ligar o
    Claude ou o painel de status de quem já ligou.
    """
    from .config import MCP_ATIVO

    conectores = len(storage.mcp_listar_tokens(usuario["usuario_id"], "pessoal"))
    conectores += len(storage.mcp_listar_tokens(usuario["usuario_id"], "acesso"))

    return {"conector_ativo": MCP_ATIVO, "conector_ligado": conectores > 0}
