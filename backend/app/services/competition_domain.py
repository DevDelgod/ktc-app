"""Monta objetos de domínio (`Competicao`/`SerieCompeticao`) a partir dos
documentos crus do Firestore.

Reaproveita `_montar_disparo` de `repository.py` — o disparo de uma
competição tem exatamente a mesma forma que o de um treino (flecha, x,
y, score), então a mesma função que resolve pontuação (por campo
explícito ou por posição na `flechasString`) serve para os dois.
"""

from __future__ import annotations

import logging
from datetime import date

from app.models.competition import Competicao, SerieCompeticao
from app.services import normalize
from app.services.competition_repository import FonteDeCompeticoes, montar_competicao_dict
from app.services.repository import _montar_disparo  # reaproveitado de treinos

logger = logging.getLogger(__name__)


def _montar_serie(doc_id: str, dados: dict, competicao_id: str, atleta_padrao: str) -> SerieCompeticao:
    tipo_alvo = normalize.tipo_alvo_do_documento(dados)
    return SerieCompeticao(
        doc_id=doc_id,
        competicao_id=competicao_id,
        prova=str(dados.get("prova") or "Prova única").strip(),
        numero=normalize.para_int(dados.get("numero"), 1) or 1,
        atleta=normalize.nome_de_atleta(dados.get("atleta")) or atleta_padrao,
        tipo_alvo=tipo_alvo,
        distancia=(str(dados["distancia"]).strip() if dados.get("distancia") else None),
        total_registrado=normalize.para_int(dados.get("total")),
        flechas_string=dados.get("flechasString"),
        criado_em=normalize.para_datetime_iso(dados.get("criadoEm")),
        atualizado_em=normalize.para_datetime_iso(dados.get("atualizadoEm")),
    )


def carregar_competicao(fonte: FonteDeCompeticoes, competicao_id: str) -> Competicao | None:
    """Monta a competição completa: metadados + provas + séries + disparos."""
    dados_competicao, series_brutas, disparos_por_serie = fonte.carregar(competicao_id)
    if dados_competicao is None:
        return None

    meta = montar_competicao_dict(competicao_id, dados_competicao)
    competicao = Competicao(
        id=meta["id"],
        nome=meta["nome"],
        atleta=meta["atleta"],
        data=meta["data"],
        local=meta["local"],
        categoria=meta["categoria"],
        modalidade=meta["modalidade"],
        tipo_alvo=meta["tipo_alvo"],
        distancia=meta["distancia"],
        status=meta["status"],
        criado_em=meta["criado_em"],
        atualizado_em=meta["atualizado_em"],
        finalizado_em=meta["finalizado_em"],
    )

    for doc_id, dados_serie in series_brutas:
        serie = _montar_serie(doc_id, dados_serie, competicao_id, competicao.atleta)
        tokens = normalize.tokens_da_string_de_flechas(serie.flechas_string)
        for dados_disparo in disparos_por_serie.get(doc_id, []):
            disparo = _montar_disparo(dados_disparo, tokens, serie.tipo_alvo)
            if disparo is not None:
                serie.disparos.append(disparo)
        competicao.series.append(serie)

    competicao.ordenar()
    return competicao


def _agregar_placar(series_leves: list[dict]) -> dict:
    """Placar corrente a partir das séries (sem precisar dos disparos).

    Cada série já guarda o próprio `total` quando finalizada — somar
    isso é suficiente para mostrar o placar no cartão da lista, sem o
    custo de descer até a subcoleção `disparos` para cada competição.
    """
    total = 0
    series_finalizadas = 0
    flechas = 0
    for serie in series_leves:
        total_serie = normalize.para_int(serie.get("total"))
        if total_serie is not None:
            total += total_serie
            series_finalizadas += 1
        flechas += len(normalize.tokens_da_string_de_flechas(serie.get("flechasString")))
    return {
        "total": total,
        "quantidade_series": series_finalizadas,
        "quantidade_flechas": flechas,
    }


def listar_competicoes_resumo(fonte: FonteDeCompeticoes) -> list[dict]:
    """Metadados de todas as competições, com o placar corrente de cada uma.

    Usado pela tela de listagem — o cartão de cada competição mostra o
    placar sem exigir um clique para abri-la.
    """
    resultado = []
    for competicao_id, dados, series_leves in fonte.listar():
        item = montar_competicao_dict(competicao_id, dados)
        item.update(_agregar_placar(series_leves))
        resultado.append(item)
    resultado.sort(key=lambda c: (c["data"] or date.min, c["id"]), reverse=True)
    return resultado
