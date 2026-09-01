/**
 * Persistência de competições no Firestore.
 *
 * Coleção **separada** de `treinos` — `competicoes`, não misturada com
 * dados de treino, como pedido. A forma do disparo é idêntica à do
 * treino (flecha, x, y, score): por isso o Canvas e o teclado de
 * pontuação do registro comum são reaproveitados sem alteração para
 * gravar flechas de competição — só o destino no Firestore muda.
 *
 * Reaproveita de `firebase.js`: a instância do Firestore (`db`), o
 * timeout de operação (`comTimeout`) e a checagem de configuração
 * (`verificarConfiguracao`) — mesmas garantias contra travamento
 * silencioso que a gravação de treino já tem.
 *
 * Estrutura:
 *
 *   competicoes/{competicaoId}
 *     nome, atleta, data, local, categoria, modalidade,
 *     tipoAlvo, distancia, status, criadoEm, atualizadoEm, finalizadoEm
 *
 *     /series/{competicaoId}-{provaSlug}-S{numero}
 *       competicaoId, prova, numero, atleta, tipoAlvo, distancia,
 *       flechasString, total, criadoEm, atualizadoEm
 *
 *       /disparos/F{1..n}
 *         flecha, x, y, score, tipoAlvo, tipo_alvo
 */

import {
  comTimeout,
  db,
  deleteDoc,
  doc,
  serverTimestamp,
  setDoc,
  verificarConfiguracao,
  calcularTotal,
} from './firebase.js';

export { calcularTotal };

export const COLECAO_COMPETICOES = 'competicoes';
export const SUBCOLECAO_SERIES = 'series';
export const SUBCOLECAO_DISPAROS = 'disparos';

export const STATUS_PLANEJADA = 'planejada';
export const STATUS_EM_ANDAMENTO = 'em_andamento';
export const STATUS_PAUSADA = 'pausada';
export const STATUS_CONCLUIDA = 'concluida';

/** ID legível: CP-DDMM-HHMM. Mesmo padrão de `gerarIdTreino()`. */
export function gerarIdCompeticao(agora = new Date()) {
  const p = (v) => String(v).padStart(2, '0');
  return `CP-${p(agora.getDate())}${p(agora.getMonth() + 1)}-${p(agora.getHours())}${p(agora.getMinutes())}`;
}

/** Transforma o nome da prova num trecho de ID estável e legível. */
export function slugDaProva(nomeProva) {
  // ̀-ͯ = marcas diacríticas combinantes, isoladas pelo NFD
  // ("á" -> "a" + acento separado, que este regex então remove).
  const semAcento = (nomeProva || 'prova').normalize('NFD').replace(/[̀-ͯ]/g, '');
  const slug = semAcento
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || 'prova';
}

export function idDocumentoSerieCompeticao(competicaoId, prova, numero) {
  return `${competicaoId}-${slugDaProva(prova)}-S${numero}`;
}

function refCompeticao(competicaoId) {
  return doc(db, COLECAO_COMPETICOES, competicaoId);
}

function refSerie(competicaoId, docId) {
  return doc(db, COLECAO_COMPETICOES, competicaoId, SUBCOLECAO_SERIES, docId);
}

function refDisparo(competicaoId, docId, numero) {
  return doc(db, COLECAO_COMPETICOES, competicaoId, SUBCOLECAO_SERIES, docId, SUBCOLECAO_DISPAROS, `F${numero}`);
}

/**
 * Cria a competição — o passo "CRIAR COMPETIÇÃO" do fluxo.
 *
 * Só grava metadados; nenhuma série existe ainda. Status inicial
 * "planejada".
 */
export async function criarCompeticao(dados) {
  verificarConfiguracao();
  const id = dados.id || gerarIdCompeticao();

  await comTimeout(
    setDoc(refCompeticao(id), {
      nome: dados.nome,
      atleta: dados.atleta,
      data: dados.data,
      local: dados.local || '',
      categoria: dados.categoria || '',
      modalidade: dados.modalidade || '',
      tipoAlvo: dados.tipoAlvo,
      tipo_alvo: dados.tipoAlvo,
      distancia: dados.distancia,
      status: STATUS_PLANEJADA,
      criadoEm: serverTimestamp(),
      atualizadoEm: serverTimestamp(),
    }),
    'Criar a competição',
  );

  return id;
}

/** Muda o status — "planejada" → "em_andamento" → "pausada"/"concluida". */
export async function atualizarStatusCompeticao(competicaoId, status) {
  verificarConfiguracao();
  const dados = { status, atualizadoEm: serverTimestamp() };
  if (status === STATUS_CONCLUIDA) {
    dados.finalizadoEm = serverTimestamp();
  }
  await comTimeout(
    setDoc(refCompeticao(competicaoId), dados, { merge: true }),
    'Atualizar status da competição',
  );
}

/**
 * Grava as coordenadas das flechas de uma série de competição.
 *
 * Mesma forma de dado e mesma estratégia de `{ merge: true }` que
 * `salvarAlvo` usa para treino — reconfirmar o alvo de uma série já
 * pontuada não apaga a pontuação.
 */
export async function salvarAlvoCompeticao(sessao, flechas) {
  verificarConfiguracao();
  const docId = idDocumentoSerieCompeticao(sessao.competicaoId, sessao.prova, sessao.numero);

  await comTimeout(
    setDoc(
      refSerie(sessao.competicaoId, docId),
      {
        competicaoId: sessao.competicaoId,
        prova: sessao.prova,
        numero: sessao.numero,
        atleta: sessao.atleta,
        tipoAlvo: sessao.tipoAlvo,
        tipo_alvo: sessao.tipoAlvo,
        distancia: sessao.distancia,
        criadoEm: serverTimestamp(),
      },
      { merge: true },
    ),
    'Salvar a série da competição',
  );

  await comTimeout(
    Promise.all(
      flechas.map((flecha, indice) => {
        const numero = indice + 1;
        return setDoc(
          refDisparo(sessao.competicaoId, docId, numero),
          {
            idDisparo: `${docId}-F${numero}`,
            flecha: numero,
            x: Number(flecha.xRel.toFixed(2)),
            y: Number(flecha.yRel.toFixed(2)),
            tipoAlvo: sessao.tipoAlvo,
            tipo_alvo: sessao.tipoAlvo,
          },
          { merge: true },
        );
      }),
    ),
    'Salvar os disparos da competição',
  );

  return docId;
}

/** Grava a pontuação da série e carimba o `score` em cada disparo. */
export async function salvarPontuacaoCompeticao(sessao, pontos) {
  verificarConfiguracao();
  const docId = idDocumentoSerieCompeticao(sessao.competicaoId, sessao.prova, sessao.numero);
  const total = calcularTotal(pontos);

  await comTimeout(
    setDoc(
      refSerie(sessao.competicaoId, docId),
      {
        competicaoId: sessao.competicaoId,
        prova: sessao.prova,
        numero: sessao.numero,
        atleta: sessao.atleta,
        flechasString: pontos.join(' '),
        total,
        atualizadoEm: serverTimestamp(),
      },
      { merge: true },
    ),
    'Salvar a pontuação da competição',
  );

  await comTimeout(
    Promise.all(
      pontos.map((rotulo, indice) =>
        setDoc(refDisparo(sessao.competicaoId, docId, indice + 1), { score: rotulo }, { merge: true }),
      ),
    ),
    'Registrar a pontuação nos disparos da competição',
  );

  await comTimeout(
    setDoc(refCompeticao(sessao.competicaoId), { atualizadoEm: serverTimestamp() }, { merge: true }),
    'Atualizar a competição',
  );

  return { docId, total };
}
