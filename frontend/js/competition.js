/**
 * Controlador da tela de competição: registro ao vivo + relatório.
 *
 * O registro reaproveita exatamente os mesmos módulos do treino comum
 * — `AlvoCanvas` (canvas.js) e o teclado de pontuação (scoring.js) —
 * como pedido explicitamente: não existe um segundo mecanismo de
 * marcação de flecha só para competição.
 */

import { apiCompeticoes, ErroDaApi } from './api.js';
import { exigirSessao, ligarBotaoSair, mostrarUsuario } from './auth-guard.js';
import { AlvoCanvas } from './canvas.js';
import * as charts from './charts.js';
import {
  STATUS_CONCLUIDA,
  STATUS_EM_ANDAMENTO,
  STATUS_PAUSADA,
  STATUS_PLANEJADA,
  atualizarStatusCompeticao,
  salvarAlvoCompeticao,
  salvarPontuacaoCompeticao,
} from './competitions-firebase.js';
import { TECLAS, conferir, somar } from './scoring.js';
import { GraficoDeAlvo } from './target-plot.js';
import { comCores, geometriaPorNome } from './targets.js';

const el = (id) => document.getElementById(id);
const mostrar = (elemento, visivel) => elemento?.classList.toggle('oculto', !visivel);
const nada = '—';

const ROTULO_STATUS = {
  [STATUS_PLANEJADA]: 'Planejada',
  [STATUS_EM_ANDAMENTO]: 'Em andamento',
  [STATUS_PAUSADA]: 'Pausada',
  [STATUS_CONCLUIDA]: 'Concluída',
};

function numero(valor, casas = 2) {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return nada;
  return Number(valor).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
}
function inteiro(valor) {
  return valor === null || valor === undefined ? nada : Number(valor).toLocaleString('pt-BR');
}
function dataBr(iso) {
  if (!iso) return nada;
  const [ano, mes, dia] = iso.split('-');
  return `${dia}/${mes}/${ano}`;
}

const params = new URLSearchParams(window.location.search);
const competicaoId = params.get('id');

/**
 * Estrutura fixa da competição: 12 séries de 6 flechas (72 no total) —
 * o formato de uma prova de ranqueamento outdoor. A série avança
 * sozinha; ao completar a 12ª, a competição é finalizada e o relatório
 * é gerado automaticamente, sem precisar de um clique manual em
 * "Finalizar".
 */
const MAX_SERIES = 12;
const FLECHAS_POR_SERIE = 6;
const PROVA_PADRAO = 'Classificação';

const estado = {
  competicao: null,
  serieAtual: 1,
  flechas: [],
  pontos: [],
};

let alvo = null;
let graficoRelatorio = null;

// ------------------------------------------------------------- erros

function mostrarErro(mensagem) {
  const aviso = el('avisoConexao');
  if (!mensagem) return mostrar(aviso, false);
  aviso.textContent = mensagem;
  mostrar(aviso, true);
}

function tratarErro(erro) {
  console.error(erro);
  if (erro instanceof ErroDaApi && erro.status === 401) {
    window.location.href = './login.html';
    return;
  }
  if (erro instanceof ErroDaApi && erro.status === 0) {
    mostrarErro('Servidor de análise indisponível.');
    return;
  }
  mostrarErro(erro.message || 'Erro ao carregar a competição.');
}

// --------------------------------------------------------- cabeçalho

function renderizarCabecalho(competicao) {
  el('seloStatus').textContent = ROTULO_STATUS[competicao.status] || competicao.status;
  el('seloStatus').className = `selo-status ${competicao.status}`;
  el('tituloCompeticao').textContent = competicao.nome;
  el('metaCompeticao').textContent = [
    competicao.atleta,
    dataBr(competicao.data),
    competicao.local,
    competicao.categoria,
    competicao.modalidade,
  ].filter(Boolean).join(' · ');

  const controles = el('controlesStatus');
  controles.innerHTML = '';
  const botao = (rotulo, classe, aoClicar) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = `btn-status ${classe}`;
    b.textContent = rotulo;
    b.addEventListener('click', aoClicar);
    controles.appendChild(b);
  };

  if (competicao.status === STATUS_PLANEJADA) {
    botao('▶ Iniciar prova', 'iniciar', () => mudarStatus(STATUS_EM_ANDAMENTO));
  }
  if (competicao.status === STATUS_EM_ANDAMENTO) {
    botao('⏸ Pausar', 'pausar', () => mudarStatus(STATUS_PAUSADA));
    botao('✓ Finalizar competição', 'finalizar', () => finalizarCompeticao());
  }
  if (competicao.status === STATUS_PAUSADA) {
    botao('▶ Retomar', 'retomar', () => mudarStatus(STATUS_EM_ANDAMENTO));
    botao('✓ Finalizar competição', 'finalizar', () => finalizarCompeticao());
  }

  mostrar(el('painel-registrar'), competicao.status !== STATUS_CONCLUIDA || document.querySelector('.aba[data-aba="registrar"]').classList.contains('ativa'));
  el('abaRegistrar').disabled = false;
}

