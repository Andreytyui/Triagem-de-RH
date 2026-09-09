"use strict";

const $ = (id) => document.getElementById(id);
const $$ = (sel, raiz = document) => [...raiz.querySelectorAll(sel)];

const estado = {
  usuario: null,
  org: null,
  vagaId: null,
  vagaTitulo: "",
  rubrica: null,
  resultados: [],
  filtro: "todos",
  busca: "",
  selecionado: null,
  timer: null,
  ultimoFeitos: -1,
  mudouEm: 0,
  pedirReavaliacao: false,
  conectorLigado: false,
  tokenRecuperacao: null,
  emailRecuperacao: "",
  timerReenvio: null,
};

const SECOES = ["passo-vaga", "passo-rubrica", "passo-upload", "passo-resultados",
                "passo-lista", "passo-config", "passo-lgpd"];

const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const ROTULO_DECISAO = {
  sem_decisao: "sem decisão",
  entrevistar: "entrevistar",
  reserva: "reserva",
  arquivado: "arquivado",
};

// ---------- comunicação ----------

function cookie(nome) {
  const achado = document.cookie.split("; ").find((c) => c.startsWith(nome + "="));
  return achado ? decodeURIComponent(achado.slice(nome.length + 1)) : "";
}

async function api(caminho, opcoes = {}) {
  const metodo = (opcoes.method || "GET").toUpperCase();
  const cabecalhos = { ...(opcoes.headers || {}) };
  if (["POST", "PUT", "PATCH", "DELETE"].includes(metodo)) {
    cabecalhos["X-CSRF-Token"] = cookie("triagem_csrf");
  }

  const resp = await fetch(caminho, { ...opcoes, headers: cabecalhos });
  if (resp.status === 401 && estado.usuario) {
    mostrarEntrada("Sua sessão expirou. Entre de novo.");
    throw new Error("sessão expirada");
  }
  if (!resp.ok) {
    let detalhe = null;
    try { detalhe = (await resp.json()).detail; } catch { /* resposta sem json */ }
    // Algumas rotas devolvem {codigo, mensagem} para a tela poder reagir a cada
    // causa; as outras devolvem texto puro, como sempre.
    const texto = typeof detalhe === "string" ? detalhe : detalhe?.mensagem;
    const erro = new Error(texto || `erro ${resp.status}`);
    erro.codigo = detalhe && typeof detalhe === "object" ? detalhe.codigo : null;
    erro.status = resp.status;
    throw erro;
  }
  return resp.status === 204 ? null : resp.json();
}

const enviarJson = (caminho, metodo, corpo) =>
  api(caminho, {
    method: metodo,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });

// ---------- avisos ----------

let brindeTimer = null;
function brinde(mensagem, ruim = false) {
  const el = $("brinde");
  el.textContent = mensagem;
  el.className = "brinde" + (ruim ? " ruim" : "");
  el.hidden = false;
  clearTimeout(brindeTimer);
  brindeTimer = setTimeout(() => { el.hidden = true; }, ruim ? 6000 : 3500);
}

function avisar(elId, mensagem) {
  const el = $(elId);
  if (!el) return;
  el.textContent = mensagem || "";
  el.hidden = !mensagem;
}

function faixa(texto, { grave = false, acao = null, aoClicar = null } = {}) {
  const el = $("faixa-aviso");
  if (!texto) { el.hidden = true; return; }
  $("faixa-texto").textContent = texto;
  el.className = "faixa-aviso" + (grave ? " grave" : "");
  el.hidden = false;
  const botao = $("faixa-acao");
  botao.hidden = !acao;
  if (acao) {
    botao.textContent = acao;
    botao.onclick = aoClicar;
  }
}

async function comBotao(botao, textoOcupado, tarefa) {
  const original = botao.textContent;
  botao.disabled = true;
  botao.textContent = textoOcupado;
  // O fio que anda no rodapé do botão diz "ainda estou trabalhando" sem
  // inventar uma porcentagem que ninguém sabe calcular.
  botao.setAttribute("data-ocupado", "");
  try {
    return await tarefa();
  } finally {
    botao.disabled = false;
    botao.textContent = original;
    botao.removeAttribute("data-ocupado");
  }
}

const plural = (n, singular, pluralForma) =>
  `${n} ${n === 1 ? singular : pluralForma}`;

const ESTADO_VAGA = {
  rascunho: "critérios ainda não aprovados",
  pronta: "pronta para receber currículos",
  processando: "avaliação em andamento",
  concluido: "avaliação concluída",
  interrompido: "avaliação interrompida",
  cancelado: "avaliação interrompida",
  erro: "terminou com erro",
};

// ---------- navegação ----------

function mostrar(secaoId) {
  SECOES.forEach((id) => { $(id).hidden = id !== secaoId; });
  window.scrollTo({ top: 0, behavior: "instant" });
}

function pararTimer() {
  clearTimeout(estado.timer);
  clearInterval(estado.timer);
  estado.timer = null;
}

// ---------- sessão ----------

// ---------- as telas do cartão de entrada ----------

const TELAS_ENTRADA = ["form-entrar", "form-criar", "form-recuperar",
                       "aviso-enviado", "form-redefinir", "aviso-link-morto",
                       "aviso-local"];

function telaEntrada(id) {
  TELAS_ENTRADA.forEach((t) => { $(t).hidden = t !== id; });
  // Fora do par entrar/criar, as abas e o lema da marca não fazem sentido: a
  // pessoa está no meio de uma tarefa, não escolhendo um caminho.
  const noPar = id === "form-entrar" || id === "form-criar";
  $("abas").hidden = !noPar;
  $("entrada-lema").hidden = !noPar;
  avisar("erro-entrada", "");

  // O foco acompanha a troca de tela; senão o teclado fica na tela anterior.
  const alvo = $(id).querySelector(".entrada-titulo") || $(id).querySelector("input");
  if (alvo) alvo.focus();
}

$$("[data-entrada]").forEach((b) =>
  b.addEventListener("click", () => telaEntrada(b.dataset.entrada)));

function mostrarEntrada(mensagem) {
  pararTimer();
  estado.usuario = null;
  $("app").hidden = true;
  $("tela-entrada").hidden = false;
  avisar("erro-entrada", mensagem || "");
}

function entrarNoApp(dados) {
  estado.usuario = dados.usuario;
  estado.org = dados.organizacao;
  $("tela-entrada").hidden = true;
  $("app").hidden = false;
  $("topo-usuario").innerHTML =
    `<b>${esc(dados.usuario.nome)}</b><span>${esc(dados.organizacao.nome)}</span>`;
  $("bloco-usuarios").hidden = dados.usuario.papel !== "admin";
  $("bloco-auditoria").hidden = dados.usuario.papel !== "admin";
  conferirModo();
  abrirListaDeVagas();
}

// A avaliação acontece no Claude do próprio recrutador, pelo conector. Só há um
// caminho, então isto serve para uma coisa só: quem ainda não ligou o Claude
// precisa ser levado a ligar, senão nada será avaliado.
async function conferirModo() {
  try {
    const r = await api("/api/org/conector");
    estado.conectorLigado = r.conector_ligado;

    if (r.conector_ligado) { faixa(null); return; }
    faixa(
      "Conecte o Claude para começar a avaliar — a avaliação roda no seu plano, " +
      "sem chave de API e sem custo por currículo.",
      { acao: "Conectar", aoClicar: abrirConfiguracoes }
    );
  } catch { /* sem sessão ainda */ }
}

async function iniciar() {
  let cfg = {};
  try {
    cfg = await api("/api/config");
    $("campo-convite").hidden = !cfg.convite_exigido;
    $("aba-criar").hidden = !cfg.cadastro_aberto;
    // Os dois modos têm caminho de volta, e são caminhos diferentes: hospedado
    // manda link por e-mail, local manda rodar o comando na própria máquina. O
    // link só some se o servidor não disser em qual modo está.
    $("btn-esqueci").hidden = !["email", "local"].includes(cfg.recuperacao);
    $("btn-esqueci").dataset.entrada =
      cfg.recuperacao === "local" ? "aviso-local" : "form-recuperar";
  } catch { /* servidor respondendo o básico já basta */ }

  // Chegou pelo link do e-mail. Vale mesmo com sessão aberta: quem está
  // trocando a senha quer trocar a senha, não voltar para o pódio.
  const token = new URLSearchParams(location.search).get("recuperar");
  if (token && cfg.recuperacao === "email") {
    estado.tokenRecuperacao = token;
    mostrarEntrada();
    telaEntrada("form-redefinir");
    return;
  }

  try {
    entrarNoApp(await api("/api/auth/eu"));
  } catch {
    mostrarEntrada();
  }
}

$("aba-entrar").addEventListener("click", () => trocarAba(true));
$("aba-criar").addEventListener("click", () => trocarAba(false));

function trocarAba(entrar) {
  $("aba-entrar").classList.toggle("aba-ativa", entrar);
  $("aba-criar").classList.toggle("aba-ativa", !entrar);
  telaEntrada(entrar ? "form-entrar" : "form-criar");
}

