"""Testes de `dispersion.py`: calibração do centro e conversão a cm.

O foco aqui é a correção do bug de calibração relatado: o "centro do
grupo" desenhado num alvo multiface (Alvo Triplo) precisa ser calculado
por face, nunca contra uma origem fictícia (0, 0) que não corresponde a
nenhuma face real.
"""

from __future__ import annotations

import pytest

from app.analytics import dispersion
from app.analytics.geometry import GEOMETRIA_SIMPLES, GEOMETRIA_TRIPLA
from app.analytics.metrics import quadro_de_disparos
from tests.test_metrics import _disparo, _serie
from app.models.domain import Treino


def _treino_com_disparos(disparos, tipo_alvo="Alvo Único"):
    treino = Treino(id_treino="TR-CAL", atleta="G", data_treino=None)
    treino.series = [_serie("TR-CAL-T1-S1", "T1", 1, disparos, None, tipo_alvo=tipo_alvo)]
    treino.ordenar()
    return treino


class TestCentroDoAlvoSimples:
    """(0,0) deve ser exatamente o centro — os quatro eixos cardeais."""

    def test_origem_produz_deslocamento_zero(self):
        treino = _treino_com_disparos([_disparo(1, 0.0, 0.0, 10, "10")])
        quadro = quadro_de_disparos(treino.series)
        assert quadro.iloc[0]["dx"] == pytest.approx(0.0)
        assert quadro.iloc[0]["dy"] == pytest.approx(0.0)

    def test_x_positivo_desloca_so_horizontal(self):
        treino = _treino_com_disparos([_disparo(1, 30.0, 0.0, 9, "9")])
        quadro = quadro_de_disparos(treino.series)
        assert quadro.iloc[0]["dx"] == pytest.approx(30.0)
        assert quadro.iloc[0]["dy"] == pytest.approx(0.0)

    def test_x_negativo_desloca_horizontal_oposto(self):
        treino = _treino_com_disparos([_disparo(1, -30.0, 0.0, 9, "9")])
        quadro = quadro_de_disparos(treino.series)
        assert quadro.iloc[0]["dx"] == pytest.approx(-30.0)

    def test_y_positivo_desloca_so_vertical(self):
        treino = _treino_com_disparos([_disparo(1, 0.0, 30.0, 9, "9")])
        quadro = quadro_de_disparos(treino.series)
        assert quadro.iloc[0]["dx"] == pytest.approx(0.0)
        assert quadro.iloc[0]["dy"] == pytest.approx(30.0)

    def test_y_negativo_desloca_vertical_oposto(self):
        treino = _treino_com_disparos([_disparo(1, 0.0, -30.0, 9, "9")])
        quadro = quadro_de_disparos(treino.series)
        assert quadro.iloc[0]["dy"] == pytest.approx(-30.0)

    def test_limite_externo_do_alvo(self):
        """Raio 150 é o anel externo do alvo simples — a borda exata."""
        treino = _treino_com_disparos([_disparo(1, 150.0, 0.0, 1, "1")])
        quadro = quadro_de_disparos(treino.series)
        assert quadro.iloc[0]["dx"] == pytest.approx(150.0)


