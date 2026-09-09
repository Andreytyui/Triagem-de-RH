# LGPD — o que o sistema faz, e o que ainda é com você

Currículo é dado pessoal, e parte dele é sensível (às vezes traz foto, estado civil, dados de
saúde numa carta de apresentação). A Lei 13.709/2018 se aplica do primeiro upload em diante.

Este documento descreve o que o software já resolve e o que continua sendo responsabilidade
de quem o opera. **Não é parecer jurídico.** Antes de vender ou usar em produção, leve este
texto a um advogado e adapte ao seu contrato.

**Nota de estado (2026-09-09):** o dono do produto decidiu conscientemente pular essa revisão
por advogado por agora e não tratar isso como bloqueador de venda ou de entrega — risco
assumido, sabendo exatamente que nada aqui é parecer jurídico (`backlog-priorizado` § "Risco
aceito conscientemente pelo dono do produto"). Isso não muda a ressalva acima nem o
tratamento deste documento daqui pra frente: ele continua sendo mantido e atualizado, para
que a revisão seja rápida quando for retomada — só deixou de ser uma pendência ativa
esperando resposta urgente.

---

## Quem é quem

**Atualizado (2026-09-09) para o pivô "modo API fora do produto" registrado em
`decisoes-dono-produto` e `backlog-priorizado`.** O motor de avaliação hoje é
exclusivamente o conector (MCP), em dois transportes com papéis jurídicos diferentes —
não escolha um só quadro para os dois.

| Papel na lei | Modo hospedado (HTTP+OAuth — claude.ai/ChatGPT) | Modo local (stdio — Claude Desktop) |
|---|---|---|
| **Titular** | O candidato que enviou o currículo | idem |
| **Controlador** | A empresa que abriu a vaga e opera a conta | A mesma empresa — aqui ela acumula os dois papéis |
| **Operador** | Você, que hospeda o serviço (SaaS multi-empresa) | Ninguém além do próprio cliente: você é só fornecedor de software, não opera dado nenhum |

No modo hospedado você **é** operador e precisa de contrato com cada empresa cliente
definindo escopo, finalidade e prazo — é o cenário que o rascunho de contrato mais abaixo
foi pensado para cobrir. No modo local, o cliente instala na própria máquina, é controlador
e operador ao mesmo tempo, e o contrato de operador **não se aplica** — confirmado pelo dono
do produto em 2026-09-09 (`REVISAO-JURIDICA.md` §5, pergunta 8): nesse modo é 100%
responsabilidade de quem instala, sem contrato de operador nem aviso de privacidade
fornecido por você.

**Decisão do dono do produto (2026-09-09), recomendação pendente de confirmação final do
advogado — `REVISAO-JURIDICA.md` §5, pergunta 7:** em ambos os modos, quem processa o texto
anonimizado do currículo é o Claude ou o ChatGPT **da assinatura do próprio recrutador**,
não uma chave de API paga por você (ver seção seguinte). A leitura adotada é que a
Anthropic/OpenAI **não** é suboperadora sua — é vínculo direto entre o cliente e o provedor
de IA que ele escolheu, contratado e mantido por ele. Você não responde por esse provedor
perante o cliente; atua só como fornecedor do dado anonimizado e da infraestrutura do
conector. Já refletido no esqueleto de contrato em `REVISAO-JURIDICA.md`.

---

## Ciclo de vida do dado

**Entrada.** O recrutador envia os currículos. O arquivo original é gravado em
`data/uploads/<organização>/`, com o nome derivado do hash do conteúdo. O texto extraído vai
para o banco.

**Separação.** No estágio de parse, os dados de identificação — nome, e-mail, telefone,
cidade, links — são separados do conteúdo profissional. O prompt manda remover também idade,
data de nascimento, estado civil, gênero, CPF, RG, foto, nome de cônjuge e filhos, e menção a
raça, religião ou deficiência.

**Avaliação.** Os estágios de pré-filtro e pontuação recebem **apenas o perfil anonimizado**.
O modelo que dá as notas não vê quem é a pessoa. Isso não é só privacidade: é o que sustenta
a defesa contra alegação de discriminação, porque o avaliador não tinha acesso à informação
que discriminaria.

**Saída.** Nome e contato voltam a aparecer só na tela do recrutador, no CSV e no relatório —
depois que a nota já foi dada.

**Eliminação.** Passado o prazo de retenção da organização, um processo automático apaga o
registro e o arquivo. Antes disso, qualquer pedido do titular pode ser atendido na hora.

---

## Quem processa o texto do currículo, e para onde ele vai

**Reescrito (2026-09-09) — o parágrafo antigo descrevia o modo API (funil próprio, chave
paga por vocês), que saiu de escopo. Isto substitui aquele texto.**

Não existe mais chamada de API paga por vocês. Quem lê o currículo e dá a nota é o
**Claude ou o ChatGPT da própria assinatura do recrutador**, através do conector (MCP) —
Claude Desktop por stdio, ou claude.ai/ChatGPT por HTTP com OAuth. O texto que cruza essa
fronteira já saiu anonimizado por regra (`anonimizacao.py`) antes de qualquer coisa — nome,
e-mail, telefone, CPF, RG, CEP, data de nascimento, idade, estado civil, filhos e links de
perfil ficam de fora. Currículo escaneado passa por OCR local (Tesseract) no próprio
servidor antes disso — a imagem do arquivo nunca é enviada a nenhum provedor de IA.

Mesmo anonimizado, o texto ainda sai do Brasil: para servidores da Anthropic quando o
conector é o Claude, e para servidores da OpenAI quando o conector é o ChatGPT. Duas
consequências práticas, agora com uma variável a mais em relação ao rascunho anterior:

1. **Transferência internacional** (art. 33) continua existindo, e agora para até dois
   provedores diferentes, não um só. Confirmado pelo dono do produto (2026-09-09): os dois
   são oficiais — Claude (Anthropic) e ChatGPT (OpenAI). O aviso de privacidade abaixo já
   previa essa possibilidade nos colchetes; mantenha só o provedor que o cliente de fato usa.
2. **Contrato com o operador.** Decidido (2026-09-09, recomendação pendente de confirmação
   final do advogado): o vínculo de processamento é direto entre o cliente e a
   Anthropic/OpenAI (pela conta que ele mesmo mantém) — não entra no contrato como
   suboperadora sua. Texto já refletido no esqueleto de contrato em `REVISAO-JURIDICA.md`.

Se o cliente não puder aceitar transferência internacional para nenhum desses provedores,
este produto não serve para ele. É melhor descobrir isso na proposta do que depois.

---

## Direitos do titular — o que já está pronto

| Direito (art. 18) | Onde fica |
|---|---|
| Confirmação e acesso | Aba **Dados** → buscar por nome, e-mail ou telefone |
| Cópia dos dados | Botão **Exportar** — devolve JSON com currículo, avaliações e decisões |
| Eliminação | Botão **Apagar** — remove banco, avaliações, decisões e arquivo original |
| Informação sobre uso compartilhado | Este documento, mais o aviso de privacidade |
| Revisão de decisão automatizada (art. 20) | A decisão final é sempre humana; a nota vem com evidência citada |

O art. 20 é o mais relevante para este produto. A defesa dele aqui é estrutural, não
declaratória: o sistema **não decide**, ele ordena e justifica. A recomendação é apoio; a
marcação *entrevistar / reserva / arquivado* é feita por uma pessoa, fica registrada com o
nome de quem marcou, e o relatório mostra a evidência de cada nota.

**Não desligue isso.** Se você automatizar o descarte, perde essa defesa.

---

## Retenção

Configurável por organização em **Configurações → Retenção de currículos**, entre 7 e 1825
dias. O padrão é 180.

O expurgo roda ao subir o servidor e a cada 12 horas. Ele apaga o currículo, as avaliações,
as decisões e o arquivo no disco. O registro de auditoria de que a exclusão aconteceu
permanece — sem o dado pessoal, só o evento.

Como escolher o prazo:

- **90 dias** — só o processo seletivo em curso. Mais seguro, obriga a repedir currículo.
- **180 dias** — cobre o processo e o banco de talentos de curto prazo. É o padrão.
- **12 meses** — banco de talentos de verdade. Exige consentimento específico do candidato
  para essa finalidade, e o aviso de privacidade tem de dizer isso com todas as letras.

---

## Base legal

O sistema registra **legítimo interesse em processo seletivo** (art. 7º, IX) como base padrão,
que é a leitura usual para currículo enviado espontaneamente a uma vaga aberta.

Duas ressalvas que valem dinheiro:

- Legítimo interesse exige **teste de proporcionalidade** documentado e um canal de oposição.
  O canal existe (a aba Dados); o documento é com o cliente.
- Guardar currículo **depois** que a vaga fechou, para futuras oportunidades, já não cabe em
  legítimo interesse com conforto. Aí é **consentimento** (art. 7º, I), coletado no momento
  da inscrição, específico para essa finalidade e revogável.

---

## Segurança (art. 46)

O que está implementado:

- Senha com PBKDF2-HMAC-SHA256, 600 mil iterações e sal por senha
- Sessão com cookie `HttpOnly`/`SameSite`, token guardado só como hash
- Proteção CSRF por dupla submissão em toda escrita
- Freio de força bruta no login
- Isolamento por organização em toda consulta ao banco
- Backup de `data/` cifrado em repouso (scrypt + Fernet), com restauração testada
- Auditoria de acesso, exportação e exclusão, guardada por 2 anos
- Cabeçalhos de segurança e nenhuma resposta de API cacheável

**Atualizado (2026-09-09):** este parágrafo dizia "o que você precisa providenciar" tratando
"você" como se fosse sempre o cliente rodando a própria instância. Com a decisão de vender
como SaaS hospedado centralmente (`decisoes-dono-produto`, item 5), isso deixou de ser
verdade para a maior parte dos clientes — no modo hospedado, é você (dono do produto) quem
precisa providenciar a lista abaixo, não o cliente. No modo local (stdio, cliente rodando a
própria máquina), a lista continua sendo responsabilidade do cliente, como estava escrita.

**Modo hospedado (SaaS) — responsabilidade de vocês:**

- **HTTPS.** Sem ele, senha e currículo trafegam em claro. Proxy com TLS na frente e
  `COOKIE_SEGURO=true` ligado.
- **Backup cifrado** de `data/`, guardado em lugar diferente do servidor, com restauração
  testada — isso deixou de ser "bom ter": é bloqueador de venda registrado em
  `backlog-priorizado` (item 6), porque agora é dado de várias empresas num só lugar.
- **Controle de quem tem acesso ao servidor.** O banco não é cifrado em repouso; quem tem o
  disco tem os currículos de todos os clientes hospedados. Disco cifrado na VPS/infra.
- **Plano de resposta a incidente.** O art. 48 exige comunicação à ANPD e aos titulares em
  caso de vazamento com risco relevante. Tenha o texto pronto antes de precisar dele — e
  decida o prazo que o contrato vai prometer ao cliente (ver `REVISAO-JURIDICA.md`).

**Modo local (stdio) — continua responsabilidade do cliente,** pelas mesmas razões de
sempre: é ele quem roda o servidor na própria máquina.

---

## Aviso de privacidade — rascunho para o candidato

Adapte e publique junto ao formulário de inscrição. **Revise com advogado.**

> **Como tratamos seu currículo**
>
> Ao se candidatar, seu currículo é analisado por [EMPRESA] com apoio de um sistema
> automatizado de triagem, que pontua sua experiência contra os critérios definidos para
> esta vaga.
>
> **O que fazemos.** O texto do seu currículo é processado por um serviço de inteligência
> artificial ([Claude, da Anthropic, Estados Unidos / ChatGPT, da OpenAI, Estados Unidos —
> manter apenas o que a EMPRESA realmente usa]) para estruturar sua experiência e compará-la
> aos critérios da vaga. Antes dessa comparação, seus dados de identificação — nome, contato,
> endereço, idade — são separados e **não** são usados na avaliação. Se o seu currículo foi
> enviado como imagem escaneada, o texto é primeiro extraído por um programa de OCR rodando
> nos nossos servidores, sem envio da imagem a nenhum serviço externo.
>
> **A decisão é humana.** O sistema produz uma nota e uma justificativa. Quem decide chamar,
> manter em reserva ou arquivar é um recrutador de [EMPRESA].
>
> **Por quanto tempo.** Guardamos seu currículo por até [PRAZO] dias, contados do envio,
> após o que ele é eliminado automaticamente.
>
> **Base legal.** Legítimo interesse na condução deste processo seletivo (art. 7º, IX, da
> Lei 13.709/2018).
>
> **Seus direitos.** Você pode pedir acesso, correção ou eliminação dos seus dados, e se opor
> ao tratamento, escrevendo para [E-MAIL DO ENCARREGADO]. Responderemos em até 15 dias.

---

## Checklist antes de vender

**Deixou de travar venda/entrega por decisão consciente do dono do produto (2026-09-09) —
ver nota de estado no topo do documento.** A lista abaixo continua valendo como referência do
que falta para a revisão jurídica de verdade, mantida atualizada, só sem urgência de bloqueio.

- [ ] Contrato de operador **redigido** (esqueleto quase completo em `REVISAO-JURIDICA.md`,
      com as respostas do dono do produto de 2026-09-09 — falta só razão social/CNPJ e
      endereço da contratada para fechar a minuta) e assinado com cada empresa cliente
- [ ] Aviso de privacidade publicado no formulário de inscrição do cliente, nomeando o(s)
      provedor(es) de IA realmente oferecidos (ver seção acima — já cobre Claude e ChatGPT)
- [ ] Texto da tela de autorização do conector MCP (`/mcp/consentir`) corrigido — hoje diz
      "o Claude vai poder..." mesmo quando quem está autorizando é o ChatGPT, e não menciona
      a transferência internacional no momento em que o recrutador efetivamente autoriza.
      Especificação já enviada a Vitral/Pigmento (`REVISAO-JURIDICA.md` §7)
- [ ] Prazo de retenção definido e configurado na conta
- [ ] Encarregado (DPO) indicado — formato decidido (e-mail de função), falta o domínio
      existir para publicar o endereço final
- [ ] HTTPS ativo e `COOKIE_SEGURO=true` (responsabilidade de vocês no modo hospedado — ver
      seção Segurança)
- [ ] Backup cifrado funcionando, com restauração testada pelo menos uma vez (bloqueador de
      venda ativo, `backlog-priorizado` item 6)
- [ ] Transferência internacional declarada ao candidato, nomeando os provedores corretos
- [ ] Plano de resposta a incidente escrito — prazo de notificação ao cliente já decidido
      (72h, `REVISAO-JURIDICA.md` §5)
- [ ] Provedor de e-mail (recuperação de senha) escolhido e mapeado como suboperador —
      ainda bloqueado, decisão técnica separada
- [ ] Razão social, CNPJ e endereço da contratada definidos (bloqueador para fechar o
      contrato — `REVISAO-JURIDICA.md` §6)
- [ ] Este documento e o contrato de operador revisados por advogado
