"""Inicialização do Firebase Admin SDK.

As credenciais nunca aparecem no código nem no frontend. Duas formas de
autenticação são aceitas, nesta ordem:

1. `FIREBASE_CREDENTIALS` apontando para o JSON da conta de serviço —
   caminho usado em desenvolvimento local. O arquivo está no
   `.gitignore`.
2. Application Default Credentials — caminho recomendado em produção
   (Cloud Run, App Engine, GCE), onde a identidade vem do ambiente e não
   existe arquivo de chave para vazar.
"""

from __future__ import annotations

import logging
import os
import threading

from app.config import config

logger = logging.getLogger(__name__)

_trava = threading.Lock()
_cliente = None


class FirebaseIndisponivel(RuntimeError):
    """O Admin SDK não pôde ser inicializado.

    A API responde 503 com esta mensagem em vez de estourar, para que o
    dashboard consiga mostrar um estado de erro compreensível.
    """


def cliente_firestore():
    """Devolve o cliente Firestore, inicializando o app na primeira chamada."""
    global _cliente
    if _cliente is not None:
        return _cliente

    with _trava:
        if _cliente is not None:
            return _cliente

        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
        except ImportError as erro:  # pragma: no cover - ambiente sem dependência
            raise FirebaseIndisponivel(
                "firebase-admin não está instalado. Rode: pip install -r requirements.txt"
            ) from erro

        cfg = config()

        if not firebase_admin._apps:  # noqa: SLF001 - API pública do SDK
            try:
                if cfg.credenciais_firebase:
                    if not os.path.exists(cfg.credenciais_firebase):
                        raise FirebaseIndisponivel(
                            f"Arquivo de credenciais não encontrado: {cfg.credenciais_firebase}. "
                            "Ajuste FIREBASE_CREDENTIALS no .env."
                        )
                    credencial = credentials.Certificate(cfg.credenciais_firebase)
                    logger.info("Firebase autenticado por conta de serviço.")
                else:
                    credencial = credentials.ApplicationDefault()
                    logger.info("Firebase autenticado por Application Default Credentials.")

                opcoes = {"projectId": cfg.projeto_firebase} if cfg.projeto_firebase else None
                firebase_admin.initialize_app(credencial, opcoes)
            except FirebaseIndisponivel:
                raise
            except Exception as erro:  # noqa: BLE001 - qualquer falha vira 503 legível
                raise FirebaseIndisponivel(
                    f"Não foi possível inicializar o Firebase: {erro}"
                ) from erro

        _cliente = firestore.client()
        return _cliente


def reiniciar() -> None:
    """Descarta o cliente em memória. Usado em teste."""
    global _cliente
    with _trava:
        _cliente = None
