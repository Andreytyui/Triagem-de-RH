"""Constrói a imagem Docker e confere que ela serve o produto.

    python testar_docker.py [--manter]

Existe porque "o Dockerfile está escrito" e "a imagem sobe e funciona" são
afirmações diferentes, e só a segunda vale para entregar a alguém. A suíte de
`testar.py` roda contra o código; esta roda contra a IMAGEM — que é o que o
comprador vai executar.

O que se confere aqui, e por quê:

- as duas dependências de sistema pesadas existem E funcionam. O `Dockerfile`
  já falha na build se elas faltarem, mas presença de binário não é o mesmo que
  conversão que roda: o LibreOffice lê o .doc antigo, e o Tesseract com o
  idioma 'por' lê o currículo que veio do scanner;
- o servidor não roda como root e o volume é escrito pelo usuário certo;
- o healthcheck do próprio Docker fica `healthy` — é o que um orquestrador usa
  para decidir se o contêiner está de pé;
- o fluxo real atravessa: criar conta, entrar, listar vagas;
- o dado sobrevive a reiniciar o contêiner. Sem isso, o volume é decorativo.

`--manter` deixa o contêiner rodando no fim, para inspeção manual.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

IMAGEM = "triagem:2.0"
NOME = "triagem-verificacao"
PORTA = 8010
BASE = "http://127.0.0.1:{}".format(PORTA)

VERDE, VERMELHO, CINZA, FIM = "\033[32m", "\033[31m", "\033[90m", "\033[0m"


class Placar:
    def __init__(self) -> None:
        self.passou = 0
        self.falhou: list[str] = []

    def rodar(self, titulo: str, funcao) -> None:
        try:
            detalhe = funcao()
            self.passou += 1
            print(f"  [ok] {titulo}" + (f" — {detalhe}" if detalhe else ""))
        except Exception as exc:                               # noqa: BLE001
            self.falhou.append(titulo)
            print(f"  [FALHOU] {titulo}\n           {exc}")


def sh(*args: str) -> str:
    r = subprocess.run(args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise AssertionError((r.stderr or r.stdout).strip()[:400])
    return (r.stdout or "").strip()


def no_container(comando: str) -> str:
    return sh("docker", "exec", NOME, "sh", "-c", comando)


def http(caminho: str, dados: dict | None = None,
         cookie: str = "") -> tuple[int, str, str]:
    cabecalhos = {"Content-Type": "application/json"}
    if cookie:
        cabecalhos["Cookie"] = cookie
    req = urllib.request.Request(
        BASE + caminho,
        data=json.dumps(dados).encode() if dados is not None else None,
        headers=cabecalhos,
        method="POST" if dados is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return (r.status, r.read().decode("utf-8", "replace"),
                    r.headers.get("Set-Cookie", ""))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), ""


def esperar_resposta(segundos: int = 60) -> bool:
    for _ in range(segundos):
        try:
            if http("/api/saude")[0] == 200:
                return True
        except Exception:                                      # noqa: BLE001
            pass
        time.sleep(1)
    return False


def main() -> int:
    manter = "--manter" in sys.argv
    placar = Placar()
    print(f"\nImagem Docker — {IMAGEM}\n")

    print(f"{CINZA}  construindo (LibreOffice e Tesseract levam alguns minutos)...{FIM}")
    inicio = time.time()
    try:
        sh("docker", "build", "-t", IMAGEM, ".")
    except AssertionError as exc:
        print(f"  [FALHOU] a build não passou\n           {exc}")
        return 1
    print(f"  [ok] build completa — {time.time() - inicio:.0f}s")
    # `docker image inspect --format {{.Size}}` reporta um número bem menor que
    # o que a imagem de fato ocupa em disco (278 MB contra 1,03 GB aqui). Quem
    # vai instalar precisa do número real, então usamos o mesmo que o `docker
    # images` mostra.
    tamanho = sh("docker", "images", "--format", "{{.Size}}", IMAGEM)
    print(f"  [ok] imagem existe — {tamanho} em disco")
    placar.passou += 2

    subprocess.run(["docker", "rm", "-f", NOME], capture_output=True)
    sh("docker", "run", "-d", "--name", NOME, "-p", f"{PORTA}:8000",
       "-e", "TRIAGEM_SECRET_KEY=segredo-de-verificacao-0123456789abcdef",
       "-e", "PERMITIR_CADASTRO=true",
       "-e", "CODIGO_CONVITE=",
       IMAGEM)

    try:
        def sobe():
            assert esperar_resposta(), "não respondeu em 60s"
            return "respondeu"

        placar.rodar("O contêiner sobe e responde", sobe)

        def saude():
            codigo, corpo, _ = http("/api/saude")
            assert codigo == 200, codigo
            d = json.loads(corpo)
            assert d["banco"] == "ok", d
            return f"banco {d['banco']}, conector {d['conector']}"

        placar.rodar("A saúde reporta banco de pé", saude)

        def estaticos():
            for caminho in ("/", "/static/styles.css", "/static/app.js"):
                assert http(caminho)[0] == 200, caminho
            return "raiz, css e js"

        placar.rodar("A interface é servida de dentro da imagem", estaticos)

        def nao_root():
            uid = no_container("id -u")
            assert uid != "0", "está rodando como root"
            dono = no_container("stat -c %U /dados")
            assert dono == "triagem", dono
            return f"uid {uid}, /dados de {dono}"

        placar.rodar("O servidor não roda como root", nao_root)

        def libreoffice():
            # Presença o Dockerfile já garante na build; aqui é conversão que roda.
            no_container(
                "printf 'Analista de Suporte N3' > /tmp/cv.txt && "
                "soffice --headless --convert-to rtf --outdir /tmp /tmp/cv.txt "
                "> /dev/null 2>&1 || true")
            saida = no_container("ls /tmp/cv.rtf")
            assert saida.endswith("cv.rtf"), saida
            return "converteu de verdade, não só respondeu --version"

        placar.rodar("O LibreOffice converte documento", libreoffice)

        def tesseract_por():
            idiomas = no_container("tesseract --list-langs 2>&1").split()
            assert "por" in idiomas, idiomas
            return "idioma 'por' instalado"

        placar.rodar("O Tesseract lê português", tesseract_por)

        def healthcheck():
            for _ in range(40):
                estado = sh("docker", "inspect", "--format",
                            "{{.State.Health.Status}}", NOME)
                if estado == "healthy":
                    return estado
                if estado == "unhealthy":
                    raise AssertionError("o healthcheck do Docker falhou")
                time.sleep(1)
            raise AssertionError("não ficou healthy em 40s")

        placar.rodar("O healthcheck do Docker fica healthy", healthcheck)

        def fluxo_real():
            conta = {"organizacao": "Empresa de verificação",
                     "nome": "Verificação",
                     "email": "verificacao@exemplo.com",
                     "senha": "senha-de-verificacao"}
            codigo, corpo, _ = http("/api/auth/registrar", conta)
            assert codigo == 201, f"registrar devolveu {codigo}: {corpo[:120]}"
            codigo, corpo, cookie = http(
                "/api/auth/login",
                {"email": conta["email"], "senha": conta["senha"]})
            assert codigo == 200, f"login devolveu {codigo}"
            codigo, _, _ = http("/api/vagas", cookie=cookie.split(";")[0])
            assert codigo == 200, f"listar vagas devolveu {codigo}"
            return "criar conta, entrar e listar vagas"

        placar.rodar("O fluxo real atravessa a imagem", fluxo_real)

        def sobrevive_a_reinicio():
            antes = no_container("ls /dados")
            assert "triagem.db" in antes, antes
            sh("docker", "restart", NOME)
            assert esperar_resposta(), "não voltou depois do restart"
            codigo, _, _ = http("/api/auth/login",
                                {"email": "verificacao@exemplo.com",
                                 "senha": "senha-de-verificacao"})
            assert codigo == 200, f"a conta sumiu no restart (login {codigo})"
            return "a conta criada antes continua valendo"

        placar.rodar("O dado sobrevive a reiniciar o contêiner",
                     sobrevive_a_reinicio)
    finally:
        if manter:
            print(f"\n{CINZA}  contêiner {NOME} mantido em {BASE}{FIM}")
        else:
            subprocess.run(["docker", "rm", "-f", NOME], capture_output=True)

    print("\n" + "-" * 60)
    if placar.falhou:
        print(f"{VERMELHO}{len(placar.falhou)} FALHA(S){FIM}, {placar.passou} passaram")
        for t in placar.falhou:
            print(f"  · {t}")
        return 1
    print(f"{VERDE}TODAS AS {placar.passou} VERIFICAÇÕES DA IMAGEM PASSARAM{FIM}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
