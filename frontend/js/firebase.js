/**
 * Persistência no Firestore.
 *
 * O formato dos documentos é **idêntico** ao do aplicativo original: os
 * mesmos IDs (`{idTreino}-{tempo}-S{serie}` e `F{n}`), os mesmos campos,
 * a mesma subcoleção. Dados novos e antigos continuam indistinguíveis
 * para quem lê.
 *
 * Duas mudanças deliberadas, ambas aditivas e documentadas:
 *
 * 1. A gravação do alvo passou a usar `{ merge: true }`. Antes era um
 *    `setDoc` sem merge, que substituía o documento inteiro: reconfirmar
 *    o alvo de uma série já pontuada apagava `total`, `distancia` e
 *    `flechasString`. Com merge, nada é perdido e nenhum campo deixa de
 *    ser escrito.
 *
 * 2. Cada disparo passa a receber o campo `score`. Antes, a ligação
 *    entre a flecha marcada e o ponto digitado só existia por posição na
 *    `flechasString`. O campo torna essa ligação explícita, sem quebrar
 *    a leitura dos registros antigos — o backend continua sabendo
 *    reconstruí-la por posição quando o campo não existe.
 *
 * 3. Toda gravação passa por `comTimeout()` (definido abaixo). O SDK do
 *    Firestore, quando a configuração é inválida (projeto inexistente,
 *    apiKey vazia), entra num estado interno de detecção de
 *    conectividade que fica retentando indefinidamente — a Promise do
 *    `setDoc` nunca resolve NEM rejeita, sem nenhuma requisição de rede
 *    sequer ser tentada. Sem esse limite, a UI ficava presa para sempre
 *    em "Salvando o alvo no Firebase...", sem erro algum para capturar.
 */

import { VERSAO_FIREBASE } from './config.js';
import { app, configuracaoAusente, ErroDeConfiguracao } from './firebase-init.js';

export { ErroDeConfiguracao };

const BASE_CDN = `https://www.gstatic.com/firebasejs/${VERSAO_FIREBASE}`;

const { getFirestore, doc, setDoc, deleteDoc, serverTimestamp } = await import(
  `${BASE_CDN}/firebase-firestore.js`
);

export { doc, setDoc, deleteDoc, serverTimestamp };

export class ErroDeTimeout extends Error {
  constructor(operacao) {
    super(
      `${operacao} não respondeu em 15s. Causas prováveis: Regras de Segurança do ` +
        'Firestore bloqueando a operação, projeto/credenciais incorretos, ou rede ' +
        'indisponível. Nenhum erro foi devolvido pelo SDK — verifique o Firestore Console.',
    );
    this.name = 'ErroDeTimeout';
  }
}

export const db = getFirestore(app);

export const COLECAO_SERIES = 'treinos';
export const SUBCOLECAO_DISPAROS = 'disparos';

const TIMEOUT_OPERACAO_MS = 15000;

/**
 * Corre uma operação do Firestore com um limite de tempo.
 *
 * Não é um `setTimeout` para esconder o loading: se a operação real
 * terminar primeiro (sucesso ou erro), é o resultado dela que vale — o
 * timeout só entra em ação quando a Promise do SDK genuinamente nunca
 * se resolve, transformando o silêncio em um erro explícito e
 * diagnosticável, que o `try/catch` já existente na tela sabe tratar.
 */
export function comTimeout(promessa, operacao) {
  return Promise.race([
    promessa,
    new Promise((_, reject) => {
      setTimeout(() => reject(new ErroDeTimeout(operacao)), TIMEOUT_OPERACAO_MS);
    }),
  ]);
}

export function verificarConfiguracao() {
  if (configuracaoAusente()) {
    throw new ErroDeConfiguracao();
  }
}

/**
 * ID do documento da série.
 * Formato preservado do original — é a identidade de todo registro.
 */
export function idDocumentoSerie(idTreino, tempo, serie) {
  return `${idTreino}-${tempo}-S${serie}`;
}

function refSerie(docId) {
  return doc(db, COLECAO_SERIES, docId);
}

function refDisparo(docId, numeroFlecha) {
  return doc(db, COLECAO_SERIES, docId, SUBCOLECAO_DISPAROS, `F${numeroFlecha}`);
}

/**
 * Ordem cronológica absoluta da série dentro do treino.
 *
 * O código original somava 6 fixo no T2, ignorando quantas séries a
 * rodada realmente tem — com 3 séries por rodada, T2-S1 virava 7 em vez
 * de 4. Aqui a soma usa o número real de séries.
 */
