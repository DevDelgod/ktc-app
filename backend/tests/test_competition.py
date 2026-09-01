"""Testes do modo Competição: domínio, analytics, relatório e API.

Cobre o ciclo pedido explicitamente: criar competição, registrar
flechas, salvar, recuperar, finalizar, gerar relatório — tudo sobre uma
fonte de dados sintética, sem tocar no Firestore real, no mesmo padrão
usado para treinos em `conftest.py`.
"""

from __future__ import annotations

import pytest

from app.analytics import performance
from app.analytics.competition import analisar_competicao, progresso
from app.models.competition import STATUS_CONCLUIDA, STATUS_EM_ANDAMENTO, STATUS_PLANEJADA
from app.services.competition_domain import carregar_competicao, listar_competicoes_resumo
from app.services.competition_service import ServicoCompeticoes


class FonteCompeticoesFalsa:
    """Fonte em memória com o mesmo contrato de `FirestoreCompeticoes`."""

    def __init__(self) -> None:
        self._competicoes: dict[str, dict] = {}
        self._series: dict[str, list[tuple[str, dict]]] = {}
        self._disparos: dict[str, dict[str, list[dict]]] = {}

    def adicionar_competicao(self, comp_id: str, dados: dict) -> None:
        self._competicoes[comp_id] = dados
        self._series.setdefault(comp_id, [])
        self._disparos.setdefault(comp_id, {})

    def adicionar_serie(self, comp_id: str, serie_id: str, dados: dict, disparos: list[dict]) -> None:
        self._series[comp_id].append((serie_id, dados))
        self._disparos[comp_id][serie_id] = disparos

    def listar(self):
        for comp_id, dados in self._competicoes.items():
            series_leves = [s for _, s in self._series.get(comp_id, [])]
            yield comp_id, dados, series_leves

    def carregar(self, competicao_id: str):
        if competicao_id not in self._competicoes:
            return None, [], {}
        return (
            self._competicoes[competicao_id],
            self._series.get(competicao_id, []),
            self._disparos.get(competicao_id, {}),
        )


def _disparo(numero: int, x: float, y: float, score: str | None = None) -> dict:
    dados = {"flecha": numero, "x": x, "y": y, "tipoAlvo": "Alvo Unitário"}
    if score is not None:
        dados["score"] = score
    return dados


def _competicao_basica() -> FonteCompeticoesFalsa:
    """Campeonato Brasileiro: 4 séries na prova 'Classificação', 6 flechas
    cada, todas finalizadas — o suficiente para exercitar destaques,
    consistência e comparação início×fim (mínimo de 4 séries)."""
    fonte = FonteCompeticoesFalsa()
    fonte.adicionar_competicao(
        "CP-TESTE",
        {
            "nome": "Campeonato Brasileiro",
            "atleta": "Gabriel Delgado",
            "data": "2026-08-31",
            "local": "Rio de Janeiro",
            "categoria": "Recurvo Adulto",
            "modalidade": "Outdoor 70m",
            "tipoAlvo": "Alvo Unitário",
            "distancia": "70m",
            "status": STATUS_EM_ANDAMENTO,
            "criadoEm": "2026-08-31T10:00:00+00:00",
        },
    )

    # Série 1: grupo largo e deslocado. Série 4: grupo apertado e centrado.
    # Isso dá uma tendência real de melhora para os testes de narrativa.
    series = [
        (1, [(20, 20, "8"), (25, 15, "8"), (18, 22, "9"), (30, 10, "7"), (22, 18, "8"), (28, 12, "8")]),
        (2, [(15, 15, "9"), (18, 12, "9"), (12, 16, "9"), (20, 10, "8"), (14, 14, "9"), (17, 13, "9")]),
        (3, [(8, 8, "9"), (10, 6, "10"), (6, 9, "9"), (12, 5, "9"), (7, 7, "10"), (9, 6, "9")]),
        (4, [(2, 2, "X"), (3, 1, "10"), (1, 3, "10"), (4, 0, "10"), (2, 1, "10"), (3, 2, "10")]),
    ]
    for numero, flechas in series:
        serie_id = f"CP-TESTE-Classificacao-S{numero}"
        rotulos = [f[2] for f in flechas]
        total = sum({"X": 10, "M": 0}.get(r, int(r) if r.isdigit() else 0) for r in rotulos)
        fonte.adicionar_serie(
            "CP-TESTE",
            serie_id,
            {
                "prova": "Classificação",
                "numero": numero,
                "atleta": "Gabriel Delgado",
                "tipoAlvo": "Alvo Unitário",
                "distancia": "70m",
                "flechasString": " ".join(rotulos),
                "total": total,
                "criadoEm": "2026-08-31T10:00:00+00:00",
                "atualizadoEm": "2026-08-31T10:05:00+00:00",
            },
            [_disparo(i + 1, x, y, r) for i, (x, y, r) in enumerate(flechas)],
        )
    return fonte