class TestAgrupamentoPorFaceCorrigeCalibracao:
    """O bug relatado: o centro do grupo não pode ficar preso em (0,0)
    fictício quando o alvo tem faces em posições físicas diferentes."""

    def test_alvo_simples_nao_gera_agrupamento_por_face(self):
        treino = _treino_com_disparos(
            [_disparo(1, 5.0, 5.0, 9, "9"), _disparo(2, -5.0, -5.0, 9, "9")]
        )
        quadro = quadro_de_disparos(treino.series)
        assert dispersion.agrupamento_por_face(quadro, GEOMETRIA_SIMPLES) == []

    def test_grupo_na_face_de_cima_e_atribuido_a_ela_nao_a_origem_ficticia(self):
        """5 flechas concentradas perto de (0, 95) -- a face de cima do
        Alvo Triplo. O centro do grupo tem que refletir ESSA face, não a
        posição fictícia (0,0) que não é nenhuma face real."""
        disparos = [
            _disparo(1, 1.0, 94.0, None, None, "Alvo Triplo"),
            _disparo(2, -1.0, 96.0, None, None, "Alvo Triplo"),
            _disparo(3, 2.0, 95.0, None, None, "Alvo Triplo"),
            _disparo(4, -2.0, 93.0, None, None, "Alvo Triplo"),
            _disparo(5, 0.0, 97.0, None, None, "Alvo Triplo"),
        ]
        treino = _treino_com_disparos(disparos, tipo_alvo="Alvo Triplo")
        quadro = quadro_de_disparos(treino.series)
        grupos = dispersion.agrupamento_por_face(quadro, GEOMETRIA_TRIPLA)

        assert len(grupos) == 1
        grupo = grupos[0]
        # A face identificada tem que ser a de cima (y=95), não (0,0).
        assert grupo["face_x"] == pytest.approx(0.0)
        assert grupo["face_y"] == pytest.approx(95.0)
        assert grupo["quantidade"] == 5
        # O centro local (relativo àquela face) fica perto de zero,
        # porque as flechas estão bem centradas NAQUELA face.
        assert grupo["centro_x"] == pytest.approx(0.0, abs=0.5)
        assert grupo["centro_y"] == pytest.approx(0.0, abs=0.5)

    def test_flechas_espalhadas_em_tres_faces_geram_tres_grupos_separados(self):
        disparos = [
            _disparo(1, 0.0, 95.0, None, None, "Alvo Triplo"),
            _disparo(2, 1.0, 96.0, None, None, "Alvo Triplo"),
            _disparo(3, 0.0, 0.0, None, None, "Alvo Triplo"),
            _disparo(4, 1.0, 1.0, None, None, "Alvo Triplo"),
            _disparo(5, 0.0, -95.0, None, None, "Alvo Triplo"),
            _disparo(6, -1.0, -94.0, None, None, "Alvo Triplo"),
        ]
        treino = _treino_com_disparos(disparos, tipo_alvo="Alvo Triplo")
        quadro = quadro_de_disparos(treino.series)
        grupos = dispersion.agrupamento_por_face(quadro, GEOMETRIA_TRIPLA)

        assert len(grupos) == 3
        faces_y = sorted(g["face_y"] for g in grupos)
        assert faces_y == pytest.approx([-95.0, 0.0, 95.0])
        assert all(g["quantidade"] == 2 for g in grupos)

    def test_uma_unica_flecha_no_grupo_nao_tem_raio(self):
        """Raio médio exige pelo menos 2 pontos para fazer sentido."""
        disparos = [_disparo(1, 0.0, 95.0, None, None, "Alvo Triplo")]
        treino = _treino_com_disparos(disparos, tipo_alvo="Alvo Triplo")
        quadro = quadro_de_disparos(treino.series)
        grupos = dispersion.agrupamento_por_face(quadro, GEOMETRIA_TRIPLA)
        assert grupos[0]["raio_medio"] is None


class TestConversaoCmCompleta:
    """Toda métrica linear ganha `_cm` — não só as com prefixo distancia_/raio_."""

    def test_todas_as_chaves_lineares_sao_convertidas(self):
        disparos = [
            _disparo(1, 10.0, 0.0, 10, "10"),
            _disparo(2, -10.0, 20.0, 9, "9"),
            _disparo(3, 5.0, -5.0, 9, "9"),
        ]
        treino = _treino_com_disparos(disparos)
        quadro = quadro_de_disparos(treino.series)
        bruto = dispersion.metricas_de_dispersao(quadro)
        com_cm = dispersion.com_cm(bruto, GEOMETRIA_SIMPLES)

        esperadas = [
            "centro_grupo_x_cm", "centro_grupo_y_cm", "desvio_x_cm", "desvio_y_cm",
            "dispersao_radial_cm", "distancia_media_centro_cm", "raio_medio_grupo_cm",
            "vies_modulo_cm",
        ]
        for chave in esperadas:
            assert chave in com_cm, f"{chave} ausente na conversão"

    def test_fator_de_conversao_e_o_mesmo_para_toda_metrica_linear(self):
        """122cm de diâmetro / 150 unidades de raio -> mesmo fator em tudo."""
        bruto = {"dispersao_radial": 30.0, "vies_modulo": 15.0}
        convertido = dispersion.com_cm(bruto, GEOMETRIA_SIMPLES)
        fator = 61.0 / 150.0
        assert convertido["dispersao_radial_cm"] == pytest.approx(30.0 * fator, abs=0.01)
        assert convertido["vies_modulo_cm"] == pytest.approx(15.0 * fator, abs=0.01)

    def test_angulo_e_rotulo_nao_ganham_versao_cm(self):
        bruto = {"vies_angulo": 45.0, "vies_direcao": "Direita"}
        convertido = dispersion.com_cm(bruto, GEOMETRIA_SIMPLES)
        assert "vies_angulo_cm" not in convertido
        assert "vies_direcao_cm" not in convertido
