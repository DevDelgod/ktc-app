"""FERRAMENTA DE DESENVOLVIMENTO — não faz parte do aplicativo.

Sobe a API com uma base sintética em memória, para inspecionar o
dashboard sem credenciais do Firebase. Serve para validar layout,
gráficos e navegação; **não** substitui o teste contra o banco real.

O aplicativo em produção nunca usa este arquivo: `app.main` fala com o
Firestore de verdade através do `FirestoreAdmin`.

Uso:
    python tools/servidor_demo.py
    # abre em http://127.0.0.1:8000
"""

from __future__ import annotations

import math
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

os.environ.setdefault("SERVE_FRONTEND", "1")
os.environ.setdefault("CACHE_TTL", "0")

from app.api.deps import definir_servico  # noqa: E402
from app.services.analytics_service import ServicoAnalitico  # noqa: E402

ATLETAS = ["Gabriel Delgado", "Marina Alves"]


class FonteSintetica:
    """Gera treinos com a forma exata dos documentos do Firestore."""

    def __init__(self, semente: int = 7) -> None:
        self._rng = random.Random(semente)
        self._series: list[tuple[str, dict]] = []
        self._disparos: list[tuple[str, dict]] = []
        self._gerar()

    def series(self):
        return self._series

    def disparos(self):
        return self._disparos

    def _rotulo(self, distancia: float, aneis) -> str:
        for raio, nivel in aneis:
            if distancia <= raio:
                return "X" if nivel == 11 else str(nivel)
        return "M"

    def _gerar(self) -> None:
        aneis_simples = [
            (7.5, 11), (15, 10), (30, 9), (45, 8), (60, 7), (75, 6),
            (90, 5), (105, 4), (120, 3), (135, 2), (150, 1),
        ]
        aneis_triplo = [(4.5, 11), (9, 10), (18, 9), (27, 8), (36, 7), (45, 6)]
        base = date.today() - timedelta(days=70)

        for indice_treino in range(12):
            atleta = ATLETAS[indice_treino % 2]
            dia = base + timedelta(days=indice_treino * 6)
            triplo = indice_treino % 4 == 3

            tipo_alvo = "Alvo Triplo" if triplo else "Alvo Unitário"
            distancia = "18m" if triplo else self._rng.choice(["50m", "70m"])
            aneis = aneis_triplo if triplo else aneis_simples
            centros = [(0.0, 95.0), (0.0, 0.0), (0.0, -95.0)] if triplo else [(0.0, 0.0)]

            id_treino = f"TR-{dia.strftime('%d%m')}-{9 + indice_treino % 6:02d}30"

            # O atleta melhora ao longo do tempo: o desvio cai e o grupo
            # se aproxima do centro.
            desvio = (26 if triplo else 34) - indice_treino * 1.6
            vies_x = 9 - indice_treino * 0.6
            vies_y = -6 + indice_treino * 0.4

            for tempo in ("T1", "T2"):
                for numero in range(1, 7):
                    doc_id = f"{id_treino}-{tempo}-S{numero}"
                    rotulos: list[str] = []
                    disparos_da_serie: list[dict] = []

                    for flecha in range(1, 7):
                        centro = centros[self._rng.randrange(len(centros))]
                        dx = self._rng.gauss(vies_x, desvio)
                        dy = self._rng.gauss(vies_y, desvio)
                        rotulo = self._rotulo(math.hypot(dx, dy), aneis)
                        rotulos.append(rotulo)
                        disparos_da_serie.append(
                            {
                                "idDisparo": f"{doc_id}-F{flecha}",
                                "flecha": flecha,
                                "x": round(centro[0] + dx, 2),
                                "y": round(centro[1] + dy, 2),
                                "clima": "Sol",
                                "v_vento": str(self._rng.randrange(0, 20)),
                                "d_vento": "Norte",
                                "tipo_alvo": tipo_alvo,
                                "tipoAlvo": tipo_alvo,
                            }
                        )

                    total = sum(
                        10 if r == "X" else 0 if r == "M" else int(r) for r in rotulos
                    )

                    # Metade dos treinos usa o formato novo, com `score`
                    # no disparo; a outra metade fica no formato antigo,
                    # só com a flechasString — para exercitar os dois
                    # caminhos de leitura.
                    if indice_treino % 2 == 0:
                        for dados, rotulo in zip(disparos_da_serie, rotulos):
                            dados["score"] = rotulo

                    self._series.append(
                        (
                            doc_id,
                            {
                                "idTreino": id_treino,
                                "dataTreino": dia.isoformat(),
                                "atleta": atleta,
                                "tempo": tempo,
                                "serie": str(numero),
                                "serieGlobal": numero if tempo == "T1" else numero + 6,
                                "distancia": distancia,
                                "clima": "Sol",
                                "v_vento": "8",
                                "d_vento": "Norte",
                                "tipo_alvo": tipo_alvo,
                                "tipoAlvo": tipo_alvo,
                                "flechasString": " ".join(rotulos),
                                "total": total,
                            },
                        )
                    )
                    for dados in disparos_da_serie:
                        self._disparos.append((doc_id, dados))


def main() -> None:
    import uvicorn

    from app.main import app

    definir_servico(ServicoAnalitico(FonteSintetica(), ttl_cache=0))
    print("=" * 62)
    print("  SERVIDOR DEMO — dados sintéticos, sem Firebase")
    print("  Registro:  http://127.0.0.1:8000/")
    print("  Dashboard: http://127.0.0.1:8000/dashboard.html")
    print("  API docs:  http://127.0.0.1:8000/api/docs")
    print("=" * 62)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
