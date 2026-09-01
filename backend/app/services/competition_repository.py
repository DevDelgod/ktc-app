"""Leitura do Firestore para o modo Competição.

Estratégia de leitura deliberadamente diferente da de `repository.py`
(treinos): ali, o dashboard precisa agregar TODOS os treinos da conta de
uma vez (histórico, comparação), o que justifica uma *collection group
query* varrendo todas as subcoleções `disparos` do banco inteiro.

Aqui não — o uso real é abrir UMA competição por vez (gravar flechas ao
vivo, ver o relatório dela). Por isso a leitura é direta pelo caminho:
`competicoes/{id}` → subcoleção `series` → subcoleção `disparos` de cada
série. Duas vantagens: evitaido custo de uma collection-group query
sobre o banco inteiro para abrir uma única competição, e evita colisão
de nome — treino e competição usam a mesma subcoleção `disparos`, então
uma collection-group query aqui misturaria os dois sem querer.
"""

from __future__ import annotations

from typing import Iterator, Protocol

from app.models.competition import STATUS_PLANEJADA
from app.services import normalize

COLECAO_COMPETICOES = "competicoes"
SUBCOLECAO_SERIES = "series"
SUBCOLECAO_DISPAROS = "disparos"


class FonteDeCompeticoes(Protocol):
    """Contrato mínimo: listar metadados (+ séries leves), e carregar uma
    competição por completo."""

    def listar(self) -> Iterator[tuple[str, dict, list[dict]]]: ...

    def carregar(self, competicao_id: str) -> tuple[dict | None, list[tuple[str, dict]], dict[str, list[dict]]]: ...


class FirestoreCompeticoes:
    """Fonte real, apoiada no Firebase Admin SDK."""

    def __init__(self, cliente) -> None:
        self._db = cliente

    def listar(self) -> Iterator[tuple[str, dict, list[dict]]]:
        """Metadados de cada competição, com as séries (sem disparos).

        A lista de competições mostra o placar corrente em cada cartão —
        cada série já guarda o próprio `total`, então basta ler os
        documentos de série (baratos, poucos por competição) para somar
        o placar, sem descer até a subcoleção `disparos`.
        """
        for documento in self._db.collection(COLECAO_COMPETICOES).stream():
            series = [s.to_dict() or {} for s in documento.reference.collection(SUBCOLECAO_SERIES).stream()]
            yield documento.id, documento.to_dict() or {}, series

    def carregar(self, competicao_id: str):
        doc_competicao = self._db.collection(COLECAO_COMPETICOES).document(competicao_id).get()
        if not doc_competicao.exists:
            return None, [], {}

        dados_competicao = doc_competicao.to_dict() or {}

        series: list[tuple[str, dict]] = []
        disparos_por_serie: dict[str, list[dict]] = {}

        ref_series = doc_competicao.reference.collection(SUBCOLECAO_SERIES)
        for doc_serie in ref_series.stream():
            series.append((doc_serie.id, doc_serie.to_dict() or {}))
            disparos = []
            for doc_disparo in doc_serie.reference.collection(SUBCOLECAO_DISPAROS).stream():
                disparos.append(doc_disparo.to_dict() or {})
            disparos_por_serie[doc_serie.id] = disparos

        return dados_competicao, series, disparos_por_serie


def montar_competicao_dict(competicao_id: str, dados: dict) -> dict:
    """Normaliza os campos de metadados de uma competição, para uso interno."""
    return {
        "id": competicao_id,
        "nome": str(dados.get("nome") or "").strip(),
        "atleta": normalize.nome_de_atleta(dados.get("atleta")),
        "data": normalize.para_data(dados.get("data")),
        "local": (str(dados["local"]).strip() if dados.get("local") else None),
        "categoria": (str(dados["categoria"]).strip() if dados.get("categoria") else None),
        "modalidade": (str(dados["modalidade"]).strip() if dados.get("modalidade") else None),
        "tipo_alvo": normalize.tipo_alvo_do_documento(dados),
        "distancia": (str(dados["distancia"]).strip() if dados.get("distancia") else None),
        "status": str(dados.get("status") or STATUS_PLANEJADA).strip(),
        "criado_em": normalize.para_datetime_iso(dados.get("criadoEm")),
        "atualizado_em": normalize.para_datetime_iso(dados.get("atualizadoEm")),
        "finalizado_em": normalize.para_datetime_iso(dados.get("finalizadoEm")),
    }
