"""Precisão, agrupamento e tendência — a partir de (x, y).

Extraído de `metrics.py` para isolar tudo que depende de coordenada,
por dois motivos: (1) é a parte mais sensível a erro de calibração, e
(2) é reaproveitada tanto por treinos quanto pelo modo Competição.

Convenção de coordenadas (não mudou — ver `geometry.py`): origem no
centro do alvo, Y positivo para cima, unidade = 1/300 da largura do
alvo. Trabalha sempre sobre (dx, dy), o deslocamento em relação ao
centro da FACE atingida — nunca sobre (x, y) absoluto, porque no alvo
triplo as três faces têm centros físicos diferentes.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import pandas as pd

from app.analytics.geometry import TargetGeometry

_ROSA_DOS_VENTOS = [
    (0, "Direita"),
    (45, "Sup. direita"),
    (90, "Cima"),
    (135, "Sup. esquerda"),
    (180, "Esquerda"),
    (225, "Inf. esquerda"),
    (270, "Baixo"),
    (315, "Inf. direita"),
]

# Toda métrica aqui é uma distância ou coordenada linear no sistema do
# alvo — a mesma constante de conversão (cm por unidade) vale para
# todas, então todas ganham uma versão `_cm`. Ângulos (`vies_angulo`) e
# rótulos ficam de fora por não serem lineares.
_CHAVES_LINEARES = (
    "centro_grupo_x",
    "centro_grupo_y",
    "desvio_x",
    "desvio_y",
    "dispersao_radial",
    "distancia_media_centro",
    "distancia_mediana_centro",
    "distancia_maxima_centro",
    "distancia_minima_centro",
    "raio_medio_grupo",
    "raio_95_grupo",
    "extreme_spread",
    "vies_modulo",
)


def _arredondar(valor: float | None, casas: int = 3) -> float | None:
    if valor is None:
        return None
    if isinstance(valor, float) and (math.isnan(valor) or math.isinf(valor)):
        return None
    return round(float(valor), casas)


def _rotulo_cardinal(angulo_graus: float) -> str:
    normalizado = angulo_graus % 360
    melhor = min(
        _ROSA_DOS_VENTOS,
        key=lambda item: min(
            abs(normalizado - item[0]), 360 - abs(normalizado - item[0])
        ),
    )
    return melhor[1]


def _maior_distancia(dx: np.ndarray, dy: np.ndarray) -> float:
    """Extreme spread: maior distância entre dois disparos quaisquer."""
    difs_x = dx[:, None] - dx[None, :]
    difs_y = dy[:, None] - dy[None, :]
    return float(np.max(np.hypot(difs_x, difs_y)))


def metricas_de_dispersao(quadro: pd.DataFrame) -> dict:
    """Precisão, agrupamento e tendência a partir das coordenadas.

    Definições:

        centro_grupo   = (média(dx), média(dy))
        desvio_x       = desvio amostral de dx        (ddof=1)
        desvio_y       = desvio amostral de dy        (ddof=1)
        dispersao_radial = sqrt(var(dx) + var(dy))
            -- desvio radial combinado; é a raiz do traço da matriz de
               covariância, ou seja, o espalhamento total do grupo em
               qualquer direção.
        distancia_centro_i = sqrt(dx_i^2 + dy_i^2)
            -- distância de cada flecha ao centro do ALVO (precisão).
        raio_grupo_i = distância da flecha ao CENTRO DO GRUPO
            -- mede agrupamento, independentemente de o grupo estar
               deslocado. É a separação entre precisão e consistência.
        r95            = percentil 95 dos raios do grupo
        extreme_spread = maior distância entre duas flechas quaisquer
            -- métrica clássica de agrupamento em tiro.
        vies           = módulo e direção do vetor centro_grupo
            -- responde "o grupo está deslocado para algum lado?".

    Todas as distâncias saem em unidades do alvo. Use `com_cm()` para
    anexar a conversão física — feita à parte porque o fator depende do
    tipo de alvo, que esta função não recebe.
    """
    if quadro.empty:
        return {"quantidade": 0}

    dx = quadro["dx"].astype(float).to_numpy()
    dy = quadro["dy"].astype(float).to_numpy()
    n = len(dx)

    centro_x = float(np.mean(dx))
    centro_y = float(np.mean(dy))

    dist_alvo = np.hypot(dx, dy)
    raios_grupo = np.hypot(dx - centro_x, dy - centro_y)

    desvio_x = float(np.std(dx, ddof=1)) if n > 1 else 0.0
    desvio_y = float(np.std(dy, ddof=1)) if n > 1 else 0.0
    dispersao_radial = math.sqrt(desvio_x**2 + desvio_y**2)

    vies_modulo = math.hypot(centro_x, centro_y)
    vies_angulo = math.degrees(math.atan2(centro_y, centro_x)) if vies_modulo > 1e-9 else 0.0

    return {
        "quantidade": n,
        "centro_grupo_x": _arredondar(centro_x),
        "centro_grupo_y": _arredondar(centro_y),
        "desvio_x": _arredondar(desvio_x),
        "desvio_y": _arredondar(desvio_y),
        "dispersao_radial": _arredondar(dispersao_radial),
        "distancia_media_centro": _arredondar(float(np.mean(dist_alvo))),
        "distancia_mediana_centro": _arredondar(float(np.median(dist_alvo))),
        "distancia_maxima_centro": _arredondar(float(np.max(dist_alvo))),
        "distancia_minima_centro": _arredondar(float(np.min(dist_alvo))),
        "raio_medio_grupo": _arredondar(float(np.mean(raios_grupo))),
        "raio_95_grupo": _arredondar(float(np.percentile(raios_grupo, 95))) if n > 1 else None,
        "extreme_spread": _arredondar(_maior_distancia(dx, dy)) if n > 1 else None,
        "vies_modulo": _arredondar(vies_modulo),
        "vies_angulo": _arredondar(vies_angulo, 1),
        "vies_direcao": _rotulo_cardinal(vies_angulo) if vies_modulo > 1e-9 else "Centrado",
    }


def com_cm(dispersao: dict, geo: TargetGeometry) -> dict:
    """Anexa a versão em centímetros de cada métrica linear.

    A conversão usa a mesma calibração de `geometry.unidades_para_cm`:
    o raio externo do alvo (em unidades) corresponde ao raio físico real
    da face (`geo.diametro_cm / 2`). Cobre TODAS as métricas lineares —
    antes só as que começavam com `distancia_`/`raio_` eram convertidas,
    deixando `dispersao_radial`, `vies_modulo` etc. presos na unidade
    interna, que não significa nada para o atleta.
    """
    convertidas = {
        f"{chave}_cm": _arredondar(geo.unidades_para_cm(dispersao[chave]))
        for chave in _CHAVES_LINEARES
        if chave in dispersao and isinstance(dispersao[chave], (int, float))
    }
    return {**dispersao, **convertidas}


def agrupamento_por_face(quadro: pd.DataFrame, geo: TargetGeometry) -> list[dict]:
    """Centro do grupo calculado separadamente por face.

    Só se aplica a alvos multiface (o Alvo Triplo). Um único "centro do
    grupo" não representa nada visualmente quando o alvo tem faces em
    posições físicas diferentes — a média das posições absolutas
    misturaria flechas de faces distintas num ponto que não corresponde
    a nenhuma face real. Aqui agrupamos por face (a mesma que `dx`/`dy`
    já usam) e calculamos um centro de grupo local por face, pronto para
    ser desenhado sobre a face correta.

    Correção do bug de calibração: antes o frontend desenhava o losango
    do centro do grupo sempre na posição fictícia (0, 0), que não é
    nenhuma das três faces reais (y = +95, 0, -95) — confirmado com
    teste de pixel: um grupo de flechas na face de cima (y≈95) fazia o
    losango aparecer 95 unidades abaixo de onde as flechas realmente
    estavam.
    """
    if not geo.multiface or quadro.empty:
        return []

    resultado = []
    for (fx, fy), grupo in quadro.groupby(["face_x", "face_y"]):
        n = len(grupo)
        dx = grupo["dx"].astype(float).to_numpy()
        dy = grupo["dy"].astype(float).to_numpy()
        centro_x = float(np.mean(dx))
        centro_y = float(np.mean(dy))
        raios = np.hypot(dx - centro_x, dy - centro_y)

        item = {
            "face_x": float(fx),
            "face_y": float(fy),
            "quantidade": n,
            "centro_x": _arredondar(centro_x),
            "centro_y": _arredondar(centro_y),
            "raio_medio": _arredondar(float(np.mean(raios))) if n > 1 else None,
            "raio_95": _arredondar(float(np.percentile(raios, 95))) if n > 1 else None,
        }
        item["centro_x_cm"] = _arredondar(geo.unidades_para_cm(item["centro_x"]))
        item["centro_y_cm"] = _arredondar(geo.unidades_para_cm(item["centro_y"]))
        item["raio_medio_cm"] = (
            _arredondar(geo.unidades_para_cm(item["raio_medio"]))
            if item["raio_medio"] is not None
            else None
        )
        resultado.append(item)

    resultado.sort(key=lambda item: -item["quantidade"])
    return resultado


def distancia_do_centro_serie(quadro_serie: pd.DataFrame) -> dict:
    """Resumo curto de precisão para uma única série — usado no relatório."""
    if quadro_serie.empty:
        return {"distancia_media": None, "distancia_maxima": None}
    dist = np.hypot(
        quadro_serie["dx"].astype(float).to_numpy(),
        quadro_serie["dy"].astype(float).to_numpy(),
    )
    return {
        "distancia_media": _arredondar(float(np.mean(dist))),
        "distancia_maxima": _arredondar(float(np.max(dist))),
    }
