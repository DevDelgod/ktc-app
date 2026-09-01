"""Verificação de identidade via Firebase Authentication.

O frontend autentica o usuário com o Firebase Auth (e-mail/senha) e anexa
o ID Token resultante em cada chamada à API, no cabeçalho
`Authorization: Bearer <token>`. Este módulo verifica esse token contra
o mesmo projeto Firebase do backend, usando o Admin SDK — a verificação
é criptográfica, não uma consulta de rede a cada chamada.

Nenhuma credencial de usuário passa pelo backend: o login acontece
inteiramente no cliente, contra o Firebase. O backend só confirma que o
token apresentado é genuíno e não expirou.
"""

from __future__ import annotations


class ErroDeAutenticacao(Exception):
    """Token ausente, malformado, expirado ou de projeto diferente."""


def verificar_id_token(token: str) -> dict:
    """Verifica um ID Token do Firebase e devolve as claims decodificadas.

    Levanta `ErroDeAutenticacao` para qualquer token inválido — a
    mensagem original do Admin SDK é preservada para diagnóstico, mas
    nunca é exposta como 500: quem chama converte isto em 401.
    """
    from firebase_admin import auth as firebase_auth

    try:
        return firebase_auth.verify_id_token(token)
    except Exception as erro:  # noqa: BLE001 — qualquer falha de verificação vira 401
        raise ErroDeAutenticacao(str(erro)) from erro