async function mudarStatus(novoStatus) {
  try {
    await atualizarStatusCompeticao(competicaoId, novoStatus);
    await apiCompeticoes.invalidarCache().catch(() => {});
    await recarregarCabecalho();
  } catch (erro) {
    window.alert(erro.message || 'Erro ao atualizar status.');
  }
}

async function finalizarCompeticao() {
  if (!window.confirm('Finalizar esta competição agora, antes das 12 séries? Você ainda poderá consultar o relatório depois.')) return;
  await mudarStatus(STATUS_CONCLUIDA);
  trocarAba('relatorio');
}

/**
 * Chamada sozinha ao completar a 12ª série — sem precisar de clique
 * manual em "Finalizar competição". Marca a competição como concluída
 * e já abre o relatório.
 */
async function finalizarAutomaticamente() {
  el('status').textContent = 'Última série registrada — gerando relatório...';
  await atualizarStatusCompeticao(competicaoId, STATUS_CONCLUIDA);
  await apiCompeticoes.invalidarCache().catch(() => {});
  await recarregarCabecalho();
  window.alert('Competição concluída! As 12 séries foram registradas — confira o relatório.');
  trocarAba('relatorio');
}

async function recarregarCabecalho() {
  const dados = await apiCompeticoes.obter(competicaoId);
  estado.competicao = dados.competicao;
  renderizarCabecalho(dados.competicao);
  renderizarAcompanhamento(dados);
  return dados;
}

// ------------------------------------------------------- registro

function sessaoAtual() {
  return {
    competicaoId,
    prova: PROVA_PADRAO,
    numero: estado.serieAtual,
    atleta: estado.competicao.atleta,
    tipoAlvo: estado.competicao.tipo_alvo,
    distancia: estado.competicao.distancia,
  };
}

function atualizarAlvoUI() {
  el('contadorAlvo').textContent = `Flechas no Alvo: ${estado.flechas.length} / ${FLECHAS_POR_SERIE}`;
  el('acFlecha').textContent = `${estado.flechas.length} / ${FLECHAS_POR_SERIE}`;
  el('acSerie').textContent = `${estado.serieAtual} / ${MAX_SERIES}`;
  mostrar(el('btnEnviarAlvo'), estado.flechas.length === FLECHAS_POR_SERIE);
}

function montarNumpad() {
  const numpad = el('numpad');
  numpad.innerHTML = '';
  for (const tecla of TECLAS) {
    const botao = document.createElement('button');
    botao.type = 'button';
    botao.className = `num-btn ${tecla.classe}`;
    botao.textContent = tecla.valor;
    botao.addEventListener('click', () => adicionarPonto(tecla.valor));
    numpad.appendChild(botao);
  }
}

function adicionarPonto(valor) {
  if (estado.pontos.length >= FLECHAS_POR_SERIE) return;
  estado.pontos.push(valor);
  atualizarScoreUI();
}

function atualizarScoreUI() {
  const geo = geometriaPorNome(estado.competicao.tipo_alvo);
  const conferencia = conferir(estado.pontos, estado.flechas, geo);
  const caixas = el('containerFlechasScore');
  caixas.innerHTML = '';

  for (let i = 0; i < FLECHAS_POR_SERIE; i += 1) {
    const caixa = document.createElement('div');
    caixa.className = 'ponto-box';
    const item = conferencia[i];
    if (item) {
      caixa.classList.add('preenchido');
      caixa.textContent = item.rotulo;
      if (item.confere === false) {
        caixa.classList.add('divergente');
        caixa.title = `Marcado no anel ${item.sugerido}`;
      }
    } else {
      caixa.textContent = '-';
    }
    caixas.appendChild(caixa);
  }

  const total = somar(estado.pontos);
  el('scoreTotal').textContent = `Total: ${total}`;
  el('contadorScore').textContent = `Pontos Inseridos: ${estado.pontos.length} / ${FLECHAS_POR_SERIE}`;
  el('acScoreSerie').textContent = total;
  mostrar(el('btnEnviarScore'), estado.pontos.length === FLECHAS_POR_SERIE);
}

