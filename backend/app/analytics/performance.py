"""Relatório final de performance de uma competição.

Monta o pacote completo do relatório: resumo, destaques, pontos de
atenção, consistência narrada e a comparação entre a primeira e a
segunda metade da prova. Tudo aqui é derivado dos números já calculados
por `competition.py` — nenhuma métrica nova é inventada, e nenhuma
afirmação (melhora, piora, "destaque") aparece sem os dados que a
sustentam. Onde não há dado suficiente, o campo correspondente vem
`None` em vez de forçar um valor.
"""

from __future__ import annotations

import pandas as pd

from app.analytics import scoring
from app.analytics.competition import (
    analisar_competicao,
    descrever_competicao,
    quadro_de_disparos_competicao,
)
from app.analytics.consistency import frase_de_consistencia, frase_de_dispersao
from app.analytics.dispersion import com_cm, metricas_de_dispersao
from app.analytics.geometry import geometria
from app.models.competition import Competicao

# Uma métrica de agrupamento/dispersão só é usada num destaque quando a
# série tem pelo menos esta quantidade de flechas — com 1 ou 2 pontos, a
# "dispersão" seria zero ou quase por falta de amostra, não porque o
# agrupamento foi realmente bom.
_MINIMO_PARA_DESTAQUE_DE_GRUPO = 3


def _melhor_flecha(quadro: pd.DataFrame) -> dict | None:
    pontuadas = quadro[quadro["pontos"].notna()]
    if pontuadas.empty:
        return None
    linha = pontuadas.loc[pontuadas["pontos"].astype(float).idxmax()]
    return {
        "pontos": int(linha["pontos"]),
        "rotulo": linha["rotulo"],
        "prova": linha["prova"],
        "serie": int(linha["serie"]),
        "flecha": int(linha["flecha"]),
    }


def _pior_flecha(quadro: pd.DataFrame) -> dict | None:
    pontuadas = quadro[quadro["pontos"].notna()]
    if pontuadas.empty:
        return None
    linha = pontuadas.loc[pontuadas["pontos"].astype(float).idxmin()]
    return {
        "pontos": int(linha["pontos"]),
        "rotulo": linha["rotulo"],
        "prova": linha["prova"],
        "serie": int(linha["serie"]),
        "flecha": int(linha["flecha"]),
    }


def _melhor_pior_agrupamento(por_serie: list[dict]) -> tuple[dict | None, dict | None]:
    """Série com menor e maior dispersão radial, entre as com amostra
    suficiente (ver `_MINIMO_PARA_DESTAQUE_DE_GRUPO`)."""
    candidatas = [
        s for s in por_serie
        if s.get("dispersao_radial_cm") is not None and s.get("quantidade_flechas", 0) >= _MINIMO_PARA_DESTAQUE_DE_GRUPO
    ]
    if not candidatas:
        return None, None
    melhor = min(candidatas, key=lambda s: s["dispersao_radial_cm"])
    pior = max(candidatas, key=lambda s: s["dispersao_radial_cm"])
    return (
        {"rotulo": melhor["rotulo"], "dispersao_cm": melhor["dispersao_radial_cm"]},
        {"rotulo": pior["rotulo"], "dispersao_cm": pior["dispersao_radial_cm"]},
    )


def _maior_precisao(por_serie: list[dict]) -> dict | None:
    """Série com menor distância média do centro — precisão não exige
    amostra mínima como agrupamento: mesmo uma flecha só já mede
    precisão real (a distância dela ao centro é um fato, não uma
    estimativa de variabilidade)."""
    candidatas = [s for s in por_serie if s.get("distancia_media_centro_cm") is not None]
    if not candidatas:
        return None
    melhor = min(candidatas, key=lambda s: s["distancia_media_centro_cm"])
    return {"rotulo": melhor["rotulo"], "distancia_cm": melhor["distancia_media_centro_cm"]}


def _maior_distancia_do_centro(por_serie: list[dict]) -> dict | None:
    candidatas = [s for s in por_serie if s.get("distancia_media_centro_cm") is not None]
    if not candidatas:
        return None
    pior = max(candidatas, key=lambda s: s["distancia_media_centro_cm"])
    return {"rotulo": pior["rotulo"], "distancia_cm": pior["distancia_media_centro_cm"]}


def destaques(quadro: pd.DataFrame, por_serie: list[dict], pontuacao: dict) -> dict:
    """Seção "Pontos altos" do relatório.

    Cada campo é `None` quando não há dado suficiente para sustentá-lo —
    nunca um valor forçado.
    """
    melhor_agrupamento, _ = _melhor_pior_agrupamento(por_serie)
    rotulos_em_ordem = quadro.sort_values(["ordem_serie", "flecha"])["rotulo"].dropna().tolist()

    return {
        "melhor_pontuacao": _melhor_flecha(quadro),
        "melhor_serie": pontuacao.get("melhor_serie"),
        "melhor_sequencia": scoring.maior_sequencia(rotulos_em_ordem) if rotulos_em_ordem else None,
        "melhor_agrupamento": melhor_agrupamento,
        "maior_precisao": _maior_precisao(por_serie),
    }


