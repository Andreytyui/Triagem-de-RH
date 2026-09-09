# Triagem — documento técnico

O que o sistema é hoje, como ele está montado, o que ele ainda não faz, e o que
falta antes de colocá-lo na frente de um cliente pagante.

Escrito para duas pessoas: alguém avaliando se compra, e alguém que vai manter o
código depois. Os números aqui foram medidos no repositório, não estimados.

---

## 1. O que é

Um sistema que lê currículos em lote e devolve um ranking de candidatos em que
**toda nota vem acompanhada do trecho do currículo que a sustenta**.

O cenário alvo é o recrutador que recebe de 40 a 150 currículos por vaga em PDF,
Word e planilha exportada de ATS, e que precisa não só decidir quem chamar, mas
**defender a escolha** para a empresa que o contratou.

A coisa toda vive em torno de três decisões de produto:

1. **A rubrica é aprovada antes de qualquer avaliação.** O sistema propõe
   critérios e pesos; o recrutador edita e aprova. Quando ele discorda de um
   resultado depois, a conversa é sobre o peso que ele mesmo definiu — não sobre
   o que "a IA achou".

2. **A nota é calculada em Python, não pelo modelo.** O modelo pontua cada
   critério e dá uma recomendação; a média ponderada e a ordenação saem do
   código. Quando os dois divergem em duas faixas, vale a nota, e o recrutador é
   avisado da divergência.

3. **Quem avalia não sabe quem é a pessoa.** Nome, contato, idade e endereço são
   separados antes da avaliação. Reduz viés, atende à Lei 9.029/95 na prática, e
   é o que sustenta a resposta quando alguém alegar discriminação.

**A decisão de contratar é sempre humana.** O sistema pontua e justifica; quem
escolhe é o recrutador, e a marcação fica registrada com o nome de quem marcou.
Isso não é escrúpulo: é a defesa contra o art. 20 da LGPD, que dá ao candidato o
direito de revisão de decisão automatizada.

---

## 2. O motor de avaliação

Quem lê e pontua é o **Claude do plano do próprio recrutador**, através de um
servidor MCP. Não existe chave de API, não existe cobrança por token, e nenhum
dado passa pela conta de terceiros. É o único motor: não há caminho alternativo,
e isso é decisão de produto, não limitação.

O servidor faz tudo o que não deve depender de julgamento: extrai o texto,
separa o dado pessoal, calcula a média ponderada, ordena, guarda e apaga.

```
Recrutador ──► interface web ──► envia currículos, aprova critérios
                    │
                    ▼
              banco (SQLite)
                    ▲
                    │  MCP (stdio ou HTTP)
Claude Desktop ─────┘  lê o perfil anonimizado, devolve notas e evidências
```

**Houve um modo API** — o servidor rodando o funil sozinho com uma chave da
Anthropic — e ele foi removido do produto. Vale saber por quê, porque explica
várias formas do código: o dono do produto não quis custo variável de IA do lado
do vendedor, nem obrigar o cliente a gerenciar uma segunda fatura. O que aquele
modo resolvia sozinho (PDF escaneado) passou a ser resolvido por OCR local.

Restou disso um princípio prático: **nada que dependa de julgamento vive no
servidor**. Se aparecer a tentação de "só uma chamadinha de modelo aqui", ela
traz de volta chave, custo, fatura e a pergunta de quem paga.

---

## 3. Como está montado

Python 3.12, FastAPI, SQLite. Frontend em HTML, CSS e JavaScript puro, **sem
etapa de build** — nada de npm, bundler ou framework. Doze dependências ao todo,
mais duas de sistema que a imagem Docker traz: LibreOffice, para o `.doc` velho,
e Tesseract com o idioma português, para o currículo digitalizado.

```
app/                                              linhas
  config.py         limites, segredo, OCR, e-mail, backup      196
  models.py         schemas Pydantic (viram os input_schema
                    das tools do conector)                     208
  security.py       senha, sessão, CSRF                         78
  extraction.py     PDF, Word, planilha, hash, assinatura      271
  ocr.py            leitura de PDF escaneado, local            165
  fila_ocr.py       faz o OCR fora da requisição de upload     173
  anonimizacao.py   separação de dado pessoal por regra        333
  pontuacao.py      média ponderada e conciliação, Python puro  99
  storage.py        SQLite multi-empresa, cache, migração     1319
  retencao.py       expurgo por prazo (LGPD)                    58
  backup.py         backup cifrado de data/, e a restauração   429
  correio.py        envio por SMTP configurável                 84
  senha.py          redefinição por linha de comando            83
  relatorio.py      relatório interno da triagem               307
  shortlist.py      o documento que vai ao cliente             320
  mcp_servidor.py   as 15 ferramentas que o Claude enxerga     843
  mcp_oauth.py      autorizador OAuth do conector              238
  deps.py           quem é o usuário, de qual organização       78
  rotas_auth.py     contas, sessão, senha, configurações       406
  rotas_vagas.py    vagas, upload, status, exportação          380
  rotas_lgpd.py     titular, exportação, exclusão, auditoria   111
  rotas_mcp.py      consentimento e tokens do conector         265
  main.py           montagem, travas globais, ciclo de vida    271

static/             interface, sem build                      2856
tests/              suíte offline                             2349
```

