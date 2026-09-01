"""Normalização de leitura dos documentos do Firestore.

Todo o saneamento acontece **em leitura**. Nenhum documento é reescrito:
os dados históricos ficam exatamente como estão no banco, e as
inconsistências conhecidas são resolvidas aqui, na entrada do pipeline
analítico. Isso é o que permite que treinos antigos e novos passem pelo
mesmo caminho.

Inconsistências tratadas (todas confirmadas no código do frontend):

1. `tipoAlvo` grava três strings para duas geometrias — 'Alvo Unitário'
   e 'Alvo Único' desenham o mesmo alvo. Agrupar por essa coluna crua
   dividiria o mesmo alvo em duas categorias.
2. `serieGlobal` soma 6 fixo no T2 (`script.js:60`), ignorando o número
   real de séries por rodada. Com 3 séries por rodada, T2-S1 vira 7 em
   vez de 4. Recalculamos a ordem a partir dos dados.
3. `v_vento` é gravado como string, inclusive `"0"` quando vazio.
4. `x`/`y` chegam como número nos documentos atuais, mas o frontend já
   os montou como string com vírgula decimal em algum ponto do
   histórico. Aceitamos as duas formas.
5. `serie` é string (`"1"`) enquanto `serieGlobal` é número.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any

from app.analytics.geometry import ALVO_TRIPLO, ALVO_UNICO, ALVO_UNITARIO

# Famílias canônicas de alvo. 'Alvo Unitário' e 'Alvo Único' colapsam
# na mesma família porque desenham a mesma geometria; o valor bruto
# continua disponível para quem precisar auditar.
FAMILIA_SIMPLES = "simples"
FAMILIA_TRIPLA = "tripla"

_FAMILIA_POR_NOME = {
    ALVO_UNITARIO: FAMILIA_SIMPLES,
    ALVO_UNICO: FAMILIA_SIMPLES,
    ALVO_TRIPLO: FAMILIA_TRIPLA,
}

_RE_DOC_ID = re.compile(r"^(?P<id_treino>.+)-(?P<tempo>T\d+)-S(?P<serie>\d+)$")


def para_float(valor: Any, padrao: float | None = None) -> float | None:
    """Converte para float aceitando número, string com ponto ou com vírgula."""
    if valor is None or valor == "":
        return padrao
    if isinstance(valor, (int, float)):
        resultado = float(valor)
        return padrao if math.isnan(resultado) else resultado
    try:
        return float(str(valor).strip().replace(",", "."))
    except (TypeError, ValueError):
        return padrao


def para_int(valor: Any, padrao: int | None = None) -> int | None:
    convertido = para_float(valor)
    return padrao if convertido is None else int(convertido)


def familia_alvo(tipo_alvo: str | None) -> str:
    if not tipo_alvo:
        return FAMILIA_SIMPLES
    return _FAMILIA_POR_NOME.get(tipo_alvo.strip(), FAMILIA_SIMPLES)


def tipo_alvo_do_documento(doc: dict) -> str:
    """Lê o tipo de alvo tolerando a duplicação `tipoAlvo` / `tipo_alvo`.

    Os dois campos guardam o mesmo valor em todos os documentos gravados
    pelo app, mas documentos parciais podem ter só um deles.
    """
    bruto = doc.get("tipoAlvo") or doc.get("tipo_alvo")
    if isinstance(bruto, str) and bruto.strip():
        return bruto.strip()
    return ALVO_UNITARIO


def pontos_do_rotulo(rotulo: Any) -> int | None:
    """Converte um símbolo do teclado numérico em pontos.

    Regra idêntica à do frontend (`script.js:780-783`):
    `X` vale 10, `M` vale 0, o resto vale o próprio número.
    Devolve `None` para símbolo irreconhecível, para que o disparo possa
    ser contado como "sem pontuação" em vez de virar zero silenciosamente.
    """
    if rotulo is None:
        return None
    texto = str(rotulo).strip().upper()
    if texto == "":
        return None
    if texto == "X":
        return 10
    if texto == "M":
        return 0
    try:
        valor = int(texto)
    except ValueError:
        return None
    return valor if 0 <= valor <= 10 else None


def tokens_da_string_de_flechas(flechas_string: Any) -> list[str]:
    """Divide `flechasString` ("X 10 9 9 8 M") na lista de símbolos."""
    if not flechas_string:
        return []
    return [t for t in str(flechas_string).split() if t]


def partes_do_doc_id(doc_id: str) -> tuple[str, str, int] | None:
    """Extrai (idTreino, tempo, serie) do ID do documento.

    O ID é montado por `getTreinoDocId()` como `{idTreino}-{tempo}-S{serie}`.
    Como o próprio `idTreino` contém hífens (`TR-3108-1605`), a separação
    é feita a partir do fim.
    """
    encontrado = _RE_DOC_ID.match(doc_id or "")
    if not encontrado:
        return None
    return (
        encontrado.group("id_treino"),
        encontrado.group("tempo"),
        int(encontrado.group("serie")),
    )


def para_data(valor: Any) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor).strip()[:10])
    except ValueError:
        return None


def para_datetime_iso(valor: Any) -> str | None:
    """Serializa carimbos do Firestore, que chegam como objetos com tzinfo."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    # Carimbos do Admin SDK expõem .isoformat() via DatetimeWithNanoseconds.
    metodo = getattr(valor, "isoformat", None)
    if callable(metodo):
        try:
            return metodo()
        except Exception:  # noqa: BLE001 - carimbo malformado não derruba a leitura
            return None
    return None


def nome_de_atleta(valor: Any) -> str:
    """Normaliza o nome para agrupamento.

    O campo é texto livre sem cadastro, então `"Gabriel"` e `"gabriel "`
    viriam como atletas diferentes. Colapsamos espaços e capitalização
    para a chave de agrupamento, preservando a grafia mais frequente na
    camada de apresentação.
    """
    return " ".join(str(valor or "").split())


def chave_de_atleta(valor: Any) -> str:
    return nome_de_atleta(valor).casefold()


def ordem_das_series(tempos_e_series: list[tuple[str, int]]) -> dict[tuple[str, int], int]:
    """Recalcula a ordem cronológica das séries dentro de um treino.

    Substitui o campo `serieGlobal` gravado no banco, que soma 6 fixo no
    T2 independentemente de quantas séries a rodada realmente teve. Aqui
    a ordem sai dos dados: ordenamos por (tempo, série) e numeramos a
    partir de 1. Para o formato padrão de 6 séries o resultado coincide
    com o campo antigo; para qualquer outro formato, corrige.
    """
    unicos = sorted(set(tempos_e_series), key=lambda ts: (ts[0], ts[1]))
    return {chave: indice for indice, chave in enumerate(unicos, start=1)}
