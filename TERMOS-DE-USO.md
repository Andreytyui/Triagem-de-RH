# Termos de uso — rascunho

Iniciado por Toga (jurídico) em 2026-09-09. Fora do escopo original do item 7 do backlog
(que era contrato de operador + aviso de privacidade), registrado como pendência futura em
`REVISAO-JURIDICA.md` §4 e agora aberto por pedido direto do dono do produto.

**Isto não é parecer jurídico e não substitui a revisão de um advogado licenciado antes de
vender ou operar em produção.** É um primeiro rascunho, não um documento fechado — várias
cláusulas ainda dependem de decisão do dono do produto (marcadas `[PERGUNTA NOVA]`) e nenhuma
foi validada por advogado.

**Nota de estado (2026-09-09):** o dono do produto decidiu conscientemente pular a revisão
jurídica por agora e não tratar o item 7 (contrato de operador + aviso de privacidade) como
bloqueador de venda/entrega — mesma decisão se estende a este rascunho, que nasceu depois
dela. Sem urgência de bloqueio, então: as perguntas do §13 seguem para o dono do produto como
material mantido, não como pendência ativa cobrada.

**Convenções usadas neste documento:**
- `[JÁ DECIDIDO — DONO DO PRODUTO, 2026-09-09]` — reaproveita uma resposta já dada para o
  contrato de operador (`REVISAO-JURIDICA.md` §5), aplicada aqui para os dois documentos não
  entrarem em contradição.
- `[SUGESTÃO DE RASCUNHO — TOGA]` — cláusula de texto padrão de mercado que escrevi por conta
  própria, por ser de baixo risco/boilerplate. Não é decisão do dono do produto nem do
  advogado — é só um ponto de partida para eles concordarem, discordarem ou reescreverem.
- `[PERGUNTA NOVA — SÓ O DONO DO PRODUTO RESPONDE]` — decisão de negócio real que não apareceu
  nas 15 perguntas anteriores porque aquelas eram específicas do contrato de operador.
- `[BLOQUEADO]` — mesmo fato pendente já registrado em `REVISAO-JURIDICA.md` §6 (CNPJ,
  endereço), repetido aqui porque este documento também precisa dele.

---

## 0. Como este documento se relaciona com os outros dois

Três documentos jurídicos distintos, sem sobreposição de conteúdo — cada um resolve uma
relação diferente:

| Documento | Relação que regula | Quem lê |
|---|---|---|
| **Termos de uso** (este) | Uso do software/serviço Triagem | A empresa cliente, como usuária do produto |
| **Contrato de operador** (`REVISAO-JURIDICA.md`) | Tratamento do dado pessoal dos candidatos | A empresa cliente, como controladora dos dados |
| **Aviso de privacidade** (`LGPD.md`) | O que acontece com o currículo do candidato | O candidato |

Onde este documento tocaria em proteção de dados pessoais (segurança, SLA, notificação de
incidente, destino dos dados ao fim do contrato), ele **remete ao contrato de operador** em
vez de repetir os números — evita os dois documentos divergirem se um for atualizado e o
outro não.

---

## 1. Partes e aceite

CONTRATADA / fornecedora do serviço: [RAZÃO SOCIAL / CNPJ — **BLOQUEADO**, mesmo fato pendente
de `REVISAO-JURIDICA.md` §6, pergunta 1]. Endereço: [**BLOQUEADO**, pergunta 2].

USUÁRIA: a empresa que cria uma conta na Triagem (modo hospedado) ou instala o software
(modo local), representada pela pessoa física que efetivamente aceita estes termos ao se
cadastrar ou instalar.

`[SUGESTÃO DE RASCUNHO — TOGA]` O aceite se dá no momento do cadastro da conta (modo
hospedado) ou da primeira execução do instalador (modo local), e é condição para uso do
serviço/software. **Gap encontrado:** hoje não existe tela de aceite de termos no fluxo de
cadastro (`app/rotas_auth.py`) — nenhuma checkbox, nenhum link. Isso é normal nesta fase (o
próprio texto ainda não existe), mas fica registrado como item a especificar para o Vitral
assim que este rascunho estiver maduro o suficiente para revisão do advogado — não faz
sentido pedir a tela antes do texto estar estável.

