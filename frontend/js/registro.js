/**
 * Controlador da tela de registro.
 *
 * Substitui as 11 funções que o `script.js` original exportava para
 * `window` só para que os `onclick` inline do HTML as enxergassem.
 * Aqui os eventos são ligados por `addEventListener`, o HTML fica livre
 * de JavaScript e o escopo do módulo volta a ser isolado.
 *
 * O fluxo do usuário é o mesmo de sempre: configurar a sessão, marcar
 * as flechas no alvo, digitar os pontos, finalizar a série, repetir.
 */

import { api } from './api.js';
import { exigirSessao, ligarBotaoSair, mostrarUsuario } from './auth-guard.js';
import { AlvoCanvas } from './canvas.js';
import { calcularTotal, excluirSerie, salvarAlvo, salvarPontuacao } from './firebase.js';
import { TECLAS, conferir, somar } from './scoring.js';
import { geometriaPorNome, VALOR_TRIPLO } from './targets.js';
import { Treino } from './training.js';

const CHAVE_TEMA = 'ktc-tema';

const el = (id) => document.getElementById(id);

const dom = {
  tema: el('btnTema'),
  setup: el('setup-container'),
  treinoContainer: el('training-container'),
  miniHeader: el('mini-header'),
  headerId: el('headerIdTreino'),
  headerAtleta: el('headerAtleta'),
  headerData: el('headerDataTreino'),

  idTreino: el('idTreino'),
  atleta: el('atleta'),
  dataTreino: el('dataTreino'),
  tempo: el('tempo'),
  serie: el('serie'),
  clima: el('clima'),
  distancia: el('distancia'),
  tipoAlvo: el('tipoAlvo'),
  qtdSeries: el('qtdSeries'),
  qtdFlechas: el('qtdFlechas'),
  vVento: el('v_vento'),
  dVento: el('d_vento'),
  comecar: el('btnStartTraining'),

  moduloAlvo: el('moduloAlvo'),
  moduloScore: el('moduloScore'),
  zoom: el('zoomRange'),
  canvas: el('alvo'),
  desfazerAlvo: el('btnDesfazerAlvo'),
  limparAlvo: el('btnLimparAlvo'),
  contadorAlvo: el('contadorAlvo'),
  enviarAlvo: el('btnEnviarAlvo'),

  caixas: el('containerFlechasScore'),
  numpad: el('numpad'),
  scoreTotal: el('scoreTotal'),
  desfazerScore: el('btnDesfazerScore'),
  limparScore: el('btnLimparScore'),
  contadorScore: el('contadorScore'),
  enviarScore: el('btnEnviarScore'),

  listaSeries: el('listaSeries'),
  status: el('status'),
};

const treino = new Treino();
const alvo = new AlvoCanvas(dom.canvas, { aoMarcar: () => atualizarAlvoUI() });

// ---------------------------------------------------------------- tema

function aplicarTema(escuro) {
  document.body.classList.toggle('dark-mode', escuro);
  try {
    localStorage.setItem(CHAVE_TEMA, escuro ? 'escuro' : 'claro');
  } catch {
    // Navegação privada pode bloquear o storage; o tema só não persiste.
  }
}

function restaurarTema() {
  let salvo = null;
  try {
    salvo = localStorage.getItem(CHAVE_TEMA);
  } catch {
    salvo = null;
  }
  const prefereEscuro = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
  aplicarTema(salvo ? salvo === 'escuro' : Boolean(prefereEscuro));
}

// -------------------------------------------------------------- estado

/** Copia o formulário para o objeto de estado. */
function lerFormulario() {
  treino.idTreino = dom.idTreino.value.trim();
  treino.atleta = dom.atleta.value.trim();
  treino.dataTreino = dom.dataTreino.value;
  treino.tempo = dom.tempo.value;
  treino.serie = parseInt(dom.serie.value, 10);
  treino.clima = dom.clima.value;
  treino.distancia = dom.distancia.value;
  treino.valorSelectAlvo = dom.tipoAlvo.value;
  treino.vVento = dom.vVento.value;
  treino.dVento = dom.dVento.value;
  treino.definirFormato({
    seriesPorRodada: dom.qtdSeries.value,
    flechasPorSerie: dom.qtdFlechas.value,
  });
}

