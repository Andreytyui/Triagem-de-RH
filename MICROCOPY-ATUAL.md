# Microcopy em uso — inventário para revisão da Pigmento

Levantado por Vitral a pedido da Pigmento, para ela revisar em cima das regras
de tom de voz dela (segunda pessoa; presente para estado e imperativo educado
para ação; sem jargão; sem culpar o usuário; sem mencionar IA para o cliente
final; sem juízo de valor sobre candidato).

Referência de arquivo e linha ao lado de cada texto. Nada aqui foi alterado.

---

## Estados vazios

| Onde | Texto | Ref |
|---|---|---|
| Ranking, busca sem resultado | Nenhum candidato com "{termo}" no nome. | `static/app.js:978` |
| Ranking, faixa sem ninguém | Nenhum candidato nesta faixa. | `static/app.js:979` |
| Detalhe, nada selecionado | Escolha um candidato para ver as notas e a evidência de cada uma. | `static/app.js:1379` |
| Painel, antes de avaliar | Nenhum candidato avaliado ainda | `static/app.js:817` |
| Critérios, sem eliminatório | Nenhum eliminatório. Todos os candidatos vão para a pontuação. | `static/app.js:435` |
| Tokens | Nenhum token gerado. | `static/app.js:1482` |
| Auditoria | Nada registrado ainda. | `static/app.js:1626` |
| Pessoas, busca | Ninguém encontrado com esse termo. | `static/app.js:1594` |
| Lista de vagas | nenhuma vaga em andamento | `static/app.js:1274` |
| Primeira vez no produto | (convite escrito, tela cheia) | `static/app.js:1253` |

## Carregando / em andamento

| Onde | Texto | Ref |
|---|---|---|
| Envio de arquivos | Enviando {n} arquivo(s)… | `static/app.js:620` |
| Progresso do envio | {i} de {n} processados… | `static/app.js:639` |
| Estado da vaga | avaliação em andamento · avaliação concluída · avaliação interrompida · pronta para receber currículos | `static/app.js` |
| Candidato | Ainda avaliando | `static/app.js:991` |
| Extração | arquivo ainda está sendo lido / arquivos ainda estão sendo lidos | `static/app.js` |

## Erro e atenção

| Onde | Texto | Ref |
|---|---|---|
| Nenhum arquivo aceito | Nenhum arquivo foi aceito. Confira os formatos. | `static/app.js:691` |
| Currículo sem avaliação | Não foi possível avaliar: {motivo} | `static/app.js` |
| Descrição curta | A descrição está curta demais para gerar critérios úteis. | `static/app.js` |
| Critérios | Mantenha ao menos um critério pontuado. | `static/app.js` |
| Sessão | Sua sessão expirou. Entre de novo. | `static/app.js` |
| Link de senha expirado | Este link expirou. Peça um novo — o próximo também vale por 30 minutos. | `static/app.js` |
| Link de senha inválido | Este link não é válido, ou já foi usado para trocar a senha. | `static/app.js` |
| OCR | PDF escaneado — o texto pode ter falhas | `static/app.js:665` |
| OCR no detalhe | …veio de OCR e pode conter falhas — os trechos citados abaixo podem estar imprecisos. | `static/app.js:1161` |
| Selo de OCR | OCR · confiança baixa | `static/app.js` |
| Evidência ausente | Sem evidência no currículo | `static/app.js` |

## Confirmação e ação destrutiva

| Onde | Texto | Ref |
|---|---|---|
| Apagar candidato | O currículo, o arquivo original e todas as avaliações somem de todas as vagas. Isso não tem volta. O registro de que você apagou fica na auditoria. | `static/app.js` |
| Reavaliar | As avaliações somem. Os currículos continuam na base e podem ser usados em … | `static/app.js` |
| Salvo | Configurações salvas. · Endereço copiado. · Senha trocada. As outras sessões foram encerradas. | `static/app.js` |
| Pessoa criada | Pessoa adicionada. Peça para ela trocar a senha no primeiro acesso. | `static/app.js` |

## Ações (botões)

Propor critérios · Aprovar critérios · Adicionar critério · Adicionar
eliminatório · Ver o andamento da avaliação · Enviar link de recuperação ·
Configurações
(`static/index.html:194,238,230,216,274,77,159`)

## Dicas de campo

| Texto | Ref |
|---|---|
| Mínimo de 10 caracteres. Prefira uma frase a um símbolo. | `static/index.html:59,101` |
| {n} caracteres — a partir de 40 dá para gerar critérios | `static/index.html:191` |
| Passado esse prazo, o currículo e o arquivo original são apagados sozinhos. É a sua política de LGPD. | `static/index.html:401` |
| Quem abriu, exportou e apagou o quê. Guardado por dois anos. | `static/index.html:460` |
| Anotação para você e para o time. Entra no relatório e no CSV. | `static/app.js` |
| Condição objetiva, verificável no currículo | `static/app.js` |
| Marque os candidatos como "entrevistar" — o shortlist é feito deles. | `static/app.js` |

## O cluster que precisa de decisão sua

Estes são os únicos textos do app que nomeiam a IA. Todos vivem em tela de
**configuração do conector**, não em resultado de avaliação:

- Conecte o Claude para começar a avaliar — a avaliação roda no seu plano, sem chave de API e sem custo por currículo.
- O Claude lê direto do banco: não precisa deixar esta janela aberta.
- O conector ainda não foi ligado nesta conta — configure em Configurações.
- Conta criada. Ligue o Claude em Configurações para começar.
- O Claude perde o acesso a esta conta e você precisará autorizar de novo.

Nenhum deles aparece no documento de entrega ao cliente. A regra da Pigmento
proíbe mencionar IA para o cliente final e pede evitar dentro do app *quando o
assunto é o resultado da avaliação* — o que estes textos não são. Falta o
veredito dela: mantém nomeando "Claude" na configuração, ou troca por
"conector" também aí?
