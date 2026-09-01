"""Compatibilidade com os dados históricos.

Este é o critério do item 18 do briefing: um treino gravado pelo
aplicativo antigo — sem `score` no disparo, com `serieGlobal` errado,
com `serie` e `v_vento` como string — precisa ser analisável pelo novo
dashboard exatamente como um treino novo.

Também cobre o item 23: os resultados da nova camada analítica são
confrontados com o que o sistema antigo já registrava (`total` e
`flechasString`), e as duas coisas têm que bater.
"""

from __future__ import annotations

import pytest

from app.services.analytics_service import Filtros
from app.services.repository import ORIGEM_CAMPO, ORIGEM_STRING


class TestLeituraDoFormatoLegado:
    def test_documentos_viram_treinos_agrupados_por_id(self, servico_legado):
        """Quatro documentos de série com o mesmo idTreino = um treino só."""
        treinos = servico_legado.treinos()
        assert len(treinos) == 1
        assert treinos[0].id_treino == "TR-2008-1030"
        assert treinos[0].quantidade_series == 4

    def test_subcolecao_de_disparos_e_vinculada_a_serie_correta(self, servico_legado):
        treino = servico_legado.treinos()[0]
        for serie in treino.series:
            assert serie.quantidade_flechas == 6
            assert [d.numero for d in serie.disparos] == [1, 2, 3, 4, 5, 6]

    def test_serie_string_vira_numero(self, servico_legado):
        treino = servico_legado.treinos()[0]
        assert all(isinstance(s.numero, int) for s in treino.series)

    def test_v_vento_string_vira_numero(self, servico_legado):
        treino = servico_legado.treinos()[0]
        assert treino.series[0].v_vento == pytest.approx(12.0)

    def test_ordem_das_series_ignora_o_serie_global_do_banco(self, servico_legado):
        """A rodada tem 2 séries, então T2-S1 é a 3ª — não a 7ª."""
        treino = servico_legado.treinos()[0]
        ordens = {(s.tempo, s.numero): s.ordem for s in treino.series}
        assert ordens[("T1", 1)] == 1
        assert ordens[("T1", 2)] == 2
        assert ordens[("T2", 1)] == 3   # o campo antigo diria 7
        assert ordens[("T2", 2)] == 4


class TestPareamentoDaPontuacaoHistorica:
    """A ligação flecha ↔ ponto nos dados antigos.

    O disparo histórico não tem pontuação. A única informação disponível
    é a `flechasString` da série, em que o n-ésimo símbolo corresponde à
    n-ésima flecha marcada. O backend reconstrói esse par.
    """

    def test_cada_flecha_recebe_o_simbolo_da_sua_posicao(self, servico_legado):
        treino = servico_legado.treinos()[0]
        serie = treino.series[0]
        assert serie.flechas_string == "X 10 9 9 8 M"
        assert [d.rotulo for d in serie.disparos] == ["X", "10", "9", "9", "8", "M"]

    def test_pontos_seguem_a_regra_do_aplicativo(self, servico_legado):
        """X vale 10, M vale 0, o resto vale o próprio número."""
        serie = servico_legado.treinos()[0].series[0]
        assert [d.pontos for d in serie.disparos] == [10, 10, 9, 9, 8, 0]

    def test_origem_do_score_e_declarada_como_inferida(self, servico_legado):
        """O pareamento por posição fica rastreável, não escondido."""
        serie = servico_legado.treinos()[0].series[0]
        assert all(d.origem_score == ORIGEM_STRING for d in serie.disparos)

    def test_soma_reconstruida_bate_com_o_total_gravado(self, servico_legado):
        """Validação contra o sistema atual: o total antigo é reproduzido."""
        for serie in servico_legado.treinos()[0].series:
            soma = sum(d.pontos for d in serie.disparos if d.pontos is not None)
            assert soma == serie.total_registrado


