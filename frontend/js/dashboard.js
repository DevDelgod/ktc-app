/**
 * Controlador do dashboard KTC Performance.
 *
 * Responsabilidade: interação, navegação, filtros e apresentação.
 * Nenhuma estatística é calculada aqui — média, desvio, dispersão e
 * agrupamento vêm prontos da API Python. O frontend só desenha.
 */

import { api, ErroDaApi } from './api.js';
import { exigirSessao, ligarBotaoSair, mostrarUsuario } from './auth-guard.js';
import * as charts from './charts.js';
import { GraficoDeAlvo } from './target-plot.js';

const CHAVE_TEMA = 'ktc-tema';
const el = (id) => document.getElementById(id);

const estado = {
  aba: 'treino',
  treinoSelecionado: null,
  treinosDisponiveis: [],
  selecaoComparacao: new Set(),
};

let graficoAlvo = null;

// ------------------------------------------------------------- utilidades

const nada = '—';

function numero(valor, casas = 2) {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return nada;
  return Number(valor).toLocaleString('pt-BR', {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
}

function inteiro(valor) {
  if (valor === null || valor === undefined) return nada;
  return Number(valor).toLocaleString('pt-BR');
}

function porcentagem(valor) {
  if (valor === null || valor === undefined) return nada;
  return `${(Number(valor) * 100).toFixed(1)}%`;
}

function dataBr(iso) {
  if (!iso) return nada;
  const [ano, mes, dia] = iso.split('-');
  return `${dia}/${mes}/${ano}`;
}

function mostrar(elemento, visivel) {
  elemento?.classList.toggle('oculto', !visivel);
}

function mostrarErro(mensagem) {
  const aviso = el('avisoConexao');
  if (!mensagem) {
    mostrar(aviso, false);
    return;
  }
  aviso.innerHTML = mensagem;
  mostrar(aviso, true);
}

// ------------------------------------------------------------------ tema

function aplicarTema(escuro) {
  document.body.classList.toggle('dark-mode', escuro);
  try {
    localStorage.setItem(CHAVE_TEMA, escuro ? 'escuro' : 'claro');
  } catch {
    /* storage indisponível: o tema só não persiste */
  }
  charts.repintarTodos();
  graficoAlvo?.desenhar();
}

function restaurarTema() {
  let salvo = null;
  try {
    salvo = localStorage.getItem(CHAVE_TEMA);
  } catch {
    salvo = null;
  }
  const prefere = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
  document.body.classList.toggle('dark-mode', salvo ? salvo === 'escuro' : Boolean(prefere));
}

// --------------------------------------------------------------- filtros

/** Filtros atualmente selecionados, prontos para virar query string. */
function filtrosAtuais() {
  return {
    atleta: el('fAtleta').value || null,
    data_inicio: el('fDataInicio').value || null,
    data_fim: el('fDataFim').value || null,
    tipo_alvo: el('fTipoAlvo').value || null,
    distancia: el('fDistancia').value || null,
    serie: el('fSerie').value || null,
  };
}

function preencherSelect(elemento, valores, rotuloVazio, valorAtual) {
  const anterior = valorAtual ?? elemento.value;
  elemento.innerHTML = '';

  if (rotuloVazio !== null) {
    const opcao = document.createElement('option');
    opcao.value = '';
    opcao.textContent = rotuloVazio;
    elemento.appendChild(opcao);
  }

  for (const item of valores) {
    const opcao = document.createElement('option');
    opcao.value = item.valor;
    opcao.textContent = item.rotulo;
    elemento.appendChild(opcao);
  }

  // Preserva a escolha do usuário se ela ainda existir no novo conjunto.
  if (anterior && valores.some((v) => String(v.valor) === String(anterior))) {
    elemento.value = anterior;
  }
}

/**
 * Recarrega as opções de filtro.
 *
 * As listas vêm já restritas pela seleção corrente, de modo que
 * escolher um atleta reduz as datas e os treinos disponíveis. Uma única
 * chamada — o backend deriva tudo do mesmo conjunto em cache.
 */
async function carregarFiltros() {
  const dados = await api.filtros(filtrosAtuais());

  preencherSelect(
    el('fAtleta'),
    dados.atletas.map((a) => ({ valor: a.atleta, rotulo: `${a.atleta} (${a.treinos})` })),
    'Todos',
  );
  preencherSelect(
    el('fTipoAlvo'),
    dados.tipos_de_alvo.map((t) => ({ valor: t, rotulo: t })),
    'Todos',
  );
  preencherSelect(
    el('fDistancia'),
    dados.distancias.map((d) => ({ valor: d, rotulo: d })),
    'Todas',
  );
  preencherSelect(
    el('fSerie'),
    dados.series.map((s) => ({ valor: s, rotulo: `Série ${s}` })),
    'Todas',
  );

  estado.treinosDisponiveis = dados.treinos;

  // Um treino que saiu do recorte não pode continuar selecionado para
  // comparação — senão a tabela ficaria com colunas de treinos que os
  // filtros já excluíram.
  const disponiveis = new Set(dados.treinos.map((t) => t.id_treino));
  for (const id of [...estado.selecaoComparacao]) {
    if (!disponiveis.has(id)) estado.selecaoComparacao.delete(id);
  }

  preencherSelect(
    el('fTreino'),
    dados.treinos.map((t) => ({
      valor: t.id_treino,
      rotulo: `${dataBr(t.data_treino)} · ${t.id_treino} · ${t.total} pts`,
    })),
    dados.treinos.length ? null : 'Nenhum treino',
    estado.treinoSelecionado,
  );

  estado.treinoSelecionado = el('fTreino').value || null;
  return dados;
}

// ---------------------------------------------------------- aba: treino

function cartaoKpi(rotulo, valor, nota, classe = '') {
  return `
    <div class="kpi ${classe}">
      <div class="kpi-rotulo">${rotulo}</div>
      <div class="kpi-valor">${valor}</div>
      ${nota ? `<div class="kpi-nota">${nota}</div>` : ''}
    </div>`;
}

function grupoDeMetricas(titulo, cartoes) {
  return `
    <div class="grupo-metricas">
      <h3 class="grupo-metricas-titulo">${titulo}</h3>
      <div class="kpis">${cartoes.join('')}</div>
    </div>`;
}

function renderizarIdentificacao(treino) {
  const itens = [
    ['Atleta', treino.atleta || nada],
    ['Data', dataBr(treino.data_treino)],
    ['Treino', treino.id_treino],
    ['Alvo', treino.tipo_alvo || nada],
    ['Distância', treino.distancias.join(', ') || nada],
    ['Tempos', treino.tempos.join(' · ') || nada],
    ['Séries', inteiro(treino.quantidade_series)],
    ['Flechas', inteiro(treino.quantidade_flechas)],
  ];
  el('identificacao').innerHTML = itens
    .map(([rotulo, valor]) => `<div><dt>${rotulo}</dt><dd>${valor}</dd></div>`)
    .join('');
}

/**
 * KPIs organizados em quatro grupos que respondem perguntas práticas do
 * atleta: quanto pontuei, quão perto do centro, quão estável, e para
 * onde meu grupo está deslocado. A unidade interna ("u") nunca aparece
 * — tudo que é distância sai em centímetros, convertido a partir da
 * calibração física real do alvo (ver `dispersion.com_cm` no backend).
 */
function renderizarKpis(analise) {
  const p = analise.pontuacao;
  const d = analise.dispersao;
  const c = analise.consistencia;

  const score = grupoDeMetricas('Score', [
    cartaoKpi('Pontuação total', inteiro(p.total), `${porcentagem(p.aproveitamento)} do máximo`),
    cartaoKpi('Média por flecha', numero(p.media), `mediana ${numero(p.mediana)}`),
    cartaoKpi('Melhor flecha', p.maximo ?? nada, 'maior pontuação individual'),
    cartaoKpi('Pior flecha', p.minimo ?? nada, 'menor pontuação individual'),
    cartaoKpi(
      'Melhor série',
      p.melhor_serie ? `${p.melhor_serie.total}` : nada,
      p.melhor_serie ? p.melhor_serie.rotulo : 'nenhuma série finalizada',
    ),
    cartaoKpi(
      'Pior série',
      p.pior_serie ? `${p.pior_serie.total}` : nada,
      p.pior_serie ? p.pior_serie.rotulo : 'nenhuma série finalizada',
    ),
  ]);

  const precisao = grupoDeMetricas('Precisão', [
    cartaoKpi(
      'Distância média do centro',
      `${numero(d.distancia_media_centro_cm, 1)} cm`,
      'quanto mais perto de zero, melhor',
      'precisao',
    ),
    cartaoKpi(
      'Melhor distância do centro',
      `${numero(d.distancia_minima_centro_cm, 1)} cm`,
      'a flecha mais próxima do centro',
      'precisao',
    ),
    cartaoKpi(
      'Maior distância do centro',
      `${numero(d.distancia_maxima_centro_cm, 1)} cm`,
      'a flecha mais longe do centro',
      'precisao',
    ),
  ]);

  const consistencia = grupoDeMetricas('Consistência', [
    cartaoKpi(
      'Dispersão das flechas',
      `${numero(d.dispersao_radial_cm, 1)} cm`,
      'o quanto as flechas variam de posição',
    ),
    cartaoKpi(
      'Variabilidade',
      c.coeficiente_variacao === null ? nada : porcentagem(c.coeficiente_variacao),
      'variação da pontuação entre séries',
    ),
    cartaoKpi(
      'Consistência entre séries',
      c.desvio_entre_series === null ? nada : `±${numero(c.desvio_entre_series, 1)}`,
      c.coeficiente_variacao === null ? 'poucas séries finalizadas' : `${c.series_consideradas} séries`,
    ),
  ]);

  const agrupamento = grupoDeMetricas('Agrupamento', [
    cartaoKpi(
      'Deslocamento horizontal',
      `${numero(Math.abs(d.centro_grupo_x_cm), 1)} cm`,
      d.centro_grupo_x_cm >= 0 ? 'para a direita do centro' : 'para a esquerda do centro',
      'agrupamento',
    ),
    cartaoKpi(
      'Deslocamento vertical',
      `${numero(Math.abs(d.centro_grupo_y_cm), 1)} cm`,
      d.centro_grupo_y_cm >= 0 ? 'acima do centro' : 'abaixo do centro',
      'agrupamento',
    ),
    cartaoKpi(
      'Tamanho do agrupamento',
      `${numero(d.raio_medio_grupo_cm, 1)} cm`,
      'raio médio até o centro do próprio grupo',
      'agrupamento',
    ),
    cartaoKpi(
      'Dispersão radial',
      `${numero(d.dispersao_radial_cm, 1)} cm`,
      d.vies_direcao ? `tendência: ${d.vies_direcao.toLowerCase()}` : '',
      'agrupamento',
    ),
  ]);

  el('kpis').innerHTML = score + precisao + consistencia + agrupamento;

  const frase = analise.analise?.consistencia;
  el('fraseAnalise').innerHTML = frase
    ? `${frase}${analise.analise?.dispersao ? ' ' + analise.analise.dispersao : ''}`
    : '';
  mostrar(el('fraseAnalise'), Boolean(frase));
}

function renderizarTabelaSeries(series) {
  el('tabelaSeries').querySelector('tbody').innerHTML = series
    .map(
      (s) => `
      <tr>
        <td><strong>${s.rotulo}</strong>${s.finalizada ? '' : ' <span class="selo selo-atencao">aberta</span>'}</td>
        <td class="num">${inteiro(s.quantidade_flechas)}</td>
        <td class="num">${inteiro(s.total)}</td>
        <td class="num">${numero(s.media)}</td>
        <td class="num">${numero(s.distancia_media_centro_cm, 1)}</td>
        <td class="num">${numero(s.dispersao_radial_cm, 1)}</td>
        <td>${s.flechas_string ?? nada}</td>
      </tr>`,
    )
    .join('');
}

function renderizarQualidade(qualidade) {
  const concordancia = qualidade.concordancia;
  let selo = '<span class="selo selo-erro">sem pontuação</span>';
  if (concordancia !== null) {
    if (concordancia >= 0.9) selo = '<span class="selo selo-ok">consistente</span>';
    else if (concordancia >= 0.6) selo = '<span class="selo selo-atencao">atenção</span>';
    else selo = '<span class="selo selo-erro">divergente</span>';
  }

  el('qualidade').innerHTML = `
    <div class="kpis" style="margin-bottom:0">
      ${cartaoKpi('Concordância', porcentagem(concordancia), `${selo}`)}
      ${cartaoKpi('Divergências', inteiro(qualidade.divergencias), 'digitado ≠ marcado')}
      ${cartaoKpi('Sem pontuação', inteiro(qualidade.sem_pontuacao), 'séries não finalizadas')}
      ${cartaoKpi(
        'Fora do alvo',
        inteiro(qualidade.fora_do_alvo),
        'marcadas além do anel externo',
        qualidade.fora_do_alvo > 0 ? 'alerta' : '',
      )}
    </div>`;
}

async function carregarTreino() {
  const id = estado.treinoSelecionado;
  mostrar(el('treinoVazio'), !id);
  mostrar(el('treinoConteudo'), false);

  if (!id) {
    mostrar(el('treinoCarregando'), false);
    return;
  }

  mostrar(el('treinoCarregando'), true);
  const filtros = filtrosAtuais();

  const [analise, disparos] = await Promise.all([
    api.analytics(id, filtros),
    api.disparos(id, filtros),
  ]);

  renderizarIdentificacao(analise.treino);
  renderizarKpis(analise);
  renderizarTabelaSeries(analise.series);
  renderizarQualidade(analise.qualidade);

  // O conteúdo precisa estar visível ANTES de criar os gráficos: um
  // canvas dentro de um contêiner com `display:none` mede zero, e o
  // Chart.js congela o tamanho padrão de 300x150 no momento da criação.
  mostrar(el('treinoCarregando'), false);
  mostrar(el('treinoConteudo'), true);

  const d = analise.dispersao;
  graficoAlvo.definirDados({
    geometria: disparos.geometria,
    disparos: disparos.disparos,
    centroGrupo: { x: d.centro_grupo_x ?? 0, y: d.centro_grupo_y ?? 0 },
    raio95: d.raio_95_grupo,
    agrupamentoPorFace: disparos.agrupamento_por_face,
  });

  charts.scorePorSerie('graficoSeries', analise.series);
  charts.distribuicao('graficoDistribuicao', analise.distribuicao);
  charts.consistencia(
    'graficoConsistencia',
    analise.series,
    analise.consistencia.media_por_serie ?? 0,
  );
  charts.distanciaDoCentro('graficoDistancia', disparos.disparos);
}

// -------------------------------------------------------- aba: histórico

async function carregarHistorico() {
  const dados = await api.historico(filtrosAtuais());
  const vazio = dados.quantidade === 0;

  mostrar(el('historicoVazio'), vazio);
  if (vazio) {
    el('kpisHistorico').innerHTML = '';
    el('tabelaHistorico').querySelector('tbody').innerHTML = '';
    return;
  }

  const a = dados.agregado;
  el('kpisHistorico').innerHTML = [
    cartaoKpi('Treinos', inteiro(a.treinos), `${inteiro(a.flechas)} flechas`),
    cartaoKpi('Melhor score', inteiro(a.melhor_total), `média ${numero(a.media_total, 1)}`),
    cartaoKpi('Média por flecha', numero(a.media_por_flecha), 'no período'),
    cartaoKpi(
      'Distância média do centro',
      `${numero(a.media_distancia_centro_cm, 1)} cm`,
      'média do período',
      'precisao',
    ),
    cartaoKpi(
      'Dispersão das flechas',
      `${numero(a.media_dispersao_radial_cm, 1)} cm`,
      'média do período',
      'agrupamento',
    ),
  ].join('');

  const pontos = dados.pontos;
  charts.evolucao('graficoEvolucaoScore', pontos, 'total', 'Score');
  charts.evolucao('graficoEvolucaoMedia', pontos, 'media', 'Média por flecha');
  charts.evolucao('graficoEvolucaoPrecisao', pontos, 'distancia_media_centro_cm', 'Distância (cm)', true);
  charts.evolucao('graficoEvolucaoDispersao', pontos, 'dispersao_radial_cm', 'Dispersão (cm)', true);

  el('tabelaHistorico').querySelector('tbody').innerHTML = pontos
    .map(
      (p) => `
      <tr>
        <td>${dataBr(p.data_treino)}</td>
        <td><strong>${p.id_treino}</strong></td>
        <td>${p.tipo_alvo ?? nada}</td>
        <td class="num">${inteiro(p.quantidade_series)}</td>
        <td class="num">${inteiro(p.quantidade_flechas)}</td>
        <td class="num">${inteiro(p.total)}</td>
        <td class="num">${numero(p.media)}</td>
        <td class="num">${numero(p.distancia_media_centro_cm, 1)}</td>
        <td class="num">${numero(p.dispersao_radial_cm, 1)}</td>
        <td>${p.vies_direcao ?? nada}</td>
      </tr>`,
    )
    .join('');
}

// ------------------------------------------------------- aba: comparação

function renderizarSelecaoComparacao() {
  const container = el('selecaoComparacao');
  container.innerHTML = '';

  for (const treino of estado.treinosDisponiveis) {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chip-treino';
    chip.textContent = `${dataBr(treino.data_treino)} · ${treino.id_treino}`;
    chip.classList.toggle('selecionado', estado.selecaoComparacao.has(treino.id_treino));

    chip.addEventListener('click', () => {
      if (estado.selecaoComparacao.has(treino.id_treino)) {
        estado.selecaoComparacao.delete(treino.id_treino);
      } else if (estado.selecaoComparacao.size < 6) {
        estado.selecaoComparacao.add(treino.id_treino);
      } else {
        window.alert('A comparação aceita no máximo 6 treinos.');
        return;
      }
      renderizarSelecaoComparacao();
      carregarComparacao().catch(tratarErro);
    });

    container.appendChild(chip);
  }
}

async function carregarComparacao() {
  const ids = [...estado.selecaoComparacao];
  const suficiente = ids.length >= 2;

  mostrar(el('comparacaoVazia'), !suficiente);
  mostrar(el('comparacaoConteudo'), suficiente);
  if (!suficiente) return;

  const dados = await api.comparacao(ids, filtrosAtuais());
  const tabela = el('tabelaComparacao');

  tabela.querySelector('thead').innerHTML = `
    <tr><th>Métrica</th>${dados.treinos.map((t) => `<th class="num">${t.id_treino}</th>`).join('')}</tr>`;

  tabela.querySelector('tbody').innerHTML = dados.metricas
    .map((metrica) => {
      const valores = dados.treinos.map((t) => t[metrica.chave]);
      const validos = valores.filter((v) => v !== null && v !== undefined);
      // "Melhor" depende da métrica: score é maior-melhor, dispersão é
      // menor-melhor. O backend informa qual é qual.
      const melhor = validos.length
        ? metrica.melhor === 'maior'
          ? Math.max(...validos)
          : Math.min(...validos)
        : null;

      const celulas = valores
        .map((valor) => {
          const destaque = valor !== null && valor === melhor ? ' class="num destaque-melhor"' : ' class="num"';
          return `<td${destaque}>${numero(valor)}</td>`;
        })
        .join('');
      return `<tr><td>${metrica.rotulo}</td>${celulas}</tr>`;
    })
    .join('');

  charts.comparacao('graficoCompScore', dados.treinos, 'total', 'Score');
  charts.comparacao(
    'graficoCompDispersao',
    dados.treinos,
    'distancia_media_centro_cm',
    'Distância do centro (cm)',
  );
}

// ----------------------------------------------------------------- abas

function trocarAba(aba) {
  estado.aba = aba;
  for (const botao of document.querySelectorAll('.aba')) {
    botao.classList.toggle('ativa', botao.dataset.aba === aba);
  }
  mostrar(el('painel-treino'), aba === 'treino');
  mostrar(el('painel-historico'), aba === 'historico');
  mostrar(el('painel-comparacao'), aba === 'comparacao');

  recarregarAbaAtual().catch(tratarErro);
}

async function recarregarAbaAtual() {
  if (estado.aba === 'treino') return carregarTreino();
  if (estado.aba === 'historico') return carregarHistorico();
  renderizarSelecaoComparacao();
  return carregarComparacao();
}

// ---------------------------------------------------------------- erros

function tratarErro(erro) {
  console.error(erro);
  mostrar(el('treinoCarregando'), false);

  if (erro instanceof ErroDaApi && erro.status === 401) {
    window.location.href = './login.html';
    return;
  }
  if (erro instanceof ErroDaApi && erro.status === 0) {
    mostrarErro(
      '<strong>Servidor de análise indisponível.</strong> ' +
        'Inicie o backend com <code>uvicorn app.main:app --port 8000</code> ' +
        'dentro da pasta <code>backend/</code>.',
    );
    return;
  }
  if (erro instanceof ErroDaApi && erro.status === 503) {
    mostrarErro(
      `<strong>Sem acesso ao Firestore.</strong> ${erro.message}`,
    );
    return;
  }
  mostrarErro(`<strong>Erro ao carregar.</strong> ${erro.message}`);
}

// ----------------------------------------------------------------- init

async function atualizarTudo() {
  mostrarErro(null);
  await carregarFiltros();
  await recarregarAbaAtual();
}

function ligarEventos() {
  el('btnTema').addEventListener('click', () =>
    aplicarTema(!document.body.classList.contains('dark-mode')),
  );

  el('btnAtualizar').addEventListener('click', async () => {
    try {
      await api.invalidarCache();
      await atualizarTudo();
    } catch (erro) {
      tratarErro(erro);
    }
  });

  for (const botao of document.querySelectorAll('.aba')) {
    botao.addEventListener('click', () => trocarAba(botao.dataset.aba));
  }

  // Mudar um filtro recalcula as opções dos outros, mantendo tudo
  // coerente, e recarrega só a aba visível.
  for (const id of ['fAtleta', 'fDataInicio', 'fDataFim', 'fTipoAlvo', 'fDistancia', 'fSerie']) {
    el(id).addEventListener('change', async () => {
      estado.treinoSelecionado = null;
      try {
        await atualizarTudo();
      } catch (erro) {
        tratarErro(erro);
      }
    });
  }

  el('fTreino').addEventListener('change', () => {
    estado.treinoSelecionado = el('fTreino').value || null;
    carregarTreino().catch(tratarErro);
  });
}

async function iniciar() {
  const usuario = await exigirSessao();
  mostrarUsuario(el('usuarioLogado'), usuario);
  ligarBotaoSair(el('btnSair'));

  restaurarTema();
  graficoAlvo = new GraficoDeAlvo(el('graficoAlvo'), el('tooltipAlvo'));
  ligarEventos();

  // Um treino pode vir indicado na URL, vindo da tela de registro.
  const parametros = new URLSearchParams(window.location.search);
  estado.treinoSelecionado = parametros.get('treino');

  try {
    await atualizarTudo();
  } catch (erro) {
    tratarErro(erro);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', iniciar);
} else {
  iniciar();
}