Cerca de **11.700 linhas**, das quais 2.349 são teste.

### O caminho de uma requisição

Toda rota de dados depende de `usuario_atual`, e é essa função que amarra a
organização na requisição. O isolamento entre clientes não depende de o
programador lembrar de filtrar: a chave primária de `curriculos` é
`(org_id, candidato_id)`, e toda consulta recebe o `org_id` como parâmetro.

Antes disso, um middleware global aplica em toda requisição: teto de tamanho de
corpo, verificação anti-CSRF nos métodos que mudam estado, cabeçalhos de
segurança e `Cache-Control: no-store` em tudo que é `/api/`.

---

## 4. O caminho de um currículo

**Estágio 0 — extração.** Não usa IA. PDF por `pdfplumber`, Word por
`python-docx`, `.doc` antigo pelo LibreOffice, planilha vira um candidato por
linha. A extensão é conferida contra a assinatura do arquivo — executável
renomeado para `.pdf` não entra.

PDF com menos de 220 caracteres extraíveis é tratado como escaneado e vai para a
**fila de OCR** (`fila_ocr.py`), fora da requisição de upload. O motivo é de
produção: OCR local leva de 2 a 6 segundos por página, e o recrutador arrasta a
pasta inteira — quinze escaneados numa remessa deixariam a requisição minutos no
ar, tempo suficiente para o proxy derrubar a conexão. Medido: o mesmo upload de
15 escaneados responde em **0,18s** com a fila, contra os minutos que levaria
fazendo o OCR ali dentro.

O que fica pendente é recolhido no boot seguinte, então uma queda no meio não
perde currículo. E pendente **não é erro**: enquanto está na fila, o currículo
conta como pendente no painel. Erro é o que já foi tentado e não deu.

**Estágio 1 — separação do dado pessoal.** Determinística, em `anonimizacao.py`,
sem modelo e sem custo. O resultado é gravado com chave no hash SHA-256 do
arquivo, por organização: o mesmo currículo nunca é separado duas vezes na mesma
conta, nem em outra vaga, nem meses depois — e nunca é compartilhado entre contas.

Texto vindo de OCR usa padrões tolerantes ao ruído de leitura (o OCR troca dígito
por letra parecida, e `CPF: l23.456.789-O0` não casaria com a regex comum). Esses
padrões **só** entram em texto de OCR: em texto limpo eles casariam com "Windows
Server 2019" e com volume de chamados.

**Estágio 2 — avaliação.** Fora do servidor, no Claude do recrutador, um
candidato por vez. Avaliar em lote produz viés de ordem e faz o modelo comparar
candidatos em vez de medi-los contra a rubrica.

**Estágio 3 — cálculo.** De volta no servidor, em `pontuacao.py`: Python puro,
sem rede e sem modelo. Média ponderada, ranking e a conciliação entre a nota e a
recomendação. Este módulo existe separado de propósito — é o que torna a nota
recalculável à mão, com a rubrica na frente.

---

## 5. O conector (modo MCP)

Quinze ferramentas: `listar_vagas`, `criar_vaga`, `definir_criterios`,
`ver_criterios`, `status_da_vaga`, `proximos_curriculos`, `registrar_avaliacao`,
`registrar_eliminacao`, `ver_ranking`, `ver_candidato`, `registrar_decisao`,
`adicionar_curriculo`, `links_da_vaga`, `buscar_titular` e
`apagar_dados_do_candidato`.

### Dois transportes

**stdio** — o Claude Desktop roda o servidor como processo filho na máquina do
recrutador. Nada é publicado na internet. Autenticado por token pessoal, gerado
na interface e gravado no banco só como hash. É o caminho da instalação local.

**HTTP** — para claude.ai e ChatGPT, que rodam na nuvem e exigem endereço público
com HTTPS. Aqui o servidor é, ele mesmo, um **autorizador OAuth 2.1**: registro
dinâmico de cliente, PKCE, código de uso único, rotação de refresh token. A tela
de consentimento reaproveita a sessão normal da Triagem, então autorizar o Claude
é o mesmo login que o recrutador já usa.

O app MCP é montado inteiro no FastAPI, por último. A autenticação dele vive em
middleware do próprio app, não das rotas — desmontá-lo rota a rota removeria a
proteção.

### A anonimização determinística

