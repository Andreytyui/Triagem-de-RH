"""SQLite. Duas coisas importam aqui.

A primeira é o isolamento: toda consulta é filtrada por `org_id`. Currículo de
uma empresa não existe para outra, nem quando o mesmo PDF é enviado nas duas.

A segunda é o cache de parse: um currículo é parseado uma vez por organização,
nunca de novo — é o que faz reprocessar uma vaga sair quase de graça.
"""
from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from .config import (
    AUDITORIA_RETENCAO_DIAS,
    DATA_DIR,
    DB_PATH,
    RETENCAO_DIAS_PADRAO,
)

log = logging.getLogger(__name__)

_local = threading.local()
_escrita = threading.Lock()          # SQLite aceita um escritor por vez
VERSAO_ESQUEMA = 7

UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS organizacoes (
    id            TEXT PRIMARY KEY,
    nome          TEXT NOT NULL,
    retencao_dias INTEGER NOT NULL,
    ativa         INTEGER NOT NULL DEFAULT 1,
    criada_em     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usuarios (
    id            TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES organizacoes(id) ON DELETE CASCADE,
    email         TEXT NOT NULL UNIQUE,
    nome          TEXT NOT NULL,
    senha_hash    TEXT NOT NULL,
    papel         TEXT NOT NULL DEFAULT 'recrutador',
    ativo         INTEGER NOT NULL DEFAULT 1,
    criado_em     TEXT NOT NULL,
    ultimo_acesso TEXT
);

CREATE TABLE IF NOT EXISTS sessoes (
    token_hash TEXT PRIMARY KEY,
    usuario_id TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    csrf       TEXT NOT NULL,
    criada_em  TEXT NOT NULL,
    expira_em  TEXT NOT NULL,
    ip         TEXT,
    agente     TEXT
);

CREATE TABLE IF NOT EXISTS tentativas_login (
    chave TEXT NOT NULL,
    em    TEXT NOT NULL
);

-- Pedido de recuperação de senha. O banco guarda só o hash do token: vazamento
-- do banco não vira link válido, do mesmo jeito que não vira sessão.
CREATE TABLE IF NOT EXISTS recuperacoes (
    token_hash TEXT PRIMARY KEY,
    usuario_id TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    criado_em  TEXT NOT NULL,
    expira_em  TEXT NOT NULL,
    usado_em   TEXT,
    ip         TEXT
);

CREATE TABLE IF NOT EXISTS vagas (
    id            TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES organizacoes(id) ON DELETE CASCADE,
    titulo        TEXT NOT NULL,
    descricao     TEXT NOT NULL,
    rubrica       TEXT,
    rubrica_ok    INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'rascunho',
    erro          TEXT,
    arquivada     INTEGER NOT NULL DEFAULT 0,
    criada_por    TEXT,
    criada_em     TEXT NOT NULL,
    atualizada_em TEXT
);

CREATE TABLE IF NOT EXISTS curriculos (
    org_id        TEXT NOT NULL REFERENCES organizacoes(id) ON DELETE CASCADE,
    candidato_id  TEXT NOT NULL,
    arquivo       TEXT NOT NULL,
    origem        TEXT NOT NULL DEFAULT 'arquivo',
    origem_hash   TEXT,
    extensao      TEXT,
    escaneado     INTEGER NOT NULL DEFAULT 0,
    origem_texto  TEXT NOT NULL DEFAULT 'direto',
    ocr_confianca TEXT,
    -- pronto | pendente | falhou. 'pendente' é o escaneado esperando o OCR da
    -- fila; enquanto está assim ele conta como pendente, nunca como falha.
    estado_extracao TEXT NOT NULL DEFAULT 'pronto',
    texto         TEXT,
    parse         TEXT,
    avisos        TEXT,
    criado_em     TEXT NOT NULL,
    PRIMARY KEY (org_id, candidato_id)
);

CREATE TABLE IF NOT EXISTS vaga_curriculos (
    vaga_id      TEXT NOT NULL REFERENCES vagas(id) ON DELETE CASCADE,
    candidato_id TEXT NOT NULL,
    PRIMARY KEY (vaga_id, candidato_id)
);

CREATE TABLE IF NOT EXISTS avaliacoes (
    vaga_id      TEXT NOT NULL REFERENCES vagas(id) ON DELETE CASCADE,
    candidato_id TEXT NOT NULL,
    estagio      TEXT NOT NULL,
    score_final  REAL,
    recomendacao TEXT,
    confianca    TEXT,
    resultado    TEXT,
    erro         TEXT,
    avaliado_em  TEXT NOT NULL,
    PRIMARY KEY (vaga_id, candidato_id)
);

CREATE TABLE IF NOT EXISTS decisoes (
    vaga_id       TEXT NOT NULL REFERENCES vagas(id) ON DELETE CASCADE,
    candidato_id  TEXT NOT NULL,
    decisao       TEXT NOT NULL DEFAULT 'sem_decisao',
    anotacao      TEXT NOT NULL DEFAULT '',
    usuario_id    TEXT,
    atualizado_em TEXT NOT NULL,
    PRIMARY KEY (vaga_id, candidato_id)
);

CREATE TABLE IF NOT EXISTS auditoria (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id      TEXT,
    usuario_id  TEXT,
    acao        TEXT NOT NULL,
    entidade    TEXT,
    entidade_id TEXT,
    detalhe     TEXT,
    ip          TEXT,
    em          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mcp_clientes (
    client_id TEXT PRIMARY KEY,
    dados     TEXT NOT NULL,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mcp_pedidos (
    id                 TEXT PRIMARY KEY,
    client_id          TEXT NOT NULL,
    redirect_uri       TEXT NOT NULL,
    redirect_explicito INTEGER NOT NULL DEFAULT 0,
    code_challenge     TEXT NOT NULL,
    state              TEXT,
    scopes             TEXT,
    recurso            TEXT,
    expira_em          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mcp_codigos (
    codigo             TEXT PRIMARY KEY,
    client_id          TEXT NOT NULL,
    usuario_id         TEXT NOT NULL,
    redirect_uri       TEXT NOT NULL,
    redirect_explicito INTEGER NOT NULL DEFAULT 0,
    code_challenge     TEXT NOT NULL,
    scopes             TEXT,
    recurso            TEXT,
    expira_em          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mcp_tokens (
    token_hash TEXT PRIMARY KEY,
    tipo       TEXT NOT NULL,
    client_id  TEXT,
    usuario_id TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    scopes     TEXT,
    recurso    TEXT,
    rotulo     TEXT,
    expira_em  TEXT,
    criado_em  TEXT NOT NULL,
    usado_em   TEXT
);

CREATE INDEX IF NOT EXISTS idx_mcp_tokens_usuario ON mcp_tokens(usuario_id);
CREATE INDEX IF NOT EXISTS idx_vagas_org    ON vagas(org_id, arquivada, criada_em DESC);
CREATE INDEX IF NOT EXISTS idx_curr_org     ON curriculos(org_id, criado_em);
CREATE INDEX IF NOT EXISTS idx_aval_vaga    ON avaliacoes(vaga_id, score_final DESC);
CREATE INDEX IF NOT EXISTS idx_sessoes_exp  ON sessoes(expira_em);
CREATE INDEX IF NOT EXISTS idx_usuarios_org ON usuarios(org_id);
CREATE INDEX IF NOT EXISTS idx_audit_org    ON auditoria(org_id, em DESC);
CREATE INDEX IF NOT EXISTS idx_tentativas   ON tentativas_login(chave, em);
CREATE INDEX IF NOT EXISTS idx_recuperacoes ON recuperacoes(usuario_id);
"""


# ---------- Conexão ----------

def conexao() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn = conn
    return _local.conn


def _executar(sql: str, parametros: Iterable = ()) -> sqlite3.Cursor:
    """Escrita serializada: o SQLite aceita um escritor por vez."""
    with _escrita:
        conn = conexao()
        cur = conn.execute(sql, tuple(parametros))
        conn.commit()
        return cur


def iniciar() -> None:
    """Cria ou migra o banco. Idempotente — pode rodar a cada boot."""
    with _escrita:
        conn = conexao()
        versao = conn.execute("PRAGMA user_version").fetchone()[0]
        if _tem_esquema_legado(conn):
            # Os índices novos citam colunas que a tabela antiga não tem: migra antes.
            _migrar_legado(conn)
        else:
            conn.executescript(ESQUEMA)
            if versao and versao < 4:
                _migrar_v4(conn)
            if versao and versao < 5:
                _migrar_v5(conn)
            if versao and versao < 7:
                _migrar_v7(conn)
        conn.execute(f"PRAGMA user_version={VERSAO_ESQUEMA}")
        conn.commit()


def _migrar_v5(conn: sqlite3.Connection) -> None:
    """Entra o OCR: de onde veio o texto de cada currículo, e com que qualidade.

    Currículo que já estava no banco veio de extração direta, então o padrão
    'direto' é a resposta certa para todos eles.
    """
    log.warning("migrando o banco para o esquema 5 (OCR do PDF escaneado)")
    existentes = _colunas(conn, "curriculos")
    if "origem_texto" not in existentes:
        conn.execute(
            "ALTER TABLE curriculos ADD COLUMN origem_texto TEXT NOT NULL DEFAULT 'direto'"
        )
    if "ocr_confianca" not in existentes:
        conn.execute("ALTER TABLE curriculos ADD COLUMN ocr_confianca TEXT")


def _migrar_v7(conn: sqlite3.Connection) -> None:
    """Entra a fila de OCR: o currículo passa a ter estado de extração.

    Tudo que já estava no banco foi extraído no upload, então 'pronto' é a
    resposta certa para todos eles.
    """
    log.warning("migrando o banco para o esquema 7 (fila de OCR)")
    if "estado_extracao" not in _colunas(conn, "curriculos"):
        conn.execute(
            "ALTER TABLE curriculos ADD COLUMN estado_extracao "
            "TEXT NOT NULL DEFAULT 'pronto'"
        )


def _colunas(conn: sqlite3.Connection, tabela: str) -> set[str]:
    return {c["name"] for c in conn.execute(f"PRAGMA table_info({tabela})")}


def _migrar_v4(conn: sqlite3.Connection) -> None:
    """Sai o modo API: chave da Anthropic, teto de gasto e estado de corrida.

    Só apaga o que era exclusivo daquele modo. Vaga, currículo, avaliação e
    decisão não são tocados — quem já tinha triagem feita continua com ela.
    """
    log.warning("migrando o banco para o esquema 4 (remoção do modo API)")

    conn.execute("DROP TABLE IF EXISTS gastos")
    conn.execute("DROP INDEX IF EXISTS idx_gastos_org")

    mortas = {
        "organizacoes": ("limite_mensal_usd", "api_key_cifrada", "api_key_mascara"),
        "vagas": ("progresso", "uso"),
    }
    for tabela, colunas in mortas.items():
        existentes = _colunas(conn, tabela)
        for coluna in colunas:
            if coluna in existentes:
                conn.execute(f"ALTER TABLE {tabela} DROP COLUMN {coluna}")

    # `precisa_visao` marcava o PDF que iria para leitura por visão da API.
    # A informação continua útil (é o mesmo PDF que vai para OCR), só muda de nome.
    colunas_curriculos = _colunas(conn, "curriculos")
    if "precisa_visao" in colunas_curriculos and "escaneado" not in colunas_curriculos:
        conn.execute("ALTER TABLE curriculos RENAME COLUMN precisa_visao TO escaneado")

    # Vaga que ficou marcada como 'processando' por uma corrida do modo API nunca
    # mais vai sair sozinha desse estado: ninguém dispara pipeline agora.
    # Estados que só o pipeline produzia. Sem ele, a vaga com rubrica aprovada
    # está sempre 'pronta': o quanto já foi avaliado sai da contagem, não do status.
    conn.execute(
        """UPDATE vagas SET status='pronta', erro=NULL
            WHERE status IN ('processando','interrompido','concluido','cancelado','erro')"""
    )


def _tem_esquema_legado(conn: sqlite3.Connection) -> bool:
    tabela = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='curriculos'"
    ).fetchone()
    if not tabela:
        return False
    colunas = {c["name"] for c in conn.execute("PRAGMA table_info(curriculos)")}
    return "org_id" not in colunas


def _migrar_legado(conn: sqlite3.Connection) -> None:
    """Banco da versão 1 (sem contas): joga tudo numa organização de migração."""
    log.warning("banco em formato antigo detectado; migrando para o esquema multi-empresa")
    org_id = uuid.uuid4().hex[:12]

    # Renomear tabela com FK ligada faz o SQLite reescrever referências alheias.
    conn.execute("PRAGMA foreign_keys=OFF")
    for tabela in ("curriculos", "vagas", "vaga_curriculos", "avaliacoes"):
        conn.execute(f"ALTER TABLE {tabela} RENAME TO {tabela}_v1")
    conn.executescript(ESQUEMA)

    conn.execute(
        "INSERT INTO organizacoes (id, nome, retencao_dias, criada_em) VALUES (?,?,?,?)",
        (org_id, "Dados migrados", RETENCAO_DIAS_PADRAO, agora()),
    )
    conn.execute(
        """INSERT INTO curriculos
             (org_id, candidato_id, arquivo, origem, texto, parse, avisos, criado_em)
           SELECT ?, candidato_id, arquivo, COALESCE(origem,'arquivo'),
                  texto, parse, avisos, criado_em FROM curriculos_v1""",
        (org_id,),
    )
    conn.execute(
        """INSERT INTO vagas
             (id, org_id, titulo, descricao, rubrica, rubrica_ok, status, criada_em)
           SELECT id, ?, titulo, descricao, rubrica, rubrica_ok, status, criada_em
             FROM vagas_v1""",
        (org_id,),
    )
    conn.execute(
        "INSERT INTO vaga_curriculos SELECT vaga_id, candidato_id FROM vaga_curriculos_v1"
    )
    conn.execute(
        """INSERT INTO avaliacoes
             (vaga_id, candidato_id, estagio, score_final, recomendacao,
              resultado, erro, avaliado_em)
           SELECT vaga_id, candidato_id, estagio, score_final, recomendacao,
                  resultado, erro, avaliado_em FROM avaliacoes_v1"""
    )
    for tabela in ("curriculos", "vagas", "vaga_curriculos", "avaliacoes"):
        conn.execute(f"DROP TABLE {tabela}_v1")
    conn.execute("PRAGMA foreign_keys=ON")
    log.warning(
        "migração concluída na organização %s — cadastre-se pela tela de login e "
        "peça a vinculação do seu usuário a essa organização", org_id
    )


# ---------- Utilitários ----------

def agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex[:12]


def _j(valor: Any) -> Optional[str]:
    return json.dumps(valor, ensure_ascii=False) if valor is not None else None


def _dj(valor: Optional[str]) -> Any:
    if not valor:
        return None
    try:
        return json.loads(valor)
    except (json.JSONDecodeError, TypeError):
        return None


def pasta_org(org_id: str) -> Path:
    pasta = UPLOAD_DIR / org_id
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


# ---------- Organizações ----------

def criar_organizacao(nome: str) -> str:
    org_id = _id()
    _executar(
        "INSERT INTO organizacoes (id, nome, retencao_dias, criada_em) VALUES (?,?,?,?)",
        (org_id, nome, RETENCAO_DIAS_PADRAO, agora()),
    )
    return org_id


def buscar_organizacao(org_id: str) -> Optional[dict]:
    linha = conexao().execute(
        "SELECT * FROM organizacoes WHERE id=?", (org_id,)
    ).fetchone()
    return dict(linha) if linha else None


def atualizar_organizacao(org_id: str, **campos: Any) -> None:
    if not campos:
        return
    sets = ", ".join(f"{k}=?" for k in campos)
    _executar(f"UPDATE organizacoes SET {sets} WHERE id=?", (*campos.values(), org_id))


# ---------- Usuários ----------

def criar_usuario(org_id: str, email: str, nome: str, senha_hash: str,
                  papel: str = "recrutador") -> str:
    usuario_id = _id()
    _executar(
        """INSERT INTO usuarios (id, org_id, email, nome, senha_hash, papel, criado_em)
           VALUES (?,?,?,?,?,?,?)""",
        (usuario_id, org_id, email.strip().lower(), nome, senha_hash, papel, agora()),
    )
    return usuario_id


def buscar_usuario_por_email(email: str) -> Optional[dict]:
    linha = conexao().execute(
        "SELECT * FROM usuarios WHERE email=?", (email.strip().lower(),)
    ).fetchone()
    return dict(linha) if linha else None


def buscar_usuario(usuario_id: str) -> Optional[dict]:
    linha = conexao().execute(
        "SELECT * FROM usuarios WHERE id=?", (usuario_id,)
    ).fetchone()
    return dict(linha) if linha else None


def listar_usuarios(org_id: str) -> list[dict]:
    linhas = conexao().execute(
        """SELECT id, email, nome, papel, ativo, criado_em, ultimo_acesso
           FROM usuarios WHERE org_id=? ORDER BY criado_em""",
        (org_id,),
    ).fetchall()
    return [dict(l) for l in linhas]


def atualizar_usuario(usuario_id: str, **campos: Any) -> None:
    if not campos:
        return
    sets = ", ".join(f"{k}=?" for k in campos)
    _executar(f"UPDATE usuarios SET {sets} WHERE id=?", (*campos.values(), usuario_id))


def remover_usuario(org_id: str, usuario_id: str) -> bool:
    cur = _executar(
        "DELETE FROM usuarios WHERE id=? AND org_id=?", (usuario_id, org_id)
    )
    return cur.rowcount > 0


def contar_admins(org_id: str) -> int:
    return conexao().execute(
        "SELECT COUNT(*) FROM usuarios WHERE org_id=? AND papel='admin' AND ativo=1",
        (org_id,),
    ).fetchone()[0]


# ---------- Sessões ----------

def criar_sessao(usuario_id: str, token_hash: str, csrf: str, horas: int,
                 ip: str = "", agente: str = "") -> None:
    expira = datetime.now(timezone.utc) + timedelta(hours=horas)
    _executar(
        """INSERT INTO sessoes (token_hash, usuario_id, csrf, criada_em, expira_em, ip, agente)
           VALUES (?,?,?,?,?,?,?)""",
        (token_hash, usuario_id, csrf, agora(), expira.isoformat(), ip, agente[:200]),
    )


def buscar_sessao(token_hash: str) -> Optional[dict]:
    linha = conexao().execute(
        """SELECT s.*, u.org_id, u.papel, u.nome, u.email, u.ativo
           FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id
           WHERE s.token_hash=?""",
        (token_hash,),
    ).fetchone()
    if not linha:
        return None
    sessao = dict(linha)
    if sessao["expira_em"] < agora():
        encerrar_sessao(token_hash)
        return None
    return sessao


def encerrar_sessao(token_hash: str) -> None:
    _executar("DELETE FROM sessoes WHERE token_hash=?", (token_hash,))


def encerrar_sessoes_do_usuario(usuario_id: str) -> None:
    _executar("DELETE FROM sessoes WHERE usuario_id=?", (usuario_id,))


def criar_recuperacao(usuario_id: str, token_hash: str, minutos: int,
                      ip: str = "") -> None:
    """Abre um pedido de recuperação e invalida os anteriores do mesmo usuário.

    Um link por vez: pedir de novo tem que apagar o link antigo, senão um
    e-mail antigo esquecido na caixa continuaria trocando a senha.
    """
    _executar("DELETE FROM recuperacoes WHERE usuario_id=?", (usuario_id,))
    _executar(
        """INSERT INTO recuperacoes (token_hash, usuario_id, criado_em, expira_em, ip)
           VALUES (?,?,?,?,?)""",
        (token_hash, usuario_id, agora(),
         (datetime.now(timezone.utc) + timedelta(minutes=minutos)).isoformat(), ip),
    )


def buscar_recuperacao(token_hash: str) -> Optional[dict]:
    linha = conexao().execute(
        "SELECT * FROM recuperacoes WHERE token_hash=?", (token_hash,)
    ).fetchone()
    return dict(linha) if linha else None


def consumir_recuperacao(token_hash: str) -> None:
    """Uso único: o link vale uma vez, e some assim que serve."""
    _executar("DELETE FROM recuperacoes WHERE token_hash=?", (token_hash,))


def invalidar_recuperacoes_do_usuario(usuario_id: str) -> None:
    _executar("DELETE FROM recuperacoes WHERE usuario_id=?", (usuario_id,))


def limpar_recuperacoes_vencidas() -> int:
    cur = _executar("DELETE FROM recuperacoes WHERE expira_em < ?", (agora(),))
    return cur.rowcount


def limpar_sessoes_vencidas() -> int:
    return _executar("DELETE FROM sessoes WHERE expira_em < ?", (agora(),)).rowcount


# ---------- Freio de força bruta no login ----------

def registrar_tentativa(chave: str) -> None:
    _executar("INSERT INTO tentativas_login (chave, em) VALUES (?,?)", (chave, agora()))


def contar_tentativas(chave: str, janela_min: int) -> int:
    desde = (datetime.now(timezone.utc) - timedelta(minutes=janela_min)).isoformat()
    return conexao().execute(
        "SELECT COUNT(*) FROM tentativas_login WHERE chave=? AND em > ?", (chave, desde)
    ).fetchone()[0]


def limpar_tentativas(chave: str) -> None:
    _executar("DELETE FROM tentativas_login WHERE chave=?", (chave,))


# ---------- Vagas ----------

def criar_vaga(org_id: str, titulo: str, descricao: str, usuario_id: str) -> str:
    vaga_id = _id()
    _executar(
        """INSERT INTO vagas (id, org_id, titulo, descricao, criada_por, criada_em, atualizada_em)
           VALUES (?,?,?,?,?,?,?)""",
        (vaga_id, org_id, titulo, descricao, usuario_id, agora(), agora()),
    )
    return vaga_id


def salvar_rubrica(org_id: str, vaga_id: str, rubrica: dict, aprovada: bool = False) -> None:
    _executar(
        "UPDATE vagas SET rubrica=?, rubrica_ok=?, atualizada_em=? WHERE id=? AND org_id=?",
        (_j(rubrica), int(aprovada), agora(), vaga_id, org_id),
    )


def atualizar_vaga(vaga_id: str, **campos: Any) -> None:
    if not campos:
        return
    serializados = {
        k: _j(v) if k == "rubrica" else v for k, v in campos.items()
    }
    serializados["atualizada_em"] = agora()
    sets = ", ".join(f"{k}=?" for k in serializados)
    _executar(f"UPDATE vagas SET {sets} WHERE id=?", (*serializados.values(), vaga_id))


def buscar_vaga(org_id: str, vaga_id: str) -> Optional[dict]:
    linha = conexao().execute(
        "SELECT * FROM vagas WHERE id=? AND org_id=?", (vaga_id, org_id)
    ).fetchone()
    if not linha:
        return None
    vaga = dict(linha)
    vaga["rubrica"] = _dj(vaga["rubrica"])
    vaga["rubrica_ok"] = bool(vaga["rubrica_ok"])
    vaga["arquivada"] = bool(vaga["arquivada"])
    return vaga


def buscar_vaga_sem_org(vaga_id: str) -> Optional[dict]:
    """Só para o pipeline, que já validou o acesso antes de disparar."""
    linha = conexao().execute("SELECT org_id FROM vagas WHERE id=?", (vaga_id,)).fetchone()
    return buscar_vaga(linha["org_id"], vaga_id) if linha else None


def listar_vagas(org_id: str, incluir_arquivadas: bool = False) -> list[dict]:
    filtro = "" if incluir_arquivadas else " AND v.arquivada=0"
    linhas = conexao().execute(
        f"""SELECT v.id, v.titulo, v.status, v.criada_em, v.arquivada, v.rubrica_ok,
                   (SELECT COUNT(*) FROM avaliacoes a
                     WHERE a.vaga_id=v.id AND a.recomendacao='chamar') AS chamar,
                   (SELECT COUNT(*) FROM decisoes d
                     WHERE d.vaga_id=v.id AND d.decisao='entrevistar') AS entrevistar
            FROM vagas v WHERE v.org_id=?{filtro}
            ORDER BY v.criada_em DESC""",
        (org_id,),
    ).fetchall()

    # O progresso vem da mesma função que serve o detalhe da vaga. Duas consultas
    # para a organização inteira, não uma por vaga.
    contagens = contagens_das_vagas(org_id)

    saida = []
    for l in linhas:
        d = dict(l)
        d["arquivada"] = bool(d["arquivada"])
        d["rubrica_ok"] = bool(d["rubrica_ok"])
        d.update(contagens.get(d["id"], {}))
        d["curriculos"] = d.get("total", 0)                    # nome antigo, mantido
        saida.append(d)
    return saida


def remover_vaga(org_id: str, vaga_id: str) -> bool:
    """Apaga a vaga e o que dependia dela. Os currículos ficam — são reusáveis."""
    cur = _executar("DELETE FROM vagas WHERE id=? AND org_id=?", (vaga_id, org_id))
    return cur.rowcount > 0


# ---------- Currículos ----------

def salvar_curriculo(org_id: str, doc) -> bool:
    """True se é novo nesta organização. Se já existe, mantém o parse — é o cache."""
    existente = conexao().execute(
        "SELECT 1 FROM curriculos WHERE org_id=? AND candidato_id=?",
        (org_id, doc.candidato_id),
    ).fetchone()
    if existente:
        return False
    _executar(
        """INSERT INTO curriculos
             (org_id, candidato_id, arquivo, origem, origem_hash, extensao,
              escaneado, origem_texto, ocr_confianca, estado_extracao,
              texto, avisos, criado_em)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (org_id, doc.candidato_id, doc.arquivo, doc.origem, doc.origem_hash,
         doc.extensao, int(doc.escaneado), getattr(doc, "origem_texto", "direto"),
         getattr(doc, "ocr_confianca", "") or None,
         getattr(doc, "estado_extracao", "pronto"),
         doc.texto, _j(doc.avisos), agora()),
    )
    return True


def vincular(vaga_id: str, candidato_id: str) -> None:
    _executar(
        "INSERT OR IGNORE INTO vaga_curriculos (vaga_id, candidato_id) VALUES (?,?)",
        (vaga_id, candidato_id),
    )


def desvincular(vaga_id: str, candidato_id: str) -> None:
    _executar(
        "DELETE FROM vaga_curriculos WHERE vaga_id=? AND candidato_id=?",
        (vaga_id, candidato_id),
    )
    _executar(
        "DELETE FROM avaliacoes WHERE vaga_id=? AND candidato_id=?", (vaga_id, candidato_id)
    )


def salvar_parse(org_id: str, candidato_id: str, parse: dict) -> None:
    _executar(
        "UPDATE curriculos SET parse=? WHERE org_id=? AND candidato_id=?",
        (_j(parse), org_id, candidato_id),
    )


def atualizar_curriculo(org_id: str, candidato_id: str, **campos: Any) -> None:
    """Atualiza o currículo depois do upload. É por aqui que a fila de OCR grava."""
    if not campos:
        return
    valores = {
        k: (_j(v) if k in {"avisos", "parse"} else v) for k, v in campos.items()
    }
    atribuicoes = ", ".join(f"{k}=?" for k in valores)
    _executar(
        f"UPDATE curriculos SET {atribuicoes} WHERE org_id=? AND candidato_id=?",
        (*valores.values(), org_id, candidato_id),
    )


def curriculos_pendentes_de_ocr(limite: int = 500) -> list[dict]:
    """O que ficou esperando OCR. Serve para recolher no boot depois de uma queda."""
    linhas = conexao().execute(
        """SELECT org_id, candidato_id FROM curriculos
            WHERE estado_extracao='pendente'
            ORDER BY criado_em LIMIT ?""",
        (limite,),
    ).fetchall()
    return [dict(l) for l in linhas]


def buscar_curriculo(org_id: str, candidato_id: str) -> Optional[dict]:
    linha = conexao().execute(
        "SELECT * FROM curriculos WHERE org_id=? AND candidato_id=?", (org_id, candidato_id)
    ).fetchone()
    if not linha:
        return None
    d = dict(linha)
    d["parse"] = _dj(d["parse"])
    d["avisos"] = _dj(d["avisos"]) or []
    d["escaneado"] = bool(d["escaneado"])
    return d


def curriculos_da_vaga(org_id: str, vaga_id: str) -> list[dict]:
    linhas = conexao().execute(
        """SELECT c.* FROM curriculos c
           JOIN vaga_curriculos vc ON vc.candidato_id = c.candidato_id
           JOIN vagas v ON v.id = vc.vaga_id
           WHERE vc.vaga_id=? AND c.org_id=? AND v.org_id=?
           ORDER BY c.arquivo""",
        (vaga_id, org_id, org_id),
    ).fetchall()
    saida = []
    for l in linhas:
        d = dict(l)
        d["parse"] = _dj(d["parse"])
        d["avisos"] = _dj(d["avisos"]) or []
        d["escaneado"] = bool(d["escaneado"])
        saida.append(d)
    return saida


def contar_curriculos_da_vaga(org_id: str, vaga_id: str) -> int:
    return conexao().execute(
        """SELECT COUNT(*) FROM vaga_curriculos vc
           JOIN vagas v ON v.id = vc.vaga_id
           WHERE vc.vaga_id=? AND v.org_id=?""",
        (vaga_id, org_id),
    ).fetchone()[0]


def contagens_das_vagas(org_id: str,
                        vaga_id: Optional[str] = None) -> dict[str, dict]:
    """Progresso por vaga, contado na hora. A única definição que existe.

    Isto aqui é fonte única de propósito. Antes a lista de vagas contava linhas
    de `avaliacoes` e o detalhe contava só `estagio='avaliado'`: os dois números
    batiam enquanto ninguém eliminava candidato nem tinha currículo ilegível, e
    passariam a divergir na frente do recrutador exatamente quando ele fosse
    olhar. Um número com duas definições é um número em que não se pode confiar.

    Nada é estado guardado: quem avalia é o Claude do recrutador, por fora e
    possivelmente com a janela fechada. Contagem no momento da consulta nunca
    dessincroniza.

    `erros` é o currículo que não tem como ser entregue ao conector — a extração
    falhou, ou o texto não pôde ser anonimizado com segurança. Sem contá-lo, ele
    ficaria pendente para sempre e a vaga nunca chegaria ao fim.
    """
    filtro = " AND v.id = ?" if vaga_id else ""
    parametros = (org_id, vaga_id) if vaga_id else (org_id,)

    totais = conexao().execute(
        f"""SELECT v.id AS vaga_id,
                   COUNT(vc.candidato_id) AS total,
                   COALESCE(SUM(c.origem_texto = 'ocr'), 0) AS por_ocr,
                   COALESCE(SUM(
                       c.estado_extracao != 'pendente'
                       AND (COALESCE(TRIM(c.texto), '') = ''
                            OR c.estado_extracao = 'insuficiente'
                            OR json_extract(c.parse, '$.retido') = 1)
                       AND NOT EXISTS (SELECT 1 FROM avaliacoes a
                                        WHERE a.vaga_id = vc.vaga_id
                                          AND a.candidato_id = vc.candidato_id)
                   ), 0) AS erros,
                   COALESCE(SUM(c.estado_extracao = 'pendente'), 0) AS lendo
              FROM vagas v
              LEFT JOIN vaga_curriculos vc ON vc.vaga_id = v.id
              LEFT JOIN curriculos c
                     ON c.candidato_id = vc.candidato_id AND c.org_id = v.org_id
             WHERE v.org_id = ?{filtro}
             GROUP BY v.id""",
        parametros,
    ).fetchall()

    vereditos = conexao().execute(
        f"""SELECT v.id AS vaga_id,
                   COALESCE(SUM(a.estagio = 'avaliado'), 0)  AS avaliados,
                   COALESCE(SUM(a.estagio = 'eliminado'), 0) AS eliminados,
                   -- Qualquer outro estágio é veredito de falha: o 'erro' que o
                   -- pipeline do modo API gravava, e o que vier depois. Contar
                   -- pelo que sobra evita ter de lembrar de cada valor novo.
                   COALESCE(SUM(a.estagio NOT IN ('avaliado', 'eliminado')), 0)
                       AS falhas_registradas,
                   MAX(a.avaliado_em)                        AS ultimo
              FROM vagas v
              JOIN avaliacoes a ON a.vaga_id = v.id
             WHERE v.org_id = ?{filtro}
             GROUP BY v.id""",
        parametros,
    ).fetchall()
    por_vaga = {linha["vaga_id"]: linha for linha in vereditos}

    saida: dict[str, dict] = {}
    for linha in totais:
        veredito = por_vaga.get(linha["vaga_id"])
        total = int(linha["total"] or 0)
        avaliados = int(veredito["avaliados"] or 0) if veredito else 0
        eliminados = int(veredito["eliminados"] or 0) if veredito else 0
        # Duas origens de erro, e elas não se sobrepõem: a de `curriculos` conta
        # quem não tem linha de avaliação nenhuma, a de `avaliacoes` conta quem
        # tem linha com estágio de falha.
        erros = int(linha["erros"] or 0)
        erros += int(veredito["falhas_registradas"] or 0) if veredito else 0
        saida[linha["vaga_id"]] = {
            "total": total,
            "avaliados": avaliados,
            "eliminados": eliminados,
            "erros": erros,
            # Tudo que já tem veredito. É este o número da manchete "X de N" e o
            # do card na lista — se as eliminações e as falhas ficassem de fora,
            # uma vaga com um único currículo ilegível nunca chegaria ao fim.
            "com_veredito": avaliados + eliminados + erros,
            # Nunca negativo: se algum dia as contas divergirem, mostra 0
            # pendente em vez de mentir.
            "pendentes": max(0, total - avaliados - eliminados - erros),
            "por_ocr": int(linha["por_ocr"] or 0),
            # Escaneado ainda na fila de leitura. Some sozinho quando o OCR roda;
            # é informação de espera, não de problema.
            "lendo": int(linha["lendo"] or 0),
            "ultimo_registro_em": veredito["ultimo"] if veredito else None,
        }
    return saida


def resumo_da_vaga(org_id: str, vaga_id: str) -> dict:
    """O progresso de uma vaga. Mesmo cálculo da lista, por construção."""
    contagens = contagens_das_vagas(org_id, vaga_id)
    return contagens.get(vaga_id) or {
        "total": 0, "avaliados": 0, "eliminados": 0, "erros": 0,
        "com_veredito": 0, "pendentes": 0, "por_ocr": 0, "lendo": 0,
        "ultimo_registro_em": None,
    }


def caminho_arquivo(org_id: str, candidato_id: str) -> Optional[Path]:
    curriculo = buscar_curriculo(org_id, candidato_id)
    if not curriculo or not curriculo.get("origem_hash"):
        return None
    caminho = pasta_org(org_id) / f"{curriculo['origem_hash']}{curriculo.get('extensao') or ''}"
    return caminho if caminho.exists() else None


# ---------- Avaliações e decisões ----------

def salvar_avaliacao(
    vaga_id: str,
    candidato_id: str,
    estagio: str,
    score_final: Optional[float] = None,
    recomendacao: Optional[str] = None,
    confianca: Optional[str] = None,
    resultado: Optional[dict] = None,
    erro: Optional[str] = None,
) -> None:
    _executar(
        """INSERT OR REPLACE INTO avaliacoes
             (vaga_id, candidato_id, estagio, score_final, recomendacao,
              confianca, resultado, erro, avaliado_em)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (vaga_id, candidato_id, estagio, score_final, recomendacao,
         confianca, _j(resultado), erro, agora()),
    )


def limpar_avaliacoes(vaga_id: str) -> None:
    _executar("DELETE FROM avaliacoes WHERE vaga_id=?", (vaga_id,))


def salvar_decisao(vaga_id: str, candidato_id: str, decisao: str,
                   anotacao: str, usuario_id: str) -> None:
    _executar(
        """INSERT OR REPLACE INTO decisoes
             (vaga_id, candidato_id, decisao, anotacao, usuario_id, atualizado_em)
           VALUES (?,?,?,?,?,?)""",
        (vaga_id, candidato_id, decisao, anotacao, usuario_id, agora()),
    )


def ranking(org_id: str, vaga_id: str) -> list[dict]:
    # O ranking parte dos currículos da vaga, não das avaliações. A diferença não
    # é de estilo: um currículo ilegível, ou retido pela anonimização, nunca teve
    # avaliação registrada. Partindo de `avaliacoes` com INNER JOIN, ele sumia da
    # tela — o recrutador via a contagem de falhas no painel e não tinha nome nem
    # arquivo para saber de quem era, nem para pedir reenvio.
    #
    # Quem ainda está na fila para ser avaliado fica de fora: não é resultado,
    # é espera, e o painel de status já conta essa parte.
    linhas = conexao().execute(
        """SELECT vc.vaga_id, vc.candidato_id,
                  a.estagio, a.score_final, a.recomendacao,
                  a.confianca, a.resultado, a.erro, a.avaliado_em,
                  c.arquivo, c.parse, c.avisos, c.origem, c.origem_hash, c.extensao,
                  c.origem_texto, c.ocr_confianca, c.estado_extracao,
                  COALESCE(TRIM(c.texto), '') = '' AS sem_texto,
                  d.decisao, d.anotacao
           FROM vaga_curriculos vc
           JOIN vagas v      ON v.id = vc.vaga_id AND v.org_id = ?
           JOIN curriculos c ON c.candidato_id = vc.candidato_id AND c.org_id = ?
           LEFT JOIN avaliacoes a
                  ON a.vaga_id = vc.vaga_id AND a.candidato_id = vc.candidato_id
           LEFT JOIN decisoes d
                  ON d.vaga_id = vc.vaga_id AND d.candidato_id = vc.candidato_id
           WHERE vc.vaga_id=?
             AND (a.candidato_id IS NOT NULL
                  OR (c.estado_extracao != 'pendente'
                      AND (COALESCE(TRIM(c.texto), '') = ''
                           OR c.estado_extracao = 'insuficiente'
                           OR json_extract(c.parse, '$.retido') = 1)))
           ORDER BY (a.score_final IS NULL), a.score_final DESC, c.arquivo""",
        (org_id, org_id, vaga_id),
    ).fetchall()

    saida = []
    for l in linhas:
        d = dict(l)
        d["resultado"] = _dj(d["resultado"])
        parse = _dj(d.pop("parse")) or {}
        identificacao = parse.get("identificacao") or {}
        d["nome"] = identificacao.get("nome") or "—"
        d["contato"] = identificacao
        d["perfil"] = parse.get("perfil") or {}
        d["avisos"] = _dj(d["avisos"]) or []
        d["decisao"] = d["decisao"] or "sem_decisao"
        d["anotacao"] = d["anotacao"] or ""
        # O hash serve ao servidor, não ao navegador: vira só um sim/não.
        d["tem_arquivo"] = bool(d.pop("origem_hash", None))

        # Amarra 1 da spec: o booleano vai para a tela junto do erro. Quem
        # separa os dois grupos é ELE, nunca substring do texto do motivo — a
        # frase está no inventário de microcopy da Pigmento e vai ser reescrita.
        d["retido"] = bool(parse.get("retido"))

        if not d["estagio"]:
            # Sem avaliação e ainda assim aqui: é um dos que não têm como ser
            # avaliados. Cai no grupo "Não foi possível avaliar" da tela, com o
            # motivo escrito para o recrutador saber o que fazer.
            d["estagio"] = "erro"
            d["erro"] = _motivo_da_falha(parse, d["avisos"], bool(d["sem_texto"]),
                                        d.get("estado_extracao") or "pronto",
                                        d["tem_arquivo"])
        d.pop("sem_texto", None)
        saida.append(d)
    return saida


def _motivo_da_falha(parse: dict, avisos: list, sem_texto: bool,
                     estado: str = "pronto", tem_arquivo: bool = True) -> str:
    """O que dizer ao recrutador sobre um currículo que não pôde ser avaliado.

    Precisa ser acionável: ele ainda tem o arquivo e pode reenviar outra versão.
    """
    if parse.get("retido"):
        # Se o original já expirou pelo prazo de retenção, mandar "revise o
        # arquivo" seria mandar o recrutador procurar o que não existe mais. A
        # ação muda: pedir outro.
        if not tem_arquivo:
            return ("o arquivo original já foi apagado pelo prazo de retenção, "
                    "e o texto escaneado não pode ser entregue sem identificação; "
                    "peça o currículo de novo a esta pessoa")
        return parse.get("motivo_retencao") or (
            "não foi possível remover a identificação com segurança do texto "
            "escaneado; revise o arquivo"
        )
    if estado == "insuficiente":
        return ("o arquivo abriu, mas não tem texto que sustente uma avaliação — "
                "confira se é o currículo certo ou peça outro")
    if sem_texto:
        for aviso in reversed(avisos):
            if "OCR" in aviso or "escaneado" in aviso or "falha" in aviso:
                return aviso
        return "não foi possível extrair texto deste arquivo"
    return "não foi possível avaliar este currículo"


# ---------- Auditoria ----------

def registrar_auditoria(org_id: Optional[str], usuario_id: Optional[str], acao: str,
                        entidade: str = "", entidade_id: str = "",
                        detalhe: Any = None, ip: str = "") -> None:
    _executar(
        """INSERT INTO auditoria
             (org_id, usuario_id, acao, entidade, entidade_id, detalhe, ip, em)
           VALUES (?,?,?,?,?,?,?,?)""",
        (org_id, usuario_id, acao, entidade, entidade_id,
         _j(detalhe) if detalhe is not None else None, ip, agora()),
    )


def listar_auditoria(org_id: str, limite: int = 200) -> list[dict]:
    linhas = conexao().execute(
        """SELECT a.*, u.nome AS usuario_nome, u.email AS usuario_email
           FROM auditoria a LEFT JOIN usuarios u ON u.id = a.usuario_id
           WHERE a.org_id=? ORDER BY a.em DESC LIMIT ?""",
        (org_id, min(limite, 1000)),
    ).fetchall()
    saida = []
    for l in linhas:
        d = dict(l)
        d["detalhe"] = _dj(d["detalhe"])
        saida.append(d)
    return saida


# ---------- LGPD: busca, exportação e exclusão ----------

def procurar_candidatos(org_id: str, termo: str, limite: int = 50) -> list[dict]:
    """Atende pedido de titular: acha a pessoa por nome, e-mail ou arquivo."""
    alvo = f"%{termo.strip().lower()}%"
    linhas = conexao().execute(
        """SELECT candidato_id, arquivo, criado_em, parse FROM curriculos
           WHERE org_id=? AND (LOWER(arquivo) LIKE ? OR LOWER(COALESCE(parse,'')) LIKE ?)
           ORDER BY criado_em DESC LIMIT ?""",
        (org_id, alvo, alvo, min(limite, 200)),
    ).fetchall()
    saida = []
    for l in linhas:
        parse = _dj(l["parse"]) or {}
        identificacao = parse.get("identificacao") or {}
        saida.append({
            "candidato_id": l["candidato_id"],
            "arquivo": l["arquivo"],
            "criado_em": l["criado_em"],
            "nome": identificacao.get("nome") or "—",
            "email": identificacao.get("email") or "",
            "telefone": identificacao.get("telefone") or "",
        })
    return saida


def exportar_candidato(org_id: str, candidato_id: str) -> Optional[dict]:
    """Tudo que a organização guarda sobre a pessoa. É o relatório do titular."""
    curriculo = buscar_curriculo(org_id, candidato_id)
    if not curriculo:
        return None
    avaliacoes = conexao().execute(
        """SELECT a.*, v.titulo AS vaga_titulo FROM avaliacoes a
           JOIN vagas v ON v.id = a.vaga_id
           WHERE a.candidato_id=? AND v.org_id=?""",
        (candidato_id, org_id),
    ).fetchall()
    decisoes = conexao().execute(
        """SELECT d.*, v.titulo AS vaga_titulo FROM decisoes d
           JOIN vagas v ON v.id = d.vaga_id
           WHERE d.candidato_id=? AND v.org_id=?""",
        (candidato_id, org_id),
    ).fetchall()
    return {
        "candidato_id": candidato_id,
        "curriculo": curriculo,
        "avaliacoes": [
            {**dict(a), "resultado": _dj(a["resultado"])} for a in avaliacoes
        ],
        "decisoes": [dict(d) for d in decisoes],
        "gerado_em": agora(),
    }


def apagar_candidato(org_id: str, candidato_id: str) -> bool:
    """Direito ao esquecimento: remove o registro, as avaliações e o arquivo."""
    curriculo = buscar_curriculo(org_id, candidato_id)
    if not curriculo:
        return False

    vagas_da_org = [
        l["id"] for l in conexao().execute(
            "SELECT id FROM vagas WHERE org_id=?", (org_id,)
        ).fetchall()
    ]
    for vaga_id in vagas_da_org:
        _executar(
            "DELETE FROM avaliacoes WHERE vaga_id=? AND candidato_id=?", (vaga_id, candidato_id)
        )
        _executar(
            "DELETE FROM decisoes WHERE vaga_id=? AND candidato_id=?", (vaga_id, candidato_id)
        )
        _executar(
            "DELETE FROM vaga_curriculos WHERE vaga_id=? AND candidato_id=?",
            (vaga_id, candidato_id),
        )
    _executar(
        "DELETE FROM curriculos WHERE org_id=? AND candidato_id=?", (org_id, candidato_id)
    )
    _apagar_arquivo_orfao(org_id, curriculo.get("origem_hash"), curriculo.get("extensao"))
    return True


def _apagar_arquivo_orfao(org_id: str, origem_hash: Optional[str],
                          extensao: Optional[str]) -> None:
    """Uma planilha vira vários candidatos; o arquivo só sai com o último deles."""
    if not origem_hash:
        return
    ainda_usado = conexao().execute(
        "SELECT 1 FROM curriculos WHERE org_id=? AND origem_hash=? LIMIT 1",
        (org_id, origem_hash),
    ).fetchone()
    if ainda_usado:
        return
    caminho = pasta_org(org_id) / f"{origem_hash}{extensao or ''}"
    try:
        caminho.unlink(missing_ok=True)
    except OSError as exc:                                     # pragma: no cover
        log.warning("não consegui apagar %s: %s", caminho, exc)


def candidatos_vencidos(org_id: str, retencao_dias: int) -> list[str]:
    corte = (datetime.now(timezone.utc) - timedelta(days=retencao_dias)).isoformat()
    linhas = conexao().execute(
        "SELECT candidato_id FROM curriculos WHERE org_id=? AND criado_em < ?",
        (org_id, corte),
    ).fetchall()
    return [l["candidato_id"] for l in linhas]


def organizacoes_ativas() -> list[dict]:
    linhas = conexao().execute(
        "SELECT id, nome, retencao_dias FROM organizacoes WHERE ativa=1"
    ).fetchall()
    return [dict(l) for l in linhas]


def limpar_auditoria_antiga() -> int:
    corte = (datetime.now(timezone.utc) - timedelta(days=AUDITORIA_RETENCAO_DIAS)).isoformat()
    apagadas = _executar("DELETE FROM auditoria WHERE em < ?", (corte,)).rowcount
    _executar("DELETE FROM tentativas_login WHERE em < ?", (corte,))
    return apagadas


def remover_organizacao(org_id: str) -> None:
    """Encerramento de contrato: some tudo, inclusive os arquivos no disco."""
    _executar("DELETE FROM organizacoes WHERE id=?", (org_id,))
    _executar("DELETE FROM auditoria WHERE org_id=?", (org_id,))
    shutil.rmtree(UPLOAD_DIR / org_id, ignore_errors=True)


# ---------- MCP: clientes, códigos e tokens do conector ----------

def mcp_salvar_cliente(client_id: str, dados: dict) -> None:
    _executar(
        """INSERT INTO mcp_clientes (client_id, dados, criado_em) VALUES (?,?,?)
           ON CONFLICT(client_id) DO UPDATE SET dados=excluded.dados""",
        (client_id, _j(dados), agora()),
    )


def mcp_buscar_cliente(client_id: str) -> Optional[dict]:
    linha = conexao().execute(
        "SELECT dados FROM mcp_clientes WHERE client_id=?", (client_id,)
    ).fetchone()
    return _dj(linha["dados"]) if linha else None


def mcp_criar_pedido(pedido_id: str, client_id: str, redirect_uri: str,
                     redirect_explicito: bool, code_challenge: str,
                     state: Optional[str], scopes: Optional[list],
                     recurso: Optional[str], minutos: int) -> None:
    expira = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    _executar(
        """INSERT INTO mcp_pedidos
             (id, client_id, redirect_uri, redirect_explicito, code_challenge,
              state, scopes, recurso, expira_em)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (pedido_id, client_id, redirect_uri, int(redirect_explicito), code_challenge,
         state, _j(scopes or []), recurso, expira.isoformat()),
    )


def mcp_buscar_pedido(pedido_id: str) -> Optional[dict]:
    linha = conexao().execute(
        "SELECT * FROM mcp_pedidos WHERE id=?", (pedido_id,)
    ).fetchone()
    if not linha:
        return None
    pedido = dict(linha)
    if pedido["expira_em"] < agora():
        _executar("DELETE FROM mcp_pedidos WHERE id=?", (pedido_id,))
        return None
    pedido["scopes"] = _dj(pedido["scopes"]) or []
    pedido["redirect_explicito"] = bool(pedido["redirect_explicito"])
    return pedido


def mcp_consumir_pedido(pedido_id: str) -> None:
    _executar("DELETE FROM mcp_pedidos WHERE id=?", (pedido_id,))


def mcp_criar_codigo(codigo: str, client_id: str, usuario_id: str, redirect_uri: str,
                     redirect_explicito: bool, code_challenge: str,
                     scopes: list, recurso: Optional[str], segundos: int = 300) -> None:
    expira = datetime.now(timezone.utc) + timedelta(seconds=segundos)
    _executar(
        """INSERT INTO mcp_codigos
             (codigo, client_id, usuario_id, redirect_uri, redirect_explicito,
              code_challenge, scopes, recurso, expira_em)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (codigo, client_id, usuario_id, redirect_uri, int(redirect_explicito),
         code_challenge, _j(scopes), recurso, expira.isoformat()),
    )


def mcp_buscar_codigo(codigo: str) -> Optional[dict]:
    linha = conexao().execute(
        "SELECT * FROM mcp_codigos WHERE codigo=?", (codigo,)
    ).fetchone()
    if not linha:
        return None
    dados = dict(linha)
    if dados["expira_em"] < agora():
        _executar("DELETE FROM mcp_codigos WHERE codigo=?", (codigo,))
        return None
    dados["scopes"] = _dj(dados["scopes"]) or []
    dados["redirect_explicito"] = bool(dados["redirect_explicito"])
    return dados


def mcp_consumir_codigo(codigo: str) -> Optional[dict]:
    """Busca e apaga numa operação atômica só. Código de autorização é de uso
    único; ler e apagar em dois passos separados abre uma janela onde o mesmo
    código interceptado, usado em paralelo pelo dono e pelo atacante, passa pela
    leitura das duas chamadas antes de qualquer delete confirmar — os dois saem
    com token válido, exatamente o replay que o uso único existe para barrar."""
    with _escrita:
        conn = conexao()
        linha = conn.execute(
            "DELETE FROM mcp_codigos WHERE codigo=? RETURNING *", (codigo,)
        ).fetchone()
        conn.commit()
    if not linha:
        return None
    dados = dict(linha)
    if dados["expira_em"] < agora():
        return None
    dados["scopes"] = _dj(dados["scopes"]) or []
    dados["redirect_explicito"] = bool(dados["redirect_explicito"])
    return dados


def mcp_criar_token(token_hash: str, tipo: str, usuario_id: str,
                    client_id: Optional[str] = None, scopes: Optional[list] = None,
                    recurso: Optional[str] = None, rotulo: str = "",
                    expira_em: Optional[str] = None) -> None:
    _executar(
        """INSERT INTO mcp_tokens
             (token_hash, tipo, client_id, usuario_id, scopes, recurso,
              rotulo, expira_em, criado_em)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (token_hash, tipo, client_id, usuario_id, _j(scopes or []), recurso,
         rotulo, expira_em, agora()),
    )


def mcp_buscar_token(token_hash: str, tipo: Optional[str] = None) -> Optional[dict]:
    sql = """SELECT t.*, u.org_id, u.papel, u.nome, u.email, u.ativo
             FROM mcp_tokens t JOIN usuarios u ON u.id = t.usuario_id
             WHERE t.token_hash=?"""
    parametros: list = [token_hash]
    if tipo:
        sql += " AND t.tipo=?"
        parametros.append(tipo)
    linha = conexao().execute(sql, parametros).fetchone()
    if not linha:
        return None
    dados = dict(linha)
    if dados["expira_em"] and dados["expira_em"] < agora():
        _executar("DELETE FROM mcp_tokens WHERE token_hash=?", (token_hash,))
        return None
    if not dados["ativo"]:
        return None
    dados["scopes"] = _dj(dados["scopes"]) or []
    return dados


def mcp_marcar_uso(token_hash: str) -> None:
    _executar("UPDATE mcp_tokens SET usado_em=? WHERE token_hash=?", (agora(), token_hash))


def mcp_apagar_token(token_hash: str) -> bool:
    return _executar(
        "DELETE FROM mcp_tokens WHERE token_hash=?", (token_hash,)
    ).rowcount > 0


def mcp_consumir_token(token_hash: str, tipo: str) -> Optional[dict]:
    """Busca e apaga numa operação atômica só — usado na rotação de refresh
    token. Ler-depois-apagar em dois passos abre a mesma janela de replay do
    código de autorização: um refresh token roubado, usado ao mesmo tempo pelo
    dono e pelo atacante, sairia válido para os dois. Confere o usuário ativo
    na mesma consulta, como mcp_buscar_token faz."""
    with _escrita:
        conn = conexao()
        linha = conn.execute(
            """DELETE FROM mcp_tokens
                 WHERE token_hash=? AND tipo=?
                   AND EXISTS (SELECT 1 FROM usuarios u
                                WHERE u.id = mcp_tokens.usuario_id AND u.ativo=1)
               RETURNING *""",
            (token_hash, tipo),
        ).fetchone()
        conn.commit()
    if not linha:
        return None
    dados = dict(linha)
    if dados["expira_em"] and dados["expira_em"] < agora():
        return None
    dados["scopes"] = _dj(dados["scopes"]) or []
    return dados


def mcp_listar_tokens(usuario_id: str, tipo: str = "pessoal") -> list[dict]:
    # Vencido não conta: sem este filtro, 5 tokens esquecidos e vencidos travam
    # o limite para sempre — nada além de mcp_buscar_token (por hash exato) os
    # apagava antes.
    linhas = conexao().execute(
        """SELECT token_hash, rotulo, criado_em, usado_em, expira_em
           FROM mcp_tokens WHERE usuario_id=? AND tipo=?
             AND (expira_em IS NULL OR expira_em >= ?)
           ORDER BY criado_em DESC""",
        (usuario_id, tipo, agora()),
    ).fetchall()
    return [dict(l) for l in linhas]


def mcp_revogar_do_usuario(usuario_id: str, tipo: Optional[str] = None) -> int:
    if tipo:
        return _executar(
            "DELETE FROM mcp_tokens WHERE usuario_id=? AND tipo=?", (usuario_id, tipo)
        ).rowcount
    return _executar("DELETE FROM mcp_tokens WHERE usuario_id=?", (usuario_id,)).rowcount


def mcp_limpar_vencidos() -> int:
    momento = agora()
    n = _executar(
        "DELETE FROM mcp_tokens WHERE expira_em IS NOT NULL AND expira_em < ?", (momento,)
    ).rowcount
    _executar("DELETE FROM mcp_codigos WHERE expira_em < ?", (momento,))
    _executar("DELETE FROM mcp_pedidos WHERE expira_em < ?", (momento,))
    return n
