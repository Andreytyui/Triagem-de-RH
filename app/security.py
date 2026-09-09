"""Senha, sessão e CSRF.

Nada aqui inventa criptografia: PBKDF2-HMAC-SHA256 da biblioteca padrão, com os
parâmetros da recomendação OWASP.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import unicodedata
from typing import Optional

from .config import PBKDF2_ITERACOES, SENHA_MIN

_ALGO = "pbkdf2_sha256"


# ---------- Senha ----------

def _normalizar(senha: str) -> bytes:
    """NFKC evita que a mesma senha digitada em teclados diferentes falhe."""
    return unicodedata.normalize("NFKC", senha).encode("utf-8")


def hash_senha(senha: str, iteracoes: int = PBKDF2_ITERACOES) -> str:
    sal = secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac("sha256", _normalizar(senha), sal, iteracoes)
    sal_b64 = base64.b64encode(sal).decode()
    derivada_b64 = base64.b64encode(derivada).decode()
    return f"{_ALGO}${iteracoes}${sal_b64}${derivada_b64}"


def conferir_senha(senha: str, guardado: str) -> bool:
    try:
        algo, iteracoes, sal_b64, esperado_b64 = guardado.split("$")
        if algo != _ALGO:
            return False
        derivada = hashlib.pbkdf2_hmac(
            "sha256", _normalizar(senha), base64.b64decode(sal_b64), int(iteracoes)
        )
        return hmac.compare_digest(derivada, base64.b64decode(esperado_b64))
    except (ValueError, TypeError):
        return False


def criticar_senha(senha: str) -> Optional[str]:
    """Devolve o problema, ou None se a senha serve. Regra curta e defensável:
    tamanho manda mais que zoológico de símbolos."""
    if len(senha) < SENHA_MIN:
        return f"a senha precisa de pelo menos {SENHA_MIN} caracteres"
    if senha.lower() in _SENHAS_OBVIAS:
        return "essa senha é previsível demais"
    if len(set(senha)) < 5:
        return "a senha repete poucos caracteres diferentes"
    return None


_SENHAS_OBVIAS = {
    "senha123456", "1234567890", "12345678901", "qwertyuiop", "senhasenha",
    "administrador", "trocar123456", "recrutamento", "curriculos123",
}


# ---------- Sessão e CSRF ----------

def novo_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """O banco guarda só o hash: vazamento do banco não vira sessão válida."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def comparar(a: str, b: str) -> bool:
    return hmac.compare_digest(a or "", b or "")