No funil por API, quem separa dado pessoal de conteúdo profissional é o Haiku, no
estágio de parse. **No modo conector não existe essa chamada**: quem avalia é o
Claude do conector, e ele não pode receber o currículo com nome e telefone,
senão a proteção contra viés evapora.

Então a separação acontece por regra, em `anonimizacao.py`, antes de qualquer
coisa cruzar a fronteira. Saem: nome, e-mail, telefone, CPF, RG, CEP, data de
nascimento, idade, estado civil, menção a filhos e links de perfil. Ficam:
empresa, cargo, ferramenta, número, data e resultado.

**Isto é mais fraco que a separação por modelo, e o sistema admite.** Quando não
identifica o nome com segurança, ele avisa no próprio lote entregue ao Claude,
em vez de fingir garantia. Vale saber disso antes de prometer ao cliente.

---

## 6. Modelo de dados

SQLite em WAL, quinze tabelas, versionadas por `PRAGMA user_version` com migração
automática do esquema antigo.

```
organizacoes ──┬── usuarios ──── sessoes
               │              └── mcp_tokens
               ├── curriculos          (PK: org_id + candidato_id)
               ├── vagas ──┬── vaga_curriculos
               │           ├── avaliacoes
               │           └── decisoes
               ├── gastos
               └── auditoria

mcp_clientes, mcp_pedidos, mcp_codigos    (fluxo OAuth do conector)
tentativas_login                          (freio de força bruta)
```

O arquivo original de cada currículo fica em `data/uploads/<org_id>/<hash><ext>`.
Uma planilha vira vários candidatos e um arquivo só; o arquivo só é apagado com o
último candidato que o referencia.

**44 endpoints**: 17 de triagem, 11 de conta, 7 do conector, 6 de LGPD e 3 de
serviço (raiz, saúde e configuração pública).

---

## 7. Segurança e LGPD

| Área | O que está feito |
|---|---|
| Senha | PBKDF2-HMAC-SHA256, 600 mil iterações, sal por senha. O login gasta o mesmo tempo com e-mail inexistente, para não revelar quem tem conta |
| Sessão | Cookie `HttpOnly`, `SameSite=Lax`; o banco guarda só o SHA-256 do token |
| CSRF | Dupla submissão de cookie, exigida em todo método que muda estado |
| Força bruta | 8 tentativas por e-mail + IP a cada 15 minutos |
| Isolamento | Toda consulta filtra por `org_id`; teste dedicado tenta atravessar e falha |
| Chave do cliente | Cifrada em repouso com Fernet, derivada do `TRIAGEM_SECRET_KEY` |
| Cabeçalhos | CSP, `nosniff`, `Referrer-Policy`, HSTS sob HTTPS; nenhuma resposta de API cacheável |
| Erros | Nenhum stack trace chega ao cliente; `/docs` desligado |
| Injeção via currículo | Os prompts declaram que o conteúdo entre as marcas é dado, nunca instrução |

Do lado da LGPD: retenção por prazo com expurgo automático, exportação e exclusão
do titular, auditoria de acesso guardada por dois anos, e minimização por
construção. O detalhamento está em [LGPD.md](LGPD.md), com rascunho de aviso de
privacidade e checklist antes de vender.

---

## 8. Estado atual

**76 testes** automatizados e offline. Não há chamada de rede a dublar: quem
avalia é o Claude do próprio recrutador, fora do servidor. Dois grupos são
pulados quando falta dependência de sistema, com aviso explícito — a leitura real
por OCR sem o Tesseract, e a extração de PDF sem o `reportlab`.

| Módulo | Testes | Cobre |
|---|---|---|
| Extração | 7 | PDF, escaneado, planilha, dedup, assinatura, truncamento |
| Anonimização | 9 | Contato, nome, dado sensível, planilha rotulada, formato |
| Pontuação | 11 | Média ponderada, cache, status, migração de esquema |
| OCR | 6 | Anonimização sobre ruído, retenção, fila, teto de contexto |
| Recuperação de senha | 8 | Link, uso único, expiração, freio, comando local |
| Backup | 7 | Snapshot com escrita, cifra, restauração, retenção |
| Segurança | 7 | Senha, cifra, isolamento, sessão, força bruta, CSRF |
| LGPD | 6 | Busca, exportação, exclusão, expurgo, auditoria |
| Conector MCP | 13 | Ferramentas, anonimização, isolamento, OAuth completo |

Além da suíte, foram verificados manualmente com o servidor rodando: o fluxo web
completo (32 verificações), o conector por HTTP com cliente MCP real, o conector
por stdio subindo o processo de verdade, e o piso de qualidade da interface
(380px sem rolagem horizontal, contraste AA em quatro telas, foco de teclado em
40 elementos, `prefers-reduced-motion`).

### Defeitos encontrados e corrigidos durante a construção

Registrados porque explicam por que certas partes são como são:

