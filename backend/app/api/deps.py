"""Dependências compartilhadas pelas rotas."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Callable

from fastapi import Depends, Header, HTTPException, Query, status

from app.auth import ErroDeAutenticacao, verificar_id_token
from app.firebase.client import FirebaseIndisponivel, cliente_firestore
from app.services.analytics_service import Filtros, ServicoAnalitico
from app.services.competition_repository import FirestoreCompeticoes
from app.services.competition_service import ServicoCompeticoes
from app.services.repository import FirestoreAdmin

# Instância única do serviço, para que o cache de leitura seja
# compartilhado entre requisições. Substituída em teste por override.
_servico: ServicoAnalitico | None = None
_servico_competicoes: ServicoCompeticoes | None = None


@lru_cache(maxsize=1)
def _construir_servico() -> ServicoAnalitico:
    return ServicoAnalitico(FirestoreAdmin(cliente_firestore()))


@lru_cache(maxsize=1)
def _construir_servico_competicoes() -> ServicoCompeticoes:
    return ServicoCompeticoes(FirestoreCompeticoes(cliente_firestore()))


def obter_servico() -> ServicoAnalitico:
    global _servico
    if _servico is not None:
        return _servico
    try:
        return _construir_servico()
    except FirebaseIndisponivel as erro:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)
        ) from erro


def obter_servico_competicoes() -> ServicoCompeticoes:
    global _servico_competicoes
    if _servico_competicoes is not None:
        return _servico_competicoes
    try:
        return _construir_servico_competicoes()
    except FirebaseIndisponivel as erro:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)
        ) from erro


def definir_servico_competicoes(servico: ServicoCompeticoes | None) -> None:
    """Injeta um serviço pronto. Usado nos testes."""
    global _servico_competicoes
    _servico_competicoes = servico
    _construir_servico_competicoes.cache_clear()


def definir_servico(servico: ServicoAnalitico | None) -> None:
    """Injeta um serviço pronto. Usado nos testes."""
    global _servico
    _servico = servico
    _construir_servico.cache_clear()


def obter_filtros(
    atleta: str | None = Query(None, description="Nome do atleta (comparação insensível a caixa)"),
    data_inicio: date | None = Query(None, description="Data inicial, inclusive (YYYY-MM-DD)"),
    data_fim: date | None = Query(None, description="Data final, inclusive (YYYY-MM-DD)"),
    tipo_alvo: str | None = Query(None, description="Ex.: 'Alvo Triplo'"),
    familia_alvo: str | None = Query(None, description="'simples' ou 'tripla'"),
    distancia: str | None = Query(None, description="Ex.: '18m', '70m'"),
    tempo: str | None = Query(None, description="'T1' ou 'T2'"),
    serie: int | None = Query(None, ge=1, description="Número da série dentro da rodada"),
) -> Filtros:
    return Filtros(
        atleta=atleta,
        data_inicio=data_inicio,
        data_fim=data_fim,
        tipo_alvo=tipo_alvo,
        familia_alvo=familia_alvo,
        distancia=distancia,
        tempo=tempo,
        serie=serie,
    )


ServicoDep = Depends(obter_servico)
FiltrosDep = Depends(obter_filtros)


# ---------------------------------------------------------------- auth

# Ponto de substituição para teste: injeta um verificador falso em vez
# de bater no Firebase Auth real a cada caso de teste.
_verificador: Callable[[str], dict] | None = None


def definir_verificador(verificador: Callable[[str], dict] | None) -> None:
    global _verificador
    _verificador = verificador


def obter_usuario_atual(authorization: str | None = Header(default=None)) -> dict:
    """Exige um ID Token válido do Firebase no cabeçalho Authorization.

    O frontend anexa `Bearer <idToken>` em toda chamada à API depois do
    login. Sem cabeçalho, cabeçalho malformado ou token que não verifica
    (expirado, de outro projeto, adulterado), a requisição é recusada
    antes de tocar em qualquer dado — a autenticação é a primeira porta,
    não uma checagem posterior.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token de autenticação ausente. Faça login novamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token de autenticação vazio. Faça login novamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    verificar = _verificador or verificar_id_token
    try:
        return verificar(token)
    except ErroDeAutenticacao as erro:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sessão expirada ou inválida. Faça login novamente.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from erro


UsuarioDep = Depends(obter_usuario_atual)
ServicoCompeticoesDep = Depends(obter_servico_competicoes)
