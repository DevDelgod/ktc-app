"""Leitura do Firestore e montagem do modelo de domínio.

A fonte de dados é injetável (`FonteDeDados`), o que permite rodar todo
o pipeline analítico em teste sobre documentos sintéticos com a forma
exata dos documentos reais, sem tocar no banco.

Estratégia de leitura
---------------------
Os disparos vivem em subcoleções (`treinos/{id}/disparos/F1..Fn`). Ler
uma subcoleção por série seria N+1 consultas. O Firestore resolve isso
com *collection group query*: uma única consulta traz todos os disparos
de todas as séries, e o documento pai é recuperado do caminho. É o que
`FirestoreAdmin.disparos()` faz.
"""

from __future__ import annotations

import logging
from typing import Iterable, Iterator, Protocol

from app.analytics import geometry
from app.models.domain import Disparo, Serie, Treino, agrupar_em_treinos
from app.services import normalize

logger = logging.getLogger(__name__)

# Origem da pontuação de um disparo, em ordem de confiança.
ORIGEM_CAMPO = "campo_score"          # documento novo, com `score` gravado
ORIGEM_STRING = "flechas_string"      # histórico, pareado por posição
ORIGEM_AUSENTE = "ausente"            # série sem pontuação registrada


class FonteDeDados(Protocol):
    """Contrato mínimo de leitura.

    `series()` devolve `(doc_id, dados)` de cada documento da coleção
    `treinos`. `disparos()` devolve `(doc_id_da_serie, dados)` de cada
    documento das subcoleções `disparos`.
    """

    def series(self) -> Iterable[tuple[str, dict]]: ...

    def disparos(self) -> Iterable[tuple[str, dict]]: ...


class FirestoreAdmin:
    """Fonte real, apoiada no Firebase Admin SDK."""

    COLECAO_SERIES = "treinos"
    SUBCOLECAO_DISPAROS = "disparos"

    def __init__(self, cliente) -> None:
        self._db = cliente

    def series(self) -> Iterator[tuple[str, dict]]:
        for documento in self._db.collection(self.COLECAO_SERIES).stream():
            yield documento.id, documento.to_dict() or {}

    def disparos(self) -> Iterator[tuple[str, dict]]:
        """Todos os disparos numa consulta só, via collection group.

        `documento.reference.parent.parent.id` devolve o ID da série dona
        do disparo — é assim que reconstruímos o vínculo pai-filho que o
        `to_dict()` não traz.
        """
        consulta = self._db.collection_group(self.SUBCOLECAO_DISPAROS)
        for documento in consulta.stream():
            pai = documento.reference.parent.parent
            if pai is None:
                continue
            yield pai.id, documento.to_dict() or {}


def _resolver_pontuacao(
    dados_disparo: dict, tokens: list[str], numero: int
) -> tuple[str | None, int | None, str]:
    """Determina a pontuação de um disparo.

    Ordem de precedência:

    1. Campo `score` no próprio documento do disparo. Passou a ser
       gravado pelo app na reestruturação; é a fonte explícita.
    2. Posição correspondente em `flechasString` da série. É a mesma
       correspondência implícita que o app sempre usou — a n-ésima
       flecha marcada no alvo com a n-ésima tecla digitada — agora
       explicitada e testada. É o que mantém os dados históricos vivos.
    3. Nada. A série não foi finalizada e o disparo fica sem pontuação,
       em vez de virar zero.
    """
    bruto = dados_disparo.get("score", dados_disparo.get("pontuacao"))
    pontos = normalize.pontos_do_rotulo(bruto)
    if pontos is not None:
        return str(bruto).strip().upper(), pontos, ORIGEM_CAMPO

    indice = numero - 1
    if 0 <= indice < len(tokens):
        rotulo = tokens[indice]
        pontos = normalize.pontos_do_rotulo(rotulo)
        if pontos is not None:
            return rotulo.strip().upper(), pontos, ORIGEM_STRING

    return None, None, ORIGEM_AUSENTE


