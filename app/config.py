"""Configuração central. Tudo que muda entre ambientes mora aqui."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

try:                                   # carrega .env sem exigir a dependência
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:                    # pragma: no cover
    pass


def _bool(nome: str, padrao: bool) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


def _int(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, "").strip() or padrao)
    except ValueError:
        return padrao


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("TRIAGEM_DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "triagem.db"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Identidade do produto (o comprador troca isto) ----------

APP_NOME = os.getenv("APP_NOME", "Triagem")
APP_VERSAO = "2.0"

# ---------- Segredo ----------
# Assina o cookie CSRF. Em produção precisa vir do ambiente: sem ele, cada
# reinício do servidor invalida as sessões abertas.

SECRET_KEY = os.getenv("TRIAGEM_SECRET_KEY", "")
SECRET_EFEMERO = not SECRET_KEY
if SECRET_EFEMERO:
    _arquivo = DATA_DIR / ".secret"
    if _arquivo.exists():
        SECRET_KEY = _arquivo.read_text(encoding="utf-8").strip()
        SECRET_EFEMERO = False
    else:
        SECRET_KEY = secrets.token_urlsafe(48)
        _arquivo.write_text(SECRET_KEY, encoding="utf-8")
        try:
            _arquivo.chmod(0o600)
        except OSError:                                        # pragma: no cover
            pass
        SECRET_EFEMERO = False

# ---------- Upload e extração ----------

MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 15)
MAX_ARQUIVOS_POR_LOTE = _int("MAX_ARQUIVOS_POR_LOTE", 30)

# Abaixo disso o PDF é considerado escaneado: não há texto embutido para ler.
# ATENÇÃO: este número tem DOIS trabalhos, e eles são perguntas diferentes.
#   1. no PDF, decide se o arquivo vai para a fila de OCR ("veio pouco texto,
#      provavelmente é escaneado");
#   2. em todos os formatos, é o piso de entrada ("abriu, mas não há currículo
#      aqui" — a linha de planilha do ATS que veio só com contato).
# Hoje o mesmo valor serve bem aos dois porque o vão medido no piloto é largo:
# 109, 116 e 131 caracteres de um lado, 358 do menor currículo real do outro.
# Se um dia isto for calibrado para o OCR, o piso de entrada muda junto — e em
# silêncio. Quem mexer aqui está mexendo em duas coisas.
MIN_CHARS_TEXTO_UTIL = 220
# Teto de caracteres do currículo enviado ao parser.
MAX_CHARS_CURRICULO = 24_000
# Páginas lidas de um PDF. Currículo passando disso é anexo, não currículo.
MAX_PAGINAS_PDF = 12

# ---------- OCR do PDF escaneado ----------
# Roda local, no Tesseract. Sem custo variável e sem nada saindo da máquina.

OCR_ATIVO = _bool("OCR_ATIVO", True)
OCR_IDIOMA = os.getenv("OCR_IDIOMA", "por")
# 300 DPI é onde o Tesseract acerta mais em papel digitalizado. Abaixo de 200 a
# taxa de erro sobe rápido; acima de 400 só custa tempo.
OCR_DPI = _int("OCR_DPI", 300)
# Confiança média (0 a 100) abaixo da qual o lote é marcado como leitura duvidosa.
OCR_CONFIANCA_MINIMA = _int("OCR_CONFIANCA_MINIMA", 75)
# Menos palavras que isto não é currículo lido, é ruído.
OCR_MIN_PALAVRAS = _int("OCR_MIN_PALAVRAS", 40)
# Leituras simultâneas. O OCR é preso a CPU: mais trabalhadores que núcleos
# úteis só faz a máquina brigar consigo mesma e travar quem está na tela.
OCR_TRABALHADORES = _int("OCR_TRABALHADORES", 2)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".rtf", ".csv", ".xlsx"}

# ---------- Contas, sessão e limites ----------

PERMITIR_CADASTRO = _bool("PERMITIR_CADASTRO", True)
CODIGO_CONVITE = os.getenv("CODIGO_CONVITE", "").strip()   # vazio = cadastro livre

SESSAO_HORAS = _int("SESSAO_HORAS", 12)
COOKIE_SEGURO = _bool("COOKIE_SEGURO", False)              # True atrás de HTTPS
COOKIE_SESSAO = "triagem_sessao"
COOKIE_CSRF = "triagem_csrf"

SENHA_MIN = 10
PBKDF2_ITERACOES = 600_000

LOGIN_MAX_TENTATIVAS = _int("LOGIN_MAX_TENTATIVAS", 8)
LOGIN_JANELA_MIN = _int("LOGIN_JANELA_MIN", 15)

# ---------- Recuperação de senha ----------
# Dois modos, porque são dois produtos de implantação diferentes:
#
# - 'email'  (padrão): o servidor manda um link. É o único caminho possível no
#            modo hospedado, onde o recrutador não tem acesso à máquina.
# - 'local': instalação na própria máquina, com Claude Desktop por stdio. Aqui
#            quem esqueceu a senha é dono do computador, e resolve com um
#            comando. Os endpoints de recuperação nem existem nesse modo — o que
#            não existe não pode ser atacado.

RECUPERACAO_MODO = os.getenv("RECUPERACAO_MODO", "email").strip().lower()
if RECUPERACAO_MODO not in {"email", "local"}:
    RECUPERACAO_MODO = "email"

# Curto de propósito: é um link que troca senha por e-mail.
RECUPERACAO_MINUTOS = _int("RECUPERACAO_MINUTOS", 30)
# Freio próprio. O login já tem o dele; sem este, /recuperar viraria ferramenta
# de descobrir quem tem conta e de bombardear a caixa de entrada de alguém.
RECUPERACAO_MAX_PEDIDOS = _int("RECUPERACAO_MAX_PEDIDOS", 5)
RECUPERACAO_JANELA_MIN = _int("RECUPERACAO_JANELA_MIN", 60)

# ---------- Envio de e-mail (SMTP) ----------
# Sem provedor no código: só host, porta e credencial. Vazio = o e-mail vai para
# o log do servidor, e o fluxo continua inteiro (útil em dev e em stdio).

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORTA = _int("SMTP_PORTA", 587)
SMTP_USUARIO = os.getenv("SMTP_USUARIO", "").strip()
SMTP_SENHA = os.getenv("SMTP_SENHA", "")
SMTP_TLS = _bool("SMTP_TLS", True)
SMTP_REMETENTE = os.getenv("SMTP_REMETENTE", "").strip()

# ---------- LGPD ----------

# Currículo é dado pessoal. Passado esse prazo sem uso, o expurgo apaga.
RETENCAO_DIAS_PADRAO = _int("RETENCAO_DIAS_PADRAO", 180)
RETENCAO_DIAS_MIN = 7
RETENCAO_DIAS_MAX = 1825
EXPURGO_INTERVALO_H = _int("EXPURGO_INTERVALO_H", 12)
AUDITORIA_RETENCAO_DIAS = _int("AUDITORIA_RETENCAO_DIAS", 730)

# ---------- Backup ----------
# O pior cenário do produto é perder o banco com currículo de várias empresas
# dentro. O artefato sai cifrado porque carrega dado pessoal de terceiros e o
# segredo que assina as sessões — cópia em claro num disco qualquer é
# comprometimento, não inconveniente.

BACKUP_ATIVO = _bool("BACKUP_ATIVO", True)
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", DATA_DIR.parent / "backups"))
BACKUP_INTERVALO_H = _int("BACKUP_INTERVALO_H", 24)

# Sem senha não há backup: o código recusa em vez de gerar um arquivo em claro.
BACKUP_SENHA = os.getenv("BACKUP_SENHA", "")

BACKUP_DIARIOS = _int("BACKUP_DIARIOS", 7)
BACKUP_SEMANAIS = _int("BACKUP_SEMANAIS", 4)

# Backup no mesmo disco do banco não é backup. Aqui vai o comando que leva o
# arquivo para fora — rclone, scp, aws s3, o que houver. `{arquivo}` é
# substituído pelo caminho do artefato recém-criado.
BACKUP_COMANDO_ENVIO = os.getenv("BACKUP_COMANDO_ENVIO", "").strip()

# ---------- Diagnóstico ----------

LOG_NIVEL = os.getenv("LOG_NIVEL", "INFO").upper()

# ---------- MCP (conector do Claude) ----------

# URL pública onde este servidor responde. O conector do Claude usa isto para
# descobrir os endpoints de OAuth, então precisa ser exatamente o endereço que
# o navegador do usuário alcança — inclusive o https e sem barra no fim.
BASE_URL = os.getenv("TRIAGEM_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

MCP_ATIVO = _bool("MCP_ATIVO", True)
MCP_CAMINHO = "/mcp"

# Validade do token que o conector recebe. O refresh renova sem novo login.
MCP_TOKEN_HORAS = _int("MCP_TOKEN_HORAS", 12)
MCP_REFRESH_DIAS = _int("MCP_REFRESH_DIAS", 30)
# Janela para o usuário concluir a autorização na tela de consentimento.
MCP_PEDIDO_MINUTOS = 10

# Quantos currículos o Claude pode puxar de uma vez pelo conector. Teto baixo de
# propósito: cada currículo ocupa contexto, e um lote grande degrada a avaliação.
MCP_LOTE_MAX = _int("MCP_LOTE_MAX", 5)

# Teto de caracteres por currículo entregue ao conector. É bem menor que o
# MAX_CHARS_CURRICULO guardado no banco, e por um motivo prático: um lote de 5
# currículos de 24 mil caracteres são ~30 mil tokens numa única resposta de
# ferramenta, e a conversa estoura antes de chegar aos 150 candidatos. O que é
# cortado fica no banco e continua visível na interface.
MCP_MAX_CHARS_CURRICULO = _int("MCP_MAX_CHARS_CURRICULO", 7000)

# ---------- Diagnóstico comparativo entre vizinhos ----------

# Duas perguntas diferentes, por isso duas variáveis: "quão perto é perto" e
# "até onde alguém ainda está comparando em vez de descartando".
#
# O 15 não é palpite: a confiabilidade entre avaliadores de uma mesma rubrica
# tem desvio-padrão de 11 a 17 pontos (dado levantado pela Bussola). O limiar
# existe para marcar onde a ordenação é frágil, e a ausência da linha afirma
# "não estão em disputa" — então ele tem de COBRIR a faixa de ruído, não parar
# antes dela: com limiar 10, dois candidatos separados por 13 pontos não
# ganhariam linha, e o produto afirmaria resolvida uma ordem que a própria
# medida não sustenta. 15 fica dentro da banda e perto do topo, do lado que
# erra mostrando em vez de escondendo — mostrar a mais custa três linhas de
# texto, esconder custa uma decisão tomada com falsa segurança.
#
# O TOPO não é afetado: responde outra pergunta, e o dado de confiabilidade
# não fala dela. Os dois seguem configuráveis porque o número pode estar
# errado — como o 10 estava.
COMPARACAO_LIMIAR = _int("COMPARACAO_LIMIAR", 15)   # diferença máxima, em pontos
COMPARACAO_TOPO = _int("COMPARACAO_TOPO", 10)       # até que posição a linha sai
