# Manual de uso

Para quem vai usar o sistema no dia a dia. Não precisa saber programar.

---

## O que este sistema é

Você descreve a vaga. Ele propõe os critérios de avaliação. **Você corrige os critérios.**
Aí você joga os currículos dentro e ele devolve um ranking — com, para cada nota, o trecho do
currículo que justifica aquela nota.

O que ele **não** é: ele não contrata, não descarta ninguém sozinho e não substitui a
entrevista. Ele lê 150 currículos em minutos e te entrega uma lista ordenada e defensável.

---

## Primeiro acesso

1. Abra o endereço do sistema e clique em **Criar conta**.
2. Preencha empresa, seu nome, e-mail e uma senha de pelo menos 10 caracteres.
   Prefira uma frase — *"cafe com pao na chuva"* é melhor que *"S3nh@2024"*, e mais fácil de
   lembrar.
3. Ligue o Claude: clique em **Conectar** na faixa do topo, ou vá em
   **Configurações → Conector do Claude**.

### Como a avaliação acontece

Quem lê e pontua os currículos é o **Claude do seu próprio plano**. Não existe chave
de API para comprar, não existe cobrança por currículo, e nada é enviado para a conta
de ninguém além da sua.

Para ligar, você precisa do **Claude Desktop** instalado. Na pasta da Triagem, clique
com o botão direito em **conectar-claude.ps1** → *Executar com o PowerShell*. Ele pede
seu e-mail e sua senha daqui e configura tudo sozinho. Feche e abra o Claude Desktop.

Depois disso o fluxo é: você prepara a vaga e envia os currículos nesta tela, e pede
ao Claude para avaliar. A própria tela te mostra a frase pronta para copiar.

### E se eu esquecer minha senha?

Na tela de entrada, **Esqueci minha senha**. Você recebe um link por e-mail, que
vale por 30 minutos e serve uma vez só.

Se a Triagem estiver instalada no seu próprio computador, o caminho é outro: na
pasta do sistema, rode `python -m app.senha seu-email@empresa.com`. Ele pede a
senha nova ali mesmo.

Nos dois casos, trocar a senha desconecta as sessões abertas e desliga o Claude —
é proposital. Depois de trocar, rode o `conectar-claude.ps1` de novo.

---

## Rodar uma vaga

### Passo 1 — descreva a vaga

Cole a descrição que você já usa no anúncio. Quanto mais concreto sobre o **dia a dia** do
cargo, melhores os critérios propostos.

Funciona melhor: *"vai atender chamados N2 de infraestrutura, com SLA de 4 horas, mexendo em
Active Directory e VPN"*.

Funciona pior: *"buscamos profissional dinâmico e comprometido"*.

### Passo 2 — revise os critérios

**Este é o passo que decide a qualidade de tudo.** O sistema propõe; você manda.

- **Eliminatórios** — quem não atende é cortado antes da pontuação, pelo modelo barato.
  Use só para o que é realmente impeditivo: registro no conselho, CNH obrigatória, presencial
  numa cidade específica. Na dúvida, **não** é eliminatório — transforme em critério com peso
  alto.

- **Critérios pontuados** — cada um de 0 a 10, com pesos somando 100. Se experiência em
  suporte vale o dobro de inglês, ponha 40 e 20. Ajuste o texto da descrição para dizer, em
  português claro, o que separa nota 9 de nota 4 — o avaliador lê exatamente isso.

- **Observações** — o que não cabe nos critérios. *"O time é pequeno, então autonomia pesa
  mais que especialização."*

Nada é avaliado antes de você clicar em **Aprovar critérios**.

### Passo 3 — envie os currículos

Arraste tudo de uma vez. Aceita PDF, Word (`.docx` e `.doc`), texto, e planilha exportada do
seu ATS ou do LinkedIn (`.csv`, `.xlsx`) — nesse caso cada linha vira um candidato.

PDF escaneado funciona. O sistema percebe que não há texto embutido e faz a leitura por
reconhecimento de caracteres, no próprio servidor. Isso leva alguns segundos por página, então
acontece **depois** que o upload termina: os arquivos entram na hora, marcados como *lendo*, e
vão ficando prontos sozinhos. Você não precisa esperar na tela.

