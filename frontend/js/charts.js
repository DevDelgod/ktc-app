/**
 * Gráficos do dashboard.
 *
 * Chart.js foi escolhido por ser leve, interativo por padrão, com
 * tooltip e responsividade prontos — e por não exigir build. Os
 * gráficos que precisam da geometria do alvo (dispersão sobre a face)
 * NÃO usam biblioteca: são desenhados em Canvas por `target-plot.js`,
 * porque nenhuma biblioteca genérica sabe desenhar um alvo triplo com
 * as três faces nos lugares certos.
 *
 * As cores vêm dos tokens do KTC, para que os gráficos pareçam parte do
 * aplicativo e não um painel administrativo qualquer.
 */

const graficos = new Map();

function token(nome, alternativa) {
  const valor = getComputedStyle(document.body).getPropertyValue(nome).trim();
  return valor || alternativa;
}

/** Paleta lida do CSS, para acompanhar o tema claro/escuro. */
function paleta() {
  return {
    azul: token('--azul', '#2980b9'),
    verde: token('--verde', '#27ae60'),
    laranja: token('--laranja', '#f39c12'),
    vermelho: token('--vermelho', '#e74c3c'),
    texto: token('--text-sub', '#555555'),
    grade: token('--border', '#dddddd'),
    fundo: token('--bg-card', '#ffffff'),
  };
}

function baseDeOpcoes() {
  const cores = paleta();
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        labels: { color: cores.texto, boxWidth: 12, font: { size: 11 } },
      },
      tooltip: {
        backgroundColor: 'rgba(20,20,20,.92)',
        padding: 10,
        titleFont: { size: 12 },
        bodyFont: { size: 12 },
      },
    },
    scales: {
      x: {
        ticks: { color: cores.texto, font: { size: 10 } },
        grid: { color: cores.grade, drawBorder: false },
      },
      y: {
        ticks: { color: cores.texto, font: { size: 10 } },
        grid: { color: cores.grade, drawBorder: false },
      },
    },
  };
}

/** Cria ou substitui um gráfico no canvas indicado. */
function renderizar(id, configuracao) {
  const canvas = document.getElementById(id);
  if (!canvas || typeof window.Chart === 'undefined') return null;

  graficos.get(id)?.destroy();
  const grafico = new window.Chart(canvas, configuracao);
  graficos.set(id, grafico);
  return grafico;
}

export function destruirTodos() {
  for (const grafico of graficos.values()) grafico.destroy();
  graficos.clear();
}

/** Redesenha todos os gráficos — usado ao trocar o tema. */
export function repintarTodos() {
  for (const grafico of graficos.values()) {
    const cores = paleta();
    grafico.options.plugins.legend.labels.color = cores.texto;
    grafico.options.scales.x.ticks.color = cores.texto;
    grafico.options.scales.y.ticks.color = cores.texto;
    grafico.options.scales.x.grid.color = cores.grade;
    grafico.options.scales.y.grid.color = cores.grade;
    grafico.update('none');
  }
}

/** Score de cada série, na ordem cronológica real do treino. */
export function scorePorSerie(id, series) {
  const cores = paleta();
  const opcoes = baseDeOpcoes();
  opcoes.plugins.legend.display = false;
  opcoes.scales.y.beginAtZero = true;

  return renderizar(id, {
    type: 'bar',
    data: {
      labels: series.map((s) => s.rotulo),
      datasets: [
        {
          label: 'Score da série',
          data: series.map((s) => s.total),
          backgroundColor: series.map((s) =>
            s.finalizada ? cores.azul : 'rgba(149,165,166,.55)',
          ),
          borderRadius: 6,
        },
      ],
    },
    options: opcoes,
  });
}

/** Quantas flechas caíram em cada anel. */
export function distribuicao(id, distribuicaoDeRotulos) {
  const cores = paleta();
  const opcoes = baseDeOpcoes();
  opcoes.plugins.legend.display = false;
  opcoes.scales.y.beginAtZero = true;
  opcoes.scales.y.ticks.precision = 0;

  const itens = distribuicaoDeRotulos.filter((d) => d.rotulo !== 'sem pontuação');

  return renderizar(id, {
    type: 'bar',
    data: {
      labels: itens.map((d) => d.rotulo),
      datasets: [
        {
          label: 'Flechas',
          data: itens.map((d) => d.quantidade),
          backgroundColor: itens.map((d) => corDoRotulo(d.rotulo, cores)),
          borderRadius: 5,
        },
      ],
    },
    options: opcoes,
  });
}

