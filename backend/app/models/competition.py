"""Modelo de domínio do modo Competição.

Uma competição é uma coleção Firestore **separada** de `treinos`
(`competicoes`, não misturada com dados de treino), mas reaproveita a
mesma forma de disparo (`Disparo`, importado de `domain.py` sem
alteração) e — o ponto central do reaproveitamento — os mesmos nomes de
atributo que `Serie` usa (`tempo`, `numero`, `total`, `finalizada`,
`quantidade_flechas`, `flechas_string`, `tipo_alvo`, `doc_id`, `ordem`,
`disparos`). Isso permite que `SerieCompeticao` passe, sem nenhuma
adaptação, pelas mesmas funções de `app/analytics/scoring.py` e
`consistency.py` que já processam séries de treino — é a forma real de
"não duplicar a lógica de pontuação" pedida, não apenas uma frase.

Hierarquia:

    Competicao (metadados: nome, data, local, categoria, modalidade...)
        └── SerieCompeticao (uma "prova" + número de série, ex: Classificação-S1)
                └── Disparo (igual ao de treino: numero, x, y, pontos...)

O campo `prova` faz o papel do `tempo` (T1/T2) do treino: identifica em
qual evento da competição aquela série está — mas é texto livre
("Classificação", "Eliminatória 1/16"), porque competições reais têm
fases com nomes variados, ao contrário do treino que sempre é T1/T2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.models.domain import Disparo

STATUS_PLANEJADA = "planejada"
STATUS_EM_ANDAMENTO = "em_andamento"
STATUS_PAUSADA = "pausada"
STATUS_CONCLUIDA = "concluida"

STATUS_VALIDOS = (STATUS_PLANEJADA, STATUS_EM_ANDAMENTO, STATUS_PAUSADA, STATUS_CONCLUIDA)


@dataclass
class SerieCompeticao:
    """Uma série dentro de uma prova da competição.

    Atributos nomeados deliberadamente como em `Serie` (treino) para que
    as funções de `scoring.py` e `consistency.py` funcionem sem
    modificação sobre uma lista de `SerieCompeticao` — ver `tempo`.
    """

    doc_id: str
    competicao_id: str
    prova: str
    numero: int
    atleta: str
    tipo_alvo: str
    distancia: str | None
    total_registrado: int | None
    flechas_string: str | None
    criado_em: str | None
    atualizado_em: str | None
    disparos: list[Disparo] = field(default_factory=list)
    ordem: int = 0

    @property
    def tempo(self) -> str:
        """Alias de `prova`. Existe só para reaproveitar as funções de
        `scoring`/`consistency` escritas originalmente para `Serie`."""
        return self.prova

    @property
    def finalizada(self) -> bool:
        return self.total_registrado is not None

    @property
    def total(self) -> int:
        if self.total_registrado is not None:
            return self.total_registrado
        return sum(d.pontos for d in self.disparos if d.pontos is not None)

    @property
    def quantidade_flechas(self) -> int:
        return len(self.disparos)


@dataclass
class Competicao:
    """Uma competição — o agrupador de todas as provas/séries."""

    id: str
    nome: str
    atleta: str
    data: date | None
    local: str | None
    categoria: str | None
    modalidade: str | None
    tipo_alvo: str
    distancia: str | None
    status: str
    criado_em: str | None
    atualizado_em: str | None
    finalizado_em: str | None
    series: list[SerieCompeticao] = field(default_factory=list)

    @property
    def disparos(self) -> list[Disparo]:
        return [d for s in self.series for d in s.disparos]

    @property
    def provas(self) -> list[str]:
        return sorted({s.prova for s in self.series})

    @property
    def total(self) -> int:
        return sum(s.total for s in self.series)

    @property
    def quantidade_series(self) -> int:
        return len(self.series)

    @property
    def quantidade_flechas(self) -> int:
        return sum(s.quantidade_flechas for s in self.series)

    def ordenar(self) -> None:
        self.series.sort(key=lambda s: (s.prova, s.numero))
        for indice, serie in enumerate(self.series, start=1):
            serie.ordem = indice
            serie.disparos.sort(key=lambda d: d.numero)
