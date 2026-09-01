"""Consistência entre séries e qualidade do dado.

Extraído de `metrics.py`. Também concentra a geração de frases sobre
consistência — usadas no relatório de competição (Parte 4) e
disponíveis para o treino também. A regra que rege todo texto gerado
aqui: **nenhuma frase afirma nada que não esteja comprovado pelos
números que a acompanham.** Sem dado suficiente, a frase diz isso
explicitamente em vez de arriscar uma afirmação vazia.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import pandas as pd

from app.analytics.dispersion import com_cm, metricas_de_dispersao
from app.analytics.geometry import geometria


def _arredondar(valor: float | None, casas: int = 3) -> float | None:
    if valor is None:
        return None
    if isinstance(valor, float) and (math.isnan(valor) or math.isinf(valor)):
        return None
    return round(float(valor), casas)


def metricas_por_serie(quadro: pd.DataFrame, series: Sequence) -> list[dict]:
    """Uma linha de métricas por série, na ordem cronológica real.

    Usa a ordem recalculada (`ordem_serie`), não o campo `serieGlobal`
    do banco, que soma 6 fixo no T2 e erra quando a rodada não tem 6
    séries.
    """
    resultado: list[dict] = []
    for serie in series:
        recorte = quadro[quadro["doc_id"] == serie.doc_id]
        pontuados = recorte[recorte["pontos"].notna()]["pontos"].astype(float)
        dispersao = com_cm(metricas_de_dispersao(recorte), geometria(serie.tipo_alvo))

        resultado.append(
            {
                "doc_id": serie.doc_id,
                "ordem": serie.ordem,
                "tempo": serie.tempo,
                "serie": serie.numero,
                "rotulo": f"{serie.tempo}-S{serie.numero}",
                "total": serie.total,
                "media": _arredondar(pontuados.mean()) if len(pontuados) else None,
                "quantidade_flechas": serie.quantidade_flechas,
                "finalizada": serie.finalizada,
                "distancia_media_centro": dispersao.get("distancia_media_centro"),
                "distancia_media_centro_cm": dispersao.get("distancia_media_centro_cm"),
                "dispersao_radial": dispersao.get("dispersao_radial"),
                "dispersao_radial_cm": dispersao.get("dispersao_radial_cm"),
                "raio_medio_grupo": dispersao.get("raio_medio_grupo"),
                "raio_medio_grupo_cm": dispersao.get("raio_medio_grupo_cm"),
                "flechas_string": serie.flechas_string,
            }
        )
    return resultado


def metricas_de_consistencia(por_serie: Sequence[dict]) -> dict:
    """Estabilidade do desempenho entre séries.

    Definições:
        desvio_entre_series = desvio amostral dos totais por série
        amplitude           = maior total - menor total
        coeficiente_variacao = desvio_entre_series / média dos totais
            -- adimensional, permite comparar treinos com número
               diferente de flechas por série.

    O coeficiente de variação só é devolvido quando a média é positiva;
    com média zero ele é indefinido e devolvemos `None` em vez de um
    número sem significado.
    """
    totais = [s["total"] for s in por_serie if s.get("finalizada")]
    if len(totais) < 2:
        return {
            "series_consideradas": len(totais),
            "desvio_entre_series": None,
            "amplitude": None,
            "coeficiente_variacao": None,
            "media_por_serie": _arredondar(float(np.mean(totais))) if totais else None,
        }

    vetor = np.array(totais, dtype=float)
    media = float(np.mean(vetor))
    desvio = float(np.std(vetor, ddof=1))
    return {
        "series_consideradas": len(totais),
        "desvio_entre_series": _arredondar(desvio),
        "amplitude": _arredondar(float(np.max(vetor) - np.min(vetor))),
        "coeficiente_variacao": _arredondar(desvio / media, 4) if media > 0 else None,
        "media_por_serie": _arredondar(media),
    }


def qualidade_dos_dados(quadro: pd.DataFrame) -> dict:
    """Confronta a pontuação digitada com a posição marcada.

    O aplicativo nunca cruzou essas duas informações: o atleta marca o
    ponto de impacto no alvo e digita o valor separadamente, e nada
    verificava se um bate com o outro. Aqui a geometria dos anéis é usada
    para derivar a pontuação a partir de (x, y) e comparar.

    Uma concordância baixa indica marcação imprecisa, digitação errada
    ou zoom mal ajustado — é um indicador de confiabilidade do dado, não
    uma correção. Nada é sobrescrito.
    """
    total = int(len(quadro))
    if total == 0:
        return {
            "flechas": 0,
            "com_pontuacao": 0,
            "sem_pontuacao": 0,
            "fora_do_alvo": 0,
            "concordancia": None,
            "divergencias": 0,
            "origem_score": {},
        }

    comparaveis = quadro[quadro["pontos"].notna()]
    n_comparaveis = int(len(comparaveis))
    concordantes = int(
        (comparaveis["pontos"].astype(int) == comparaveis["pontos_geometricos"].astype(int)).sum()
    ) if n_comparaveis else 0

    return {
        "flechas": total,
        "com_pontuacao": n_comparaveis,
        "sem_pontuacao": total - n_comparaveis,
        "fora_do_alvo": int((~quadro["dentro_do_alvo"].astype(bool)).sum()),
        "concordancia": _arredondar(concordantes / n_comparaveis, 4) if n_comparaveis else None,
        "divergencias": n_comparaveis - concordantes,
        "origem_score": {
            str(k): int(v) for k, v in quadro["origem_score"].value_counts().items()
        },
    }


# Limiares do coeficiente de variação dos totais por série. É uma
# convenção deste aplicativo, não um padrão externo — documentada aqui
# para poder ser revisada, não uma verdade estatística universal.
_CV_MUITO_ESTAVEL = 0.10
_CV_ESTAVEL = 0.20
_CV_VARIAVEL = 0.35

# Uma mudança entre metades da prova só é relatada como tendência se for
# maior que este percentual — abaixo disso, é ruído, não sinal.
_LIMIAR_TENDENCIA = 0.08


def classificar_estabilidade(coeficiente_variacao: float | None) -> str | None:
    if coeficiente_variacao is None:
        return None
    if coeficiente_variacao <= _CV_MUITO_ESTAVEL:
        return "muito estável"
    if coeficiente_variacao <= _CV_ESTAVEL:
        return "estável"
    if coeficiente_variacao <= _CV_VARIAVEL:
        return "variável"
    return "instável"


def frase_de_consistencia(por_serie: Sequence[dict]) -> str:
    """Frase em português sobre a estabilidade do desempenho.

    Nunca afirma tendência sem que a diferença entre a primeira e a
    segunda metade das séries finalizadas ultrapasse `_LIMIAR_TENDENCIA`
    — abaixo disso, a frase declara estabilidade em vez de arriscar uma
    leitura de ruído como sinal.
    """
    finalizadas = [s for s in por_serie if s.get("finalizada")]
    if len(finalizadas) < 2:
        return "Poucas séries finalizadas para avaliar consistência."

    totais = [s["total"] for s in finalizadas]
    media_geral = float(np.mean(totais))
    desvio = float(np.std(totais, ddof=1)) if len(totais) > 1 else 0.0
    cv = desvio / media_geral if media_geral > 0 else None
    estabilidade = classificar_estabilidade(cv)

    if len(finalizadas) < 4:
        return f"Desempenho {estabilidade} ao longo da prova." if estabilidade else "Dados insuficientes para avaliar consistência."

    metade = len(finalizadas) // 2
    primeira = totais[:metade]
    segunda = totais[-metade:]
    media_primeira = float(np.mean(primeira))
    media_segunda = float(np.mean(segunda))
    variacao_relativa = (
        (media_segunda - media_primeira) / media_primeira if media_primeira > 0 else 0.0
    )

    if abs(variacao_relativa) < _LIMIAR_TENDENCIA:
        return f"Desempenho {estabilidade} durante toda a prova." if estabilidade else "Desempenho sem tendência clara durante a prova."

    direcao = "melhora" if variacao_relativa > 0 else "queda"
    return (
        f"Desempenho {estabilidade} no geral, com {direcao} de "
        f"{abs(variacao_relativa) * 100:.0f}% na pontuação média entre a primeira e a "
        f"segunda metade da prova."
    )


def frase_de_dispersao(por_serie: Sequence[dict]) -> str | None:
    """Frase sobre a evolução do agrupamento — só quando há dado suficiente.

    Usa `dispersao_radial` por série, na mesma lógica de duas metades da
    `frase_de_consistencia`. Devolve `None` quando a métrica não estava
    disponível nas séries (série sem coordenada, por exemplo).
    """
    disponiveis = [s for s in por_serie if s.get("finalizada") and s.get("dispersao_radial") is not None]
    if len(disponiveis) < 4:
        return None

    valores = [s["dispersao_radial"] for s in disponiveis]
    metade = len(valores) // 2
    primeira = float(np.mean(valores[:metade]))
    segunda = float(np.mean(valores[-metade:]))
    if primeira <= 0:
        return None

    variacao = (segunda - primeira) / primeira
    if abs(variacao) < _LIMIAR_TENDENCIA:
        return "O agrupamento das flechas se manteve estável ao longo da prova."
    if variacao < 0:
        return (
            f"O agrupamento ficou {abs(variacao) * 100:.0f}% mais compacto na segunda "
            f"metade da prova em relação à primeira."
        )
    return (
        f"O agrupamento ficou {variacao * 100:.0f}% mais disperso na segunda metade da "
        f"prova em relação à primeira."
    )
