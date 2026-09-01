# CLAUDE.md — contexto para trabalhar neste repositório

Kafu Tiro Certo: registro de treinos de tiro com arco + plataforma
própria de análise de performance. Leia o `README.md` para a arquitetura
geral; este arquivo registra o que **não** é óbvio pelo código.

---

## O que não se muda sem entender a consequência

### 1. A matemática das coordenadas

```text
ratio = larguraDoCanvasPx / 300
x = (px - centro) / ratio
y = (centro - py) / ratio        ← Y positivo para CIMA
```

Vive em `frontend/js/canvas.js` (captura e desenho) e é espelhada em
`backend/app/analytics/geometry.py`. **Todo o histórico já gravado foi
capturado nessa escala.** Alterar origem, unidade, orientação ou o
divisor 300 invalida silenciosamente os dados antigos — sem erro, sem
aviso, sem como detectar depois.

O centro vertical usa `larguraLogica / 2`, não a altura. É proposital:
desenho e captura usam a mesma convenção, então as coordenadas ficam
corretas mesmo se o elemento não for perfeitamente quadrado.

### 2. Os raios e níveis dos alvos

`ANEIS_SIMPLES` e `ANEIS_TRIPLO` em `frontend/js/targets.js`, e as
constantes equivalentes em `backend/app/analytics/geometry.py`. Os dois
lados precisam concordar. O `nivel` **é** a pontuação; nível 11 é o X e
vale 10.

Relação que o código não comenta mas que se verifica número a número: o
alvo triplo é o miolo do simples reduzido a exatamente 60%.

### 3. O centro do alvo nem sempre é (0,0)

No alvo triplo há **três faces**, em (0, +95), (0, 0) e (0, −95).
Qualquer cálculo de distância ao centro precisa usar a face mais próxima.
Usar a origem produziria uma "dispersão" que na verdade mede a distância
entre as faces. Há teste cobrindo isso.

### 4. O formato dos documentos no Firestore

ID da série: `{idTreino}-{tempo}-S{serie}`. ID do disparo: `F{n}`, com
`n` começando em 1. São chaves determinísticas — o app não usa IDs
automáticos, e a exclusão remonta o mesmo ID por outro caminho.

**A coleção `treinos` guarda séries, não treinos.** Um treino é o
conjunto de séries com o mesmo `idTreino`; o backend reconstrói essa
hierarquia em memória (`app/models/domain.py`). Isso é histórico, não
escolha nova — mudar exigiria migrar todos os dados.

### 5. Escrita com merge

`salvarAlvo` e `salvarPontuacao` usam `{ merge: true }`. A versão
original do app usava `setDoc` **sem** merge na gravação do alvo, e
reconfirmar o alvo de uma série já pontuada apagava `total`,
`distancia` e `flechasString`. Não remova o merge.

---

## Decisões de arquitetura e o porquê

### Toda estatística fica no Python

O frontend cuida de interação e visualização; média, desvio, dispersão e
agrupamento vêm prontos da API. Se você se pegar calculando estatística
em JavaScript, provavelmente está no lugar errado — a exceção é a
conferência ao vivo do teclado (`scoring.js`), que precisa responder a
cada tecla sem ida ao servidor.

### Normalização acontece em leitura, nunca em escrita

`backend/app/services/normalize.py`. Nenhum documento antigo é
reescrito. As três inconsistências conhecidas do formato legado
(`serieGlobal` com +6 fixo, `Alvo Único`/`Alvo Unitário`, campos
numéricos como string) são resolvidas na entrada do pipeline. Isso é o
que mantém dado antigo e novo no mesmo caminho.

### A ligação flecha ↔ pontuação tem três origens

Verificável no campo `origem_score` de cada disparo:

- `campo_score` — gravado no disparo (registros novos, formato atual)
- `flechas_string` — inferido pela posição na string (histórico)
- `ausente` — série confirmada no alvo mas nunca finalizada

Disparo sem pontuação fica com `pontos = None`, **não** zero. Contar
como zero diluiria médias e inflaria contagens de erro.

