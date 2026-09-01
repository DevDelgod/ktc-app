"""Pontuação — a partir dos pontos digitados, nunca da posição.

Extraído de `metrics.py`. A regra de pontuação é a mesma do teclado do
aplicativo desde sempre: X vale 10, M vale 0, o resto vale o próprio
número (ver `app/services/normalize.pontos_do_rotulo`, que resolve o
rótulo de cada disparo antes de chegar aqui).
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import pandas as pd

from app.models.domain import Serie

# Rótulos do teclado numérico, do melhor para o pior. É a ordem em que a
# distribuição de pontuação é apresentada no dashboard.
ROTULOS_ORDENADOS = ["X", "10", "9", "8", "7", "6", "5", "4", "3", "2", "1", "M"]


def _arredondar(valor: float | None, casas: int = 3) -> float | None:
    if valor is None:
        return None
    if isinstance(valor, float) and (math.isnan(valor) or math.isinf(valor)):
        return None
    return round(float(valor), casas)


def metricas_de_pontuacao(quadro: pd.DataFrame, series: Sequence[Serie]) -> dict:
    """Métricas básicas de pontuação.

    Definições:
        total          = soma dos pontos de todas as flechas
        media          = total / número de flechas pontuadas
        mediana        = percentil 50 dos pontos por flecha
        desvio_padrao  = desvio amostral (ddof=1) dos pontos por flecha
        aproveitamento = total / (flechas * 10)   -- 10 é o máximo por flecha
        maximo/minimo  = melhor/pior flecha individual, em pontos

    `aproveitamento` usa 10 como teto porque o X, embora seja o anel
    interno, vale 10 pontos na contagem do aplicativo.
    """
    pontuados = quadro[quadro["pontos"].notna()]
    pontos = pontuados["pontos"].astype(float)
    n = int(len(pontos))

    total_series = sum(s.total for s in series)
    total = int(pontos.sum()) if n else total_series

    return {
        "total": total,
        "media": _arredondar(pontos.mean()) if n else None,
        "mediana": _arredondar(pontos.median()) if n else None,
        "maximo": int(pontos.max()) if n else None,
        "minimo": int(pontos.min()) if n else None,
        "desvio_padrao": _arredondar(pontos.std(ddof=1)) if n > 1 else None,
        "quantidade_flechas": int(len(quadro)),
        "quantidade_flechas_pontuadas": n,
        "quantidade_series": len(series),
        "aproveitamento": _arredondar(total / (n * 10), 4) if n else None,
        "media_por_flecha": _arredondar(total / n) if n else None,
    }


def melhor_pior_serie(por_serie: Sequence[dict]) -> dict:
    """Melhor e pior série pelo total, entre as séries finalizadas.

    Uma série "aberta" (confirmada no alvo, sem pontuação digitada) não
    tem total comparável e fica de fora — comparar um total real com um
    zero de série incompleta distorceria o resultado.
    """
    finalizadas = [s for s in por_serie if s.get("finalizada")]
    if not finalizadas:
        return {"melhor_serie": None, "pior_serie": None}

    melhor = max(finalizadas, key=lambda s: s["total"])
    pior = min(finalizadas, key=lambda s: s["total"])
    return {
        "melhor_serie": {"rotulo": melhor["rotulo"], "total": melhor["total"]},
        "pior_serie": {"rotulo": pior["rotulo"], "total": pior["total"]},
    }


def distribuicao_de_pontuacao(quadro: pd.DataFrame) -> list[dict]:
    """Contagem de flechas por rótulo, na ordem do teclado."""
    if quadro.empty:
        return [{"rotulo": r, "quantidade": 0} for r in ROTULOS_ORDENADOS]
    contagem = quadro["rotulo"].fillna("—").value_counts().to_dict()
    distribuicao = [
        {"rotulo": rotulo, "quantidade": int(contagem.get(rotulo, 0))}
        for rotulo in ROTULOS_ORDENADOS
    ]
    sem_rotulo = int(contagem.get("—", 0))
    if sem_rotulo:
        distribuicao.append({"rotulo": "sem pontuação", "quantidade": sem_rotulo})
    return distribuicao


def maior_sequencia(rotulos: Sequence[str], minimo_pontos: int = 9) -> int:
    """Maior sequência consecutiva de flechas valendo `minimo_pontos` ou mais.

    'Melhor sequência' só tem definição estatística clara como uma
    sequência de acertos de alto valor (9, 10 ou X) sem interrupção —
    é a métrica que arqueiros usam informalmente ("fiz 6 noves
    seguidos"). X e 10 contam como 10; M conta como 0.
    """
    from app.services.normalize import pontos_do_rotulo

    maior = atual = 0
    for rotulo in rotulos:
        pontos = pontos_do_rotulo(rotulo)
        if pontos is not None and pontos >= minimo_pontos:
            atual += 1
            maior = max(maior, atual)
        else:
            atual = 0
    return maior