---

## 2. Descrição do serviço — dois modos, dois regimes

`[JÁ DECIDIDO — DONO DO PRODUTO, 2026-09-09]` — mesma distinção já usada em `LGPD.md` e
`REVISAO-JURIDICA.md`, reaproveitada aqui para não haver contradição entre os documentos.

**Parte A — Modo hospedado (SaaS).** A CONTRATADA hospeda o serviço centralmente; a USUÁRIA
acessa pela interface web e/ou autoriza o conector MCP (HTTP + OAuth) para claude.ai/ChatGPT.
Regido também pelo Contrato de Operação de Dados Pessoais (`REVISAO-JURIDICA.md`).

**Parte B — Modo local (instalação própria, stdio).** A USUÁRIA instala e executa o software
na própria infraestrutura, conectando ao Claude Desktop via stdio. Aqui a CONTRATADA **não**
hospeda dado nenhum e **não** é operadora — a relação é de licença de uso de software, não de
prestação de serviço com tratamento de dados. Não se aplica o Contrato de Operação nem o
aviso de privacidade fornecido pela CONTRATADA (`LGPD.md` § Quem é quem, decisão confirmada).

`[PERGUNTA NOVA — SÓ O DONO DO PRODUTO RESPONDE]` **1.** Você quer um único documento de
Termos de Uso com as duas partes claramente separadas (como este rascunho já está
organizado), ou prefere dois documentos formalmente distintos — um "Termos de Uso do SaaS" e
uma "Licença de Uso de Software" separada para quem instala localmente? A estrutura em duas
partes dentro de um documento só é mais simples de manter, mas um advogado pode preferir
separar por serem relações jurídicas de natureza diferente (prestação de serviço vs. licença).

Em ambos os modos: o motor de avaliação usa a assinatura Claude e/ou ChatGPT da própria
USUÁRIA — a Triagem não fornece, não revende, nem se responsabiliza pela disponibilidade,
termos de uso ou preço desses serviços de terceiros. Isso é redigido explicitamente na
cláusula 6 abaixo.

---

## 3. Cadastro e responsabilidades da usuária

`[SUGESTÃO DE RASCUNHO — TOGA]`

3.1. A USUÁRIA é responsável pela veracidade dos dados de cadastro, pela guarda da senha de
acesso e por toda ação realizada pela conta — incluindo pelo conector MCP, cujas ações ficam
registradas em auditoria com o nome de quem autorizou (`LGPD.md` § Direitos do titular).

3.2. **Declaração de base legal.** A USUÁRIA declara ter base legal própria, nos termos da
Lei 13.709/2018, para tratar os dados pessoais dos candidatos que submeter ao serviço, e é
responsável por essa determinação perante os titulares e a ANPD — a CONTRATADA atua como
operadora (modo hospedado) ou fornecedora de software (modo local), não decide nem valida a
base legal usada pela USUÁRIA. **Nota de risco, não é cláusula:** esta é a cláusula que
protege a CONTRATADA caso um cliente use o produto para um processo seletivo sem base legal
adequada (ex.: currículo obtido de fonte duvidosa) — recomendo que o advogado dê atenção
particular a ela, mas o texto acima é só o meu rascunho, não uma garantia jurídica de que
está redigida do jeito certo.

3.3. **Manutenção da decisão humana.** A USUÁRIA se compromete a manter a decisão final de
cada candidato (chamar, reservar, arquivar) como ato de uma pessoa da própria organização,
nunca automatizada — condição de uso do serviço, não só descrição técnica. Isso transforma um
princípio de produto (`backlog-priorizado` § Princípios inegociáveis, `LGPD.md` art. 20) em
obrigação contratual da USUÁRIA, reforçando a defesa em caso de alegação de decisão
automatizada discriminatória. **Nota de risco:** vale conferir com o advogado se essa cláusula
deveria vir acompanhada de consequência explícita em caso de descumprimento (suspensão de
conta?) — não coloquei isso porque é decisão de risco, não texto padrão.