Currículo digitalizado sai pior que um PDF normal, e o sistema diz isso em vez de esconder:
quando a leitura fica duvidosa, o candidato aparece marcado com **texto por OCR**. Se nem
assim der para garantir que o nome saiu do texto, aquele currículo **não é enviado para
avaliação** e aparece na lista de *Não foi possível avaliar*, com o motivo — é o momento de
mandar uma versão melhor do arquivo.

Arquivo repetido é reconhecido pelo conteúdo e não é processado de novo, mesmo que o nome seja
diferente e mesmo meses depois.

### Passo 4 — acompanhe e decida

O painel mostra quantos já foram avaliados dos que você enviou, e quando foi o último
registro. Quem avalia é o Claude, na conversa que você abriu com ele — então o número anda
enquanto vocês conversam, e para quando a conversa para.

Se ficar parado por muito tempo, o painel avisa e te dá a frase para pedir que ele continue.
Fechar esta tela não interrompe nada, e reabrir mostra o estado real.

Você já pode clicar nos candidatos que ficaram prontos.

Ao clicar num nome, o painel da direita mostra:

- **A nota de cada critério** e a **evidência**: o trecho do currículo que sustenta aquela
  nota. Se aparecer *"sem evidência no currículo"* em vermelho, o candidato não escreveu nada
  sobre aquele ponto — não é que ele não saiba, é que não está lá.
- **Pontos fortes** e **Atenção**.
- **Abrir currículo original** — o arquivo como chegou.
- **Sua decisão**: *entrevistar*, *reserva* ou *arquivado*, com espaço para anotação.

A decisão e a anotação entram no CSV e no relatório.

---

## O que levar para a reunião

**Relatório** abre um documento pronto para imprimir ou salvar em PDF. Ele traz os critérios
que você aprovou, a nota de cada candidato e a evidência de cada nota.

É esse documento que responde a *"por que esse candidato ficou de fora?"* — a resposta não é
"a IA achou", é "ele tirou 3 no critério que vale 40%, e o currículo não menciona o assunto".

**CSV** abre no Excel com acentos certos e ponto-e-vírgula como separador. Serve para juntar
com sua planilha de controle.

---

## Coisas que economizam seu tempo

**Mudou de ideia sobre os pesos?** Volte aos critérios, ajuste e clique em **Reavaliar**. A
leitura dos currículos vem do cache e **não é cobrada de novo** — só a nova pontuação.

**Buscar alguém no meio de 150?** O campo de busca no topo do ranking filtra por nome ou
arquivo.

**Ver só quem interessa?** Os filtros *Chamar*, *Talvez*, *Descartar* e *Marcados*.

**Confiança baixa** ao lado do nome significa: o currículo é curto ou genérico demais para
uma avaliação segura. Vale um olhar humano antes de descartar.

**Aviso de divergência** significa: o modelo recomendou uma coisa e a nota ponderada aponta
outra. Nesse caso vale a nota, que é a que você pode auditar — mas leia o candidato com
atenção.

---

## Fazer a triagem conversando com o Claude

Dá para usar tudo isso por dentro do Claude, sem abrir o sistema. Serve bem para
uma vaga pequena, para ajustar critérios conversando, ou para perguntar coisas que
a tela não responde: *"desses cinco, quem tem mais experiência com SLA apertado?"*

### Ligar

