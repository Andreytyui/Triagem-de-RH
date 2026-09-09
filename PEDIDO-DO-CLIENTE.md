# O que eu preciso

Pedido de um recrutador para quem vai construir a ferramenta.
Escrito em janeiro de 2026.

---

## Quem eu sou e onde dói

Trabalho sozinho. Atendo três ou quatro empresas por mês, quase sempre vagas
operacionais e de tecnologia, e cobro por vaga fechada.

Meu problema não é achar candidato. É que **chegam 150 e eu preciso olhar todos**.
Um anúncio de analista de suporte no LinkedIn traz 120 inscritos em três dias, e
mais 30 me chegam por indicação e WhatsApp. Eu passo dois dias abrindo PDF, e no
segundo dia eu já não estou lendo do mesmo jeito que no primeiro — o candidato
número 90 recebe menos atenção que o número 6, e isso não é justo com ele nem
comigo.

O segundo problema é o que vem depois. Quando eu levo cinco nomes para o cliente,
ele pergunta "por que esses?". Hoje eu respondo de cabeça, ou com uma anotação
solta no meu caderno. **Isso é o que eu vendo, e é a parte que eu faço pior.**

Já testei duas ferramentas que prometiam resolver. As duas me devolveram uma nota
de 0 a 100 por candidato e nenhuma explicação. Quando o cliente perguntou por que
o candidato tinha 82, eu não soube responder. Não uso mais nenhuma das duas.

---

## A vaga que eu quero usar como teste

**Analista de Suporte Técnico Pleno**, para uma empresa de médio porte aqui na
região. É uma vaga que eu preencho duas ou três vezes por ano, então serve bem de
piloto.

O que a pessoa vai fazer:

- Atender chamados de nível 2 com prazo contratual de 4 horas para prioridade
  alta, num volume de 40 a 60 chamados por semana
- Administrar Active Directory: criar conta, mexer em GPO, dar e tirar permissão
  de pasta
- Dar suporte a Windows Server, Microsoft 365 e acesso remoto por VPN
- Documentar procedimento e reduzir chamado repetido
- Escalar para o time de infraestrutura quando sair do escopo dele

Obrigatório: superior completo em área de tecnologia, experiência comprovada com
Active Directory e Windows Server, e ter trabalhado com prazo de atendimento
acordado.

Desejável: inglês para ler documentação, certificação ITIL, noção de PowerShell.

Híbrido, três dias presenciais.

---

## O que eu quero que a ferramenta faça

### 1. Me deixar mandar nos critérios

Não quero que a máquina decida sozinha o que importa. Quero dizer:
*experiência em suporte N2 vale 35, Active Directory vale 30, redes vale 20,
inglês vale 15*. E quero poder mudar isso depois e ver o resultado mudar junto.

Se a ferramenta me propuser os critérios primeiro, ótimo — economiza meu tempo.
Mas **eu preciso poder editar antes de qualquer coisa ser avaliada**. Se eu não
puder mexer, é a mesma caixa-preta das outras duas que eu abandonei.

### 2. Ler os arquivos como eles chegam

Não vou converter nada. Chega PDF, chega Word, chega o `.doc` velho de gente que
usa Office 2010, chega planilha exportada do sistema da empresa cliente com 40
linhas. Uma parte vem escaneada, que é currículo impresso e digitalizado — e essa
parte não é pequena, é uns 10%.

Se a ferramenta recusar metade dos arquivos, eu vou ter mais trabalho, não menos.

### 3. O pódio: até 10 nomes, em ordem

É isso que eu quero ver quando abrir a tela. Não a lista de 150. **Os melhores,
ranqueados, no máximo 10.**

Por que 10 e não 5: porque o cliente quase sempre quer ver mais que a minha
primeira escolha, e porque do 6º ao 10º costuma sair alguém que sobe quando eu
falo com todo mundo. Por que no máximo 10: porque acima disso não é seleção, é
lista, e lista eu já tenho.

Quero cada posição com:

- **Colocação e nota.** Primeiro, segundo, terceiro. Com número, para eu comparar
  de relance quem está perto de quem. Se o primeiro tem 87 e o segundo 86, isso é
  um empate e eu preciso enxergar que é.
- **O nome e como falar com a pessoa.**
- **Duas linhas** dizendo quem é, para eu lembrar sem reabrir o currículo.

E abaixo do pódio, o resto: quem ficou na dúvida, quem não serve, e quem foi
cortado logo de cara por não ter o obrigatório. Não quero que sumam — às vezes a
vaga muda e eu preciso voltar.

### 4. O diagnóstico — a parte que eu mais preciso

Para cada nome do pódio, eu quero saber **por que ele está ali**. E "por que" para
mim não é uma nota, é uma frase que eu possa repetir na frente do cliente sem
gaguejar.

Concretamente, para cada critério que eu defini:

- A nota que ele tirou naquele critério
- **O trecho do currículo que justifica aquela nota** — copiado do documento, não
  um resumo, não uma interpretação

Se o candidato tirou 9 em "experiência em suporte N2", quero ver escrito:
*"Atendimento de chamados críticos com SLA de 4 horas; média de 55 por semana"*.
Aí eu sei que a nota é real, e o cliente também sabe.

