/**
 * Geometria dos alvos — fonte de verdade do frontend.
 *
 * Estas constantes são exatamente as do `script.js` original (função
 * `desenharAlvo`). Nenhum raio, nível ou centro foi alterado: mudar
 * qualquer número aqui invalidaria silenciosamente todo o histórico já
 * gravado, porque as coordenadas antigas foram capturadas nesta escala.
 *
 * SISTEMA DE COORDENADAS
 * ----------------------
 *   ratio = larguraDoCanvasPx / ESPACO_LOGICO   (ESPACO_LOGICO = 300)
 *   x = (px - centro) / ratio
 *   y = (centro - py) / ratio        <- Y positivo para CIMA
 *
 * Origem no centro do canvas. O anel externo do alvo simples tem raio
 * 150, metade de 300 — o alvo ocupa a largura inteira por construção.
 */

/** Largura do espaço lógico do alvo, em unidades. */
export const ESPACO_LOGICO = 300;

/** Metade do espaço lógico — raio máximo desenhável. */
export const RAIO_MAXIMO = ESPACO_LOGICO / 2;

/** Nomes gravados no Firestore. Três strings, duas geometrias. */
export const NOME_UNITARIO = 'Alvo Unitário'; // usado fora dos 18m
export const NOME_UNICO = 'Alvo Único';       // 18m, face simples
export const NOME_TRIPLO = 'Alvo Triplo';     // 18m, três faces

/** Valores do <select> de tipo de alvo. */
export const VALOR_SIMPLES = 'indoor_18_single';
export const VALOR_TRIPLO = 'indoor_18_triplo';

/**
 * Alvo simples: 11 anéis, raios 150 -> 7,5.
 * O nível corresponde à pontuação; o nível 11 é o X e vale 10.
 */
export const ANEIS_SIMPLES = [
  { raio: 150, cor: '#FFFFFF', nivel: 1 },
  { raio: 135, cor: '#FFFFFF', nivel: 2 },
  { raio: 120, cor: '#202020', nivel: 3 },
  { raio: 105, cor: '#202020', nivel: 4 },
  { raio: 90, cor: '#00B4E4', nivel: 5 },
  { raio: 75, cor: '#00B4E4', nivel: 6 },
  { raio: 60, cor: '#FF0000', nivel: 7 },
  { raio: 45, cor: '#FF0000', nivel: 8 },
  { raio: 30, cor: '#FFE500', nivel: 9 },
  { raio: 15, cor: '#FFE500', nivel: 10 },
  { raio: 7.5, cor: '#FFE500', nivel: 11 },
];

/**
 * Alvo triplo: 6 anéis por face, raios 45 -> 4,5.
 * É exatamente o miolo do alvo simples reduzido a 60%.
 */
export const ANEIS_TRIPLO = [
  { raio: 45, cor: '#00B4E4', nivel: 6 },
  { raio: 36, cor: '#FF0000', nivel: 7 },
  { raio: 27, cor: '#FF0000', nivel: 8 },
  { raio: 18, cor: '#FFE500', nivel: 9 },
  { raio: 9, cor: '#FFE500', nivel: 10 },
  { raio: 4.5, cor: '#FFE500', nivel: 11 },
];

/** Centros das faces do alvo triplo, empilhadas na vertical. */
export const CENTROS_TRIPLO = [
  { x: 0, y: 95 },
  { x: 0, y: 0 },
  { x: 0, y: -95 },
];

export const CENTROS_SIMPLES = [{ x: 0, y: 0 }];

/** Diâmetro real da face, usado só para converter unidades em cm. */
const DIAMETRO_CM = { simples: 122, tripla: 40 };

/**
 * Descreve a geometria a partir do nome gravado no banco.
 * 'Alvo Unitário' e 'Alvo Único' devolvem a mesma coisa.
 */
