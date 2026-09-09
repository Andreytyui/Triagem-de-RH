# Revisão jurídica — material preparado para o advogado

Preparado por Toga (jurídico) em 2026-09-09, a partir de `LGPD.md`, `triagem-documento-tecnico`,
`decisoes-dono-produto` e `backlog-priorizado` (item 7: contrato de operador e aviso de
privacidade — inicialmente bloqueador de venda, ver nota de estado abaixo).

**Isto não é parecer jurídico e não substitui a revisão de um advogado licenciado antes de
vender ou operar em produção.** O objetivo deste documento é o oposto de pular essa revisão:
organizar o que já existe, apontar lacunas óbvias e isolar as decisões que só o dono do
produto pode tomar — para que quando um advogado entrar, o trabalho dele seja rápido e
barato, e não uma reconstrução do zero. Nada aqui está "fechado" ou "pronto para produção".

**Nota de estado (2026-09-09):** o dono do produto decidiu conscientemente pular a revisão
por advogado por agora e não tratar o item 7 como bloqueador de venda ou entrega — risco
assumido, sabendo exatamente que este documento não é parecer jurídico
(`backlog-priorizado` § "Risco aceito conscientemente pelo dono do produto"). Isto **não**
muda o disclaimer acima nem o cuidado no texto — muda só a urgência: o material segue sendo
mantido e atualizado (inclusive os 4 fatos pendentes do §6 e as perguntas novas do
`TERMOS-DE-USO.md`), mas deixou de ser tratado como pendência ativa aguardando resposta
urgente. Se ele mudar de ideia, o trabalho de reabrir isso é ler este documento atualizado,
não recomeçar do zero.

---

## 1. Índice do material jurídico que já existe

| Documento | O que cobre | Estado |
|---|---|---|
| `LGPD.md` | Ciclo de vida do dado, papéis (titular/controlador/operador), rascunho de aviso de privacidade, checklist de venda | Atualizado hoje para refletir o pivô "modo API fora" (`decisoes-dono-produto`) — ver §2 |
| `LGPD.md` § Aviso de privacidade | Rascunho do texto que o candidato lê ao se inscrever | Rascunho existe, precisa dos colchetes preenchidos e de decisão sobre quais provedores de IA nomear |
| `LGPD.md` § Checklist antes de vender | Lista do que falta antes de vender | Existe, atualizada hoje |
| **Contrato de operador** | — | **Não existe rascunho nenhum ainda.** O único registro anterior era um item de checklist ("contrato assinado") e uma frase no documento técnico dizendo que precisa existir. Esqueleto novo em §3 abaixo |
| **Termos de uso do software** (`TERMOS-DE-USO.md`) | Uso do produto pela empresa cliente (conta, planos, propriedade intelectual, rescisão) — separado do contrato de operador (dado pessoal) e do aviso de privacidade (candidato) | Rascunho iniciado em 2026-09-09, por pedido direto do dono do produto. Reaproveita as decisões já tomadas para o contrato de operador; levanta 4 perguntas novas, específicas de ToS (ver `TERMOS-DE-USO.md` §13) |
| `app/rotas_mcp.py` (`/mcp/consentir`) | Texto da tela de autorização do conector MCP | Existe e funciona, mas tem um problema de precisão que vira problema jurídico — ver §4 |

---

## 2. O que mudou desde a última vez que alguém pensou nisso juridicamente

A decisão estrutural registrada em `decisoes-dono-produto` — modo API sai do produto, motor
passa a ser exclusivamente o conector (MCP), com dois transportes (stdio local / HTTP+OAuth
hospedado) — muda fatos que o rascunho anterior de `LGPD.md` dava como certos:

1. **Não existe mais um único operador de IA fixo (Anthropic via chave paga por vocês).**
   Quem processa o currículo anonimizado é a assinatura Claude **ou** ChatGPT do próprio
   recrutador. Isso significa até dois provedores possíveis (Anthropic e OpenAI), não um.
2. **Dois modos de implantação com papéis jurídicos diferentes.** No modo hospedado
   (HTTP+OAuth, SaaS multi-empresa) vocês são operador. No modo local (stdio, cliente roda a
   própria máquina) o cliente é controlador e operador ao mesmo tempo, e vocês são só
   fornecedor de software — o contrato de operador provavelmente não se aplica a esse modo.
