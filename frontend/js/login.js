/**
 * Controlador da tela de login.
 *
 * Se já existir sessão válida, pula direto para o destino — evita que
 * quem já está logado veja a tela de login ao abrir a URL de novo.
 */

import { aguardarEstadoInicial, entrar, mensagemDeErro } from './auth.js';

const el = (id) => document.getElementById(id);

function destino() {
  const parametros = new URLSearchParams(window.location.search);
  const redirect = parametros.get('redirect');
  // Só aceita um caminho relativo dentro do próprio app — nunca segue
  // uma URL completa vinda da query string, para não virar um redirect
  // aberto controlável por quem monta o link.
  if (redirect && redirect.startsWith('/') && !redirect.startsWith('//')) {
    return `.${redirect}`;
  }
  return './index.html';
}

function mostrarErro(mensagem) {
  const elemento = el('erroLogin');
  elemento.textContent = mensagem;
  elemento.classList.toggle('oculto', !mensagem);
}

async function aoSubmeter(evento) {
  evento.preventDefault();
  mostrarErro('');

  const email = el('email').value.trim();
  const senha = el('senha').value;
  if (!email || !senha) {
    mostrarErro('Preencha e-mail e senha.');
    return;
  }

  const botao = el('btnEntrar');
  botao.disabled = true;
  botao.textContent = 'ENTRANDO...';

  try {
    await entrar(email, senha);
    window.location.href = destino();
  } catch (erro) {
    mostrarErro(mensagemDeErro(erro));
    botao.disabled = false;
    botao.textContent = 'ENTRAR';
  }
}

async function iniciar() {
  document.getElementById('formLogin').addEventListener('submit', aoSubmeter);

  const usuario = await aguardarEstadoInicial();
  if (usuario) {
    window.location.href = destino();
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', iniciar);
} else {
  iniciar();
}
