"""Rotas da API analítica do KTC.

Cada endpoint tem uma responsabilidade só. Nenhuma rota faz tudo: os
catálogos alimentam os filtros, o treino individual alimenta a visão
detalhada, o histórico alimenta a evolução e a comparação alimenta o
confronto entre treinos.

Contrato de dados: todas as distâncias e coordenadas saem em *unidades
do alvo* — o mesmo sistema que o aplicativo usa para gravar. Onde faz
sentido, a conversão para centímetros vem junto, com sufixo `_cm`.
"""

from __future__ import annotations

from dataclasses import replace

from fastapi import APIRouter, HTTPException, Query, status

from app.analytics import geometry
from app.analytics.metrics import descrever_treino
from app.api.deps import FiltrosDep, ServicoDep, UsuarioDep
from app.services.analytics_service import Filtros, ServicoAnalitico

# `/api/health` fica público — não expõe dado de atleta nenhum, só o
# estado do serviço, e é útil para monitoramento sem exigir login.
# Todo o resto exige um usuário autenticado: o dashboard mostra
# performance de atletas reais, e a API é o único guardião desses dados
# depois que a UI decide mostrá-los ou não.
router = APIRouter(prefix="/api")
router_protegido = APIRouter(prefix="/api", dependencies=[UsuarioDep])


@router.get("/health", tags=["sistema"], summary="Estado do serviço")
def health(servico: ServicoAnalitico = ServicoDep) -> dict:
    """Verifica se o backend fala com o Firestore e devolve o estado do cache."""
    treinos = servico.treinos()
    return {
        "status": "ok",
        "treinos_carregados": len(treinos),
        "cache": servico.estado_do_cache(),
    }


@router_protegido.post("/cache/invalidar", tags=["sistema"], summary="Força releitura do Firestore")
def invalidar_cache(servico: ServicoAnalitico = ServicoDep) -> dict:
    """Descarta o cache para que o próximo acesso releia o banco.

    Chamado pelo aplicativo logo após finalizar um treino, para que a
    análise apareça sem esperar o TTL expirar.
    """
    servico.invalidar_cache()
    return {"status": "cache invalidado"}


@router_protegido.get("/filters", tags=["catálogo"], summary="Opções de filtro coerentes entre si")
def filtros_disponiveis(
    servico: ServicoAnalitico = ServicoDep, filtros: Filtros = FiltrosDep
) -> dict:
    """Listas de seleção já restritas pelo que foi escolhido antes.

    Selecionar um atleta reduz as datas às dele; selecionar uma data
    reduz os treinos àquela data. Tudo sai do mesmo conjunto em cache,
    sem consulta adicional ao Firestore.
    """
    return servico.opcoes_de_filtro(filtros)


@router_protegido.get("/athletes", tags=["catálogo"], summary="Atletas com dados registrados")
def atletas(servico: ServicoAnalitico = ServicoDep) -> dict:
    return {"atletas": servico.atletas()}


@router_protegido.get("/athletes/{nome}/trainings", tags=["catálogo"], summary="Treinos de um atleta")
def treinos_do_atleta(
    nome: str, servico: ServicoAnalitico = ServicoDep, filtros: Filtros = FiltrosDep
) -> dict:
    """O nome vai no caminho; os demais filtros continuam disponíveis na query."""
    treinos = servico.filtrar(replace(filtros, atleta=nome))
    return {
        "atleta": nome,
        "quantidade": len(treinos),
        "treinos": [
            {
                "id_treino": t.id_treino,
                "data_treino": t.data_treino.isoformat() if t.data_treino else None,
                "series": t.quantidade_series,
                "flechas": t.quantidade_flechas,
                "total": t.total,
                "tipo_alvo": t.tipo_alvo_predominante,
                "distancias": t.distancias,
            }
            for t in treinos
        ],
    }


@router_protegido.get("/trainings", tags=["treinos"], summary="Lista de treinos filtrada")
def listar_treinos(
    servico: ServicoAnalitico = ServicoDep, filtros: Filtros = FiltrosDep
) -> dict:
    treinos = servico.filtrar(filtros)
    return {
        "quantidade": len(treinos),
        "treinos": [descrever_treino(t) for t in treinos],
    }


@router_protegido.get("/trainings/{id_treino}", tags=["treinos"], summary="Cabeçalho de um treino")
def obter_treino(
    id_treino: str, servico: ServicoAnalitico = ServicoDep, filtros: Filtros = FiltrosDep
) -> dict:
    treino = servico.treino_por_id(id_treino, filtros)
    if treino is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Treino '{id_treino}' não encontrado.")
    return descrever_treino(treino)


@router_protegido.get(
    "/trainings/{id_treino}/analytics",
    tags=["treinos"],
    summary="Pacote analítico completo de um treino",
)
def analytics_do_treino(
    id_treino: str, servico: ServicoAnalitico = ServicoDep, filtros: Filtros = FiltrosDep
) -> dict:
    """Pontuação, dispersão, consistência, distribuição e qualidade do dado."""
    treino = servico.treino_por_id(id_treino, filtros)
    if treino is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Treino '{id_treino}' não encontrado.")
    return servico.analisar(treino)


@router_protegido.get(
    "/trainings/{id_treino}/shots",
    tags=["treinos"],
    summary="Disparos individuais e geometria do alvo",
)
def disparos_do_treino(
    id_treino: str, servico: ServicoAnalitico = ServicoDep, filtros: Filtros = FiltrosDep
) -> dict:
    """Alimenta o gráfico de dispersão sobre o alvo.

    Devolve cada flecha com coordenada absoluta (x, y), deslocamento em
    relação à face atingida (dx, dy), pontuação e distância ao centro —
    mais a geometria do alvo, para que o frontend desenhe os anéis
    corretos sem duplicar as constantes.
    """
    treino = servico.treino_por_id(id_treino, filtros)
    if treino is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Treino '{id_treino}' não encontrado.")
    return servico.disparos(treino)


@router_protegido.get("/analytics/history", tags=["analytics"], summary="Evolução ao longo do tempo")
def historico(servico: ServicoAnalitico = ServicoDep, filtros: Filtros = FiltrosDep) -> dict:
    """Um ponto por treino, com score, média, dispersão e consistência."""
    return servico.historico(filtros)


@router_protegido.get("/analytics/comparison", tags=["analytics"], summary="Comparação entre treinos")
def comparacao(
    ids: str = Query(..., description="IDs de treino separados por vírgula", alias="ids"),
    servico: ServicoAnalitico = ServicoDep,
    filtros: Filtros = FiltrosDep,
) -> dict:
    lista = [i.strip() for i in ids.split(",") if i.strip()]
    if not lista:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Informe ao menos um ID de treino.")
    if len(lista) > 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Comparação limitada a 6 treinos.")
    return servico.comparar(lista, filtros)


@router_protegido.get("/targets/{tipo_alvo}", tags=["catálogo"], summary="Geometria de um tipo de alvo")
def geometria_do_alvo(tipo_alvo: str) -> dict:
    """Raios, níveis e centros das faces.

    O frontend desenha o alvo do dashboard a partir daqui, o que mantém
    uma fonte de verdade só para a geometria.
    """
    return geometry.descrever(tipo_alvo)