class TestModeloDeDominio:
    def test_recuperar_competicao_inexistente_devolve_none(self):
        servico = ServicoCompeticoes(FonteCompeticoesFalsa(), ttl_cache=0)
        assert servico.obter("NAO-EXISTE") is None

    def test_criar_e_recuperar_competicao(self):
        fonte = _competicao_basica()
        competicao = carregar_competicao(fonte, "CP-TESTE")
        assert competicao is not None
        assert competicao.nome == "Campeonato Brasileiro"
        assert competicao.atleta == "Gabriel Delgado"
        assert competicao.quantidade_series == 4
        assert competicao.quantidade_flechas == 24

    def test_series_ficam_ordenadas_cronologicamente(self):
        fonte = _competicao_basica()
        competicao = carregar_competicao(fonte, "CP-TESTE")
        ordens = [s.ordem for s in sorted(competicao.series, key=lambda s: s.numero)]
        assert ordens == [1, 2, 3, 4]

    def test_serie_nao_finalizada_fica_sem_total(self):
        fonte = FonteCompeticoesFalsa()
        fonte.adicionar_competicao("CP-ABERTA", {"nome": "Teste", "atleta": "G", "status": STATUS_EM_ANDAMENTO})
        fonte.adicionar_serie(
            "CP-ABERTA", "CP-ABERTA-Prova-S1",
            {"prova": "Prova", "numero": 1, "atleta": "G"},
            [_disparo(1, 5.0, 5.0)],  # sem score: alvo confirmado, pontuação pendente
        )
        competicao = carregar_competicao(fonte, "CP-ABERTA")
        serie = competicao.series[0]
        assert serie.finalizada is False
        assert serie.disparos[0].pontos is None

    def test_listar_competicoes_traz_metadados_sem_ler_series(self):
        fonte = _competicao_basica()
        resumo = listar_competicoes_resumo(fonte)
        assert len(resumo) == 1
        assert resumo[0]["nome"] == "Campeonato Brasileiro"
        assert resumo[0]["status"] == STATUS_EM_ANDAMENTO

    def test_listar_competicoes_traz_o_placar_no_cartao(self):
        """O cartão da listagem mostra o placar sem precisar abrir a
        competição — soma direto dos `total` de cada série, sem ler
        disparos."""
        fonte = _competicao_basica()
        resumo = listar_competicoes_resumo(fonte)
        assert resumo[0]["total"] == 48 + 53 + 56 + 60
        assert resumo[0]["quantidade_series"] == 4
        assert resumo[0]["quantidade_flechas"] == 24

    def test_placar_ignora_serie_nao_finalizada(self):
        """Uma série confirmada no alvo mas sem pontuação digitada não
        soma no total nem conta como série completa."""
        fonte = _competicao_basica()
        fonte.adicionar_serie(
            "CP-TESTE", "CP-TESTE-Classificacao-S5",
            {"prova": "Classificação", "numero": 5, "atleta": "Gabriel Delgado"},
            [_disparo(1, 1.0, 1.0), _disparo(2, 2.0, 2.0)],
        )
        resumo = listar_competicoes_resumo(fonte)
        assert resumo[0]["total"] == 48 + 53 + 56 + 60  # inalterado
        assert resumo[0]["quantidade_series"] == 4  # a S5 nao conta

    def test_competicao_sem_series_tem_placar_zerado(self):
        fonte = FonteCompeticoesFalsa()
        fonte.adicionar_competicao("CP-VAZIA", {"nome": "Nova", "atleta": "G", "status": STATUS_PLANEJADA})
        resumo = listar_competicoes_resumo(fonte)
        assert resumo[0]["total"] == 0
        assert resumo[0]["quantidade_series"] == 0
        assert resumo[0]["quantidade_flechas"] == 0