3. **A hospedagem central deixou de ser hipótese e virou plano de venda confirmado**
   (`decisoes-dono-produto` item 5, `backlog-priorizado` item 6). Isso aumenta o peso real das
   cláusulas de segurança/backup/incidente no contrato: o dado de várias empresas passa a
   ficar num lugar só, sob a guarda de vocês.
4. **PDF escaneado não usa mais visão via API.** Passa por OCR local (Tesseract). A imagem do
   currículo nunca sai para nenhum provedor de IA — isso é uma melhora de privacidade em
   relação ao desenho anterior, vale mencionar como ponto positivo ao cliente.

`LGPD.md` já foi atualizado hoje para refletir os pontos 1, 2 e 3 nas seções "Quem é quem",
"Quem processa o texto do currículo, e para onde ele vai" e "Segurança". O que ficou em
aberto lá — porque não é uma correção factual, é uma escolha de risco — está isolado nas
perguntas do §5.

---

## 3. Rascunho — esqueleto do contrato de operador

**Isto é um esqueleto, não um contrato pronto para assinar.** Ele organiza as cláusulas que
um contrato de operador para este produto precisa ter, na estrutura que a LGPD e a prática de
mercado esperam. Cobre o **modo hospedado** — o modo local não usa este contrato (pergunta 8,
respondida, ver §5). Atualizado em 2026-09-09 com as respostas do dono do produto.

**Convenção usada abaixo:** `[RECOMENDAÇÃO — DONO DO PRODUTO, PENDENTE DE CONFIRMAÇÃO FINAL
DO ADVOGADO]` marca texto que já tem uma direção decidida, mas que ainda não foi validado por
advogado — não é o mesmo que "fechado". `[BLOQUEADO]` marca o que continua sem resposta real.

