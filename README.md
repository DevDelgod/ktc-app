# 🎯 Kafu Tiro Certo — Performance App

Plataforma de registro e análise de performance em tiro com arco. O atleta
marca cada flecha no alvo, registra a pontuação e analisa o próprio
desempenho **dentro do próprio aplicativo** — precisão, agrupamento,
tendência, consistência e evolução ao longo do tempo.

O Power BI não faz mais parte da arquitetura.

---

## Arquitetura

```text
                     ┌──────────────────┐
                     │     ATLETA       │
                     └────────┬─────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   ┌──────────────────────┐        ┌──────────────────────┐
   │  Registro de treino  │        │  KTC Performance     │
   │  index.html          │        │  dashboard.html      │
   │  Canvas + teclado    │        │  Métricas + gráficos │
   └──────────┬───────────┘        └──────────┬───────────┘
              │ escreve                       │ lê análises
              │ (Firebase Web SDK)            │ (HTTP)
              ▼                               ▼
   ┌──────────────────────┐        ┌──────────────────────┐
   │      FIRESTORE       │◄───────┤   FastAPI + Pandas   │
   │  treinos/{série}     │  Admin │   Camada analítica   │
   │    └ disparos/F1..Fn │   SDK  │   NumPy              │
   └──────────────────────┘        └──────────────────────┘
```

O Firestore continua sendo a **fonte única dos dados**. O Python calcula
tudo o que é **derivado** — média, desvio, dispersão, agrupamento — e
nada disso é gravado de volta no banco.

### Por que FastAPI

Validação de parâmetros por tipo (datas e filtros chegam conferidos),
documentação OpenAPI automática em `/api/docs`, e execução assíncrona —
o dashboard dispara várias consultas em paralelo. Flask exigiria camada
extra para o mesmo resultado.

---

## Estrutura

```text
ktc-app/
├── frontend/
│   ├── index.html              registro de treino (protegido por login)
│   ├── dashboard.html          análise de performance (protegido por login)
│   ├── login.html              tela de login
│   ├── css/
│   │   ├── base.css            tokens e identidade visual
│   │   ├── app.css             tela de registro
│   │   ├── dashboard.css       tela de análise
│   │   └── login.css           tela de login
│   └── js/
│       ├── config.js           configuração compartilhada
│       ├── firebase-config.js  credenciais Web  (NÃO versionado)
│       ├── firebase-init.js    inicialização única do Firebase App
│       ├── firebase.js         escrita no Firestore
│       ├── auth.js             login, logout, ID Token
│       ├── auth-guard.js       bloqueia a página até confirmar sessão
│       ├── login.js            controlador da tela de login
│       ├── targets.js          geometria dos alvos
│       ├── canvas.js           desenho e captura de coordenadas
│       ├── training.js         estado do treino e máquina de séries
│       ├── scoring.js          pontuação e conferência
│       ├── registro.js         controlador da tela de registro
│       ├── api.js              cliente da API analítica (anexa o ID Token)
│       ├── charts.js           gráficos (Chart.js)
│       ├── target-plot.js      dispersão desenhada sobre o alvo
│       └── dashboard.js        controlador do dashboard
│
└── backend/
    ├── app/
    │   ├── main.py             aplicação FastAPI
    │   ├── config.py           variáveis de ambiente
    │   ├── cache.py            cache de leitura com TTL
    │   ├── auth.py             verificação de ID Token do Firebase
    │   ├── api/                rotas e dependências (auth aplicada aqui)
    │   ├── models/domain.py    Treino → Série → Disparo
    │   ├── services/           Firestore, normalização, orquestração
    │   ├── analytics/          geometria e métricas
    │   └── firebase/client.py  Admin SDK
    ├── tools/servidor_demo.py  servidor com dados sintéticos (dev)
    ├── requirements.txt
    └── tests/                  175 testes
```

---