async function enviarAlvo() {
  if (estado.flechas.length !== FLECHAS_POR_SERIE) {
    window.alert(`Marque as ${FLECHAS_POR_SERIE} flechas antes de confirmar.`);
    return;
  }

  el('btnEnviarAlvo').disabled = true;
  el('status').textContent = 'Salvando o alvo na competição...';

  try {
    await salvarAlvoCompeticao(sessaoAtual(), estado.flechas);
    el('status').textContent = 'Alvo salvo. Agora insira a pontuação.';
    mostrar(el('moduloAlvo'), false);
    mostrar(el('moduloScore'), true);
    estado.pontos = [];
    atualizarScoreUI();
  } catch (erro) {
    console.error(erro);
    el('status').textContent = erro.message;
    window.alert(erro.message);
  } finally {
    el('btnEnviarAlvo').disabled = false;
  }
}

async function enviarPontuacao() {
  if (estado.pontos.length !== FLECHAS_POR_SERIE) {
    window.alert(`Insira os ${FLECHAS_POR_SERIE} pontos antes de finalizar.`);
    return;
  }

  el('btnEnviarScore').disabled = true;
  el('status').textContent = 'Finalizando série...';

  try {
    const { total } = await salvarPontuacaoCompeticao(sessaoAtual(), estado.pontos);
    await apiCompeticoes.invalidarCache().catch(() => {});
    el('status').textContent = `Série ${estado.serieAtual}/${MAX_SERIES} salva — ${total} pontos.`;

    const eraAUltimaSerie = estado.serieAtual >= MAX_SERIES;
    estado.serieAtual += 1;
    estado.flechas = [];
    estado.pontos = [];
    alvo.limpar();

    await recarregarCabecalho();
    await carregarSeriesRegistradas();

    if (eraAUltimaSerie) {
      await finalizarAutomaticamente();
      return;
    }

    mostrar(el('moduloAlvo'), true);
    mostrar(el('moduloScore'), false);
    atualizarAlvoUI();
    atualizarScoreUI();
  } catch (erro) {
    console.error(erro);
    el('status').textContent = erro.message;
    window.alert(erro.message);
  } finally {
    el('btnEnviarScore').disabled = false;
  }
}

async function carregarSeriesRegistradas() {
  const analytics = await apiCompeticoes.analytics(competicaoId).catch(() => null);
  const container = el('listaSeries');
  container.innerHTML = '';
  if (!analytics || !analytics.series.length) {
    container.innerHTML = '<p class="historico-vazio">Nenhuma série registrada ainda.</p>';
    return;
  }
  for (const serie of analytics.series) {
    const item = document.createElement('div');
    item.className = 'serie-item';
    item.innerHTML = `<span style="flex:1; font-size:12px;">${serie.rotulo}${serie.finalizada ? ` · ${serie.total}` : ' (aberta)'}</span>`;
    container.appendChild(item);
  }
}

/**
 * Sincroniza `estado.serieAtual` com o que já está gravado no Firestore
 * — importante ao reabrir uma competição em andamento: a série
 * corrente não pode reiniciar do 1, precisa retomar de onde parou.
 */
function renderizarAcompanhamento(dados) {
  const s = dados.serie_atual;
  estado.serieAtual = s ? (s.finalizada ? s.numero + 1 : s.numero) : 1;

  el('acProva').textContent = s ? s.prova : PROVA_PADRAO;
  el('acSerie').textContent = `${Math.min(estado.serieAtual, MAX_SERIES)} / ${MAX_SERIES}`;
  el('acScoreTotal').textContent = inteiro(dados.score_total);
}

// ------------------------------------------------------------ abas

function trocarAba(aba) {
  for (const botao of document.querySelectorAll('.aba')) {
    botao.classList.toggle('ativa', botao.dataset.aba === aba);
  }
  mostrar(el('painel-registrar'), aba === 'registrar');
  mostrar(el('painel-relatorio'), aba === 'relatorio');
  if (aba === 'relatorio') {
    carregarRelatorio().catch(tratarErro);
  }
}

// --------------------------------------------------------- relatório

function cartaoKpi(rotulo, valor, nota = '') {
  return `<div class="kpi"><div class="kpi-rotulo">${rotulo}</div><div class="kpi-valor">${valor}</div>${nota ? `<div class="kpi-nota">${nota}</div>` : ''}</div>`;
}