def pontos_de_atencao(quadro: pd.DataFrame, por_serie: list[dict], pontuacao: dict) -> dict:
    """Seção "Pontos de atenção" do relatório.

    São fatos (o pior número observado), não um veredito de "problema" —
    a distinção entre evento isolado e tendência real fica a cargo das
    frases de `consistency.py` (`frase_de_consistencia`,
    `frase_de_dispersao`), que só apontam tendência quando a diferença
    entre a primeira e a segunda metade da prova é grande o bastante
    para não ser ruído.
    """
    _, pior_agrupamento = _melhor_pior_agrupamento(por_serie)

    return {
        "pior_pontuacao": _pior_flecha(quadro),
        "pior_serie": pontuacao.get("pior_serie"),
        "maior_dispersao": pior_agrupamento,
        "maior_distancia_centro": _maior_distancia_do_centro(por_serie),
    }


def comparacao_inicio_fim(competicao: Competicao, quadro: pd.DataFrame) -> dict | None:
    """Agrupamento da primeira metade da prova contra a segunda metade.

    Só produzida quando há pelo menos 4 séries finalizadas — com menos
    que isso, "primeira metade" e "segunda metade" seriam 1 série cada,
    o que não é comparação, é ruído.
    """
    finalizadas = sorted(
        [s for s in competicao.series if s.finalizada], key=lambda s: s.ordem
    )
    if len(finalizadas) < 4:
        return None

    metade = len(finalizadas) // 2
    ids_inicio = {s.doc_id for s in finalizadas[:metade]}
    ids_fim = {s.doc_id for s in finalizadas[-metade:]}

    geo = geometria(competicao.tipo_alvo)
    disp_inicio = com_cm(metricas_de_dispersao(quadro[quadro["doc_id"].isin(ids_inicio)]), geo)
    disp_fim = com_cm(metricas_de_dispersao(quadro[quadro["doc_id"].isin(ids_fim)]), geo)

    if disp_inicio.get("quantidade", 0) < 2 or disp_fim.get("quantidade", 0) < 2:
        return None

    aproximou = None
    if disp_inicio.get("distancia_media_centro_cm") is not None and disp_fim.get("distancia_media_centro_cm") is not None:
        aproximou = disp_fim["distancia_media_centro_cm"] < disp_inicio["distancia_media_centro_cm"]

    mais_compacto = None
    if disp_inicio.get("dispersao_radial_cm") is not None and disp_fim.get("dispersao_radial_cm") is not None:
        mais_compacto = disp_fim["dispersao_radial_cm"] < disp_inicio["dispersao_radial_cm"]

    return {
        "series_no_inicio": len(ids_inicio),
        "series_no_fim": len(ids_fim),
        "inicio": disp_inicio,
        "fim": disp_fim,
        "aproximou_do_centro": aproximou,
        "ficou_mais_compacto": mais_compacto,
    }


def analise_final(por_serie: list[dict], comparacao: dict | None) -> str:
    """Parágrafo final do relatório — concatena as frases já geradas por
    `consistency.py`, mais uma linha sobre início×fim quando disponível.
    Nenhum texto novo é inventado aqui; isto só combina o que já foi
    calculado."""
    partes = [frase_de_consistencia(por_serie)]

    frase_disp = frase_de_dispersao(por_serie)
    if frase_disp:
        partes.append(frase_disp)

    if comparacao:
        if comparacao["aproximou_do_centro"] is True:
            partes.append("O grupo terminou a prova mais próximo do centro do que começou.")
        elif comparacao["aproximou_do_centro"] is False:
            partes.append("O grupo terminou a prova mais afastado do centro do que começou.")

    return " ".join(partes)


def montar_relatorio(competicao: Competicao) -> dict:
    """Relatório final completo — chamado quando a competição é
    consultada com status concluída (ou sob demanda antes disso, como
    prévia)."""
    pacote = analisar_competicao(competicao)
    quadro = quadro_de_disparos_competicao(competicao.series)
    por_serie = pacote["series"]

    comparacao = comparacao_inicio_fim(competicao, quadro)

    return {
        "resumo": descrever_competicao(competicao),
        "pontuacao": pacote["pontuacao"],
        "dispersao": pacote["dispersao"],
        "agrupamento_por_face": pacote["agrupamento_por_face"],
        "consistencia": pacote["consistencia"],
        "distribuicao": pacote["distribuicao"],
        "qualidade": pacote["qualidade"],
        "series": por_serie,
        "destaques": destaques(quadro, por_serie, pacote["pontuacao"]),
        "pontos_de_atencao": pontos_de_atencao(quadro, por_serie, pacote["pontuacao"]),
        "comparacao_inicio_fim": comparacao,
        "analise_final": analise_final(por_serie, comparacao),
    }