class TestAnalyticsReaproveitaTreino:
    """Prova de que scoring/dispersion/consistency funcionam sem
    modificação sobre SerieCompeticao — o reaproveitamento real pedido."""

    def test_pontuacao_soma_as_quatro_series(self):
        fonte = _competicao_basica()
        competicao = carregar_competicao(fonte, "CP-TESTE")
        pacote = analisar_competicao(competicao)
        assert pacote["pontuacao"]["total"] == competicao.total
        assert pacote["pontuacao"]["quantidade_flechas"] == 24

    def test_melhor_e_pior_serie_calculadas(self):
        fonte = _competicao_basica()
        competicao = carregar_competicao(fonte, "CP-TESTE")
        pacote = analisar_competicao(competicao)
        assert pacote["pontuacao"]["melhor_serie"]["rotulo"] == "Classificação-S4"
        assert pacote["pontuacao"]["pior_serie"]["rotulo"] == "Classificação-S1"

    def test_dispersao_convertida_para_cm(self):
        fonte = _competicao_basica()
        competicao = carregar_competicao(fonte, "CP-TESTE")
        pacote = analisar_competicao(competicao)
        assert "dispersao_radial_cm" in pacote["dispersao"]
        assert "distancia_media_centro_cm" in pacote["dispersao"]

    def test_consistencia_usa_as_quatro_series(self):
        fonte = _competicao_basica()
        competicao = carregar_competicao(fonte, "CP-TESTE")
        pacote = analisar_competicao(competicao)
        assert pacote["consistencia"]["series_consideradas"] == 4


class TestProgresso:
    def test_competicao_em_andamento_aponta_ultima_serie(self):
        fonte = _competicao_basica()
        competicao = carregar_competicao(fonte, "CP-TESTE")
        estado = progresso(competicao)
        assert estado["serie_atual"]["numero"] == 4
        assert estado["score_total"] == competicao.total

    def test_serie_aberta_e_identificada_como_atual(self):
        fonte = _competicao_basica()
        fonte.adicionar_serie(
            "CP-TESTE", "CP-TESTE-Classificacao-S5",
            {"prova": "Classificação", "numero": 5, "atleta": "Gabriel Delgado"},
            [_disparo(1, 1.0, 1.0), _disparo(2, 2.0, 2.0)],
        )
        competicao = carregar_competicao(fonte, "CP-TESTE")
        estado = progresso(competicao)
        assert estado["serie_atual"]["numero"] == 5
        assert estado["serie_atual"]["finalizada"] is False


class TestRelatorioFinal:
    def test_relatorio_completo_tem_todas_as_secoes(self):
        fonte = _competicao_basica()
        competicao = carregar_competicao(fonte, "CP-TESTE")
        relatorio = performance.montar_relatorio(competicao)
        assert set(relatorio) == {
            "resumo", "pontuacao", "dispersao", "agrupamento_por_face",
            "consistencia", "distribuicao", "qualidade", "series",
            "destaques", "pontos_de_atencao", "comparacao_inicio_fim", "analise_final",
        }

    def test_destaques_encontra_melhor_flecha_e_serie(self):
        fonte = _competicao_basica()
        competicao = carregar_competicao(fonte, "CP-TESTE")
        relatorio = performance.montar_relatorio(competicao)
        assert relatorio["destaques"]["melhor_pontuacao"]["pontos"] == 10
        assert relatorio["destaques"]["melhor_serie"]["rotulo"] == "Classificação-S4"

    def test_pontos_de_atencao_encontra_pior_flecha_e_serie(self):
        fonte = _competicao_basica()
        competicao = carregar_competicao(fonte, "CP-TESTE")
        relatorio = performance.montar_relatorio(competicao)
        assert relatorio["pontos_de_atencao"]["pior_pontuacao"]["pontos"] == 7
        assert relatorio["pontos_de_atencao"]["pior_serie"]["rotulo"] == "Classificação-S1"

    def test_comparacao_inicio_fim_detecta_aproximacao_real(self):
        """As séries 1-2 (início) estão longe do centro; 3-4 (fim) perto.
        O relatório tem que refletir isso como fato, não como frase vaga."""
        fonte = _competicao_basica()
        competicao = carregar_competicao(fonte, "CP-TESTE")
        relatorio = performance.montar_relatorio(competicao)
        comparacao = relatorio["comparacao_inicio_fim"]
        assert comparacao is not None
        assert comparacao["aproximou_do_centro"] is True
        assert comparacao["fim"]["distancia_media_centro_cm"] < comparacao["inicio"]["distancia_media_centro_cm"]

    def test_analise_final_nao_inventa_melhora_sem_dado(self):
        """Competição com só 1 série: não há dado para 'início x fim',
        e o texto não pode fingir uma tendência que não existe."""
        fonte = FonteCompeticoesFalsa()
        fonte.adicionar_competicao("CP-CURTA", {"nome": "Teste", "atleta": "G", "status": STATUS_CONCLUIDA})
        fonte.adicionar_serie(
            "CP-CURTA", "CP-CURTA-Prova-S1",
            {"prova": "Prova", "numero": 1, "atleta": "G", "flechasString": "9 9 9", "total": 27},
            [_disparo(1, 5, 5, "9"), _disparo(2, 5, 5, "9"), _disparo(3, 5, 5, "9")],
        )
        competicao = carregar_competicao(fonte, "CP-CURTA")
        relatorio = performance.montar_relatorio(competicao)
        assert relatorio["comparacao_inicio_fim"] is None
        assert "insuficiente" in relatorio["analise_final"].lower() or "poucas" in relatorio["analise_final"].lower()

    def test_agrupamento_destaque_exige_amostra_minima(self):
        """Uma série de 1 flecha não pode 'vencer' como melhor
        agrupamento só por ter dispersão zero artificial."""
        fonte = FonteCompeticoesFalsa()
        fonte.adicionar_competicao("CP-MIN", {"nome": "Teste", "atleta": "G", "status": STATUS_CONCLUIDA})
        fonte.adicionar_serie(
            "CP-MIN", "CP-MIN-Prova-S1",
            {"prova": "Prova", "numero": 1, "atleta": "G", "flechasString": "9", "total": 9},
            [_disparo(1, 50, 50, "9")],  # 1 flecha só, longe do centro
        )
        fonte.adicionar_serie(
            "CP-MIN", "CP-MIN-Prova-S2",
            {"prova": "Prova", "numero": 2, "atleta": "G", "flechasString": "9 9 9", "total": 27},
            [_disparo(1, 5, 5, "9"), _disparo(2, 8, 5, "9"), _disparo(3, 5, 8, "9")],
        )
        competicao = carregar_competicao(fonte, "CP-MIN")
        relatorio = performance.montar_relatorio(competicao)
        # A série de 1 flecha não pode aparecer como "melhor agrupamento"
        # mesmo tendo dispersão radial 0 (degenerada, não real).
        melhor = relatorio["destaques"]["melhor_agrupamento"]
        if melhor is not None:
            assert melhor["rotulo"] != "Prova-S1"