def _montar_disparo(dados: dict, tokens: list[str], tipo_alvo: str) -> Disparo | None:
    """Converte um documento de disparo em objeto de domínio.

    Descarta o disparo se faltar coordenada — sem X/Y ele não serve para
    nenhuma das análises e contaminaria as médias.
    """
    x = normalize.para_float(dados.get("x"))
    y = normalize.para_float(dados.get("y"))
    if x is None or y is None:
        return None

    numero = normalize.para_int(dados.get("flecha"), 0) or 0
    rotulo, pontos, origem = _resolver_pontuacao(dados, tokens, numero)

    anel = geometry.anel_do_disparo(x, y, tipo_alvo)
    return Disparo(
        numero=numero,
        x=x,
        y=y,
        id_disparo=dados.get("idDisparo"),
        rotulo=rotulo,
        pontos=pontos,
        origem_score=origem,
        distancia_centro=geometry.distancia_do_centro(x, y, tipo_alvo),
        pontos_geometricos=anel.pontos if anel else 0,
        rotulo_geometrico=anel.rotulo if anel else "M",
        dentro_do_alvo=anel is not None,
    )


def _montar_serie(doc_id: str, dados: dict) -> Serie | None:
    """Converte um documento da coleção `treinos` em uma série.

    O `idTreino`, o tempo e o número da série são lidos dos campos do
    documento; quando faltam (documento parcial), caem para o que estiver
    codificado no próprio ID, que é como o app monta a chave.
    """
    partes = normalize.partes_do_doc_id(doc_id)
    id_treino = str(dados.get("idTreino") or "").strip()
    tempo = str(dados.get("tempo") or "").strip()
    numero = normalize.para_int(dados.get("serie"))

    if partes:
        id_treino = id_treino or partes[0]
        tempo = tempo or partes[1]
        numero = numero if numero is not None else partes[2]

    if not id_treino:
        logger.warning("Documento %s ignorado: sem idTreino identificável", doc_id)
        return None

    tipo_alvo = normalize.tipo_alvo_do_documento(dados)
    return Serie(
        doc_id=doc_id,
        id_treino=id_treino,
        tempo=tempo or "T1",
        numero=numero if numero is not None else 0,
        atleta=normalize.nome_de_atleta(dados.get("atleta")),
        data_treino=normalize.para_data(dados.get("dataTreino")),
        distancia=(str(dados["distancia"]).strip() if dados.get("distancia") else None),
        tipo_alvo=tipo_alvo,
        familia_alvo=normalize.familia_alvo(tipo_alvo),
        clima=(str(dados["clima"]).strip() if dados.get("clima") else None),
        v_vento=normalize.para_float(dados.get("v_vento"), 0.0),
        d_vento=(str(dados["d_vento"]).strip() if dados.get("d_vento") else None),
        total_registrado=normalize.para_int(dados.get("total")),
        flechas_string=dados.get("flechasString"),
        criado_em=normalize.para_datetime_iso(dados.get("createdAt")),
        atualizado_em=normalize.para_datetime_iso(dados.get("updatedAt")),
    )


class Repositorio:
    """Monta o modelo de domínio completo a partir de uma fonte de dados."""

    def __init__(self, fonte: FonteDeDados) -> None:
        self._fonte = fonte

    def carregar_treinos(self) -> list[Treino]:
        series_por_doc: dict[str, Serie] = {}
        for doc_id, dados in self._fonte.series():
            serie = _montar_serie(doc_id, dados)
            if serie is not None:
                series_por_doc[doc_id] = serie

        disparos_por_serie: dict[str, list[dict]] = {}
        for doc_id_serie, dados in self._fonte.disparos():
            disparos_por_serie.setdefault(doc_id_serie, []).append(dados)

        orfaos = set(disparos_por_serie) - set(series_por_doc)
        if orfaos:
            logger.warning(
                "%d subcoleção(ões) de disparos sem série correspondente: %s",
                len(orfaos),
                ", ".join(sorted(orfaos)[:5]),
            )

        for doc_id, serie in series_por_doc.items():
            tokens = normalize.tokens_da_string_de_flechas(serie.flechas_string)
            for dados in disparos_por_serie.get(doc_id, []):
                disparo = _montar_disparo(dados, tokens, serie.tipo_alvo)
                if disparo is not None:
                    serie.disparos.append(disparo)

        return agrupar_em_treinos(series_por_doc.values())
