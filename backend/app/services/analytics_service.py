"""Serviço de aplicação: carrega, filtra e analisa.

Concentra a orquestração para que as rotas fiquem finas — cada endpoint
delega para um método daqui e não conhece Firestore, cache nem pandas.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Sequence

from app.analytics import geometry, metrics
from app.cache import CacheComTTL
from app.config import config
from app.models.domain import Serie, Treino
from app.services import normalize
from app.services.repository import FonteDeDados, Repositorio


@dataclass(frozen=True)
class Filtros:
    """Critérios de seleção do dashboard.

    `atleta` é comparado pela chave normalizada (sem acento de caixa nem
    espaço extra), porque o campo é texto livre no aplicativo.
    """

    atleta: str | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    tipo_alvo: str | None = None
    familia_alvo: str | None = None
    distancia: str | None = None
    tempo: str | None = None
    serie: int | None = None
    id_treino: str | None = None

    def aplica_a_serie(self, serie: Serie) -> bool:
        if self.tipo_alvo and serie.tipo_alvo != self.tipo_alvo:
            return False
        if self.familia_alvo and serie.familia_alvo != self.familia_alvo:
            return False
        if self.distancia and serie.distancia != self.distancia:
            return False
        if self.tempo and serie.tempo != self.tempo:
            return False
        if self.serie is not None and serie.numero != self.serie:
            return False
        return True

    def aplica_ao_treino(self, treino: Treino) -> bool:
        if self.id_treino and treino.id_treino != self.id_treino:
            return False
        if self.atleta and normalize.chave_de_atleta(treino.atleta) != normalize.chave_de_atleta(
            self.atleta
        ):
            return False
        if self.data_inicio and (treino.data_treino is None or treino.data_treino < self.data_inicio):
            return False
        if self.data_fim and (treino.data_treino is None or treino.data_treino > self.data_fim):
            return False
        return True


class ServicoAnalitico:
    """Fachada de leitura e análise."""

    def __init__(self, fonte: FonteDeDados, ttl_cache: int | None = None) -> None:
        self._repositorio = Repositorio(fonte)
        ttl = config().ttl_cache if ttl_cache is None else ttl_cache
        self._cache: CacheComTTL[list[Treino]] = CacheComTTL(ttl)

    # ---------- carga ----------

    def treinos(self) -> list[Treino]:
        return self._cache.obter(self._repositorio.carregar_treinos)

    def invalidar_cache(self) -> None:
        self._cache.invalidar()

    def estado_do_cache(self) -> dict:
        return {"valido": self._cache.valido, "idade_segundos": self._cache.idade_segundos()}

    # ---------- seleção ----------

    def filtrar(self, filtros: Filtros) -> list[Treino]:
        """Aplica os filtros em dois níveis.

        Atleta, data e ID selecionam treinos inteiros. Tipo de alvo,
        distância, tempo e série selecionam séries dentro do treino — o
        treino sobrevive com o subconjunto de séries que casou, e some
        se nenhuma casar.
        """
        selecionados: list[Treino] = []
        for treino in self.treinos():
            if not filtros.aplica_ao_treino(treino):
                continue
            series = [s for s in treino.series if filtros.aplica_a_serie(s)]
            if not series:
                continue
            recorte = replace(treino, series=list(series))
            recorte.ordenar()
            selecionados.append(recorte)
        return selecionados

    def treino_por_id(self, id_treino: str, filtros: Filtros | None = None) -> Treino | None:
        base = filtros or Filtros()
        for treino in self.filtrar(replace(base, id_treino=id_treino)):
            return treino
        return None

    # ---------- catálogos ----------

    def atletas(self) -> list[dict]:
        """Atletas com o resumo do que existe para cada um.

        A grafia apresentada é a mais frequente entre os registros, já
        que o campo é livre e admite variações de digitação.
        """
        por_chave: dict[str, dict] = {}
        for treino in self.treinos():
            chave = normalize.chave_de_atleta(treino.atleta)
            if not chave:
                continue
            registro = por_chave.setdefault(
                chave,
                {
                    "chave": chave,
                    "grafias": {},
                    "treinos": 0,
                    "flechas": 0,
                    "primeiro_treino": None,
                    "ultimo_treino": None,
                },
            )
            registro["grafias"][treino.atleta] = registro["grafias"].get(treino.atleta, 0) + 1
            registro["treinos"] += 1
            registro["flechas"] += treino.quantidade_flechas
            if treino.data_treino:
                iso = treino.data_treino.isoformat()
                if registro["primeiro_treino"] is None or iso < registro["primeiro_treino"]:
                    registro["primeiro_treino"] = iso
                if registro["ultimo_treino"] is None or iso > registro["ultimo_treino"]:
                    registro["ultimo_treino"] = iso

        resultado = []
        for registro in por_chave.values():
            nome = max(registro["grafias"].items(), key=lambda item: (item[1], item[0]))[0]
            resultado.append(
                {
                    "atleta": nome,
                    "chave": registro["chave"],
                    "treinos": registro["treinos"],
                    "flechas": registro["flechas"],
                    "primeiro_treino": registro["primeiro_treino"],
                    "ultimo_treino": registro["ultimo_treino"],
                }
            )
        resultado.sort(key=lambda item: item["atleta"].casefold())
        return resultado

    def opcoes_de_filtro(self, filtros: Filtros) -> dict:
        """Opções coerentes entre si.

        As listas são derivadas do recorte já filtrado, de modo que
        escolher um atleta reduz as datas às daquele atleta, e escolher
        uma data reduz os treinos àquela data — sem consulta extra ao
        Firestore, porque tudo sai do mesmo conjunto em cache.
        """
        treinos = self.filtrar(filtros)
        datas, tipos, distancias, tempos, series = set(), set(), set(), set(), set()
        lista_treinos = []

        for treino in treinos:
            if treino.data_treino:
                datas.add(treino.data_treino.isoformat())
            lista_treinos.append(
                {
                    "id_treino": treino.id_treino,
                    "atleta": treino.atleta,
                    "data_treino": treino.data_treino.isoformat() if treino.data_treino else None,
                    "series": treino.quantidade_series,
                    "flechas": treino.quantidade_flechas,
                    "total": treino.total,
                    "tipo_alvo": treino.tipo_alvo_predominante,
                }
            )
            for serie in treino.series:
                tipos.add(serie.tipo_alvo)
                if serie.distancia:
                    distancias.add(serie.distancia)
                tempos.add(serie.tempo)
                series.add(serie.numero)

        lista_treinos.sort(key=lambda t: (t["data_treino"] or "", t["id_treino"]), reverse=True)

        return {
            "atletas": self.atletas(),
            "datas": sorted(datas, reverse=True),
            "tipos_de_alvo": sorted(tipos),
            "distancias": sorted(distancias, key=_ordem_de_distancia),
            "tempos": sorted(tempos),
            "series": sorted(series),
            "treinos": lista_treinos,
        }

    # ---------- análises ----------

    def analisar(self, treino: Treino) -> dict:
        return metrics.analisar_treino(treino)

    def disparos(self, treino: Treino) -> dict:
        quadro = metrics.quadro_de_disparos(treino.series)
        geo = geometry.geometria(treino.tipo_alvo_predominante)
        dispersao = metrics.com_cm(metrics.metricas_de_dispersao(quadro), geo)

        return {
            "treino": metrics.descrever_treino(treino),
            "geometria": geometry.descrever(treino.tipo_alvo_predominante),
            "disparos": metrics.serializar_disparos(treino),
            # Centro do grupo geral — só faz sentido plotar direto para
            # alvo de face única. Para o Alvo Triplo, o frontend usa
            # `agrupamento_por_face` (um centro por face real).
            "centro_grupo": {
                "x": dispersao.get("centro_grupo_x"),
                "y": dispersao.get("centro_grupo_y"),
            },
            "raio_95_grupo": dispersao.get("raio_95_grupo"),
            "agrupamento_por_face": metrics.agrupamento_por_face(quadro, geo),
        }

    def historico(self, filtros: Filtros) -> dict:
        """Série temporal de métricas, um ponto por treino."""
        treinos = self.filtrar(filtros)
        pontos = [metrics.resumo_para_historico(t) for t in treinos]
        pontos.sort(key=lambda p: (p["data_treino"] or "", p["id_treino"]))
        return {
            "quantidade": len(pontos),
            "pontos": pontos,
            "agregado": _agregado_do_historico(pontos),
        }

    def comparar(self, ids: Sequence[str], filtros: Filtros | None = None) -> dict:
        base = filtros or Filtros()
        treinos = [t for t in (self.treino_por_id(i, base) for i in ids) if t is not None]
        faltantes = [i for i in ids if all(t.id_treino != i for t in treinos)]
        resultado = metrics.comparar_treinos(treinos)
        resultado["nao_encontrados"] = faltantes
        return resultado


def _ordem_de_distancia(valor: str) -> tuple[int, str]:
    """Ordena '18m', '30m', '50m', '70m' numericamente, não como texto."""
    digitos = "".join(c for c in valor if c.isdigit())
    return (int(digitos) if digitos else 9999, valor)


def _agregado_do_historico(pontos: list[dict]) -> dict:
    """Números de topo da visão histórica."""
    if not pontos:
        return {"treinos": 0}

    def media(chave: str) -> float | None:
        valores = [p[chave] for p in pontos if p.get(chave) is not None]
        return round(sum(valores) / len(valores), 3) if valores else None

    totais = [p["total"] for p in pontos if p.get("total") is not None]
    return {
        "treinos": len(pontos),
        "flechas": sum(p.get("quantidade_flechas") or 0 for p in pontos),
        "melhor_total": max(totais) if totais else None,
        "media_total": round(sum(totais) / len(totais), 2) if totais else None,
        "media_por_flecha": media("media"),
        "media_distancia_centro": media("distancia_media_centro"),
        "media_distancia_centro_cm": media("distancia_media_centro_cm"),
        "media_dispersao_radial": media("dispersao_radial"),
        "media_dispersao_radial_cm": media("dispersao_radial_cm"),
        "primeiro_treino": pontos[0].get("data_treino"),
        "ultimo_treino": pontos[-1].get("data_treino"),
    }
