"""Ponto de entrada da API do KTC Performance.

Sobe o FastAPI, configura CORS e — em deploy de instância única —
serve o frontend estático pelo mesmo processo, o que elimina
configuração de CORS em produção e simplifica o deploy.

Execução local:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.competitions import router as router_competicoes
from app.api.routes import router, router_protegido
from app.config import config
from app.firebase.client import FirebaseIndisponivel, cliente_firestore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)
logger = logging.getLogger("ktc")

DESCRICAO = """
Camada analítica do **Kafu Tiro Certo**.

Lê os treinos gravados pelo aplicativo no Firestore e devolve métricas de
performance de tiro com arco: pontuação, precisão, agrupamento,
tendência e consistência.

As coordenadas são preservadas no sistema original do aplicativo —
origem no centro do alvo, eixo Y positivo para cima, unidade igual a
1/300 da largura do alvo desenhado.
"""


@asynccontextmanager
async def _ciclo_de_vida(_app: FastAPI):
    """Inicializa o Firebase Admin no boot, não na primeira requisição.

    A autenticação (`UsuarioDep`) roda antes de qualquer dependência de
    rota — inclusive antes da que toca o Firestore, que é quem inicializa
    o Admin SDK na primeira chamada. Num processo recém-iniciado, isso faz
    a primeiríssima requisição autenticada (a qualquer rota protegida)
    falhar com 401 espúrio, porque `verify_id_token` precisa do app do
    Admin SDK já existir. Adiantar essa inicialização aqui remove a
    corrida: o app já está pronto antes de aceitar a primeira requisição.
    """
    try:
        cliente_firestore()
    except FirebaseIndisponivel as erro:
        logger.error("Firebase indisponível no startup: %s", erro)
    yield


def criar_app() -> FastAPI:
    cfg = config()
    app = FastAPI(
        title="KTC Performance API",
        description=DESCRICAO,
        version="2.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=_ciclo_de_vida,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.origens_cors,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.exception_handler(FirebaseIndisponivel)
    async def _firebase_indisponivel(_request, erro: FirebaseIndisponivel):
        """Falha de credencial vira 503 legível, não stack trace."""
        logger.error("Firebase indisponível: %s", erro)
        return JSONResponse(status_code=503, content={"detail": str(erro)})

    app.include_router(router)
    app.include_router(router_protegido)
    app.include_router(router_competicoes)

    @app.middleware("http")
    async def _sem_cache_agressivo(request, call_next):
        """Evita que o navegador reuse JS/CSS antigos sem revalidar.

        `StaticFiles` só envia `ETag`/`Last-Modified`, sem `Cache-Control`.
        Sem essa diretiva, navegadores aplicam cache heurístico e podem
        reaproveitar por dezenas de minutos uma resposta antiga sem sequer
        consultar o servidor — foi exatamente isso que produziu uma
        configuração do Firebase desatualizada durante o desenvolvimento,
        mesmo depois do arquivo já ter sido corrigido em disco.
        `no-cache` não desliga o cache: força revalidação via ETag a cada
        acesso, que é barata (304 sem corpo) e sempre correta.
        """
        resposta = await call_next(request)
        if request.method == "GET" and "text" in resposta.headers.get("content-type", ""):
            resposta.headers["Cache-Control"] = "no-cache"
        return resposta

    if cfg.servir_frontend:
        _montar_frontend(app)

    return app


def _montar_frontend(app: FastAPI) -> None:
    """Serve o frontend estático quando ele existe ao lado do backend."""
    raiz = Path(__file__).resolve().parents[2] / "frontend"
    if not raiz.is_dir():
        logger.warning("Pasta frontend não encontrada em %s — servindo só a API.", raiz)
        return

    @app.get("/", include_in_schema=False)
    async def _raiz():
        return FileResponse(raiz / "index.html")

    @app.get("/dashboard", include_in_schema=False)
    async def _dashboard():
        return FileResponse(raiz / "dashboard.html")

    app.mount("/", StaticFiles(directory=raiz, html=True), name="frontend")
    logger.info("Frontend servido de %s", raiz)


app = criar_app()