function cartaoDestaque(titulo, valor, contexto, classe = '') {
  return `<div class="destaque-card ${classe}"><div class="titulo">${titulo}</div><div class="valor">${valor}</div>${contexto ? `<div class="contexto">${contexto}</div>` : ''}</div>`;
}

async function carregarRelatorio() {
  mostrar(el('relatorioCarregando'), true);
  mostrar(el('relatorioConteudo'), false);

  const [relatorio, disparos] = await Promise.all([
    apiCompeticoes.relatorio(competicaoId),
    apiCompeticoes.disparos(competicaoId),
  ]);

  const r = relatorio.resumo;
  el('relNome').textContent = r.nome;
  el('relMeta').textContent = [r.atleta, dataBr(r.data), r.local, r.categoria, r.modalidade].filter(Boolean).join(' · ');

  el('relKpisScore').innerHTML = [
    cartaoKpi('Pontuação total', inteiro(relatorio.pontuacao.total)),
    cartaoKpi('Média por flecha', numero(relatorio.pontuacao.media)),
    cartaoKpi('Melhor flecha', relatorio.pontuacao.maximo ?? nada),
    cartaoKpi('Pior flecha', relatorio.pontuacao.minimo ?? nada),
    cartaoKpi('Séries', inteiro(r.quantidade_series)),
    cartaoKpi('Flechas', inteiro(r.quantidade_flechas)),
  ].join('');

  const c = relatorio.consistencia;
  el('relFraseConsistencia').textContent = relatorio.analise_final;
  el('relKpisConsistencia').innerHTML = [
    cartaoKpi('Variabilidade', c.coeficiente_variacao === null ? nada : `${(c.coeficiente_variacao * 100).toFixed(1)}%`),
    cartaoKpi('Desvio entre séries', c.desvio_entre_series === null ? nada : `±${numero(c.desvio_entre_series, 1)}`),
    cartaoKpi('Amplitude', c.amplitude === null ? nada : numero(c.amplitude, 1)),
  ].join('');

  const d = relatorio.dispersao;
  el('relKpisPrecisao').innerHTML = [
    cartaoKpi('Distância média do centro', `${numero(d.distancia_media_centro_cm, 1)} cm`),
    cartaoKpi('Maior distância', `${numero(d.distancia_maxima_centro_cm, 1)} cm`),
    cartaoKpi('Dispersão das flechas', `${numero(d.dispersao_radial_cm, 1)} cm`),
  ].join('');

  const dest = relatorio.destaques;
  el('relDestaques').innerHTML = [
    dest.melhor_pontuacao ? cartaoDestaque('Melhor pontuação', dest.melhor_pontuacao.rotulo, `${dest.melhor_pontuacao.prova} · série ${dest.melhor_pontuacao.serie}, flecha ${dest.melhor_pontuacao.flecha}`) : '',
    dest.melhor_serie ? cartaoDestaque('Melhor série', dest.melhor_serie.total, dest.melhor_serie.rotulo) : '',
    dest.melhor_sequencia ? cartaoDestaque('Melhor sequência', `${dest.melhor_sequencia} flechas`, 'seguidas valendo 9 ou mais') : '',
    dest.melhor_agrupamento ? cartaoDestaque('Melhor agrupamento', `${numero(dest.melhor_agrupamento.dispersao_cm, 1)} cm`, dest.melhor_agrupamento.rotulo) : '',
    dest.maior_precisao ? cartaoDestaque('Maior precisão', `${numero(dest.maior_precisao.distancia_cm, 1)} cm`, dest.maior_precisao.rotulo) : '',
  ].filter(Boolean).join('') || '<p class="legenda">Dados insuficientes para destaques.</p>';

  const pa = relatorio.pontos_de_atencao;
  el('relPontosAtencao').innerHTML = [
    pa.pior_pontuacao ? cartaoDestaque('Pior flecha', pa.pior_pontuacao.rotulo, `${pa.pior_pontuacao.prova} · série ${pa.pior_pontuacao.serie}, flecha ${pa.pior_pontuacao.flecha}`, 'atencao') : '',
    pa.pior_serie ? cartaoDestaque('Pior série', pa.pior_serie.total, pa.pior_serie.rotulo, 'atencao') : '',
    pa.maior_dispersao ? cartaoDestaque('Maior dispersão', `${numero(pa.maior_dispersao.dispersao_cm, 1)} cm`, pa.maior_dispersao.rotulo, 'atencao') : '',
    pa.maior_distancia_centro ? cartaoDestaque('Maior distância do centro', `${numero(pa.maior_distancia_centro.distancia_cm, 1)} cm`, pa.maior_distancia_centro.rotulo, 'atencao') : '',
  ].filter(Boolean).join('') || '<p class="legenda">Nenhum ponto de atenção identificado.</p>';

  const comp = relatorio.comparacao_inicio_fim;
  mostrar(el('painelInicioFim'), Boolean(comp));
  if (comp) {
    el('relInicioFim').innerHTML = [
      cartaoKpi('Distância do centro no início', `${numero(comp.inicio.distancia_media_centro_cm, 1)} cm`),
      cartaoKpi('Distância do centro no final', `${numero(comp.fim.distancia_media_centro_cm, 1)} cm`, comp.aproximou_do_centro ? 'aproximou' : 'afastou'),
      cartaoKpi('Dispersão no início', `${numero(comp.inicio.dispersao_radial_cm, 1)} cm`),
      cartaoKpi('Dispersão no final', `${numero(comp.fim.dispersao_radial_cm, 1)} cm`, comp.ficou_mais_compacto ? 'mais compacto' : 'mais disperso'),
    ].join('');
  }

  el('relAnaliseFinal').textContent = relatorio.analise_final;

  if (!graficoRelatorio) {
    graficoRelatorio = new GraficoDeAlvo(el('relGraficoAlvo'), el('relTooltipAlvo'));
  }
  graficoRelatorio.definirDados({
    geometria: disparos.geometria,
    disparos: disparos.disparos,
    centroGrupo: { x: d.centro_grupo_x ?? 0, y: d.centro_grupo_y ?? 0 },
    raio95: d.raio_95_grupo,
    agrupamentoPorFace: relatorio.agrupamento_por_face,
  });

  charts.scorePorSerie('relGraficoSeries', relatorio.series);
  charts.distribuicao('relGraficoDistribuicao', relatorio.distribuicao);

  mostrar(el('relatorioCarregando'), false);
  mostrar(el('relatorioConteudo'), true);
}