class TestFormatoNovoTemPrecedencia:
    def test_campo_score_do_disparo_vence_a_string(self, servico_misto):
        treino = servico_misto.treino_por_id("TR-1508-1400")
        serie = next(s for s in treino.series if s.numero == 1)
        assert all(d.origem_score == ORIGEM_CAMPO for d in serie.disparos)
        assert [d.rotulo for d in serie.disparos] == ["X", "10", "9"]

    def test_treinos_novo_e_antigo_convivem_na_mesma_base(self, servico_misto):
        origens = {
            d.origem_score for t in servico_misto.treinos() for d in t.disparos
        }
        assert ORIGEM_CAMPO in origens
        assert ORIGEM_STRING in origens


class TestSerieNaoFinalizada:
    """Série em que o atleta confirmou o alvo mas não digitou a pontuação."""

    def test_disparos_ficam_sem_pontuacao_em_vez_de_zero(self, servico_misto):
        treino = servico_misto.treino_por_id("TR-1508-1400")
        serie = next(s for s in treino.series if s.numero == 2)
        assert serie.finalizada is False
        assert all(d.pontos is None for d in serie.disparos)

    def test_coordenadas_continuam_disponiveis_para_analise(self, servico_misto):
        """Sem pontuação, mas a dispersão ainda pode ser calculada."""
        treino = servico_misto.treino_por_id("TR-1508-1400")
        serie = next(s for s in treino.series if s.numero == 2)
        assert serie.quantidade_flechas == 2
        assert all(d.distancia_centro > 0 for d in serie.disparos)

    def test_media_do_treino_nao_e_diluida_por_flecha_sem_pontuacao(self, servico_misto):
        treino = servico_misto.treino_por_id("TR-1508-1400")
        analise = servico_misto.analisar(treino)
        assert analise["pontuacao"]["quantidade_flechas"] == 5
        assert analise["pontuacao"]["quantidade_flechas_pontuadas"] == 3
        assert analise["pontuacao"]["media"] == pytest.approx(29 / 3, abs=0.01)


class TestNomesDeAlvoLegados:
    def test_unitario_e_unico_nao_dividem_o_mesmo_alvo(self, servico_misto):
        """As duas strings antigas caem na mesma família canônica."""
        familias = {s.familia_alvo for t in servico_misto.treinos() for s in t.series}
        assert familias == {"simples", "tripla"}

    def test_alvo_triplo_e_analisado_com_a_geometria_correta(self, servico_misto):
        treino = servico_misto.treino_por_id("TR-2008-1600")
        analise = servico_misto.analisar(treino)
        # Flechas próximas ao centro de faces diferentes continuam sendo
        # disparos precisos — não uma dispersão de 95 unidades.
        assert analise["dispersao"]["distancia_media_centro"] < 6


class TestFiltrosSobreDadosHistoricos:
    def test_filtro_por_atleta_e_insensivel_a_caixa(self, servico_misto):
        assert len(servico_misto.filtrar(Filtros(atleta="gabriel"))) == 3
        assert len(servico_misto.filtrar(Filtros(atleta="GABRIEL"))) == 3

    def test_filtro_por_intervalo_de_datas(self, servico_misto):
        from datetime import date

        recorte = servico_misto.filtrar(Filtros(data_inicio=date(2026, 8, 1)))
        assert {t.id_treino for t in recorte} == {"TR-1508-1400", "TR-2008-1600"}

    def test_filtro_por_tipo_de_alvo_seleciona_series(self, servico_misto):
        recorte = servico_misto.filtrar(Filtros(tipo_alvo="Alvo Triplo"))
        assert len(recorte) == 1
        assert recorte[0].id_treino == "TR-2008-1600"

    def test_filtro_sem_correspondencia_devolve_lista_vazia(self, servico_misto):
        assert servico_misto.filtrar(Filtros(atleta="Ninguém")) == []

    def test_opcoes_de_filtro_sao_coerentes_com_a_selecao(self, servico_misto):
        """Escolher o treino do alvo triplo restringe as distâncias a 18m."""
        opcoes = servico_misto.opcoes_de_filtro(Filtros(tipo_alvo="Alvo Triplo"))
        assert opcoes["distancias"] == ["18m"]
        assert [t["id_treino"] for t in opcoes["treinos"]] == ["TR-2008-1600"]


