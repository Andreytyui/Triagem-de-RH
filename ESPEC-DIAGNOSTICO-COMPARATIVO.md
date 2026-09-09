# Diagnóstico comparativo entre vizinhos — spec de interface

Item 3 do backlog-priorizado. Pedido da Bussola: comparação entre vizinhos no
ranking, calculada em Python, sem julgamento novo de modelo.

Spec para a Bussola validar e o Alicate implementar.

---

## Antes de desenhar: em qual tela isso mora

`ver_ranking` e `ver_candidato` são ferramentas MCP (`app/mcp_servidor.py:599` e
`:648`). Elas devolvem **texto**, que o conector renderiza na conversa do
recrutador — não têm 380px nem coluna de 0.5rem. O aperto de espaço lá é outro: é
atenção numa conversa, onde o custo de uma linha a mais é o recrutador parar de
ler.

Mas o produto tem **duas** superfícies com ranking e detalhe: as ferramentas MCP e
a interface web (`.ranking` e `.detalhe`). Conteúdo novo que faz sentido numa não
faz automaticamente sentido na outra, e o orçamento de espaço é diferente nas
duas. Esta spec cobre as duas, e a resposta é diferente em cada uma.

## A aritmética, porque é ela que torna isso honesto

`pontuacao.py:53` calcula a nota final assim:

```
score_final = round( Σ(nota_c × peso_c) × 10 / Σpeso , 1 )
```

Com os pesos somando 100, a contribuição de cada critério é `nota_c × peso_c / 10`
**em pontos da nota final** — e o teto de cada critério é exatamente o peso dele.
Logo, a diferença entre dois candidatos decompõe-se sem sobra:

```
score_A − score_B = Σ ( (nota_A,c − nota_B,c) × peso_c / 10 )
```

Isso não é heurística, é identidade algébrica. É o que permite a frase existir sem
modelo nenhum, e é também o que a torna verificável: os números que a gente mostra
**somam a diferença que o recrutador já vê na tela**. Se não somarem, está errado.

**Regra de unidade, e é a armadilha da implementação:** todo número exibido é em
pontos da nota final (0-100), nunca em pontos de nota por critério (0-10). Mostrar
`−3` quando a contribuição é `−12` faz a conta não fechar, e a frase perde a única
coisa que a sustenta.

### Os dois casos em que a aritmética mente, e o que fazer

**1. Critério não respondido conta como zero.** `calcular_score` soma só os
critérios presentes em `resultado.criterios`; o que faltou vira zero, e a lacuna
aparece em `criterios_faltantes()`. Então a decomposição pode dizer "perde 12 em
Active Directory" quando a verdade é "Active Directory não foi respondido para
ele". São coisas diferentes: uma é o candidato, a outra é a nossa extração.

Quando o critério que mais pesa na diferença está em `criterios_faltantes` de um
dos dois lados, a frase **tem de dizer isso**, não escondê-lo atrás do número:

> Active Directory não foi respondido no currículo dele e conta como zero — parte
> dessa diferença é lacuna nossa, não dele.

**2. Confiança baixa e OCR.** Comparar uma nota de texto limpo com uma nota que
veio de OCR de confiança baixa dá precisão falsa: a diferença de 7 pode ser ruído
de extração. Quando qualquer um dos dois lados tem `confianca == "baixa"` ou
`origem_texto == "ocr"`, a comparação sai com a ressalva junto, na mesma frase.

---

## `ver_ranking` — uma linha, e só quando ela se paga

Hoje cada candidato ocupa duas linhas:

```
2. candidato mcpcand0002 — 81/100 [chamar]
   <resumo, cortado em 150 caracteres>
```

A comparação entra como **uma terceira linha, curta**, referenciando o vizinho de
cima — nunca id, nunca nome:

```
2. candidato mcpcand0002 — 81/100 [chamar]
   Sete anos em suporte, com passagem por AD e gestão de SLA.
   7 abaixo do anterior — Active Directory (−12), SLA (+5)
```

`−12` e `+5` somam `−7`, que é exatamente a diferença de nota. O recrutador confere
a conta de olho, sem precisar confiar em nós.

A forma da referência — "o anterior" ou a qualificada, quando o filtro escondeu o
vizinho — está na seção **Numeração**.

### A regra que decide quando a linha aparece

**Ela só aparece onde o ranking é frágil.** Duas condições, as duas necessárias:

1. posição ≤ `COMPARACAO_TOPO` — abaixo disso ninguém está comparando, está
   descartando;