export function calcularSerieGlobal(tempo, serie, seriesPorRodada) {
  const numero = parseInt(serie, 10);
  return tempo === 'T1' ? numero : numero + parseInt(seriesPorRodada, 10);
}

/**
 * Grava as coordenadas das flechas de uma série.
 *
 * @param {object} sessao  metadados do treino
 * @param {Array<{xRel:number, yRel:number}>} flechas
 */
export async function salvarAlvo(sessao, flechas) {
  verificarConfiguracao();

  const docId = idDocumentoSerie(sessao.idTreino, sessao.tempo, sessao.serie);

  await comTimeout(
    setDoc(
      refSerie(docId),
      {
        idTreino: sessao.idTreino,
        dataTreino: sessao.dataTreino,
        atleta: sessao.atleta,
        tempo: sessao.tempo,
        serie: String(sessao.serie),
        serieGlobal: calcularSerieGlobal(sessao.tempo, sessao.serie, sessao.seriesPorRodada),
        v_vento: sessao.vVento || '0',
        d_vento: sessao.dVento,
        clima: sessao.clima,
        distancia: sessao.distancia,
        tipo_alvo: sessao.tipoAlvo,
        tipoAlvo: sessao.tipoAlvo,
        createdAt: serverTimestamp(),
      },
      { merge: true },
    ),
    'Salvar a série',
  );

  await comTimeout(
    Promise.all(
      flechas.map((flecha, indice) => {
        const numero = indice + 1;
        return setDoc(
          refDisparo(docId, numero),
          {
            idDisparo: `${docId}-F${numero}`,
            flecha: numero,
            // Duas casas decimais, como no original. A conversão para
            // número acontece aqui; o banco guarda number, não string.
            x: Number(flecha.xRel.toFixed(2)),
            y: Number(flecha.yRel.toFixed(2)),
            v_vento: sessao.vVento || '0',
            d_vento: sessao.dVento,
            clima: sessao.clima,
            tipo_alvo: sessao.tipoAlvo,
            tipoAlvo: sessao.tipoAlvo,
          },
          { merge: true },
        );
      }),
    ),
    'Salvar os disparos',
  );

  return docId;
}

/**
 * Grava a pontuação da série e carimba o `score` em cada disparo.
 *
 * O total é calculado com a regra do aplicativo: X vale 10, M vale 0.
 */
export async function salvarPontuacao(sessao, pontos) {
  verificarConfiguracao();

  const docId = idDocumentoSerie(sessao.idTreino, sessao.tempo, sessao.serie);
  const total = calcularTotal(pontos);

  await comTimeout(
    setDoc(
      refSerie(docId),
      {
        idTreino: sessao.idTreino,
        dataTreino: sessao.dataTreino,
        atleta: sessao.atleta,
        distancia: sessao.distancia,
        flechasString: pontos.join(' '),
        total,
        clima: sessao.clima,
        v_vento: sessao.vVento || '0',
        d_vento: sessao.dVento,
        tipo_alvo: sessao.tipoAlvo,
        tipoAlvo: sessao.tipoAlvo,
        updatedAt: serverTimestamp(),
      },
      { merge: true },
    ),
    'Salvar a pontuação',
  );

  // Carimba o ponto de cada flecha no seu próprio documento.
  await comTimeout(
    Promise.all(
      pontos.map((rotulo, indice) =>
        setDoc(refDisparo(docId, indice + 1), { score: rotulo }, { merge: true }),
      ),
    ),
    'Registrar a pontuação nos disparos',
  );

  return { docId, total };
}

/** Soma dos pontos de uma série. X = 10, M = 0. */
export function calcularTotal(pontos) {
  return pontos.reduce((soma, valor) => {
    if (valor === 'X') return soma + 10;
    if (valor === 'M') return soma;
    const numero = parseInt(valor, 10);
    return soma + (Number.isNaN(numero) ? 0 : numero);
  }, 0);
}

/** Apaga uma série inteira: os disparos e o documento da série. */
export async function excluirSerie(idTreino, tempo, serie, quantidadeFlechas) {
  verificarConfiguracao();

  const docId = idDocumentoSerie(idTreino, tempo, serie);
  const exclusoes = [];
  for (let numero = 1; numero <= quantidadeFlechas; numero += 1) {
    exclusoes.push(deleteDoc(refDisparo(docId, numero)));
  }
  await comTimeout(Promise.all(exclusoes), 'Excluir os disparos');
  await comTimeout(deleteDoc(refSerie(docId)), 'Excluir a série');
  return docId;
}
