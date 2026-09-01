/**
 * Renderização do alvo e captura de coordenadas.
 *
 * A matemática aqui é transplantada literalmente do `script.js`
 * original (`desenharAlvo`, `desenharFlechas`, `getCanvasCoordinates` e
 * os listeners de click/touchstart). Nada foi "melhorado": qualquer
 * mudança na conversão de coordenadas tornaria o histórico já gravado
 * incompatível com os dados novos, sem erro visível.
 *
 * O que mudou é só o empacotamento — de variáveis soltas de módulo para
 * uma classe com estado explícito.
 */

import { ESPACO_LOGICO } from './targets.js';

/** Divisor do slider de zoom. Faixa 300–1200 vira 0,6x–2,4x. */
export const ZOOM_BASE = 500;

export class AlvoCanvas {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {{aoMarcar?: (flecha: {xRel: number, yRel: number}) => void}} opcoes
   */
  constructor(canvas, opcoes = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.dpr = window.devicePixelRatio || 1;
    this.zoom = 1;
    this.flechas = [];
    this.geometria = null;
    this.limiteFlechas = 6;
    this.aoMarcar = opcoes.aoMarcar || (() => {});

    this._ligarEventos();
  }

  /** Dimensiona o canvas considerando a densidade de pixels da tela. */
  dimensionar() {
    const rect = this.canvas.getBoundingClientRect();
    // Quando o canvas está oculto o rect vem zerado; o fallback de 400
    // é o mesmo do código original.
    const largura = rect.width || this.canvas.offsetWidth || 400;
    const altura = rect.height || this.canvas.offsetHeight || largura;

    this.canvas.width = largura * this.dpr;
    this.canvas.height = altura * this.dpr;
    this.canvas.style.width = '100%';
    this.canvas.style.height = 'auto';
  }

  definirGeometria(geometria) {
    this.geometria = geometria;
    this.desenhar();
  }

  definirLimite(limite) {
    this.limiteFlechas = limite;
    if (this.flechas.length > limite) {
      this.flechas = this.flechas.slice(0, limite);
    }
    this.desenhar();
  }

  definirZoom(valorDoSlider) {
    this.zoom = Number(valorDoSlider) / ZOOM_BASE;
    this.desenhar();
  }

  definirFlechas(flechas) {
    this.flechas = [...flechas];
    this.desenhar();
  }

  limpar() {
    this.flechas = [];
    this.desenhar();
  }

  desfazer() {
    this.flechas.pop();
    this.desenhar();
  }

  get cheio() {
    return this.flechas.length >= this.limiteFlechas;
  }

  /**
   * Redesenha o alvo inteiro.
   *
   * Observação preservada do original: o centro vertical usa
   * `larguraLogica / 2`, não a altura. Desenho e captura usam a mesma
   * convenção, então as coordenadas ficam corretas mesmo quando o
   * elemento não é perfeitamente quadrado.
   */
  desenhar() {
    if (!this.geometria) return;

    const rect = this.canvas.getBoundingClientRect();
    const larguraLogica = rect.width || this.canvas.width / this.dpr || 400;
    const alturaLogica = rect.height || this.canvas.height / this.dpr || larguraLogica;

    if (rect.width > 0 && rect.height > 0) {
      this.canvas.width = larguraLogica * this.dpr;
      this.canvas.height = alturaLogica * this.dpr;
    }

    const ctx = this.ctx;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.scale(this.dpr, this.dpr);

    const centro = larguraLogica / 2;
    const ratio = larguraLogica / ESPACO_LOGICO;
    // A espessura é pré-dividida pelo zoom para que a linha mantenha a
    // mesma grossura na tela depois do ctx.scale.
    const traco = 2 / this.zoom;
    const tracoFino = 1 / this.zoom;

    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, larguraLogica, alturaLogica);

    ctx.save();
    ctx.translate(centro, centro);
    ctx.scale(this.zoom, this.zoom);
    ctx.translate(-centro, -centro);

    for (const face of this.geometria.centros) {
      this._desenharFace(face, centro, ratio, traco, tracoFino);
    }
    this._desenharFlechas(centro, ratio);

