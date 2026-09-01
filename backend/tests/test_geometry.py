"""Testes da geometria dos alvos.

Garantem a regra do item 22 do briefing: **mesma coordenada, mesma
pontuação**. E garantem que a geometria transplantada do JavaScript não
sofreu desvio.
"""

from __future__ import annotations

import math

import pytest

from app.analytics import geometry


class TestConstantes:
    def test_alvo_simples_tem_os_onze_aneis_do_frontend(self):
        raios = sorted((a.raio for a in geometry.GEOMETRIA_SIMPLES.aneis), reverse=True)
        assert raios == [150, 135, 120, 105, 90, 75, 60, 45, 30, 15, 7.5]

    def test_alvo_triplo_tem_os_seis_aneis_do_frontend(self):
        raios = sorted((a.raio for a in geometry.GEOMETRIA_TRIPLA.aneis), reverse=True)
        assert raios == [45, 36, 27, 18, 9, 4.5]

    def test_alvo_triplo_tem_tres_faces_empilhadas(self):
        assert geometry.GEOMETRIA_TRIPLA.centros == ((0.0, 95.0), (0.0, 0.0), (0.0, -95.0))

    def test_triplo_e_o_miolo_do_simples_a_sessenta_por_cento(self):
        """Relação verificada no código original, anel a anel."""
        simples = {a.nivel: a.raio for a in geometry.GEOMETRIA_SIMPLES.aneis}
        for anel in geometry.GEOMETRIA_TRIPLA.aneis:
            assert anel.raio == pytest.approx(simples[anel.nivel] * 0.6)

    def test_nivel_onze_e_o_x_e_vale_dez(self):
        x = next(a for a in geometry.GEOMETRIA_SIMPLES.aneis if a.nivel == 11)
        assert x.rotulo == "X"
        assert x.pontos == 10


class TestResolucaoDeTipo:
    @pytest.mark.parametrize(
        "nome", ["Alvo Unitário", "Alvo Único", "alvo unitário  ", None, "desconhecido"]
    )
    def test_nomes_que_caem_no_alvo_simples(self, nome):
        """'Unitário' e 'Único' são a mesma geometria; desconhecido cai no padrão."""
        assert geometry.geometria(nome).multiface is False

    def test_alvo_triplo_e_multiface(self):
        assert geometry.geometria("Alvo Triplo").multiface is True


class TestDistanciaDoCentro:
    def test_alvo_simples_usa_a_origem(self):
        assert geometry.distancia_do_centro(3.0, 4.0, "Alvo Único") == pytest.approx(5.0)

    def test_alvo_triplo_usa_a_face_mais_proxima(self):
        """Um disparo em (0, 96) está a 1 unidade da face de cima, não a 96 da origem."""
        assert geometry.distancia_do_centro(0.0, 96.0, "Alvo Triplo") == pytest.approx(1.0)
        assert geometry.distancia_do_centro(0.0, -94.0, "Alvo Triplo") == pytest.approx(1.0)
        assert geometry.distancia_do_centro(0.0, 0.0, "Alvo Triplo") == pytest.approx(0.0)

    def test_ponto_equidistante_entre_faces_escolhe_uma_face_deterministicamente(self):
        distancia = geometry.distancia_do_centro(0.0, 47.5, "Alvo Triplo")
        assert distancia == pytest.approx(47.5)


class TestPontuacaoGeometrica:
    @pytest.mark.parametrize(
        "distancia,pontos_esperados",
        [
            (0.0, 10),     # centro -> X
            (7.5, 10),     # exatamente na borda do X
            (7.6, 10),     # anel do 10
            (15.0, 10),
            (15.1, 9),
            (30.0, 9),
            (45.0, 8),
            (60.0, 7),
            (75.0, 6),
            (90.0, 5),
            (105.0, 4),
            (120.0, 3),
            (135.0, 2),
            (150.0, 1),    # último anel válido
            (150.1, 0),    # fora do alvo -> M
        ],
    )
    def test_aneis_do_alvo_simples(self, distancia, pontos_esperados):
        """A borda pertence ao anel de dentro, como na marcação em campo."""
        assert geometry.score_geometrico(distancia, 0.0, "Alvo Único") == pontos_esperados

    def test_fora_do_alvo_vira_m(self):
        assert geometry.rotulo_geometrico(200.0, 0.0, "Alvo Único") == "M"
        assert geometry.dentro_do_alvo(200.0, 0.0, "Alvo Único") is False

    def test_x_e_distinguido_do_dez(self):
        """X e 10 valem o mesmo, mas o rótulo diferencia."""
        assert geometry.rotulo_geometrico(5.0, 0.0, "Alvo Único") == "X"
        assert geometry.rotulo_geometrico(12.0, 0.0, "Alvo Único") == "10"
        assert geometry.score_geometrico(5.0, 0.0, "Alvo Único") == 10
        assert geometry.score_geometrico(12.0, 0.0, "Alvo Único") == 10

    def test_alvo_triplo_so_pontua_de_seis_para_cima(self):
        """As faces do triplo não têm anéis abaixo de 6."""
        assert geometry.score_geometrico(0.0, 95.0, "Alvo Triplo") == 10
        assert geometry.score_geometrico(44.0, 95.0, "Alvo Triplo") == 6
        assert geometry.score_geometrico(46.0, 95.0, "Alvo Triplo") == 0

    def test_mesma_coordenada_produz_sempre_a_mesma_pontuacao(self):
        """Requisito explícito: determinismo do cálculo."""
        for _ in range(50):
            assert geometry.score_geometrico(23.4, -11.7, "Alvo Único") == 9


class TestConversaoParaCentimetros:
    def test_raio_externo_do_alvo_simples_e_metade_de_122cm(self):
        geo = geometry.GEOMETRIA_SIMPLES
        assert geo.unidades_para_cm(geo.raio_externo) == pytest.approx(61.0)

    def test_raio_externo_do_alvo_triplo_e_metade_de_40cm(self):
        geo = geometry.GEOMETRIA_TRIPLA
        assert geo.unidades_para_cm(geo.raio_externo) == pytest.approx(20.0)


class TestSerializacao:
    def test_descrever_entrega_aneis_do_maior_para_o_menor(self):
        descricao = geometry.descrever("Alvo Único")
        raios = [a["raio"] for a in descricao["aneis"]]
        assert raios == sorted(raios, reverse=True)
        assert descricao["centros"] == [{"x": 0.0, "y": 0.0}]

    def test_descrever_do_triplo_traz_as_tres_faces(self):
        descricao = geometry.descrever("Alvo Triplo")
        assert len(descricao["centros"]) == 3
        assert descricao["multiface"] is True


class TestSistemaDeCoordenadas:
    """O eixo Y é positivo para cima — a convenção do aplicativo."""

    def test_y_positivo_esta_acima_do_centro(self):
        acima = geometry.distancia_do_centro(0.0, 10.0, "Alvo Único")
        abaixo = geometry.distancia_do_centro(0.0, -10.0, "Alvo Único")
        assert acima == abaixo == pytest.approx(10.0)

    def test_distancia_e_euclidiana_pura(self):
        assert geometry.distancia_do_centro(30.0, 40.0, "Alvo Único") == pytest.approx(
            math.hypot(30.0, 40.0)
        )
