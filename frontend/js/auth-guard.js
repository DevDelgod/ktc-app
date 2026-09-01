/**
 * Guarda de autenticação para páginas protegidas.
 *
 * `registro.js` e `dashboard.js` chamam `exigirSessao()` como a
 * primeira coisa que fazem. Sem sessão válida, a função redireciona
 * para `login.html` e **nunca resolve** — o restante do código da
 * página, que vem depois do `await`, simplesmente não roda, porque a
 * navegação já trocou o documento.
 */

import { aguardarEstadoInicial, sair, mensagemDeErro } from './auth.js';

/**
 * Bloqueia até confirmar sessão. Redireciona para o login se não houver.
 *
 * @returns {Promise<object>} o usuário autenticado.
 */
export async function exigirSessao() {
  const usuario = await aguardarEstadoInicial();
  if (usuario) return usuario;

  const destino = window.location.pathname + window.location.search;
  window.location.href = `./login.html?redirect=${encodeURIComponent(destino)}`;
  // Propositalmente nunca resolve: a navegação acima já está a caminho,
  // e não há nada de útil a devolver para um chamador que não vai
  // continuar executando.
  return new Promise(() => {});
}

/** Liga um botão de logout: sai do Firebase e volta para a tela de login. */
export function ligarBotaoSair(elemento) {
  if (!elemento) return;
  elemento.addEventListener('click', async () => {
    elemento.disabled = true;
    try {
      await sair();
      window.location.href = './login.html';
    } catch (erro) {
      elemento.disabled = false;
      window.alert(mensagemDeErro(erro));
    }
  });
}

/** Mostra o e-mail do usuário logado num elemento de texto. */
export function mostrarUsuario(elemento, usuario) {
  if (!elemento || !usuario) return;
  elemento.textContent = usuario.email;
  elemento.title = usuario.email;
}
