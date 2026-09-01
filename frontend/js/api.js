/**
 * Cliente da API analítica.
 *
 * Toda estatística é calculada no backend Python. Este módulo só
 * transporta: monta a URL, trata o erro e devolve o JSON. Nenhuma
 * métrica é recalculada aqui — o frontend cuida de interação e
 * visualização.
 */

import { API_BASE } from './config.js';
import { obterIdToken } from './auth.js';

export class ErroDaApi extends Error {
  constructor(mensagem, status) {
    super(mensagem);
    this.name = 'ErroDaApi';
    this.status = status;
  }
}

function montarUrl(caminho, parametros = {}) {
  const url = new URL(`${API_BASE}/api${caminho}`, window.location.origin);
  for (const [chave, valor] of Object.entries(parametros)) {
    if (valor === null || valor === undefined || valor === '') continue;
    url.searchParams.set(chave, valor);
  }
  return url;
}

async function buscar(caminho, parametros, opcoes = {}) {
  // Toda rota além de /health exige login (ver backend/app/api/routes.py).
  // `obterIdToken()` devolve `null` sem sessão — a chamada segue sem o
  // cabeçalho e o backend responde 401, tratado abaixo como qualquer
  // outro erro da API.
  const token = await obterIdToken();
  const cabecalhos = { ...(opcoes.headers || {}) };
  if (token) cabecalhos.Authorization = `Bearer ${token}`;

  let resposta;
  try {
    resposta = await fetch(montarUrl(caminho, parametros), { ...opcoes, headers: cabecalhos });
  } catch (erro) {
    throw new ErroDaApi(
      'Não foi possível falar com o servidor de análise. Ele está rodando?',
      0,
    );
  }

  if (resposta.status === 401) {
    throw new ErroDaApi('Sessão expirada. Faça login novamente.', 401);
  }

  if (!resposta.ok) {
    let detalhe = `Erro ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      if (corpo?.detail) detalhe = corpo.detail;
    } catch {
      // Resposta sem corpo JSON — o status já basta.
    }
    throw new ErroDaApi(detalhe, resposta.status);
  }

  return resposta.json();
}

export const api = {
  saude: () => buscar('/health'),

  /** Opções de filtro já restritas pela seleção corrente. */
  filtros: (parametros) => buscar('/filters', parametros),

  atletas: () => buscar('/athletes'),

  treinos: (parametros) => buscar('/trainings', parametros),

  treino: (id, parametros) => buscar(`/trainings/${encodeURIComponent(id)}`, parametros),

  /** Pontuação, dispersão, consistência, distribuição e qualidade. */
  analytics: (id, parametros) =>
    buscar(`/trainings/${encodeURIComponent(id)}/analytics`, parametros),

  /** Disparos individuais + geometria do alvo, para o gráfico. */
  disparos: (id, parametros) =>
    buscar(`/trainings/${encodeURIComponent(id)}/shots`, parametros),

  historico: (parametros) => buscar('/analytics/history', parametros),

  comparacao: (ids, parametros) =>
    buscar('/analytics/comparison', { ...parametros, ids: ids.join(',') }),

  geometria: (tipoAlvo) => buscar(`/targets/${encodeURIComponent(tipoAlvo)}`),

  /**
   * Pede ao backend que releia o Firestore.
   * Chamado ao finalizar um treino, para a análise aparecer na hora.
   */
  invalidarCache: () => buscar('/cache/invalidar', {}, { method: 'POST' }),
};

export const apiCompeticoes = {
  listar: () => buscar('/competitions'),

  /** Metadados + progresso atual (série/flecha corrente, score). */
  obter: (id) => buscar(`/competitions/${encodeURIComponent(id)}`),

  analytics: (id) => buscar(`/competitions/${encodeURIComponent(id)}/analytics`),

  disparos: (id) => buscar(`/competitions/${encodeURIComponent(id)}/shots`),

  /** Relatório final completo — pode ser consultado como prévia a qualquer momento. */
  relatorio: (id) => buscar(`/competitions/${encodeURIComponent(id)}/report`),

  invalidarCache: () => buscar('/competitions/cache/invalidar', {}, { method: 'POST' }),
};