3.4. É vedado à USUÁRIA: usar o serviço para finalidade diferente de processo seletivo
próprio; tentar extrair, copiar ou fazer engenharia reversa do software (exceto na medida em
que a lei expressamente permitir); compartilhar credenciais de acesso com terceiros não
autorizados; e enviar dado de candidato sabidamente obtido sem consentimento ou outra base
legal válida.

---

## 4. Planos e pagamento

`[PERGUNTA NOVA — SÓ O DONO DO PRODUTO RESPONDE]` **2.** Não há modelo de precificação
registrado em nenhum documento do projeto — só a preferência do cliente-alvo, em
`PEDIDO-DO-CLIENTE.md`: *"pago pela ferramenta, não por currículo"*. Preciso saber, antes de
escrever esta cláusula de verdade: existe(m) plano(s) definido(s) (mensal, anual, por número
de vagas simultâneas, por usuário)? Valor(es)? Política de reajuste? Sem isso a cláusula 4
fica um placeholder puro — não arrisquei um rascunho aqui porque preço é decisão de negócio
central, não boilerplate.

`[PLACEHOLDER — sem sugestão de texto até a pergunta acima ser respondida]`

---

## 5. Propriedade intelectual

`[SUGESTÃO DE RASCUNHO — TOGA, boilerplate padrão de mercado]`

5.1. O software, seu código-fonte, marca e documentação são de titularidade exclusiva da
CONTRATADA. Estes termos concedem à USUÁRIA apenas um direito de uso, não uma licença de
propriedade intelectual sobre o software.

5.2. Os dados inseridos pela USUÁRIA (currículos, critérios de vaga, avaliações, decisões)
continuam de titularidade da USUÁRIA (e, quanto ao dado pessoal do candidato, sujeitos ao
regime do Contrato de Operação). A CONTRATADA não usa esses dados para treinar modelo,
divulgação, benchmarking entre clientes, ou qualquer finalidade fora da prestação do serviço
à própria USUÁRIA — mesma vedação já registrada no esqueleto do contrato de operador.

---

## 6. Uso da assinatura de IA da própria usuária

`[JÁ DECIDIDO — DONO DO PRODUTO, 2026-09-09]` — decorre diretamente da resposta à pergunta 7
de `REVISAO-JURIDICA.md` (vínculo direto cliente-provedor, não suboperação da CONTRATADA).

6.1. O processamento de pontuação dos currículos é feito pela conta/assinatura Claude e/ou
ChatGPT da própria USUÁRIA, contratada e mantida diretamente por ela junto à Anthropic e/ou
OpenAI. A CONTRATADA não é parte dessa relação, não garante disponibilidade, preço,
qualidade, ou continuidade desses serviços de terceiros, e não se responsabiliza por
indisponibilidade do serviço da Triagem que decorra exclusivamente de falha, mudança de
termos, ou indisponibilidade da Anthropic ou da OpenAI.

6.2. A USUÁRIA é responsável por manter assinatura válida e por cumprir os termos de uso do
provedor de IA escolhido.

---

## 7. Disponibilidade, dados pessoais e segurança (modo hospedado)

`[JÁ DECIDIDO — DONO DO PRODUTO, 2026-09-09]` Por remissão, para não duplicar (e arriscar
divergir) números já decididos: as obrigações de segurança, backup, disponibilidade
("melhores esforços", sem SLA percentual nesta fase — `REVISAO-JURIDICA.md` §3, cláusula 6),
notificação de incidente (72 horas — cláusula 7) e destino dos dados ao fim do contrato (30
dias de exportação, depois exclusão — cláusula 10) estão descritas no Contrato de Operação de
Dados Pessoais, parte vinculante destes Termos para clientes do modo hospedado.

Para o modo local, nenhuma dessas obrigações se aplica — é responsabilidade de quem instala,
como já descrito em `LGPD.md` § Segurança.

---

## 8. Limitação de responsabilidade

