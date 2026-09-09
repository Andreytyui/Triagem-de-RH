# Especificação de interface — Entrega 1 (pós-pivô MCP)

Três itens, mesma prioridade, todos bloqueadores de venda. Escrito para o Product
Manager validar e para o Engenheiro de Software implementar.

Restrições que valem para os três, e que não se negociam: HTML/CSS/JS puro em
`static/`, sem build; 380px sem rolagem horizontal; contraste AA; foco de teclado
visível; `prefers-reduced-motion` respeitado. Nenhum item abaixo pede componente
visual novo — todos reaproveitam classes que já existem em `styles.css`.

---

## Item 1 — Indicador de qualidade de OCR

### O problema de nomenclatura, antes de tudo

A interface já usa a palavra **confiança** para outra coisa: `confianca`
(alta/média/baixa) é o quanto a *avaliação* se apoia em evidência, vem do
`registrar_avaliacao` do conector e aparece hoje em `app.js:728` (linha do
ranking) e `app.js:871` (selo ao lado do nome).

Qualidade de OCR é outro eixo — fidelidade da **extração**, no Estágio 0, antes
de existir avaliação. Se os dois compartilharem palavra e selo, o recrutador não
consegue distinguir "o currículo é fraco em evidência" de "nós lemos mal o
arquivo". São reações diferentes: a primeira é sobre o candidato, a segunda é
sobre pedir um arquivo melhor.

**Regra:** o eixo de OCR nunca usa a palavra "confiança" sozinha na interface.
Usa **"OCR"**.

### Contrato de dados (para o Alicate)

Três acréscimos, nenhum destrutivo:

1. `POST /api/vagas/{id}/curriculos` (resposta do upload) ganha
   `por_ocr: [{ arquivo, confianca }]` — os arquivos que passaram por OCR nesta
   remessa. Sem isso não há como montar o grupo da fila.
2. `GET /api/vagas/{id}/resultados` — cada linha ganha
   `origem_texto: "direto" | "ocr"` e `ocr_confianca: "alta" | "baixa" | null`.
3. `GET /api/vagas/{id}/status` — o progresso ganha `por_ocr: <int>`.

A interface degrada sem erro se os campos não vierem: campo ausente = extração
normal = nenhum elemento novo na tela.

**Correção de texto obrigatória, no mesmo item:** `extraction.py:280` grava hoje
`"pouco texto extraível; será lido por visão"`, e esse aviso chega à tela pelo
canal `avisos`. Sem modo API, o texto virou mentira. Passa a ser
`"PDF escaneado; texto extraído por OCR"`.

### Onde aparece — quatro superfícies, pesos diferentes

**1. Fila de upload — a mais importante.** É o único momento em que o recrutador
ainda pode agir (reescanear, pedir o arquivo de novo). A fila já agrupa em
novos/repetidos/rejeitados (`app.js:501+`). Entra um quarto grupo, mesmo padrão
`.fila-grupo`:

```
+---------------------------------------------+
| 3 lidos por OCR                             |   .fila-grupo-titulo
| PDF escaneado - o texto pode ter falhas     |   .fila-grupo-nota
| ------------------------------------------- |
| curriculo-joao.pdf                          |   .fila-item
| cv_scan_02.pdf                              |
| digitalizado-3.pdf                          |
+---------------------------------------------+
```

Cor neutra (`--tinta-fraca`), **nunca** `--tijolo`: não é rejeição, é informação.
Fica abaixo de "novos" e acima de "rejeitados".

**2. Pódio — mínimo absoluto.** Reaproveita o slot `.cand-meta` que já carrega
"confiança baixa" hoje. Texto: `texto por OCR`.

```
+----------------------------------------------+
|  87   Candidato 12                        *  |
|       texto por OCR                          |   .cand-meta, 0.75rem, --tinta-fraca
+----------------------------------------------+
```

Regras duras:
- Aparece **só** quando `ocr_confianca === "baixa"`. OCR bom não gera marca.
- Quando OCR baixo e confiança de avaliação baixa coincidem: **uma linha só**,
  `OCR · confiança baixa`. Nunca dois selos.
- Sem cor, sem fundo, sem borda. Não pode competir com a nota, que é o que o
  pódio existe para mostrar.
- **A marca ocupa uma segunda linha sob o nome, e a linha do pódio cresce de 43px
  para 61px quando ela aparece.** Isto é decisão aprovada, não efeito colateral:
  é o mesmo comportamento que o selo de confiança já tinha antes desta entrega, e
  a alternativa — marca ao lado do nome, altura fixa — truncaria nome de
  candidato mais cedo. Dezoito pixels não valem um nome cortado. O que a marca
  não pode fazer continua valendo: deslocar a nota ou quebrar o ritmo de
  varredura da coluna.

**3. Diagnóstico por critério — a explicação honesta.** Um `.nota-aviso` (par
`--ocre`/`--ocre-cl`, já medido em 4,86:1) **acima do primeiro critério**, não no
rodapé junto dos outros avisos.

A posição é a decisão de design, não detalhe de implementação: o aviso muda *como
se lê* cada citação de evidência abaixo dele. Vir depois seria informar tarde.

> Este currículo é um PDF escaneado. O texto foi lido por OCR e pode conter
> falhas — os trechos citados abaixo podem estar imprecisos.

O registro é o mesmo de "sem evidência no currículo": admitir o limite em vez de
fingir certeza.

**4. Métricas da corrida.** Uma métrica a mais no bloco `#metricas`, só quando
`por_ocr > 0`: valor `N`, rótulo `lidos por OCR`. É o "aviso no lote" que o dono
do produto pediu, na granularidade certa.

### Onde NÃO aparece

- **Documento de entrega ao cliente (`shortlist.py`): nunca, sem exceção.** O
  pedido original proíbe qualquer menção a IA, robô ou processamento nesse
  documento. Aviso de OCR é ruído de processo nosso.
- **`faixa-aviso` do topo:** reservada a estado de conta e bloqueio.

### Estados de borda

- **OCR falha inteira** (texto vazio): não é "OCR baixa". Cai no grupo que já
  existe, "Não foi possível avaliar", com motivo "não foi possível extrair texto
  do arquivo escaneado".
- **Vaga inteira sem OCR:** zero elementos novos em qualquer tela. Sem selo
  vazio, sem espaço reservado, sem métrica zerada.

---

## Item 2 — Recuperação de senha por e-mail

Só para o **modo hospedado (SaaS)**. Quem instala local via Claude Desktop/stdio
redefine por linha de comando.

### Como a interface sabe em qual modo está

`GET /api/config` (a configuração pública que a tela já consome em `app.js:186`)
passa a devolver `recuperacao: "email" | "local"`. A interface renderiza um de
dois caminhos — nunca um link morto, nunca um usuário local sem saída.

- `"email"` → o fluxo de três telas abaixo.
- `"local"` → o mesmo link, levando a uma tela estática sem backend nenhum:
  *"A Triagem está rodando no seu próprio computador, então a senha se troca por
  lá."* O comando é `python -m app.senha seu-email@empresa.com` (`app/senha.py`),
  com bloco copiável e a nota de que sessões caem e tokens do conector são
  revogados — o mesmo efeito do link por e-mail. **Construído e conferido.**

### As três telas

Todas dentro da `.entrada-caixa` que já existe. É o mesmo cartão de login com
conteúdo diferente — por isso o piso de qualidade sai de graça.

**Tela A — Esqueci minha senha**

Alcançada por um `.btn-texto` logo abaixo do botão Entrar.

```
+-------------------------------+
| Triagem                       |
|                               |
| Esqueci minha senha           |  h1
| Enviamos um link para voce    |
| criar uma senha nova.         |
|                               |
| E-mail                        |  .campo
| [__________________________]  |
|                               |
| [ Enviar link de recuperacao ]|  .btn-principal.btn-largo
|                               |
| Voltar para entrar            |  .btn-texto
+-------------------------------+
```

Carregando: o spinner que já existe em `.btn-principal[data-ocupado]`.
Erro (rede/servidor): `.erro` abaixo do botão.

**Tela B — Confirmação**

Sem formulário.

```
+-------------------------------+
| Verifique seu e-mail          |  h1
|                               |
| Se existir uma conta com esse |
| e-mail, o link chegou la. Ele |
| vale por 30 minutos e serve   |
| uma vez so.                   |
|                               |
| Reenviar (60s)                |  .btn-texto, desabilitado com contagem
| Voltar para entrar            |  .btn-texto
+-------------------------------+
```

**A formulação "se existir uma conta" é obrigatória, não estilística.** O login
hoje já gasta o mesmo tempo com e-mail inexistente para não revelar quem tem
conta (seção 7 do documento técnico). Esta tela não pode ser o furo que desfaz
isso: mesma resposta, mesmo texto, mesma latência, e-mail existindo ou não.

**Tela C — Nova senha**

Alcançada pelo token na URL.

```
+-------------------------------+
| Criar uma senha nova          |  h1
|                               |
| Senha                         |  .campo
| [__________________________]  |
| Minimo de 10 caracteres.      |  .dica - mesma frase do cadastro
| Prefira uma frase a um simbolo|
|                               |
| [ ] mostrar senha             |  .linha-check
|                               |
| [ Salvar nova senha ]         |  .btn-principal.btn-largo
+-------------------------------+
```

- Sucesso → volta ao login com o `brinde()` que já existe: "Senha alterada. Entre
  com a nova senha." O token some da barra de endereço (`history.replaceState`).