/** Cor de cada rótulo, seguindo as cores dos anéis do alvo. */
function corDoRotulo(rotulo, cores) {
  if (rotulo === 'X' || rotulo === '10' || rotulo === '9') return '#f1c40f';
  if (rotulo === '8' || rotulo === '7') return cores.vermelho;
  if (rotulo === '6' || rotulo === '5') return '#3498db';
  if (rotulo === 'M') return '#95a5a6';
  return '#7f8c8d';
}

/** Distância de cada flecha ao centro, na ordem em que foram atiradas. */
export function distanciaDoCentro(id, disparos) {
  const cores = paleta();
  const opcoes = baseDeOpcoes();
  opcoes.scales.y.beginAtZero = true;
  opcoes.scales.y.title = {
    display: true,
    text: 'centímetros do centro',
    color: cores.texto,
    font: { size: 10 },
  };
  opcoes.plugins.tooltip.callbacks = {
    title: (itens) => `Flecha ${itens[0].label}`,
    label: (item) => `${Number(item.raw).toFixed(1)} cm do centro`,
  };

  return renderizar(id, {
    type: 'line',
    data: {
      labels: disparos.map((d) => `${d.tempo}-S${d.serie}·F${d.flecha}`),
      datasets: [
        {
          label: 'Distância do centro',
          data: disparos.map((d) => d.distancia_centro_cm),
          borderColor: cores.azul,
          backgroundColor: 'rgba(41,128,185,.14)',
          fill: true,
          tension: 0.28,
          pointRadius: 2.5,
          pointHoverRadius: 5,
        },
      ],
    },
    options: opcoes,
  });
}

/** Consistência: score por série contra a média do treino. */
export function consistencia(id, series, media) {
  const cores = paleta();
  const opcoes = baseDeOpcoes();
  opcoes.scales.y.beginAtZero = true;

  return renderizar(id, {
    type: 'line',
    data: {
      labels: series.map((s) => s.rotulo),
      datasets: [
        {
          label: 'Score da série',
          data: series.map((s) => s.total),
          borderColor: cores.verde,
          backgroundColor: 'rgba(39,174,96,.15)',
          fill: true,
          tension: 0.3,
          pointRadius: 4,
        },
        {
          label: 'Média do treino',
          data: series.map(() => media),
          borderColor: cores.laranja,
          borderDash: [7, 5],
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: opcoes,
  });
}

/**
 * Evolução histórica: uma métrica por treino ao longo do tempo.
 * `inverso` marca métricas em que menor é melhor (dispersão, distância).
 */
export function evolucao(id, pontos, chave, rotulo, inverso = false) {
  const cores = paleta();
  const opcoes = baseDeOpcoes();
  opcoes.plugins.tooltip.callbacks = {
    title: (itens) => pontos[itens[0].dataIndex].id_treino,
    label: (item) => `${rotulo}: ${Number(item.raw).toFixed(2)}`,
  };

  return renderizar(id, {
    type: 'line',
    data: {
      labels: pontos.map((p) => p.data_treino ?? p.id_treino),
      datasets: [
        {
          label: rotulo,
          data: pontos.map((p) => p[chave]),
          borderColor: inverso ? cores.laranja : cores.azul,
          backgroundColor: inverso ? 'rgba(243,156,18,.15)' : 'rgba(41,128,185,.15)',
          fill: true,
          tension: 0.3,
          pointRadius: 4,
          pointHoverRadius: 6,
          spanGaps: true,
        },
      ],
    },
    options: opcoes,
  });
}

/** Comparação entre treinos: barras agrupadas por métrica normalizada. */
export function comparacao(id, treinos, chave, rotulo) {
  const cores = paleta();
  const opcoes = baseDeOpcoes();
  opcoes.plugins.legend.display = false;
  opcoes.scales.y.beginAtZero = true;
  opcoes.plugins.tooltip.callbacks = {
    label: (item) => `${rotulo}: ${Number(item.raw).toFixed(2)}`,
  };

  const paletaBarras = [cores.azul, cores.verde, cores.laranja, cores.vermelho, '#8e44ad', '#16a085'];

  return renderizar(id, {
    type: 'bar',
    data: {
      labels: treinos.map((t) => t.id_treino),
      datasets: [
        {
          label: rotulo,
          data: treinos.map((t) => t[chave]),
          backgroundColor: treinos.map((_, i) => paletaBarras[i % paletaBarras.length]),
          borderRadius: 6,
        },
      ],
    },
    options: opcoes,
  });
}