```
CONTRATO DE OPERAÇÃO DE DADOS PESSOAIS

1. PARTES
   CONTRATANTE (controladora): [empresa cliente, qualificação completa]
   CONTRATADA (operadora): [RAZÃO SOCIAL / CNPJ — BLOQUEADO, pergunta 1, §5. Se ainda não
   existe CNPJ constituído, isso precisa ser resolvido antes deste contrato poder existir]
   Endereço da CONTRATADA: [BLOQUEADO, pergunta 2, §5 — depende de 1]

2. OBJETO
   Prestação do serviço "Triagem" — leitura, estruturação e pontuação de currículos
   recebidos pela CONTRATANTE em processos seletivos, incluindo hospedagem dos dados,
   nos termos descritos em [ANEXO TÉCNICO — pode reaproveitar a seção "Ciclo de vida do
   dado" de LGPD.md].

3. PAPÉIS E RESPONSABILIDADES (art. 39, LGPD)
   A CONTRATANTE é controladora dos dados pessoais dos candidatos.
   A CONTRATADA é operadora, e trata os dados exclusivamente conforme instruções
   documentadas da CONTRATANTE e para a finalidade deste contrato.

   [RECOMENDAÇÃO — DONO DO PRODUTO, PENDENTE DE CONFIRMAÇÃO FINAL DO ADVOGADO — pergunta 7,
   §5. Decisão: vínculo direto entre CONTRATANTE e provedor de IA, não suboperação da
   CONTRATADA. Justificativa registrada: no modo conector é a assinatura do próprio
   recrutador processando direto com o provedor dele; o Triagem nunca processa nada através
   da conta desses provedores nesse modo.]

   O processamento de pontuação dos currículos é realizado pela conta/assinatura da própria
   CONTRATANTE junto à Anthropic (Claude) e/ou OpenAI (ChatGPT), contratada e mantida
   diretamente pela CONTRATANTE — a CONTRATADA não é parte dessa relação e não a subcontrata
   como suboperadora. A CONTRATADA atua somente como fornecedora de dado anonimizado e da
   infraestrutura de conector (MCP), sem transmitir ou processar o conteúdo por conta própria
   nessa etapa. A CONTRATANTE reconhece que a escolha de conector (Claude e/ou ChatGPT, ver
   cláusula 8) implica sua própria relação contratual e de transferência internacional com o
   respectivo provedor, independente deste contrato.

4. ESCOPO DE DADOS E FINALIDADE
   Dados tratados: [reaproveitar tabela de dados de LGPD.md — nome, e-mail, telefone,
   currículo, avaliações, decisões, dados de auditoria].
   Finalidade: exclusivamente condução de processo seletivo da CONTRATANTE. Vedado uso
   para treinar modelo, benchmarking entre clientes, ou qualquer finalidade que misture
   dados de candidatos de contas diferentes.

5. PRAZO E RETENÇÃO
   [RECOMENDAÇÃO — pergunta 9, §5: não travar teto contratual diferente do técnico.]
   Prazo de retenção configurável por conta, entre 7 e 1825 dias, padrão 180
   (`LGPD.md` § Retenção) — o contrato referencia o padrão técnico vigente em vez de fixar
   um número próprio, para não exigir aditamento toda vez que o padrão técnico mudar.

6. SEGURANÇA (art. 46-49)
   A CONTRATADA se compromete a manter as medidas descritas em `LGPD.md` § Segurança
   (modo hospedado): HTTPS, backup cifrado com restauração testada, controle de acesso
   ao servidor, auditoria de acesso/exportação/exclusão por 2 anos.

   [RECOMENDAÇÃO — pergunta 10, §5: sem número fechado de SLA agora — MVP sem histórico de
   operação. Linguagem de "melhores esforços" até haver dado real de uptime, revisitar
   quando houver histórico.] A CONTRATADA envidará seus melhores esforços para manter o
   serviço disponível e o backup restaurável, sem compromisso de disponibilidade mínima
   percentual nesta fase inicial de operação.

7. NOTIFICAÇÃO DE INCIDENTE
   [RECOMENDAÇÃO — pergunta 11, §5: 72 horas.]
   A CONTRATADA notificará a CONTRATANTE em até 72 (setenta e duas) horas a partir da
   confirmação de incidente de segurança com risco relevante aos titulares, com
   informações suficientes para a CONTRATANTE cumprir suas próprias obrigações perante a
   ANPD e os titulares (art. 48).

8. SUBOPERADORES ADICIONAIS
   [RECOMENDAÇÃO — pergunta 6, §5: os dois provedores de IA são oferecidos oficialmente —
   Claude (Anthropic) e ChatGPT (OpenAI). Por definição da cláusula 3, eles não são
   suboperadores da CONTRATADA (vínculo é direto CONTRATANTE-provedor) — listados aqui só
   para transparência, não como responsabilidade assumida pela CONTRATADA.]
   Suboperador de fato da CONTRATADA nesta relação: [PROVEDOR DE E-MAIL — BLOQUEADO,
   pergunta 12, §5, ainda não escolhido] (recuperação de senha da conta do recrutador).
   Lista a manter atualizada conforme novos fornecedores forem integrados.

9. DIREITOS DO TITULAR E APOIO À CONTRATANTE
   A CONTRATADA mantém os canais técnicos descritos em `LGPD.md` § Direitos do titular
   (busca, exportação, eliminação) e os disponibiliza à CONTRATANTE para atendimento aos
   titulares em prazo hábil.

10. TÉRMINO DO CONTRATO E DESTINO DOS DADOS
    [RECOMENDAÇÃO — pergunta 13, §5: já compatível com o que o sistema já faz (exportação
    LGPD + expurgo).]
    Ao fim da relação contratual (por rescisão, cancelamento ou inadimplência), os dados
    permanecem disponíveis para exportação pela CONTRATANTE por 30 (trinta) dias, findos os
    quais a CONTRATADA os elimina definitivamente.

11. LIMITAÇÃO DE RESPONSABILIDADE
    [RECOMENDAÇÃO — pergunta 4, §5 — cláusula com maior peso financeiro, tratar com atenção
    redobrada do advogado antes de fechar.]
    A responsabilidade da CONTRATADA por danos decorrentes deste contrato fica limitada a um
    múltiplo de [N] vezes o valor das mensalidades pagas pela CONTRATANTE nos 12 (doze)
    meses anteriores ao evento, ressalvados os casos de dolo, má-fé, e multa aplicada pela
    ANPD em razão de violação da LGPD diretamente imputável à CONTRATADA, que não se sujeitam
    a este limite. [Multiplicador N ainda não definido — decisão explícita pendente antes de
    fechar o texto; item operacional separado, sem bloquear o contrato em si: cotar/contratar
    cyber insurance antes de escalar para múltiplos clientes pagantes.]

12. FORO E LEGISLAÇÃO APLICÁVEL
    [RECOMENDAÇÃO — pergunta 3, §5: domicílio da própria CONTRATADA.] [BLOQUEADO — o valor
    final só pode ser preenchido quando as perguntas 1 e 2 (razão social/CNPJ e endereço)
    forem respondidas.]
    Fica eleito o foro da comarca de [PENDENTE — depende de 1/2], com renúncia a qualquer
    outro, por mais privilegiado que seja. Legislação aplicável: leis da República
    Federativa do Brasil.

13. DISPOSIÇÕES GERAIS
    [RECOMENDAÇÃO — pergunta 14, §5: contrato só em português por enquanto.]
    [Vigência, reajuste, confidencialidade, vedação de cessão sem anuência, etc. — texto
    final do advogado.]
```