- Token inválido ou expirado → não é `.erro` genérico. É uma tela própria: *"Este
  link expirou ou já foi usado."* + botão "Pedir um link novo" que leva à Tela A.
- Menos de 10 caracteres → validação local antes de enviar, mesma frase do
  cadastro.

### Contrato (para o Alicate)

- `POST /api/auth/recuperar` `{ email }` → **sempre 204**, sempre no mesmo tempo.
  Nunca diferencia e-mail existente de inexistente no corpo, no status ou na
  latência.
- `POST /api/auth/redefinir` `{ token, senha }` → 204, ou 400 com um código
  distinguível (`token_invalido` / `token_expirado` / `senha_curta`).
- **Pedido concreto:** um modo de e-mail *stub* que imprima o link no log do
  servidor em vez de enviar. Com ele eu testo as três telas ponta a ponta antes
  de existir decisão de provedor SMTP — e o item 2 deixa de depender do elo mais
  lento da cadeia.

---

## Item 3 — Painel de status no lugar do botão "Rodar triagem"

### O que muda de verdade

Não é trocar um botão por um texto. Muda a natureza do que a tela mostra.

A barra de hoje representa **um processo que é nosso**: determinado, cancelável,
monótono, que começa quando o recrutador clica e termina sozinho. O painel novo
representa **um registro do que o Claude do recrutador já anotou**: assíncrono,
que pode pausar por minutos, que pode nunca terminar, que não é cancelável por
nós e que avança com esta janela fechada, de outro dispositivo.

Se o painel novo parecer uma barra de progresso rodando, ele mente. O trabalho de
design aqui é justamente não mentir.

### O que sai do `static/`

`#btn-rodar`, `#btn-cancelar`, as chamadas a `POST /executar` e `POST /cancelar`,
o bloco de custo em `desenharMetricas` (`app.js:633`, já condicionado a
`custo_usd > 0`, que agora é sempre falso) e o ramo `estado.modo === "api"` de
`desenharProximoPasso` (`app.js:448`). O `#btn-reavaliar` fica, com outro
comportamento (abaixo).

### Contrato de dados (para o Alicate)

`GET /api/vagas/{id}/status` passa a devolver, sem `rodando` e sem `uso`:

```json
{
  "total": 150,
  "avaliados": 83,
  "eliminados": 12,
  "erros": 3,
  "pendentes": 52,
  "por_ocr": 4,
  "ultimo_registro_em": "2026-09-08T14:31:02Z"
}
```

E `GET /api/vagas` (a lista) — cada vaga ganha `avaliados: <int>`, para o card
mostrar "83/150 avaliados" sem abrir a vaga. Sem esse campo o card cai no rótulo
de status antigo, que descreve um pipeline que não existe mais.

`ultimo_registro_em` (o `avaliado_em` mais recente da vaga) **não existe hoje e é
o campo mais importante do item.** É ele que separa "o Claude está trabalhando"
de "o Claude parou no meio" — sem ele, o painel não tem como ser honesto, e o
recrutador fica olhando 83 de 150 sem saber se espera ou se pede de novo.

Invariante: `avaliados + eliminados + erros + pendentes === total`, sempre.

**Como a manchete conta.** "X de N avaliados" usa
`X = avaliados + eliminados + erros` — tudo que já tem veredito. Se as
eliminações e as falhas ficassem de fora, uma vaga com um único currículo
ilegível nunca chegaria ao estado "completo" e o painel ficaria parado em "149 de
150" para sempre. A linha de detalhe então **decompõe** esse número
(`83 com nota · 12 cortados no eliminatório · 3 com falha`) em vez de parecer
somar a ele — se parecesse soma, o recrutador faria a conta errada.

### Os cinco estados

**1. Nada avaliado (0 de N).** O painel *é* a instrução. Sem barra vazia — barra
em 0% comunica "travado", não "não começou".

```
+------------------------------------------------+
| Nenhum candidato avaliado ainda                |
| A avaliacao roda no seu plano do Claude.       |
| Abra o Claude e mande esta frase:              |
|                                                |
| +------------------------------------+         |
| | Avalie os curriculos da vaga       | [Copiar]|
| | "Analista de Suporte Pleno"...     |         |
| +------------------------------------+         |
+------------------------------------------------+
```

É o `#proximo-conector` que já existe (`index.html:189`), reaproveitado inteiro.

**2. Em andamento (0 < X < N, com registro recente).**

```
+------------------------------------------------+
| 83 de 150 avaliados                            |  0.9375rem, tabular-nums
| ##############.............................    |  .progresso-trilho (2px)
| 12 cortados no eliminatorio - 3 com falha      |  .progresso-texto
| ultimo registro ha 2 min                       |  --tinta-fraca
+------------------------------------------------+
```

"Último registro há 2 min" é o substituto honesto do spinner. Um spinner
afirmaria que algo roda aqui; o carimbo apenas relata o que foi anotado.

**3. Parado no meio (0 < X < N, sem registro novo há mais de 5 min).** O estado
que o desenho antigo nunca precisou ter — e o mais importante dos cinco. Com MCP,
a avaliação simplesmente para: a conversa acabou, o contexto estourou, o
recrutador fechou o Claude. Ninguém avisa.

```
+------------------------------------------------+
| 83 de 150 avaliados                            |
| ##############.............................    |
| Sem registros novos ha 12 minutos. Se o Claude |  .nota-aviso (--ocre)
| parou, peca para continuar:                    |
| +------------------------------------+         |
| | Continue avaliando os curriculos...| [Copiar]|
| +------------------------------------+         |
+------------------------------------------------+
```

**4. Completo (X = N).** O ranking é a estrela; o painel encolhe para uma linha
silenciosa: `150 de 150 avaliados · 12 cortados no eliminatório`. Sem barra, sem
cor, sem celebração.

**5. Com falhas.** Não há faixa de erro global. O painel conta (`3 com falha`), e
o grupo "Não foi possível avaliar" que já existe no ranking mostra quem. Clicar
na contagem rola até o grupo.

### Atualização

Polling continua (a tela não tem outro jeito sem WebSocket, que sairia do padrão
sem build), mas com recuo — porque nada roda do nosso lado e martelar o servidor
a cada 2,5s durante uma conversa de uma hora é desperdício:

| Situação | Intervalo |
|---|---|
| X < N, com mudança nos últimos 2 min | 2,5s (como hoje) |
| X < N, sem mudança há mais de 2 min | 10s |
| X < N, sem mudança há mais de 15 min | para, e mostra um botão "Atualizar" |
| X = N | não faz polling |

Fechar e reabrir a aba mostra o estado real sem exigir ação — o painel lê do
banco, não de memória de sessão.

### "Reavaliar"

Deixa de ser uma ação e vira uma instrução. Não chama servidor nenhum: abre a
mesma frase pronta, com outro texto — *"Reavalie os candidatos da vaga X na
Triagem com os critérios atuais."* — e diz o que a decisão 9 do dono do produto
manda dizer: **"A reavaliação roda no seu plano do Claude e consome sua cota."**

### Vocabulário

As palavras "processando", "rodando", "execução" e "triagem em andamento" saem da
interface. Elas descrevem um pipeline que é nosso, e ele não existe mais. O verbo
é **avaliar**, e o sujeito é o Claude do recrutador.

### Lista de vagas

Cada card ganha `83/150 avaliados` na linha de metadados. Sem gatilho de execução,
a lista de vagas é onde o recrutador vai olhar para saber se terminou — e hoje ela
mostraria só um status de pipeline que não existe mais.

---

## Conferência com dados reais (380px)

Servidor local com os campos do backend já entregues, 35 currículos semeados
(5 por OCR, 3 deles de qualidade baixa; 2 cortados no eliminatório; 1 sem texto
utilizável; 9 ainda não avaliados), viewport de 380x891.

**Item 1.** As quatro variações de marca aparecem exatamente como especificado e
nenhuma a mais: `texto por OCR` (2), `OCR · confiança baixa` (1),
`confiança baixa` (1, extração normal), e nada nos dois candidatos de OCR com
qualidade alta. O aviso no diagnóstico renderiza entre o resumo e o primeiro
critério (ordem conferida no DOM: `det-resumo` → `nota-aviso` → `criterio`). A
métrica "5 lidos por OCR" aparece no bloco da corrida.

**Documento de entrega.** Gerado com um candidato de OCR dentro: nenhuma
ocorrência de "OCR", "escaneado", "extraído", "IA", "Claude", "processamento" ou
"confiança". O critério inegociável está cumprido com dado real, não por
construção.

**Item 3.** Os três estados alcançáveis com o banco semeado renderizaram certo:
"nada avaliado" (instrução + frase pronta, zero barras no DOM), "parado no meio"
(o carimbo virou aviso sozinho depois de 5 minutos sem registro novo, com
"faltam 9") e "completo" (uma linha só: `<p class="status-linha">1 de 1
avaliados</p>`, sem barra e sem frase). O card da lista mostra "26/35 avaliados".