$("form-entrar").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  avisar("erro-entrada", "");
  const botao = ev.submitter || $("form-entrar").querySelector("button");
  try {
    await comBotao(botao, "Entrando…", async () => {
      const dados = await enviarJson("/api/auth/login", "POST", {
        email: $("login-email").value.trim(),
        senha: $("login-senha").value,
      });
      $("login-senha").value = "";
      entrarNoApp(dados);
    });
  } catch (e) { avisar("erro-entrada", e.message); }
});

// Pedir o link. A resposta é sempre a mesma tela, exista a conta ou não — e o
// servidor responde 204 até quando freia por excesso de pedidos, pelo mesmo
// motivo: um 429 diria que este e-mail é interessante.
$("form-recuperar").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  avisar("erro-entrada", "");
  const botao = ev.submitter || $("form-recuperar").querySelector(".btn-principal");
  estado.emailRecuperacao = $("rec-email").value.trim();
  try {
    await comBotao(botao, "Enviando…", () =>
      enviarJson("/api/auth/recuperar", "POST", { email: estado.emailRecuperacao }));
    telaEntrada("aviso-enviado");
    contarReenvio();
  } catch (e) { avisar("erro-entrada", e.message); }
});

// Reenviar tem espera própria: sem ela, o botão vira um jeito de encher a caixa
// de entrada de outra pessoa.
function contarReenvio() {
  const botao = $("btn-reenviar");
  let resta = 60;
  clearInterval(estado.timerReenvio);
  const passo = () => {
    botao.disabled = resta > 0;
    botao.textContent = resta > 0 ? `Reenviar (${resta}s)` : "Reenviar";
    if (resta <= 0) clearInterval(estado.timerReenvio);
    resta -= 1;
  };
  passo();
  estado.timerReenvio = setInterval(passo, 1000);
}

$("btn-reenviar").addEventListener("click", async () => {
  if (!estado.emailRecuperacao) { telaEntrada("form-recuperar"); return; }
  try {
    await enviarJson("/api/auth/recuperar", "POST", { email: estado.emailRecuperacao });
    brinde("Link reenviado, se a conta existir.");
  } catch (e) { avisar("erro-entrada", e.message); }
  contarReenvio();
});

$("red-mostrar").addEventListener("change", (ev) => {
  $("red-senha").type = ev.target.checked ? "text" : "password";
});

function linkMorto(texto) {
  $("texto-link-morto").textContent = texto;
  estado.tokenRecuperacao = null;
  limparTokenDaUrl();
  telaEntrada("aviso-link-morto");
}

// O token sai da barra de endereço assim que deixa de servir: ele troca uma
// senha, e barra de endereço é copiada, colada e guardada no histórico.
function limparTokenDaUrl() {
  if (location.search) history.replaceState({}, "", location.pathname);
}

$("form-redefinir").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  avisar("erro-entrada", "");
  const senha = $("red-senha").value;
  // Só o tamanho é conferido aqui. As outras críticas (senha previsível, poucos
  // caracteres diferentes) são do servidor, e a mensagem dele é melhor que um
  // palpite nosso.
  if (senha.length < 10) {
    avisar("erro-entrada", "A senha precisa de pelo menos 10 caracteres.");
    return;
  }
  const botao = ev.submitter || $("form-redefinir").querySelector(".btn-principal");
  try {
    await comBotao(botao, "Salvando…", () =>
      enviarJson("/api/auth/redefinir", "POST",
                 { token: estado.tokenRecuperacao, senha }));
    $("red-senha").value = "";
    estado.tokenRecuperacao = null;
    limparTokenDaUrl();
    telaEntrada("form-entrar");
    brinde("Senha alterada. Entre com a nova senha.");
  } catch (e) {
    if (e.codigo === "token_expirado") {
      linkMorto("Este link expirou. Peça um novo — o próximo também vale por 30 minutos.");
    } else if (e.codigo === "token_invalido") {
      linkMorto("Este link não é válido, ou já foi usado para trocar a senha.");
    } else {
      avisar("erro-entrada", e.message);
    }
  }
});

$("form-criar").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  avisar("erro-entrada", "");
  const botao = ev.submitter || $("form-criar").querySelector("button");
  try {
    await comBotao(botao, "Criando…", async () => {
      const dados = await enviarJson("/api/auth/registrar", "POST", {
        organizacao: $("reg-org").value.trim(),
        nome: $("reg-nome").value.trim(),
        email: $("reg-email").value.trim(),
        senha: $("reg-senha").value,
        convite: $("reg-convite").value.trim(),
      });
      $("reg-senha").value = "";
      entrarNoApp(dados);
      brinde("Conta criada. Ligue o Claude em Configurações para começar.");
    });
  } catch (e) { avisar("erro-entrada", e.message); }
});

$("btn-sair").addEventListener("click", async () => {
  try { await api("/api/auth/logout", { method: "POST" }); } catch { /* já saiu */ }
  mostrarEntrada();
});

// ---------- passo 1: vaga ----------

$("in-descricao").addEventListener("input", () => {
  $("conta-descricao").textContent = $("in-descricao").value.trim().length;
});

$("btn-gerar").addEventListener("click", async () => {
  const titulo = $("in-titulo").value.trim();
  const descricao = $("in-descricao").value.trim();

  if (!titulo) return avisar("erro-vaga", "Informe o cargo.");
  if (descricao.length < 40) {
    return avisar("erro-vaga", "A descrição está curta demais para gerar critérios úteis.");
  }
  avisar("erro-vaga", "");

  try {
    await comBotao($("btn-gerar"), "Lendo a vaga…", async () => {
      const dados = await enviarJson("/api/vagas", "POST", { titulo, descricao });
      estado.vagaId = dados.vaga_id;
      estado.vagaTitulo = titulo;
      estado.rubrica = dados.rubrica;
      $("topo-vaga").textContent = titulo;
      desenharRubrica();
      mostrar("passo-rubrica");
    });
  } catch (e) { avisar("erro-vaga", e.message); }
});

// ---------- passo 2: rubrica ----------

// Rampa de um tom só: as fatias são partes de um mesmo todo, não categorias.
// A cor mora no CSS (--petroleo-1..7); aqui só sai o índice, para quem trocar
// tom não precisar abrir JavaScript. Numeração 1..7 igual à dos tokens.
const TONS = 7;
const tomDe = (i) => (i % TONS) + 1;

function desenharRubrica() {
  const r = estado.rubrica;

  // Eliminatório é regra binária: sem peso, sem nota. A forma diz isso.
  $("lista-eliminatorios").innerHTML = r.eliminatorios.length
    ? `<div class="elim-lista">` + r.eliminatorios.map((el, i) => `
        <div class="elim-item" data-tipo="elim" data-i="${i}">
          <span class="elim-marca" aria-hidden="true"></span>
          <input type="text" class="f-descricao" value="${esc(el.descricao)}"
                 placeholder="Condição objetiva, verificável no currículo"
                 aria-label="Requisito eliminatório ${i + 1}">
          <button class="btn-remover" data-remove="elim" data-i="${i}">Remover</button>
        </div>`).join("") + `</div>`
    : `<p class="vazio">Nenhum eliminatório. Todos os candidatos vão para a pontuação.</p>`;

  // Critério tem peso, e o peso tem tamanho visível.
  $("lista-criterios").innerHTML = `<div class="crit-lista">` +
    r.criterios.map((c, i) => `
      <div class="crit-item" data-tipo="crit" data-i="${i}">
        <input type="text" class="f-nome" value="${esc(c.nome)}"
               placeholder="Nome do critério" aria-label="Nome do critério ${i + 1}">
        <label class="crit-peso">
          <input type="number" class="f-peso" value="${c.peso}" min="0" max="100"
                 aria-label="Peso de ${esc(c.nome) || `critério ${i + 1}`}">
          <span>%</span>
        </label>
        <div class="crit-barra" aria-hidden="true">
          <div data-tom="${tomDe(i)}" style="width:${Math.min(100, c.peso)}%"></div>
        </div>
        <textarea class="f-descricao" rows="2"
                  placeholder="O que separa nota alta de nota baixa, em termos concretos"
                  aria-label="Descrição do critério ${i + 1}">${esc(c.descricao)}</textarea>
        <div class="crit-rodape">
          <button class="btn-remover" data-remove="crit" data-i="${i}">Remover</button>
        </div>
      </div>`).join("") + `</div>`;

  $("in-observacoes").value = r.observacoes || "";
  atualizarSoma();
}

function lerRubrica() {
  const r = estado.rubrica;
  const elims = $$('[data-tipo="elim"]').map((no, i) => ({
    id: r.eliminatorios[i]?.id || `elim_${i}`,
    descricao: no.querySelector(".f-descricao").value.trim(),
  })).filter((e) => e.descricao);

  const crits = $$('[data-tipo="crit"]').map((no, i) => ({
    id: r.criterios[i]?.id || `crit_${i}`,
    nome: no.querySelector(".f-nome").value.trim(),
    descricao: no.querySelector(".f-descricao").value.trim(),
    peso: parseInt(no.querySelector(".f-peso").value, 10) || 0,
  })).filter((c) => c.nome);

  return {
    cargo: r.cargo, senioridade: r.senioridade,
    eliminatorios: elims, criterios: crits,
    observacoes: $("in-observacoes").value.trim(),
  };
}

