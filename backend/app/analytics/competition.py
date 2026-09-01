"""Analytics de uma competição inteira.

Reaproveita `scoring.py`, `dispersion.py` e `consistency.py` sem
duplicar nenhuma fórmula: `SerieCompeticao` tem os mesmos nomes de
atributo que `Serie` (ver `models/competition.py`), então as mesmas
funções que processam um treino processam uma competição — só a tabela
de disparos (`quadro`) precisa de um construtor próprio, porque
`SerieCompeticao` não carrega os campos de treino (clima, vento) que a
função de treino grava por coincidência de esquema, não por
necessidade: nenhuma métrica estatística depende deles.
"""

from __future__ import annotations

import pandas as pd

from app.analytics import scoring
from app.analytics.consistency import (
    metricas_de_consistencia,
    metricas_por_serie,
    qualidade_dos_dados,
)
from app.analytics.dispersion import agrupamento_por_face, com_cm, metricas_de_dispersao
from app.analytics.geometry import centro_mais_proximo, geometria
from app.models.competition import Competicao, SerieCompeticao


def quadro_de_disparos_competicao(series: list[SerieCompeticao]) -> pd.DataFrame:
    """Mesma forma de tabela que `metrics.quadro_de_disparos` produz para
    um treino — as funções de análise consomem colunas, não sabem (nem
    precisam saber) se a origem foi um treino ou uma competição."""
    linhas: list[dict] = []
    for serie in series:
        geo = geometria(serie.tipo_alvo)
        for disparo in serie.disparos:
            cx, cy = centro_mais_proximo(disparo.x, disparo.y, geo.centros)
            linhas.append(
                {
                    "doc_id": serie.doc_id,
                    "competicao_id": serie.competicao_id,
                    "prova": serie.prova,
                    "tempo": serie.prova,
                    "serie": serie.numero,
                    "ordem_serie": serie.ordem,
                    "tipo_alvo": serie.tipo_alvo,
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
                "doc_id", "competicao_id", "prova", "tempo", "serie", "ordem_serie",
                "tipo_alvo", "flecha", "x", "y", "dx", "dy", "face_x", "face_y",
                "rotulo", "pontos", "origem_score", "distancia_centro",
                "pontos_geometricos", "rotulo_geometrico", "dentro_do_alvo",
            ]
        )
    return pd.DataFrame(linhas)


def analisar_competicao(competicao: Competicao) -> dict:
    """Pacote analítico completo — mesmo formato de `metrics.analisar_treino`."""
    quadro = quadro_de_disparos_competicao(competicao.series)
    por_serie = metricas_por_serie(quadro, competicao.series)
    geo = geometria(competicao.tipo_alvo)

    pontuacao = scoring.metricas_de_pontuacao(quadro, competicao.series)
    pontuacao.update(scoring.melhor_pior_serie(por_serie))

    dispersao = com_cm(metricas_de_dispersao(quadro), geo)

    return {
        "competicao": descrever_competicao(competicao),
        "pontuacao": pontuacao,
        "dispersao": dispersao,
        "agrupamento_por_face": agrupamento_por_face(quadro, geo),
        "consistencia": metricas_de_consistencia(por_serie),
        "distribuicao": scoring.distribuicao_de_pontuacao(quadro),
        "qualidade": qualidade_dos_dados(quadro),
        "series": por_serie,
    }


def descrever_competicao(competicao: Competicao) -> dict:
    return {
        "id": competicao.id,
        "nome": competicao.nome,
        "atleta": competicao.atleta,
        "data": competicao.data.isoformat() if competicao.data else None,
        "local": competicao.local,
        "categoria": competicao.categoria,
        "modalidade": competicao.modalidade,
        "tipo_alvo": competicao.tipo_alvo,
        "distancia": competicao.distancia,
        "status": competicao.status,
        "provas": competicao.provas,
        "quantidade_series": competicao.quantidade_series,
        "quantidade_flechas": competicao.quantidade_flechas,
        "total": competicao.total,
        "criado_em": competicao.criado_em,
        "finalizado_em": competicao.finalizado_em,
    }


def progresso(competicao: Competicao) -> dict:
    """Estado corrente para a tela de acompanhamento ao vivo.

    A "série atual" e a "flecha atual" são a última série não finalizada
    (ou a última de todas, se todas estiverem finalizadas) — é o ponto
    onde o atleta parou.
    """
    series_ordenadas = sorted(competicao.series, key=lambda s: s.ordem)
    atual = next((s for s in series_ordenadas if not s.finalizada), None)
    if atual is None and series_ordenadas:
        atual = series_ordenadas[-1]

    return {
        "competicao": descrever_competicao(competicao),
        "serie_atual": (
            {
                "doc_id": atual.doc_id,
                "prova": atual.prova,
                "numero": atual.numero,
                "ordem": atual.ordem,
                "quantidade_flechas": atual.quantidade_flechas,
                "finalizada": atual.finalizada,
                "total": atual.total if atual.finalizada else None,
            }
            if atual
            else None
        ),
        "score_total": competicao.total,
        "quantidade_series": competicao.quantidade_series,
        "quantidade_flechas": competicao.quantidade_flechas,
    }
