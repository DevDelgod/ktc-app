/**
 * Controlador da tela de listagem e criação de competições.
 */

import { apiCompeticoes, ErroDaApi } from './api.js';
import { exigirSessao, ligarBotaoSair, mostrarUsuario } from './auth-guard.js';
import { criarCompeticao } from './competitions-firebase.js';

const el = (id) => document.getElementById(id);
const mostrar = (elemento, visivel) => elemento?.classList.toggle('oculto', !visivel);

const ROTULO_STATUS = {
  planejada: 'Planejada',
  em_andamento: 'Em andamento',
  pausada: 'Pausada',
  concluida: 'Concluída',
};

function dataBr(iso) {
  if (!iso) return '—';
  const [ano, mes, dia] = iso.split('-');
  return `${dia}/${mes}/${ano}`;
}

function mostrarErro(mensagem) {
  const aviso = el('avisoConexao');
  if (!mensagem) {
    mostrar(aviso, false);
    return;
  }
  aviso.textContent = mensagem;
  mostrar(aviso, true);
}

function tratarErro(erro) {
  console.error(erro);
  if (erro instanceof ErroDaApi && erro.status === 0) {
    mostrarErro('Servidor de análise indisponível. Verifique se o backend está rodando.');
    return;
  }
  if (erro instanceof ErroDaApi && erro.status === 401) {
    window.location.href = './login.html';
    return;
  }
  mostrarErro(erro.message || 'Erro ao carregar competições.');
}

/** Estrutura fixa da competição: 12 séries de 6 flechas (72 no total). */
const MAX_SERIES = 12;

function cartaoCompeticao(c) {
  const div = document.createElement('div');
  div.className = 'cartao-competicao';

  const concluida = c.status === 'concluida';
  const temPlacar = (c.quantidade_series || 0) > 0;

  const linhaPlacar = temPlacar
    ? `<div class="cartao-competicao-score">${c.total} <span style="font-size:12px; font-weight:normal; color:var(--text-sub)">· ${c.quantidade_series}/${MAX_SERIES} séries</span></div>`
    : '';

  const linhaRelatorio = concluida
    ? '<div style="margin-top:8px; font-size:12px; font-weight:bold; color:var(--azul)">📊 Ver relatório →</div>'
    : '';

  div.innerHTML = `
    <span class="selo-status ${c.status}">${ROTULO_STATUS[c.status] || c.status}</span>
    <div class="cartao-competicao-nome">${c.nome || 'Sem nome'}</div>
    <div class="cartao-competicao-meta">
      ${c.atleta || '—'}<br>
      ${dataBr(c.data)}${c.local ? ' · ' + c.local : ''}<br>
      ${c.categoria || ''}${c.categoria && c.modalidade ? ' · ' : ''}${c.modalidade || ''}
    </div>
    ${linhaPlacar}
    ${linhaRelatorio}`;

  div.addEventListener('click', () => {
    // Competição concluída abre direto no relatório (ver competition.js).
    window.location.href = `./competition.html?id=${encodeURIComponent(c.id)}`;
  });
  return div;
}

async function carregarLista() {
  mostrarErro(null);
  const dados = await apiCompeticoes.listar();
  const container = el('listaCompeticoes');
  container.innerHTML = '';

  mostrar(el('listaVazia'), dados.quantidade === 0);
  for (const competicao of dados.competicoes) {
    container.appendChild(cartaoCompeticao(competicao));
  }
}

async function aoCriarCompeticao(evento) {
  evento.preventDefault();
  const botao = el('btnCriarCompeticao');
  botao.disabled = true;
  botao.textContent = 'Criando...';

  try {
    const id = await criarCompeticao({
      nome: el('fcNome').value.trim(),
      atleta: el('fcAtleta').value.trim(),
      data: el('fcData').value,
      local: el('fcLocal').value.trim(),
      categoria: el('fcCategoria').value.trim(),
      modalidade: el('fcModalidade').value.trim(),
      distancia: el('fcDistancia').value,
      tipoAlvo: el('fcTipoAlvo').value,
    });
    await apiCompeticoes.invalidarCache().catch(() => {});
    window.location.href = `./competition.html?id=${encodeURIComponent(id)}`;
  } catch (erro) {
    console.error(erro);
    window.alert(erro.message || 'Erro ao criar a competição.');
    botao.disabled = false;
    botao.textContent = 'Criar competição';
  }
}

function ligarEventos() {
  el('btnTema').addEventListener('click', () =>
    document.body.classList.toggle('dark-mode'),
  );

  el('btnNovaCompeticao').addEventListener('click', () => {
    mostrar(el('formNovaCompeticao'), true);
    mostrar(el('btnNovaCompeticao'), false);
    el('fcData').value = new Date().toISOString().slice(0, 10);
  });

  el('btnCancelarNova').addEventListener('click', () => {
    mostrar(el('formNovaCompeticao'), false);
    mostrar(el('btnNovaCompeticao'), true);
    el('formNovaCompeticao').reset();
  });

  el('formNovaCompeticao').addEventListener('submit', aoCriarCompeticao);
}

async function iniciar() {
  const usuario = await exigirSessao();
  mostrarUsuario(el('usuarioLogado'), usuario);
  ligarBotaoSair(el('btnSair'));
  ligarEventos();

  mostrar(el('listaCarregando'), true);
  try {
    await carregarLista();
  } catch (erro) {
    tratarErro(erro);
  } finally {
    mostrar(el('listaCarregando'), false);
    mostrar(el('conteudo'), true);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', iniciar);
} else {
  iniciar();
}