/** Escreve o estado de volta no formulário. */
function escreverFormulario() {
  dom.idTreino.value = treino.idTreino;
  dom.atleta.value = treino.atleta;
  dom.dataTreino.value = treino.dataTreino;
  dom.tempo.value = treino.tempo;
  dom.serie.value = String(treino.serie);
  dom.qtdSeries.value = String(treino.seriesPorRodada);
  dom.qtdFlechas.value = String(treino.flechasPorSerie);
}

function definirStatus(texto) {
  dom.status.textContent = texto;
}

// ------------------------------------------------------- tipo de alvo

/**
 * Mostra o seletor de alvo apenas nos 18m.
 *
 * O código original atribuía ao `<select>` o valor `"outdoor_122"`, que
 * não existe entre as opções — o navegador zerava o campo e, ao voltar
 * para 18m, o seletor aparecia em branco. Aqui o seletor é escondido e
 * o valor válido é mantido, sem inventar opção inexistente.
 */
function sincronizarTipoDeAlvo() {
  const indoor = dom.distancia.value === '18m';
  dom.tipoAlvo.classList.toggle('oculto', !indoor);
  if (!indoor) {
    dom.tipoAlvo.value = 'indoor_18_single';
  }
  treino.distancia = dom.distancia.value;
  treino.valorSelectAlvo = indoor ? dom.tipoAlvo.value : '';
  alvo.definirGeometria(geometriaAtual());
}

function geometriaAtual() {
  const indoor = dom.distancia.value === '18m';
  const triplo = indoor && dom.tipoAlvo.value === VALOR_TRIPLO;
  return geometriaPorNome(triplo ? 'Alvo Triplo' : 'Alvo Único');
}

// ---------------------------------------------------------------- alvo

function atualizarAlvoUI() {
  treino.flechas = alvo.flechas;
  dom.contadorAlvo.textContent =
    `Flechas no Alvo: ${treino.flechas.length} / ${treino.flechasPorSerie}`;
  dom.enviarAlvo.classList.toggle('oculto', !treino.alvoCompleto);
}

// ----------------------------------------------------------- pontuação

function montarNumpad() {
  dom.numpad.innerHTML = '';
  for (const tecla of TECLAS) {
    const botao = document.createElement('button');
    botao.type = 'button';
    botao.className = `num-btn ${tecla.classe}`;
    botao.textContent = tecla.valor;
    botao.addEventListener('click', () => adicionarPonto(tecla.valor));
    dom.numpad.appendChild(botao);
  }
}

function adicionarPonto(valor) {
  if (treino.pontos.length >= treino.flechasPorSerie) return;
  treino.pontos.push(valor);
  atualizarScoreUI();
}

function atualizarScoreUI() {
  dom.caixas.innerHTML = '';
  const conferencia = conferir(treino.pontos, treino.flechas, geometriaAtual());

  for (let i = 0; i < treino.flechasPorSerie; i += 1) {
    const caixa = document.createElement('div');
    caixa.className = 'ponto-box';

    const item = conferencia[i];
    if (item) {
      caixa.classList.add('preenchido');
      caixa.textContent = item.rotulo;
      // Divergência entre o que foi digitado e o anel onde a flecha
      // caiu. Apenas sinaliza — o valor digitado não é alterado.
      if (item.confere === false) {
        caixa.classList.add('divergente');
        caixa.title = `Marcado no anel ${item.sugerido}`;
        const dica = document.createElement('span');
        dica.className = 'sugestao';
        dica.textContent = `alvo: ${item.sugerido}`;
        caixa.appendChild(dica);
      }
    } else {
      caixa.textContent = '-';
    }
    dom.caixas.appendChild(caixa);
  }

  dom.scoreTotal.textContent = `Total: ${somar(treino.pontos)}`;
  dom.contadorScore.textContent =
    `Pontos Inseridos: ${treino.pontos.length} / ${treino.flechasPorSerie}`;
  dom.enviarScore.classList.toggle('oculto', !treino.pontuacaoCompleta);
}

// ------------------------------------------------------------ histórico

