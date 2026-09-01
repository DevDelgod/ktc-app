"""Rotas do modo Competição.

Somente leitura, no mesmo espírito de `routes.py`: criar competição,
registrar flechas e mudar status acontecem no frontend, direto no
Firestore (`frontend/js/competitions-firebase.js`), como já acontece
para treinos. O backend lê o que foi gravado e devolve análise —
"consultar progresso" fica dentro do próprio `GET /{id}`, sem rota
redundante, porque progresso é só um subconjunto do estado da
competição, não uma consulta com forma diferente.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ServicoCompeticoesDep, UsuarioDep
from app.services.competition_service import ServicoCompeticoes

router = APIRouter(prefix="/api/competitions", dependencies=[UsuarioDep])


def _exigir(servico: ServicoCompeticoes, competicao_id: str):
    competicao = servico.obter(competicao_id)
    if competicao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Competição '{competicao_id}' não encontrada.")
    return competicao


@router.get("", summary="Lista competições")
def listar_competicoes(servico: ServicoCompeticoes = ServicoCompeticoesDep) -> dict:
    lista = servico.listar()
    return {"quantidade": len(lista), "competicoes": lista}


@router.post("/cache/invalidar", summary="Força releitura do Firestore")
def invalidar_cache(servico: ServicoCompeticoes = ServicoCompeticoesDep) -> dict:
    """Chamado pelo frontend após criar competição, gravar flecha,
    gravar pontuação ou mudar status — mesmo padrão do
    `/api/cache/invalidar` de treinos."""
    servico.invalidar_cache()
    return {"status": "cache invalidado"}


@router.get("/{competicao_id}", summary="Consulta uma competição, incluindo o progresso atual")
def obter_competicao(competicao_id: str, servico: ServicoCompeticoes = ServicoCompeticoesDep) -> dict:
    _exigir(servico, competicao_id)
    return servico.progresso(competicao_id)


@router.get("/{competicao_id}/analytics", summary="Pacote analítico completo da competição")
def analytics_da_competicao(competicao_id: str, servico: ServicoCompeticoes = ServicoCompeticoesDep) -> dict:
    _exigir(servico, competicao_id)
    return servico.analytics(competicao_id)


@router.get("/{competicao_id}/shots", summary="Disparos individuais e geometria do alvo")
def disparos_da_competicao(competicao_id: str, servico: ServicoCompeticoes = ServicoCompeticoesDep) -> dict:
    _exigir(servico, competicao_id)
    return servico.disparos(competicao_id)


@router.get("/{competicao_id}/report", summary="Relatório final de performance")
def relatorio_da_competicao(competicao_id: str, servico: ServicoCompeticoes = ServicoCompeticoesDep) -> dict:
    """Gerado sob demanda a partir dos dados reais — inclusive antes de a
    competição ser marcada como concluída, como prévia."""
    _exigir(servico, competicao_id)
    return servico.relatorio(competicao_id)
