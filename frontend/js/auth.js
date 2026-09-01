/**
 * Autenticação por e-mail e senha.
 *
 * Usa a mesma instância de app do Firestore (`firebase-init.js`), para
 * que Auth e Firestore operem sobre o mesmo projeto. O login acontece
 * inteiramente no cliente — o backend nunca vê e-mail nem senha, só o
 * ID Token resultante, que verifica sem depender de rede a cada chamada
 * (ver `backend/app/auth.py`).
 */

import { VERSAO_FIREBASE } from './config.js';
import { app, configuracaoAusente, ErroDeConfiguracao } from './firebase-init.js';

const BASE_CDN = `https://www.gstatic.com/firebasejs/${VERSAO_FIREBASE}`;

const {
  getAuth,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
} = await import(`${BASE_CDN}/firebase-auth.js`);

export { ErroDeConfiguracao };

const auth = getAuth(app);

/** Traduz os códigos de erro do Firebase Auth para mensagens em português. */
const MENSAGENS_DE_ERRO = {
  'auth/invalid-email': 'E-mail em formato inválido.',
  'auth/user-disabled': 'Esta conta foi desativada.',
  'auth/user-not-found': 'E-mail ou senha incorretos.',
  'auth/wrong-password': 'E-mail ou senha incorretos.',
  'auth/invalid-credential': 'E-mail ou senha incorretos.',
  'auth/too-many-requests': 'Muitas tentativas. Aguarde alguns minutos e tente de novo.',
  'auth/network-request-failed': 'Sem conexão com o Firebase. Verifique a rede.',
  'auth/configuration-not-found':
    'Login por e-mail/senha não está habilitado no Firebase Console ' +
    '(Authentication → Sign-in method).',
};

export function mensagemDeErro(erro) {
  return MENSAGENS_DE_ERRO[erro?.code] || erro?.message || 'Erro desconhecido ao entrar.';
}

/** Faz login. Lança erro com mensagem já traduzida em `.message`. */
export async function entrar(email, senha) {
  if (configuracaoAusente()) throw new ErroDeConfiguracao();
  try {
    const credencial = await signInWithEmailAndPassword(auth, email, senha);
    return credencial.user;
  } catch (erro) {
    const traduzido = new Error(mensagemDeErro(erro));
    traduzido.code = erro.code;
    throw traduzido;
  }
}

export async function sair() {
  await signOut(auth);
}

/** Usuário logado agora, ou `null`. Só é confiável após `aguardarEstadoInicial()`. */
export function usuarioAtual() {
  return auth.currentUser;
}

/**
 * O SDK carrega a sessão do armazenamento local de forma assíncrona.
 * Ler `auth.currentUser` antes desse carregamento terminar sempre
 * devolve `null`, mesmo com uma sessão válida salva — por isso todo
 * ponto de entrada da aplicação espera este sinal antes de decidir se
 * redireciona para o login.
 */
export function aguardarEstadoInicial() {
  return new Promise((resolve) => {
    const cancelar = onAuthStateChanged(auth, (usuario) => {
      cancelar();
      resolve(usuario);
    });
  });
}

export function aoMudarAutenticacao(callback) {
  return onAuthStateChanged(auth, callback);
}

/**
 * Token para autorizar chamadas à API Python (`Authorization: Bearer`).
 *
 * `getIdToken()` devolve o token em cache e o renova sozinho quando
 * está perto de expirar — seguro chamar a cada requisição.
 */
export async function obterIdToken() {
  const usuario = auth.currentUser;
  if (!usuario) return null;
  return usuario.getIdToken();
}