function atualizarListaLateral() {
  dom.listaSeries.innerHTML = '';

  if (treino.seriesEnviadas.size === 0) {
    const vazio = document.createElement('p');
    vazio.className = 'historico-vazio';
    vazio.textContent = 'Nenhuma série enviada nesta sessão.';
    dom.listaSeries.appendChild(vazio);
    return;
  }

  for (const registro of treino.seriesEnviadas.values()) {
    const item = document.createElement('div');
    item.className = 'serie-item';

    const revisar = document.createElement('button');
    revisar.type = 'button';
    revisar.className = 'btn-revisar';
    revisar.textContent = `✔️ ${registro.chave} · ${registro.total}`;
    revisar.title = 'Abrir a análise deste treino';
    revisar.addEventListener('click', () => {
      window.location.href = `./dashboard.html?treino=${encodeURIComponent(treino.idTreino)}`;
    });

    const excluir = document.createElement('button');
    excluir.type = 'button';
    excluir.className = 'btn-del-mini';
    excluir.textContent = 'X';
    excluir.title = 'Excluir esta série do banco';
    excluir.addEventListener('click', () => removerSerie(registro));

    item.append(revisar, excluir);
    dom.listaSeries.appendChild(item);
  }
}

async function removerSerie(registro) {
  if (!window.confirm(`Excluir a série ${registro.chave} do banco de dados?`)) return;

  definirStatus('Excluindo do Firebase...');
  try {
    await excluirSerie(treino.idTreino, registro.tempo, registro.serie, registro.flechas);
    treino.removerEnvio(registro.chave);
    atualizarListaLateral();
    definirStatus(`Série ${registro.chave} excluída.`);
    api.invalidarCache().catch(() => {});
  } catch (erro) {
    console.error(erro);
    definirStatus('Erro ao excluir do Firebase.');
    window.alert(`Não foi possível excluir: ${erro.message}`);
  }
}

// ---------------------------------------------------------------- fluxo

function validarAtleta() {
  const valido = dom.atleta.value.trim() !== '';
  dom.atleta.classList.toggle('campo-invalido', !valido);
  if (!valido) {
    dom.atleta.focus();
    window.alert('Informe o nome do atleta antes de salvar.');
  }
  return valido;
}

