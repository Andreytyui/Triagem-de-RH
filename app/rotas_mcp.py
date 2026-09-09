"""Tela de consentimento do conector e tokens pessoais.

Quando o Claude pede autorização, o SDK manda o usuário para cá. Esta página é
onde uma pessoa — logada na Triagem, com a sessão que ela já usa — decide se
autoriza. É o único ponto do fluxo OAuth que precisa de olho humano.
"""
from __future__ import annotations

import logging
import secrets
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from mcp.server.auth.provider import construct_redirect_uri
from pydantic import BaseModel, Field

from . import estilo, storage
from .config import APP_NOME, COOKIE_SESSAO, LOGIN_JANELA_MIN, LOGIN_MAX_TENTATIVAS
from .deps import auditar, ip_do, sessao_opcional, usuario_atual
from .mcp_oauth import criar_token_pessoal
from .security import conferir_senha, hash_token

log = logging.getLogger(__name__)
router = APIRouter(tags=["mcp"])


# ---------- Página de consentimento ----------

ESTILO = """
* { box-sizing:border-box; }
body { margin:0; min-height:100vh; display:grid; place-items:center; padding:2rem 1rem;
       background:var(--papel); color:var(--tinta);
       font:15px/1.55 "Instrument Sans", ui-sans-serif, system-ui, sans-serif; }
.caixa { width:100%; max-width:26rem; background:var(--painel);
         border:1px solid var(--regua); border-radius:3px; padding:2rem; }
h1 { font-size:1.25rem; margin:0 0 .35rem; letter-spacing:-.02em; }
p { margin:0 0 .9rem; }
.sub { color:var(--tinta-fraca); font-size:.9rem; }
.quem { padding:.75rem .9rem; margin:1.1rem 0; background:var(--papel);
        border-left:2px solid var(--petroleo); font-size:.9rem; }
ul { margin:.4rem 0 1.1rem; padding-left:1.1rem; font-size:.9rem; color:var(--tinta-fraca); }
li { margin-bottom:.25rem; }
label { display:block; margin-bottom:.9rem; font-size:.9rem; }
label span { display:block; margin-bottom:.3rem; font-weight:500; }
input { width:100%; padding:.6rem .75rem; font:inherit; background:var(--painel);
        border:1px solid var(--regua); border-radius:3px; }
input:focus { border-color:var(--petroleo); outline:none; }
.botoes { display:flex; gap:.75rem; margin-top:1.2rem; }
button { font:inherit; font-weight:500; padding:.65rem 1.3rem; border-radius:3px;
         cursor:pointer; border:1px solid transparent; }
.sim { color:var(--tinta-reversa); background:var(--petroleo); flex:1; }
.sim:hover { background:var(--petroleo-esc); }
.nao { color:var(--tinta-fraca); background:none; border-color:var(--regua); }
.erro { padding:.7rem; margin-bottom:1rem; font-size:.9rem;
        color:var(--tijolo); background:var(--tijolo-cl); border-radius:3px; }
.rodape { margin-top:1.3rem; padding-top:1rem; border-top:1px solid var(--regua);
          font-size:.8rem; color:var(--tinta-fraca); }
"""


