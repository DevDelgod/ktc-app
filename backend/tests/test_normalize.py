"""Testes da normalização de leitura dos documentos legados."""

from __future__ import annotations

from datetime import date

import pytest

from app.services import normalize


class TestConversaoNumerica:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            (12.34, 12.34),
            ("12.34", 12.34),
            ("12,34", 12.34),      # formato que o frontend chegou a produzir
            ("-8,5", -8.5),
            (0, 0.0),
            ("0", 0.0),
            ("  7 ", 7.0),
        ],
    )
    def test_aceita_numero_ponto_e_virgula(self, entrada, esperado):
        assert normalize.para_float(entrada) == pytest.approx(esperado)

    @pytest.mark.parametrize("entrada", [None, "", "abc", "--"])
    def test_valores_invalidos_caem_no_padrao(self, entrada):
        assert normalize.para_float(entrada, 99.0) == 99.0

    def test_v_vento_vazio_vira_zero(self):
        """O app grava a string '0' quando o campo fica em branco."""
        assert normalize.para_float("0", 0.0) == 0.0
        assert normalize.para_float("", 0.0) == 0.0


class TestPontosDoRotulo:
    @pytest.mark.parametrize(
        "rotulo,pontos",
        [("X", 10), ("x", 10), ("10", 10), ("9", 9), ("1", 1), ("M", 0), ("m", 0), (" 8 ", 8)],
    )
    def test_regra_identica_a_do_frontend(self, rotulo, pontos):
        assert normalize.pontos_do_rotulo(rotulo) == pontos

    @pytest.mark.parametrize("rotulo", [None, "", "??", "11", "-1"])
    def test_simbolo_irreconhecivel_nao_vira_zero(self, rotulo):
        """Devolver 0 aqui inflaria a contagem de erros com dado ausente."""
        assert normalize.pontos_do_rotulo(rotulo) is None


class TestFamiliaDeAlvo:
    def test_unitario_e_unico_colapsam_na_mesma_familia(self):
        """As duas strings desenham a mesma geometria no aplicativo."""
        assert normalize.familia_alvo("Alvo Unitário") == normalize.familia_alvo("Alvo Único")
        assert normalize.familia_alvo("Alvo Unitário") == normalize.FAMILIA_SIMPLES

    def test_triplo_tem_familia_propria(self):
        assert normalize.familia_alvo("Alvo Triplo") == normalize.FAMILIA_TRIPLA

    def test_documento_com_apenas_um_dos_campos_duplicados(self):
        assert normalize.tipo_alvo_do_documento({"tipo_alvo": "Alvo Triplo"}) == "Alvo Triplo"
        assert normalize.tipo_alvo_do_documento({"tipoAlvo": "Alvo Único"}) == "Alvo Único"

    def test_documento_sem_tipo_cai_no_padrao_do_app(self):
        assert normalize.tipo_alvo_do_documento({}) == "Alvo Unitário"


class TestIdDoDocumento:
    def test_separa_id_treino_tempo_e_serie(self):
        """O idTreino contém hífens, então a separação vem do fim."""
        assert normalize.partes_do_doc_id("TR-3108-1605-T1-S4") == ("TR-3108-1605", "T1", 4)
        assert normalize.partes_do_doc_id("TR-0101-0000-T2-S12") == ("TR-0101-0000", "T2", 12)

    def test_id_com_nome_digitado_pelo_usuario(self):
        assert normalize.partes_do_doc_id("Treino da Serra-T2-S3") == ("Treino da Serra", "T2", 3)

    @pytest.mark.parametrize("doc_id", ["", "sem-padrao", "TR-1234", "TR-1-T1-4"])
    def test_id_fora_do_padrao_devolve_none(self, doc_id):
        assert normalize.partes_do_doc_id(doc_id) is None


class TestAtleta:
    def test_espacos_extras_nao_criam_atleta_novo(self):
        assert normalize.chave_de_atleta("  Gabriel  ") == normalize.chave_de_atleta("Gabriel")

    def test_caixa_nao_cria_atleta_novo(self):
        assert normalize.chave_de_atleta("GABRIEL") == normalize.chave_de_atleta("gabriel")

    def test_espaco_interno_e_colapsado(self):
        assert normalize.nome_de_atleta("Gabriel   Delgado") == "Gabriel Delgado"


class TestOrdemDasSeries:
    def test_formato_padrao_reproduz_o_serie_global_antigo(self):
        """Com 6 séries por rodada, a ordem recalculada bate com o campo do banco."""
        pares = [("T1", n) for n in range(1, 7)] + [("T2", n) for n in range(1, 7)]
        ordem = normalize.ordem_das_series(pares)
        assert ordem[("T1", 1)] == 1
        assert ordem[("T1", 6)] == 6
        assert ordem[("T2", 1)] == 7   # igual ao serieGlobal antigo
        assert ordem[("T2", 6)] == 12

    def test_formato_de_tres_series_corrige_o_bug_do_mais_seis(self):
        """O campo `serieGlobal` gravaria 7 para T2-S1; a ordem real é 4."""
        pares = [("T1", n) for n in (1, 2, 3)] + [("T2", n) for n in (1, 2, 3)]
        ordem = normalize.ordem_das_series(pares)
        assert ordem[("T2", 1)] == 4
        assert ordem[("T2", 3)] == 6

    def test_series_repetidas_nao_duplicam_a_ordem(self):
        ordem = normalize.ordem_das_series([("T1", 1), ("T1", 1), ("T1", 2)])
        assert ordem == {("T1", 1): 1, ("T1", 2): 2}


class TestDatas:
    def test_le_o_formato_do_input_date(self):
        assert normalize.para_data("2026-08-20") == date(2026, 8, 20)

    @pytest.mark.parametrize("valor", [None, "", "20/08/2026", "data"])
    def test_data_invalida_devolve_none(self, valor):
        assert normalize.para_data(valor) is None


class TestStringDeFlechas:
    def test_divide_nos_espacos(self):
        assert normalize.tokens_da_string_de_flechas("X 10 9 9 8 M") == [
            "X", "10", "9", "9", "8", "M"
        ]

    def test_espacos_multiplos_nao_geram_token_vazio(self):
        assert normalize.tokens_da_string_de_flechas("X  10   9") == ["X", "10", "9"]

    @pytest.mark.parametrize("valor", [None, "", "   "])
    def test_ausente_devolve_lista_vazia(self, valor):
        assert normalize.tokens_da_string_de_flechas(valor) == []
