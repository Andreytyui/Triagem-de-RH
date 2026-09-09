"""Aplicação. Sobe com: uvicorn app.main:app

Este arquivo só monta as peças. A avaliação acontece fora, no Claude do próprio
recrutador, pelo conector MCP; o acesso a dados está em storage e o controle de
acesso em deps — aqui ficam as travas que precisam valer para toda requisição,
sem depender de lembrança.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import (
    backup,
    fila_ocr,
    retencao,
    rotas_auth,
    rotas_lgpd,
    rotas_mcp,
    rotas_vagas,
    storage,
)
from .config import (
    APP_NOME,
    APP_VERSAO,
    BASE_DIR,
    BASE_URL,
    CODIGO_CONVITE,
    COOKIE_CSRF,
    COOKIE_SEGURO,
    COOKIE_SESSAO,
    LOG_NIVEL,
    MAX_ARQUIVOS_POR_LOTE,
    MAX_UPLOAD_MB,
    MCP_ATIVO,
    MCP_CAMINHO,
    PERMITIR_CADASTRO,
    RECUPERACAO_MODO,
)
from .security import comparar, hash_token

logging.basicConfig(
    level=getattr(logging, LOG_NIVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("triagem")

ESTATICOS = BASE_DIR / "static"

# Métodos que mudam estado precisam do token anti-CSRF. As duas exceções são as
# rotas que ainda não têm sessão para conferir.
METODOS_INSEGUROS = {"POST", "PUT", "PATCH", "DELETE"}
SEM_CSRF = {"/api/auth/login", "/api/auth/registrar",
            "/api/auth/recuperar", "/api/auth/redefinir"}

# Teto de corpo: o lote inteiro de upload, com folga para o envelope multipart.
LIMITE_CORPO = (MAX_ARQUIVOS_POR_LOTE * MAX_UPLOAD_MB + 8) * 1024 * 1024


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    storage.iniciar()

    tarefas = [
        asyncio.create_task(retencao.rodar_periodicamente()),
        asyncio.create_task(backup.rodar_periodicamente()),
        # Lê os PDFs escaneados fora da requisição de upload, e recolhe no boot
        # o que tiver ficado pendente de uma queda anterior.
        asyncio.create_task(fila_ocr.rodar()),
    ]

    log.info("%s %s no ar", APP_NOME, APP_VERSAO)
    try:
        if MCP_ATIVO:
            # O gerenciador de sessão do MCP precisa viver junto com o servidor:
            # sem este bloco, o /mcp responde 500 na primeira conexão.
            from .mcp_servidor import gerenciador_de_sessao
            async with gerenciador_de_sessao().run():
                log.info("conector MCP em %s%s", BASE_URL, MCP_CAMINHO)
                yield
        else:
            yield
    finally:
        for tarefa in tarefas:
            tarefa.cancel()
            with contextlib.suppress(BaseException):
                await tarefa


app = FastAPI(
    title=f"{APP_NOME} — triagem de currículos",
    version=APP_VERSAO,
    lifespan=ciclo_de_vida,
    docs_url=None,                 # a documentação interativa não vai para produção
    redoc_url=None,
    openapi_url=None,
)


# ---------- Travas globais ----------

@app.middleware("http")
async def travas(request: Request, chamar_proximo):
    inicio = time.monotonic()

    tamanho = request.headers.get("content-length")
    if tamanho and tamanho.isdigit() and int(tamanho) > LIMITE_CORPO:
        return JSONResponse(
            {"detail": f"envio grande demais; no máximo {MAX_ARQUIVOS_POR_LOTE} "
                       f"arquivos de {MAX_UPLOAD_MB} MB por vez"},
            status_code=413,
        )

    caminho = request.url.path
    if (request.method in METODOS_INSEGUROS
            and caminho.startswith("/api/")
            and caminho not in SEM_CSRF):
        if not _csrf_ok(request):
            return JSONResponse(
                {"detail": "sessão inválida para esta ação; recarregue a página"},
                status_code=403,
            )

    resposta = await chamar_proximo(request)

    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    resposta.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resposta.headers.setdefault("Referrer-Policy", "same-origin")
    resposta.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "object-src 'self'; "
        "frame-ancestors 'self'; "
        "base-uri 'none'; "
        "form-action 'self'",
    )
    if COOKIE_SEGURO:
        resposta.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    # Currículo é dado pessoal: fora do cache de proxy e de navegador.
    if caminho.startswith("/api/"):
        resposta.headers.setdefault("Cache-Control", "no-store")

    duracao = (time.monotonic() - inicio) * 1000
    if duracao > 3000:
        log.info("%s %s levou %.0f ms", request.method, caminho, duracao)
    return resposta


def _csrf_ok(request: Request) -> bool:
    """Dupla submissão: o valor do cookie tem de voltar no cabeçalho. Um site
    de terceiros consegue disparar a requisição, mas não consegue ler o cookie."""
    if not request.cookies.get(COOKIE_SESSAO):
        return True                                   # sem sessão, o 401 resolve depois
    enviado = request.headers.get("x-csrf-token", "")
    if not enviado:
        return False
    sessao = storage.buscar_sessao(hash_token(request.cookies[COOKIE_SESSAO]))
    if not sessao:
        return True
    return comparar(enviado, sessao["csrf"]) and comparar(
        enviado, request.cookies.get(COOKIE_CSRF, "")
    )


@app.exception_handler(Exception)
async def erro_inesperado(request: Request, exc: Exception):
    """Nunca devolver stack trace ao cliente: ela conta a estrutura do servidor."""
    log.exception("erro não tratado em %s %s", request.method, request.url.path)
    return JSONResponse(
        {"detail": "erro interno; a equipe foi notificada pelo log do servidor"},
        status_code=500,
    )


@app.exception_handler(HTTPException)
async def erro_http(request: Request, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                        headers=getattr(exc, "headers", None))


CAMPOS_EM_PORTUGUES = {
    "email": "e-mail", "senha": "senha", "senha_nova": "nova senha",
    "senha_atual": "senha atual", "nome": "nome", "organizacao": "empresa",
    "titulo": "cargo", "descricao": "descrição", "peso": "peso",
    "retencao_dias": "retenção",
    "token": "código de recuperação", "convite": "código de convite",
    "papel": "papel", "decisao": "decisão", "anotacao": "anotação",
    "cargo": "cargo", "senioridade": "senioridade", "id": "identificador",
    "observacoes": "observações", "criterios": "critérios",
    "eliminatorios": "requisitos eliminatórios", "rotulo": "rótulo",
}

# Chaveado pelo `type` do Pydantic, não por trecho da mensagem: o texto das
# mensagens muda entre versões da biblioteca, e uma atualização quebraria a
# tradução em silêncio — o `type` é estável.
FRASES_DE_VALIDACAO = {
    "missing": "Falta preencher {rotulo}.",
    "string_too_short": "{Rotulo} precisa de pelo menos {min_length} caracteres.",
    "string_too_long": "{Rotulo} pode ter no máximo {max_length} caracteres.",
    "literal_error": "{Rotulo} não aceita esse valor.",
    "enum": "{Rotulo} não aceita esse valor.",
    "int_parsing": "{Rotulo} precisa ser um número.",
    "float_parsing": "{Rotulo} precisa ser um número.",
    "greater_than_equal": "{Rotulo} não pode ser menor que {ge}.",
    "less_than_equal": "{Rotulo} não pode ser maior que {le}.",
    "greater_than": "{Rotulo} precisa ser maior que {gt}.",
    "less_than": "{Rotulo} precisa ser menor que {lt}.",
    "string_type": "{Rotulo} veio num formato inesperado.",
    "int_type": "{Rotulo} veio num formato inesperado.",
    "float_type": "{Rotulo} veio num formato inesperado.",
    "bool_type": "{Rotulo} veio num formato inesperado.",
    "list_type": "{Rotulo} veio num formato inesperado.",
    "dict_type": "{Rotulo} veio num formato inesperado.",
}
FRASE_GENERICA = "Não foi possível validar {rotulo}."

# Sem prefixo de campo, e sem instruir "confira se tem @ e domínio": o validador
# também recusa domínio de uso especial bem formado (`@algo.local`), e essa
# instrução viraria beco sem saída para quem digitou certo.
EMAIL_RECUSADO = "Esse e-mail não foi aceito. Confira o endereço digitado."


def _campo_do_erro(erro: dict) -> str:
    return next((str(p) for p in reversed(erro.get("loc", ())) if isinstance(p, str)
                 and p not in ("body", "query", "path")), "")


def _frase_de_validacao(erro: dict) -> str:
    campo = _campo_do_erro(erro)
    rotulo = CAMPOS_EM_PORTUGUES.get(campo, campo) or "os dados enviados"
    contexto = erro.get("ctx") or {}

    # `reason` no contexto é como o EmailStr reporta — sinal estrutural, sem
    # depender de o campo se chamar "email". Premissa que sustenta isto: nenhum
    # validador nosso levanta ValueError, então todo `value_error` é de e-mail.
    # Se alguém acrescentar um `raise ValueError` com mensagem própria em
    # português, ela cai e este ramo precisa distinguir os dois casos.
    if erro.get("type") == "value_error" and "reason" in contexto:
        return EMAIL_RECUSADO

    modelo = FRASES_DE_VALIDACAO.get(erro.get("type", ""), FRASE_GENERICA)
    try:
        return modelo.format(rotulo=rotulo, Rotulo=rotulo[:1].upper() + rotulo[1:],
                             **contexto)
    except (KeyError, IndexError):
        # Versão nova do Pydantic pode renomear as chaves de contexto. Frase pior
        # é aceitável; 500 no meio do tratador de erro não é.
        return FRASE_GENERICA.format(rotulo=rotulo)


@app.exception_handler(RequestValidationError)
async def erro_validacao(request: Request, exc: RequestValidationError):
    """O 422 do Pydantic é uma lista de objetos em inglês. A tela precisa de frases."""
    # Um erro por campo, e a chave é o campo cru, não a frase: dois campos podem
    # compartilhar rótulo ("titulo" e "cargo" já compartilham), e deduplicar por
    # texto faria um deles sumir em silêncio se caíssem no mesmo corpo.
    partes: list[str] = []
    vistos: set[str] = set()
    for erro in exc.errors():
        campo = _campo_do_erro(erro)
        if campo in vistos:
            continue
        vistos.add(campo)
        partes.append(_frase_de_validacao(erro))
        if len(partes) == 3:
            break
    return JSONResponse(
        {"detail": " ".join(partes) or "Não foi possível validar os dados enviados."},
        status_code=422,
    )


# ---------- Rotas ----------

app.include_router(rotas_auth.router)
app.include_router(rotas_vagas.router)
app.include_router(rotas_lgpd.router)
app.include_router(rotas_mcp.router)


@app.get("/api/saude")
async def saude():
    """Para o monitoramento saber se vale a pena mandar tráfego."""
    try:
        storage.conexao().execute("SELECT 1").fetchone()
        banco = "ok"
    except Exception as exc:                                   # noqa: BLE001
        banco = f"falha: {exc}"
    return {
        "app": APP_NOME,
        "versao": APP_VERSAO,
        "banco": banco,
        "conector": MCP_ATIVO,
    }


@app.get("/api/config")
async def config_publica():
    """O que a tela de entrada precisa saber antes de haver sessão."""
    return {
        "app": APP_NOME,
        "versao": APP_VERSAO,
        "cadastro_aberto": PERMITIR_CADASTRO,
        "convite_exigido": bool(CODIGO_CONVITE),
        # A tela de entrada precisa saber isto antes de haver sessão: em 'local'
        # o link de "esqueci minha senha" leva à instrução do comando, e não a
        # um formulário que não teria para onde enviar.
        "recuperacao": RECUPERACAO_MODO,
    }


@app.get("/")
async def raiz():
    return FileResponse(ESTATICOS / "index.html")


app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")

# O app do MCP entra por último, montado inteiro: a autenticação dele vive em
# middleware do próprio app, então desmontá-lo rota a rota tiraria a proteção.
# Como o Starlette casa as rotas na ordem, tudo o que já foi declarado acima
# continua ganhando; sobram para ele o /mcp, o /authorize, o /token, o /register
# e os documentos de descoberta em /.well-known.
if MCP_ATIVO:
    from .mcp_servidor import construir_app
    app.mount("/", construir_app(), name="mcp")