## Instalação

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
```

Crie o `.env` a partir do modelo:

```bash
cp .env.example .env
```

E baixe a chave da conta de serviço em **Firebase Console → Configurações
do projeto → Contas de serviço → Gerar nova chave privada**. Salve como
`backend/chave-firebase.json` — o `.gitignore` já protege esse arquivo.

### 2. Frontend

```bash
cp frontend/js/firebase-config.example.js frontend/js/firebase-config.js
```

Preencha com os valores de **Firebase Console → Configurações do projeto →
Seus apps → ícone Web**. Esse arquivo também não é versionado.

### 3. Executar

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

O backend serve a API **e** o frontend:

| Endereço | O quê |
|---|---|
| <http://localhost:8000/> | Registro de treino |
| <http://localhost:8000/dashboard.html> | Análise de performance |
| <http://localhost:8000/api/docs> | Documentação da API |

Para inspecionar a interface sem credenciais, existe um servidor com
dados sintéticos — **ferramenta de desenvolvimento, não parte do
aplicativo**:

```bash
python backend/tools/servidor_demo.py
```

---

## Estrutura dos dados

A coleção chama-se `treinos`, mas **cada documento é uma série**. O ID é
montado como `{idTreino}-{tempo}-S{serie}`, por exemplo
`TR-3108-1605-T1-S1`. Uma sessão de treino é o conjunto de séries que
compartilham o mesmo `idTreino` — o backend reconstrói essa hierarquia em
memória, sem alterar nada no banco.

```text
treinos/TR-3108-1605-T1-S1
   ├─ idTreino, atleta, dataTreino, tempo, serie
   ├─ distancia, clima, v_vento, d_vento, tipoAlvo
   ├─ flechasString ("X 10 9 9 8 M"), total
   ├─ createdAt, updatedAt
   └─ disparos/
        ├─ F1 { flecha, x, y, score, ... }
        └─ F2 ...
