/**
 * Pontuação da série.
 *
 * Regra preservada do aplicativo original: X vale 10, M vale 0, o resto
 * vale o próprio número. A pontuação continua sendo digitada pelo
 * atleta — o aplicativo nunca derivou o ponto da posição da flecha, e
 * isso não muda aqui.
 *
 * A novidade é o confronto: como a geometria dos anéis está disponível,
 * o teclado agora consegue sugerir qual anel a flecha atingiu e avisar
 * quando o valor digitado diverge da marcação. É um aviso, nunca uma
 * correção automática — quem decide é o atleta.
 */

import { distanciaDoCentro } from './targets.js';

/** Teclas do numpad, na ordem em que aparecem na tela. */
export const TECLAS = [
  { valor: 'X', classe: 'amarelo' },
  { valor: '10', classe: 'amarelo' },
  { valor: '9', classe: 'vermelho' },
  { valor: '8', classe: 'vermelho' },
  { valor: '7', classe: 'azul' },
  { valor: '6', classe: 'azul' },
  { valor: '5', classe: 'preto' },
  { valor: '4', classe: 'preto' },
  { valor: '3', classe: 'branco' },
  { valor: '2', classe: 'branco' },
  { valor: '1', classe: 'branco' },
  { valor: 'M', classe: 'miss' },
];

/** Pontos de um rótulo. Devolve null se o símbolo não for reconhecido. */
export function pontosDoRotulo(rotulo) {
  if (rotulo === 'X') return 10;
  if (rotulo === 'M') return 0;
  const numero = parseInt(rotulo, 10);
  return Number.isNaN(numero) ? null : numero;
}

/** Soma de uma lista de rótulos. */
export function somar(pontos) {
  return pontos.reduce((soma, rotulo) => soma + (pontosDoRotulo(rotulo) ?? 0), 0);
}

/**
 * Rótulo do anel atingido por uma flecha, segundo a geometria do alvo.
 *
 * O anel válido é o de menor raio que ainda contém o ponto. Fora do
 * alvo devolve 'M'.
 */
export function rotuloGeometrico(flecha, geometria) {
  const distancia = distanciaDoCentro(flecha.xRel, flecha.yRel, geometria);
  const ordenados = [...geometria.aneis].sort((a, b) => a.raio - b.raio);
  for (const anel of ordenados) {
    if (distancia <= anel.raio) {
      return anel.nivel === 11 ? 'X' : String(anel.nivel);
    }
  }
  return 'M';
}

/**
 * Compara o digitado com o marcado, flecha a flecha.
 *
 * Devolve uma lista paralela a `pontos`, em que cada item diz se aquela
 * flecha confere. Alimenta o aviso visual do teclado.
 */
export function conferir(pontos, flechas, geometria) {
  return pontos.map((rotulo, indice) => {
    const flecha = flechas[indice];
    if (!flecha) return { rotulo, sugerido: null, confere: null };

    const sugerido = rotuloGeometrico(flecha, geometria);
    const digitados = pontosDoRotulo(rotulo);
    const sugeridos = pontosDoRotulo(sugerido);
    return {
      rotulo,
      sugerido,
      confere: digitados !== null && digitados === sugeridos,
    };
  });
}