- **PDF escaneado quebrava 100% das vezes.** O `pdf_b64` era gerado no upload mas
  nunca gravado; o documento era remontado sem ele no parse. Hoje o arquivo
  original é preservado e há teste de regressão que espia a chamada.
- **A tela de login aparecia acima do app depois de entrar.** `display: grid`
  sobrepunha o `display:none` do atributo `hidden`.
- **Colisão de nome de classe** entre o `.vazio` de estado vazio e a nota ausente
  do ranking, dobrando a altura das linhas.
- **Vazamento de nome** nas linhas de planilha de ATS: o rótulo `Nome:` fazia o
  detector rejeitar a linha, e o nome passava batido para o texto anonimizado.
- **Erro de ferramenta engolido**: as tools do MCP levantavam `ValueError`, e o
  SDK descarta a mensagem. O Claude recebia "Error executing tool" sem saber como
  corrigir. Hoje levantam `ToolError`.
- **`.env` nunca era lido** e o `reportlab` faltava no requirements, então a suíte
  não rodava.

---

## 9. Limites conhecidos

Coisas que o sistema **não** faz, ditas antes de alguém descobrir usando:

~~**Não existe recuperação de senha.**~~ Resolvido: fluxo por e-mail com SMTP
configurável no modo hospedado, e `python -m app.senha <email>` na instalação
local. Os dois derrubam sessões abertas e revogam os tokens do conector.

**A imagem Docker nunca foi construída.** O `Dockerfile` está escrito e blindado
para falhar na build em vez de falhar no primeiro `.doc` do cliente, mas nunca
rodou. Rode `docker compose build` antes de entregar.

**O conector não faz upload em lote.** Arrastar 150 arquivos é coisa da
interface web. PDF escaneado, esse, funciona: o OCR roda no servidor antes de
qualquer coisa cruzar para o conector — mandar a imagem do currículo pelo MCP
devolveria nome e foto para quem pontua, e está descartado por princípio.

**claude.ai e ChatGPT exigem endereço público com HTTPS.** Instalação local só
funciona com Claude Desktop, por stdio.

**O envio de e-mail cobre só recuperação de senha.** Convite de usuário e aviso
de expurgo usariam a mesma infraestrutura (`correio.py`), mas ainda não foram
construídos.

**SQLite aguenta uma agência de recrutamento, não um SaaS com dezenas de empresas
ativas ao mesmo tempo.** O ponto de troca é `storage.py` para PostgreSQL; o resto
do código não muda, porque nada mais toca no banco.

**Rate limit existe só no login.** As demais rotas não têm teto de requisições.

---

## 10. O que vem depois

Em ordem de urgência para vender, não de dificuldade.

### Antes do primeiro cliente pagante

1. **Recuperação de senha.** Sem isso o suporte vira você abrindo SQLite. Precisa
   de envio de e-mail, ou de um comando de linha que o comprador rode na máquina
   dele — no cenário local, o segundo resolve e é mais simples.
2. **Construir e testar a imagem Docker.** Uma tarde.
3. **Backup automatizado de `data/`**, com restauração testada pelo menos uma vez.
   Hoje é manual e não documentado como rotina.
4. **Contrato de operador e aviso de privacidade** revisados por advogado. O
   rascunho está no LGPD.md.

### Melhoram o produto de verdade

5. **Comparar candidatos lado a lado.** O recrutador escolhe 2 ou 3 e vê as notas
   por critério em colunas. É a pergunta que ele faz o tempo todo e que hoje exige
   abrir e fechar o painel.
6. **Templates de vaga.** Quem atende as mesmas posições repete a rubrica; hoje
   redigita.
7. **Versionar a rubrica.** Se ele reavalia com pesos novos, o resultado antigo
   some. Guardar as duas permitiria comparar — e é defesa numa auditoria.
8. **Anonimização melhor.** Hoje é regex, e é o ponto mais frágil da promessa
   central. Um modelo local pequeno fecharia a diferença — e, com o modo API
   fora, é a única forma de melhorar isso sem reintroduzir custo variável.

### Se escalar

9. **PostgreSQL**, quando houver mais de uma dezena de empresas ativas.
10. **Rate limit geral** e fila de execução, para uma conta não travar as outras.
11. **Métricas de qualidade da triagem**: quantos "chamar" viraram entrevista,
    quantos viraram contratação. É o dado que prova o valor do produto — e hoje
    ninguém coleta.

---

## Uma nota sobre o que se vende aqui

O produto não é "IA que contrata". É a leitura de 150 currículos em minutos com
**justificativa auditável** — e a diferença está inteira na evidência citada em
cada nota.

Um sistema que descarta candidato sozinho é um problema jurídico esperando
acontecer, e é também uma promessa que o modelo não sustenta. Mantenha a decisão
final com o recrutador; é o que a arquitetura toda foi construída para proteger.
