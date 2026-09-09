"""Envio de e-mail. Um provedor nenhum, uma configuração só.

O produto precisa mandar e-mail para uma coisa em particular — recuperação de
senha no modo hospedado, onde o recrutador não tem acesso ao servidor para rodar
comando nenhum. Isso é bloqueador de venda, e não podia ficar esperando decisão
de provedor.

Então aqui não existe SDK de ninguém: é SMTP puro da biblioteca padrão,
configurado por variável de ambiente. Trocar de provedor é trocar quatro
variáveis, sem tocar em código.

Sem SMTP configurado, o modo `stub` escreve a mensagem inteira no log do servidor
em vez de enviar. Não é enfeite de desenvolvimento: é o que permite testar o
fluxo de ponta a ponta antes de existir domínio, e é o que faz uma instalação
local funcionar sem obrigar ninguém a ter servidor de e-mail.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from .config import (
    APP_NOME,
    SMTP_HOST,
    SMTP_PORTA,
    SMTP_REMETENTE,
    SMTP_SENHA,
    SMTP_TLS,
    SMTP_USUARIO,
)

log = logging.getLogger(__name__)


def configurado() -> bool:
    """Há relay de verdade? Se não, o envio cai no log."""
    return bool(SMTP_HOST)


def enviar(destino: str, assunto: str, corpo: str) -> bool:
    """Manda a mensagem. Devolve se saiu de fato; nunca levanta exceção.

    Falha de envio não pode derrubar a rota que chamou: do lado de quem pediu a
    recuperação, a resposta é a mesma de qualquer jeito — e tem que ser, senão o
    tempo de resposta passa a dizer quem tem conta neste servidor.
    """
    if not configurado():
        log.warning(
            "[correio: sem SMTP configurado, a mensagem vai para o log]\n"
            "para: %s\nassunto: %s\n%s", destino, assunto, corpo
        )
        return False

    mensagem = EmailMessage()
    mensagem["From"] = SMTP_REMETENTE or f"{APP_NOME} <nao-responda@localhost>"
    mensagem["To"] = destino
    mensagem["Subject"] = assunto
    mensagem.set_content(corpo)

    try:
        if SMTP_PORTA == 465:                                  # SMTPS, TLS desde o início
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORTA, timeout=20,
                                  context=ssl.create_default_context()) as servidor:
                _autenticar(servidor)
                servidor.send_message(mensagem)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORTA, timeout=20) as servidor:
                if SMTP_TLS:
                    servidor.starttls(context=ssl.create_default_context())
                _autenticar(servidor)
                servidor.send_message(mensagem)
    except Exception as exc:                                   # noqa: BLE001
        log.error("falha ao enviar e-mail para %s: %s", destino, exc)
        return False

    log.info("e-mail enviado para %s (%s)", destino, assunto)
    return True


def _autenticar(servidor: smtplib.SMTP) -> None:
    if SMTP_USUARIO:
        servidor.login(SMTP_USUARIO, SMTP_SENHA)
