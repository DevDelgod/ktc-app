"""Fachada de leitura e análise do modo Competição.

Espelha `ServicoAnalitico` (treinos), mas com cache separado — a lista
de competições muda numa cadência bem diferente da lista de treinos, e
misturar os dois TTLs faria um invalidar o outro sem necessidade.

Escrita fica inteiramente fora daqui: criar competição, gravar alvo,
gravar pontuação e mudar status são operações do frontend direto no
Firestore (`frontend/js/competitions-firebase.js`), no mesmo padrão que
`firebase.js` já usa para treinos. Este serviço só lê e deriva
estatística — é o mesmo papel que `ServicoAnalitico` cumpre hoje, sem
introduzir um segundo caminho de escrita paralelo ao que já existe.
"""

from __future__ import annotations

import numpy as np

from app.analytics import competition as competition_analytics
from app.analytics import geometry
from app.analytics import performance as performance_analytics
from app.cache import CacheComTTL
from app.config import config
from app.models.competition import Competicao
from app.services.competition_domain import carregar_competicao, listar_competicoes_resumo
from app.services.competition_repository import FonteDeCompeticoes


class ServicoCompeticoes:
    def __init__(self, fonte: FonteDeCompeticoes, ttl_cache: int | None = None) -> None:
        self._fonte = fonte
        self._ttl = config().ttl_cache if ttl_cache is None else ttl_cache
        self._cache_lista: CacheComTTL[list[dict]] = CacheComTTL(self._ttl)
        self._cache_competicoes: dict[str, CacheComTTL[Competicao | None]] = {}

    def listar(self) -> list[dict]:
        return self._cache_lista.obter(lambda: listar_competicoes_resumo(self._fonte))

    def obter(self, competicao_id: str) -> Competicao | None:
        cache = self._cache_competicoes.setdefault(competicao_id, CacheComTTL(self._ttl))
        return cache.obter(lambda: carregar_competicao(self._fonte, competicao_id))

    def invalidar_cache(self, competicao_id: str | None = None) -> None:
        self._cache_lista.invalidar()
        if competicao_id is not None:
            self._cache_competicoes.pop(competicao_id, None)
        else:
            self._cache_competicoes.clear()

    def progresso(self, competicao_id: str) -> dict | None:
        competicao = self.obter(competicao_id)
        if competicao is None:
            return None
        return competition_analytics.progresso(competicao)

    def analytics(self, competicao_id: str) -> dict | None:
        competicao = self.obter(competicao_id)
        if competicao is None:
            return None
        return competition_analytics.analisar_competicao(competicao)

    def disparos(self, competicao_id: str) -> dict | None:
        competicao = self.obter(competicao_id)
        if competicao is None:
            return None

        quadro = competition_analytics.quadro_de_disparos_competicao(competicao.series)
        colunas = [
            "doc_id", "prova", "serie", "ordem_serie", "flecha", "x", "y", "dx", "dy",
            "face_x", "face_y", "rotulo", "pontos", "distancia_centro", "distancia_centro_cm",
            "pontos_geometricos", "rotulo_geometrico", "dentro_do_alvo", "tipo_alvo",
        ]
        if not quadro.empty:
            quadro = quadro.copy()
            quadro["distancia_centro_cm"] = quadro.apply(
                lambda linha: round(
                    geometry.geometria(linha["tipo_alvo"]).unidades_para_cm(linha["distancia_centro"]), 3
                ),
                axis=1,
            )
        disparos = (
            quadro[colunas].replace({np.nan: None}).to_dict(orient="records") if not quadro.empty else []
        )
        return {
            "competicao": competition_analytics.descrever_competicao(competicao),
            "geometria": geometry.descrever(competicao.tipo_alvo),
            "disparos": disparos,
        }

    def relatorio(self, competicao_id: str) -> dict | None:
        competicao = self.obter(competicao_id)
        if competicao is None:
            return None
        return performance_analytics.montar_relatorio(competicao)
