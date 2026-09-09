"""OAuth para o conector do Claude.

O conector de claude.ai não aceita uma chave colada à mão: ele descobre os
endpoints, registra-se sozinho e conduz o usuário por um login. Então o servidor
precisa ser, ele mesmo, um autorizador OAuth — é o que este módulo faz.

O SDK do MCP cuida do protocolo (descoberta, PKCE, formato das respostas). Aqui
fica o que é nosso: onde os códigos e tokens moram, e quem é o dono de cada um.
A tela de consentimento reaproveita a sessão normal da Triagem, então autorizar
o Claude é o mesmo login que o recrutador já usa — não há segunda senha.

O token de acesso guarda só o hash no banco, igual à sessão web: vazar o banco
não entrega acesso a conta nenhuma.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from . import storage
from .config import (
    BASE_URL,
    MCP_PEDIDO_MINUTOS,
    MCP_REFRESH_DIAS,
    MCP_TOKEN_HORAS,
)
from .security import hash_token, novo_token

log = logging.getLogger(__name__)

ESCOPO_TRIAGEM = "triagem"
ESCOPOS = [ESCOPO_TRIAGEM]


def _instante(quando: Optional[str]) -> Optional[int]:
    if not quando:
        return None
    return int(datetime.fromisoformat(quando).timestamp())


class AutorizadorTriagem(OAuthAuthorizationServerProvider):
    """Autorizador OAuth apoiado no mesmo SQLite do resto do sistema."""

    # ---------- Clientes ----------

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        dados = storage.mcp_buscar_cliente(client_id)
        if not dados:
            return None
        try:
            return OAuthClientInformationFull.model_validate(dados)
        except Exception:                                      # noqa: BLE001
            log.warning("cliente MCP %s com dados ilegíveis; ignorando", client_id)
            return None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Registro dinâmico: o Claude se apresenta sozinho na primeira conexão."""
        storage.mcp_salvar_cliente(
            client_info.client_id, client_info.model_dump(mode="json", exclude_none=True)
        )
        log.info("conector MCP registrado: %s (%s)",
                 client_info.client_id, client_info.client_name or "sem nome")

    # ---------- Autorização ----------

    async def authorize(self, client: OAuthClientInformationFull,
                        params: AuthorizationParams) -> str:
        """Devolve para onde mandar o usuário. Aqui é a nossa tela de consentimento:
        quem decide autorizar é a pessoa logada, não o cliente OAuth."""
        pedido_id = uuid.uuid4().hex
        storage.mcp_criar_pedido(
            pedido_id=pedido_id,
            client_id=client.client_id,
            redirect_uri=str(params.redirect_uri),
            redirect_explicito=params.redirect_uri_provided_explicitly,
            code_challenge=params.code_challenge,
            state=params.state,
            scopes=params.scopes or ESCOPOS,
            recurso=params.resource,
            minutos=MCP_PEDIDO_MINUTOS,
        )
        return f"{BASE_URL}/mcp/consentir?pedido={pedido_id}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        dados = storage.mcp_buscar_codigo(authorization_code)
        if not dados or dados["client_id"] != client.client_id:
            return None
        return AuthorizationCode(
            code=dados["codigo"],
            scopes=dados["scopes"],
            expires_at=_instante(dados["expira_em"]) or 0,
            client_id=dados["client_id"],
            code_challenge=dados["code_challenge"],
            redirect_uri=dados["redirect_uri"],
            redirect_uri_provided_explicitly=dados["redirect_explicito"],
            resource=dados["recurso"],
            subject=dados["usuario_id"],
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        # Busca e apaga como uma operação atômica só (uso único: se o mesmo
        # código voltar, alguém o interceptou) — ver storage.mcp_consumir_codigo.
        dados = storage.mcp_consumir_codigo(authorization_code.code)
        if not dados:
            raise ValueError("código de autorização inválido ou vencido")

        return self._emitir(
            usuario_id=dados["usuario_id"],
            client_id=client.client_id,
            scopes=dados["scopes"],
            recurso=dados["recurso"],
        )

    # ---------- Tokens ----------

    def _emitir(self, usuario_id: str, client_id: str, scopes: list[str],
                recurso: Optional[str]) -> OAuthToken:
        acesso = novo_token()
        refresh = novo_token()
        agora = datetime.now(timezone.utc)
        vence_acesso = agora + timedelta(hours=MCP_TOKEN_HORAS)
        vence_refresh = agora + timedelta(days=MCP_REFRESH_DIAS)

        storage.mcp_criar_token(
            hash_token(acesso), "acesso", usuario_id, client_id, scopes, recurso,
            rotulo="conector Claude", expira_em=vence_acesso.isoformat(),
        )
        storage.mcp_criar_token(
            hash_token(refresh), "refresh", usuario_id, client_id, scopes, recurso,
            rotulo="conector Claude", expira_em=vence_refresh.isoformat(),
        )
        return OAuthToken(
            access_token=acesso,
            token_type="Bearer",
            expires_in=MCP_TOKEN_HORAS * 3600,
            scope=" ".join(scopes),
            refresh_token=refresh,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        """Aceita o token do OAuth e também o token pessoal gerado na tela de
        Configurações — os dois moram na mesma tabela, com tipos diferentes."""
        dados = storage.mcp_buscar_token(hash_token(token))
        if not dados or dados["tipo"] not in ("acesso", "pessoal"):
            return None
        storage.mcp_marcar_uso(hash_token(token))
        return AccessToken(
            token=token,
            client_id=dados["client_id"] or "token-pessoal",
            scopes=dados["scopes"] or ESCOPOS,
            expires_at=_instante(dados["expira_em"]),
            resource=dados["recurso"],
            subject=dados["usuario_id"],
            claims={"org_id": dados["org_id"], "papel": dados["papel"],
                    "nome": dados["nome"], "email": dados["email"]},
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        dados = storage.mcp_buscar_token(hash_token(refresh_token), tipo="refresh")
        if not dados or dados["client_id"] != client.client_id:
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=dados["client_id"],
            scopes=dados["scopes"] or ESCOPOS,
            expires_at=_instante(dados["expira_em"]),
            resource=dados["recurso"],
            subject=dados["usuario_id"],
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        # Rotação: busca e apaga como uma operação atômica só, senão um refresh
        # token roubado usado ao mesmo tempo pelo dono e pelo atacante sairia
        # válido para os dois — ver storage.mcp_consumir_token.
        dados = storage.mcp_consumir_token(hash_token(refresh_token.token), "refresh")
        if not dados:
            raise ValueError("refresh token inválido ou vencido")
        return self._emitir(
            usuario_id=dados["usuario_id"],
            client_id=client.client_id,
            scopes=scopes or dados["scopes"] or ESCOPOS,
            recurso=dados["recurso"],
        )

    async def revoke_token(self, token) -> None:
        alvo = getattr(token, "token", None)
        if alvo:
            storage.mcp_apagar_token(hash_token(alvo))

    async def exchange_identity_assertion(self, client, params) -> OAuthToken:
        raise NotImplementedError(
            "este servidor não aceita troca por asserção de identidade"
        )


# ---------- Token pessoal (para uso local, via stdio) ----------

def criar_token_pessoal(usuario_id: str, rotulo: str, dias: int = 365) -> str:
    """Token que o usuário cola na configuração do Claude Desktop ou do Claude
    Code. Devolvido em texto uma única vez — o banco guarda só o hash."""
    token = novo_token()
    vence = datetime.now(timezone.utc) + timedelta(days=dias)
    storage.mcp_criar_token(
        hash_token(token), "pessoal", usuario_id, client_id=None,
        scopes=ESCOPOS, rotulo=rotulo[:60] or "sem rótulo",
        expira_em=vence.isoformat(),
    )
    return token


def contexto_do_token(token: str) -> Optional[dict]:
    """Usado pelo transporte stdio, que não passa pelo middleware HTTP."""
    dados = storage.mcp_buscar_token(hash_token(token))
    if not dados or dados["tipo"] not in ("acesso", "pessoal"):
        return None
    return {
        "usuario_id": dados["usuario_id"], "org_id": dados["org_id"],
        "papel": dados["papel"], "nome": dados["nome"], "email": dados["email"],
    }
