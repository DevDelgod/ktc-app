"""Configuração central do backend.

Nenhum valor sensível fica no código. Tudo vem de variáveis de ambiente,
opcionalmente carregadas de um arquivo `.env` que o `.gitignore` já
protege. Veja `.env.example` para o conjunto completo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Carrega backend/.env antes de qualquer os.getenv() deste módulo.
# Sem isso, FIREBASE_CREDENTIALS nunca chega ao processo e o SDK cai
# silenciosamente em Application Default Credentials, que não existe
# fora do Google Cloud — foi exatamente esse o sintoma em desenvolvimento.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _lista(valor: str | None, padrao: list[str]) -> list[str]:
    if not valor:
        return padrao
    return [item.strip() for item in valor.split(",") if item.strip()]


def _inteiro(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, "") or padrao)
    except ValueError:
        return padrao


@dataclass(frozen=True)
class Config:
    # Caminho do JSON da conta de serviço do Firebase Admin. Quando
    # vazio, o SDK cai nas Application Default Credentials — que é o
    # caminho recomendado em produção (Cloud Run, GCE, etc.).
    credenciais_firebase: str | None = field(
        default_factory=lambda: os.getenv("FIREBASE_CREDENTIALS") or None
    )
    projeto_firebase: str | None = field(
        default_factory=lambda: os.getenv("FIREBASE_PROJECT_ID") or None
    )

    # Origens autorizadas a chamar a API. Em produção isto deve listar
    # apenas o domínio do frontend.
    origens_cors: list[str] = field(
        default_factory=lambda: _lista(
            os.getenv("CORS_ORIGINS"),
            [
                "http://localhost:5173",
                "http://localhost:8000",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:8000",
            ],
        )
    )

    # Tempo de vida do cache analítico, em segundos. O Firestore é a
    # fonte da verdade; o cache evita reler a base inteira a cada
    # interação do dashboard.
    ttl_cache: int = field(default_factory=lambda: _inteiro("CACHE_TTL", 60))

    # Serve o frontend pelo próprio backend. Prático em desenvolvimento
    # e em deploy de instância única; em CDN, desligue.
    servir_frontend: bool = field(
        default_factory=lambda: os.getenv("SERVE_FRONTEND", "1") not in ("0", "false", "False")
    )

    ambiente: str = field(default_factory=lambda: os.getenv("AMBIENTE", "desenvolvimento"))

    @property
    def producao(self) -> bool:
        return self.ambiente.lower().startswith("prod")


@lru_cache(maxsize=1)
def config() -> Config:
    return Config()
