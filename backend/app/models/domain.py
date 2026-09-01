"""Modelo de domínio do KTC.

O Firestore guarda **uma série por documento** — o ID é
`{idTreino}-{tempo}-S{serie}`, apesar de a coleção se chamar `treinos`.
Um treino real (uma sessão) é o conjunto de séries que compartilham o
mesmo `idTreino`.

Este módulo reconstrói essa hierarquia em memória, sem alterar nada no
banco:

    Treino (idTreino)
      └── Série (tempo, serie)
            └── Disparo (F1..Fn)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable


@dataclass
class Disparo:
    """Uma flecha registrada, com coordenada e pontuação resolvida."""

    numero: int
    x: float
    y: float
    id_disparo: str | None = None

    # Pontuação digitada pelo atleta. Vem do campo `score` do documento
    # quando existe (registros novos) ou da posição correspondente em
    # `flechasString` (registros históricos). `origem_score` diz qual.
    rotulo: str | None = None
    pontos: int | None = None
    origem_score: str = "ausente"

    # Derivados da geometria — calculados, nunca lidos do banco.
    distancia_centro: float = 0.0
    pontos_geometricos: int = 0
    rotulo_geometrico: str = "M"
    dentro_do_alvo: bool = False

    @property
    def score_confere(self) -> bool | None:
        """A pontuação digitada bate com a posição marcada?

        `None` quando não há pontuação digitada para comparar.
        """
        if self.pontos is None:
            return None
        return self.pontos == self.pontos_geometricos


@dataclass
class Serie:
    """Uma série — corresponde a um documento da coleção `treinos`."""

    doc_id: str
    id_treino: str
    tempo: str
    numero: int
    atleta: str
    data_treino: date | None
    distancia: str | None
    tipo_alvo: str
    familia_alvo: str
    clima: str | None
    v_vento: float | None
    d_vento: str | None
    total_registrado: int | None
    flechas_string: str | None
    criado_em: str | None
    atualizado_em: str | None
    disparos: list[Disparo] = field(default_factory=list)

    # Preenchido pelo agregador do treino: ordem cronológica real,
    # recalculada em vez de confiar no campo `serieGlobal`.
    ordem: int = 0

    @property
    def finalizada(self) -> bool:
        """A série passou pela segunda escrita (pontuação)?

        Séries em que o atleta confirmou o alvo mas não finalizou a
        pontuação existem no banco sem `total` nem `distancia`.
        """
        return self.total_registrado is not None

    @property
    def total(self) -> int:
        """Total da série.

        Prefere o valor gravado pelo app; se ausente, soma os disparos
        que tiverem pontuação resolvida.
        """
        if self.total_registrado is not None:
            return self.total_registrado
        return sum(d.pontos for d in self.disparos if d.pontos is not None)

    @property
    def quantidade_flechas(self) -> int:
        return len(self.disparos)


@dataclass
class Treino:
    """Uma sessão de treino — todas as séries com o mesmo `idTreino`."""

    id_treino: str
    atleta: str
    data_treino: date | None
    series: list[Serie] = field(default_factory=list)

    @property
    def disparos(self) -> list[Disparo]:
        return [d for s in self.series for d in s.disparos]

    @property
    def tipos_de_alvo(self) -> list[str]:
        return sorted({s.tipo_alvo for s in self.series})

    @property
    def tipo_alvo_predominante(self) -> str:
        """Tipo de alvo mais frequente entre as séries.

        Um treino normalmente usa um alvo só, mas o modelo de dados
        permite variação — a geometria é escolhida por série na hora de
        calcular, e este campo serve apenas para rotular o treino.
        """
        if not self.series:
            return ""
        contagem: dict[str, int] = {}
        for serie in self.series:
            contagem[serie.tipo_alvo] = contagem.get(serie.tipo_alvo, 0) + 1
        return max(contagem.items(), key=lambda item: (item[1], item[0]))[0]

    @property
    def distancias(self) -> list[str]:
        return sorted({s.distancia for s in self.series if s.distancia})

    @property
    def total(self) -> int:
        return sum(s.total for s in self.series)

    @property
    def quantidade_series(self) -> int:
        return len(self.series)

    @property
    def quantidade_flechas(self) -> int:
        return sum(s.quantidade_flechas for s in self.series)

    @property
    def criado_em(self) -> str | None:
        carimbos = [s.criado_em for s in self.series if s.criado_em]
        return min(carimbos) if carimbos else None

    def ordenar(self) -> None:
        """Ordena séries e recalcula a ordem cronológica."""
        self.series.sort(key=lambda s: (s.tempo, s.numero))
        for indice, serie in enumerate(self.series, start=1):
            serie.ordem = indice
            serie.disparos.sort(key=lambda d: d.numero)


def agrupar_em_treinos(series: Iterable[Serie]) -> list[Treino]:
    """Agrupa séries por `idTreino`, formando as sessões de treino."""
    por_id: dict[str, Treino] = {}
    for serie in series:
        treino = por_id.get(serie.id_treino)
        if treino is None:
            treino = Treino(
                id_treino=serie.id_treino,
                atleta=serie.atleta,
                data_treino=serie.data_treino,
            )
            por_id[serie.id_treino] = treino
        treino.series.append(serie)
        # A data e o atleta do treino vêm da primeira série que os tiver.
        if treino.data_treino is None and serie.data_treino is not None:
            treino.data_treino = serie.data_treino
        if not treino.atleta and serie.atleta:
            treino.atleta = serie.atleta

    treinos = list(por_id.values())
    for treino in treinos:
        treino.ordenar()
    treinos.sort(key=lambda t: (t.data_treino or date.min, t.id_treino))
    return treinos
