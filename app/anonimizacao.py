"""Separação de dado pessoal sem chamar modelo nenhum.

No funil da API, quem separa identificação de conteúdo profissional é o Haiku,
no estágio de parse. No fluxo por MCP não existe essa chamada: quem avalia é o
Claude do conector, e ele não pode receber o currículo com nome e telefone —
senão a proteção contra viés, que é metade do que se vende aqui, evapora.

Então a separação acontece por regra, aqui, antes de qualquer coisa sair do
servidor. É menos esperta que um modelo lendo o texto, e o módulo assume isso:
`confianca_baixa` avisa quando o nome não foi identificado com segurança, para
a interface poder dizer isso ao recrutador em vez de fingir garantia.

Texto vindo de OCR é um caso à parte, e mais perigoso. O OCR troca dígito por
letra parecida — "CPF: l23.456.789-O0" — e a regex de CPF não casa mais. O nome
sai em caixa alta, ou com um dígito no meio, e deixa de ser reconhecido. O
resultado seria o pior possível: o dado pessoal continua no texto e o sistema
acha que limpou. Por isso `separar(texto, de_ocr=True)` liga padrões tolerantes
a essa troca e, quando ainda assim não dá para garantir, **retém** o currículo:
ele não é entregue ao conector e o recrutador é avisado para mandar um arquivo
melhor. Reter é pior para o fluxo e melhor para a promessa — e a promessa é o
que se está vendendo.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# ---------- Padrões ----------

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", re.I)

# (81) 98812-4477 | 81 98812-4477 | +55 81 988124477 | 8198812447
TELEFONE = re.compile(
    r"(?:\+?55[\s.-]?)?"
    r"(?:\(?\d{2}\)?[\s.-]?)?"
    r"(?:9[\s.-]?)?\d{4}[\s.-]?\d{4}\b"
)

CPF = re.compile(r"\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?\d{2}\b")
RG = re.compile(r"\b(?:RG|R\.G\.|identidade)\s*:?\s*[\d.\-/]{5,15}\b", re.I)
CEP = re.compile(r"\b\d{5}[-\s]?\d{3}\b")
URL_PERFIL = re.compile(
    r"\b(?:https?://)?(?:www\.)?"
    r"(?:linkedin\.com|github\.com|gitlab\.com|behance\.net|lattes\.cnpq\.br)"
    r"/[\w\-/.%]+", re.I,
)
NASCIMENTO = re.compile(
    r"(?:data\s+de\s+)?nascimento\s*:?\s*\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}", re.I
)
IDADE = re.compile(r"\b\d{2}\s*anos\s*(?:de\s*idade)?\b", re.I)
ESTADO_CIVIL = re.compile(
    r"\b(?:estado\s+civil\s*:?\s*)?"
    r"(?:solteir[oa]|casad[oa]|divorciad[oa]|viúv[oa]|viuv[oa]|"
    r"uni[aã]o\s+est[aá]vel)\b", re.I,
)
FILHOS = re.compile(r"\b(?:possui\s+)?(?:\d+\s+)?filh[oa]s?\b[^.\n]{0,40}", re.I)

# Palavras que aparecem em cabeçalho de currículo e não são nome de pessoa.
NAO_E_NOME = {
    "curriculo", "currículo", "curriculum", "vitae", "cv", "resumo", "profissional",
    "dados", "pessoais", "contato", "objetivo", "perfil", "experiencia", "experiência",
    "formacao", "formação", "analista", "assistente", "tecnico", "técnico", "auxiliar",
    "coordenador", "gerente", "desenvolvedor", "engenheiro", "estagiario", "estagiário",
    "especialista", "consultor", "supervisor", "senior", "sênior", "pleno", "junior",
    "júnior", "de", "da", "do", "em", "e",
}

# Partículas que fazem parte de nome brasileiro e não contam como palavra "forte".
PARTICULAS = {"de", "da", "do", "das", "dos", "e", "van", "von", "del", "di", "la"}

MARCA = "[candidato]"

# ---------- Ruído de OCR ----------
# O Tesseract confunde dígito com letra de forma previsível. Estas classes
# aceitam o dígito e os sósias dele, e só entram em texto vindo de OCR: num
# currículo com texto embutido elas só serviriam para gerar falso positivo.

_D = r"[0-9OoQDlIiZzSsGbBTtgq|!]"          # um dígito, ou algo que o OCR leu como um
_SEP = r"[.\s,\-]?"

CPF_OCR = re.compile(rf"\b{_D}{{3}}{_SEP}{_D}{{3}}{_SEP}{_D}{{3}}[-.\s]?{_D}{{2}}\b")
TELEFONE_OCR = re.compile(
    rf"(?:\+?{_D}{{2}}[\s.-]?)?"
    rf"(?:\(?{_D}{{2}}\)?[\s.-]?)?"
    rf"(?:9[\s.-]?)?{_D}{{4}}[\s.-]?{_D}{{4}}\b"
)
CEP_OCR = re.compile(rf"\b{_D}{{5}}[-\s]?{_D}{{3}}\b")

# O OCR também estraga o e-mail: "joao@exemplo. com", "joao(a)exemplo.com".
EMAIL_OCR = re.compile(
    r"\b[\w.+-]+\s*(?:@|\(a\)|\[a\])\s*[\w-]+\s*\.\s*[\w.-]+\b", re.I
)


@dataclass
class Separacao:
    """O que saiu do currículo, e o que sobrou dele."""
    nome: str = ""
    email: str = ""
    telefone: str = ""
    cidade: str = ""
    links: list[str] = field(default_factory=list)
    texto_anonimo: str = ""
    confianca_baixa: bool = False
    de_ocr: bool = False
    retido: bool = False
    motivo_retencao: str = ""
    avisos: list[str] = field(default_factory=list)

    def identificacao(self) -> dict:
        return {
            "nome": self.nome, "email": self.email, "telefone": self.telefone,
            "cidade": self.cidade, "links": self.links,
        }


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _parece_nome(linha: str, de_ocr: bool = False) -> bool:
    """Nome de pessoa: 2 a 5 palavras capitalizadas, sem dígito, sem cargo.

    Vindo de OCR, um dígito solto no meio da linha é ruído de leitura, não sinal
    de que aquilo não é um nome — "J0ão da Silva" continua sendo o nome da
    pessoa, e não reconhecê-lo é justamente o que faz o nome vazar. Então a
    regra do dígito afrouxa: barra só quando há dígito demais para ser engano.
    """
    linha = linha.strip(" \t-–—•|")
    if not (4 <= len(linha) <= 70):
        return False
    if sum(c.isdigit() for c in linha) > (2 if de_ocr else 0):
        return False
    if "@" in linha or "/" in linha or ":" in linha:
        return False

    palavras = linha.split()
    if not 2 <= len(palavras) <= 5:
        return False

    fortes = [p for p in palavras if _sem_acento(p).lower() not in PARTICULAS]
    if len(fortes) < 2:
        return False
    if any(_sem_acento(p).lower() in NAO_E_NOME for p in fortes):
        return False
    # Todas as palavras fortes começam com maiúscula (ou o currículo está em caixa alta).
    return all(p[:1].isupper() for p in fortes)


# Planilha de ATS vira "Nome: Fulano de Tal" — o rótulo é a pista mais confiável
# que existe, e sem ele o nome passava batido para dentro do texto anonimizado.
NOME_ROTULADO = re.compile(
    r"^\s*(?:nome(?:\s+completo)?|nome\s+do\s+candidato|candidato|candidate|"
    r"name|full\s+name)\s*[:\-]\s*(.+)$",
    re.I | re.M,
)


def _achar_nome(texto: str, de_ocr: bool = False) -> tuple[str, bool]:
    """Devolve (nome, achou_com_seguranca). Olha só o topo do documento."""
    rotulado = NOME_ROTULADO.search(texto)
    if rotulado:
        candidato = rotulado.group(1).strip(" \t-–—•|")
        digitos = sum(c.isdigit() for c in candidato)
        if 3 <= len(candidato) <= 70 and digitos <= (2 if de_ocr else 0):
            return candidato, True

    linhas = [l.strip() for l in texto.splitlines()[:12] if l.strip()]
    for linha in linhas[:6]:
        if _parece_nome(linha, de_ocr):
            return linha.strip(" \t-–—•|"), True
    return "", False


def _achar_cidade(texto: str) -> str:
    achado = re.search(
        r"\b([A-ZÁÂÃÉÊÍÓÔÕÚÇ][\wÀ-ÿ'\-]+(?:\s+[A-ZÁÂÃÉÊÍÓÔÕÚÇ][\wÀ-ÿ'\-]+){0,2})"
        r"\s*[-–/,]\s*(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|"
        r"RS|RO|RR|SC|SP|SE|TO)\b",
        texto[:1200],
    )
    return f"{achado.group(1)}, {achado.group(2)}" if achado else ""


def _variacoes_do_nome(nome: str) -> list[str]:
    """O nome aparece inteiro, só o primeiro, ou primeiro + último."""
    partes = [p for p in nome.split() if _sem_acento(p).lower() not in PARTICULAS]
    if not partes:
        return []
    variacoes = {nome}
    if len(partes) >= 2:
        variacoes.add(" ".join(partes))
        variacoes.add(f"{partes[0]} {partes[-1]}")
    variacoes.add(partes[0])                       # o primeiro nome, sozinho
    # Do mais longo para o mais curto: senão o primeiro nome come o nome inteiro.
    return sorted(variacoes, key=len, reverse=True)


def separar(texto: str, de_ocr: bool = False) -> Separacao:
    """Tira o dado pessoal do texto e devolve os dois lados.

    `de_ocr=True` liga os padrões tolerantes ao ruído de leitura e a política de
    retenção: sem certeza sobre o nome, o currículo não sai daqui.
    """
    resultado = Separacao(de_ocr=de_ocr)
    if not texto or not texto.strip():
        resultado.avisos.append("currículo sem texto")
        resultado.confianca_baixa = True
        return resultado

    emails = EMAIL.findall(texto)
    resultado.email = emails[0] if emails else ""
    resultado.links = list(dict.fromkeys(URL_PERFIL.findall(texto)))[:5]
    resultado.cidade = _achar_cidade(texto)

    nome, seguro = _achar_nome(texto, de_ocr)
    resultado.nome = nome
    if not seguro:
        resultado.confianca_baixa = True
        resultado.avisos.append(
            "não identifiquei o nome no topo do currículo; o texto pode ter sobrado "
            "com o nome da pessoa"
        )

    telefones = TELEFONE.findall(texto)
    resultado.telefone = telefones[0].strip() if telefones else ""

    # Contatos primeiro: assim "mariana.vasques@exemplo.com" vira "[e-mail]"
    # inteiro, em vez de virar "[candidato].[e-mail]" com o nome já mordido.
    anonimo = texto
    for padrao, substituto in (
        (URL_PERFIL, "[perfil]"),
        (EMAIL, "[e-mail]"),
        (CPF, "[cpf]"),
        (RG, "[documento]"),
        (NASCIMENTO, "[nascimento]"),
        (CEP, "[cep]"),
        (TELEFONE, "[telefone]"),
        (IDADE, "[idade]"),
        (ESTADO_CIVIL, "[estado civil]"),
        (FILHOS, "[situação familiar]"),
    ):
        anonimo = padrao.sub(substituto, anonimo)

    # Segunda passada, só para texto de OCR: pega o que a troca de dígito por
    # letra escondeu da primeira. Fora do OCR estes padrões não entram, porque
    # num texto limpo eles casariam com coisa que não é dado pessoal.
    if de_ocr:
        for padrao, substituto in (
            (EMAIL_OCR, "[e-mail]"),
            (CPF_OCR, "[cpf]"),
            (CEP_OCR, "[cep]"),
            (TELEFONE_OCR, "[telefone]"),
        ):
            anonimo = padrao.sub(substituto, anonimo)

    # O nome depois, do mais longo para o mais curto.
    if nome:
        for variacao in _variacoes_do_nome(nome):
            if len(variacao) >= 3:
                anonimo = re.sub(
                    rf"\b{re.escape(variacao)}\b", MARCA, anonimo, flags=re.I
                )
        # "Nome: [candidato]" ainda anuncia que ali havia um nome; some com o rótulo.
        anonimo = NOME_ROTULADO.sub(f"Nome: {MARCA}", anonimo)

    # Sobrou algo com cara de contato? Melhor avisar que fingir que está limpo.
    sobrou_contato = bool(EMAIL.search(anonimo) or CPF.search(anonimo))
    if de_ocr:
        sobrou_contato = sobrou_contato or bool(
            EMAIL_OCR.search(anonimo) or CPF_OCR.search(anonimo)
        )
    if sobrou_contato:
        resultado.confianca_baixa = True
        resultado.avisos.append("pode ter restado dado de contato no texto anonimizado")

    resultado.texto_anonimo = re.sub(r"\n{3,}", "\n\n", anonimo).strip()

    # A regra dura do OCR. Em texto limpo, não achar o nome vira aviso e o
    # currículo segue — o texto é fiel e a chance de sobrar identificação é
    # pequena. Em texto de OCR não dá para assumir isso: o que o detector não
    # reconheceu pode estar inteiro no meio do texto, e quem recebe é justamente
    # quem não pode ver. Então aqui o currículo fica retido, e o recrutador é
    # avisado de que precisa de um arquivo melhor.
    if de_ocr:
        if not seguro:
            resultado.retido = True
            resultado.motivo_retencao = (
                "não foi possível identificar o nome com segurança no texto "
                "escaneado, então não dá para garantir que ele foi removido; "
                "revise o arquivo ou envie uma versão com texto"
            )
        elif sobrou_contato:
            resultado.retido = True
            resultado.motivo_retencao = (
                "sobrou dado de contato no texto extraído por OCR; "
                "revise o arquivo ou envie uma versão com texto"
            )

    return resultado


def perfil_anonimo(texto: str, de_ocr: bool = False) -> dict:
    """Monta o `PerfilAnonimo` no formato que o resto do sistema já entende."""
    sep = separar(texto, de_ocr)
    return {
        "resumo": "",
        "anos_experiencia_total": 0,
        "experiencias": [], "formacoes": [], "habilidades": [],
        "idiomas": [], "certificacoes": [],
        "trecho_bruto": sep.texto_anonimo,
    }


def parse_deterministico(texto: str, de_ocr: bool = False) -> tuple[dict, Separacao]:
    """Devolve algo com a mesma forma do parse por IA, sem gastar um token."""
    sep = separar(texto, de_ocr)
    return {
        "identificacao": sep.identificacao(),
        "retido": sep.retido,
        "motivo_retencao": sep.motivo_retencao,
        "perfil": {
            "resumo": "",
            "anos_experiencia_total": 0,
            "experiencias": [], "formacoes": [], "habilidades": [],
            "idiomas": [], "certificacoes": [],
            "trecho_bruto": sep.texto_anonimo,
        },
    }, sep