`[JÁ DECIDIDO — DONO DO PRODUTO, 2026-09-09]` — mesma fórmula do contrato de operador
(`REVISAO-JURIDICA.md` §3, cláusula 11), para as duas relações (uso do software e tratamento
de dado) ficarem sob o mesmo teto de risco, e não duas fórmulas divergentes para o mesmo
cliente.

A responsabilidade da CONTRATADA por danos decorrentes destes Termos fica limitada a um
múltiplo de [N] vezes o valor das mensalidades pagas pela USUÁRIA nos 12 (doze) meses
anteriores ao evento, ressalvados dolo, má-fé, e multa aplicada pela ANPD em razão de
violação da LGPD diretamente imputável à CONTRATADA. `[N ainda não definido — mesma pendência
do contrato de operador, não é uma segunda decisão a tomar, é a mesma resposta usada duas
vezes]`

---

## 9. Rescisão

`[SUGESTÃO DE RASCUNHO — TOGA]`

9.1. A USUÁRIA pode encerrar a conta a qualquer momento pela interface (modo hospedado) ou
simplesmente parar de usar o software (modo local).

9.2. A CONTRATADA pode suspender ou encerrar o acesso em caso de descumprimento destes
Termos, inadimplência não sanada em [PERGUNTA NOVA — prazo de carência, não decidido] dias
após notificação, ou uso que coloque em risco a segurança de outros clientes hospedados.

9.3. Destino dos dados ao encerrar: ver cláusula 7 (remissão ao contrato de operador).

`[PERGUNTA NOVA — SÓ O DONO DO PRODUTO RESPONDE]` **3.** Qual prazo de carência para
inadimplência antes de suspender a conta? Não é a mesma pergunta do prazo de exportação pós-
encerramento (já respondida, 30 dias) — é quanto tempo depois de um pagamento atrasado a
conta continua ativa antes de ser suspensa.

---

## 10. Alterações nestes termos

`[SUGESTÃO DE RASCUNHO — TOGA, prazo é chute de padrão de mercado, não decisão de ninguém
ainda]` A CONTRATADA pode alterar estes Termos mediante aviso à USUÁRIA com [30 dias?] de
antecedência para mudanças materiais (preço, limitação de responsabilidade, escopo do
serviço). O uso continuado após a data de vigência da alteração implica aceite.

`[PERGUNTA NOVA — SÓ O DONO DO PRODUTO RESPONDE]` **4.** Confirma 30 dias de aviso prévio
para mudança material dos termos, ou prefere outro prazo?

---

## 11. Foro e legislação aplicável

`[JÁ DECIDIDO — DONO DO PRODUTO, 2026-09-09]` mesma resposta do contrato de operador — foro
do domicílio da CONTRATADA. `[BLOQUEADO — mesmo motivo: só preenche quando existir CNPJ e
endereço, `REVISAO-JURIDICA.md` §6]`.

---

## 12. Disposições gerais

`[Vigência, confidencialidade, vedação de cessão sem anuência, integralidade do contrato
(este documento + Contrato de Operação quando aplicável) — texto final do advogado.]`

---

## 13. O que falta antes deste rascunho poder ir para o advogado junto com o resto

Além dos 4 bloqueios já conhecidos (CNPJ/razão social, endereço, domínio do DPO, provedor de
e-mail — `REVISAO-JURIDICA.md` §6, os dois primeiros também travam a cláusula 11 daqui), este
documento levanta **4 perguntas novas**, específicas de Termos de Uso, que não estavam nas 15
anteriores:

1. Um documento só (duas partes) ou dois documentos separados (SaaS × licença local)?
2. Modelo de precificação — planos, valores, política de reajuste. Sem isso a cláusula 4
   fica vazia.
3. Prazo de carência de inadimplência antes de suspender a conta.
4. Prazo de aviso prévio para mudança material dos termos (sugeri 30 dias, é só chute de
   padrão de mercado, não decisão de ninguém ainda).

Quando essas 4 perguntas forem respondidas — e os 4 bloqueios de `REVISAO-JURIDICA.md` §6
resolvidos — os três documentos (Termos de Uso, Contrato de Operação, Aviso de Privacidade)
ficam prontos para irem juntos para o advogado, com as mesmas decisões refletidas de forma
consistente nos três.