function atualizarSoma() {
  const campos = $$(".f-peso");
  const pesos = campos.map((i) => Math.max(0, parseInt(i.value, 10) || 0));
  const soma = pesos.reduce((t, p) => t + p, 0);
  const nomes = $$(".f-nome").map((i) => i.value.trim());

  // A distribuição como um objeto só: dá para ver a proporção sem ler número.
  $("distribuicao").innerHTML = soma
    ? pesos.map((p, i) => `
        <span class="distribuicao-fatia" data-tom="${tomDe(i)}"
              style="flex:0 0 ${(p / soma) * 100}%"
              title="${esc(nomes[i] || "critério")}: ${p}%"></span>`).join("")
    : "";

  $("distribuicao-nomes").textContent = campos.length
    ? plural(campos.length, "critério", "critérios") + ", na ordem abaixo"
    : "";

  const alvo = $("soma-pesos");
  alvo.textContent = soma === 100 ? "100%" : `${soma}% — ajustado para 100 ao salvar`;
  alvo.classList.toggle("errada", soma !== 100);

  // A barra de cada critério mostra o peso dele dentro do total, não em 100.
  $(".crit-barra > div").forEach((barra, i) => {
    barra.style.width = soma ? `${(pesos[i] / soma) * 100}%` : "0%";
    barra.dataset.tom = tomDe(i);
  });
}

$("lista-criterios").addEventListener("input", (ev) => {
  if (ev.target.classList.contains("f-peso") || ev.target.classList.contains("f-nome")) {
    atualizarSoma();
  }
});

document.addEventListener("click", (ev) => {
  const alvo = ev.target.closest("[data-remove]");
  if (!alvo) return;
  const i = Number(alvo.dataset.i);
  estado.rubrica = lerRubrica();
  if (alvo.dataset.remove === "elim") estado.rubrica.eliminatorios.splice(i, 1);
  else estado.rubrica.criterios.splice(i, 1);
  desenharRubrica();
});

$("btn-add-elim").addEventListener("click", () => {
  estado.rubrica = lerRubrica();
  estado.rubrica.eliminatorios.push({ id: `elim_${Date.now()}`, descricao: "" });
  desenharRubrica();
});

$("btn-add-crit").addEventListener("click", () => {
  estado.rubrica = lerRubrica();
  estado.rubrica.criterios.push({ id: `crit_${Date.now()}`, nome: "", descricao: "", peso: 0 });
  desenharRubrica();
});

$("btn-aprovar").addEventListener("click", async () => {
  const rubrica = lerRubrica();
  if (!rubrica.criterios.length) {
    return avisar("erro-rubrica", "Mantenha ao menos um critério pontuado.");
  }
  avisar("erro-rubrica", "");
  try {
    await comBotao($("btn-aprovar"), "Salvando…", async () => {
      const dados = await enviarJson(`/api/vagas/${estado.vagaId}/rubrica`, "PUT", rubrica);
      estado.rubrica = dados.rubrica;
      await atualizarContagem();
      mostrar("passo-upload");
    });
  } catch (e) { avisar("erro-rubrica", e.message); }
});

// ---------- passo 3: upload ----------

const solta = $("solta");
const entrada = $("in-arquivos");

solta.addEventListener("click", () => entrada.click());
solta.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); entrada.click(); }
});
["dragenter", "dragover"].forEach((ev) =>
  solta.addEventListener(ev, (e) => { e.preventDefault(); solta.classList.add("ativa"); }));
["dragleave", "drop"].forEach((ev) =>
  solta.addEventListener(ev, (e) => { e.preventDefault(); solta.classList.remove("ativa"); }));

solta.addEventListener("drop", (e) => enviar([...e.dataTransfer.files]));
entrada.addEventListener("change", () => enviar([...entrada.files]));

async function atualizarContagem() {
  const vaga = await api(`/api/vagas/${estado.vagaId}`);
  $("contagem-curriculos").textContent =
    plural(vaga.curriculos, "currículo na vaga", "currículos na vaga");
  desenharProximoPasso(vaga.curriculos);
  return vaga.curriculos;
}

// Um caminho só: quem avalia é o Claude do plano do recrutador. Não há gatilho
// aqui para disparar — há um pedido para levar até ele.
function desenharProximoPasso(quantos) {
  $("proximo-conector").hidden = !quantos;
  if (!quantos) return;

  $("frase-claude").textContent =
    `Avalie os currículos da vaga "${estado.vagaTitulo}" na Triagem.`;
  $("dica-conector").textContent = estado.conectorLigado
    ? "O Claude lê direto do banco: não precisa deixar esta janela aberta."
    : "O conector ainda não foi ligado nesta conta — configure em Configurações.";
}

// Delegado: a mesma frase pronta aparece depois do upload e dentro do painel
// de status, e id duplicado não existe.
document.addEventListener("click", async (ev) => {
  const botao = ev.target.closest("[data-copiar]");
  if (!botao) return;
  const alvo = $(botao.dataset.copiar);
  if (!alvo) return;
  try {
    await navigator.clipboard.writeText(alvo.textContent.trim());
    brinde("Frase copiada. Cole no Claude.");
  } catch {
    const faixaSel = document.createRange();
    faixaSel.selectNodeContents(alvo);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(faixaSel);
    brinde("Selecionado — use Ctrl+C para copiar.");
  }
});

async function enviar(arquivos) {
  if (!arquivos.length) return;
  avisar("erro-upload", "");
  const fila = $("fila-upload");
  fila.hidden = false;
  fila.innerHTML = `<p class="vazio">Enviando ${arquivos.length} arquivo(s)…</p>`;

  // Lotes evitam estourar o limite de corpo do servidor com 150 PDFs de uma vez.
  const LOTE = 20;
  let novos = 0, repetidos = 0;
  const rejeitados = [];
  const porOcr = [];

  try {
    for (let i = 0; i < arquivos.length; i += LOTE) {
      const form = new FormData();
      arquivos.slice(i, i + LOTE).forEach((a) => form.append("arquivos", a));
      const r = await api(`/api/vagas/${estado.vagaId}/curriculos`,
                          { method: "POST", body: form });
      novos += r.novos;
      repetidos += r.ja_conhecidos;
      rejeitados.push(...r.rejeitados);
      porOcr.push(...(r.por_ocr || []));
      fila.innerHTML =
        `<p class="vazio">${Math.min(i + LOTE, arquivos.length)} de ${arquivos.length} processados…</p>`;
    }

    // Quatro grupos, porque são quatro situações diferentes e cada uma pede uma
    // reação diferente do recrutador.
    const grupos = [];
    if (novos) {
      grupos.push(`
        <div class="fila-grupo">
          <p class="fila-grupo-titulo">${plural(novos, "currículo novo", "currículos novos")}</p>
        </div>`);
    }
    if (repetidos) {
      grupos.push(`
        <div class="fila-grupo">
          <p class="fila-grupo-titulo">${plural(repetidos, "já conhecido", "já conhecidos")}
            <span class="fila-grupo-nota">reaproveitados do que você já enviou antes,
              sem custo de leitura</span></p>
        </div>`);
    }
    // O único momento em que o recrutador ainda pode agir: reescanear, ou pedir
    // o arquivo de novo. Cor neutra — não é recusa, é informação.
    if (porOcr.length) {
      grupos.push(`
        <div class="fila-grupo">
          <p class="fila-grupo-titulo">${plural(porOcr.length, "lido por OCR", "lidos por OCR")}
            <span class="fila-grupo-nota">PDF escaneado — o texto pode ter falhas</span></p>
          <div class="fila-lista">
            ${porOcr.map((o) => `
              <div class="fila-item">
                <span>${esc(o.arquivo)}</span>
                ${o.confianca === "baixa"
                  ? `<span class="fila-grupo-nota">qualidade baixa</span>` : ""}
              </div>`).join("")}
          </div>
        </div>`);
    }
    if (rejeitados.length) {
      grupos.push(`
        <div class="fila-grupo">
          <p class="fila-grupo-titulo">${plural(rejeitados.length, "recusado", "recusados")}
            <span class="fila-grupo-nota">não entraram na vaga</span></p>
          <div class="fila-lista">
            ${rejeitados.map((r) => `
              <div class="fila-item">
                <span>${esc(r.arquivo)}</span>
                <span class="fila-motivo">${esc(r.motivo)}</span>
              </div>`).join("")}
          </div>
        </div>`);
    }
    fila.innerHTML = grupos.join("") ||
      `<p class="vazio">Nenhum arquivo foi aceito. Confira os formatos.</p>`;

    await atualizarContagem();
  } catch (e) {
    avisar("erro-upload", e.message);
    fila.hidden = true;
  } finally {
    entrada.value = "";
  }
}