```

### Sistema de coordenadas

Preservado exatamente como no aplicativo original:

```text
ratio = larguraDoCanvasPx / 300
x = (px - centro) / ratio
y = (centro - py) / ratio        ← Y positivo para CIMA
```

- Origem no **centro do alvo**; unidade = 1/300 da largura do alvo.
- O anel externo do alvo simples tem raio 150 — o alvo ocupa a largura
  inteira do espaço lógico.
- **Atenção:** no alvo triplo o centro do alvo **não** é (0,0). Há três
  faces, em (0, +95), (0, 0) e (0, −95). Toda distância ao centro usa a
  face mais próxima.

### Tipos de alvo

| Nome gravado | Geometria | Anéis | Quando |
|---|---|---|---|
| `Alvo Unitário` | simples | 11 (raios 150→7,5) | distância ≠ 18m |
| `Alvo Único` | simples — **a mesma** | 11 | 18m, face única |
| `Alvo Triplo` | 3 faces | 6 por face (45→4,5) | 18m, face tripla |

`Unitário` e `Único` são strings diferentes para o mesmo alvo. O backend
normaliza as duas na família `simples` na leitura, sem reescrever nada.

---

## Endpoints

| Método | Rota | Devolve |
|---|---|---|
| GET | `/api/health` | Estado do serviço e do cache |
| GET | `/api/filters` | Opções de filtro coerentes entre si |
| GET | `/api/athletes` | Atletas com dados registrados |
| GET | `/api/athletes/{nome}/trainings` | Treinos de um atleta |
| GET | `/api/trainings` | Lista de treinos filtrada |
| GET | `/api/trainings/{id}` | Cabeçalho de um treino |
| GET | `/api/trainings/{id}/analytics` | Pacote analítico completo |
| GET | `/api/trainings/{id}/shots` | Disparos + geometria do alvo |
| GET | `/api/analytics/history` | Evolução ao longo do tempo |
| GET | `/api/analytics/comparison?ids=a,b` | Comparação entre treinos |
| GET | `/api/targets/{tipo}` | Geometria de um tipo de alvo |
| POST | `/api/cache/invalidar` | Força releitura do Firestore |

Filtros aceitos em query: `atleta`, `data_inicio`, `data_fim`,
`tipo_alvo`, `familia_alvo`, `distancia`, `tempo`, `serie`.

---

## Métricas e suas definições

Todas as distâncias saem em **unidades do alvo**; onde faz sentido, a
conversão para centímetros vem junto, com sufixo `_cm`.

A análise de dispersão trabalha com o deslocamento de cada disparo em
relação ao centro da **sua própria face** (`dx = x − cx`, `dy = y − cy`).
Esse é o espaço comum em que faces diferentes podem ser comparadas —
usar (x, y) absoluto no alvo triplo mediria a distância entre as faces,
não a dispersão do atleta.

### Pontuação

| Métrica | Definição |
|---|---|
| `total` | Soma dos pontos. X = 10, M = 0 |
| `media` | total ÷ flechas pontuadas |
| `mediana` | percentil 50 dos pontos por flecha |
| `desvio_padrao` | desvio **amostral** (ddof = 1) |
| `aproveitamento` | total ÷ (flechas × 10) |

### Precisão — onde as flechas estão em relação ao centro

| Métrica | Definição |
|---|---|
| `distancia_media_centro` | média de `√(dx² + dy²)` |
| `distancia_maxima_centro` | pior flecha |

### Agrupamento — quão juntas estão

| Métrica | Definição |
|---|---|
| `centro_grupo_x/y` | `média(dx)`, `média(dy)` |
| `desvio_x`, `desvio_y` | desvio amostral de dx e dy |
| `dispersao_radial` | `√(var(dx) + var(dy))` — raiz do traço da covariância |
| `raio_medio_grupo` | distância média ao **centro do grupo** |
| `raio_95_grupo` | percentil 95 dos raios do grupo |
| `extreme_spread` | maior distância entre duas flechas |

Precisão e agrupamento são coisas distintas: um grupo pode ser apertado
(agrupamento bom) e estar longe do centro (precisão ruim).

### Tendência — o grupo está deslocado para algum lado?

| Métrica | Definição |
|---|---|
| `vies_modulo` | `√(média(dx)² + média(dy)²)` |
| `vies_angulo` | `atan2(média(dy), média(dx))` em graus |
| `vies_direcao` | rótulo cardinal mais próximo |

### Consistência — o desempenho varia entre séries?

| Métrica | Definição |
|---|---|
| `desvio_entre_series` | desvio amostral dos totais por série |
| `amplitude` | maior total − menor total |
| `coeficiente_variacao` | desvio ÷ média (adimensional) |

### Qualidade do dado

O aplicativo nunca cruzou a posição marcada com o ponto digitado — são
duas entradas independentes. Com a geometria dos anéis disponível, o
backend deriva a pontuação a partir de (x, y) e compara:

| Métrica | Significado |
|---|---|
| `concordancia` | fração de flechas em que digitado = marcado |
| `divergencias` | quantas não batem |
| `fora_do_alvo` | marcadas além do anel externo |

**Nada é corrigido automaticamente.** Concordância baixa indica marcação
imprecisa, zoom mal ajustado ou digitação trocada.

---

## Compatibilidade com dados históricos

Treinos antigos e novos passam pelo **mesmo pipeline**. Nenhum documento
foi migrado ou reescrito; as inconsistências conhecidas são resolvidas na
leitura:

| Situação no banco | Tratamento |
|---|---|
| Disparo sem pontuação | Pareado com a posição correspondente em `flechasString` |
| `serieGlobal` somando 6 fixo no T2 | Ordem recalculada a partir dos dados |
| `Alvo Único` vs `Alvo Unitário` | Colapsados na família `simples` |
| `v_vento`, `serie` como string | Convertidos para número |
| `x`/`y` com vírgula decimal | Aceitos nas duas formas |
| Série sem `total` | Fica sem pontuação, **não** vira zero |

### A ligação flecha ↔ pontuação

Nos registros antigos essa ligação só existia por posição: a n-ésima
flecha marcada com a n-ésima tecla digitada. O backend reconstrói esse
par e declara a origem em `origem_score`:

- `campo_score` — gravado no próprio disparo (registros novos)
- `flechas_string` — inferido por posição (histórico)
- `ausente` — série não finalizada

A partir desta versão o aplicativo grava `score` em cada disparo, o que
torna a ligação explícita sem quebrar a leitura do que já existe.

---

## Testes

```bash
cd backend
pytest -q
```

175 testes cobrindo geometria e determinismo da pontuação, normalização
do formato legado, métricas conferidas contra valores calculados à mão,
compatibilidade com dados históricos e respostas dos endpoints.

---

## Segurança

- Credenciais **nunca** vão para o Git: `chave-firebase.json`, `.env` e
  `frontend/js/firebase-config.js` estão no `.gitignore`.
- Em produção, prefira **Application Default Credentials** (Cloud Run,
  GCE) a um arquivo de chave — deixe `FIREBASE_CREDENTIALS` vazio.
- O CORS é restrito por `CORS_ORIGINS`; em produção liste apenas o
  domínio do frontend.
- As chaves do Firebase Web são públicas por natureza — elas identificam
  o projeto, não autorizam acesso. **Quem protege o banco são as Regras
  de Segurança do Firestore.**

### Autenticação

O app usa **Firebase Authentication (e-mail/senha)**. Ambas as telas —
registro e dashboard — exigem login; sem sessão válida, o usuário é
redirecionado para `login.html`.

```text
Navegador                          Backend
   │                                  │
   │ login com e-mail/senha           │
   ├──────────────► Firebase Auth     │
   │ ID Token                         │
   │◄──────────────                   │
   │                                  │
   │ Authorization: Bearer <token>    │
   ├─────────────────────────────────►│ firebase_admin.auth.verify_id_token()
   │                                  │ (verificação criptográfica, sem round-trip)