---

## 4. Lacunas encontradas (além das já corrigidas em `LGPD.md` hoje)

1. **Contrato de operador não tinha rascunho nenhum antes de hoje** — só um item de
   checklist dizendo que precisava existir. O esqueleto do §3 cobre isso, mas está cheio de
   pendências que dependem das respostas do §5.

2. **Tela de autorização do conector MCP (`app/rotas_mcp.py:112-135`, rota
   `/mcp/consentir`) tem um problema de precisão com peso jurídico.** O título é dinâmico
   ("Autorizar {cliente}?"), mas o corpo do texto é fixo: *"Se você autorizar, o Claude vai
   poder, em seu nome..."* — mesmo quando quem está pedindo autorização é o ChatGPT. Um
   recrutador autorizando o conector para o ChatGPT está sendo informado, por escrito, de que
   é "o Claude" quem vai processar os dados. Isso é o momento exato em que a transferência
   internacional deveria ser explicitada ao recrutador (é um consentimento ativo, diferente
   do aviso de privacidade que o candidato lê passivamente) — e hoje a tela não menciona
   transferência internacional nenhuma, só lista o que o conector pode fazer dentro do
   sistema. **Status (2026-09-09): endereçado.** A pergunta 6 do §5 foi respondida (os dois
   provedores são oficiais), então a especificação de texto corrigido foi escrita e enviada
   ao Vitral (tela) e à Pigmento (tom) — ver §7.

3. **Aviso de privacidade cobre só o candidato, nunca o usuário da conta (o recrutador).**
   O recrutador também é titular de dado (nome, e-mail, senha, ações registradas em
   auditoria com seu nome). Isso normalmente é coberto por um contrato/termos entre a
   CONTRATANTE (empresa cliente, como empregadora) e o próprio funcionário, não por vocês —
   mas vale confirmar com o advogado se algum texto adicional é necessário do seu lado.

4. **Nenhuma lista formal de suboperadores existe em lugar nenhum,** nem para consulta
   interna nem para o cliente. **Status (2026-09-09): parcialmente resolvido.** A pergunta 7
   do §5 definiu que Anthropic/OpenAI não são suboperadores da CONTRATADA (vínculo direto
   cliente-provedor) — então a lista real de suboperadores da CONTRATADA fica menor do que se
   pensava, hoje com um único item pendente: o provedor de e-mail (item 5 abaixo, ainda
   bloqueado).

5. **Recuperação de senha por e-mail (`backlog-priorizado`, item 4, bloqueador da Entrega
   1) vai introduzir um suboperador que ainda não está escolhido nem mapeado** — o
   provedor de SMTP/relay. A maioria dos provedores simples/gratuitos hospeda fora do
   Brasil, o que pode significar mais uma transferência internacional, desta vez do
   e-mail do recrutador, não do currículo do candidato. **Status: continua bloqueado**
   (pergunta 12, §5) — depende de decisão técnica separada, fora do escopo jurídico.

6. **Termos de uso do software não existiam** (nem rascunho). **Status (2026-09-09):
   rascunho iniciado**, por pedido direto do dono do produto — ver `TERMOS-DE-USO.md`.
   Reaproveita as respostas já dadas (papel da Anthropic/OpenAI, limitação de
   responsabilidade, foro) para não contradizer o contrato de operador, e levanta 4
   perguntas novas específicas de Termos de Uso (modelo de precificação, um documento ou
   dois para os dois modos de implantação, prazo de carência de inadimplência, prazo de
   aviso para mudança dos termos).

