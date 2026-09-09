"""LGPD: exportar, apagar, expurgar por prazo e provar que foi feito."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .comum import Placar


def rodar(placar: Placar) -> None:
    from app import extraction, retencao, storage

    print("\nLGPD")
    storage.iniciar()

    org_id = storage.criar_organizacao("Empresa LGPD")
    usuario_id = storage.criar_usuario(org_id, "dpo@lgpd.com", "DPO", "h", "admin")

    def montar(candidato_id: str, nome: str, email: str, dias_atras: int = 0) -> str:
        doc = extraction.Documento(
            candidato_id=candidato_id, arquivo=f"{candidato_id}.pdf",
            texto="conteudo", origem_hash=f"hash-{candidato_id}", extensao=".pdf",
        )
        storage.salvar_curriculo(org_id, doc)
        storage.salvar_parse(org_id, candidato_id, {
            "identificacao": {"nome": nome, "email": email, "telefone": "81 90000-0000",
                              "cidade": "Recife", "links": []},
            "perfil": {"resumo": "trajetória", "anos_experiencia_total": 5,
                       "experiencias": [], "formacoes": [], "habilidades": [],
                       "idiomas": [], "certificacoes": [], "trecho_bruto": "[candidato]"},
        })
        arquivo = storage.pasta_org(org_id) / f"hash-{candidato_id}.pdf"
        arquivo.write_bytes(b"%PDF-1.7 conteudo de mentira")
        if dias_atras:
            antigo = (datetime.now(timezone.utc) - timedelta(days=dias_atras)).isoformat()
            storage._executar(
                "UPDATE curriculos SET criado_em=? WHERE org_id=? AND candidato_id=?",
                (antigo, org_id, candidato_id),
            )
        return str(arquivo)

    # ---- busca do titular ----
    def busca():
        montar("titular01", "Joana Ribeiro", "joana@exemplo.com")
        montar("titular02", "Carlos Mendes", "carlos@exemplo.com")

        por_nome = storage.procurar_candidatos(org_id, "joana")
        assert len(por_nome) == 1, f"busca por nome achou {len(por_nome)}"
        assert por_nome[0]["nome"] == "Joana Ribeiro"

        por_email = storage.procurar_candidatos(org_id, "carlos@exemplo")
        assert len(por_email) == 1 and por_email[0]["candidato_id"] == "titular02"

        outra_org = storage.criar_organizacao("Empresa vizinha")
        assert storage.procurar_candidatos(outra_org, "joana") == [], (
            "a busca de titular atravessou a fronteira entre contas"
        )
        return "acha por nome e por e-mail, dentro da própria conta"

    placar.rodar("Titular é encontrado por nome ou e-mail", busca)

    # ---- exportação ----
    def exportar():
        vaga_id = storage.criar_vaga(org_id, "Vaga X", "descrição", usuario_id)
        storage.vincular(vaga_id, "titular01")
        storage.salvar_avaliacao(vaga_id, "titular01", estagio="avaliado",
                                 score_final=72.5, recomendacao="chamar",
                                 confianca="alta", resultado={"resumo": "boa trajetória"})
        storage.salvar_decisao(vaga_id, "titular01", "entrevistar", "ligar terça", usuario_id)

        dados = storage.exportar_candidato(org_id, "titular01")
        assert dados is not None
        assert dados["curriculo"]["parse"]["identificacao"]["nome"] == "Joana Ribeiro"
        assert len(dados["avaliacoes"]) == 1, dados["avaliacoes"]
        assert dados["avaliacoes"][0]["vaga_titulo"] == "Vaga X"
        assert dados["avaliacoes"][0]["resultado"]["resumo"] == "boa trajetória"
        assert len(dados["decisoes"]) == 1 and dados["decisoes"][0]["anotacao"] == "ligar terça"
        assert storage.exportar_candidato(org_id, "nao-existe") is None
        return "currículo, avaliações e decisões num pacote só"

    placar.rodar("Exportação entrega tudo que a empresa guarda da pessoa", exportar)

    # ---- exclusão ----
    def apagar():
        from pathlib import Path
        caminho = Path(montar("apagavel01", "Pedro Alves", "pedro@exemplo.com"))
        vaga_id = storage.criar_vaga(org_id, "Vaga Y", "descrição", usuario_id)
        storage.vincular(vaga_id, "apagavel01")
        storage.salvar_avaliacao(vaga_id, "apagavel01", estagio="avaliado",
                                 score_final=50.0, recomendacao="talvez")
        storage.salvar_decisao(vaga_id, "apagavel01", "reserva", "", usuario_id)
        assert caminho.exists(), "o arquivo de teste não foi criado"

        assert storage.apagar_candidato(org_id, "apagavel01") is True
        assert storage.buscar_curriculo(org_id, "apagavel01") is None
        assert not caminho.exists(), "o arquivo original continuou no disco"

        rank = storage.ranking(org_id, vaga_id)
        assert all(r["candidato_id"] != "apagavel01" for r in rank), (
            "a avaliação sobreviveu à exclusão do candidato"
        )
        assert storage.apagar_candidato(org_id, "apagavel01") is False
        return "some do banco e do disco, em todas as vagas"

    placar.rodar("Exclusão do titular limpa banco, avaliações e arquivo", apagar)

    # ---- arquivo compartilhado por várias linhas de planilha ----
    def planilha_compartilhada():
        from pathlib import Path
        arquivo = storage.pasta_org(org_id) / "hash-planilha.xlsx"
        arquivo.write_bytes(b"PK\x03\x04planilha")
        for i in (1, 2):
            doc = extraction.Documento(
                candidato_id=f"linha0{i}", arquivo=f"planilha · linha {i}",
                texto="dados", origem="planilha",
                origem_hash="hash-planilha", extensao=".xlsx",
            )
            storage.salvar_curriculo(org_id, doc)

        storage.apagar_candidato(org_id, "linha01")
        assert arquivo.exists(), (
            "a planilha foi apagada com o primeiro candidato, deixando o segundo sem origem"
        )
        storage.apagar_candidato(org_id, "linha02")
        assert not arquivo.exists(), "a planilha ficou órfã no disco"
        return "o arquivo só sai com o último candidato que o usa"

    placar.rodar("Planilha compartilhada só é apagada com o último candidato",
                 planilha_compartilhada)

    # ---- expurgo por retenção ----
    def expurgo():
        from pathlib import Path
        recente = Path(montar("recente01", "Nova Pessoa", "nova@exemplo.com", dias_atras=10))
        antigo = Path(montar("antigo01", "Velha Inscrição", "velha@exemplo.com",
                             dias_atras=400))

        vencidos = storage.candidatos_vencidos(org_id, 180)
        assert "antigo01" in vencidos, vencidos
        assert "recente01" not in vencidos, vencidos

        org = storage.buscar_organizacao(org_id)
        org["retencao_dias"] = 180
        apagados = retencao.expurgar_organizacao(org)
        assert apagados >= 1, f"o expurgo não apagou nada ({apagados})"
        assert storage.buscar_curriculo(org_id, "antigo01") is None
        assert storage.buscar_curriculo(org_id, "recente01") is not None, (
            "o expurgo levou junto um currículo dentro do prazo"
        )
        assert not antigo.exists() and recente.exists()
        return f"{apagados} currículo(s) vencido(s) apagado(s)"

    placar.rodar("Expurgo apaga o que passou do prazo e poupa o resto", expurgo)

    # ---- auditoria ----
    def auditoria():
        storage.registrar_auditoria(org_id, usuario_id, "lgpd.exclusao", "candidato",
                                    "apagavel01", {"arquivo": "apagavel01.pdf"},
                                    ip="10.0.0.9")
        registros = storage.listar_auditoria(org_id, 50)
        acoes = [r["acao"] for r in registros]
        assert "lgpd.exclusao" in acoes, acoes[:5]
        assert "retencao.expurgo" in acoes, "o expurgo automático não deixou registro"

        exclusao = next(r for r in registros if r["acao"] == "lgpd.exclusao")
        assert exclusao["usuario_nome"] == "DPO"
        assert exclusao["detalhe"]["arquivo"] == "apagavel01.pdf"
        assert exclusao["ip"] == "10.0.0.9"

        outra = storage.criar_organizacao("Sem auditoria")
        assert storage.listar_auditoria(outra, 50) == [], (
            "o registro de uma conta apareceu na outra"
        )
        return f"{len(registros)} eventos registrados"

    placar.rodar("Toda ação sobre dado pessoal fica registrada", auditoria)
