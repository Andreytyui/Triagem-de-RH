"use strict";
// Botão de impressão do relatório. Fica em arquivo próprio porque a política de
// segurança da página (CSP) bloqueia script embutido no HTML.
document.addEventListener("DOMContentLoaded", () => {
  const botao = document.getElementById("imprimir");
  if (botao) botao.addEventListener("click", () => window.print());
});