7. **O aviso de privacidade não distingue modo hospedado de modo local.** Hoje ele é escrito
   como se sempre existisse um "nós" hospedando — o que é verdade só no modo hospedado.
   **Status (2026-09-09): resolvido.** Pergunta 8, §5, confirmada: no modo local o aviso de
   privacidade do operador não se aplica — é 100% responsabilidade de quem instala. O rascunho
   em `LGPD.md` já valia só para o modo hospedado; nenhuma mudança de texto foi necessária.

---

## 5. Perguntas e decisões — respondidas pelo dono do produto em 2026-09-09

Nenhuma foi decidida por mim. O dono do produto respondeu todas; onde ele mesmo tomou a
decisão em vez de só fornecer um fato, marcou como **RECOMENDAÇÃO** — vale para o esqueleto
do §3, mas segue sem validação de advogado. Onde não havia decisão real a dar, ficou
**BLOQUEADO** — ver §6 para o que fazer com isso agora.

1. **BLOQUEADO** — Razão social e CNPJ da CONTRATADA: não fornecido. Se não existe CNPJ
   constituído, é bloqueador anterior ao próprio contrato — precisa ser resolvido antes de
   qualquer minuta poder ser finalizada.

2. **BLOQUEADO** — Endereço/domicílio da contratada: idem, depende da pergunta 1.

3. **RECOMENDAÇÃO** — Foro de eleição: comarca do domicílio da própria operadora. O valor
   final da cláusula só pode ser preenchido quando 1/2 existirem.

4. **RECOMENDAÇÃO** — Limite de responsabilidade: múltiplo das mensalidades pagas nos
   últimos 12 meses, excluindo dolo/má-fé e multa de LGPD por violação direta da operadora
   (padrão de mercado SaaS). Cyber insurance: recomendado contratar antes de escalar para
   múltiplos clientes pagantes, mas é ação real (cotar/contratar), não resposta de texto —
   registrada como **pendência operacional separada** em §6, não bloqueia o contrato em si.

5. **PARCIAL** — Encarregado (DPO): recomendado o próprio dono do produto no início, com
   e-mail de função (ex. `privacidade@dominio`), não pessoal. Nome final e domínio:
   **BLOQUEADO**, dependem de ele escolher/ter o domínio.

6. **RECOMENDAÇÃO** — Provedores de IA oficiais: os dois, Claude e ChatGPT — coerente com o
   que já foi construído e validado (MCP+OAuth funcionando para os dois). Destrava a
   correção da tela de consentimento (lacuna 2, §4) — ver §7.

7. **RECOMENDAÇÃO** — Papel legal da Anthropic/OpenAI no modo conector: Versão B (vínculo
   direto cliente-provedor). Justificativa registrada: no modo conector é a assinatura do
   próprio recrutador processando direto com o provedor dele; o Triagem nunca processa nada
   através da conta desses provedores nesse modo. Já refletido no §3, cláusula 3.

8. **RECOMENDAÇÃO** — Modo local/stdio: confirmado, sem contrato/aviso de privacidade do
   operador — 100% responsabilidade de quem instala. Já bate com o texto atual de `LGPD.md`,
   nenhuma mudança necessária lá.

9. **RECOMENDAÇÃO** — Retenção contratual: não travar teto diferente do técnico; o contrato
   referencia o padrão técnico (180 dias, configurável 7–1825 pelo cliente). Já refletido no
   §3, cláusula 5.

10. **RECOMENDAÇÃO** — SLA: sem número fechado agora (MVP sem histórico de operação);
    linguagem de "melhores esforços" até haver dado real de uptime. Já refletido no §3,
    cláusula 6.

11. **RECOMENDAÇÃO** — Notificação de incidente: 72 horas após confirmação. Já refletido no
    §3, cláusula 7.

12. **BLOQUEADO** — Provedor de e-mail: ainda não escolhido, pendente de decisão técnica
    separada (fora do escopo jurídico desta rodada).

13. **RECOMENDAÇÃO** — Fim de contrato: exportação disponível por 30 dias, depois exclusão
    definitiva — já compatível com o que o sistema já faz (exportação LGPD + expurgo). Já
    refletido no §3, cláusula 10.

14. **RECOMENDAÇÃO** — Idioma: só português por agora. Já refletido no §3, cláusula 13.

15. **RECOMENDAÇÃO** — Modelo de publicação do aviso: confirmado, cada cliente publica com o
    próprio nome, vocês fornecem o texto-modelo — já é como `LGPD.md` está escrito, nenhuma
    mudança necessária lá.