2. diferença para o vizinho de cima ≤ `COMPARACAO_LIMIAR` pontos.

Os dois são configuração, não constante — ver "Decidido pela Bussola" no fim.

Fora disso a linha não sai. Se o primeiro tem 88 e o segundo tem 61, dizer
"27 abaixo" é
ruído: eles não estão em disputa, e a distância já está nas duas notas.

Essa regra faz duas coisas de uma vez. Contém o custo de espaço — num ranking bem
espalhado quase nenhuma linha ganha a terceira linha, e no pior caso são 10 linhas
a mais, não 30. E, mais importante, **ela aparece exatamente onde a ordenação não é
decisiva**, o que empurra o recrutador a olhar com atenção em vez de aceitar a
ordem como veredito. Uma nota de 0 a 100 sugere uma precisão que ela não tem; a
linha comparativa é onde a gente admite isso.

### Composição da frase

- Vizinho referenciado sem id e sem nome; a forma está na seção **Numeração**.
- Até **dois** critérios, os de maior `|delta|`.
- Critério com `|delta| < 1.0` ponto não é nomeado — é ruído de arredondamento.
- Se os nomeados não cobrem toda a diferença, entra o resto: `outros (−2)`. A conta
  precisa fechar, sempre.
- Nome do critério é `Criterio.nome` (`models.py:23`), não o `id` — o `id` é slug e
  o recrutador nunca o viu.
- Empate (diferença 0.0): `empatado com o anterior — SLA (+9), Active Directory (−9)`. É
  o caso mais informativo dos três: mesma nota, caminhos diferentes.

## `ver_candidato` — os dois lados, e as ressalvas

Aqui o recrutador pediu por esta pessoa, e há espaço para dizer mais. Entra depois
das notas por critério e antes da decisão:

```
Vizinhança no ranking geral (este candidato é o nº 2)
  nº 1, 88/100 — 7 à frente: Active Directory (+12), SLA (−5)
  nº 3, 74/100 — 7 atrás:    SLA (+9), Suporte N3 (−2)

Os números são pontos da nota final e somam exatamente a diferença: é a mesma nota
por critério, pesada pela rubrica. Nenhum julgamento novo entrou aqui.
```

Mesmas regras de composição do `ver_ranking`, com três diferenças:

1. **Os dois vizinhos**, o de cima e o de baixo, quando existem.
2. **Sem o filtro de fragilidade.** Quem abriu o detalhe quer o detalhe; a
   diferença grande também informa — "está 27 atrás do topo" é resposta.
3. **As ressalvas entram aqui por extenso** — critério não respondido, OCR,
   confiança baixa. No `ver_ranking` não cabe; aqui cabe, e é obrigatório.

**Regra de privacidade, não negociável:** o vizinho é sempre posição ou referência
relativa, nunca nome nem `candidato_id` — inclusive quando a chamada vem com `incluir_contato=True`. O
contato pedido é de **um** candidato; a comparação não pode ser a porta lateral que
entrega a identidade de outro.

## Interface web — onde entra e onde não entra

**No `.ranking`: não entra.** A grade é `3rem minmax(0, 1fr) 0.5rem` e a linha
existe para varrer 10 a 40 nomes de relance. Uma frase comparativa por linha
destrói exatamente a densidade pela qual essa tela existe, e a 380px ela quebraria
em duas ou três linhas. O ranking é para achar quem olhar; comparar é o passo
seguinte.

**No `.detalhe`: entra**, como bloco próprio depois do diagnóstico por critério e
antes de `.decisao`. É o ritmo de leitura, tem 2rem de respiro, e é onde o
recrutador já está lendo um candidato por vez.

Forma: mesma estrutura do `ver_candidato`, números em `tabular-nums` e nome do
critério em peso 500. **A serif não entra aqui** — regra da Pigmento: ela é para
nota e citação, e isto não é nem um nem outro. Sem cor semântica no sinal: `+` e
`−` já dizem a direção, e verde/vermelho aqui viraria o semáforo de
aprovado/reprovado que a paleta proíbe.

A 380px o bloco vira uma linha por vizinho, com quebra natural; sem coluna nova,
sem largura fixa.

## O documento de entrega ao cliente — entra, com duas amarras

Decidido pela Bussola, sem precisar escalar: a comparação **entra** no documento
de entrega. A minha objeção original estava mal colocada e eu a retirei — escrevi
que o documento "não diz que um candidato é melhor que o outro", e ele diz: é uma
lista ordenada, com nota, dos recomendados. A comparação já está lá, na ordem. O
que a decomposição acrescenta não é a comparação, é o **motivo** dela.