class TestServicoCompeticoes:
    """Ciclo completo através da fachada, incluindo cache."""

    def test_ciclo_criar_registrar_recuperar_finalizar(self):
        fonte = _competicao_basica()
        servico = ServicoCompeticoes(fonte, ttl_cache=0)

        lista = servico.listar()
        assert len(lista) == 1

        competicao = servico.obter("CP-TESTE")
        assert competicao.quantidade_flechas == 24

        # "Registrar flecha": mais uma série chega na fonte.
        fonte.adicionar_serie(
            "CP-TESTE", "CP-TESTE-Classificacao-S5",
            {"prova": "Classificação", "numero": 5, "atleta": "Gabriel Delgado", "flechasString": "10 10 10 10 10 10", "total": 60},
            [_disparo(i + 1, 1.0, 1.0, "10") for i in range(6)],
        )
        servico.invalidar_cache("CP-TESTE")
        recarregada = servico.obter("CP-TESTE")
        assert recarregada.quantidade_series == 5

        # "Finalizar": muda o status na fonte e relê.
        fonte._competicoes["CP-TESTE"]["status"] = STATUS_CONCLUIDA
        servico.invalidar_cache("CP-TESTE")
        finalizada = servico.obter("CP-TESTE")
        assert finalizada.status == STATUS_CONCLUIDA

        # "Gerar relatório" sobre o estado final.
        relatorio = servico.relatorio("CP-TESTE")
        assert relatorio["resumo"]["status"] == STATUS_CONCLUIDA
        assert relatorio["resumo"]["quantidade_series"] == 5

    def test_analytics_e_disparos_e_progresso_nao_quebram(self):
        fonte = _competicao_basica()
        servico = ServicoCompeticoes(fonte, ttl_cache=0)
        assert servico.analytics("CP-TESTE")["pontuacao"]["total"] > 0
        assert len(servico.disparos("CP-TESTE")["disparos"]) == 24
        assert servico.progresso("CP-TESTE")["quantidade_series"] == 4

    def test_competicao_planejada_sem_series_nao_quebra_nada(self):
        """Competição recém-criada, sem nenhuma flecha ainda."""
        fonte = FonteCompeticoesFalsa()
        fonte.adicionar_competicao("CP-NOVA", {"nome": "Nova", "atleta": "G", "status": STATUS_PLANEJADA})
        servico = ServicoCompeticoes(fonte, ttl_cache=0)

        assert servico.progresso("CP-NOVA")["serie_atual"] is None
        assert servico.analytics("CP-NOVA")["pontuacao"]["quantidade_flechas"] == 0
        assert servico.disparos("CP-NOVA")["disparos"] == []
