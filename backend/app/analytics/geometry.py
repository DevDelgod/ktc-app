"""Geometria dos alvos do KTC.

Esta é a tradução direta, número a número, das constantes de `script.js`
(função `desenharAlvo`, linhas 441-533 do arquivo original). Nada aqui é
inventado: os raios, os níveis e as coordenadas dos centros são os mesmos
usados para desenhar o alvo na tela.

SISTEMA DE COORDENADAS (verificado no código do frontend)
---------------------------------------------------------
O app grava `x` e `y` num espaço lógico de 300 unidades de largura:

    ratio = largura_do_canvas_px / 300
    x = (px - centro) / ratio
    y = (centro - py) / ratio      <- eixo Y invertido: positivo para CIMA

Portanto:
  * origem (0, 0) = centro geométrico do canvas;
  * unidade = 1/300 da largura do alvo desenhado;
  * o anel externo do alvo simples tem raio 150 u, ou seja, o alvo simples
    ocupa exatamente a largura inteira do espaço lógico.

ATENÇÃO AO CENTRO DO ALVO
-------------------------
Para o alvo simples o centro do alvo coincide com a origem (0, 0).
Para o alvo TRIPLO isso é FALSO: existem três faces, centradas em
(0, +95), (0, 0) e (0, -95). Qualquer cálculo de "distância ao centro"
no alvo triplo precisa usar o centro da face mais próxima, não a origem.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

# Nomes de tipo de alvo gravados pelo frontend.
# Três strings para duas geometrias — 'Alvo Unitário' (outdoor) e
# 'Alvo Único' (18m, face simples) desenham exatamente o mesmo alvo.
ALVO_UNITARIO = "Alvo Unitário"
ALVO_UNICO = "Alvo Único"
ALVO_TRIPLO = "Alvo Triplo"


@dataclass(frozen=True)
class Ring:
    """Um anel do alvo.

    `raio` está em unidades do alvo. `nivel` é a propriedade homônima do
    JavaScript e corresponde à pontuação: nível 1..10 valem o próprio
    número, e o nível 11 é o X (10 interno), que também vale 10 pontos.
    """

    raio: float
    nivel: int

    @property
    def pontos(self) -> int:
        return 10 if self.nivel == 11 else self.nivel

    @property
    def rotulo(self) -> str:
        return "X" if self.nivel == 11 else str(self.nivel)


@dataclass(frozen=True)
class TargetGeometry:
    """Geometria completa de um tipo de alvo."""

    nome: str
    aneis: tuple[Ring, ...]
    centros: tuple[tuple[float, float], ...]
    # Diâmetro real da face em centímetros, usado só para converter
    # unidades em cm. Ver nota sobre calibração em `unidades_para_cm`.
    diametro_cm: float
    # Metade da largura do espaço lógico. Constante do frontend.
    extensao_logica: float = 150.0

    @property
    def raio_externo(self) -> float:
        return max(anel.raio for anel in self.aneis)

    @property
    def multiface(self) -> bool:
        return len(self.centros) > 1

    def unidades_para_cm(self, valor: float) -> float:
        """Converte unidades do alvo para centímetros.

        A calibração é feita por tipo de alvo: o raio externo desenhado
        corresponde ao raio real da face. Os dois tipos têm fatores
        diferentes porque o desenho do alvo triplo não está na mesma
        escala do simples — isso é uma característica do desenho
        original, não uma correção nossa.
        """
        cm_por_unidade = (self.diametro_cm / 2.0) / self.raio_externo
        return valor * cm_por_unidade


# Alvo simples: 11 anéis, raios 150 -> 7,5 (passo 15, com o X pela metade).
# Fonte: script.js linhas 491-503.
GEOMETRIA_SIMPLES = TargetGeometry(
    nome=ALVO_UNICO,
    aneis=(
        Ring(150.0, 1),
        Ring(135.0, 2),
        Ring(120.0, 3),
        Ring(105.0, 4),
        Ring(90.0, 5),
        Ring(75.0, 6),
        Ring(60.0, 7),
        Ring(45.0, 8),
        Ring(30.0, 9),
        Ring(15.0, 10),
        Ring(7.5, 11),
    ),
    centros=((0.0, 0.0),),
    diametro_cm=122.0,
)

# Alvo triplo: 3 faces em y = +95, 0, -95; 6 anéis por face, raios 45 -> 4,5.
# Fonte: script.js linhas 442-455.
GEOMETRIA_TRIPLA = TargetGeometry(
    nome=ALVO_TRIPLO,
    aneis=(
        Ring(45.0, 6),
        Ring(36.0, 7),
        Ring(27.0, 8),
        Ring(18.0, 9),
        Ring(9.0, 10),
        Ring(4.5, 11),
    ),
    centros=((0.0, 95.0), (0.0, 0.0), (0.0, -95.0)),
    diametro_cm=40.0,
)

_POR_NOME: dict[str, TargetGeometry] = {
    ALVO_UNITARIO: GEOMETRIA_SIMPLES,
    ALVO_UNICO: GEOMETRIA_SIMPLES,
    ALVO_TRIPLO: GEOMETRIA_TRIPLA,
}


def geometria(tipo_alvo: str | None) -> TargetGeometry:
    """Devolve a geometria de um tipo de alvo.

    Aceita as três strings que o app grava. Qualquer valor desconhecido
    (inclusive `None`, que aparece em documentos antigos incompletos)
    cai no alvo simples, que é o padrão do aplicativo.
    """
    if not tipo_alvo:
        return GEOMETRIA_SIMPLES
    return _POR_NOME.get(tipo_alvo.strip(), GEOMETRIA_SIMPLES)


def centro_mais_proximo(
    x: float, y: float, centros: Sequence[tuple[float, float]]
) -> tuple[float, float]:
    """Face do alvo à qual o disparo pertence.

    Para o alvo simples há um único centro e a resposta é sempre (0, 0).
    Para o triplo, o disparo é atribuído à face mais próxima — que é como
    a pontuação funciona em campo.
    """
    return min(centros, key=lambda c: math.hypot(x - c[0], y - c[1]))


def distancia_do_centro(x: float, y: float, tipo_alvo: str | None) -> float:
    """Distância euclidiana do disparo ao centro da sua face, em unidades.

        d = sqrt((x - cx)^2 + (y - cy)^2)

    onde (cx, cy) é o centro da face mais próxima. Para o alvo simples
    isso se reduz a sqrt(x^2 + y^2), mas para o triplo NÃO — por isso o
    centro nunca é assumido como (0, 0).
    """
    geo = geometria(tipo_alvo)
    cx, cy = centro_mais_proximo(x, y, geo.centros)
    return math.hypot(x - cx, y - cy)


def anel_do_disparo(x: float, y: float, tipo_alvo: str | None) -> Ring | None:
    """Anel atingido pelo disparo, ou `None` se caiu fora do alvo (M).

    O anel válido é o de menor raio que ainda contém o ponto: percorremos
    do centro para fora e paramos no primeiro que comporta a distância.
    """
    geo = geometria(tipo_alvo)
    dist = distancia_do_centro(x, y, tipo_alvo)
    for anel in sorted(geo.aneis, key=lambda a: a.raio):
        if dist <= anel.raio:
            return anel
    return None


def score_geometrico(x: float, y: float, tipo_alvo: str | None) -> int:
    """Pontuação derivada da posição do disparo.

    Este valor NÃO é o que o app grava — o app registra a pontuação
    digitada pelo atleta no teclado. Serve para conferir uma coisa contra
    a outra e medir a qualidade do dado.
    """
    anel = anel_do_disparo(x, y, tipo_alvo)
    return anel.pontos if anel else 0


def rotulo_geometrico(x: float, y: float, tipo_alvo: str | None) -> str:
    anel = anel_do_disparo(x, y, tipo_alvo)
    return anel.rotulo if anel else "M"


def dentro_do_alvo(x: float, y: float, tipo_alvo: str | None) -> bool:
    return anel_do_disparo(x, y, tipo_alvo) is not None


def descrever(tipo_alvo: str | None) -> dict:
    """Geometria serializável, consumida pelo frontend para desenhar o alvo.

    Mantém o frontend e o backend com uma fonte de verdade só para os
    raios: o dashboard desenha o alvo a partir daqui.
    """
    geo = geometria(tipo_alvo)
    return {
        "nome": geo.nome,
        "extensao_logica": geo.extensao_logica,
        "raio_externo": geo.raio_externo,
        "diametro_cm": geo.diametro_cm,
        "multiface": geo.multiface,
        "centros": [{"x": cx, "y": cy} for cx, cy in geo.centros],
        "aneis": [
            {
                "raio": anel.raio,
                "nivel": anel.nivel,
                "pontos": anel.pontos,
                "rotulo": anel.rotulo,
            }
            for anel in sorted(geo.aneis, key=lambda a: -a.raio)
        ],
    }
