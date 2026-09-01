"""Cache de leitura com tempo de vida.

O dashboard dispara várias consultas em sequência — filtros, métricas,
disparos, histórico — e todas derivam do mesmo conjunto de treinos.
Reler o Firestore em cada uma seria desperdício de cota e de latência.

A estratégia é simples e adequada ao volume: carrega-se a base de
treinos uma vez, guarda-se em memória por `ttl` segundos, e todas as
análises do período são calculadas sob demanda a partir dela. Nenhum
dado derivado é gravado no banco.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class CacheComTTL(Generic[T]):
    """Cache de valor único, seguro para uso concorrente."""

    def __init__(self, ttl_segundos: int) -> None:
        self._ttl = max(0, ttl_segundos)
        self._valor: T | None = None
        self._carregado_em: float = 0.0
        self._trava = threading.Lock()

    @property
    def valido(self) -> bool:
        if self._valor is None:
            return False
        if self._ttl == 0:
            return False
        return (time.monotonic() - self._carregado_em) < self._ttl

    def obter(self, produtor: Callable[[], T]) -> T:
        """Devolve o valor em cache ou o reconstrói com `produtor`."""
        if self.valido:
            return self._valor  # type: ignore[return-value]

        with self._trava:
            # Outra thread pode ter preenchido enquanto esperávamos.
            if self.valido:
                return self._valor  # type: ignore[return-value]
            valor = produtor()
            self._valor = valor
            self._carregado_em = time.monotonic()
            return valor

    def invalidar(self) -> None:
        with self._trava:
            self._valor = None
            self._carregado_em = 0.0

    def idade_segundos(self) -> float | None:
        if self._valor is None:
            return None
        return round(time.monotonic() - self._carregado_em, 2)