$("btn-ver-status").addEventListener("click", () => {
  mostrar("passo-resultados");
  acompanhar();
});

// Reavaliar deixa de ser uma ação nossa e vira um pedido ao Claude do
// recrutador — e um aviso de que a cota consumida é a dele.
$("btn-reavaliar").addEventListener("click", () => {
  estado.pedirReavaliacao = true;
  mostrar("passo-resultados");
  acompanhar();
});

$("painel-status").addEventListener("click", (ev) => {
  if (ev.target.id === "btn-ver-falhas") {
    // Sem rolagem suave: a tela já respeita prefers-reduced-motion, e um salto
    // de 150 linhas com animação é exatamente o que essa preferência evita.
    const grupo = $$(".ranking-grupo")
      .find((g) => g.textContent.includes("Não foi possível avaliar"));
    if (grupo) grupo.scrollIntoView({ block: "start" });
  }
  if (ev.target.id === "btn-fechar-reavaliar") {
    estado.pedirReavaliacao = false;
    acompanhar();
  }
  if (ev.target.id === "btn-atualizar") acompanhar();
});

// ---------- passo 4: o painel de status ----------

// A avaliação não roda aqui. Quem avalia é o Claude do plano do recrutador,
// chamando as ferramentas do conector quando ele pede — de outro dispositivo,
// com esta janela fechada, e podendo parar no meio sem avisar ninguém.
//
// Por isso este painel não comanda nada: ele relata o que já foi registrado.
// Sem botão de rodar, sem cancelar, e sem animação contínua — um spinner
// afirmaria que alguma coisa acontece deste lado, e não acontece.

const PARADO_MS  =  5 * 60 * 1000;   // sem registro novo: provavelmente parou
const DESISTE_MS = 15 * 60 * 1000;   // sem registro novo: paramos de perguntar

// Aceita o formato novo e o antigo: enquanto o backend não expõe os campos, o
// painel mostra menos, mas nunca mostra errado.
function lerStatus(s) {
  const p = s.progresso || s;
  const total = p.total ?? 0;
  const avaliados = p.avaliados ?? p.pontuados ?? 0;
  const eliminados = p.eliminados ?? 0;
  const erros = p.erros ?? 0;
  // `com_veredito` é a mesma soma, contada no servidor. Prefiro a dele: um
  // número com duas definições é um número em que não se pode confiar, e essa
  // lição já custou uma divergência entre a lista de vagas e o painel.
  const feitos = Math.min(p.com_veredito ?? (avaliados + eliminados + erros), total);
  return {
    total, avaliados, eliminados, erros, feitos,
    lendo: p.lendo ?? 0,
    pendentes: Math.max(total - feitos, 0),
    ultimo: s.ultimo_registro_em ?? p.ultimo_registro_em ?? null,
  };
}

function haQuantoTempo(iso) {
  if (!iso) return null;
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return null;
  const min = Math.floor(ms / 60000);
  if (min < 1) return "agora há pouco";
  if (min < 60) return `há ${plural(min, "minuto", "minutos")}`;
  return `há ${plural(Math.floor(min / 60), "hora", "horas")}`;
}

function blocoFrase(id, texto) {
  return `
    <div class="frase-pronta">
      <p id="${id}">${esc(texto)}</p>
      <button class="btn-secundario" data-copiar="${id}">Copiar</button>
    </div>`;
}

function desenharStatus(s) {
  const d = lerStatus(s);
  const painel = $("painel-status");
  const vaga = estado.vagaTitulo || "";

  if (!d.total) { painel.hidden = true; return; }
  painel.hidden = false;

  // A manchete conta tudo que já tem veredito. O detalhe decompõe esse número —
  // se ele parecesse somar à manchete, o recrutador faria a conta errada.
  const detalhe = (d.eliminados || d.erros || d.lendo) ? [
    `${d.avaliados} com nota`,
    d.eliminados ? `${d.eliminados} cortados no eliminatório` : "",
    // O ranking agora mostra esses candidatos com o motivo escrito, então a
    // contagem pode levar até eles: é o único grupo do pódio em que a ação é do
    // recrutador (reenviar um arquivo melhor), e ele não some no meio de 150.
    d.erros
      ? `<button class="btn-texto" id="btn-ver-falhas">${d.erros} que não foi
         possível avaliar</button>`
      : "",
    // Extração é trabalho nosso, não do Claude: enquanto ela roda, o candidato
    // ainda não existe para o conector, e dizer isso evita a conta não fechar.
    d.lendo ? `${d.lendo} ainda sendo lidos aqui` : "",
  ].filter(Boolean).join(" · ") : "";

  const reavaliar = estado.pedirReavaliacao ? `
    <p class="status-titulo">Reavaliar com os critérios atuais</p>
    ${blocoFrase("frase-reavaliar",
      `Reavalie os candidatos da vaga "${vaga}" na Triagem com os critérios atuais.`)}
    <p class="dica">A reavaliação roda no seu plano do Claude e consome a sua cota.</p>
    <button class="btn-texto" id="btn-fechar-reavaliar">Fechar</button>` : "";

  // 1. Nada avaliado ainda: o painel é a instrução. Barra em 0% comunicaria
  //    "travado", e o que houve foi só ainda não ter começado.
  if (!d.feitos) {
    painel.innerHTML = `${reavaliar}
      <p class="status-titulo">Nenhum candidato avaliado ainda</p>
      <p class="progresso-texto">A avaliação roda no seu plano do Claude, sem custo
         por currículo. Abra o Claude e mande esta frase:</p>
      ${blocoFrase("frase-status", `Avalie os currículos da vaga "${vaga}" na Triagem.`)}
      ${d.lendo ? `<p class="status-carimbo">${d.lendo} ${d.lendo === 1
        ? "arquivo ainda está sendo lido" : "arquivos ainda estão sendo lidos"} aqui —
        o Claude só enxerga o que já foi lido.</p>` : ""}`;
    return;
  }

  const cabeca = `<p class="status-linha">${d.feitos} de ${d.total} avaliados</p>`;
  const barra = `
    <div class="progresso-trilho" aria-hidden="true">
      <div class="progresso-preenchido"
           style="width:${Math.round((d.feitos / d.total) * 100)}%"></div>
    </div>`;
  // O detalhe carrega um botão, então não pode passar por esc(): as contagens
  // que o compõem são números nossos, não texto vindo de currículo.
  const linhaDetalhe = detalhe ? `<p class="progresso-texto">${detalhe}</p>` : "";

  // 4. Completo: o ranking é a estrela. Uma linha, sem barra, sem celebração.
  if (d.feitos >= d.total) {
    painel.innerHTML = `${reavaliar}
      <p class="status-linha">${d.feitos} de ${d.total} avaliados${
        detalhe ? ` · ${detalhe}` : ""}</p>`;
    return;
  }

  const quieto = d.ultimo ? Date.now() - new Date(d.ultimo).getTime() : 0;

  // 3. Parado no meio. Com MCP a avaliação simplesmente para: a conversa
  //    acabou, o contexto estourou, ele fechou o Claude. Ninguém avisa — e sem
  //    este estado o recrutador ficaria olhando um número que não anda mais.
  if (d.ultimo && quieto > PARADO_MS) {
    painel.innerHTML = `${reavaliar}${cabeca}${barra}${linhaDetalhe}
      <p class="nota-aviso">Sem registros novos ${esc(haQuantoTempo(d.ultimo))}.
         Se o Claude parou, peça para continuar:</p>
      ${blocoFrase("frase-status",
        `Continue avaliando os currículos da vaga "${vaga}" na Triagem — faltam ${d.pendentes}.`)}`;
    return;
  }

  // 2. Em andamento. O carimbo do último registro é o substituto honesto do
  //    spinner: relata o que foi anotado, sem afirmar que algo roda aqui.
  const carimbo = haQuantoTempo(d.ultimo);
  painel.innerHTML = `${reavaliar}${cabeca}${barra}${linhaDetalhe}
    ${carimbo ? `<p class="status-carimbo">último registro ${esc(carimbo)}</p>` : ""}`;
}

function acompanhar() {
  pararTimer();
  estado.mudouEm = Date.now();
  estado.ultimoFeitos = -1;

  const passo = async () => {
    let s;
    try { s = await api(`/api/vagas/${estado.vagaId}/status`); }
    catch { pararTimer(); return; }

    const d = lerStatus(s);
    if (d.feitos !== estado.ultimoFeitos) {
      estado.ultimoFeitos = d.feitos;
      estado.mudouEm = Date.now();
      await carregarResultados();
      // Filtros e exportação já valem para o que ficou pronto até aqui.
      if (estado.resultados.length) desenharMetricas(d);
    }
    desenharStatus(s);
    faixa(s.erro || null, { grave: true });

    // Nada roda do nosso lado: perguntar de 2,5 em 2,5 segundos durante uma
    // conversa de uma hora é desperdício, e um painel que nunca para de piscar
    // sugere um trabalho que não é nosso.
    if (d.feitos >= d.total) { pararTimer(); return; }
    const parado = Date.now() - estado.mudouEm;
    if (parado > DESISTE_MS) {
      pararTimer();
      $("painel-status").insertAdjacentHTML("beforeend",
        `<button class="btn-texto" id="btn-atualizar">Atualizar</button>`);
      return;
    }
    estado.timer = setTimeout(passo, parado > 2 * 60 * 1000 ? 10000 : 2500);
  };
  passo();
}

