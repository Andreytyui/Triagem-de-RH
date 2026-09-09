"""Schemas do domínio. Também viram o input_schema das tools do conector —
fonte única de verdade para o que o Claude do recrutador pode mandar de volta."""
from __future__ import annotations

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

RECOMENDACOES = ("chamar", "talvez", "descartar")
DECISOES = ("sem_decisao", "entrevistar", "reserva", "arquivado")


def _slug(texto: str, reserva: str) -> str:
    limpo = re.sub(r"[^a-z0-9_]+", "_", (texto or "").strip().lower()).strip("_")
    return (limpo or reserva)[:40]


# ---------- Rubrica ----------

class Criterio(BaseModel):
    id: str = Field(description="slug curto e estável, ex: 'python_backend'")
    nome: str = Field(min_length=1, max_length=80)
    descricao: str = Field(description="o que conta como evidência forte para este critério")
    peso: int = Field(ge=0, le=100, description="peso relativo; a soma dos pesos deve dar 100")

    @field_validator("id")
    @classmethod
    def _id_valido(cls, v: str) -> str:
        return _slug(v, "criterio")


class RequisitoEliminatorio(BaseModel):
    id: str
    descricao: str = Field(description="condição objetiva, verificável no currículo")

    @field_validator("id")
    @classmethod
    def _id_valido(cls, v: str) -> str:
        return _slug(v, "eliminatorio")


class Rubrica(BaseModel):
    cargo: str
    senioridade: str
    eliminatorios: List[RequisitoEliminatorio] = []
    criterios: List[Criterio] = []
    observacoes: str = ""

    @model_validator(mode="after")
    def _ids_unicos(self) -> "Rubrica":
        """Id repetido faria duas notas colidirem no cálculo do score."""
        for colecao in (self.criterios, self.eliminatorios):
            vistos: set[str] = set()
            for i, item in enumerate(colecao):
                base = item.id
                while item.id in vistos:
                    item.id = f"{base}_{i}"
                    i += 1
                vistos.add(item.id)
        return self

    def peso_total(self) -> int:
        return sum(c.peso for c in self.criterios)

    def normalizar_pesos(self) -> None:
        """Pesos viram percentual somando 100. Todos zerados vira peso igual."""
        if not self.criterios:
            return
        total = self.peso_total()
        if total == 0:
            fatia = 100 // len(self.criterios)
            for c in self.criterios:
                c.peso = fatia
        elif total != 100:
            for c in self.criterios:
                c.peso = round(c.peso * 100 / total)
        sobra = 100 - sum(c.peso for c in self.criterios)
        if sobra:
            maior = max(self.criterios, key=lambda c: c.peso)
            maior.peso = max(0, maior.peso + sobra)


# ---------- Currículo estruturado ----------

class Experiencia(BaseModel):
    cargo: str
    empresa: str = ""
    inicio: str = Field(default="", description="AAAA-MM ou AAAA; vazio se ilegível")
    fim: str = Field(default="", description="AAAA-MM, AAAA ou 'atual'")
    descricao: str = ""


class Formacao(BaseModel):
    curso: str
    instituicao: str = ""
    nivel: str = Field(default="", description="técnico, tecnólogo, bacharelado, pós, mestrado…")
    conclusao: str = ""
    situacao: str = Field(default="", description="concluído, cursando ou trancado")


class Identificacao(BaseModel):
    """Dado pessoal. Fica guardado, mas NUNCA entra nos prompts de avaliação."""
    nome: str = ""
    email: str = ""
    telefone: str = ""
    cidade: str = ""
    links: List[str] = []


class PerfilAnonimo(BaseModel):
    """O único material que os estágios de avaliação enxergam."""
    resumo: str = Field(description="2 a 3 frases sobre a trajetória, sem nome nem contato")
    anos_experiencia_total: float = Field(default=0, ge=0, le=60)
    experiencias: List[Experiencia] = []
    formacoes: List[Formacao] = []
    habilidades: List[str] = []
    idiomas: List[str] = []
    certificacoes: List[str] = []
    trecho_bruto: str = Field(default="", description="texto do currículo já sem dados pessoais")


class CurriculoParseado(BaseModel):
    identificacao: Identificacao
    perfil: PerfilAnonimo


# ---------- Resultados ----------

class ResultadoPreFiltro(BaseModel):
    aprovado: bool
    eliminatorios_falhos: List[str] = Field(
        default=[], description="ids dos requisitos eliminatórios não atendidos"
    )
    justificativa: str = Field(description="uma frase, objetiva")


class NotaCriterio(BaseModel):
    criterio_id: str
    nota: int = Field(ge=0, le=10)
    evidencia: str = Field(
        description="trecho do currículo que sustenta a nota; "
                    "'sem evidência no currículo' se não houver"
    )


class ResultadoScore(BaseModel):
    criterios: List[NotaCriterio]
    red_flags: List[str] = []
    pontos_fortes: List[str] = []
    resumo: str = Field(description="2 linhas para o recrutador bater o olho")
    recomendacao: Literal["chamar", "talvez", "descartar"]
    confianca: Literal["alta", "media", "baixa"] = Field(
        default="alta",
        description="baixa quando o currículo é curto, genérico ou mal extraído, "
                    "e a avaliação depende mais de suposição que de evidência",
    )


# ---------- Entradas da API ----------

class NovaConta(BaseModel):
    organizacao: str = Field(min_length=2, max_length=120)
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str
    convite: str = ""


class Credenciais(BaseModel):
    email: EmailStr
    senha: str


class TrocaSenha(BaseModel):
    senha_atual: str
    senha_nova: str


class PedidoRecuperacao(BaseModel):
    email: EmailStr


class RedefinicaoSenha(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    senha: str


class NovoUsuario(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str
    papel: Literal["admin", "recrutador"] = "recrutador"


class ConfigOrganizacao(BaseModel):
    nome: Optional[str] = Field(default=None, max_length=120)
    retencao_dias: Optional[int] = None


class NovaVaga(BaseModel):
    titulo: str = Field(min_length=2, max_length=140)
    descricao: str = Field(min_length=40, max_length=20_000)


class DecisaoRecrutador(BaseModel):
    decisao: Literal["sem_decisao", "entrevistar", "reserva", "arquivado"]
    anotacao: str = Field(default="", max_length=4000)