    ctx.restore();
  }

  _desenharFace(face, centro, ratio, traco, tracoFino) {
    const ctx = this.ctx;
    const xVis = centro + face.x * ratio;
    const yVis = centro - face.y * ratio;

    // Preenchimento do maior para o menor, para que os anéis internos
    // fiquem por cima.
    for (const anel of this.geometria.aneis) {
      ctx.beginPath();
      ctx.arc(xVis, yVis, anel.raio * ratio, 0, 2 * Math.PI);
      ctx.fillStyle = anel.cor;
      ctx.fill();
    }

    // Contornos. Os anéis 3 e 4 são pretos, então recebem traço branco
    // para continuarem visíveis.
    for (const anel of this.geometria.aneis) {
      ctx.beginPath();
      ctx.arc(xVis, yVis, anel.raio * ratio, 0, 2 * Math.PI);
      if (anel.nivel === 3 || anel.nivel === 4) {
        ctx.strokeStyle = 'white';
        ctx.lineWidth = tracoFino;
      } else {
        ctx.strokeStyle = 'black';
        ctx.lineWidth = traco;
      }
      ctx.stroke();
    }

    const cruz = 3;
    ctx.beginPath();
    ctx.moveTo(xVis - cruz, yVis);
    ctx.lineTo(xVis + cruz, yVis);
    ctx.moveTo(xVis, yVis - cruz);
    ctx.lineTo(xVis, yVis + cruz);
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = traco;
    ctx.stroke();
  }

  _desenharFlechas(centro, ratio) {
    const ctx = this.ctx;
    this.flechas.forEach((flecha, indice) => {
      const xVis = centro + flecha.xRel * ratio;
      const yVis = centro - flecha.yRel * ratio;

      ctx.beginPath();
      ctx.arc(xVis, yVis, 2.5 * ratio, 0, 2 * Math.PI);
      ctx.fillStyle = '#2ecc71';
      ctx.fill();
      ctx.strokeStyle = '#000000';
      ctx.lineWidth = 1 * ratio;
      ctx.stroke();

      // Cruz de precisão: marca o centro real do impacto.
      ctx.beginPath();
      ctx.moveTo(xVis - 6 * ratio, yVis);
      ctx.lineTo(xVis + 6 * ratio, yVis);
      ctx.moveTo(xVis, yVis - 6 * ratio);
      ctx.lineTo(xVis, yVis + 6 * ratio);
      ctx.strokeStyle = '#000000';
      ctx.lineWidth = 1 * ratio;
      ctx.stroke();

      ctx.fillStyle = '#000000';
      ctx.font = `bold ${9 * ratio}px Arial`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      ctx.fillText(String(indice + 1), xVis, yVis - 8 * ratio);
    });
  }

  /**
   * Converte um evento de ponteiro em coordenadas do alvo.
   *
   * Três etapas, na ordem exata do código original:
   *   1. tela -> canvas:  x = clientX - rect.left
   *   2. desfaz o zoom:   x = centro + (x - centro) / zoom
   *   3. pixels -> unidades, com Y invertido
   */
  _coordenadasDoEvento(evento) {
    const rect = this.canvas.getBoundingClientRect();
    const clientX = evento.clientX !== undefined ? evento.clientX : evento.touches[0].clientX;
    const clientY = evento.clientY !== undefined ? evento.clientY : evento.touches[0].clientY;

    // O centro horizontal é usado nos dois eixos, como no original.
    const centro = rect.width / 2;
    const ratio = rect.width / ESPACO_LOGICO;

    let x = clientX - rect.left;
    let y = clientY - rect.top;

    x = centro + (x - centro) / this.zoom;
    y = centro + (y - centro) / this.zoom;

    return {
      xRel: (x - centro) / ratio,
      yRel: (centro - y) / ratio,
    };
  }

  _registrar(evento) {
    if (this.cheio) return;
    const flecha = this._coordenadasDoEvento(evento);
    // Clique pode chegar com o canvas ainda display:none (transição entre
    // séries) — nesse instante rect.width é 0 e a divisão vira NaN/Infinity.
    // Ignorar em vez de gravar uma coordenada inválida.
    if (!Number.isFinite(flecha.xRel) || !Number.isFinite(flecha.yRel)) return;
    this.flechas.push(flecha);
    this.desenhar();
    this.aoMarcar(flecha);
  }

  _ligarEventos() {
    this.canvas.addEventListener('click', (evento) => this._registrar(evento));
    this.canvas.addEventListener(
      'touchstart',
      (evento) => {
        // Suprime o clique sintético que o navegador dispara depois do
        // toque, evitando registrar a mesma flecha duas vezes.
        evento.preventDefault();
        this._registrar(evento);
      },
      { passive: false },
    );
  }
}