function iniciarTreino() {
  lerFormulario();

  const faltando = treino.validarInicio();
  if (faltando.length > 0) {
    window.alert(`Preencha ${faltando.join(' e ')} antes de começar.`);
    return;
  }

  treino.iniciado = true;
  dom.setup.classList.add('oculto');
  dom.miniHeader.classList.remove('oculto');
  dom.treinoContainer.classList.remove('oculto');
  dom.moduloAlvo.classList.remove('oculto');
  dom.moduloScore.classList.add('oculto');

  dom.headerId.textContent = `ID: ${treino.idTreino}`;
  dom.headerAtleta.textContent = `Atleta: ${treino.atleta}`;
  dom.headerData.textContent = `Data: ${treino.dataTreino}`;

  alvo.dimensionar();
  alvo.definirLimite(treino.flechasPorSerie);
  alvo.definirGeometria(geometriaAtual());

  atualizarAlvoUI();
  atualizarScoreUI();
  atualizarListaLateral();

  definirStatus('Treino iniciado. Marque o alvo para começar.');
  dom.moduloAlvo.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function enviarAlvo() {
  if (!validarAtleta()) return;
  if (!treino.alvoCompleto) {
    window.alert(`Marque as ${treino.flechasPorSerie} flechas antes de confirmar.`);
    return;
  }

  dom.enviarAlvo.disabled = true;
  definirStatus('Salvando o alvo no Firebase...');

  try {
    lerFormulario();
    treino.flechas = alvo.flechas;
    const docId = await salvarAlvo(treino.sessao, treino.flechas);

    definirStatus(`${docId} salvo. Agora insira a pontuação.`);
    dom.moduloAlvo.classList.add('oculto');
    dom.moduloScore.classList.remove('oculto');
    treino.pontos = [];
    atualizarScoreUI();
  } catch (erro) {
    console.error(erro);
    definirStatus(erro.message);
    window.alert(erro.message);
  } finally {
    dom.enviarAlvo.disabled = false;
  }
}

async function enviarPontuacao() {
  if (!validarAtleta()) return;
  if (!treino.pontuacaoCompleta) {
    window.alert(`Insira os ${treino.flechasPorSerie} pontos antes de finalizar.`);
    return;
  }

  dom.enviarScore.disabled = true;
  definirStatus('Finalizando a série...');

  try {
    const { total } = await salvarPontuacao(treino.sessao, treino.pontos);
    treino.registrarEnvio(total);
    atualizarListaLateral();
    definirStatus(`${treino.chaveSerie} concluída — ${total} pontos.`);

    // O dashboard lê pelo backend, que mantém cache: avisamos para que
    // a análise apareça imediatamente.
    api.invalidarCache().catch(() => {});

    avancar();
  } catch (erro) {
    console.error(erro);
    definirStatus('Erro ao salvar a pontuação.');
    window.alert(`Erro ao salvar a pontuação: ${erro.message}`);
  } finally {
    dom.enviarScore.disabled = false;
  }
}

function avancar() {
  const resultado = treino.avancar();

  if (resultado === 'treino-concluido') {
    const id = treino.idTreino;
    window.setTimeout(() => {
      if (window.confirm('Treino concluído! Deseja abrir a análise agora?')) {
        window.location.href = `./dashboard.html?treino=${encodeURIComponent(id)}`;
        return;
      }
      reiniciarParaNovoTreino();
    }, 300);
    return;
  }

  if (resultado === 'novo-tempo') {
    window.alert('T1 concluído! Iniciando T2 - Série 1.');
  }

  voltarParaAlvo();
}

function voltarParaAlvo() {
  alvo.limpar();
  treino.limparSerie();
  escreverFormulario();

  dom.moduloAlvo.classList.remove('oculto');
  dom.moduloScore.classList.add('oculto');

  atualizarAlvoUI();
  atualizarScoreUI();
  definirStatus(`Pronto para ${treino.tempo} - Série ${treino.serie}.`);
}

function reiniciarParaNovoTreino() {
  treino.reiniciar({ manterAtleta: true });
  alvo.limpar();
  escreverFormulario();

  dom.setup.classList.remove('oculto');
  dom.treinoContainer.classList.add('oculto');
  dom.miniHeader.classList.add('oculto');
  dom.moduloAlvo.classList.add('oculto');
  dom.moduloScore.classList.add('oculto');

  atualizarAlvoUI();
  atualizarScoreUI();
  atualizarListaLateral();
  definirStatus('');
}

// ---------------------------------------------------------------- init

function ligarEventos() {
  dom.tema.addEventListener('click', () =>
    aplicarTema(!document.body.classList.contains('dark-mode')),
  );

  dom.comecar.addEventListener('click', iniciarTreino);
  dom.distancia.addEventListener('change', sincronizarTipoDeAlvo);
  dom.tipoAlvo.addEventListener('change', sincronizarTipoDeAlvo);

  dom.zoom.addEventListener('input', (evento) => alvo.definirZoom(evento.target.value));

  dom.qtdFlechas.addEventListener('change', () => {
    lerFormulario();
    alvo.definirLimite(treino.flechasPorSerie);
    atualizarAlvoUI();
    atualizarScoreUI();
  });
  dom.qtdSeries.addEventListener('change', () => lerFormulario());

  dom.desfazerAlvo.addEventListener('click', () => {
    alvo.desfazer();
    atualizarAlvoUI();
  });
  dom.limparAlvo.addEventListener('click', () => {
    alvo.limpar();
    atualizarAlvoUI();
  });
  dom.enviarAlvo.addEventListener('click', enviarAlvo);

  dom.desfazerScore.addEventListener('click', () => {
    treino.pontos.pop();
    atualizarScoreUI();
  });
  dom.limparScore.addEventListener('click', () => {
    treino.pontos = [];
    atualizarScoreUI();
  });
  dom.enviarScore.addEventListener('click', enviarPontuacao);

  // O alvo é redesenhado ao mudar o tamanho da janela para que a
  // conversão de coordenadas continue casando com o que está na tela.
  window.addEventListener('resize', () => {
    if (treino.iniciado) alvo.desenhar();
  });
}

async function iniciar() {
  // Nunca resolve sem sessão válida — redireciona para o login e a
  // execução para exatamente aqui.
  const usuario = await exigirSessao();
  mostrarUsuario(document.getElementById('usuarioLogado'), usuario);
  ligarBotaoSair(document.getElementById('btnSair'));

  restaurarTema();
  escreverFormulario();
  montarNumpad();
  ligarEventos();

  alvo.dimensionar();
  alvo.definirLimite(treino.flechasPorSerie);
  sincronizarTipoDeAlvo();

  atualizarAlvoUI();
  atualizarScoreUI();
  atualizarListaLateral();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', iniciar);
} else {
  iniciar();
}