### `score_geometrico` é conferência, não correção

O app registra a posição e a pontuação como duas entradas independentes,
e nunca as cruzou. O backend deriva a pontuação a partir de (x, y) e
compara — isso vira a métrica `concordancia`. **Nunca sobrescreva o
valor digitado pelo derivado.** O atleta é a autoridade sobre o que ele
marcou; a divergência é um sinal de qualidade do dado.

### O cache existe para não reler a base a cada interação

`app/cache.py`, TTL configurável. O dashboard dispara várias consultas
que derivam do mesmo conjunto de treinos. Depois de gravar, o frontend
chama `POST /api/cache/invalidar` para a análise aparecer na hora.

### Gráficos: biblioteca para o comum, Canvas para o alvo

Chart.js cobre barras e linhas. O gráfico de dispersão sobre o alvo é
desenhado à mão em `target-plot.js` porque nenhuma biblioteca genérica
sabe desenhar um alvo triplo com as três faces nos lugares certos, com
os raios reais.

**A geometria que vem da API traz `raio` e `nivel`, mas não `cor`** —
cor é apresentação. `comCores()` em `targets.js` preenche antes de
desenhar. Sem essa etapa, `fillStyle` recebe `undefined` e todos os
anéis saem brancos. Já aconteceu.

---

## Armadilhas conhecidas

- **Canvas em contêiner oculto mede zero.** Chart.js congela 300×150 no
  momento da criação. Revele o contêiner **antes** de criar o gráfico.
- **Reescrever `style.height` a cada desenho pode virar laço** com o
  aparecimento da barra de rolagem. `target-plot.js` só escreve quando o
  valor muda, e agenda o redesenho por `requestAnimationFrame`.
- **Nome de parâmetro de rota não pode colidir com filtro de query** no
  FastAPI. Por isso `/athletes/{nome}/trainings` usa `nome`, e não
  `atleta`.
- **`to_dict()` do Firestore não traz subcoleções.** Era esse o motivo
  de o ETL antigo nunca exportar as coordenadas. A leitura dos disparos
  usa *collection group query*, uma consulta só para todos.
- **Nome de atleta é texto livre**, sem cadastro. O agrupamento usa
  chave normalizada (sem caixa nem espaço extra); a grafia exibida é a
  mais frequente.
- **`initializeApp()` só pode rodar uma vez.** Firestore (`firebase.js`)
  e Auth (`auth.js`) compartilham a mesma instância de app, exportada
  por `firebase-init.js`. Uma segunda chamada a `initializeApp()` com o
  app padrão lança `Firebase App named '[DEFAULT]' already exists`.
- **A config do Firebase Web não valida sozinha.** Com `apiKey` vazia ou
  `projectId` de exemplo, `initializeApp`/`getFirestore` não lançam erro
  — o SDK só falha na primeira operação real, e falha travando para
  sempre, sem rejeitar a Promise nem tentar nenhuma requisição de rede.
  É por isso que `configuracaoAusente()` existe e é checada antes de
  qualquer `setDoc`/login.
- **As regras padrão de início rápido do Firestore expiram em 30 dias**
  e passam a bloquear tudo — sem aviso na aplicação, só
  `permission-denied`. Qualquer projeto novo do Firebase nasce com essa
  bomba-relógio; confira a data em Firestore Database → Regras.

---

## Ao mexer aqui

- Rode os testes: `cd backend && pytest -q`. São 175.
- Métrica nova precisa de definição matemática documentada junto da
  função, e de teste conferindo contra valor calculado à mão — não
  contra a saída da própria implementação.
- Não invente métrica que não responda a uma pergunta de performance
  real (precisão, consistência, tendência, evolução, estabilidade).
- Dado derivado se calcula, não se grava. O Firestore guarda o original:
  x, y, score, série, treino, atleta, timestamp.
- Para inspecionar a interface sem credenciais:
  `python backend/tools/servidor_demo.py`. É ferramenta de
  desenvolvimento — **não** deixe dado sintético vazar para o produto.
