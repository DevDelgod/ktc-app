"""Testes da camada analítica.

Cada métrica é conferida contra o valor calculado à mão, não contra a
saída da própria implementação — para que um erro de fórmula apareça.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.analytics import metrics
from app.models.domain import Disparo, Serie, Treino


def _serie(doc_id: str, tempo: str, numero: int, disparos: list[Disparo], total: int | None,
           tipo_alvo: str = "Alvo Único", flechas_string: str | None = None) -> Serie:
    serie = Serie(
        doc_id=doc_id,
        id_treino="TR-TESTE",
        tempo=tempo,
        numero=numero,
        atleta="Gabriel",
        data_treino=None,
        distancia="70m",
        tipo_alvo=tipo_alvo,
        familia_alvo="simples",
        clima="Sol",
        v_vento=0.0,
        d_vento="Norte",
        total_registrado=total,
        flechas_string=flechas_string,
        criado_em=None,
        atualizado_em=None,
        disparos=disparos,
    )
    return serie


def _disparo(numero: int, x: float, y: float, pontos: int | None, rotulo: str | None,
             tipo_alvo: str = "Alvo Único") -> Disparo:
    from app.analytics.geometry import anel_do_disparo, distancia_do_centro

    anel = anel_do_disparo(x, y, tipo_alvo)
    return Disparo(
        numero=numero,
        x=x,
        y=y,
        rotulo=rotulo,
        pontos=pontos,
        origem_score="teste",
        distancia_centro=distancia_do_centro(x, y, tipo_alvo),
        pontos_geometricos=anel.pontos if anel else 0,
        rotulo_geometrico=anel.rotulo if anel else "M",
        dentro_do_alvo=anel is not None,
    )


@pytest.fixture
def treino_simples() -> Treino:
    """Quatro flechas com pontos 10, 9, 8, 9 — total 36, média 9."""
    disparos = [
        _disparo(1, 10.0, 0.0, 10, "10"),
        _disparo(2, 0.0, 20.0, 9, "9"),
        _disparo(3, -40.0, 0.0, 8, "8"),
        _disparo(4, 0.0, -20.0, 9, "9"),
    ]
    treino = Treino(id_treino="TR-TESTE", atleta="Gabriel", data_treino=None)
    treino.series = [_serie("TR-TESTE-T1-S1", "T1", 1, disparos, 36, flechas_string="10 9 8 9")]
    treino.ordenar()
    return treino


class TestMetricasDePontuacao:
    def test_total_media_e_mediana(self, treino_simples):
        quadro = metrics.quadro_de_disparos(treino_simples.series)
        resultado = metrics.metricas_de_pontuacao(quadro, treino_simples.series)

        assert resultado["total"] == 36
        assert resultado["media"] == pytest.approx(9.0)
        assert resultado["mediana"] == pytest.approx(9.0)
        assert resultado["maximo"] == 10
        assert resultado["minimo"] == 8
        assert resultado["quantidade_flechas"] == 4

    def test_desvio_padrao_e_amostral(self, treino_simples):
        """ddof=1: desvio da amostra, não da população."""
        quadro = metrics.quadro_de_disparos(treino_simples.series)
        resultado = metrics.metricas_de_pontuacao(quadro, treino_simples.series)
        esperado = float(np.std([10, 9, 8, 9], ddof=1))
        assert resultado["desvio_padrao"] == pytest.approx(esperado, abs=1e-3)

    def test_aproveitamento_usa_dez_como_teto(self, treino_simples):
        """36 pontos em 4 flechas = 36/40 = 0,9."""
        quadro = metrics.quadro_de_disparos(treino_simples.series)
        resultado = metrics.metricas_de_pontuacao(quadro, treino_simples.series)
        assert resultado["aproveitamento"] == pytest.approx(0.9)

    def test_flecha_sem_pontuacao_nao_conta_como_zero(self):
        """Série não finalizada não pode puxar a média para baixo."""
        disparos = [_disparo(1, 5.0, 0.0, 10, "10"), _disparo(2, 5.0, 0.0, None, None)]
        treino = Treino(id_treino="TR-X", atleta="G", data_treino=None)
        treino.series = [_serie("TR-X-T1-S1", "T1", 1, disparos, None)]
        treino.ordenar()

        quadro = metrics.quadro_de_disparos(treino.series)
        resultado = metrics.metricas_de_pontuacao(quadro, treino.series)

        assert resultado["quantidade_flechas"] == 2
        assert resultado["quantidade_flechas_pontuadas"] == 1
        assert resultado["media"] == pytest.approx(10.0)


class TestMetricasDeDispersao:
    def test_centro_do_grupo_e_a_media_das_coordenadas(self, treino_simples):
        """Pontos em (10,0), (0,20), (-40,0), (0,-20) -> centro (-7,5 , 0)."""
        quadro = metrics.quadro_de_disparos(treino_simples.series)
        resultado = metrics.metricas_de_dispersao(quadro)

        assert resultado["centro_grupo_x"] == pytest.approx(-7.5)
        assert resultado["centro_grupo_y"] == pytest.approx(0.0)

    def test_distancia_media_do_centro_do_alvo(self, treino_simples):
        """Distâncias 10, 20, 40, 20 -> média 22,5."""
        quadro = metrics.quadro_de_disparos(treino_simples.series)
        resultado = metrics.metricas_de_dispersao(quadro)
        assert resultado["distancia_media_centro"] == pytest.approx(22.5)
        assert resultado["distancia_maxima_centro"] == pytest.approx(40.0)
        assert resultado["distancia_minima_centro"] == pytest.approx(10.0)

    def test_dispersao_radial_e_a_raiz_da_soma_das_variancias(self, treino_simples):
        quadro = metrics.quadro_de_disparos(treino_simples.series)
        resultado = metrics.metricas_de_dispersao(quadro)

        dx = np.array([10.0, 0.0, -40.0, 0.0])
        dy = np.array([0.0, 20.0, 0.0, -20.0])
        esperado = math.sqrt(np.std(dx, ddof=1) ** 2 + np.std(dy, ddof=1) ** 2)
        assert resultado["dispersao_radial"] == pytest.approx(esperado, abs=1e-3)

    def test_extreme_spread_e_a_maior_distancia_entre_duas_flechas(self, treino_simples):
        """A maior separação é entre (10,0) e (-40,0) = 50."""
        quadro = metrics.quadro_de_disparos(treino_simples.series)
        resultado = metrics.metricas_de_dispersao(quadro)
        assert resultado["extreme_spread"] == pytest.approx(50.0)

    def test_precisao_e_agrupamento_sao_metricas_diferentes(self):
        """Grupo apertado mas deslocado: distância do centro alta, raio do grupo baixo."""
        disparos = [
            _disparo(1, 100.0, 0.0, 4, "4"),
            _disparo(2, 102.0, 0.0, 4, "4"),
            _disparo(3, 101.0, 2.0, 4, "4"),
        ]
        treino = Treino(id_treino="TR-D", atleta="G", data_treino=None)
        treino.series = [_serie("TR-D-T1-S1", "T1", 1, disparos, 12)]
        treino.ordenar()

        resultado = metrics.metricas_de_dispersao(metrics.quadro_de_disparos(treino.series))

        assert resultado["distancia_media_centro"] > 100     # longe do alvo
        assert resultado["raio_medio_grupo"] < 2             # mas bem agrupado
        assert resultado["vies_modulo"] > 100

    def test_vies_aponta_a_direcao_do_deslocamento(self):
        """Grupo à direita e acima -> viés na diagonal superior direita."""
        disparos = [_disparo(i, 50.0, 50.0, 7, "7") for i in range(1, 4)]
        treino = Treino(id_treino="TR-V", atleta="G", data_treino=None)
        treino.series = [_serie("TR-V-T1-S1", "T1", 1, disparos, 21)]
        treino.ordenar()

        resultado = metrics.metricas_de_dispersao(metrics.quadro_de_disparos(treino.series))
        assert resultado["vies_angulo"] == pytest.approx(45.0, abs=0.1)
        assert resultado["vies_direcao"] == "Sup. direita"

    def test_alvo_triplo_mede_a_partir_da_face_atingida(self):
        """Sem isso, a 'dispersão' mediria a distância entre as faces."""
        disparos = [
            _disparo(1, 0.0, 95.0, 10, "10", "Alvo Triplo"),
            _disparo(2, 0.0, 0.0, 10, "10", "Alvo Triplo"),
            _disparo(3, 0.0, -95.0, 10, "10", "Alvo Triplo"),
        ]
        treino = Treino(id_treino="TR-T", atleta="G", data_treino=None)
        treino.series = [
            _serie("TR-T-T1-S1", "T1", 1, disparos, 30, tipo_alvo="Alvo Triplo")
        ]
        treino.ordenar()

        resultado = metrics.metricas_de_dispersao(metrics.quadro_de_disparos(treino.series))

        # Três flechas no centro de cada face: dispersão zero, não 95.
        assert resultado["distancia_media_centro"] == pytest.approx(0.0)
        assert resultado["dispersao_radial"] == pytest.approx(0.0)

    def test_quadro_vazio_nao_quebra(self):
        assert metrics.metricas_de_dispersao(metrics.quadro_de_disparos([])) == {"quantidade": 0}


class TestConsistencia:
    def test_desvio_entre_series(self):
        por_serie = [
            {"total": 50, "finalizada": True},
            {"total": 54, "finalizada": True},
            {"total": 46, "finalizada": True},
        ]
        resultado = metrics.metricas_de_consistencia(por_serie)

        assert resultado["media_por_serie"] == pytest.approx(50.0)
        assert resultado["amplitude"] == pytest.approx(8.0)
        assert resultado["desvio_entre_series"] == pytest.approx(
            float(np.std([50, 54, 46], ddof=1)), abs=1e-3
        )

    def test_coeficiente_de_variacao_e_adimensional(self):
        por_serie = [{"total": 100, "finalizada": True}, {"total": 120, "finalizada": True}]
        resultado = metrics.metricas_de_consistencia(por_serie)
        desvio = float(np.std([100, 120], ddof=1))
        assert resultado["coeficiente_variacao"] == pytest.approx(desvio / 110, abs=1e-4)

    def test_series_nao_finalizadas_sao_ignoradas(self):
        por_serie = [
            {"total": 50, "finalizada": True},
            {"total": 0, "finalizada": False},
        ]
        resultado = metrics.metricas_de_consistencia(por_serie)
        assert resultado["series_consideradas"] == 1
        assert resultado["desvio_entre_series"] is None

    def test_media_zero_nao_produz_divisao_por_zero(self):
        por_serie = [{"total": 0, "finalizada": True}, {"total": 0, "finalizada": True}]
        assert metrics.metricas_de_consistencia(por_serie)["coeficiente_variacao"] is None


class TestQualidadeDosDados:
    def test_concordancia_total_quando_digitado_bate_com_a_posicao(self, treino_simples):
        quadro = metrics.quadro_de_disparos(treino_simples.series)
        resultado = metrics.qualidade_dos_dados(quadro)
        assert resultado["concordancia"] == pytest.approx(1.0)
        assert resultado["divergencias"] == 0

    def test_divergencia_e_detectada_sem_sobrescrever_o_dado(self):
        """Flecha marcada no anel do 9 mas digitada como 10."""
        disparos = [_disparo(1, 20.0, 0.0, 10, "10")]
        treino = Treino(id_treino="TR-Q", atleta="G", data_treino=None)
        treino.series = [_serie("TR-Q-T1-S1", "T1", 1, disparos, 10)]
        treino.ordenar()

        quadro = metrics.quadro_de_disparos(treino.series)
        resultado = metrics.qualidade_dos_dados(quadro)

        assert resultado["divergencias"] == 1
        assert resultado["concordancia"] == pytest.approx(0.0)
        # O valor digitado permanece intacto.
        assert int(quadro.iloc[0]["pontos"]) == 10
        assert int(quadro.iloc[0]["pontos_geometricos"]) == 9

    def test_conta_flechas_fora_do_alvo(self):
        disparos = [_disparo(1, 300.0, 0.0, 0, "M")]
        treino = Treino(id_treino="TR-F", atleta="G", data_treino=None)
        treino.series = [_serie("TR-F-T1-S1", "T1", 1, disparos, 0)]
        treino.ordenar()

        resultado = metrics.qualidade_dos_dados(metrics.quadro_de_disparos(treino.series))
        assert resultado["fora_do_alvo"] == 1


class TestDistribuicao:
    def test_ordem_do_teclado_e_preservada(self, treino_simples):
        quadro = metrics.quadro_de_disparos(treino_simples.series)
        distribuicao = metrics.distribuicao_de_pontuacao(quadro)
        rotulos = [d["rotulo"] for d in distribuicao]
        assert rotulos[:4] == ["X", "10", "9", "8"]

    def test_contagem_correta(self, treino_simples):
        distribuicao = metrics.distribuicao_de_pontuacao(
            metrics.quadro_de_disparos(treino_simples.series)
        )
        por_rotulo = {d["rotulo"]: d["quantidade"] for d in distribuicao}
        assert por_rotulo["9"] == 2
        assert por_rotulo["10"] == 1
        assert por_rotulo["8"] == 1
        assert por_rotulo["X"] == 0


class TestPacoteCompleto:
    def test_analisar_treino_entrega_todas_as_secoes(self, treino_simples):
        resultado = metrics.analisar_treino(treino_simples)
        assert set(resultado) == {
            "treino", "pontuacao", "dispersao", "agrupamento_por_face",
            "consistencia", "distribuicao", "qualidade", "series", "analise",
        }

    def test_dispersao_traz_conversao_para_centimetros(self, treino_simples):
        resultado = metrics.analisar_treino(treino_simples)
        assert "distancia_media_centro_cm" in resultado["dispersao"]
        # 22,5 unidades num alvo de 122 cm -> 22,5 * (61/150) = 9,15 cm
        assert resultado["dispersao"]["distancia_media_centro_cm"] == pytest.approx(9.15, abs=0.01)

    def test_conversao_cm_cobre_todas_as_metricas_lineares(self, treino_simples):
        """Antes só distancia_/raio_ eram convertidas; dispersao_radial e
        vies_modulo ficavam presos na unidade interna — a queixa relatada."""
        resultado = metrics.analisar_treino(treino_simples)
        for chave in ("dispersao_radial_cm", "vies_modulo_cm", "desvio_x_cm", "desvio_y_cm"):
            assert chave in resultado["dispersao"], f"{chave} deveria ter conversão para cm"

    def test_agrupamento_por_face_vazio_para_alvo_simples(self, treino_simples):
        """Só o alvo triplo tem múltiplas faces; o simples não precisa disso."""
        resultado = metrics.analisar_treino(treino_simples)
        assert resultado["agrupamento_por_face"] == []

    def test_serializar_disparos_nao_deixa_nan_no_json(self):
        """NaN não é JSON válido — precisa virar null."""
        disparos = [_disparo(1, 5.0, 0.0, None, None)]
        treino = Treino(id_treino="TR-N", atleta="G", data_treino=None)
        treino.series = [_serie("TR-N-T1-S1", "T1", 1, disparos, None)]
        treino.ordenar()

        serializado = metrics.serializar_disparos(treino)
        assert serializado[0]["pontos"] is None
        for valor in serializado[0].values():
            assert not (isinstance(valor, float) and math.isnan(valor))