async function carregarResultados() {
  estado.resultados = await api(`/api/vagas/${estado.vagaId}/resultados`);
  desenharRanking();
  if (estado.selecionado) desenharDetalhe();
}

function desenharMetricas(dados) {
  $("resumo-corrida").hidden = false;
  $("btn-csv").href = `/api/vagas/${estado.vagaId}/export.csv`;
  $("btn-shortlist").href = `/api/vagas/${estado.vagaId}/shortlist`;

  const conta = (chave, valor) => estado.resultados.filter((r) => r[chave] === valor).length;
  const marcados = conta("decisao", "entrevistar");
  const porOcr = conta("origem_texto", "ocr");
  // Condicional de propósito: numa vaga sem nenhum retido, a métrica não existe
  // em vez de mostrar um zero que o recrutador precisa aprender a ignorar.
  const paraLer = estado.resultados.filter((r) => faixaDe(r) === "retido").length;

  $("metricas").innerHTML = `
    <div><span class="metrica-valor acento">${conta("recomendacao", "chamar")}</span>
         <span class="metrica-rotulo">recomendados</span></div>
    <div><span class="metrica-valor">${conta("recomendacao", "talvez")}</span>
         <span class="metrica-rotulo">na dúvida</span></div>
    ${paraLer ? `<div><span class="metrica-valor">${paraLer}</span>
         <span class="metrica-rotulo">para você ler</span></div>` : ""}
    <div><span class="metrica-valor">${marcados}</span>
         <span class="metrica-rotulo">marcados por você</span></div>
    <div><span class="metrica-valor">${dados?.total || estado.resultados.length}</span>
         <span class="metrica-rotulo">currículos lidos</span></div>
    ${porOcr ? `<div><span class="metrica-valor">${porOcr}</span>
         <span class="metrica-rotulo">lidos por OCR</span></div>` : ""}`;

  // O shortlist só existe se houver alguém marcado — dizer isso evita a página vazia.
  const atalho = $("btn-shortlist");
  atalho.textContent = marcados ? `Shortlist (${marcados})` : "Shortlist";
  atalho.dataset.marcados = marcados;

  $$(".filtro").forEach((b) => {
    const f = b.dataset.f;
    const n = f === "todos" ? estado.resultados.length
            : f === "entrevistar" ? marcados
            : estado.resultados.filter((r) => faixaDe(r) === f).length;
    let conta_el = b.querySelector(".filtro-conta");
    if (!conta_el) {
      conta_el = document.createElement("span");
      conta_el.className = "filtro-conta";
      b.appendChild(conta_el);
    }
    conta_el.textContent = n;
  });
}

// Quem a linha identifica. Sem nome lido, o nome do arquivo é a ÚNICA
// identidade que existe para este candidato — e é justamente a que o recrutador
// reconhece, porque foi ele quem subiu o arquivo. Sem isso o grupo "Peça o
// currículo" não tem alça: ele não consegue pedir o currículo de "—".
function nomeDe(r) {
  const nome = (r.nome || "").trim();
  if (nome && nome !== "—") return nome;
  return (r.arquivo || "").trim() || "candidato sem identificação";
}

// O rótulo que a pessoa vê, para o leitor de tela dizer a mesma coisa que a
// tela. A chave da faixa é vocabulário interno e não deve vazar no nome
// acessível — além de envelhecer: "erro" virou "Peça o currículo".
const ROTULO_FAIXA = {
  chamar: "para chamar", talvez: "na dúvida", descartar: "descartar",
  eliminado: "cortado no eliminatório", retido: "para você ler",
  erro: "peça o currículo", pendente: "ainda avaliando",
};

// Faixa de um candidato. Serve ao filtro, ao agrupamento e às contagens — as
// três coisas precisam concordar, senão o chip diz 8 e o grupo mostra 3.
function faixaDe(r) {
  // "eu li, mas não vou arriscar te entregar" e "não consegui ler" são duas
  // situações com ações diferentes, e por muito tempo caíram no mesmo balde.
  // Quem separa é o booleano que o servidor manda — NUNCA substring do texto
  // do motivo, que é microcopy e vai ser reescrito.
  if (r.estagio === "erro") return r.retido ? "retido" : "erro";
  if (r.estagio === "eliminado") return "eliminado";
  return r.recomendacao || "pendente";
}

function listaFiltrada() {
  let lista = estado.resultados;
  if (estado.filtro === "entrevistar") {
    lista = lista.filter((r) => r.decisao === "entrevistar");
  } else if (estado.filtro !== "todos") {
    lista = lista.filter((r) => faixaDe(r) === estado.filtro);
  }
  if (estado.busca) {
    const alvo = estado.busca.toLowerCase();
    lista = lista.filter((r) =>
      (r.nome || "").toLowerCase().includes(alvo) ||
      (r.arquivo || "").toLowerCase().includes(alvo));
  }
  return lista;
}

function desenharRanking() {
  const lista = listaFiltrada();
  if (!lista.length) {
    $("ranking").innerHTML = estado.busca
      ? `<p class="ranking-vazio">Nenhum candidato com “${esc(estado.busca)}” no nome.</p>`
      : `<p class="ranking-vazio">Nenhum candidato nesta faixa.</p>`;
    return;
  }

  // A lista já vem ordenada pela nota, e a recomendação acompanha a nota. Então
  // um selo por linha repetiria 25 vezes o que um cabeçalho de grupo diz uma vez.
  const GRUPOS = [
    ["chamar", "Para chamar"],
    ["talvez", "Na dúvida"],
    ["descartar", "Descartar"],
    ["eliminado", "Cortados no eliminatório"],
    // A ação decide o grupo; a verdade decide o nome. Aqui cabem dois estados —
    // arquivo ilegível e arquivo lido que não era currículo — e eles ficam
    // juntos porque o próximo clique do recrutador é o mesmo: conseguir o
    // currículo desta pessoa. Um rótulo dizendo que a leitura falhou seria
    // mentira no segundo: a extração funcionou, e o que faltou era currículo.
    // O motivo na linha distingue por quê, e isso é
    // legítimo justamente porque a ação não muda.
    ["retido", "Para você ler"],
    ["erro", "Peça o currículo"],
    ["pendente", "Ainda avaliando"],
  ];

  // Dois eixos diferentes moram nesta linha, e o recrutador reage a cada um de
  // um jeito: OCR é sobre a nossa leitura do arquivo (peça outro), confiança é
  // sobre o quanto a nota se apoia em evidência (leia com reserva). Quando os
  // dois valem, uma linha só — dois selos brigariam com a nota, que é o que o
  // pódio existe para mostrar.
  const metaDe = (r) => {
    const ocr = r.origem_texto === "ocr" && r.ocr_confianca === "baixa";
    const fraca = r.confianca === "baixa";
    // Para quem não pôde ser avaliado, o motivo é o que o recrutador precisa
    // para agir — e ele estava só atrás de um clique. O cand-meta já trunca a
    // 380px, então cabe aqui.
    if (r.estagio === "erro" && r.erro) return r.erro;
    if (ocr && fraca) return "OCR · confiança baixa";
    if (ocr) return "texto por OCR";
    if (fraca) return "confiança baixa";
    return "";
  };

  const linha = (r) => {
    const semNota = r.estagio !== "avaliado" || r.score_final == null;
    const score = semNota ? "—" : Math.round(r.score_final);
    const decidiu = r.decisao && r.decisao !== "sem_decisao";
    const meta = metaDe(r);
    return `
      <li>
        <button class="linha-cand${estado.selecionado === r.candidato_id ? " selecionada" : ""}"
                data-cid="${esc(r.candidato_id)}"
                aria-label="${esc(nomeDe(r))}, ${semNota ? esc(ROTULO_FAIXA[faixaDe(r)] || faixaDe(r)) : `nota ${score} de 100`}${
                  meta ? `, ${esc(meta)}` : ""}${decidiu ? `, ${esc(ROTULO_DECISAO[r.decisao])}` : ""}">
          <span class="cand-score${semNota ? " sem-nota" : ""}" aria-hidden="true">${score}</span>
          <span>
            <span class="cand-nome">${esc(nomeDe(r))}</span>
            ${meta ? `<span class="cand-meta"><span>${esc(meta)}</span></span>` : ""}
          </span>
          ${decidiu
            ? `<span class="marca-decisao marca-${esc(r.decisao)}" aria-hidden="true"></span>`
            : "<span></span>"}
        </button>
      </li>`;
  };

  const partes = [];
  for (const [chave, rotulo] of GRUPOS) {
    const doGrupo = lista.filter((r) => faixaDe(r) === chave);
    if (!doGrupo.length) continue;
    partes.push(
      `<li class="ranking-grupo"><span>${rotulo}</span><span>${doGrupo.length}</span></li>`,
      ...doGrupo.map(linha)
    );
  }
  $("ranking").innerHTML = partes.join("");
}