E se não houver nada no currículo sobre aquele critério, **quero que a ferramenta
diga isso com todas as letras**, não que invente. "Sem evidência no currículo" é
uma resposta perfeitamente útil para mim — significa que ou a pessoa não tem, ou
ela escreveu mal o currículo, e nos dois casos eu vou perguntar na entrevista.

Além disso, por candidato:

- **O que pesa a favor**, em fatos, não em adjetivo. "Reduziu o tempo médio de
  resolução de 9h para 2h40" me serve. "Profissional dedicado" não me serve para
  nada.
- **O que me preocupa.** Lacuna longa sem explicação, três empregos em dois anos,
  cargo que não bate com o tempo de carreira. Mas **não** me venha dizer que o
  currículo é feio, que a empresa é desconhecida ou que a faculdade não é famosa.
  Isso não é sinal de nada e eu não vou descartar ninguém por isso.
- **Um aviso quando a ferramenta não tiver certeza.** Se o currículo é curto e
  genérico demais para uma avaliação séria, prefiro que ela me diga isso a que
  chute uma nota. Eu olho com meus olhos e decido.

### 5. Uma página para eu entregar ao cliente

Depois que eu escolher — e quem escolhe sou eu — quero gerar um documento com os
três ou cinco que eu selecionei, com os critérios da vaga e a justificativa de
cada nota, para mandar por e-mail ou imprimir.

Esse documento **não pode ter** os descartados, nem o total de inscritos, nem
qualquer menção a inteligência artificial, robô ou processamento. O trabalho que
eu apresento é meu. A ferramenta é minha ferramenta, não é o assunto da reunião.

---

## O que eu não quero

**Que ela descarte alguém sozinha.** A ferramenta ordena e explica; quem elimina
sou eu. Se ela mandar embora um candidato bom e eu descobrir depois, o problema é
meu, com o meu cliente. Além disso me disseram que a lei brasileira dá ao
candidato o direito de pedir revisão de decisão automatizada — não quero ficar
sem resposta se isso acontecer.

**Que ela olhe nome, idade, foto, endereço ou estado civil na hora de pontuar.**
Não é só questão de justiça, é questão de risco: se um candidato alegar
discriminação, eu preciso poder dizer que quem deu a nota não sabia essas coisas.
Eu vou ver o nome depois, quando for ligar.

**Que eu precise de conta em serviço de inteligência artificial.** Eu já pago o
Claude. Se der para a ferramenta usar a minha assinatura em vez de me obrigar a
abrir mais uma conta com cobrança por uso, é isso que eu quero. Não quero
gerenciar duas faturas nem descobrir no fim do mês que gastei mais do que
imaginava.

**Que fique na nuvem de outra pessoa.** Currículo tem CPF, telefone, endereço.
Prefiro que rode no meu computador. Se um dia precisar sair dali, aí conversamos.

**Coisa demais.** Não quero integração com dez sistemas, não quero relatório
gerencial, não quero dashboard. Quero triar, entender e apresentar.

---

## Como eu vou saber que funcionou

Vou pegar a vaga de suporte, jogar os 150 currículos dentro e conferir:

1. **Os cinco primeiros do pódio fazem sentido para mim?** Se eu li os currículos
   antes e a ferramenta colocou lá em cima gente que eu não colocaria, ela não
   entendeu o que eu pedi — ou eu escrevi mal os critérios, e aí quero poder
   corrigir e rodar de novo sem pagar tudo outra vez.

2. **Eu consigo defender cada um dos cinco?** Vou pegar o diagnóstico do terceiro
   colocado e tentar explicar em voz alta por que ele está ali. Se a evidência
   citada estiver mesmo no currículo dele, passou.

3. **Alguém bom ficou de fora?** Vou olhar a lista dos descartados procurando
   erro. Se achar um nome que eu chamaria e a ferramenta descartou, quero
   entender por quê — e se o motivo for burro, quero poder mudar o critério.

4. **Levou menos que meio dia?** Hoje leva dois. Se levar mais que uma manhã,
   incluindo o tempo de eu revisar tudo, não resolveu meu problema.

5. **O documento de entrega está apresentável?** Vou mandar para uma cliente de
   confiança e perguntar o que ela achou. Se ela perguntar "isso foi feito por
   robô?", está errado.

---

## Prazo, dinheiro e o resto

Preciso disso funcionando para a próxima vaga que abre, o que me dá umas seis
semanas.

Sobre custo: pago pela ferramenta, não por currículo lido. Se cada triagem tiver
um custo variável, quero saber quanto é **antes** de rodar, e quero um teto que
eu configure — se passar, para e me avisa.

Sobre os dados: os currículos ficam guardados por quanto tempo? Preciso poder
responder isso se um candidato perguntar, e preciso poder apagar os dados de
alguém que peça. Isso não é preciosismo meu, é a lei, e a multa é minha, não sua.

---

## Uma coisa que eu quero deixar clara

Se a ferramenta acertar 100% e eu não conseguir explicar as escolhas, ela não me
serve. Se ela acertar 80% e cada escolha vier com o trecho do currículo que a
sustenta, ela me serve muito.

**O que eu estou comprando não é a decisão. É o argumento.**
