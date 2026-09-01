"""Testes dos endpoints da API.

O serviço analítico é injetado com a fonte de dados sintética, de modo
que as rotas são exercitadas de ponta a ponta sem tocar no Firestore.
Da mesma forma, a verificação de token é substituída por um verificador
falso: os testes exercitam a lógica de autorização (cabeçalho presente,
token aceito/rejeitado) sem depender do Firebase Auth real.
"""

from __future__ import annotations

import os

# Precisa vir antes de importar a aplicação: o frontend estático não é
# necessário nestes testes e a configuração é lida na criação do app.
os.environ["SERVE_FRONTEND"] = "0"
os.environ["CACHE_TTL"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import definir_servico, definir_verificador  # noqa: E402
from app.auth import ErroDeAutenticacao  # noqa: E402
from app.main import app  # noqa: E402

TOKEN_VALIDO = "token-de-teste-valido"


def _verificador_falso(token: str) -> dict:
    if token != TOKEN_VALIDO:
        raise ErroDeAutenticacao("token de teste inválido")
    return {"uid": "usuario-de-teste", "email": "teste@ktc.local"}


@pytest.fixture
def cliente(servico_misto):
    definir_servico(servico_misto)
    definir_verificador(_verificador_falso)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN_VALIDO}"}) as c:
        yield c
    definir_servico(None)
    definir_verificador(None)


class TestAutenticacao:
    """`/api/health` é público; todo o resto exige um token válido."""

    def test_health_nao_exige_token(self, servico_misto):
        definir_servico(servico_misto)
        definir_verificador(_verificador_falso)
        with TestClient(app) as sem_header:
            assert sem_header.get("/api/health").status_code == 200
        definir_servico(None)
        definir_verificador(None)

    def test_rota_protegida_sem_cabecalho_devolve_401(self, servico_misto):
        definir_servico(servico_misto)
        definir_verificador(_verificador_falso)
        with TestClient(app) as sem_header:
            resposta = sem_header.get("/api/athletes")
        definir_servico(None)
        definir_verificador(None)
        assert resposta.status_code == 401
        assert "WWW-Authenticate" in resposta.headers

    def test_rota_protegida_com_token_invalido_devolve_401(self, servico_misto):
        definir_servico(servico_misto)
        definir_verificador(_verificador_falso)
        with TestClient(app, headers={"Authorization": "Bearer token-forjado"}) as c:
            resposta = c.get("/api/athletes")
        definir_servico(None)
        definir_verificador(None)
        assert resposta.status_code == 401

    def test_cabecalho_sem_bearer_devolve_401(self, servico_misto):
        definir_servico(servico_misto)
        definir_verificador(_verificador_falso)
        with TestClient(app, headers={"Authorization": TOKEN_VALIDO}) as c:
            resposta = c.get("/api/athletes")
        definir_servico(None)
        definir_verificador(None)
        assert resposta.status_code == 401

    def test_rota_protegida_com_token_valido_funciona(self, cliente):
        assert cliente.get("/api/athletes").status_code == 200


class TestSistema:
    def test_health_reporta_treinos_carregados(self, cliente):
        resposta = cliente.get("/api/health")
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["status"] == "ok"
        assert corpo["treinos_carregados"] == 3

    def test_invalidar_cache(self, cliente):
        assert cliente.post("/api/cache/invalidar").status_code == 200

    def test_documentacao_openapi_e_publicada(self, cliente):
        esquema = cliente.get("/api/openapi.json")
        assert esquema.status_code == 200
        assert "/api/trainings/{id_treino}/analytics" in esquema.json()["paths"]


class TestCatalogo:
    def test_lista_de_atletas(self, cliente):
        corpo = cliente.get("/api/athletes").json()
        assert len(corpo["atletas"]) == 1
        atleta = corpo["atletas"][0]
        assert atleta["atleta"] == "Gabriel"
        assert atleta["treinos"] == 3
        assert atleta["primeiro_treino"] == "2026-07-01"

    def test_treinos_de_um_atleta(self, cliente):
        corpo = cliente.get("/api/athletes/Gabriel/trainings").json()
        assert corpo["quantidade"] == 3
        assert all("total" in t for t in corpo["treinos"])

    def test_filtros_disponiveis(self, cliente):
        corpo = cliente.get("/api/filters").json()
        assert set(corpo) == {
            "atletas", "datas", "tipos_de_alvo", "distancias", "tempos", "series", "treinos"
        }
        assert corpo["datas"] == ["2026-08-20", "2026-08-15", "2026-07-01"]

    def test_filtros_encadeiam_coerentemente(self, cliente):
        """Selecionar a data reduz os treinos àquela data."""
        corpo = cliente.get("/api/filters", params={"data_inicio": "2026-08-20"}).json()
        assert [t["id_treino"] for t in corpo["treinos"]] == ["TR-2008-1600"]
        assert corpo["distancias"] == ["18m"]

    def test_distancias_sao_ordenadas_numericamente(self, cliente):
        """'18m' antes de '70m' — ordenação de texto colocaria '18m' depois de '70m'? não,
        mas colocaria '100m' antes de '18m'. A ordem é pelo número."""
        corpo = cliente.get("/api/filters").json()
        numeros = [int("".join(c for c in d if c.isdigit())) for d in corpo["distancias"]]
        assert numeros == sorted(numeros)

    def test_geometria_do_alvo(self, cliente):
        corpo = cliente.get("/api/targets/Alvo Triplo").json()
        assert corpo["multiface"] is True
        assert len(corpo["centros"]) == 3
        assert len(corpo["aneis"]) == 6

    def test_geometria_de_alvo_desconhecido_cai_no_padrao(self, cliente):
        corpo = cliente.get("/api/targets/inexistente").json()
        assert corpo["multiface"] is False