class TestHistoricoEComparacao:
    def test_historico_ordena_por_data(self, servico_misto):
        historico = servico_misto.historico(Filtros())
        datas = [p["data_treino"] for p in historico["pontos"]]
        assert datas == sorted(datas)

    def test_agregado_do_historico(self, servico_misto):
        historico = servico_misto.historico(Filtros())
        assert historico["agregado"]["treinos"] == 3
        assert historico["agregado"]["primeiro_treino"] == "2026-07-01"
        assert historico["agregado"]["ultimo_treino"] == "2026-08-20"

    def test_comparacao_entre_treino_antigo_e_novo(self, servico_misto):
        """Um treino histórico e um novo, lado a lado nas mesmas métricas."""
        resultado = servico_misto.comparar(["TR-0107-0900", "TR-1508-1400"])
        assert len(resultado["treinos"]) == 2
        assert resultado["nao_encontrados"] == []
        for linha in resultado["treinos"]:
            assert linha["total"] is not None
            assert linha["distancia_media_centro"] is not None

    def test_id_inexistente_e_reportado_sem_derrubar(self, servico_misto):
        resultado = servico_misto.comparar(["TR-0107-0900", "NAO-EXISTE"])
        assert resultado["nao_encontrados"] == ["NAO-EXISTE"]
        assert len(resultado["treinos"]) == 1


class TestRobustez:
    def test_documento_sem_id_treino_e_ignorado_sem_quebrar(self):
        from tests.conftest import FonteFalsa
        from app.services.analytics_service import ServicoAnalitico

        fonte = FonteFalsa([("lixo", {"atleta": "X"})], [])
        assert ServicoAnalitico(fonte, ttl_cache=0).treinos() == []

    def test_disparo_sem_coordenada_e_descartado(self):
        from tests.conftest import FonteFalsa, doc_serie_legado
        from app.services.analytics_service import ServicoAnalitico

        doc_id, dados = doc_serie_legado("TR-1", "T1", 1, flechas_string="10", total=10)
        fonte = FonteFalsa(
            [(doc_id, dados)],
            [(doc_id, {"flecha": 1, "x": None, "y": None}), (doc_id, {"flecha": 2, "x": 5, "y": 5})],
        )
        treino = ServicoAnalitico(fonte, ttl_cache=0).treinos()[0]
        assert treino.quantidade_flechas == 1

    def test_disparo_orfao_nao_derruba_a_carga(self):
        """Subcoleção cujo documento pai foi apagado."""
        from tests.conftest import FonteFalsa, doc_serie_legado, doc_disparo_legado
        from app.services.analytics_service import ServicoAnalitico

        doc_id, dados = doc_serie_legado("TR-1", "T1", 1, flechas_string="10", total=10)
        fonte = FonteFalsa(
            [(doc_id, dados)],
            [doc_disparo_legado(doc_id, 1, 5.0, 5.0), doc_disparo_legado("TR-ORFAO-T1-S1", 1, 1.0, 1.0)],
        )
        treinos = ServicoAnalitico(fonte, ttl_cache=0).treinos()
        assert len(treinos) == 1
        assert treinos[0].quantidade_flechas == 1

    def test_base_vazia_nao_quebra_nenhuma_analise(self):
        from tests.conftest import FonteFalsa
        from app.services.analytics_service import ServicoAnalitico

        servico = ServicoAnalitico(FonteFalsa([], []), ttl_cache=0)
        assert servico.treinos() == []
        assert servico.atletas() == []
        assert servico.historico(Filtros())["quantidade"] == 0
        assert servico.opcoes_de_filtro(Filtros())["treinos"] == []
