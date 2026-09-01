"""Fixtures de teste.

Os documentos sintéticos reproduzem a forma **exata** dos documentos que
o aplicativo grava no Firestore, incluindo as peculiaridades do formato
legado: `serie` como string, `v_vento` como string, `tipo_alvo` e
`tipoAlvo` duplicados, disparo sem campo de pontuação e `serieGlobal`
com o bug do +6 fixo.

É isso que permite validar a compatibilidade com os dados históricos sem
acesso ao banco real.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analytics_service import ServicoAnalitico  # noqa: E402


class FonteFalsa:
    """Fonte de dados em memória, com o mesmo contrato do Firestore."""

    def __init__(self, series: list[tuple[str, dict]], disparos: list[tuple[str, dict]]) -> None:
        self._series = series
        self._disparos = disparos

    def series(self):
        return list(self._series)

    def disparos(self):
        return list(self._disparos)


def doc_serie_legado(
    id_treino: str,
    tempo: str,
    serie: int,
    *,
    atleta: str = "Gabriel",
    data: str = "2026-08-20",
    distancia: str = "70m",
    tipo_alvo: str = "Alvo Unitário",
    flechas_string: str | None = "X 10 9 9 8 M",
    total: int | None = 46,
) -> tuple[str, dict]:
    """Documento no formato exatamente igual ao que o app grava hoje."""
    doc_id = f"{id_treino}-{tempo}-S{serie}"
    dados = {
        "idTreino": id_treino,
        "dataTreino": data,
        "atleta": atleta,
        "tempo": tempo,
        "serie": str(serie),
        # Bug conhecido do frontend: soma 6 fixo no T2.
        "serieGlobal": serie if tempo == "T1" else serie + 6,
        "v_vento": "12",
        "d_vento": "Norte",
        "clima": "Sol",
        "tipo_alvo": tipo_alvo,
        "tipoAlvo": tipo_alvo,
        "createdAt": "2026-08-20T10:00:00+00:00",
    }
    if total is not None:
        dados.update(
            {
                "distancia": distancia,
                "flechasString": flechas_string,
                "total": total,
                "updatedAt": "2026-08-20T10:05:00+00:00",
            }
        )
    return doc_id, dados


def doc_disparo_legado(
    doc_id_serie: str, flecha: int, x: float, y: float, tipo_alvo: str = "Alvo Unitário"
) -> tuple[str, dict]:
    """Disparo histórico: SEM campo de pontuação, como o app sempre gravou."""
    return doc_id_serie, {
        "idDisparo": f"{doc_id_serie}-F{flecha}",
        "flecha": flecha,
        "x": x,
        "y": y,
        "v_vento": "12",
        "d_vento": "Norte",
        "clima": "Sol",
        "tipo_alvo": tipo_alvo,
        "tipoAlvo": tipo_alvo,
    }


def doc_disparo_novo(
    doc_id_serie: str,
    flecha: int,
    x: float,
    y: float,
    score: str,
    tipo_alvo: str = "Alvo Unitário",
) -> tuple[str, dict]:
    """Disparo no formato novo, com `score` gravado explicitamente."""
    doc_id, dados = doc_disparo_legado(doc_id_serie, flecha, x, y, tipo_alvo)
    dados["score"] = score
    return doc_id, dados


# Coordenadas escolhidas para cair em anéis conhecidos do alvo simples,
# cujos raios são 7,5 (X) / 15 (10) / 30 (9) / 45 (8) / 150 (1).
COORDENADAS_SERIE = [
    (3.0, 2.0, "X"),      # d = 3,61  -> dentro de 7,5  -> X
    (10.0, 5.0, "10"),    # d = 11,18 -> dentro de 15   -> 10
    (20.0, 10.0, "9"),    # d = 22,36 -> dentro de 30   -> 9
    (25.0, 20.0, "9"),    # d = 32,02 -> dentro de 45   -> 8  (divergente de propósito)
    (40.0, 10.0, "8"),    # d = 41,23 -> dentro de 45   -> 8
    (200.0, 0.0, "M"),    # d = 200   -> fora do alvo   -> M
]


@pytest.fixture
def base_legada() -> FonteFalsa:
    """Um treino completo no formato histórico: 2 tempos x 2 séries."""
    series: list[tuple[str, dict]] = []
    disparos: list[tuple[str, dict]] = []

    rotulos = " ".join(r for _, _, r in COORDENADAS_SERIE)
    total = sum({"X": 10, "M": 0}.get(r, int(r) if r.isdigit() else 0) for _, _, r in COORDENADAS_SERIE)

    for tempo in ("T1", "T2"):
        for numero in (1, 2):
            doc_id, dados = doc_serie_legado(
                "TR-2008-1030", tempo, numero, flechas_string=rotulos, total=total
            )
            series.append((doc_id, dados))
            for indice, (x, y, _) in enumerate(COORDENADAS_SERIE, start=1):
                disparos.append(doc_disparo_legado(doc_id, indice, x, y))

    return FonteFalsa(series, disparos)


@pytest.fixture
def base_mista() -> FonteFalsa:
    """Treino histórico + treino novo + série não finalizada + alvo triplo."""
    series: list[tuple[str, dict]] = []
    disparos: list[tuple[str, dict]] = []

    # 1) Treino antigo, sem `score` nos disparos.
    doc_id, dados = doc_serie_legado(
        "TR-0107-0900", "T1", 1, data="2026-07-01", flechas_string="10 9 8", total=27
    )
    series.append((doc_id, dados))
    for indice, (x, y) in enumerate([(5.0, 5.0), (20.0, 0.0), (35.0, 5.0)], start=1):
        disparos.append(doc_disparo_legado(doc_id, indice, x, y))

    # 2) Treino novo, com `score` gravado no disparo.
    doc_id, dados = doc_serie_legado(
        "TR-1508-1400", "T1", 1, data="2026-08-15", flechas_string="X 10 9", total=29
    )
    series.append((doc_id, dados))
    for indice, (x, y, s) in enumerate(
        [(1.0, 1.0, "X"), (8.0, 8.0, "10"), (25.0, 5.0, "9")], start=1
    ):
        disparos.append(doc_disparo_novo(doc_id, indice, x, y, s))

    # 3) Série confirmada no alvo mas nunca finalizada: sem total nem string.
    doc_id, dados = doc_serie_legado(
        "TR-1508-1400", "T1", 2, data="2026-08-15", flechas_string=None, total=None
    )
    series.append((doc_id, dados))
    for indice, (x, y) in enumerate([(4.0, 0.0), (12.0, 3.0)], start=1):
        disparos.append(doc_disparo_legado(doc_id, indice, x, y))

    # 4) Treino no alvo triplo: faces em y = +95, 0, -95.
    doc_id, dados = doc_serie_legado(
        "TR-2008-1600",
        "T1",
        1,
        data="2026-08-20",
        distancia="18m",
        tipo_alvo="Alvo Triplo",
        flechas_string="10 10 9",
        total=29,
    )
    series.append((doc_id, dados))
    for indice, (x, y) in enumerate([(2.0, 96.0), (1.0, 1.0), (0.0, -90.0)], start=1):
        disparos.append(doc_disparo_legado(doc_id, indice, x, y, tipo_alvo="Alvo Triplo"))

    return FonteFalsa(series, disparos)


@pytest.fixture
def servico_legado(base_legada: FonteFalsa) -> ServicoAnalitico:
    return ServicoAnalitico(base_legada, ttl_cache=0)


@pytest.fixture
def servico_misto(base_mista: FonteFalsa) -> ServicoAnalitico:
    return ServicoAnalitico(base_mista, ttl_cache=0)