def _pagina(titulo: str, corpo: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo)} — {escape(APP_NOME)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400..700&display=swap" rel="stylesheet">
<style>{estilo.folha()}{ESTILO}</style></head><body><div class="caixa">{corpo}</div></body></html>"""
    )


def _nome_do_cliente(client_id: str) -> str:
    dados = storage.mcp_buscar_cliente(client_id) or {}
    # Minúsculo e com artigo: assim serve tanto no título ("Autorizar o
    # aplicativo?") quanto no meio de frase, que é onde um "Um aplicativo"
    # capitalizado obrigava a reescrever o texto em volta.
    return dados.get("client_name") or "o aplicativo"


def _erro(mensagem: str) -> HTMLResponse:
    return _pagina("Não deu", f"""
        <h1>Não foi possível continuar</h1>
        <p class="sub">{escape(mensagem)}</p>
        <div class="rodape">Volte ao Claude e tente conectar o conector de novo.</div>""")


@router.get("/mcp/consentir", response_class=HTMLResponse)
async def consentir(request: Request, pedido: str = ""):
    ped = storage.mcp_buscar_pedido(pedido) if pedido else None
    if not ped:
        return _erro("este pedido de autorização não existe mais ou já venceu.")

    cliente = escape(_nome_do_cliente(ped["client_id"]))
    sessao = sessao_opcional(request)

    if not sessao:
        return _pagina("Entrar", f"""
            <h1>Entrar na Triagem</h1>
            <p class="sub">Entre para decidir se {cliente} pode acessar sua conta.</p>
            <form method="post" action="/mcp/consentir/entrar">
              <input type="hidden" name="pedido" value="{escape(pedido)}">
              <label><span>E-mail</span>
                <input type="email" name="email" autocomplete="username" required autofocus></label>
              <label><span>Senha</span>
                <input type="password" name="senha" autocomplete="current-password" required></label>
              <div class="botoes"><button class="sim" type="submit">Entrar</button></div>
            </form>""")

    org = storage.buscar_organizacao(sessao["org_id"])
    return _pagina("Autorizar", f"""
        <h1>Autorizar {cliente}?</h1>
        <p class="sub">Se você autorizar, o Claude vai poder, em seu nome:</p>
        <ul>
          <li>ver as vagas e os currículos <strong>anonimizados</strong> desta conta</li>
          <li>registrar avaliações, notas e decisões</li>
          <li>ver nome e contato de um candidato quando você pedir</li>
          <li>apagar dados de um candidato, se você confirmar</li>
        </ul>
        <div class="quem">
          Conectando como <strong>{escape(sessao['nome'])}</strong><br>
          {escape(sessao['email'])} · organização <strong>{escape(org['nome'] if org else '—')}</strong>
        </div>
        <form method="post" action="/mcp/consentir">
          <input type="hidden" name="pedido" value="{escape(pedido)}">
          <div class="botoes">
            <button class="sim" type="submit" name="decisao" value="sim">Autorizar</button>
            <button class="nao" type="submit" name="decisao" value="nao">Recusar</button>
          </div>
        </form>
        <div class="rodape">
          Tudo o que o conector fizer fica registrado na auditoria da conta, com
          seu nome. Você pode revogar o acesso a qualquer momento em Configurações.
        </div>""")


@router.post("/mcp/consentir/entrar", response_class=HTMLResponse)
async def consentir_entrar(request: Request, pedido: str = Form(""),
                           email: str = Form(""), senha: str = Form("")):
    if not storage.mcp_buscar_pedido(pedido):
        return _erro("este pedido de autorização não existe mais ou já venceu.")

    chave = f"{email.strip().lower()}|{ip_do(request)}"
    if storage.contar_tentativas(chave, LOGIN_JANELA_MIN) >= LOGIN_MAX_TENTATIVAS:
        return _erro(f"tentativas demais; espere {LOGIN_JANELA_MIN} minutos.")

    usuario = storage.buscar_usuario_por_email(email)
    if not usuario or not conferir_senha(senha, usuario["senha_hash"]) or not usuario["ativo"]:
        storage.registrar_tentativa(chave)
        return _pagina("Entrar", f"""
            <h1>Entrar na Triagem</h1>
            <p class="erro">E-mail ou senha incorretos.</p>
            <form method="post" action="/mcp/consentir/entrar">
              <input type="hidden" name="pedido" value="{escape(pedido)}">
              <label><span>E-mail</span>
                <input type="email" name="email" value="{escape(email)}" required autofocus></label>
              <label><span>Senha</span>
                <input type="password" name="senha" required></label>
              <div class="botoes"><button class="sim" type="submit">Entrar</button></div>
            </form>""")

    storage.limpar_tentativas(chave)
    resposta = RedirectResponse(f"/mcp/consentir?pedido={pedido}", status_code=303)

    from .rotas_auth import _abrir_sessao
    _abrir_sessao(resposta, request, usuario["id"])
    return resposta


@router.post("/mcp/consentir")
async def consentir_decidir(request: Request, pedido: str = Form(""),
                            decisao: str = Form("nao")):
    """A sessão é SameSite=Lax, então um POST de outro site não traz o cookie —
    é o que impede alguém de autorizar o conector no lugar do recrutador."""
    ped = storage.mcp_buscar_pedido(pedido)
    if not ped:
        return _erro("este pedido de autorização não existe mais ou já venceu.")

    sessao = sessao_opcional(request)
    if not sessao:
        return RedirectResponse(f"/mcp/consentir?pedido={pedido}", status_code=303)

    storage.mcp_consumir_pedido(pedido)

    if decisao != "sim":
        destino = construct_redirect_uri(
            ped["redirect_uri"], error="access_denied",
            error_description="o usuário recusou a autorização", state=ped["state"],
        )
        return RedirectResponse(destino, status_code=303)

    codigo = secrets.token_urlsafe(32)
    storage.mcp_criar_codigo(
        codigo=codigo, client_id=ped["client_id"], usuario_id=sessao["usuario_id"],
        redirect_uri=ped["redirect_uri"], redirect_explicito=ped["redirect_explicito"],
        code_challenge=ped["code_challenge"], scopes=ped["scopes"],
        recurso=ped["recurso"],
    )
    storage.registrar_auditoria(
        sessao["org_id"], sessao["usuario_id"], "mcp.autorizado", "conector",
        ped["client_id"], {"cliente": _nome_do_cliente(ped["client_id"])},
        ip=ip_do(request),
    )
    destino = construct_redirect_uri(
        ped["redirect_uri"], code=codigo, state=ped["state"]
    )
    return RedirectResponse(destino, status_code=303)


# ---------- Tokens pessoais (modo local, via stdio) ----------

class NovoTokenMCP(BaseModel):
    rotulo: str = Field(default="", max_length=60)


@router.get("/api/mcp/tokens")
async def listar_tokens(usuario: dict = Depends(usuario_atual)):
    return storage.mcp_listar_tokens(usuario["usuario_id"], "pessoal")


@router.post("/api/mcp/tokens", status_code=201)
async def criar_token(dados: NovoTokenMCP, request: Request,
                      usuario: dict = Depends(usuario_atual)):
    """Devolve o token em texto uma única vez — o banco guarda só o hash."""
    existentes = storage.mcp_listar_tokens(usuario["usuario_id"], "pessoal")
    if len(existentes) >= 5:
        raise HTTPException(400, "você já tem 5 tokens; revogue um antes de criar outro")

    token = criar_token_pessoal(
        usuario["usuario_id"], dados.rotulo.strip() or "Claude local"
    )
    auditar(request, usuario, "mcp.token_criado", "token", "",
            {"rotulo": dados.rotulo})
    return {
        "token": token,
        "aviso": "Copie agora. Este token não será mostrado de novo.",
    }


@router.delete("/api/mcp/tokens/{token_hash}")
async def revogar_token(token_hash: str, request: Request,
                        usuario: dict = Depends(usuario_atual)):
    dono = storage.mcp_buscar_token(token_hash)
    if not dono or dono["usuario_id"] != usuario["usuario_id"]:
        raise HTTPException(404, "token não encontrado")
    storage.mcp_apagar_token(token_hash)
    auditar(request, usuario, "mcp.token_revogado", "token", token_hash[:12])
    return {"ok": True}


@router.post("/api/mcp/desconectar")
async def desconectar_conectores(request: Request,
                                 usuario: dict = Depends(usuario_atual)):
    """Corta todos os conectores ligados a esta conta, inclusive o do claude.ai."""
    for tipo in ("acesso", "refresh"):
        storage.mcp_revogar_do_usuario(usuario["usuario_id"], tipo)
    auditar(request, usuario, "mcp.desconectado")
    return {"ok": True}


def _cookie_da_sessao(request: Request) -> Optional[str]:
    """Usado só pelos testes, para conferir que a sessão sobreviveu ao consentimento."""
    token = request.cookies.get(COOKIE_SESSAO)
    return hash_token(token) if token else None