---

## 6. O que ainda falta preencher (material mantido, sem urgência de bloqueio)

**Deixou de ser pendência ativa em 2026-09-09** — ver nota de estado no topo do documento. Os
quatro pontos abaixo continuam sem resposta, e continuam não sendo decisão de risco (são fato
que falta: documento, escolha técnica, ou providência concreta), mas ninguém está sendo
cobrado com urgência por eles. Ficam registrados aqui para quando a revisão jurídica for
retomada, e é isso que Toga mantém atualizado — não uma cobrança ativa:

- **Razão social e CNPJ da contratada** (pergunta 1) — pode ser bloqueador anterior ao
  próprio contrato, se ainda não há pessoa jurídica constituída.
- **Endereço da contratada** (pergunta 2) — depende do item acima.
- **Nome e domínio de e-mail do encarregado (DPO)** (pergunta 5, parcial) — o formato
  (e-mail de função, não pessoal) já está decidido; falta só o domínio existir.
- **Provedor de e-mail (SMTP/relay) para recuperação de senha** (pergunta 12) — decisão
  técnica separada, ainda não tomada.

Fora dessa lista, registrado à parte por não ser bloqueio de contrato: **cotar/contratar
cyber insurance antes de escalar para múltiplos clientes pagantes** — ação operacional
recomendada, sem prazo travado aqui.

Com as respostas de §5, o esqueleto do §3 já é um rascunho de contrato quase completo — quando
(e se) a revisão for retomada, falta só preencher os quatro pontos acima e mandar para
revisão de advogado. O aviso de privacidade em `LGPD.md` não precisou de mudança adicional
(os colchetes que tinha já previam corretamente os dois provedores). A especificação de
correção da tela de consentimento (lacuna 2, §4) foi escrita e enviada, e já está em
implementação — ver §7 — porque aquela correção tem valor de produto e de UX independente da
revisão jurídica estar pausada ou não.

---

## 7. Especificação enviada — tela de autorização do conector MCP

Enviada ao Vitral (tela) e à Pigmento (tom) em 2026-09-09, agora que a pergunta 6 confirmou
os dois provedores oficiais. Resumo do pedido — texto completo na mensagem trocada com eles:

1. O corpo do texto (`app/rotas_mcp.py:114`, hoje fixo em *"Se você autorizar, o Claude vai
   poder, em seu nome:"*) passa a usar a mesma variável dinâmica que já resolve o nome no
   título (`{cliente}`), em vez do nome fixo "Claude" — para não informar errado quem vai
   processar os dados quando a autorização for para o ChatGPT.
2. Nova linha de divulgação da transferência internacional, no momento em que o recrutador
   efetivamente consente (hoje só existe no aviso de privacidade do candidato, que o
   recrutador não necessariamente lê): nomeando o provedor real por trás do `{cliente}` que
   está sendo autorizado (Anthropic, Estados Unidos, quando o conector é o Claude; OpenAI,
   Estados Unidos, quando é o ChatGPT) e deixando claro que o dado enviado já sai anonimizado.
3. Pedido explícito de revisão de tom à Pigmento antes de qualquer texto final entrar em
   produção, como já é praxe no time (mesmo padrão usado no `MICROCOPY-ATUAL.md` e no item 3
   do backlog).

**Status (2026-09-09): texto aprovado, sem alteração.** A Pigmento revisou os dois pontos
juridicamente obrigatórios (nome dinâmico do conector no corpo do texto, e a linha de
divulgação da transferência internacional) e não pediu troca de palavra nenhuma — confirmou
inclusive que a frase evita minimizar a transferência ("mesmo assim" reconhece que ela é real
apesar da anonimização) e que separa corretamente o nome do conector ({cliente}, o que o
recrutador está autorizando) do nome de quem processa o dado (Anthropic/OpenAI). O Vitral já
está com o layout pronto e implementando junto com o Alicate. Levantou uma questão — de
posicionamento na tela, não de tom, e não é decisão jurídica: se a linha de divulgação
precisa ficar visível sem rolar a página até o botão de autorizar. Isso ficou para
Bussola/Vitral resolverem no desenho; do ponto de vista jurídico, a exigência é só que a
informação exista na tela antes da confirmação, não onde exatamente ela cai no layout.
