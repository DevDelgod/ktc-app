"""Orquestração da análise de um treino.

Este módulo é a fachada pública da camada analítica: monta o "quadro"
(disparos achatados numa tabela), e combina pontuação (`scoring.py`),
precisão/agrupamento (`dispersion.py`) e consistência
(`consistency.py`) no pacote que a API devolve para um treino.

A estatística em si não mora mais aqui — foi dividida em módulos
focados por responsabilidade, para não voltar a acumular tudo num
arquivo só:

    scoring.py       pontuação: total, média, melhor/pior flecha e série
    dispersion.py     precisão, agrupamento, tendência, conversão a cm
    consistency.py    consistência entre séries, qualidade do dado, texto

As funções são reexportadas aqui para quem já importava de
`app.analytics.metrics` (testes e módulos existentes) continuar
funcionando sem alteração.

Convenção de coordenadas
------------------------
Os disparos chegam no sistema do aplicativo: origem no centro do canvas,
Y positivo para cima, unidade = 1/300 da largura do alvo.

Para alvos de face única o centro do alvo é (0, 0). Para o alvo triplo
**não é**: há três faces, em (0, +95), (0, 0) e (0, -95). Por isso toda
a análise de dispersão trabalha com o *deslocamento* de cada disparo em
relação ao centro da sua própria face:

    dx = x - cx        dy = y - cy

Esse deslocamento é o espaço comum em que faces diferentes podem ser
comparadas e somadas. Usar (x, y) absoluto no alvo triplo produziria uma
"dispersão" que na verdade mede a distância entre as faces.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from app.analytics.consistency import (  # noqa: F401 — reexport
    frase_de_consistencia,
    frase_de_dispersao,
    metricas_de_consistencia,
    metricas_por_serie,
    qualidade_dos_dados,
)
from app.analytics.dispersion import (  # noqa: F401 — reexport
    agrupamento_por_face,
    com_cm,
    metricas_de_dispersao,
)
from app.analytics.geometry import centro_mais_proximo, geometria
from app.analytics.scoring import (  # noqa: F401 — reexport
    ROTULOS_ORDENADOS,
    distribuicao_de_pontuacao,
    melhor_pior_serie,
    metricas_de_pontuacao,
)
from app.models.domain import Disparo, Serie, Treino


def quadro_de_disparos(series) -> pd.DataFrame:
    """Achata séries e disparos numa tabela única.

    É o equivalente estrutural do que o `exportar.py` fazia para o CSV —
    a lógica de achatamento foi preservada e estendida para descer até o
    nível do disparo, que o script antigo nunca alcançava.

    Cada linha é um disparo, com o deslocamento em relação ao centro da
    sua face já calculado. Reaproveitada pelo modo Competição
    (`competition.py`), que monta o mesmo formato de tabela a partir dos
    disparos de uma competição em vez de um treino.
    """
    linhas: list[dict] = []
    for serie in series:
        geo = geometria(serie.tipo_alvo)
        for disparo in serie.disparos:
            cx, cy = centro_mais_proximo(disparo.x, disparo.y, geo.centros)
            linhas.append(
                {
                    "id_treino": serie.id_treino,
                    "doc_id": serie.doc_id,
                    "atleta": serie.atleta,
                    "data_treino": serie.data_treino,
                    "tempo": serie.tempo,
                    "serie": serie.numero,
                    "ordem_serie": serie.ordem,
                    "distancia": serie.distancia,
                    "tipo_alvo": serie.tipo_alvo,
                    "familia_alvo": serie.familia_alvo,
                    "clima": serie.clima,
                    "v_vento": serie.v_vento,
                    "d_vento": serie.d_vento,
                    "flecha": disparo.numero,
                    "x": disparo.x,
                    "y": disparo.y,
                    "dx": disparo.x - cx,
                    "dy": disparo.y - cy,
                    "face_x": cx,
                    "face_y": cy,
                    "rotulo": disparo.rotulo,
                    "pontos": disparo.pontos,
                    "origem_score": disparo.origem_score,
                    "distancia_centro": disparo.distancia_centro,
                    "pontos_geometricos": disparo.pontos_geometricos,
                    "rotulo_geometrico": disparo.rotulo_geometrico,
                    "dentro_do_alvo": disparo.dentro_do_alvo,
                }
            )

    if not linhas:
        return pd.DataFrame(
            columns=[
                "id_treino", "doc_id", "atleta", "data_treino", "tempo", "serie",
                "ordem_serie", "distancia", "tipo_alvo", "familia_alvo", "clima",
                "v_vento", "d_vento", "flecha", "x", "y", "dx", "dy", "face_x",
                "face_y", "rotulo", "pontos", "origem_score", "distancia_centro",
                "pontos_geometricos", "rotulo_geometrico", "dentro_do_alvo",
            ]
        )
    return pd.DataFrame(linhas)


def analisar_treino(treino: Treino) -> dict:
    """Pacote analítico completo de um treino."""
    quadro = quadro_de_disparos(treino.series)
    por_serie = metricas_por_serie(quadro, treino.series)
    geo = geometria(treino.tipo_alvo_predominante)

    pontuacao = metricas_de_pontuacao(quadro, treino.series)
    pontuacao.update(melhor_pior_serie(por_serie))

    dispersao = com_cm(metricas_de_dispersao(quadro), geo)

    return {
        "treino": descrever_treino(treino),
        "pontuacao": pontuacao,
        "dispersao": dispersao,
        "agrupamento_por_face": agrupamento_por_face(quadro, geo),
        "consistencia": metricas_de_consistencia(por_serie),
        "distribuicao": distribuicao_de_pontuacao(quadro),
        "qualidade": qualidade_dos_dados(quadro),
        "series": por_serie,
        "analise": {
            "consistencia": frase_de_consistencia(por_serie),
            "dispersao": frase_de_dispersao(por_serie),
        },
    }


def descrever_treino(treino: Treino) -> dict:
    """Cabeçalho de identificação do treino."""
    return {
        "id_treino": treino.id_treino,
        "atleta": treino.atleta,
        "data_treino": treino.data_treino.isoformat() if treino.data_treino else None,
        "criado_em": treino.criado_em,
        "tipo_alvo": treino.tipo_alvo_predominante,
        "tipos_de_alvo": treino.tipos_de_alvo,
        "distancias": treino.distancias,
        "quantidade_series": treino.quantidade_series,
        "quantidade_flechas": treino.quantidade_flechas,
        "total": treino.total,
        "tempos": sorted({s.tempo for s in treino.series}),
    }


def serializar_disparos(treino: Treino) -> list[dict]:
    """Disparos prontos para o gráfico de dispersão do dashboard.

    Inclui `distancia_centro_cm` — a mesma distância convertida para
    centímetros pela geometria do tipo de alvo daquele disparo
    especificamente (uma série pode, em tese, ter usado um alvo
    diferente da predominante do treino).
    """
    quadro = quadro_de_disparos(treino.series)
    if quadro.empty:
        return []
    quadro = quadro.copy()
    quadro["distancia_centro_cm"] = quadro.apply(
        lambda linha: round(
            geometria(linha["tipo_alvo"]).unidades_para_cm(linha["distancia_centro"]), 3
        ),
        axis=1,
    )
    colunas = [
        "id_treino", "doc_id", "tempo", "serie", "ordem_serie", "flecha",
        "x", "y", "dx", "dy", "face_x", "face_y", "rotulo", "pontos",
        "distancia_centro", "distancia_centro_cm", "pontos_geometricos",
        "rotulo_geometrico", "dentro_do_alvo", "tipo_alvo", "origem_score",
    ]
    return quadro[colunas].replace({np.nan: None}).to_dict(orient="records")


def resumo_para_historico(treino: Treino) -> dict:
    """Uma linha por treino, para as séries temporais de evolução."""
    quadro = quadro_de_disparos(treino.series)
    pontuacao = metricas_de_pontuacao(quadro, treino.series)
    geo = geometria(treino.tipo_alvo_predominante)
    dispersao = com_cm(metricas_de_dispersao(quadro), geo)
    consistencia = metricas_de_consistencia(metricas_por_serie(quadro, treino.series))

    return {
        "id_treino": treino.id_treino,
        "atleta": treino.atleta,
        "data_treino": treino.data_treino.isoformat() if treino.data_treino else None,
        "tipo_alvo": treino.tipo_alvo_predominante,
        "distancias": treino.distancias,
        "total": pontuacao["total"],
        "media": pontuacao["media"],
        "aproveitamento": pontuacao["aproveitamento"],
        "quantidade_flechas": pontuacao["quantidade_flechas"],
        "quantidade_series": pontuacao["quantidade_series"],
        "distancia_media_centro": dispersao.get("distancia_media_centro"),
        "distancia_media_centro_cm": dispersao.get("distancia_media_centro_cm"),
        "dispersao_radial": dispersao.get("dispersao_radial"),
        "dispersao_radial_cm": dispersao.get("dispersao_radial_cm"),
        "raio_medio_grupo": dispersao.get("raio_medio_grupo"),
        "raio_medio_grupo_cm": dispersao.get("raio_medio_grupo_cm"),
        "vies_modulo": dispersao.get("vies_modulo"),
        "vies_modulo_cm": dispersao.get("vies_modulo_cm"),
        "vies_direcao": dispersao.get("vies_direcao"),
        "desvio_entre_series": consistencia.get("desvio_entre_series"),
        "coeficiente_variacao": consistencia.get("coeficiente_variacao"),
    }


def comparar_treinos(treinos: Iterable[Treino]) -> dict:
    """Comparação lado a lado, com as mesmas métricas para cada treino."""
    linhas = [resumo_para_historico(t) for t in treinos]
    return {
        "treinos": linhas,
        "metricas": [
            {"chave": "total", "rotulo": "Score total", "melhor": "maior"},
            {"chave": "media", "rotulo": "Média por flecha", "melhor": "maior"},
            {"chave": "aproveitamento", "rotulo": "Aproveitamento", "melhor": "maior"},
            {"chave": "distancia_media_centro_cm", "rotulo": "Distância média do centro (cm)", "melhor": "menor"},
            {"chave": "dispersao_radial_cm", "rotulo": "Dispersão radial (cm)", "melhor": "menor"},
            {"chave": "raio_medio_grupo_cm", "rotulo": "Raio médio do grupo (cm)", "melhor": "menor"},
            {"chave": "vies_modulo_cm", "rotulo": "Deslocamento do grupo (cm)", "melhor": "menor"},
            {"chave": "desvio_entre_series", "rotulo": "Desvio entre séries", "melhor": "menor"},
        ],
    }