```

- `frontend/js/auth.js` — login, logout, obtenção do ID Token.
- `frontend/js/auth-guard.js` — bloqueia cada página até confirmar sessão.
- `backend/app/auth.py` + `app/api/deps.py` — verifica o token em toda
  rota, exceto `/api/health` (não expõe dado de atleta, fica público
  para monitoramento).

**Habilitando pela primeira vez:** o Firebase Authentication precisa ser
ativado uma vez pelo Console — não existe API para provisionar isso do
zero num projeto que nunca usou Auth.

1. Firebase Console → **Authentication** → **Get started**
2. Aba **Sign-in method** → habilite **E-mail/senha**
3. Aba **Users** → **Add user**, um por pessoa que vai usar o app

Sem esse passo, o login falha com uma mensagem clara
(`auth/configuration-not-found`) em vez de travar — a aplicação
detecta e explica, mas não substitui a ativação manual.

### Regras do Firestore

Depois que o Authentication estiver ativo e as contas criadas, atualize
as regras para exigir login (Console → Firestore Database → Regras):

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if request.auth != null;
    }
  }
}
```

As regras padrão de início rápido do Firebase **expiram 30 dias após a
criação do projeto** e passam a bloquear tudo — é um erro comum de
projetos novos. A regra acima não expira.

---

## Deploy

O backend serve a API e o frontend no mesmo processo, então uma única
instância basta:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Variáveis de ambiente: `FIREBASE_PROJECT_ID`, `CORS_ORIGINS`,
`CACHE_TTL`, `AMBIENTE=producao`. Com `SERVE_FRONTEND=0` o backend serve
apenas a API, para quando o frontend estiver numa CDN.

---

Propriedade intelectual de Gabriel Delgado Ribeiro — Kafu Tiro Certo © 2026
