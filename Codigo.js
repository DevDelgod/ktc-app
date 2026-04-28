function getConfig(nome) {
  const valor = PropertiesService.getScriptProperties().getProperty(nome);

  if (!valor) {
    throw new Error("Config não encontrada: " + nome);
  }

  return valor;
}

const GRAPH_FILE_ID = getConfig("GRAPH_FILE_ID");
const TABELA_DISPERSAO = "Tabela1"; // Página1
const TABELA_TREINOS = "Tabela2";   // Treinos
const CLIENT_SECRET = getConfig("CLIENT_SECRET");
const REFRESH_TOKEN = getConfig("REFRESH_TOKEN");

function doGet() {
  return HtmlService.createHtmlOutputFromFile("Index")
    .setTitle("Kafu Tiro Certo")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag("viewport", "width=device-width, initial-scale=1");
}

function gerarAccessToken() {
  const TENANT_ID = getConfig("TENANT_ID");
  const CLIENT_ID = getConfig("CLIENT_ID");
  const CLIENT_SECRET = getConfig("CLIENT_SECRET");
  const REFRESH_TOKEN = getConfig("REFRESH_TOKEN");

  const url = `https://login.microsoftonline.com/${TENANT_ID}/oauth2/v2.0/token`;

  const payload = {
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    refresh_token: REFRESH_TOKEN,
    grant_type: "refresh_token",
    scope: "https://graph.microsoft.com/Files.ReadWrite offline_access User.Read"
  };

  const response = UrlFetchApp.fetch(url, {
    method: "post",
    payload: payload,
    muteHttpExceptions: true
  });

  const code = response.getResponseCode();
  const text = response.getContentText();

  if (code < 200 || code >= 300) {
    throw new Error("Erro ao gerar token: " + text);
  }

  const data = JSON.parse(text);
  return data.access_token;
}

function graphFetch(url, method, body) {
  const token = gerarAccessToken();

  const options = {
    method: method,
    contentType: "application/json",
    headers: {
      Authorization: "Bearer " + token
    },
    muteHttpExceptions: true
  };

  if (body) {
    options.payload = JSON.stringify(body);
  }

  const response = UrlFetchApp.fetch(url, options);
  const code = response.getResponseCode();
  const text = response.getContentText();

  Logger.log(code);
  Logger.log(text);

  if (code < 200 || code >= 300) {
    throw new Error("Erro Graph " + code + ": " + text);
  }

  return text ? JSON.parse(text) : null;
}

function adicionarLinhasTabela(nomeTabela, linhas) {
  const url =
    `https://graph.microsoft.com/v1.0/me/drive/items/${GRAPH_FILE_ID}/workbook/tables/${nomeTabela}/rows/add`;

  return graphFetch(url, "post", {
    values: linhas
  });
}

// SALVAR COORDENADAS - Página1 / Tabela1
function salvarDados(pacoteDeDados) {
  try {
    if (!pacoteDeDados || pacoteDeDados.length === 0) {
      return "Nenhum dado de alvo para salvar.";
    }

    const linhas = pacoteDeDados.map(function(dados) {
      return [
        dados.idTreino,
        dados.dataTreino,
        dados.atleta,
        dados.tempo,
        dados.serie,
        dados.serieGlobal,
        dados.flecha,
        dados.idDisparo,
        dados.x,
        dados.y,
        dados.v_vento,
        dados.d_vento,
        dados.clima,
        dados.tipo_alvo
      ];
    });

    adicionarLinhasTabela(TABELA_DISPERSAO, linhas);

    return "Alvo salvo!";
  } catch (e) {
    return "Erro ao salvar alvo: " + e.message;
  }
}

// SALVAR SCORECARD - Treinos / Tabela2
function salvarScorecard(pacote) {
  try {
    const linha = [[
      pacote.idTreino,
      pacote.dataTreino,
      pacote.atleta,
      pacote.tempo,
      pacote.serie,
      pacote.total,
      pacote.flechasString,
      pacote.clima,
      pacote.distancia,
      pacote.v_vento,
      pacote.d_vento,
      pacote.tipo_alvo
    ]];

    adicionarLinhasTabela(TABELA_TREINOS, linha);

    return "Pontuação salva!";
  } catch (e) {
    return "Erro ao salvar pontuação: " + e.message;
  }
}

// TESTE RÁPIDO DO TOKEN AUTOMÁTICO
function testarTokenAutomatico() {
  const token = gerarAccessToken();

  const url = "https://graph.microsoft.com/v1.0/me";

  const response = UrlFetchApp.fetch(url, {
    method: "get",
    headers: {
      Authorization: "Bearer " + token
    },
    muteHttpExceptions: true
  });

  Logger.log(response.getResponseCode());
  Logger.log(response.getContentText());
}

// TESTE DE ESCRITA EM TREINOS
function inserirTreinoTesteAutomatico() {
  adicionarLinhasTabela(TABELA_TREINOS, [[
    "T1000",
    "24/04/2026",
    "Gabriel Delgado",
    "T1",
    1,
    60,
    "10 10 10 10 10 10",
    "Sol",
    "70m",
    5,
    "Norte",
    "Alvo_select"
  ]]);
}

// TESTE DE ESCRITA EM PÁGINA1
function inserirDisparoTesteAutomatico() {
  adicionarLinhasTabela(TABELA_DISPERSAO, [[
    "T1000",
    "24/04/2026",
    "Gabriel Delgado",
    "T1",
    1,
    1,
    1,
    "T1000-S1-F1",
    0,
    0,
    5,
    "Norte",
    "Sol"
  ]]);

// Colunas na planilha do excel 
var linha = [
  pacote.idTreino,
  pacote.dataTreino,
  pacote.atleta,
  pacote.tempo, // (Sessão)
  pacote.serie,
  pacote.total, // (Pontos_Serie)
  pacote.flechasString,
  pacote.clima,
  pacote.distancia,
  pacote.v_vento,
  pacote.d_vento,
  pacote.tipo_alvo    // <--- Tipo de alvo selecionado 18/40/60/70
];

// 2. O COMANDO QUE SALVA NA PLANILHA FICA LOGO ABAIXO DA VARIÁVEL
  adicionarLinhasTabela(TABELA_TREINOS, linha); 
  
  return "Treino salvo com sucesso!";

} // <--- 3

// EXCLUSÃO FÍSICA DESATIVADA POR SEGURANÇA
function excluirSeriePlanilha(idTreino, tempo, serie) {
  return "Exclusão física temporariamente desativada. Inserção no Excel está funcionando normalmente.";
}