"""Separação determinística de dado pessoal — a que sustenta o fluxo por MCP.

No fluxo por MCP quem avalia é o Claude do conector, e não existe chamada de
parse para separar identificação de conteúdo. Se estas regras falharem, o
avaliador recebe o nome do candidato e a proteção contra viés deixa de existir.
"""
from __future__ import annotations

import re

from .comum import Placar


def rodar(placar: Placar) -> None:
    from app.anonimizacao import parse_deterministico, separar

    print("\nAnonimização determinística")

    CURRICULO = """Mariana Coelho Vasques
mariana.vasques@exemplo.com | (81) 98812-4477 | Recife, PE
linkedin.com/in/mariana-vasques
CPF 123.456.789-01 | Nascimento: 14/03/1991 | 34 anos | Casada, 2 filhos

ANALISTA DE SUPORTE TECNICO N3
Nove anos em suporte de infraestrutura corporativa.

EXPERIENCIA
Analista de Suporte N3 - Nexora Tecnologia (03/2021 - atual)
  Administracao de Active Directory para 900 usuarios.
  Mariana implantou monitoramento com Zabbix.
  Contato do gestor: chefe@nexora.com.br
"""

    def tira_contato():
        s = separar(CURRICULO)
        t = s.texto_anonimo
        assert s.email == "mariana.vasques@exemplo.com", s.email
        assert "98812" in s.telefone, s.telefone
        assert s.cidade == "Recife, PE", s.cidade
        assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", t), "sobrou e-mail no texto"
        assert "98812-4477" not in t, "sobrou telefone"
        assert "123.456.789-01" not in t, "sobrou CPF"
        assert "14/03/1991" not in t, "sobrou data de nascimento"
        assert "linkedin.com/in/mariana" not in t, "sobrou link de perfil"
        return "e-mail, telefone, CPF, nascimento e perfil saem"

    placar.rodar("Contatos e documentos são removidos do texto", tira_contato)

    def tira_nome():
        s = separar(CURRICULO)
        t = s.texto_anonimo
        assert s.nome == "Mariana Coelho Vasques", s.nome
        # inclusive a menção solta no meio do texto, longe do cabeçalho
        for parte in ("Mariana", "Coelho", "Vasques"):
            assert not re.search(rf"\b{parte}\b", t, re.I), f"sobrou '{parte}' no texto"
        assert "[candidato]" in t, "o nome saiu sem deixar a marca no lugar"
        return "nome sai do cabeçalho e do corpo"

    placar.rodar("O nome do candidato desaparece do texto inteiro", tira_nome)

    def preserva_profissional():
        t = separar(CURRICULO).texto_anonimo
        # o que é informação profissional tem de sobreviver
        for termo in ("Nexora Tecnologia", "Active Directory", "Zabbix",
                      "900 usuarios", "03/2021", "Analista de Suporte N3"):
            assert termo in t, f"a anonimização comeu '{termo}'"
        return "empresa, ferramenta, número e data sobrevivem"

    placar.rodar("Informação profissional é preservada", preserva_profissional)

    def dado_sensivel():
        t = separar(CURRICULO).texto_anonimo
        assert "Casada" not in t and "casada" not in t, "sobrou estado civil"
        assert "34 anos" not in t, "sobrou idade"
        assert not re.search(r"\b2 filhos\b", t), "sobrou situação familiar"
        return "idade, estado civil e filhos saem"

    placar.rodar("Dado que a Lei 9.029/95 proíbe usar é removido", dado_sensivel)

    def planilha_rotulada():
        """Linha de ATS vem como 'Nome: Fulano' — sem tratar o rótulo, vazava."""
        linha = (
            "Nome: Adriana Peixoto Villar\n"
            "Email: adriana.villar@exemplo.com\n"
            "Telefone: (11) 99001-2233\n"
            "Cargo atual: Analista de Suporte Pleno\n"
            "Resumo profissional: Seis anos de service desk com SLA de 4h.\n"
        )
        s = separar(linha)
        assert s.nome == "Adriana Peixoto Villar", s.nome
        for parte in ("Adriana", "Peixoto", "Villar"):
            assert parte not in s.texto_anonimo, f"sobrou '{parte}' na linha de planilha"
        assert "Analista de Suporte Pleno" in s.texto_anonimo
        return "o rótulo 'Nome:' é a pista mais confiável e é usada"

    placar.rodar("Linha de planilha de ATS é anonimizada pelo rótulo", planilha_rotulada)

    def nome_nao_encontrado():
        """Currículo que começa direto no texto: o sistema precisa admitir a dúvida."""
        s = separar("Profissional de tecnologia com experiencia em suporte.\n"
                    "Atuei em mesa de ajuda por quatro anos.")
        assert s.confianca_baixa, "não achou o nome e mesmo assim disse estar confiante"
        assert s.avisos, "não avisou que o nome pode ter sobrado"
        return "admite quando não achou o nome, em vez de fingir garantia"

    placar.rodar("Quando o nome não é achado, o sistema avisa", nome_nao_encontrado)

    def nao_confunde_cargo_com_nome():
        s = separar("ANALISTA DE SUPORTE\nJoao Pedro Almeida\njoao@exemplo.com\n")
        assert s.nome == "Joao Pedro Almeida", f"pegou '{s.nome}' como nome"
        return "cabeçalho de cargo não é confundido com nome de pessoa"

    placar.rodar("Cargo no topo não vira nome do candidato", nao_confunde_cargo_com_nome)

    def formato_compativel():
        """O parse determinístico tem de caber onde o parse por IA cabia."""
        from app.models import CurriculoParseado
        dados, sep = parse_deterministico(CURRICULO)
        modelo = CurriculoParseado.model_validate(dados)
        assert modelo.identificacao.nome == "Mariana Coelho Vasques"
        assert modelo.perfil.trecho_bruto == sep.texto_anonimo
        assert "Mariana" not in modelo.perfil.trecho_bruto
        return "valida como CurriculoParseado, igual ao parse por IA"

    placar.rodar("Sai no mesmo formato do parse por IA", formato_compativel)

    def texto_vazio():
        s = separar("")
        assert s.confianca_baixa and s.avisos
        assert s.texto_anonimo == ""
        return "não quebra com currículo vazio"

    placar.rodar("Currículo vazio não derruba a separação", texto_vazio)
