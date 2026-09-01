/**
 * Configuração compartilhada do frontend.
 *
 * A configuração do Firebase NÃO entra aqui: ela vive em
 * `firebase-config.js` (não versionado) e é importada apenas por
 * `firebase.js`. Assim o dashboard, que lê tudo pela API Python, não
 * depende de credencial nenhuma para carregar.
 */

/**
 * Base da API analítica.
 *
 * Vazio significa "mesma origem", que é o caso quando o backend FastAPI
 * serve o frontend. Em desenvolvimento com servidores separados, defina
 * `window.KTC_API_BASE` antes de carregar os módulos.
 */
export const API_BASE = window.KTC_API_BASE ?? '';

/** Versão do SDK Firebase carregado do CDN. */
export const VERSAO_FIREBASE = '12.12.1';

/** Padrões do formulário de treino, iguais aos do aplicativo original. */
export const PADROES = {
  seriesPorRodada: 6,
  flechasPorSerie: 6,
  distancia: '70m',
  tempo: 'T1',
  serie: 1,
};

/** Tempos de rodada suportados. Preservado do aplicativo original. */
export const TEMPOS = ['T1', 'T2'];
