/**
 * Gráfico de dispersão desenhado sobre o alvo real.
 *
 * Não é um scatter plot genérico: os anéis são os do alvo que o atleta
 * de fato usou, com os raios e as cores do aplicativo. Um agrupamento
 * só significa alguma coisa quando se vê contra a face correta — e as
 * duas geometrias do KTC não são iguais, então o alvo triplo desenha
 * suas três faces.
 *
 * Sobre o alvo aparecem:
 *   · cada flecha, colorida pelo anel em que caiu;
 *   · o centro do alvo (cruz);
 *   · o centro do agrupamento (losango), que é a média das posições;
 *   · o raio que contém 95% do grupo, quando há flechas suficientes.
 *
 * A distância entre a cruz e o losango é a leitura visual da tendência:
 * o quanto o atleta está deslocado, e para que lado.
 */

import { ESPACO_LOGICO, comCores } from './targets.js';

const COR_FLECHA_BORDA = '#111111';
const RAIO_FLECHA = 5;

export class GraficoDeAlvo {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {HTMLElement} tooltip
   */
  constructor(canvas, tooltip) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.tooltip = tooltip;
    this.geometria = null;
    this.disparos = [];
    this.centroGrupo = null;
    this.raio95 = null;
    this.destaque = null;
    this._pontosNaTela = [];