E o motivo, sendo decomposição de critérios acordados, é o argumento mais forte a
favor da ordem: mostra que ela saiu da rubrica que o cliente aprovou, e não de
gosto. Numa alegação de discriminação, "ficou à frente por +12 em Active
Directory, que vale 35% dos critérios que combinamos" defende melhor que uma
ordem sem explicação nenhuma.

O que precisa ser proibido não é comparar. É o seguinte:

### Amarra 1 — linguagem

Só delta de critério. Nenhuma palavra avaliativa sobre a pessoa: "mais forte",
"melhor", "mais preparado" não entram, em lugar nenhum do documento.

```
Diferença para o anterior da lista: Active Directory (+12), SLA (−5)
```

### Amarra 2 — a base do cálculo é o shortlist, não o ranking

`montar_shortlist` recebe as linhas **já filtradas** (`shortlist.py:258`): só quem
entra no documento. O vizinho de um candidato no **ranking completo** pode ser
alguém que **não está** no shortlist — foi descartado, e por regra de produto o
documento não menciona descartado nenhum.

Referenciar "#4" quando o #4 foi cortado vaza a existência dos excluídos para
dentro do documento do cliente, que é o oposto do que a regra protege.

Então: o "anterior" é o anterior **daquela lista**, e as posições são as da lista.
É a mesma aritmética sobre outro conjunto — mas não é o mesmo código.

### O CSV fica de fora

Mesmo com a decisão de incluir no documento, o CSV não recebe a comparação. Ele é
exportação bruta, sem a moldura de critérios acordados — e é justamente essa
moldura que torna a frase defensável. Sem ela, sobra a comparação nua.

## Numeração — a posição continua local, e a frase se vira sozinha

**Decisão do dono do produto, e ela reverte o que eu tinha fechado antes.** A
"Posição" mantém o significado local e sequencial de sempre em **todo** lugar que
já a exibe hoje: `ver_ranking`, `ver_candidato`, `.detalhe`, relatório interno e a
coluna do CSV. A renumeração global com buracos foi cancelada.

Ganha em duas frentes que a minha proposta perdia: zero mudança de comportamento
existente, e o risco de compatibilidade do CSV desaparece junto — quem montou
planilha em cima da coluna "Posição" continua com o arquivo de pé.

A necessidade real da feature — referenciar o vizinho certo mesmo com a visão
filtrada — resolve-se **dentro da frase do diagnóstico**, sem competir com o
rótulo de posição impresso ao lado.

### A regra de referência

**Se o vizinho do ranking geral é a linha imediatamente acima na saída atual, a
referência é relativa:**

```
2. candidato mcpcand0002 — 81/100 [chamar]
   Sete anos em suporte, com passagem por AD e gestão de SLA.
   7 abaixo do anterior — Active Directory (−12), SLA (+5)
```

Sem número, sem colisão, e mais curto. Cobre o `ver_ranking` sem filtro inteiro,
onde o vizinho no ranking geral é sempre a linha de cima.

**Se o filtro escondeu o vizinho, aí sim a forma qualificada:**

```
7 abaixo de quem está logo acima no ranking geral, fora deste filtro
  — Active Directory (−12), SLA (+5)
```

Ela paga duas contas de uma vez: diz com quem a comparação foi feita, e diz que
**este filtro está escondendo alguém relevante** — que era exatamente a informação
que os buracos da numeração global iam carregar, agora entregue em texto e sem
mexer em numeração nenhuma.

### Por que a colisão só existia no `ver_ranking`

Era o único lugar com um rótulo de posição impresso ao lado da frase. Sem a regra
acima, a linha rotulada `2.` diria "abaixo do número 3 do ranking geral" sobre uma
pessoa impressa quatro linhas acima como `1.` — a qualificação evita o erro de
leitura, mas obriga o recrutador a segurar uma tabela de tradução para alguém que
está bem na frente dele.

O `ver_candidato` não mostra lista, então não há rótulo local competindo. O
`.detalhe` da web também não: o `.ranking` ao lado mostra nota, nome, meta e marca
de decisão, **não mostra posição**. Nesses dois a referência numerada é a única
forma possível, e o quadro se estabelece uma vez no cabeçalho do bloco:

```
Vizinhança no ranking geral (este candidato é o nº 2)
  nº 1, 88/100 — 7 à frente: Active Directory (+12), SLA (−5)
  nº 3, 74/100 — 7 atrás:    SLA (+9), Suporte N3 (−2)
```