**Item 2.** Fluxo inteiro no navegador: e-mail inexistente e e-mail real produzem
a mesma tela e o mesmo texto; o link saiu pelo stub no log; senha rejeitada pelo
servidor mostrou a mensagem específica dele ("a senha repete poucos caracteres
diferentes"), não um erro genérico; a redefinição voltou ao login com a URL
limpa; e o mesmo link, reusado, caiu na tela "Este link não vale mais". O foco
pousa no título em cada troca de tela.

**380px.** Borda direita mais extrema em toda a varredura do pódio: 353px de 380.
Sem rolagem horizontal.

### Fechamento (backend entregue)

Os dois pontos abaixo foram corrigidos por ele e as pontas do meu lado estão
ligadas: `ranking()` agora parte de `vaga_curriculos` com LEFT JOIN e devolve
`estagio: "erro"` com motivo escrito, então o currículo ilegível aparece no pódio
— e a contagem de falhas no painel virou botão que rola até o grupo. E
`contagens_das_vagas` é fonte única: o painel e o card da lista passaram a usar
`com_veredito` do servidor, em vez de o cliente somar por conta própria (o card
mostrava 23/35 enquanto o painel mostrava 26 de 35 — a mesma divergência de
antes, só que mais sutil). O campo novo `lendo` aparece no detalhe do painel:
extração é trabalho nosso, e enquanto ela roda o candidato ainda não existe para
o conector.

Sobra um detalhe de dado migrado para ele decidir: uma linha de `avaliacoes` com
`estagio='erro'` deixada pelo funil antigo entra no grupo "Não foi possível
avaliar" do pódio, mas não é contada em `erros` pelo `contagens_das_vagas` — em
base nova nunca acontece; em base que já rodou o modo API, o pódio mostraria um a
mais que o painel.

### O que era das duas coisas para o Alicate

1. **Currículo "sem texto utilizável" não aparece no pódio.** `storage.ranking()`
   faz INNER JOIN com `avaliacoes`, e esse candidato nunca teve avaliação — então
   o painel conta 1 e o recrutador não tem onde clicar, nem nome, nem arquivo
   para reenviar. É justamente quem mais precisa de ação dele. O conserto é
   partir de `vaga_curriculos` com LEFT JOIN, devolvendo `estagio: "erro"` para
   quem está sem texto ou com anonimização retida. Enquanto isso, o rótulo na
   tela mudou de "com falha" para "sem texto utilizável", que é o que o número
   realmente significa.
2. **`avaliados` da lista e do status têm definições diferentes.** O da lista
   conta linhas de `avaliacoes`; o do status conta `estagio = 'avaliado'` e soma
   eliminados e erros à parte. Hoje os dois dão o mesmo número por coincidência
   do dado; vale alinhar antes que divirjam na frente do cliente.

---

## Identidade visual passa a ser da Pigmento

A partir de agora, **paleta, tipografia, wordmark e tom de voz não são mais
decisão minha**. Quem responde por isso é a Pigmento. O que está hoje no `:root`
do `styles.css` foi escolha minha no improviso e vale como provisório até ela
mandar os tokens dela.

Isso não afrouxa nada: os valores dela chegam com contraste **medido** (4.5:1
texto normal, 3:1 texto grande e elemento de interface), e continuam valendo
380px sem rolagem horizontal, foco de teclado visível e `prefers-reduced-motion`.
Token novo que não passe nessa régua volta para ela, não entra na spec.

### O contrato de troca (para o Alicate)

A identidade está isolada num único bloco `:root`, hoje em **`static/tokens.css`**
(saiu do `styles.css`, que já não tem `:root` nenhum). Aplicar a Pigmento é
**trocar valor, não estrutura** — nenhum seletor fora desse bloco deve ganhar cor
literal. Slots vigentes:

- superfícies: `--papel`, `--papel-fundo`, `--painel`
- texto: `--tinta`, `--tinta-media`, `--tinta-fraca`
- fios: `--regua`, `--regua-forte`
- semântica: `--petroleo` (+`-cl`, `-md`), `--ocre` (+`-cl`), `--tijolo` (+`-cl`)
- tipografia: `--sans`, `--serif`

Se aparecer hex solto fora do `:root`, é regressão — a próxima troca de paleta
deixa de ser uma edição e vira uma caçada.

**A regra do `--contorno` deixou de viver só nesta prosa.** `tests/` passou a
cobrir três modos de falha desta família, os três achados por conferência à mão
com a suíte verde:

1. hex literal fora do bloco de tokens (`test_identidade.py`);
2. `var(--x)` usado numa superfície que não recebe aquele token — o modo
   silencioso, em que `color` herda do pai e a hierarquia colapsa sem nada sumir;
3. **limite de controle e separador trocando de papel**: os cinco seletores que
   são limite de controle não podem usar `--regua-forte`, **e** têm de usar
   `--contorno`.

A segunda metade do item 3 é o que o torna sólido. Uma proibição pode ser
satisfeita fugindo para um terceiro valor; exigir `--contorno` fixa a intenção em
vez de só barrar uma saída. É a mesma forma do requisito central do diagnóstico
comparativo — "os números exibidos somam a diferença de nota": uma regra
verificável por construção vale mais que uma que depende de vigilância.

O que o teste **não** compra: ele protege os cinco seletores, não a regra. Um
controle novo amanhã não entra na lista sozinho. Para esse caso o que resta é a
pergunta que a spec já dá — *se esta linha sumisse, o usuário ainda saberia onde
o controle começa?* — e ela continua sendo trabalho de quem escreve, não do teste.

### Duas restrições que mandei para ela, e que valem como regra

**Fonte.** Sem build, a família entra por `<link>` do Google Fonts no
`index.html` ou por stack de sistema. O app roda em `127.0.0.1` e às vezes
offline, então toda família precisa de fallback de sistema que não quebre a
diagramação quando a CDN não responde. Família de marca com queda visível só é
aceitável no wordmark; nunca no corpo de texto.

**Cor não julga gente.** O produto ordena candidatos. `--petroleo` (forte),
`--ocre` (talvez) e `--tijolo` (erro) não podem virar semáforo
verde/amarelo/vermelho de aprovado/reprovado — nenhum candidato é "vermelho". E
cor nunca é o único portador de sentido: colocação, nota e rótulo já dizem tudo
sem ela.

### Tokens ratificados pela Pigmento

Ela revisou o `:root` inteiro e **não trocou nenhum hex** — formalizou o que já
existia como fonte única, preencheu os pares que faltavam e fechou as regras de
uso. O nome do produto **continua "Triagem"**, validado com a Bussola: sem
rebranding por causa do pivô MCP. Os 15 slots estão certos para o tamanho do
produto; nenhum entra, nenhum sai.

**Cor.** Ratios conferidos por mim, ponto a ponto, e batem com os dela: `--tinta`
13.99:1, `--tinta-media` 8.50:1, `--tinta-fraca` 5.19:1 sobre `--papel`;
`--petroleo` 7.88:1; `--ocre` 4.86:1 sobre `--ocre-cl`; `--tijolo` 6.91:1 sobre
`--tijolo-cl`. Os três pares que faltavam também: branco sobre `--petroleo`
9.05:1, sobre `--ocre` 5.58:1, sobre `--tinta-fraca` 5.96:1 — os fundos dos
estados `.decisao-btn.ativa`. Todos passam AA.

**Tipografia.** Base 15px/1.55 e a escala de títulos ficam como estão. A serif é
Instrument Serif peso 400, sem itálico salvo o próprio glifo de aspa de abertura
da citação, e ela entra em **exatamente três lugares**: a nota do candidato
(1.5rem no ranking, 2.75rem no hero do detalhe, 1.5rem por critério), a citação
de evidência (1.1875rem/1.5) e o wordmark da entrada (2.5rem/1). É sempre número
ou citação. Proibida em botão, campo, navegação, tabela, filtro, selo, aviso e
qualquer microcopy funcional — porque serif de exibição quebra pior no fallback
de sistema, e texto funcional não pode depender de fonte decorativa para ficar
legível.

Os dois ritmos ficam ratificados como regra, não como acaso da implementação:
densidade de varredura no ranking (linha de 0.5625rem de padding, sans compacto,
serif só no número) e ritmo de leitura no diagnóstico (respiro de 2rem, serif
também na citação).

**Wordmark.** `.entrada-marca` é o único momento de marca do produto: serif
2.5rem, nunca abaixo de 1.75rem em tela nenhuma, respiro mínimo de 0.75× o
tamanho da fonte nos quatro lados. A 380px cabe sem ajuste. A `.topo-marca` é
navegação, não marca — sans 600 1rem, fica como está. O `<title>` não tem regra
de identidade.

**No documento de entrega ao cliente: zero wordmark.** Nenhuma marca nossa, nem
discreta, nem monocromática. Confirmado com o Alicate que `app/shortlist.py` já
é assim — título da vaga, cabeçalho com recrutador/empresa/data, rodapé falando
de "critérios acordados" e "recomendação da empresa". Isso é condição da
Bussola, não escolha estética: o documento é do recrutador, a ferramenta não
aparece. É a única regra de wordmark que vale naquele arquivo — não ter nenhuma.

**Tom de voz.** Segunda pessoa direta; presente para estado, imperativo educado
para ação; sem jargão além do que o recrutador já precisa saber (token do
conector passa, "endpoint" não); nunca culpar o usuário ("Você errou" vira "Isso
não confere"); nunca juízo de valor sobre candidato em microcopy nenhuma. O
padrão de incerteza é o que já fazemos: "Sem evidência no currículo" em vez de
inventar certeza. O inventário do texto que já existe está em
`MICROCOPY-ATUAL.md`, esperando a revisão dela.

### Duas regressões de contraste que a ratificação expôs

A própria Pigmento marcou `--regua-forte` como "confirmar 3:1 antes de usar como
borda funcional". Confirmei, e não passa.

**1. `--regua-forte` acumula duas funções, e só uma delas tem exigência.**
`#b9c1b6` dá 1.85:1 contra `--painel`, 1.61:1 contra `--papel` e 1.52:1 contra
`--papel-fundo`. Como fio de separação isso é correto e bonito — divisor não é
componente de interface e não tem piso de contraste. Mas o mesmo token é a
**borda que define o limite** de campo de formulário (`styles.css:136`),
`.btn-secundario` (174), `.filtro` (470), `.decisao-btn` (666) e a zona de
soltar arquivo (388). Aí vale a 1.4.11, que é AA e pede 3:1, e o preenchimento
não salva: `--painel` sobre `--papel` é 1.13:1, então a borda é mesmo a única
coisa que diz onde o controle começa.

O conserto não é escurecer `--regua-forte` — isso engrossaria todos os divisores
da tela de uma vez. É **partir o token em dois**: `--regua-forte` continua sendo
o fio de separação como está, e entra um `--contorno` só para limite de
controle. O teto matemático é luminância ≤ 0.30 para dar 3:1 sobre branco;
`#76837a` fecha em 3.96:1 / 3.45:1 / 3.26:1 contra `--painel` / `--papel` /
`--papel-fundo`. O valor final é dela — mandei o teto e os candidatos.

**2. A bolinha de decisão no ranking é cor sozinha.** `styles.css:537-542` +
`app.js:1025`: entrevistar, reserva e arquivado diferem só pelo `background`, e
o único rótulo é um `title` — tooltip, que não aparece para teclado nem é lido
de forma confiável. Isso é 1.4.1 (Uso de cor, nível A), e a variante arquivado
ainda usa `--regua-forte` a 1.85:1, o que também derruba a 1.4.11. É exatamente
a regra que a Pigmento acabou de formalizar — cor nunca é portador único — só
que aqui a violação já existe, não é hipótese para o que vier.

Os selos do detalhe estão certos (texto + cor). É a bolinha do ranking que
precisa de rótulo em texto ou de forma própria por decisão, além da cor.

---

## Spec dos dois consertos de contraste (itens 7 e 8 do backlog)

Pigmento aprovou o valor e a partição do token; Bussola subiu os dois para antes
dos itens de identidade e vai tratá-los como critério de aceite do teste ponta a
ponta. Isto aqui é a spec implementável para o Alicate.

### Item 7 — `--contorno`, o token que faltava

Entra um slot novo no `:root`:

```css
--contorno: #76837a;   /* limite de controle — 3.96:1 painel, 3.45:1 papel, 3.26:1 papel-fundo */
```

**A regra, que é o que importa mais que o hex:** `--regua-forte` é *só* separação
decorativa e nunca define limite de controle. `--contorno` é a única borda que
carrega significado de interface, e por isso tem piso de 3:1 nas três
superfícies. Quem for escolher entre os dois no futuro pergunta uma coisa só: se
esta linha sumisse, o usuário ainda saberia onde o controle começa? Se a resposta
for não, é `--contorno`.

**Trocar `var(--regua-forte)` por `var(--contorno)` em seis lugares** — todos são
o limite de um controle, e o preenchimento não os salva porque `--painel` sobre
`--papel` é 1.13:1:

| Seletor | Por quê |
|---|---|
| `input, textarea, select` | a borda é o campo |
| `.btn-secundario` | a borda é o botão |
| `.solta` (tracejada) | a borda é a zona de soltar |
| `.filtro` | a borda é a pílula |
| `.decisao-btn` | a borda é o botão |
| `.marca-arquivado` | ver item 8 |

Por seletor, não por número de linha: o token novo empurrou o arquivo inteiro
para baixo assim que entrou. Número de linha em spec que vira checklist envelhece
no primeiro commit.

**Não trocar nos outros oito.** São separação, e separador não tem piso de
contraste — escurecer todos de uma vez engrossaria a tela inteira, que é
exatamente o efeito colateral que a partição do token existe para evitar:
`.vagas-tabela`, `.distribuicao` (moldura de gráfico — quem carrega dado ali são
as fatias), `.metricas`, `.ranking`, `.ranking-grupo`,
`.trilho-preenchido.magra` (a nota em número está do lado, a barra é redundante),
`.evidencia-ausente` (quem carrega o sentido é o texto "Sem evidência no
currículo"), `.decisao`.

A conta fecha em 15 ocorrências de `--regua-forte`: 1 definição + 6 trocadas +
8 mantidas.

Os `:hover` que já mudam para `--tinta-fraca` (5.96:1) continuam como estão.

### Item 8 — a marca de decisão no ranking

Pigmento decidiu: **forma, não palavra**. A coluna tem 0.5rem e o ranking existe
para varrer 10-40 nomes de relance — uma palavra ali mata a densidade.

**Antes da forma, o achado que muda a implementação.** A linha do ranking é um
`<button>` com `aria-label` próprio (`app.js:1016`). `aria-label` **substitui a
subárvore inteira** no cálculo do nome acessível: hoje o `title` da bolinha não é
"pouco confiável", ele é **inexistente** para leitor de tela, e um `<span
class="sr">` colocado dentro do botão seria engolido do mesmo jeito. A Pigmento
ofereceu as duas saídas — `.sr` ou rótulo no elemento; **aqui só a segunda
funciona**. A decisão tem de entrar no `aria-label` do próprio botão:

```js
aria-label="${esc(r.nome)}, ${semNota ? esc(faixaDe(r)) : `nota ${score} de 100`}${
  meta ? `, ${esc(meta)}` : ""}${decidiu ? `, ${esc(ROTULO_DECISAO[r.decisao])}` : ""}"
```

Lê como "Ana Souza, nota 87 de 100, entrevistar". Candidato sem decisão não
anuncia nada — ausência de decisão não é informação que mereça ser repetida em
40 linhas. O `title` sai; ele não fazia nada além de aparecer no mouse.

**As três formas.** Marca vai a 0.5rem para preencher a coluna e dar corpo ao
anel:

```css
.marca-decisao     { width: 0.5rem; height: 0.5rem; justify-self: center; }
.marca-entrevistar { border-radius: 50%; background: var(--petroleo); }
.marca-reserva     { border-radius: 50%; background: transparent;
                     box-shadow: inset 0 0 0 2px var(--ocre); }
.marca-arquivado   { height: 2px; border-radius: 1px; background: var(--contorno); }
```

Cheio, anel, traço. A leitura é a própria semântica: entrevistar é presença
sólida, reserva é contorno à espera, arquivado é uma linha fechando. A cor segue
ali, mas como reforço — some a cor e as três continuam distintas.

Contraste das três contra `--painel`: `--petroleo` 9.05:1, `--ocre` 5.58:1,
`--contorno` 3.96:1. As três passam os 3:1 de objeto gráfico.

**380px:** nada muda de largura — a coluna continua 0.5rem e a marca cresce
0.0625rem dentro dela. Sem risco de empurrar a nota ou quebrar a linha.

**`forced-colors`:** o modo de alto contraste do sistema achata `background` e
`box-shadow`, então as três formas podem virar a mesma coisa. Não é regressão
nova e não precisa de tratamento agora, justamente porque o `aria-label` passa a
carregar a decisão em texto — que é o que resolve o caso de verdade.

### Critério de aceite

1. Nenhuma ocorrência de `var(--regua-forte)` sobrevive nos seis seletores da
   tabela; as outras nove continuam intactas.
2. Nenhum hex literal fora do `:root` — a próxima troca de paleta continua sendo
   uma edição, não uma caçada.
3. Leitor de tela numa linha decidida anuncia nome, nota e decisão.
4. Em escala de cinza, entrevistar/reserva/arquivado continuam distinguíveis.
5. 380px sem rolagem horizontal no ranking, como já estava.

### Critério 2 — fechado em `static/`, e o que ele arrastou junto

O Alicate recusou dar o critério por cumprido quando não estava, e a recusa
rendeu mais que o conserto. Eram quatro sítios de hex literal, todos anteriores
a esta mudança: três em `styles.css` (`.btn-principal`, seu `:hover`,
`.decisao-btn.ativa`) e um em `app.js:420` — uma rampa de sete cores morando num
array de JavaScript, com seis valores que não existiam em paleta nenhuma.

**Nomes, decididos pela Pigmento:**

- `--petroleo-esc: #0e3c3a` — o `:hover` da ação. Branco sobre ele dá 12.17:1;
  o estado sempre esteve certo, faltava nome.
- `--tinta-reversa: #fff` — tinta clara sobre fundo escuro. Ela recusou o
  `--sobre-acao` que tinha sido proposto (nome funcional numa família toda
  material: papel, tinta, painel, régua, petróleo, ocre, tijolo — um nome que
  descreve o uso mente no dia em que o uso muda) e recusou também reusar
  `--painel`, que tem exatamente o mesmo `#ffffff`: a economia trocaria duas
  coisas que variam por motivos diferentes por uma coincidência numérica de hoje.
- `--petroleo-1` … `--petroleo-7` — a rampa, com os mesmos sete hexes de sempre.
  Zero mudança visual foi exigência dela: interpolar mexeria na aparência antes
  de ela ter olhado o resultado.

**A regra de nomenclatura que veio junto**, e que vale mais que os três nomes:
sufixo descritivo (`cl` / `md` / `esc`) é variante semântica de uma cor; escala
numerada (1..N, do escuro ao claro) é só para rampa sequencial de visualização de
dado, onde o que importa é a ordem e não o papel individual de cada tom.

**O mecanismo é do Alicate e é melhor do que mover os hexes para o `:root`:** o
JavaScript nunca encosta em cor. Ele calcula o índice e emite `data-tom`; o CSS
tem os sete pares `[data-tom="n"] { background: var(--petroleo-n); }`. Sem
`getComputedStyle`, sem custo em runtime, e quem for trocar um tom não precisa
saber que existe JavaScript no projeto.

Conferido por mim no CSS **servido pelo servidor**, não só no arquivo local:
tokens presentes, os sete pares de `data-tom`, as três formas da marca de
decisão, `--regua-forte` em 1 definição + 8 usos, e zero hex literal fora do
`:root`. A rampa mapeia um a um contra os valores antigos, na ordem.

**O órfão do documento do cliente.** `app/shortlist.py:155` tinha
`border-top-color:#999` dentro do `@media print` — o caminho que gera o PDF que
vai para a mesa do cliente do recrutador. Não era falha de contraste: é o fio
que separa um candidato do outro no impresso, separação decorativa pura, sem
piso. Era um valor que ninguém escolheu, no único artefato que sai da nossa
casa. A Pigmento resolveu na hora, sem esperar a consolidação das paletas: vira
`var(--regua-forte)`, token que o próprio arquivo já define.

A simetria com o item 7 é o que me deixa tranquila com a troca: na tela nós
**tiramos** `--regua-forte` de onde ele era limite de controle e precisava de
3:1; aqui nós o **colocamos** onde ele é separação de verdade. O token não mudou
de valor nem de sentido — passou a estar nos lugares certos nos dois arquivos.

**O que continua aberto** é a duplicação das paletas em Python: `shortlist.py`,
`relatorio.py` e `rotas_mcp.py` têm cada um seu `:root` digitado à mão dentro de
uma string. Pelo critério "fora do `:root`" passam; pelo critério que importa,
são três paletas paralelas. É item próprio de backlog e quem prioriza é a
Bussola.

### A regra virou teste

Três vezes em duas conversas um sítio de cor apareceu por inspeção manual, e nas
três o escopo estava certo e a varredura incompleta. Regra que depende de alguém
lembrar não é regra. O Alicate fechou isso em `tests/test_identidade.py`: CSS só
guarda cor no `:root`, JavaScript não carrega cor nenhuma, a rampa mora no CSS
com os sete tokens e as sete regras, e a dívida em Python fica travada por teto
numérico que só desce. Ele conferiu que o teste morde antes de aceitar que passa.

É a diferença entre uma regra escrita numa spec e uma regra que ninguém precisa
lembrar.

### Registrado para quando a rampa for revisada

A `.crit-barra` — o fio de 3px sob cada critério na tela de rubrica — usa a mesma
rampa, mas o trilho dela é `--papel-fundo` e o primeiro desenho usa o peso cru,
não normalizado. Do sexto critério em diante o fio é `--petroleo-6` (1.50:1) ou
`--petroleo-7` (1.22:1) sobre esse trilho, e some.

Não é falha de acessibilidade: a porcentagem está no campo numérico ao lado, e
nenhuma informação depende de enxergar o fio. É perda de utilidade — uma barra
que não dá para ver não faz o trabalho pelo qual existe. Fica como meio critério
para a Pigmento decidir entre escala fixa e interpolação, não como dívida
escondida.

A `.distribuicao` — a barra empilhada, que era a que preocupava — **não** tem esse
problema: as fatias são `flex: 0 0 (peso / soma) * 100%`, normalizadas pela soma
e não por 100, então preenchem a barra inteira some quanto somar. O único caso de
trilho nu é soma zero, e aí a legenda mostra o aviso de soma errada. Não existe
caminho onde o trilho aparece sem o aviso ao lado.

### Conferência visual — o que falta

Ambiente pronto: servidor em `127.0.0.1:8000` — a Bussola fechou 8000 como porta
canônica e o Alicate reverteu o override antes do ponta a ponta, para não sobrar
dois valores circulando quando o conector for testar descoberta de OAuth. O
portal Triagem380 já aponta para lá. Organização de conferência
isolada por `org_id` com os quatro estados de decisão em quatro linhas seguidas
do mesmo grupo, sem filtro. O Alicate conferiu pelo `storage.ranking()`, a mesma
função que o endpoint usa.

**Critério 5 — cumprido, e agora medido na interface de verdade**, não só por
construção. Entrei na organização de conferência pelo portal a 380px e li a
geometria da árvore de acessibilidade: viewport 380, as quatro linhas do ranking
em `x=12, largura=341` — borda direita em 353. O grupo de filtros mede 341, a
busca 256. Nada passa de 380. A grade continua `3rem minmax(0, 1fr) 0.5rem` e a
marca cresceu 0.0625rem dentro de uma coluna que já era 0.5rem.

**Critério 3 — confirmado no ar**, pelos rótulos que o navegador realmente expõe:

    "Ana Souza, nota 88 de 100, entrevistar"
    "Bruno Martins, nota 81 de 100, reserva"
    "Carla Nogueira, nota 74 de 100, arquivado"
    "Diego Alves, nota 69 de 100"

Nome, nota e decisão na ordem especificada, e o candidato sem decisão não anuncia
nada. É a prova de que o conserto do `aria-label` funcionou onde o `title` e um
`span.sr` teriam sido inertes.

**Critério 4 — cumprido.** O risco era específico: a forma "anel" da reserva é um
`inset 0 0 0 2px` num quadrado de 8px, deixando um miolo de 4px. Geometricamente é
distinto do disco cheio da entrevistar, mas num display sem alta densidade esses
4px podiam borrar e o anel virar um disco apagado — e aí as duas formas deixariam
de ser distinguíveis sem cor, que é o que o critério existe para impedir.

Não borra. Na conferência do layout estreito, o anel sai **nitidamente vazado, com
o oco central visível**, e as três marcas ficam claramente distintas entre si:
disco cheio (Ana, 88), anel (Bruno, 80), traço (Carla, 74), e nada para quem não
decidiu (Diego, 68) — que era o quarto estado esperado.

Isso basta para a escala de cinza, e não por analogia: um miolo aberto é diferença
de luminância dentro da própria marca, não de matiz. Disco sólido contra círculo
com furo continuam distintos quando a cor sai, e o traço é outra geometria. O que
faltava saber era se o furo sobrevivia à renderização. Sobreviveu.

**Procedência da evidência**, para quem for auditar: a captura do portal ficou
quebrada o tempo todo — navegar, ler a árvore de acessibilidade, preencher e
clicar funcionavam, imagem não saía. Os prints vieram do dono do produto, e eu
fechei o critério sobre a descrição deles, não sobre pixels que eu mesma tenha
visto. A descrição responde exatamente à pergunta que estava aberta — se o oco
aparece —, e é por isso que aceito; mas fica registrado que é observação relatada,
no mesmo espírito com que o Alicate registrou ter conferido estrutura e não pixel.

A Bussola resolveu isso sem trabalho avulso: a reconferência com pixel de verdade
foi dobrada dentro do item 12.

**E ela aconteceu.** A captura do portal voltou a funcionar e eu conferi as duas
coisas:

1. **Na interface real**, a 380px, com os quatro estados no mesmo grupo: disco
   cheio (Ana, 88), anel (Bruno, 80), traço (Carla, 74), nada (Diego, 68). O
   miolo de 4px sobreviveu à renderização — o anel lê como anel, não como disco
   apagado. Sem rolagem horizontal, o que fecha o critério 5 também com o olho.
2. **Em escala de cinza de verdade**, e não por raciocínio: montei a mesma lista
   com o `tokens.css` e o `styles.css` atuais, lado a lado com uma cópia sob
   `filter: grayscale(1)`. As três formas continuam distintas sem cor nenhuma.

**O que a conferência mostra com honestidade:** sem cor, o disco e o anel têm
peso parecido, e o que os separa é o furo. A 8px ele é visível e funciona — mas é
uma distinção fina, não uma distinção berrante. Se algum dia precisar de margem
maior (tela pequena, baixa visão), a alavanca é engrossar o anel, não trocar a
forma. Não é necessário agora, e registro para não parecer que passou com folga
maior do que passou.


---

## Mensagem de e-mail inválido — texto final

Pendência antiga da Bussola: a mensagem vem crua do `EmailStr` do Pydantic pelo
handler de 422 (`main.py:203`) e é a mesma em cadastro, convite e recuperação de
senha. Correção central, um texto serve os três.

### Como é hoje

O handler monta `"{rótulo}: {mensagem}"` e trata o caso de e-mail com um
`if "valid email" in mensagem`. O resultado na tela é:

```
e-mail: não parece um e-mail válido
```

Três problemas, e o terceiro é o que ninguém vê à primeira leitura:

1. **Redundante** — o rótulo e a mensagem repetem "e-mail".
2. **Não acionável** — diz o que está errado, não o que fazer.
3. **Não é uma frase, é um registro de log.** A forma `campo: mensagem` serve para
   depuração. Quem lê é um recrutador no meio de um cadastro.

### O texto

```
Esse e-mail não foi aceito. Confira o endereço digitado.
```

Por que assim, contra as regras de voz da Pigmento:

- **Não culpa.** "Não foi aceito" fala do que aconteceu com o dado, não de quem
  digitou. "E-mail inválido" é veredito, e "você errou" é o que a regra proíbe.
- **Acionável em uma ação só**, e a certa: conferir. Não manda tentar de novo, que
  é filler — quem vai tentar de novo já sabe disso.
- **Não afirma a causa.** Aqui está a parte que quase escapou. A tentação é
  escrever "confira se está completo, com @ e domínio", que ajuda no caso comum,
  o erro de digitação. Mas o validador também recusa endereços **completos e bem
  formados** de domínio de uso especial — foi assim que a conta de conferência com
  `@conferencia.local` foi barrada. Para quem digitou certo um domínio interno,
  "confira se tem @ e domínio" é um beco sem saída: a pessoa olha, está tudo lá, e
  não sabe o que fazer. O texto curto não promete um diagnóstico que não temos.

### O detalhe de implementação que faz ou quebra o texto

O handler prefixa o rótulo do campo. Sem mudança, o resultado seria:

```
e-mail: Esse e-mail não foi aceito. Confira o endereço digitado.
```

**Neste caso o prefixo tem de ser suprimido** e a frase sai sozinha. É a diferença
entre a copy funcionar e ela ficar pior que a de hoje.

### O vizinho, que não é escopo desta correção mas é o mesmo handler

Só o caso de e-mail tem tradução. Todas as outras mensagens do Pydantic saem em
inglês, e não é hipotético: `organizacao` e `nome` têm `min_length=2`
(`models.py:163-164`), então uma empresa de uma letra no mesmo formulário de
cadastro devolve

```
empresa: String should have at least 2 characters
```

Corrigir o e-mail e deixar isso ao lado é polir uma frase no meio de um parágrafo
em outro idioma. Não estou pedindo agora — é item de backlog e quem prioriza é a
Bussola —, mas o conserto é do mesmo tamanho: um mapa de tipo de erro para frase
em português, no lugar onde hoje há um `if` para um caso só.

Vale junto uma nota sobre a forma: quando há mais de um erro, o handler junta com
`"; "`. Uma frase completa misturada a fragmentos `campo: msg` lê mal. Se o mapa
for feito, todas viram frase e o problema some junto.


## O mapa completo de erros de validação

A Bussola aprovou ampliar: em vez de um `if` avulso para o e-mail, um mapa de tipo
de erro do Pydantic para frase em português, cobrindo todos os campos. Resolve
forma e conteúdo de uma vez.

**A frase do e-mail deixa de ser exceção e vira o padrão.** O caso genérico é a
mesma construção — "não foi aceito" + o que conferir —, e o e-mail é só a
especialização que troca "o valor" por "o endereço". Isso importa porque um mapa
onde uma entrada foi escrita com carinho e as outras no automático se denuncia na
primeira tela.

### As frases

Levantei os erros que **de fato alcançam** o recrutador, a partir das restrições
nos modelos de entrada (`models.py:158-208`) — não é lista genérica de Pydantic.

**Versão final** — a minha primeira redação foi substituída pelo rascunho do
Chave, que é melhor por não depender de artigo; ver a seção de respostas adiante.

| Erro | Frase | Onde acontece hoje |
|---|---|---|
| `missing` | Falta preencher {rótulo}. | qualquer campo obrigatório |
| `string_too_short` | {Rótulo} precisa de pelo menos {n} caracteres. | empresa e nome (2), token (10), cargo (2), descrição (40) |
| `string_too_long` | {Rótulo} pode ter no máximo {n} caracteres. | nome e empresa (120), cargo (140), anotação (4000) |
| e-mail | Esse e-mail não foi aceito. Confira o endereço digitado. | cadastro, convite, recuperação |
| `int_parsing` | {Rótulo} precisa ser um número. | retenção, peso |
| `greater_than_equal` | {Rótulo} não pode ser menor que {n}. | peso (0) |
| `less_than_equal` | {Rótulo} não pode ser maior que {n}. | peso (100) |
| `literal_error` | (com a Pigmento — ver adiante) | decisão, papel |
| tipo errado | {Rótulo} veio num formato inesperado. | JSON malformado |
| qualquer outro | Não foi possível validar {rótulo}. | rede de segurança |

As duas duplas são espelhadas de propósito: **pelo menos / no máximo** e **menor
que / maior que**. É o que faz o conjunto ler como um sistema e não como dez
frases escritas em dias diferentes.

### Três coisas que a implementação precisa saber

**1. O artigo deixou de ser problema.** A minha primeira redação ("Preencha o
e-mail") obrigava o mapa de rótulos a carregar artigo. A construção do Chave —
"Falta preencher {rótulo}." — dispensa isso por inteiro. Nenhum artigo, nenhum
mapa extra. Registro aqui só para quem leu a versão antiga não ir procurar.

**2. Cinco campos não têm rótulo e cairiam com o nome cru:** `token`, `convite`,
`papel`, `decisao` e `anotacao`. Hoje isso é invisível porque só o e-mail é
traduzido; com o mapa, `anotacao: ...` apareceria na tela. Precisam entrar em
`CAMPOS_EM_PORTUGUES`.

**3. O separador muda.** Com fragmentos `campo: msg`, juntar com `"; "` fazia
sentido. Com frases completas terminadas em ponto, o separador é espaço — senão
sai "Preencha o e-mail.; A empresa precisa de...".

### Onde o mapa não deve atropelar

Onde a tela já tem mensagem própria, escrita para aquele contexto, o mapa é rede
de segurança e não substituto. O caso claro é a descrição da vaga: `min_length=40`
geraria "A descrição precisa de pelo menos 40 caracteres", enquanto a tela já diz
"A descrição está curta demais para gerar critérios úteis" e o campo mostra
"{n} caracteres — a partir de 40 dá para gerar critérios". A segunda explica **por
que** 40; a primeira só repete o número.

Nota de escopo: a senha **não** tem `min_length` no modelo (`models.py:167`), então
senha curta não passa por aqui — é validada na rota, com texto próprio. O mapa não
precisa de frase para isso.


---

## Tela de autorização do conector — layout da divulgação de transferência

Correção jurídica pedida pela Bussola (item 7). O texto está sendo fechado com a
Pigmento; isto é o layout, que não depende das palavras finais.

### A tela hoje

`rotas_mcp.py:112`, cartão de 26rem, e ela já tem **três registros visuais**:

1. lista de permissões — 0.9rem, `--fraca`. Recessiva de propósito.
2. `.quem` — o único bloco destacado: fundo `--papel` e fio de 2px `--petroleo` à
   esquerda. Destaca **identidade**: "confira que é você".
3. `.rodape` — 0.8rem `--fraca`, separado por fio. Registro de letra miúda.

### Posição: depois da lista, antes do `.quem` — concordo, e por quê

A ordem de leitura fica: **o que ele vai poder fazer** (lista) → **para onde o dado
vai** (linha nova) → **quem é você** (`.quem`) → **decidir** (botões).

Capacidade, consequência, identidade, decisão. E a divulgação precisa ser lida
antes dos botões: colocada depois do `.quem` ela encostaria no par
Autorizar/Recusar, justamente onde a mão já está indo.

### Tratamento visual: nenhum. E isso é decisão, não economia

**Sem caixa, sem cor, sem ícone.** Parágrafo comum, no corpo de 15px do cartão,
com `--tinta` cheia — 16.06:1 sobre `--painel`.

Três motivos, e o terceiro é o que decide:

1. **Um segundo bloco destacado apaga o primeiro.** Num cartão de 26rem, dois
   realces significam nenhum realce, e o `.quem` perde a função de "confira que é
   você".
2. **Caixa de aviso lê-se como boilerplate.** As pessoas aprenderam a pular caixas
   com borda colorida — é onde mora o texto que ninguém precisa ler. Emoldurar a
   divulgação a tornaria menos lida, não mais.
3. **É tela de consentimento.** Alarmar visualmente enviesa a decisão que o
   recrutador está tomando ali. Isto é divulgação, não advertência: precisa ser
   clara e neutra. Assustar seria tão errado quanto esconder.

E ela não fica fraca por não ter enfeite: **é o único texto de força total naquela
região.** A lista acima é 0.9rem `--fraca`, o rodapé abaixo é 0.8rem `--fraca`.
Um parágrafo em `--tinta` no corpo do cartão se destaca por contraste de peso, sem
um pixel de decoração — e é mais proeminente que a lista de permissões, que é
exatamente a hierarquia certa: para onde o dado vai importa mais que o detalhe do
que a ferramenta pode fazer.

O que **não** pode é cair no `.rodape`. Ali é letra miúda, e uma divulgação exigida
por revisão jurídica na letra miúda é o oposto do que a revisão pediu.

### O problema do nome dinâmico no meio da frase

O corpo hoje é `"Se você autorizar, o Claude vai poder, em seu nome:"`. Trocar por
`{cliente}` resolve o ChatGPT — mas `_nome_do_cliente()` cai em `"Um aplicativo"`
quando o cliente não está registrado (`rotas_mcp.py:79`), e aí sai **"Se você
autorizar, o Um aplicativo vai poder"**.

O título aguenta porque a inserção é no fim (`Autorizar Um aplicativo?`, já
esquisito hoje); no meio da frase, com artigo antes, quebra.

Duas saídas, e recomendo a segunda:

1. Frase sem artigo: `"Se você autorizar, {cliente} vai poder, em seu nome:"`.
   Funciona com Claude, ChatGPT e até com o fallback.
2. **Trocar o fallback de `"Um aplicativo"` para `"o aplicativo"`.** Conserta os
   dois lugares de uma vez: o corpo passa a ler "o aplicativo vai poder" e o título
   vira "Autorizar o aplicativo?", melhor que o "Autorizar Um aplicativo?" de hoje.

É o mesmo problema de artigo do mapa de erros de validação, e aqui custa mais caro
porque a tela é a do consentimento.

**Resolvido:** a Bussola passou a troca do fallback ao Alicate como bug próprio,
independente do resto desta correção — não precisa esperar o texto da Pigmento
para entrar.

### Notas de implementação

- O nome do cliente **já vem escapado** (`rotas_mcp.py:95`), então usá-lo em mais
  um lugar não abre superfície nova. Conferi antes de pedir.
- Esta tela tem `:root` próprio — é uma das três paletas paralelas em Python. A
  linha nova usa `--tinta`, que já existe lá. **Nenhum valor de cor novo entra
  aqui.**
- A 380px o cartão fica em 348px com 284px de conteúdo. Um parágrafo corrido não
  cria rolagem; uma caixa com padding próprio apertaria mais um nível.
- O texto precisa ser **um único template** com as partes variáveis nomeadas
  (provedor e destino), não duas frases mantidas em paralelo — senão uma delas
  envelhece sozinha no dia em que entrar um terceiro provedor.


## Mapa de erros — respostas ao rascunho do Chave

O rascunho dele é melhor que o meu num ponto e vale dizer qual: **as frases dele
não dependem de artigo.** "Falta preencher nome." funciona; a minha versão
("Preencha o e-mail.") obrigava o mapa de rótulos a carregar artigo, e eu tinha
gasto um parágrafo especificando isso. A construção dele elimina o problema em vez
de resolvê-lo. Fica a dele.

### Juntar mais de um erro: espaço, e conserte a causa

Fui ver quando isso acontece de verdade. **Nos formulários de autenticação, quase
nunca:** login, cadastro, recuperação e redefinição têm `required` em todos os
campos (`index.html:32-100`), então o navegador barra o envio vazio e o erro
`missing` nem chega ao servidor.

Mas em dois formulários ele chega, e são justamente os que **não** têm `required`:

- adicionar pessoa — `nu-email`, `nu-senha` (`index.html:415-416`)
- trocar senha — `senha-atual`, `senha-nova` (`index.html:430-431`)

Ali dá para enviar vazio e receber dois `missing` de uma vez.

**Resposta: juntar com espaço simples**, mantendo o corte em 3. Mostrar só o
primeiro cria caça ao erro — corrige um, envia, aparece o próximo —, e com dois
campos a lista completa é curta.

**E a resposta melhor: pôr `required` nos quatro campos.** A melhor mensagem de
erro é a que não precisa aparecer. Com isso o caso de vários `missing` some quase
por completo, e o que sobra são erros de tipos diferentes, onde repetição não
existe e o espaço simples lê bem.

Não recomendo agrupar por tipo ("Falta preencher nome e empresa"). Leria melhor,
mas resolve um caso que o `required` já elimina — é código para um problema que a
gente acabou de tirar do caminho.

**Feito, e melhor do que eu propus.** O Alicate resolveu isto mais cedo no mesmo
dia: `required` nos cinco campos (achou o `nu-nome`, que eu não tinha listado, e
pôs `minlength="2"` nele para bater com o backend), e em vez de só o atributo,
envolveu os dois painéis em `<form>` de verdade com handler de `submit` — então
Enter-para-enviar passou a funcionar junto. A minha proposta era uma palavra em
quatro `<input>`; a dele conserta a validação e o teclado de uma vez.

Consequência que vale saber, e que **não pede trabalho**: com a validação nativa
nesses campos, as mensagens de `missing` e de texto curto do mapa do servidor
ficam praticamente inalcançáveis ali — o navegador barra antes. Em troca, o que o
recrutador vê nesses casos é a bolha nativa do navegador, que usa o texto e o
idioma **dele**, não os nossos: num navegador em inglês sai "Please fill out this
field." no mesmo formulário cujas mensagens de servidor estão em português.

Não recomendo consertar. Validação nativa é instantânea, fica ao lado do campo,
não custa viagem ao servidor e é mais acessível do que qualquer coisa que a gente
escrevesse por cima. Trocar isso por validação própria para casar o tom seria
piorar a experiência para ganhar consistência de texto numa mensagem que aparece
por meio segundo. Fica registrado como escolha consciente, não como ponta solta.

### "Tipo errado" e "desconhecido": genéricos, mas com uma emenda

Não vale caprichar em volume: são a rede de segurança, e o usuário normal não
chega lá. Mas as frases estão numa tela, então precisam pertencer à família.

Uma emenda de voz, e essa é da Pigmento: **"veio num formato que não reconhecemos"
usa uma primeira pessoa do plural que não existe em nenhum outro texto do
produto.** O "nós" aparece só aí. `"{Rotulo} veio num formato inesperado."` diz o
mesmo sem estrear uma voz.

E vale notar o que esses dois casos significam: se aparecerem, quem errou fomos
nós — JSON malformado é bug de cliente, não digitação do recrutador. Por isso
`"Não foi possível validar {rotulo}."` está certo como está: passivo, sem culpar
ninguém, e **sem instruir o usuário a consertar** algo que não está no alcance
dele. Aqui o rascunho do Chave é melhor que a minha proposta de rede de segurança
("não foi aceito. Confira o valor digitado"), que mandava conferir um valor que
pode não ter nada de errado.

### Uma nota de wording para a Pigmento arbitrar

`"{Rotulo} não aceita esse valor."` diz o que não serve, não o que serve. Onde a
lista é fechada e curta — decisão (entrevistar, reserva, arquivado, sem decisão) e
papel (admin, recrutador) —, `"{Rotulo} aceita: entrevistar, reserva, arquivado ou
sem decisão."` resolve o problema em vez de anunciá-lo. O `expected` vem no
contexto do erro do Pydantic, então o custo é baixo. Preferência minha, decisão
dela.


---

## Retido pela anonimização não é erro — spec de separação

Achado do item 12 rodando com dado real: 15 de 150 currículos escaneados (10%)
são retidos pela anonimização. Não é bug, é o princípio funcionando — o OCR lê,
mas não garante remoção segura da identificação, e o sistema recusa avaliar em
vez de arriscar vazar. Hoje esses 15 caem no mesmo grupo de tela que os arquivos
ilegíveis de verdade.

**Um dos 15 é qualificado no gabarito do piloto.** Não é hipótese.

### O erro de enquadramento, que é a raiz

"Não foi possível avaliar" diz duas mentiras sobre o caso retido.

A primeira: sugere que o **documento** falhou. Não falhou — ele é perfeitamente
legível por uma pessoa. Quem recusou fomos nós.

A segunda, pior: sugere que **não há o que fazer**. Há, e é a coisa mais simples
do produto: abrir o arquivo e ler. O dado está lá, inteiro, na mão do recrutador.

Os dois casos pedem ações opostas — *peça outro arquivo* contra *leia você
mesmo* — e hoje recebem a mesma frase. É por isso que alguém bom some sem
ninguém perceber.

### Os dois grupos

| Hoje | Passa a ser | O que significa | Ação do recrutador |
|---|---|---|---|
| Não foi possível avaliar | **Não foi possível ler** | o arquivo não deu texto utilizável | peça outro arquivo |
| Não foi possível avaliar | **Para você ler** | o texto existe; não enviamos para avaliação porque não dava para remover a identificação com segurança | abra o arquivo e leia |

"Para você ler" entra na família de rótulos de ação que o ranking já usa — "Para
chamar", "Descartar" — e não na família de estado. É deliberado: o grupo existe
para pedir uma ação, não para descrever uma condição.

**Ordem dos grupos:** "Para você ler" vem **antes** de "Não foi possível ler".
Entre os dois grupos sem nota, o que pode conter alguém bom vem primeiro.

### O contrato de dados (para o Alicate)

A distinção já existe no servidor: `_motivo_da_falha` (`storage.py:996`) decide
pelo `parse.get("retido")`. Ela só não sai de lá.

**`storage.ranking()` passa a devolver um booleano** — `retido` — junto do
`erro` que já devolve. `faixaDe()` no `app.js` usa o booleano.

**Nunca distinguir pelo texto do motivo.** Casar substring em `r.erro` funciona
hoje e quebra na primeira vez que a Pigmento reescrever a frase — e ela vai
reescrever, porque esse texto está no inventário de microcopy dela.

**As três coisas continuam tendo de concordar.** O comentário do `faixaDe`
(`app.js:953`) já avisa: faixa serve ao filtro, ao agrupamento e às contagens, e
se divergirem "o chip diz 8 e o grupo mostra 3". Partir a faixa `erro` em duas
obriga a conferir os três. Qualquer superfície que hoje conta "erro" — painel,
`contagens_das_vagas`, chips — precisa dizer **qual dos dois** está contando, ou
contar os dois separados. Somar os dois num número só reintroduz o problema com
outra roupa.

### Onde o número aparece antes de alguém rolar a tela

Grupo no fim da lista protege pouco: quem não rola não vê. O lugar barato e
eficaz é a **linha de métricas** do painel (`app.js:921`), que o recrutador lê
antes de qualquer coisa.

Entra uma métrica, no mesmo padrão condicional do "lidos por OCR" — só existe
quando o número é maior que zero:

```
{n}   para você ler
```

**Posição: logo depois de "na dúvida"**, antes de "currículos lidos". As três
primeiras são o que ainda pede atenção do recrutador; as últimas são volume.
Última posição leria como rodapé, que é o oposto do que este número precisa ser.

Isso é o item mais barato que existe para sustentar o critério de que alguém bom
não some sem o recrutador perceber — uma métrica condicional, sem tela nova.

### A linha do ranking precisa dizer o motivo

Hoje, na lista, um currículo sem nota mostra nome e um traço no lugar da nota. O
motivo só aparece depois de clicar (`app.js:1148`). Para os dois grupos novos
isso é caro: o recrutador vê um nome sem nota e sem explicação, e o custo de
descobrir é um clique por pessoa — quinze cliques, no piloto.

O motivo curto passa a sair no `cand-meta` da linha, que já existe, já é
`--tinta-fraca` 0.75rem e já corta com reticências a 380px. Sem componente novo,
sem coluna nova.

### Texto

Regras da Pigmento valendo, e uma a mais que é deste caso: **nada aqui pode
sugerir que o candidato é pior.** Ele não foi avaliado; não há nota, e portanto
não há juízo nenhum a insinuar.

- Cabeçalho do grupo: `Para você ler`
- Motivo na linha: `texto escaneado — a identificação não pôde ser removida com segurança`
- No detalhe, a frase com a ação: `O arquivo está aqui e é legível. Como não deu para remover a identificação com segurança do texto escaneado, ele não foi enviado para avaliação — a leitura deste é sua.`

Note o que a frase **não** diz: não fala em IA, modelo nem processamento, seguindo
a regra da Pigmento para texto sobre resultado de avaliação. E não pede desculpa:
a retenção é o produto funcionando, não uma falha a ser lamentada.

### Estados de borda

| Situação | O que acontece |
|---|---|
| Nenhum retido | grupo e métrica não aparecem — silêncio, não zero |
| Retido sem arquivo guardado (`tem_arquivo` falso) | "leia você mesmo" vira beco sem saída; o motivo tem de dizer que o arquivo não está mais aqui, e a ação passa a ser pedir outro |
| Retido e depois reenviado legível | sai do grupo sozinho, pela avaliação normal |
| Todos os 150 retidos | a lista fica sem nota nenhuma; o grupo e a métrica carregam a tela inteira, e é a leitura certa |

### O que não muda

**O documento de entrega ao cliente não vê nada disso.** `montar_shortlist`
recebe as linhas já filtradas, e quem não tem avaliação nunca entra. Um candidato
retido não aparece — nem como nome, nem como lacuna, nem como aviso de que
existiu. Isso está certo: o cliente contratou uma recomendação, e a nossa decisão
interna de não processar um arquivo não é assunto dele.


---

## Currículo que não é currículo — as três linhas do ATS

Achado do item 12: três linhas exportadas de planilha de ATS com **nome, e-mail,
telefone e cidade e mais nada** — sem formação, sem experiência. Foram avaliadas,
receberam zero e confiança baixa, e caíram em "Descartar", indistinguíveis de
alguém que foi avaliado e não serviu.

### Por que isto é pior que os 15 retidos

No caso retido o sistema **se recusou** a avaliar e disse isso. Aqui ele avaliou,
produziu uma nota que parece legítima e emitiu uma **recomendação sobre uma
pessoa** — tudo a partir de um arquivo que não continha currículo nenhum.

"Descartar" é, além disso, o grupo que o recrutador menos revisita. É onde um
falso negativo tem a vida mais longa.

### A raiz, e ela já apareceu duas vezes antes

`calcular_score` (`pontuacao.py:53`) soma só os critérios presentes em
`resultado.criterios`; **o que não foi respondido conta como zero**. Para um
arquivo sem currículo, nenhum critério é respondido, e a soma de nada dá 0 — um
zero que parece uma nota e não é.

É a terceira aparição do mesmo defeito:

1. na spec do diagnóstico comparativo, onde a frase diria "perde 12 em Active
   Directory" para um critério que ninguém respondeu;
2. nos 15 retidos, onde ausência de avaliação virava "não foi possível avaliar";
3. aqui, onde ausência de currículo virou nota zero e recomendação de descarte.

**Ausência de dado está sendo renderizada como resultado.** Consertar por tela,
uma de cada vez, é enxugar gelo.

### O conserto de raiz: sem critério respondido, não há nota

**Se `criterios_faltantes` cobre todos os critérios da rubrica, `score_final` é
nulo — não zero.** Não é ajuste de tela: enquanto o 0 existir no dado, ele vaza
para o CSV, para o relatório e para a decomposição do diagnóstico comparativo,
onde ancoraria uma comparação inteira num número que não significa nada.

Hoje essas três linhas saem na planilha como `0` e `descartar`. Quem abrir o CSV
lê três pessoas reprovadas com nota zero.

Com `score_final` nulo, elas caem no caminho que a tela já tem para quem não tem
nota — o mesmo traço no lugar do número que os outros grupos sem nota usam.

### O grupo, e a regra que impede a cauda de virar taxonomia

A tentação é criar um grupo por motivo. Não: **um grupo existe só se a ação do
recrutador for diferente.** Pelo teste:

| Motivo | Ação do recrutador | Grupo |
|---|---|---|
| retido pela anonimização | abrir o arquivo e ler — o dado está lá | **Para você ler** |
| arquivo ilegível | conseguir o currículo desta pessoa | **Peça o currículo** |
| texto insuficiente (linha de ATS) | conseguir o currículo desta pessoa | **Peça o currículo** |

**O nome mudou de "Peça outro arquivo" para "Peça o currículo", e a mudança
importa.** Quando o terceiro estado apareceu — extração funcionou, texto saiu, e
o texto era uma linha de planilha com contato —, ficou claro que o rótulo antigo
mentia para ele: o arquivo pode estar perfeito, quem veio pela metade foi a
exportação do ATS. "Peça o currículo" é verdade nos dois casos e não afirma nada
sobre o arquivo.

Foi o mesmo erro do "Não foi possível avaliar", em escala menor: **o agrupamento
estava certo e o rótulo é que era falso para um dos membros.** A regra que
decide o grupo continua sendo a ação; a regra que decide o nome é que ele
precisa ser verdadeiro para todos os membros, não só para o caso que motivou o
grupo.

Os dois últimos pedem a mesma coisa. Viram um grupo só; o que muda entre eles é
o **motivo na linha**, não o cabeçalho. Assim a cauda fica em dois grupos, não em
três, e a regra dá um teste para a próxima vez que alguém quiser um quarto.

("Peça outro arquivo" é imperativo dirigido ao recrutador, o que destoa um pouco
de "Descartar". Se a Pigmento preferir manter o registro dos outros rótulos,
"Sem currículo utilizável" serve — mas perde a ação, que é o que faz o grupo
existir.)

### Motivo na linha

No `cand-meta`, como no caso retido:

- ilegível: `não foi possível extrair texto deste arquivo`
- contato sem currículo: `só nome e contato — sem formação nem experiência no arquivo`

O segundo descreve **o arquivo**, nunca a pessoa. "Currículo vazio" ou
"incompleto" seria juízo sobre o candidato a partir de uma falha de exportação do
ATS de quem enviou.

### O que o sistema já sabe e não mostra

Nada aqui precisa de detecção nova. `criterios_faltantes` (`pontuacao.py:69`) já
existe e já é usado no caminho MCP (`mcp_servidor.py:539`); ele só não é
persistido nem devolvido pelo `ranking()`. É o mesmo formato do `retido`: o
servidor sabe, a tela não recebe.

**Correção, depois do item 12 rodar com julgamento humano.** O detector que eu
tinha proposto — `criterios_faltantes` cobrindo todos os critérios — **não
dispara no dado real**. O avaliador não deixou critérios sem resposta: respondeu
todos **com zero** e confiança baixa. Então `criterios_faltantes` volta vazio,
`score_final` é 0 legitimamente calculado, e a minha regra ficaria dormindo
exatamente no caso que ela existia para pegar.

O sinal certo está mais acima, e é estrutural: **o perfil extraído está vazio.**
`PerfilAnonimo` (`models.py:111`) tem `experiencias`, `formacoes`, `habilidades`,
`idiomas` e `certificacoes`; numa linha de ATS com só contato, as cinco listas
voltam vazias e `anos_experiencia_total` é 0. Não havia o que avaliar — e isso é
verdade independentemente de como o avaliador escolheu pontuar.

A distinção que importa: um candidato genuinamente fraco tem **evidência de
ausência** — "não menciona experiência com AD" é uma frase que só se escreve
depois de ler um currículo. O caso do ATS não tem currículo para ler. O zero
parece igual nos dois; a origem não é.

**Contrato:** `ranking()` devolve um booleano de perfil vazio, calculado no
servidor a partir do perfil extraído. Nunca inferir de `score_final == 0` — zero
é nota legítima para quem foi avaliado e não pontuou em nada —, nunca do texto do
motivo, e **nunca de `confianca == "baixa"` sozinha**, que também é verdade para
OCR ruim e misturaria dois casos que pedem ações diferentes.

**As duas condições coexistem e não se substituem:**

- perfil vazio → não havia currículo. É o caso das três linhas do ATS.
- `criterios_faltantes` cobrindo tudo → havia currículo e a avaliação não
  respondeu. É o caveat que já está na spec do diagnóstico comparativo.

As duas suprimem a nota, por motivos diferentes. Eu tinha escrito só a segunda.

### O buraco que fica aberto, e que eu não estou fechando aqui

Existe "texto vazio" (`sem_texto`, `TRIM(texto) = ''`) e existe "tem texto". Não
existe **"tem texto, mas não é um currículo"**. O `MIN_CHARS_TEXTO_UTIL` de 220
caracteres (`config.py:65`) parece cobrir isso, mas não cobre: ele só é usado no
caminho de PDF, para decidir se o arquivo vai para a fila de OCR
(`extraction.py:279`). Um `.docx` ou `.txt` com 60 caracteres de contato passa
direto para avaliação.

Um piso de texto útil na entrada pegaria essas três linhas **antes** de gastar
avaliação nelas, e o recrutador saberia no envio em vez de no ranking. Não estou
propondo agora — mexe no funil de entrada e é decisão da Bussola —, mas é onde o
problema deixa de existir em vez de ser exibido melhor.