class TestTreinos:
    def test_listagem(self, cliente):
        corpo = cliente.get("/api/trainings").json()
        assert corpo["quantidade"] == 3

    def test_cabecalho_de_um_treino(self, cliente):
        corpo = cliente.get("/api/trainings/TR-1508-1400").json()
        assert corpo["id_treino"] == "TR-1508-1400"
        assert corpo["quantidade_series"] == 2
        assert corpo["quantidade_flechas"] == 5

    def test_treino_inexistente_devolve_404(self, cliente):
        resposta = cliente.get("/api/trainings/NAO-EXISTE")
        assert resposta.status_code == 404
        assert "não encontrado" in resposta.json()["detail"]

    def test_analytics_de_um_treino(self, cliente):
        corpo = cliente.get("/api/trainings/TR-0107-0900/analytics").json()
        assert corpo["pontuacao"]["total"] == 27
        assert corpo["pontuacao"]["quantidade_flechas"] == 3
        assert corpo["dispersao"]["quantidade"] == 3
        assert len(corpo["series"]) == 1
        assert corpo["qualidade"]["com_pontuacao"] == 3

    def test_analytics_de_treino_inexistente_devolve_404(self, cliente):
        assert cliente.get("/api/trainings/NAO/analytics").status_code == 404

    def test_disparos_trazem_coordenadas_e_geometria(self, cliente):
        corpo = cliente.get("/api/trainings/TR-2008-1600/shots").json()
        assert len(corpo["disparos"]) == 3
        assert corpo["geometria"]["multiface"] is True

        disparo = corpo["disparos"][0]
        for campo in ("x", "y", "dx", "dy", "face_x", "face_y", "distancia_centro", "rotulo"):
            assert campo in disparo

    def test_shots_do_alvo_triplo_trazem_agrupamento_por_face(self, cliente):
        """Correção da calibração: o centro do grupo do Alvo Triplo é por
        face real, não uma origem fictícia (0,0)."""
        corpo = cliente.get("/api/trainings/TR-2008-1600/shots").json()
        assert "agrupamento_por_face" in corpo
        for grupo in corpo["agrupamento_por_face"]:
            assert "face_x" in grupo and "face_y" in grupo
            assert "centro_x" in grupo and "centro_y" in grupo

    def test_shots_de_alvo_simples_nao_tem_agrupamento_por_face(self, cliente):
        corpo = cliente.get("/api/trainings/TR-0107-0900/shots").json()
        assert corpo["agrupamento_por_face"] == []

    def test_coordenadas_saem_no_sistema_original_do_aplicativo(self, cliente):
        """A flecha gravada em (2, 96) sai como (2, 96) — sem reescala."""
        corpo = cliente.get("/api/trainings/TR-2008-1600/shots").json()
        primeiro = next(d for d in corpo["disparos"] if d["flecha"] == 1)
        assert primeiro["x"] == pytest.approx(2.0)
        assert primeiro["y"] == pytest.approx(96.0)
        # E o deslocamento é medido da face de cima, em (0, 95).
        assert primeiro["face_y"] == pytest.approx(95.0)
        assert primeiro["dy"] == pytest.approx(1.0)


class TestAnalytics:
    def test_historico(self, cliente):
        corpo = cliente.get("/api/analytics/history").json()
        assert corpo["quantidade"] == 3
        assert corpo["agregado"]["treinos"] == 3
        datas = [p["data_treino"] for p in corpo["pontos"]]
        assert datas == sorted(datas)

    def test_historico_filtrado_por_atleta(self, cliente):
        corpo = cliente.get("/api/analytics/history", params={"atleta": "gabriel"}).json()
        assert corpo["quantidade"] == 3

    def test_historico_de_atleta_inexistente_e_vazio(self, cliente):
        corpo = cliente.get("/api/analytics/history", params={"atleta": "Ninguém"}).json()
        assert corpo["quantidade"] == 0
        assert corpo["agregado"] == {"treinos": 0}

    def test_comparacao(self, cliente):
        resposta = cliente.get(
            "/api/analytics/comparison", params={"ids": "TR-0107-0900,TR-1508-1400"}
        )
        corpo = resposta.json()
        assert len(corpo["treinos"]) == 2
        assert len(corpo["metricas"]) == 8

    def test_comparacao_sem_ids_devolve_400(self, cliente):
        assert cliente.get("/api/analytics/comparison", params={"ids": " , "}).status_code == 400

    def test_comparacao_limita_a_seis_treinos(self, cliente):
        ids = ",".join(f"TR-{i}" for i in range(7))
        assert cliente.get("/api/analytics/comparison", params={"ids": ids}).status_code == 400


class TestValidacaoDeParametros:
    def test_data_invalida_devolve_422(self, cliente):
        assert cliente.get("/api/filters", params={"data_inicio": "20/08/2026"}).status_code == 422

    def test_serie_zero_devolve_422(self, cliente):
        assert cliente.get("/api/filters", params={"serie": 0}).status_code == 422

    def test_serie_valida_e_aceita(self, cliente):
        assert cliente.get("/api/filters", params={"serie": 1}).status_code == 200


class TestSerializacaoJson:
    def test_nenhuma_resposta_contem_nan(self, cliente):
        """NaN quebra parsers de JSON estritos."""
        for caminho in (
            "/api/trainings/TR-1508-1400/analytics",
            "/api/trainings/TR-1508-1400/shots",
            "/api/analytics/history",
        ):
            assert "NaN" not in cliente.get(caminho).text