$("ranking").addEventListener("click", (ev) => {
  const botao = ev.target.closest("[data-cid]");
  if (!botao) return;
  estado.selecionado = botao.dataset.cid;
  desenharRanking();
  desenharDetalhe();
});

$$(".filtro").forEach((b) =>
  b.addEventListener("click", () => {
    $$(".filtro").forEach((x) => x.classList.remove("filtro-ativo"));
    b.classList.add("filtro-ativo");
    estado.filtro = b.dataset.f;
    desenharRanking();
  }));

$("busca").addEventListener("input", (ev) => {
  estado.busca = ev.target.value.trim();
  desenharRanking();
});

// O shortlist é a peça que o recrutador entrega ao cliente dele. Se não houver
// ninguém marcado, a página sairia vazia — melhor explicar do que abrir o vazio.
$("btn-shortlist").addEventListener("click", (ev) => {
  if (Number(ev.currentTarget.dataset.marcados || 0) > 0) return;
  ev.preventDefault();
  brinde("Marque os candidatos como “entrevistar” — o shortlist é feito deles.", true);
});

// ---------- detalhe do candidato ----------

// A vizinhança vem PRONTA do servidor: números, sinais e rótulos já calculados
// em Python. Aqui não se faz conta de nota — se fizesse, a mesma aritmética
// existiria em duas linguagens e um dia elas discordariam sobre o mesmo par.
function blocoVizinhanca(c) {
  const v = c.vizinhanca;
  if (!v || !v.lados?.length) return "";
  const linhas = v.lados.map((lado) => {
    const numeros = lado.identicos
      ? "praticamente idênticos nos critérios"
      : `${lado.gap} ${esc(lado.rotulo)}: ` + lado.criterios.map((x) =>
          `<span class="viz-criterio">${esc(x.nome)}</span> (${esc(x.delta)})`).join(", ");
    return `<li><span class="viz-quem">nº ${lado.posicao}, ${lado.score}/100</span>
              <span class="viz-conta">${numeros}</span></li>`;
  }).join("");
  const ressalvas = (v.ressalvas || []).map(
    (r) => `<p class="viz-ressalva">${esc(r)}</p>`).join("");
  return `
    <section class="vizinhanca">
      <h3>Vizinhança no ranking geral <span>este candidato é o nº ${v.posicao}</span></h3>
      <ul>${linhas}</ul>
      ${ressalvas}
    </section>`;
}



function secao(titulo, itens, classe = "") {
  return itens?.length
    ? `<div class="det-secao"><h3>${titulo}</h3>
         <ul class="${classe}">${itens.map((i) => `<li>${esc(i)}</li>`).join("")}</ul></div>`
    : "";
}

function blocoDecisao(c) {
  const botoes = ["entrevistar", "reserva", "arquivado"].map((d) => `
    <button class="decisao-btn${c.decisao === d ? " ativa" : ""}" data-d="${d}">
      ${ROTULO_DECISAO[d]}
    </button>`).join("");
  return `
    <div class="decisao">
      <h3>Sua decisão</h3>
      <div class="decisao-botoes">
        ${botoes}
        <button class="decisao-btn${!c.decisao || c.decisao === "sem_decisao" ? " ativa" : ""}"
                data-d="sem_decisao">limpar</button>
      </div>
      <textarea id="anotacao" rows="3"
                placeholder="Anotação para você e para o time. Entra no relatório e no CSV."
                aria-label="Anotação">${esc(c.anotacao || "")}</textarea>
      <p class="decisao-estado" id="decisao-estado">A nota é do sistema; a decisão é sua.</p>
    </div>`;
}

function desenharDetalhe() {
  const c = estado.resultados.find((r) => r.candidato_id === estado.selecionado);
  if (!c) return;

  const res = c.resultado || {};
  const contato = c.contato || {};
  const pesos = Object.fromEntries((estado.rubrica?.criterios || []).map((x) => [x.id, x]));
  const linkArquivo = c.tem_arquivo
    ? `<a class="btn-texto" href="/api/vagas/${estado.vagaId}/curriculos/${encodeURIComponent(c.candidato_id)}/arquivo"
          target="_blank" rel="noopener">Abrir currículo original</a>`
    : "";

  const cabeca = `
    <h2 class="det-nome">${esc(c.nome)}</h2>
    <p class="det-contato">${esc(c.arquivo)}</p>`;

  if (c.estagio === "erro") {
    $("detalhe").innerHTML = `${cabeca}
      <p class="erro">Não foi possível avaliar: ${esc(c.erro || "erro desconhecido")}</p>
      <div class="det-acoes">${linkArquivo}</div>
      ${blocoDecisao(c)}`;
    ligarDecisao(c);
    return;
  }

  if (c.estagio === "eliminado") {
    $("detalhe").innerHTML = `${cabeca}
      <p class="det-resumo">Cortado no eliminatório: ${esc(res.motivo || "requisito não atendido")}</p>
      <div class="det-acoes">${linkArquivo}</div>
      ${blocoDecisao(c)}`;
    ligarDecisao(c);
    return;
  }

  // Modo leitura: a evidência é o ponto alto, e cada nota se explica.
  const criterios = (res.criterios || []).map((n) => {
    const meta = pesos[n.criterio_id] || { nome: n.criterio_id, peso: 0 };
    const semEvidencia = /sem evid[êe]ncia/i.test(n.evidencia || "");
    return `
      <div class="criterio">
        <div class="criterio-topo">
          <span class="criterio-nome">${esc(meta.nome)}
            <span class="criterio-peso">peso ${meta.peso}% do total</span>
          </span>
          <span class="criterio-nota">${n.nota}<small>/10</small></span>
        </div>
        <div class="trilho" aria-hidden="true">
          <div class="trilho-preenchido${semEvidencia ? " magra" : ""}"
               style="width:${n.nota * 10}%"></div>
        </div>
        <p class="evidencia${semEvidencia ? " evidencia-ausente" : ""}">${esc(n.evidencia)}</p>
      </div>`;
  }).join("");

  // A posição é a decisão: este aviso muda como se lê cada citação abaixo dele.
  // Depois dos critérios, informaria tarde. Vale para todo OCR, não só o ruim —
  // o trecho citado pode estar torto mesmo quando a extração foi razoável.
  const avisoOcr = c.origem_texto === "ocr"
    ? `<p class="nota-aviso">Este currículo é um PDF escaneado. O texto foi lido por
       OCR e pode conter falhas — os trechos citados abaixo podem estar imprecisos.</p>`
    : "";

  const linhasContato = [
    ["E-mail", contato.email],
    ["Telefone", contato.telefone],
    ["Cidade", contato.cidade],
    ["Arquivo", c.arquivo],
  ].filter(([, v]) => v)
   .map(([r, v]) => `<div><dt>${r}</dt><dd>${esc(v)}</dd></div>`).join("");

  const confianca = c.confianca && c.confianca !== "alta"
    ? `<span class="selo-confianca">confiança ${esc(c.confianca)}</span>` : "";
  const alertas = [
    res.divergencia ? `<p class="nota-aviso">${esc(res.divergencia)}</p>` : "",
    res.criterios_sem_resposta?.length
      ? `<p class="nota-aviso">Sem avaliação para: ${esc(res.criterios_sem_resposta.join(", "))} — contaram como zero.</p>`
      : "",
    c.avisos?.length
      ? `<p class="nota-aviso">Na leitura do arquivo: ${esc(c.avisos.join("; "))}</p>` : "",
  ].join("");

  $("detalhe").innerHTML = `
    <div class="det-cabeca">
      <h2 class="det-nome">${esc(nomeDe(c))}${confianca}</h2>
      <span class="det-nota-final">${Math.round(c.score_final)}<small>de 100</small></span>
    </div>
    <dl class="det-contato">${linhasContato ||
      "<div><dd>contato não identificado no currículo</dd></div>"}</dl>
    <div class="det-acoes">${linkArquivo}</div>
    <p class="det-resumo">${esc(res.resumo || "")}</p>
    ${avisoOcr}
    ${criterios}
    ${secao("Pontos fortes", res.pontos_fortes)}
    ${secao("Atenção", res.red_flags, "lista-flags")}
    ${alertas}
    ${blocoVizinhanca(c)}
    ${blocoDecisao(c)}`;
  ligarDecisao(c);
}