// ------------------------------------------------------------ init

function ligarEventos() {
  el('btnTema').addEventListener('click', () => document.body.classList.toggle('dark-mode'));

  for (const botao of document.querySelectorAll('.aba')) {
    botao.addEventListener('click', () => trocarAba(botao.dataset.aba));
  }

  el('zoomRange').addEventListener('input', (e) => alvo.definirZoom(e.target.value));
  el('btnDesfazerAlvo').addEventListener('click', () => { alvo.desfazer(); atualizarAlvoUI(); });
  el('btnLimparAlvo').addEventListener('click', () => { alvo.limpar(); atualizarAlvoUI(); });
  el('btnEnviarAlvo').addEventListener('click', enviarAlvo);

  el('btnDesfazerScore').addEventListener('click', () => { estado.pontos.pop(); atualizarScoreUI(); });
  el('btnLimparScore').addEventListener('click', () => { estado.pontos = []; atualizarScoreUI(); });
  el('btnEnviarScore').addEventListener('click', enviarPontuacao);

  window.addEventListener('resize', () => alvo?.desenhar());
}

async function iniciar() {
  const usuario = await exigirSessao();
  mostrarUsuario(el('usuarioLogado'), usuario);
  ligarBotaoSair(el('btnSair'));
  ligarEventos();

  if (!competicaoId) {
    mostrar(el('carregando'), false);
    mostrar(el('naoEncontrada'), true);
    return;
  }

  try {
    const dados = await recarregarCabecalho();

    alvo = new AlvoCanvas(el('alvo'), {
      aoMarcar: () => {
        estado.flechas = alvo.flechas;
        atualizarAlvoUI();
      },
    });
    alvo.dimensionar();
    alvo.definirLimite(FLECHAS_POR_SERIE);
    alvo.definirGeometria(comCores(geometriaPorNome(estado.competicao.tipo_alvo)));
    montarNumpad();

    atualizarAlvoUI();
    atualizarScoreUI();
    await carregarSeriesRegistradas();

    if (dados.competicao.status === STATUS_CONCLUIDA) {
      trocarAba('relatorio');
    }

    mostrar(el('carregando'), false);
    mostrar(el('conteudo'), true);
  } catch (erro) {
    mostrar(el('carregando'), false);
    tratarErro(erro);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', iniciar);
} else {
  iniciar();
}