Assim "ranking geral" é dito uma vez e os números dentro do bloco não precisam
repetir a qualificação.

### O que não muda

**A comparação é sempre contra o vizinho do ranking geral**, nunca contra o
vizinho da lista filtrada. Comparar dentro do recorte daria um gap maior e faria a
regra de fragilidade disparar errado.

**Quem não tem nota continua fora da comparação.** A regra "posição é lugar por
nota" caiu como mudança de numeração, mas continua valendo para a escolha do
vizinho: eliminado, erro e ainda-avaliando são pulados, e o vizinho de comparação
é o candidato pontuado mais próximo. A numeração exibida segue como sempre foi.

**"Ranking geral" é vocabulário novo** e por isso aparece pouco: só no caso
filtrado do `ver_ranking` e uma vez no cabeçalho do bloco de detalhe. Se aparecesse
em toda linha, seria jargão nosso vazando para a tela do recrutador.

### O relatório interno não recebe a comparação

Ninguém pediu. O pedido cobria as ferramentas MCP, a tela e o documento de entrega;
o relatório não estava nele. Fica de fora até que alguém peça — é decisão, não
esquecimento.

## Estados

| Situação | O que aparece |
|---|---|
| Primeiro colocado | só o lado "atrás": o vizinho de baixo |
| Último colocado | só o lado "à frente" |
| Vaga com um candidato só | nada, sem mensagem de erro — não há vizinhança |
| Vizinho sem nota (erro, sem texto, ainda avaliando) | pula aquele lado; se os dois, nada |
| Candidato cortado no eliminatório | nada. Ele não tem nota por critério, e comparar quem foi cortado com quem foi pontuado é comparar coisas diferentes |
| Diferença acima de `COMPARACAO_LIMIAR` (15), no `ver_ranking` | nada, deliberadamente. A ausência é a informação: não estão em disputa |
| Todos os deltas < 1.0 | `praticamente idênticos nos critérios` — sem lista de números |

## Decidido pela Bussola

**1. O limiar não é constante, é configuração.** Ela não tem dado por trás dos 10
pontos e nem eu — palpite contra palpite não vira número travado no código. Entra
como ajuste, no padrão do `config.py` (`_int` lendo variável de ambiente):

```python
COMPARACAO_LIMIAR = _int("COMPARACAO_LIMIAR", 15)   # diferença máxima, em pontos
COMPARACAO_TOPO   = _int("COMPARACAO_TOPO", 10)     # até que posição a linha sai
```

**O padrão de 15 não é palpite — veio de dado da Bussola.** A confiabilidade entre
avaliadores de uma mesma rubrica tem desvio-padrão de 11 a 17 pontos. Isso derrubou
o meu 10 original: um limiar abaixo do piso de ruído faria a linha **não** aparecer
para uma diferença de 13 pontos, e a ausência da linha afirma "não estão em disputa"
— justamente onde a ordem não é confiável. O limiar existe para marcar onde a
ordenação é frágil; se a medida da fragilidade é 11-17, ele tem de cobrir a faixa em
vez de parar antes dela.

15 fica dentro da banda e perto do topo, do lado que erra mostrando a linha em vez
de escondendo: mostrar a mais custa três linhas de texto, esconder custa uma decisão
tomada com falsa segurança.

`COMPARACAO_TOPO` continua em 10 — "até que posição alguém ainda está comparando" é
outra pergunta, e o dado de confiabilidade não a responde.

O teste ponta a ponta com a vaga piloto real (item 12) é onde os dois números viram
dado de campo. Se o recrutador achar que 15 está errado para a escala dele, muda a
variável, não o código.

**2. `ver_ranking` ganha a linha**, com a regra de fragilidade. Ela comprou o
argumento pelo motivo certo — é onde a ordenação não é decisiva que o recrutador
precisa olhar com atenção — e tratou o "aparece pouco" como bônus, não como razão.

**3. A ressalva de critério não respondido: aprovada sem ressalva.** A leitura dela
é melhor que o meu aviso: isso não aumenta a percepção de erro, é a mesma
honestidade que o produto já pratica em "Sem evidência no currículo". Esconder a
lacuna atrás de um zero seria pior que qualquer desconforto de mostrá-la.

## Estado da spec

Fechada e implementável inteira: `ver_ranking`, `ver_candidato`, tela web e
documento de entrega. Nada pendente de decisão.