function ligarDecisao(c) {
  const painel = $("detalhe");
  const estadoEl = () => $("decisao-estado");

  const salvar = async (decisao, anotacao) => {
    try {
      await enviarJson(
        `/api/vagas/${estado.vagaId}/candidatos/${encodeURIComponent(c.candidato_id)}/decisao`,
        "PUT", { decisao, anotacao }
      );
      c.decisao = decisao;
      c.anotacao = anotacao;
      if (estadoEl()) estadoEl().textContent = "Salvo.";
      desenharRanking();
    } catch (e) {
      if (estadoEl()) estadoEl().textContent = `Não salvou: ${e.message}`;
      brinde(e.message, true);
    }
  };

  $$(".decisao-btn", painel).forEach((b) =>
    b.addEventListener("click", () => {
      $$(".decisao-btn", painel).forEach((x) => x.classList.remove("ativa"));
      b.classList.add("ativa");
      salvar(b.dataset.d, $("anotacao")?.value || "");
    }));

  const campo = $("anotacao");
  if (campo) {
    let atraso = null;
    campo.addEventListener("input", () => {
      clearTimeout(atraso);
      if (estadoEl()) estadoEl().textContent = "Salvando…";
      atraso = setTimeout(() => salvar(c.decisao || "sem_decisao", campo.value), 900);
    });
  }
}

// ---------- vagas ----------

$("btn-inicio").addEventListener("click", abrirListaDeVagas);
$("btn-vagas").addEventListener("click", abrirListaDeVagas);
$("ver-arquivadas").addEventListener("change", abrirListaDeVagas);

async function abrirListaDeVagas() {
  pararTimer();
  mostrar("passo-lista");
  const arquivadas = $("ver-arquivadas").checked;
  const vagas = await api(`/api/vagas?incluir_arquivadas=${arquivadas}`);

  if (!vagas.length) {
    $("painel-sub").textContent = "";
    // Estado vazio como convite escrito: quem chega aqui nunca usou o produto.
    $("lista-vagas").innerHTML = `
      <div class="convite">
        <h2>Comece pela primeira vaga</h2>
        <p>São três passos, e o segundo é o que importa.</p>
        <ol>
          <li>Você cola a descrição da vaga.</li>
          <li><strong>O sistema propõe os critérios e você corrige</strong> — pesos,
              textos, o que é eliminatório. Nada é avaliado antes de você aprovar.</li>
          <li>Você joga os currículos dentro e recebe um ranking em que cada nota
              vem com o trecho do currículo que a sustenta.</li>
        </ol>
        <button class="btn-principal" id="btn-primeira">Criar a primeira vaga</button>
      </div>`;
    $("btn-primeira").addEventListener("click", novaVaga);
    return;
  }

  const emAndamento = vagas.filter((v) => !v.arquivada).length;
  $("painel-sub").textContent = emAndamento
    ? `${plural(emAndamento, "vaga em andamento", "vagas em andamento")}`
    : "nenhuma vaga em andamento";

  const linhas = vagas.map((v) => {
    // Sem gatilho de execução, esta lista é onde ele confere se terminou.
    // O mesmo número do painel, do mesmo campo: `com_veredito`. Usar `avaliados`
    // aqui mostraria 23/35 no card e 26 de 35 dentro da vaga, com o eliminado e
    // o ilegível sumindo no caminho — a divergência de novo, só que mais sutil.
    const feitos = v.com_veredito ?? v.avaliados;
    const estado = v.arquivada ? "arquivada"
      : (feitos != null && v.curriculos
          ? `${feitos}/${v.curriculos} avaliados`
          : (ESTADO_VAGA[v.status] || v.status));
    return `
      <button class="vaga-linha" data-vaga="${esc(v.id)}">
        <span>
          <span class="vaga-titulo">${esc(v.titulo)}</span>
          <span class="vaga-estado">${esc(estado)}</span>
        </span>
        <span class="vaga-num${v.curriculos ? "" : " apagado"}">${v.curriculos}</span>
        <span class="vaga-num${v.chamar ? " destaque" : " apagado"}">${v.chamar}</span>
        <span class="vaga-num${v.entrevistar ? "" : " apagado"}">${v.entrevistar}</span>
      </button>`;
  }).join("");

  $("lista-vagas").innerHTML = `
    <div class="vagas-cabecalho" aria-hidden="true">
      <span>Vaga</span><span>Currículos</span><span>Para chamar</span><span>Marcados</span>
    </div>
    <div class="vagas-tabela">${linhas}</div>`;
}

$("lista-vagas").addEventListener("click", async (ev) => {
  const abrir = ev.target.closest("[data-vaga]");
  if (abrir) await abrirVaga(abrir.dataset.vaga);
});

$("btn-nova-vaga").addEventListener("click", novaVaga);

async function abrirVaga(vagaId) {
  estado.vagaId = vagaId;
  estado.selecionado = null;
  estado.ultimoFeitos = -1;
  estado.pedirReavaliacao = false;
  const vaga = await api(`/api/vagas/${vagaId}`);
  estado.rubrica = vaga.rubrica;
  estado.vagaTitulo = vaga.titulo;
  estado.vagaArquivada = vaga.arquivada;
  $("topo-vaga").textContent = vaga.titulo;
  $("btn-arquivar-vaga").textContent = vaga.arquivada ? "Reabrir vaga" : "Arquivar vaga";

  // Não há mais estado de execução para consultar: vaga com currículo abre no
  // pódio, e o painel conta o que o Claude já registrou.
  if (vaga.rubrica_ok && vaga.curriculos) {
    mostrar("passo-resultados");
    await carregarResultados();
    acompanhar();
  } else if (vaga.rubrica_ok) {
    $("contagem-curriculos").textContent =
      plural(vaga.curriculos, "currículo na vaga", "currículos na vaga");
    desenharProximoPasso(vaga.curriculos);
    mostrar("passo-upload");
  } else if (vaga.rubrica) {
    desenharRubrica();
    mostrar("passo-rubrica");
  } else {
    novaVaga();
  }
}

$("btn-arquivar-vaga").addEventListener("click", async () => {
  const arquivando = !estado.vagaArquivada;
  try {
    await api(`/api/vagas/${estado.vagaId}/arquivar?arquivada=${arquivando}`,
              { method: "POST" });
    brinde(arquivando ? "Vaga arquivada." : "Vaga reaberta.");
    await abrirListaDeVagas();
  } catch (e) { brinde(e.message, true); }
});

$("btn-apagar-vaga").addEventListener("click", async () => {
  if (!confirm(
    `Apagar a vaga "${estado.vagaTitulo}"?\n\n` +
    "As avaliações somem. Os currículos continuam na base e podem ser usados em " +
    "outras vagas — para apagar os dados de um candidato, use a aba Dados."
  )) return;
  try {
    await api(`/api/vagas/${estado.vagaId}`, { method: "DELETE" });
    brinde("Vaga apagada.");
    await abrirListaDeVagas();
  } catch (e) { brinde(e.message, true); }
});

function novaVaga() {
  pararTimer();
  Object.assign(estado, {
    vagaId: null, rubrica: null, resultados: [], selecionado: null,
    filtro: "todos", busca: "", ultimoFeitos: -1, pedirReavaliacao: false,
  });
  $("in-titulo").value = "";
  $("in-descricao").value = "";
  $("conta-descricao").textContent = "0";
  $("topo-vaga").textContent = "";
  $("fila-upload").hidden = true;
  $("resumo-corrida").hidden = true;
  $("painel-status").hidden = true;
  $("detalhe").innerHTML = `<p class="detalhe-vazio">Escolha um candidato para ver as notas e a evidência de cada uma.</p>`;
  mostrar("passo-vaga");
}

$("btn-nova").addEventListener("click", novaVaga);

// ---------- configurações ----------

$("btn-config").addEventListener("click", abrirConfiguracoes);

async function abrirConfiguracoes() {
  pararTimer();
  mostrar("passo-config");
  avisar("erro-config", ""); avisar("ok-config", "");

  const cfg = await api("/api/org/configuracoes");
  $("cfg-nome").value = cfg.nome;
  $("cfg-retencao").value = cfg.retencao_dias;

  await carregarConector();
  if (estado.usuario?.papel === "admin") await carregarUsuarios();
}

$("btn-salvar-config").addEventListener("click", async () => {
  avisar("erro-config", ""); avisar("ok-config", "");
  try {
    await comBotao($("btn-salvar-config"), "Salvando…", async () => {
      await enviarJson("/api/org/configuracoes", "PUT", {
        nome: $("cfg-nome").value.trim(),
        retencao_dias: parseInt($("cfg-retencao").value, 10),
      });
      avisar("ok-config", "Configurações salvas.");
      await abrirConfiguracoes();
    });
  } catch (e) { avisar("erro-config", e.message); }
});

