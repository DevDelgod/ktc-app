"""Testes dos endpoints de competição via HTTP."""

from __future__ import annotations

import os

os.environ["SERVE_FRONTEND"] = "0"
os.environ["CACHE_TTL"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import definir_servico_competicoes, definir_verificador  # noqa: E402
from app.auth import ErroDeAutenticacao  # noqa: E402
from app.main import app  # noqa: E402
from app.services.competition_service import ServicoCompeticoes  # noqa: E402
from tests.test_competition import FonteCompeticoesFalsa, _competicao_basica  # noqa: E402

TOKEN_VALIDO = "token-de-teste-valido"


def _verificador_falso(token: str) -> dict:
    if token != TOKEN_VALIDO:
        raise ErroDeAutenticacao("token de teste inválido")
    return {"uid": "usuario-de-teste"}


@pytest.fixture
def cliente():
    fonte = _competicao_basica()
    definir_servico_competicoes(ServicoCompeticoes(fonte, ttl_cache=0))
    definir_verificador(_verificador_falso)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN_VALIDO}"}) as c:
        yield c
    definir_servico_competicoes(None)
    definir_verificador(None)


class TestAutenticacao:
    def test_rotas_de_competicao_exigem_token(self):
        definir_servico_competicoes(ServicoCompeticoes(_competicao_basica(), ttl_cache=0))
        definir_verificador(_verificador_falso)
        with TestClient(app) as sem_token:
            resposta = sem_token.get("/api/competitions")
        definir_servico_competicoes(None)
        definir_verificador(None)
        assert resposta.status_code == 401


class TestListagemEConsulta:
    def test_lista_competicoes(self, cliente):
        corpo = cliente.get("/api/competitions").json()
        assert corpo["quantidade"] == 1
        assert corpo["competicoes"][0]["nome"] == "Campeonato Brasileiro"

    def test_consultar_competicao_traz_progresso(self, cliente):
        corpo = cliente.get("/api/competitions/CP-TESTE").json()
        assert corpo["competicao"]["nome"] == "Campeonato Brasileiro"
        assert corpo["serie_atual"]["numero"] == 4
        assert corpo["score_total"] > 0

    def test_competicao_inexistente_devolve_404(self, cliente):
        resposta = cliente.get("/api/competitions/NAO-EXISTE")
        assert resposta.status_code == 404


class TestAnalyticsEShotsEReport:
    def test_analytics_completo(self, cliente):
        corpo = cliente.get("/api/competitions/CP-TESTE/analytics").json()
        assert corpo["pontuacao"]["quantidade_flechas"] == 24
        assert corpo["pontuacao"]["melhor_serie"]["rotulo"] == "Classificação-S4"

    def test_shots_trazem_coordenadas_para_o_alvo(self, cliente):
        corpo = cliente.get("/api/competitions/CP-TESTE/shots").json()
        assert len(corpo["disparos"]) == 24
        assert corpo["geometria"]["nome"]
        disparo = corpo["disparos"][0]
        for campo in ("x", "y", "dx", "dy", "distancia_centro_cm", "rotulo"):
            assert campo in disparo

    def test_relatorio_final_completo(self, cliente):
        corpo = cliente.get("/api/competitions/CP-TESTE/report").json()
        assert corpo["resumo"]["nome"] == "Campeonato Brasileiro"
        assert corpo["destaques"]["melhor_pontuacao"] is not None
        assert corpo["pontos_de_atencao"]["pior_pontuacao"] is not None
        assert isinstance(corpo["analise_final"], str) and len(corpo["analise_final"]) > 0

    def test_analytics_de_competicao_inexistente_devolve_404(self, cliente):
        assert cliente.get("/api/competitions/NAO/analytics").status_code == 404
        assert cliente.get("/api/competitions/NAO/shots").status_code == 404
        assert cliente.get("/api/competitions/NAO/report").status_code == 404

    def test_invalidar_cache(self, cliente):
        assert cliente.post("/api/competitions/cache/invalidar").status_code == 200
