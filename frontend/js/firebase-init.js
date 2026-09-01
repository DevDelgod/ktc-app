/**
 * Inicialização única do Firebase.
 *
 * `initializeApp()` só pode ser chamado uma vez por app nomeado — uma
 * segunda chamada com o app padrão lança "Firebase App named
 * '[DEFAULT]' already exists". Firestore (`firebase.js`) e
 * Authentication (`auth.js`) precisam da MESMA instância de app para
 * operar sobre o mesmo projeto, então a inicialização mora aqui, num
 * módulo só, e os dois a importam.
 */

import { VERSAO_FIREBASE } from './config.js';
import { firebaseConfig } from './firebase-config.js';

const BASE_CDN = `https://www.gstatic.com/firebasejs/${VERSAO_FIREBASE}`;

const { initializeApp } = await import(`${BASE_CDN}/firebase-app.js`);

/**
 * A configuração ainda está com os valores de exemplo?
 *
 * Compartilhado entre `firebase.js` e `auth.js` — os dois precisam
 * detectar a mesma condição antes de tentar falar com o Firebase.
 */
export function configuracaoAusente() {
  return (
    !firebaseConfig.apiKey ||
    !firebaseConfig.projectId ||
    firebaseConfig.projectId === 'SEU-PROJETO'
  );
}

export class ErroDeConfiguracao extends Error {
  constructor() {
    super(
      'Firebase não configurado. Preencha frontend/js/firebase-config.js com os valores ' +
        'reais do seu projeto (Firebase Console → Configurações do projeto → Seus apps → Web).',
    );
    this.name = 'ErroDeConfiguracao';
  }
}

export const app = initializeApp(firebaseConfig);