async function carregarUsuarios() {
  const usuarios = await api("/api/org/usuarios");
  $("lista-usuarios").innerHTML = usuarios.map((u) => `
    <div class="linha-dado">
      <span>${esc(u.nome)}
        <span class="linha-dado-meta">${esc(u.email)}</span>
        <span class="linha-dado-meta">${u.papel === "admin" ? "administradora" : "recrutador"}${
          u.ultimo_acesso ? `, último acesso em ${esc(u.ultimo_acesso.slice(0, 10).split("-").reverse().join("/"))}` : ", nunca acessou"}</span>
      </span>
      <span class="linha-dado-acoes">
        ${u.id === estado.usuario.id ? "<span class='linha-dado-meta'>você</span>"
          : `<button class="btn-remover" data-usuario="${esc(u.id)}" data-nome="${esc(u.nome)}">Remover</button>`}
      </span>
    </div>`).join("");
}

$("lista-usuarios").addEventListener("click", async (ev) => {
  const alvo = ev.target.closest("[data-usuario]");
  if (!alvo) return;
  if (!confirm(`Remover ${alvo.dataset.nome}? A pessoa perde o acesso imediatamente.`)) return;
  try {
    await api(`/api/org/usuarios/${alvo.dataset.usuario}`, { method: "DELETE" });
    await carregarUsuarios();
    brinde("Acesso removido.");
  } catch (e) { brinde(e.message, true); }
});

// Os dois painéis abaixo são <form> de verdade, e não div com botão. Isso
// compra duas coisas de uma vez: o `required` do HTML passa a ser vinculante
// sozinho — o navegador barra o envio e mostra a mensagem no idioma do
// usuário, sem código nosso — e o Enter envia, que é o que qualquer pessoa
// tenta primeiro num campo de senha.

$("form-usuario").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  avisar("erro-usuario", "");
  try {
    await enviarJson("/api/org/usuarios", "POST", {
      nome: $("nu-nome").value.trim(),
      email: $("nu-email").value.trim(),
      senha: $("nu-senha").value,
      papel: $("nu-papel").value,
    });
    ["nu-nome", "nu-email", "nu-senha"].forEach((id) => { $(id).value = ""; });
    await carregarUsuarios();
    brinde("Pessoa adicionada. Peça para ela trocar a senha no primeiro acesso.");
  } catch (e) { avisar("erro-usuario", e.message); }
});

// ---------- conector do Claude ----------

async function carregarConector() {
  const url = `${window.location.origin}/mcp`;
  $("mcp-url").value = url;
  // O claude.ai roda na nuvem: um endereço local não é alcançável de lá.
  $("mcp-aviso-local").hidden = !/^https?:\/\/(127\.0\.0\.1|localhost|\[::1\])/i
    .test(window.location.origin);

  const tokens = await api("/api/mcp/tokens");
  $("lista-tokens").innerHTML = tokens.length
    ? tokens.map((t) => `
      <div class="linha-dado">
        <span>${esc(t.rotulo || "sem rótulo")}
          <span class="linha-dado-meta" style="display:block">
            criado em ${esc((t.criado_em || "").slice(0, 10))}${t.usado_em
              ? " · usado pela última vez em " + esc(t.usado_em.slice(0, 10))
              : " · nunca usado"}
          </span>
        </span>
        <span class="linha-dado-acoes">
          <button class="btn-remover" data-token="${esc(t.token_hash)}">Revogar</button>
        </span>
      </div>`).join("")
    : `<p class="vazio">Nenhum token gerado.</p>`;
}

$("btn-copiar-url").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("mcp-url").value);
    brinde("Endereço copiado.");
  } catch {
    $("mcp-url").select();
    brinde("Selecionado — use Ctrl+C para copiar.");
  }
});

$("btn-gerar-token").addEventListener("click", async () => {
  avisar("erro-mcp", "");
  try {
    const r = await enviarJson("/api/mcp/tokens", "POST",
                               { rotulo: $("mcp-rotulo").value.trim() });
    $("mcp-rotulo").value = "";
    const painel = $("mcp-token-novo");
    painel.hidden = false;
    painel.innerHTML = `
      <div class="token-revelado">
        <p><strong>Copie agora.</strong> ${esc(r.aviso)}</p>
        <code>${esc(r.token)}</code>
        <p class="dica">No Claude Desktop, coloque em
          <code>env.TRIAGEM_MCP_TOKEN</code>. O passo a passo está no README.</p>
      </div>`;
    await carregarConector();
  } catch (e) { avisar("erro-mcp", e.message); }
});

$("lista-tokens").addEventListener("click", async (ev) => {
  const alvo = ev.target.closest("[data-token]");
  if (!alvo) return;
  if (!confirm("Revogar este token? Quem estiver usando perde o acesso na hora.")) return;
  try {
    await api(`/api/mcp/tokens/${alvo.dataset.token}`, { method: "DELETE" });
    await carregarConector();
    brinde("Token revogado.");
  } catch (e) { brinde(e.message, true); }
});

$("btn-desconectar-mcp").addEventListener("click", async () => {
  if (!confirm(
    "Desconectar todos os conectores?\n\n" +
    "O Claude perde o acesso a esta conta e você precisará autorizar de novo. " +
    "Os tokens gerados para uso local continuam valendo — revogue-os um a um."
  )) return;
  try {
    await api("/api/mcp/desconectar", { method: "POST" });
    brinde("Conectores desconectados.");
  } catch (e) { brinde(e.message, true); }
});

$("form-senha").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  avisar("erro-senha", ""); avisar("ok-senha", "");
  try {
    await enviarJson("/api/auth/senha", "POST", {
      senha_atual: $("senha-atual").value,
      senha_nova: $("senha-nova").value,
    });
    $("senha-atual").value = ""; $("senha-nova").value = "";
    avisar("ok-senha", "Senha trocada. As outras sessões foram encerradas.");
  } catch (e) { avisar("erro-senha", e.message); }
});

// ---------- LGPD ----------

$("btn-lgpd").addEventListener("click", abrirLgpd);

async function abrirLgpd() {
  pararTimer();
  mostrar("passo-lgpd");
  $("lgpd-achados").innerHTML = "";

  const r = await api("/api/lgpd/resumo");
  $("lgpd-resumo").innerHTML = `
    <div><span class="metrica-valor">${r.curriculos_guardados}</span>
         <span class="metrica-rotulo">currículos guardados</span></div>
    <div><span class="metrica-valor">${r.retencao_dias}</span>
         <span class="metrica-rotulo">dias de retenção</span></div>
    <div><span class="metrica-valor">${r.a_expurgar}</span>
         <span class="metrica-rotulo">a expurgar</span></div>`;

  if (estado.usuario?.papel === "admin") await carregarAuditoria();
}

$("btn-lgpd-buscar").addEventListener("click", buscarTitular);
$("lgpd-busca").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") buscarTitular();
});

async function buscarTitular() {
  const termo = $("lgpd-busca").value.trim();
  if (termo.length < 3) return brinde("Digite pelo menos 3 caracteres.", true);
  try {
    const achados = await api(`/api/lgpd/buscar?termo=${encodeURIComponent(termo)}`);
    $("lgpd-achados").innerHTML = achados.length
      ? achados.map((a) => `
        <div class="linha-dado">
          <span>${esc(a.nome)}
            <span class="linha-dado-meta" style="display:block">
              ${esc(a.email || "sem e-mail")} · ${esc(a.arquivo)} · recebido em ${esc(a.criado_em.slice(0, 10))}
            </span>
          </span>
          <span class="linha-dado-acoes">
            <a class="btn-texto" href="/api/lgpd/candidato/${esc(a.candidato_id)}">Exportar</a>
            <button class="btn-remover" data-apagar-cand="${esc(a.candidato_id)}"
                    data-nome="${esc(a.nome)}">Apagar</button>
          </span>
        </div>`).join("")
      : `<p class="vazio">Ninguém encontrado com esse termo.</p>`;
  } catch (e) { brinde(e.message, true); }
}

$("lgpd-achados").addEventListener("click", async (ev) => {
  const alvo = ev.target.closest("[data-apagar-cand]");
  if (!alvo) return;
  if (!confirm(
    `Apagar todos os dados de ${alvo.dataset.nome}?\n\n` +
    "O currículo, o arquivo original e todas as avaliações somem de todas as " +
    "vagas. Isso não tem volta. O registro de que você apagou fica na auditoria."
  )) return;
  try {
    await api(`/api/lgpd/candidato/${alvo.dataset.apagarCand}`, { method: "DELETE" });
    brinde("Dados apagados.");
    await buscarTitular();
    await abrirLgpd();
  } catch (e) { brinde(e.message, true); }
});

async function carregarAuditoria() {
  const registros = await api("/api/lgpd/auditoria?limite=100");
  $("lista-auditoria").innerHTML = registros.length
    ? registros.map((a) => `
      <div class="linha-dado">
        <span>${esc(a.acao)}
          <span class="linha-dado-meta" style="display:block">
            ${esc(a.usuario_nome || "sistema")}${a.entidade_id ? " · " + esc(a.entidade_id) : ""}
          </span>
        </span>
        <span class="linha-dado-meta">${esc(a.em.slice(0, 16).replace("T", " "))}</span>
      </div>`).join("")
    : `<p class="vazio">Nada registrado ainda.</p>`;
}

// ---------- partida ----------

iniciar();
