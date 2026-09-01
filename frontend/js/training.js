/**
 * Estado do treino e máquina de séries.
 *
 * Substitui as variáveis soltas de módulo do `script.js` original
 * (`flechas`, `flechasScore`, `historicoLocal`, `maxFlechas`,
 * `maxSeries`, `tipoAlvoSelecionado`) e, principalmente, tira o estado
 * de dentro do DOM.
 *
 * No aplicativo original os campos do formulário ERAM a fonte da
 * verdade: `avancarProximaSerie()` mudava a série escrevendo no
 * `<select>`, e cada função de persistência relia o DOM na hora de
 * salvar. Aqui o estado é um objeto, e o DOM apenas o reflete.
 *
 * As regras de negócio são as mesmas: dois tempos (T1 e T2), número de
 * séries e de flechas configurável, série fechada só com a contagem
 * exata.
 */

import { PADROES } from './config.js';
import { nomeDoAlvoAtivo } from './targets.js';

/** Gera o ID padrão do treino: TR-DDMM-HHMM. Formato preservado. */
export function gerarIdTreino(agora = new Date()) {
  const p = (valor) => String(valor).padStart(2, '0');
  return `TR-${p(agora.getDate())}${p(agora.getMonth() + 1)}-${p(agora.getHours())}${p(
    agora.getMinutes(),
  )}`;
}

/** Data de hoje no formato aceito por <input type="date">. */
export function dataDeHoje(agora = new Date()) {
  const p = (valor) => String(valor).padStart(2, '0');
  return `${agora.getFullYear()}-${p(agora.getMonth() + 1)}-${p(agora.getDate())}`;
}

export class Treino {
  constructor() {
    this.reiniciar();
  }

  reiniciar({ manterAtleta = false } = {}) {
    const atleta = manterAtleta ? this.atleta : '';

    this.idTreino = gerarIdTreino();
    this.atleta = atleta || '';
    this.dataTreino = dataDeHoje();
    this.tempo = PADROES.tempo;
    this.serie = PADROES.serie;
    this.distancia = PADROES.distancia;
    this.clima = 'Sol';
    this.vVento = '';
    this.dVento = 'Norte';
    this.valorSelectAlvo = '';
    this.seriesPorRodada = PADROES.seriesPorRodada;
    this.flechasPorSerie = PADROES.flechasPorSerie;

    this.flechas = [];
    this.pontos = [];
    this.seriesEnviadas = new Map();
    this.iniciado = false;
  }

  /** Nome do alvo que vai para o banco. Regra preservada do original. */
  get tipoAlvo() {
    return nomeDoAlvoAtivo(this.distancia, this.valorSelectAlvo);
  }

  /** Chave da série no histórico local: `T1-S3`. */
  get chaveSerie() {
    return `${this.tempo}-S${this.serie}`;
  }

  /** Dados que as funções de persistência precisam. */
  get sessao() {
    return {
      idTreino: this.idTreino,
      atleta: this.atleta,
      dataTreino: this.dataTreino,
      tempo: this.tempo,
      serie: this.serie,
      distancia: this.distancia,
      clima: this.clima,
      vVento: this.vVento,
      dVento: this.dVento,
      tipoAlvo: this.tipoAlvo,
      seriesPorRodada: this.seriesPorRodada,
    };
  }

  /** Aplica os limites do formato, truncando o que já passou do novo limite. */
  definirFormato({ seriesPorRodada, flechasPorSerie }) {
    const series = parseInt(seriesPorRodada, 10);
    const flechas = parseInt(flechasPorSerie, 10);

    this.seriesPorRodada =
      Number.isNaN(series) || series < 1 ? PADROES.seriesPorRodada : series;
    this.flechasPorSerie =
      Number.isNaN(flechas) || flechas < 1 ? PADROES.flechasPorSerie : flechas;

    if (this.flechas.length > this.flechasPorSerie) {
      this.flechas = this.flechas.slice(0, this.flechasPorSerie);
    }
    if (this.pontos.length > this.flechasPorSerie) {
      this.pontos = this.pontos.slice(0, this.flechasPorSerie);
    }
  }

  /** O que falta para iniciar o treino. Vazio significa pronto. */
  validarInicio() {
    const faltando = [];
    if (!this.idTreino.trim()) faltando.push('ID do treino');
    if (!this.atleta.trim()) faltando.push('nome do atleta');
    return faltando;
  }

  get alvoCompleto() {
    return this.flechas.length === this.flechasPorSerie;
  }

  get pontuacaoCompleta() {
    return this.pontos.length === this.flechasPorSerie;
  }

  /** Registra a série enviada no histórico da sessão. */
  registrarEnvio(total) {
    this.seriesEnviadas.set(this.chaveSerie, {
      chave: this.chaveSerie,
      tempo: this.tempo,
      serie: this.serie,
      total,
      flechas: this.flechas.length,
      pontos: [...this.pontos],
    });
  }

  removerEnvio(chave) {
    this.seriesEnviadas.delete(chave);
  }

  /** Zera a série corrente, mantendo a configuração do treino. */
  limparSerie() {
    this.flechas = [];
    this.pontos = [];
  }

  /**
   * Avança para a próxima série.
   *
   * Máquina de estados idêntica à do `avancarProximaSerie()` original:
   * dentro do T1 incrementa; no fim do T1 salta para T2-S1; dentro do T2
   * incrementa; no fim do T2 o treino acabou.
   *
   * @returns {'proxima-serie'|'novo-tempo'|'treino-concluido'}
   */
  avancar() {
    if (this.serie < this.seriesPorRodada) {
      this.serie += 1;
      this.limparSerie();
      return 'proxima-serie';
    }

    if (this.tempo === 'T1') {
      this.tempo = 'T2';
      this.serie = 1;
      this.limparSerie();
      return 'novo-tempo';
    }

    return 'treino-concluido';
  }
}