    this._ligarEventos();
  }

  definirDados({ geometria, disparos, centroGrupo, raio95, agrupamentoPorFace }) {
    // A geometria da API traz raio e nível, mas não cor — ela é
    // preenchida aqui, na camada de desenho.
    this.geometria = comCores(geometria);
    this.disparos = disparos || [];
    this.centroGrupo = centroGrupo || null;
    this.raio95 = raio95 ?? null;
    // Só usado para alvo multiface (Alvo Triplo): um centro de grupo por
    // face real, em vez de uma origem única fictícia — ver correção de
    // calibração em `_desenharCentroDoGrupo`.
    this.agrupamentoPorFace = agrupamentoPorFace || [];
    this.desenhar();
  }

  /** Escala e origem: mesmo esquema do canvas de registro. */
  _metricas() {
    const rect = this.canvas.getBoundingClientRect();
    const lado = rect.width || 420;
    return { lado, centro: lado / 2, ratio: lado / ESPACO_LOGICO };
  }

  desenhar() {
    if (!this.geometria) return;

    const dpr = window.devicePixelRatio || 1;
    const { lado, centro, ratio } = this._metricas();

    this.canvas.width = lado * dpr;
    this.canvas.height = lado * dpr;

    // Só escreve a altura quando ela realmente muda. Reescrever a cada
    // desenho altera o layout, que pode fazer a barra de rolagem
    // aparecer e sumir, disparando `resize` de novo — um laço.
    const alturaCss = `${Math.round(lado)}px`;
    if (this.canvas.style.height !== alturaCss) {
      this.canvas.style.height = alturaCss;
    }

    const ctx = this.ctx;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, lado, lado);

    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, lado, lado);

    for (const face of this.geometria.centros) {
      this._desenharFace(face, centro, ratio);
    }

    this._desenharDispersao(centro, ratio);
    this._desenharFlechas(centro, ratio);
    this._desenharCentroDoGrupo(centro, ratio);
  }

  _paraTela(x, y, centro, ratio) {
    // Y invertido: o dado guarda "para cima" positivo, a tela cresce
    // para baixo.
    return { px: centro + x * ratio, py: centro - y * ratio };
  }

  _desenharFace(face, centro, ratio) {
    const ctx = this.ctx;
    const { px, py } = this._paraTela(face.x, face.y, centro, ratio);
    const aneis = [...this.geometria.aneis].sort((a, b) => b.raio - a.raio);

    for (const anel of aneis) {
      ctx.beginPath();
      ctx.arc(px, py, anel.raio * ratio, 0, 2 * Math.PI);
      ctx.fillStyle = anel.cor;
      ctx.fill();
    }

    for (const anel of aneis) {
      ctx.beginPath();
      ctx.arc(px, py, anel.raio * ratio, 0, 2 * Math.PI);
      const escuro = anel.nivel === 3 || anel.nivel === 4;
      ctx.strokeStyle = escuro ? 'rgba(255,255,255,.85)' : 'rgba(0,0,0,.75)';
      ctx.lineWidth = escuro ? 0.8 : 1;
      ctx.stroke();
    }

    // Centro do alvo: a referência de precisão.
    const braco = 7;
    ctx.beginPath();
    ctx.moveTo(px - braco, py);
    ctx.lineTo(px + braco, py);
    ctx.moveTo(px, py - braco);
    ctx.lineTo(px, py + braco);
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 1.4;
    ctx.stroke();
  }

  /** Círculo que contém 95% das flechas em torno do centro do grupo. */
  _desenharDispersao(centro, ratio) {
    if (this.geometria.multiface) {
      // Alvo com várias faces: um círculo por face, só onde há flechas
      // suficientes para o raio significar algo.
      for (const grupo of this.agrupamentoPorFace) {
        if (grupo.raio_95 == null || grupo.quantidade < 3) continue;
        this._desenharCirculoDispersao(
          grupo.face_x + grupo.centro_x,
          grupo.face_y + grupo.centro_y,
          grupo.raio_95,
          centro,
          ratio,
        );
      }
      return;
    }

    if (!this.centroGrupo || !this.raio95 || this.disparos.length < 3) return;
    const face = this.geometria.centros[0];
    this._desenharCirculoDispersao(
      face.x + this.centroGrupo.x,
      face.y + this.centroGrupo.y,
      this.raio95,
      centro,
      ratio,
    );
  }

  _desenharCirculoDispersao(x, y, raio, centro, ratio) {
    const { px, py } = this._paraTela(x, y, centro, ratio);
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.arc(px, py, raio * ratio, 0, 2 * Math.PI);
    ctx.strokeStyle = 'rgba(41, 128, 185, .95)';
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 5]);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  _desenharFlechas(centro, ratio) {
    const ctx = this.ctx;
    this._pontosNaTela = [];

    this.disparos.forEach((disparo, indice) => {
      const { px, py } = this._paraTela(disparo.x, disparo.y, centro, ratio);
      const destacado = this.destaque === indice;
      const raio = destacado ? RAIO_FLECHA + 2.5 : RAIO_FLECHA;

      ctx.beginPath();
      ctx.arc(px, py, raio, 0, 2 * Math.PI);
      ctx.fillStyle = destacado ? '#2ecc71' : 'rgba(46, 204, 113, .92)';
      ctx.fill();
      ctx.strokeStyle = COR_FLECHA_BORDA;
      ctx.lineWidth = destacado ? 2 : 1.2;
      ctx.stroke();

      this._pontosNaTela.push({ px, py, indice });
    });
  }

  /**
   * Losango do centro do grupo — para não confundir com a cruz do
   * centro do alvo.
   *
   * Correção de calibração: um alvo multiface (Alvo Triplo) tem três
   * faces em posições físicas diferentes (y = +95, 0, -95). Antes, o
   * centro do grupo era sempre desenhado numa origem fictícia (0, 0),
   * que não corresponde a nenhuma face real — um grupo de flechas na
   * face de cima fazia o losango aparecer 95 unidades abaixo de onde as
   * flechas realmente estavam (confirmado por teste de pixel). Agora
   * desenha-se um losango por face, na posição real daquela face.
   */
  _desenharCentroDoGrupo(centro, ratio) {
    if (this.geometria.multiface) {
      for (const grupo of this.agrupamentoPorFace) {
        if (grupo.quantidade < 2) continue;
        this._desenharLosango(
          grupo.face_x + grupo.centro_x,
          grupo.face_y + grupo.centro_y,
          centro,
          ratio,
        );
      }
      return;
    }

    if (!this.centroGrupo || this.disparos.length < 2) return;
    const face = this.geometria.centros[0];
    this._desenharLosango(face.x + this.centroGrupo.x, face.y + this.centroGrupo.y, centro, ratio);
  }

  _desenharLosango(x, y, centro, ratio) {
    const { px, py } = this._paraTela(x, y, centro, ratio);
    const ctx = this.ctx;
    const lado = 8;
    ctx.beginPath();
    ctx.moveTo(px, py - lado);
    ctx.lineTo(px + lado, py);
    ctx.lineTo(px, py + lado);
    ctx.lineTo(px - lado, py);
    ctx.closePath();
    ctx.fillStyle = '#2980b9';
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // -------------------------------------------------------- interação

  _ligarEventos() {
    this.canvas.addEventListener('mousemove', (evento) => this._aoMover(evento));
    this.canvas.addEventListener('mouseleave', () => this._esconderTooltip());
    this.canvas.addEventListener('touchstart', (evento) => {
      if (evento.touches.length === 1) this._aoMover(evento.touches[0]);
    }, { passive: true });

    // O redesenho por redimensionamento é agendado num quadro de
    // animação e nunca se acumula, para que uma sequência rápida de
    // eventos produza um único desenho.
    let agendado = false;
    window.addEventListener('resize', () => {
      if (agendado) return;
      agendado = true;
      window.requestAnimationFrame(() => {
        agendado = false;
        this.desenhar();
      });
    });
  }

  _aoMover(evento) {
    const rect = this.canvas.getBoundingClientRect();
    const x = evento.clientX - rect.left;
    const y = evento.clientY - rect.top;

    let encontrado = null;
    let menor = 14; // raio de tolerância do ponteiro, em pixels
    for (const ponto of this._pontosNaTela) {
      const distancia = Math.hypot(ponto.px - x, ponto.py - y);
      if (distancia < menor) {
        menor = distancia;
        encontrado = ponto;
      }
    }

    if (!encontrado) {
      this._esconderTooltip();
      return;
    }

    if (this.destaque !== encontrado.indice) {
      this.destaque = encontrado.indice;
      this.desenhar();
    }
    this._mostrarTooltip(this.disparos[encontrado.indice], encontrado);
  }

  _mostrarTooltip(disparo, ponto) {
    if (!this.tooltip) return;

    const pontos = disparo.rotulo ?? '—';
    const linhas = [
      `<strong>Flecha ${disparo.flecha} · ${disparo.tempo}-S${disparo.serie}</strong>`,
      `Pontuação: ${pontos}`,
      `Distância do centro: ${Number(disparo.distancia_centro_cm).toFixed(1)} cm`,
      `Posição: (${Number(disparo.x).toFixed(1)}, ${Number(disparo.y).toFixed(1)})`,
    ];

    // Divergência entre o digitado e o anel onde a flecha caiu.
    if (disparo.rotulo && disparo.rotulo !== disparo.rotulo_geometrico) {
      linhas.push(`<em>Marcado no anel ${disparo.rotulo_geometrico}</em>`);
    }

    this.tooltip.innerHTML = linhas.join('<br>');
    this.tooltip.classList.remove('oculto');

    const largura = this.tooltip.offsetWidth;
    const esquerda = Math.min(
      Math.max(ponto.px - largura / 2, 4),
      this.canvas.clientWidth - largura - 4,
    );
    this.tooltip.style.left = `${esquerda}px`;
    this.tooltip.style.top = `${ponto.py + 16}px`;
  }

  _esconderTooltip() {
    if (this.destaque !== null) {
      this.destaque = null;
      this.desenhar();
    }
    this.tooltip?.classList.add('oculto');
  }
}