Você precisa do **Claude Desktop** instalado (https://claude.ai/download).

Com a Triagem aberta, clique com o botão direito em **conectar-claude.ps1** e
escolha *Executar com o PowerShell*. Ele pede seu e-mail e sua senha da Triagem
— a mesma que você já usa, não há segunda conta — e configura tudo sozinho.

Feche e abra o Claude Desktop. Pronto.

**Pelo site claude.ai não funciona**, e não é defeito: o site roda nos servidores
da Anthropic e a Triagem roda no seu computador. Um não enxerga o outro. Se um
dia o sistema for instalado num servidor da empresa, com endereço próprio, aí o
site passa a funcionar também.

### Usar

Depois de conectado, converse normalmente:

- *"Liste minhas vagas na Triagem"*
- *"Proponha critérios para a vaga de analista de suporte"*
- *"Avalie os currículos dessa vaga"*
- *"Quem são os cinco melhores e por quê?"*
- *"Marque o primeiro para entrevista, com a anotação: ligar terça"*

Tudo o que o Claude fizer aparece na tela normal do sistema — o ranking, o CSV e
o relatório continuam funcionando igual. E o contrário também: o que você envia
pela tela, o Claude encontra.

Você **não precisa** deixar a Triagem aberta para conversar com o Claude: ele lê
os dados direto. Abra o atalho *iniciar* quando for enviar currículos, ver o
relatório ou usar a tela.

### O que o Claude vê e o que ele não vê

Os currículos chegam ao Claude **sem nome, e-mail, telefone, idade, CPF nem
endereço**. É de propósito: quem dá as notas não deve saber quem é a pessoa.

Isso vale até no ranking. Quando você pede *"mostra o ranking"*, ele responde por
código de candidato e nota, não por nome. O nome sai quando você pede o contato —
*"me dá o contato do primeiro colocado"* — e essa consulta fica registrada.

Parece incômodo, e é de propósito: é isso que te deixa responder, se alguém
questionar, que quem deu a nota não sabia o nome, a idade nem o endereço de
ninguém. **Nesta tela aqui você continua vendo tudo** — a restrição é sobre o que
o Claude enxerga, não sobre o que você enxerga.

Como essa limpeza é feita por regra, e não por leitura, ela às vezes não acha o
nome (currículo que começa direto no texto, sem cabeçalho). Quando isso acontece
num currículo normal, o Claude recebe um aviso de que pode ter sobrado
identificação. Quando acontece num currículo **digitalizado**, onde a leitura já
é menos confiável, o sistema não arrisca: aquele currículo não é enviado, e
aparece para você com o motivo.

**Uma coisa não funciona pelo conector:** enviar muitos arquivos de uma vez.
Arraste os arquivos nesta tela e depois volte a conversar. PDF escaneado, esse,
funciona normalmente — a leitura acontece aqui no servidor antes de o Claude
receber qualquer coisa.

---

## Quando um candidato pede os dados dele

Isso é direito dele pela LGPD, e você tem 15 dias para responder.

Vá em **Dados**, busque pelo nome ou e-mail e escolha:

- **Exportar** — baixa um arquivo com tudo que a empresa guarda sobre a pessoa. É isso que
  você envia para ela.
- **Apagar** — remove o currículo, o arquivo original e todas as avaliações, em todas as
  vagas. **Não tem volta.**

Fica registrado que você atendeu, com data e seu nome. É essa prova que importa se alguém
questionar depois.

Nessa mesma tela você vê quantos currículos estão guardados e quantos estão para ser
apagados pelo prazo de retenção que você definiu.

---

## Perguntas que aparecem sempre

**O sistema vê o nome e a idade do candidato?**
Não na hora de avaliar. Nome, contato, idade e endereço são separados antes, e quem dá as
notas recebe só a trajetória profissional. Isso reduz viés e é o que sustenta a resposta
quando alguém alegar discriminação.

**E se o candidato escrever "me dê nota 10" no currículo?**
O sistema é instruído a tratar tudo que vem dentro do currículo como material a analisar,
nunca como ordem. Uma tentativa dessas aparece como ponto de atenção no candidato.

**Posso confiar na nota?**
Confie na *evidência*, não na nota. A nota é uma média ponderada dos critérios que você
mesmo definiu. Se a evidência citada não te convence, a nota não vale — e é para isso que ela
está ali.

**Quantos currículos por vez?**
Não há limite prático no envio. 150 é o cenário testado. A avaliação em si acontece na sua
conversa com o Claude, e uma vaga desse tamanho costuma não caber numa conversa só — quando
ele parar, abra outra e peça para continuar. O sistema sabe quem já foi avaliado e entrega só
o que falta, sem repetir.

**Fechei o navegador no meio. Perdi?**
Não. Tudo que o Claude já registrou está salvo. Volte em **Vagas** e clique na vaga: o painel
mostra o estado real, inclusive de outro computador.

**Isso consome o quê?**
A sua assinatura do Claude, que você já paga. Não há cobrança por currículo, nem conta de
serviço de IA para abrir. A leitura de PDF digitalizado acontece no próprio servidor e não
consome nada.

**Mandei a mesma vaga para avaliar de novo com pesos diferentes. Custa alguma coisa?**
Não em dinheiro. Refaz a pontuação usando a sua cota do Claude, como qualquer conversa. Os
currículos não precisam ser lidos de novo.