export function geometriaPorNome(nomeAlvo) {
  if (nomeAlvo === NOME_TRIPLO) {
    return {
      nome: NOME_TRIPLO,
      familia: 'tripla',
      aneis: ANEIS_TRIPLO,
      centros: CENTROS_TRIPLO,
      raioExterno: 45,
      diametroCm: DIAMETRO_CM.tripla,
      multiface: true,
    };
  }
  return {
    nome: nomeAlvo || NOME_UNITARIO,
    familia: 'simples',
    aneis: ANEIS_SIMPLES,
    centros: CENTROS_SIMPLES,
    raioExterno: 150,
    diametroCm: DIAMETRO_CM.simples,
    multiface: false,
  };
}

/** Geometria a partir do valor do <select> do formulário. */
export function geometriaPorValorSelect(valor) {
  return geometriaPorNome(valor === VALOR_TRIPLO ? NOME_TRIPLO : NOME_UNICO);
}

/**
 * Resolve o nome do alvo que vai para o banco.
 *
 * Regra transplantada de `obterTipoAlvoAtivo()` e `ativarTreino()`:
 * fora dos 18m é sempre 'Alvo Unitário'; nos 18m depende do seletor.
 * Preservada exatamente para não quebrar a leitura dos dados antigos.
 */
export function nomeDoAlvoAtivo(distancia, valorSelect) {
  if (distancia !== '18m') return NOME_UNITARIO;
  return valorSelect === VALOR_TRIPLO ? NOME_TRIPLO : NOME_UNICO;
}

/**
 * Cor de cada anel, indexada pelo nível.
 *
 * O nível é o mesmo em qualquer alvo — o anel 9 é dourado tanto no alvo
 * simples quanto no triplo — então o mapa serve para as duas
 * geometrias. É a ponte entre a geometria que vem da API (que carrega
 * raio e nível, mas não cor, porque cor é apresentação) e o desenho.
 */
export const COR_POR_NIVEL = {
  1: '#FFFFFF',
  2: '#FFFFFF',
  3: '#202020',
  4: '#202020',
  5: '#00B4E4',
  6: '#00B4E4',
  7: '#FF0000',
  8: '#FF0000',
  9: '#FFE500',
  10: '#FFE500',
  11: '#FFE500',
};

/**
 * Devolve a geometria com as cores preenchidas.
 *
 * A API entrega os anéis sem cor. Sem esta etapa o desenho pinta tudo
 * de branco, porque `fillStyle` recebe `undefined` e o canvas mantém a
 * cor anterior.
 */
export function comCores(geometria) {
  return {
    ...geometria,
    aneis: geometria.aneis.map((anel) => ({
      ...anel,
      cor: anel.cor ?? COR_POR_NIVEL[anel.nivel] ?? '#FFFFFF',
    })),
  };
}

/** Centro da face mais próxima de um ponto. */
export function centroMaisProximo(x, y, centros) {
  let melhor = centros[0];
  let menor = Infinity;
  for (const centro of centros) {
    const d = Math.hypot(x - centro.x, y - centro.y);
    if (d < menor) {
      menor = d;
      melhor = centro;
    }
  }
  return melhor;
}

/** Distância do disparo ao centro da sua face, em unidades do alvo. */
export function distanciaDoCentro(x, y, geometria) {
  const centro = centroMaisProximo(x, y, geometria.centros);
  return Math.hypot(x - centro.x, y - centro.y);
}

/** Converte unidades do alvo em centímetros, calibrando pelo raio externo. */
export function unidadesParaCm(valor, geometria) {
  return valor * ((geometria.diametroCm / 2) / geometria.raioExterno);
}

/** Cor de referência do anel atingido — usada para colorir os pontos do gráfico. */
export function corDoAnel(x, y, geometria) {
  const distancia = distanciaDoCentro(x, y, geometria);
  const ordenados = [...geometria.aneis].sort((a, b) => a.raio - b.raio);
  for (const anel of ordenados) {
    if (distancia <= anel.raio) return anel.cor;
  }
  return null;
}
