import { initializeApp } from 'https://www.gstatic.com/firebasejs/12.12.1/firebase-app.js';
import { getFirestore, doc, setDoc, deleteDoc, serverTimestamp } from 'https://www.gstatic.com/firebasejs/12.12.1/firebase-firestore.js';

// Firebase Web App — copie os valores em Firebase Console > Configurações do projeto > Seus apps (ícone Web).
const firebaseConfig = {
  apiKey: 'REPLACE_WITH_WEB_API_KEY',
  authDomain: 'kafutirocert0.firebaseapp.com',
  projectId: 'kafutirocert0',
  storageBucket: 'kafutirocert0.appspot.com',
  messagingSenderId: 'REPLACE_WITH_MESSAGING_SENDER_ID',
  appId: 'REPLACE_WITH_APP_ID',
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

window.firebase = {
  db,
  doc,
  setDoc,
  deleteDoc,
  serverTimestamp,
};

  const canvas = document.getElementById('alvo');
  const ctx = canvas.getContext('2d');
  const zoomRange = document.getElementById('zoomRange');
  const dpr = window.devicePixelRatio || 1;
  const ZOOM_BASE = 500;
  let nivelZoomAtual = zoomRange ? Number(zoomRange.value) / ZOOM_BASE : 1;
  let flechas = [];
  let flechasScore = [];
  let historicoLocal = {};
  let tipoAlvoSelecionado = 'Alvo Unitário';
  // Variáveis que controlam o limite do app (começam em 6 por padrão)
  let maxFlechas = 6;
  let maxSeries = 6;

  function getTreinoDocId() {
    const idTreino = document.getElementById('idTreino').value.trim();
    const tempo = document.getElementById('tempo').value;
    const serie = document.getElementById('serie').value;
    return `${idTreino}-${tempo}-S${serie}`;
  }

  function getTreinoDocRef(docId) {
    return window.firebase.doc(window.firebase.db, 'treinos', docId);
  }

  async function salvarTreinoNoFirebase(pacote) {
    const treinoId = getTreinoDocId();
    const tipoAlvo = tipoAlvoSelecionado || obterTipoAlvoAtivo();

    const treinoDados = {
      idTreino: document.getElementById('idTreino').value.trim(),
      dataTreino: document.getElementById('dataTreino').value,
      atleta: document.getElementById('atleta').value.trim(),
      tempo: document.getElementById('tempo').value,
      serie: document.getElementById('serie').value,
      serieGlobal: document.getElementById('tempo').value === 'T1' ? parseInt(document.getElementById('serie').value) : parseInt(document.getElementById('serie').value) + 6,
      v_vento: document.getElementById('v_vento').value || '0',
      d_vento: document.getElementById('d_vento').value,
      clima: document.getElementById('clima').value,
      tipo_alvo: tipoAlvo,
      tipoAlvo: tipoAlvo,
      createdAt: window.firebase.serverTimestamp()
    };

    await window.firebase.setDoc(getTreinoDocRef(treinoId), treinoDados);

    const promessas = pacote.map((disparo) => {
      const disparoRef = window.firebase.doc(window.firebase.db, 'treinos', treinoId, 'disparos', `F${disparo.flecha}`);
      return window.firebase.setDoc(disparoRef, {
        idDisparo: disparo.idDisparo,
        flecha: disparo.flecha,
        x: parseFloat(disparo.x.toString().replace(',', '.')),
        y: parseFloat(disparo.y.toString().replace(',', '.')),
        v_vento: disparo.v_vento,
        d_vento: disparo.d_vento,
        clima: disparo.clima,
        tipo_alvo: disparo.tipo_alvo,
        tipoAlvo: disparo.tipoAlvo
      });
    });

    await Promise.all(promessas);
    return `Treino ${treinoId} salvo no Firebase.`;
  }

  async function salvarScoreNoFirebase(pacoteScore) {
    const treinoId = getTreinoDocId();
    const tipoAlvo = pacoteScore.tipoAlvo || 'Alvo Unitário';

    await window.firebase.setDoc(getTreinoDocRef(treinoId), {
      distancia: pacoteScore.distancia,
      flechasString: pacoteScore.flechasString,
      total: pacoteScore.total,
      clima: pacoteScore.clima,
      v_vento: pacoteScore.v_vento,
      d_vento: pacoteScore.d_vento,
      tipo_alvo: tipoAlvo,
      tipoAlvo: tipoAlvo,
      updatedAt: window.firebase.serverTimestamp()
    }, { merge: true });

    return `Pontuação da série salva no Firebase.`;
  }

  async function excluirTreinoDoFirebase(chave) {
    const registro = historicoLocal[chave];
    const idTreino = registro?.idTreino || document.getElementById('idTreino').value.trim();
    if (!idTreino) {
      throw new Error('ID do treino não foi encontrado para exclusão.');
    }

    const treinoId = `${idTreino}-${chave}`;
    const disparos = registro?.alvo || [];
    const promessas = disparos.map((_, index) => {
      const disparoRef = window.firebase.doc(window.firebase.db, 'treinos', treinoId, 'disparos', `F${index + 1}`);
      return window.firebase.deleteDoc(disparoRef);
    });
    promessas.push(window.firebase.deleteDoc(getTreinoDocRef(treinoId)));
    await Promise.all(promessas);
    return `Série ${chave} excluída do Firebase.`;
  }

// Função que lê o que o atleta digitou e tranca as regras do treino
function atualizarRegrasFormato() {
  const inputSeries = document.getElementById('qtdSeries');
  const inputFlechas = document.getElementById('qtdFlechas');
  
  // Se os campos existirem, pega o valor, se não, usa 6 como padrão
  maxSeries = (inputSeries && inputSeries.value) ? parseInt(inputSeries.value) : 6;
  maxFlechas = (inputFlechas && inputFlechas.value) ? parseInt(inputFlechas.value) : 6;

  // Garante que não seja zero ou texto vazio
  if (isNaN(maxSeries) || maxSeries < 1) maxSeries = 6;
  if (isNaN(maxFlechas) || maxFlechas < 1) maxFlechas = 6;

  // Ajusta listas internas caso o usuário reduza o número de flechas
  if (flechas.length > maxFlechas) {
    flechas = flechas.slice(0, maxFlechas);
  }
  if (flechasScore.length > maxFlechas) {
    flechasScore = flechasScore.slice(0, maxFlechas);
  }
  
  console.log("Regras atualizadas: Séries:", maxSeries, "Flechas:", maxFlechas);
  
  // Atualiza os textos de ajuda na tela (0 / 6 vira 0 / 3)
  atualizarAlvoUI();
  atualizarScoreUI();
}

  function iniciarApp() {
    const idInput = document.getElementById('idTreino');
    if (idInput && !idInput.value) {
      idInput.value = gerarIDTreino();
    }

    const rect = canvas.getBoundingClientRect();
    const fallbackWidth = rect.width || canvas.offsetWidth || 400;
    const fallbackHeight = rect.height || canvas.offsetHeight || 400;

    canvas.width = fallbackWidth * dpr;
    canvas.height = fallbackHeight * dpr;
    canvas.style.width = '100%';
    canvas.style.height = 'auto';

    gerarNovoTreino(false);

    if (zoomRange) {
      zoomRange.addEventListener('input', function() {
        nivelZoomAtual = Number(this.value) / ZOOM_BASE;
        desenharAlvo();
      });
    }

    const qtdSeries = document.getElementById('qtdSeries');
    const qtdFlechas = document.getElementById('qtdFlechas');
    const tipoAlvo = document.getElementById('tipoAlvo');
    if (qtdSeries) {
      qtdSeries.addEventListener('change', () => {
        atualizarRegrasFormato();
      });
    }

    if (qtdFlechas) {
      qtdFlechas.addEventListener('change', () => {
        atualizarRegrasFormato();
        atualizarAlvoUI();
        atualizarScoreUI();
      });
    }

    if (tipoAlvo) {
      tipoAlvo.addEventListener('change', () => {
        desenharAlvo();
      });
    }

    verificarDistancia();
  }

  function gerarIDTreino() {
    const agora = new Date();
    const dia = String(agora.getDate()).padStart(2, '0');
    const mes = String(agora.getMonth() + 1).padStart(2, '0');
    const hora = String(agora.getHours()).padStart(2, '0');
    const minuto = String(agora.getMinutes()).padStart(2, '0');
    return `TR-${dia}${mes}-${hora}${minuto}`;
  }

  function obterTipoAlvoAtivo() {
    const distancia = document.getElementById('distancia').value;
    if (distancia !== '18m') {
      return 'Alvo Unitário';
    }

    const seletorAlvo = document.getElementById('tipoAlvo');
    if (seletorAlvo && seletorAlvo.value === 'indoor_18_triplo') {
      return 'Alvo Triplo';
    }

    return 'Alvo Único';
  }

  function obterDataAtualInput() {
    const agora = new Date();
    const ano = String(agora.getFullYear());
    const mes = String(agora.getMonth() + 1).padStart(2, '0');
    const dia = String(agora.getDate()).padStart(2, '0');
    return `${ano}-${mes}-${dia}`;
  }

  function gerarNovoTreino(limparAtleta = true) {
  // === 1. Gera um novo ID de treino e limpa apenas o atleta ===
  const idInput = document.getElementById('idTreino');
  if (idInput) {
    idInput.value = gerarIDTreino();
  }

  const atletaInput = document.getElementById('atleta');
  if (atletaInput && limparAtleta) {
    atletaInput.value = "";
  }

  document.getElementById('dataTreino').value = obterDataAtualInput();
  document.getElementById('tempo').value = "T1";
  document.getElementById('serie').value = "1";

  // === 2. Limpa o estado interno do treino ===
  flechas = [];
  flechasScore = [];
  historicoLocal = {};

  // === 3. Atualiza interfaces e desenho ===
  atualizarRegrasFormato();
  atualizarAlvoUI();
  atualizarScoreUI();
  atualizarListaLateral();

  // === 4. Volta para a tela de cadastro ===
  const setup = document.getElementById('setup-container');
  const training = document.getElementById('training-container');
  const header = document.getElementById('mini-header');

  if (setup) setup.style.display = 'flex';
  if (training) training.style.display = 'none';
  if (header) header.style.display = 'none';

  document.getElementById('moduloAlvo').style.display = 'none';
  document.getElementById('moduloScore').style.display = 'none';
  document.getElementById('status').innerText = "";
}

  function ativarTreino() {
    const setup = document.getElementById('setup-container');
    const header = document.getElementById('mini-header');
    const training = document.getElementById('training-container');

    if (!setup || !header || !training) return;

    const idTreino = document.getElementById('idTreino').value.trim();
    const atleta = document.getElementById('atleta').value.trim();
    const dataTreino = document.getElementById('dataTreino').value;
    const distancia = document.getElementById('distancia').value;

    if (!idTreino || !atleta) {
      alert('Preencha o ID do Treino e o nome do atleta antes de começar.');
      return;
    }

    if (distancia !== '18m') {
      tipoAlvoSelecionado = 'Alvo Unitário';
    } else {
      const seletorAlvo = document.getElementById('tipoAlvo');
      tipoAlvoSelecionado = (seletorAlvo && seletorAlvo.value === 'indoor_18_triplo') ? 'Alvo Triplo' : 'Alvo Único';
    }

    setup.style.display = 'none';
    header.style.display = 'flex';
    training.style.display = 'block';
    document.getElementById('moduloAlvo').style.display = 'block';
    document.getElementById('moduloScore').style.display = 'none';

    document.getElementById('headerIdTreino').innerText = `ID: ${idTreino}`;
    document.getElementById('headerAtleta').innerText = `Atleta: ${atleta}`;
    document.getElementById('headerDataTreino').innerText = `Data: ${dataTreino}`;
    desenharAlvo();

    document.getElementById('status').innerText = "Treino iniciado. Marque o alvo para começar.";

    verificarDistancia();
    const moduloAlvo = document.getElementById('moduloAlvo');
    if (moduloAlvo) moduloAlvo.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function verificarDistancia() {
    const distancia = document.getElementById('distancia').value;
    const seletorAlvo = document.getElementById('tipoAlvo');

    if (distancia === "18m") {
      seletorAlvo.style.display = "inline-block";
      if (seletorAlvo.value === "outdoor_122") {
        seletorAlvo.value = "indoor_18_single";
      }
    } else {
      seletorAlvo.style.display = "none";
      seletorAlvo.value = "outdoor_122";
    }

    desenharAlvo();
  }

  function validarAtleta() {
    const campoAtleta = document.getElementById('atleta');
    const nomeAtleta = campoAtleta.value.trim();

    if (nomeAtleta === "") {
      alert("Informe o nome do atleta antes de salvar a série.");
      campoAtleta.focus();
      campoAtleta.style.border = "2px solid #e74c3c";
      return false;
    }

    campoAtleta.style.border = "1px solid var(--border)";
    return true;
  }

  function retornarParaAlvo() {
    flechas = [];
    flechasScore = [];

    atualizarAlvoUI();
    atualizarScoreUI();

    document.getElementById('moduloAlvo').style.display = 'block';
    document.getElementById('moduloScore').style.display = 'none';

    const tempoAtual = document.getElementById('tempo').value;
    const serieAtual = document.getElementById('serie').value;

    document.getElementById('status').innerText = `Pronto para ${tempoAtual} - Série ${serieAtual}.`;
  }

  function avancarProximaSerie() {
  const tempoAtual = document.getElementById('tempo').value;
  const serieAtual = parseInt(document.getElementById('serie').value);

  // Se ainda não chegou no limite de séries do T1, avança uma série
  if (tempoAtual === "T1" && serieAtual < maxSeries) {
    document.getElementById('serie').value = String(serieAtual + 1);
    retornarParaAlvo();
    return;
  }

  // Se bateu no limite do T1, pula para o T2 - Série 1
  if (tempoAtual === "T1" && serieAtual === maxSeries) {
    document.getElementById('tempo').value = "T2";
    document.getElementById('serie').value = "1";
    alert(`T1 concluído! Iniciando T2 - Série 1.`);
    retornarParaAlvo();
    return;
  }

  // Se ainda não chegou no limite de séries do T2, avança uma série
  if (tempoAtual === "T2" && serieAtual < maxSeries) {
    document.getElementById('serie').value = String(serieAtual + 1);
    retornarParaAlvo();
    return;
  }

  // Se bateu no limite do T2, finaliza o treino!
  if (tempoAtual === "T2" && serieAtual === maxSeries) {
    setTimeout(() => {
      alert("Treino completo finalizado! O app será resetado para um novo treino.");
      gerarNovoTreino(true);
    }, 300);
  }
}

 

  function desenharAlvo() {
    const rect = canvas.getBoundingClientRect();
    const logicalWidth = rect.width || canvas.width / dpr || 400;
    const logicalHeight = rect.height || canvas.height / dpr || logicalWidth;

    if (rect.width > 0 && rect.height > 0) {
      canvas.width = logicalWidth * dpr;
      canvas.height = logicalHeight * dpr;
    }

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.webkitImageSmoothingEnabled = true;
    ctx.mozImageSmoothingEnabled = true;

    ctx.scale(dpr, dpr);

    const center = logicalWidth / 2;
    const ratio = logicalWidth / 300;
    const strokeWidth = 2 / nivelZoomAtual;
    const fineStrokeWidth = 1 / nivelZoomAtual;

    // Limpa o fundo do alvo em unidade de tela lógica
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, logicalWidth, logicalHeight);

    ctx.save();
    ctx.translate(center, center);
    ctx.scale(nivelZoomAtual, nivelZoomAtual);
    ctx.translate(-center, -center);

    const seletorAlvo = document.getElementById('tipoAlvo');
    const tipo = seletorAlvo ? seletorAlvo.value : "outdoor_122";

    if (tipo === "indoor_18_triplo") {
      const coordenadasCentros = [
        { x: 0, y: 95 },
        { x: 0, y: 0 },
        { x: 0, y: -95 }
      ];

      const aneisTriplo = [
        { raio: 45, cor: "#00B4E4", nivel: 6 },
        { raio: 36, cor: "#FF0000", nivel: 7 },
        { raio: 27, cor: "#FF0000", nivel: 8 },
        { raio: 18, cor: "#FFE500", nivel: 9 },
        { raio: 9, cor: "#FFE500", nivel: 10 },
        { raio: 4.5, cor: "#FFE500", nivel: 11 }
      ];

      coordenadasCentros.forEach(coord => {
        const xVis = center + (coord.x * ratio);
        const yVis = center - (coord.y * ratio);

        aneisTriplo.forEach((anel) => {
          ctx.beginPath();
          ctx.arc(xVis, yVis, anel.raio * ratio, 0, 2 * Math.PI);
          ctx.fillStyle = anel.cor;
          ctx.fill();
        });

        aneisTriplo.forEach((anel) => {
          ctx.beginPath();
          ctx.arc(xVis, yVis, anel.raio * ratio, 0, 2 * Math.PI);
          ctx.strokeStyle = 'black';
          ctx.lineWidth = strokeWidth;
          if (anel.nivel === 3 || anel.nivel === 4) {
            ctx.strokeStyle = 'white';
            ctx.lineWidth = fineStrokeWidth;
          }
          ctx.stroke();
        });

        const cruzTamanho = 3;
        ctx.beginPath();
        ctx.moveTo(xVis - cruzTamanho, yVis);
        ctx.lineTo(xVis + cruzTamanho, yVis);
        ctx.moveTo(xVis, yVis - cruzTamanho);
        ctx.lineTo(xVis, yVis + cruzTamanho);
        ctx.strokeStyle = "#000000";
        ctx.lineWidth = strokeWidth;
        ctx.stroke();
      });
    } else {
      const aneis = [
        { raio: 150, cor: "#FFFFFF", nivel: 1 },
        { raio: 135, cor: "#FFFFFF", nivel: 2 },
        { raio: 120, cor: "#202020", nivel: 3 },
        { raio: 105, cor: "#202020", nivel: 4 },
        { raio: 90, cor: "#00B4E4", nivel: 5 },
        { raio: 75, cor: "#00B4E4", nivel: 6 },
        { raio: 60, cor: "#FF0000", nivel: 7 },
        { raio: 45, cor: "#FF0000", nivel: 8 },
        { raio: 30, cor: "#FFE500", nivel: 9 },
        { raio: 15, cor: "#FFE500", nivel: 10 },
        { raio: 7.5, cor: "#FFE500", nivel: 11 }
      ];

      aneis.forEach((anel) => {
        ctx.beginPath();
        ctx.arc(center, center, anel.raio * ratio, 0, 2 * Math.PI);
        ctx.fillStyle = anel.cor;
        ctx.fill();
      });

      aneis.forEach((anel) => {
        ctx.beginPath();
        ctx.arc(center, center, anel.raio * ratio, 0, 2 * Math.PI);
        ctx.strokeStyle = 'black';
        ctx.lineWidth = strokeWidth;
        if (anel.nivel === 3 || anel.nivel === 4) {
          ctx.strokeStyle = 'white';
          ctx.lineWidth = fineStrokeWidth;
        }
        ctx.stroke();
      });

      const cruzTamanho = 3;
      ctx.beginPath();
      ctx.moveTo(center - cruzTamanho, center);
      ctx.lineTo(center + cruzTamanho, center);
      ctx.moveTo(center, center - cruzTamanho);
      ctx.lineTo(center, center + cruzTamanho);
      ctx.strokeStyle = "#000000";
      ctx.lineWidth = strokeWidth;
      ctx.stroke();
    }

    desenharFlechas(center, ratio);
    ctx.restore();
  }

// FUNÇÃO AUXILIAR: Desenha as flechas capturadas (sem código duplicado)
function desenharFlechas(center, ratio) {
  flechas.forEach((f, i) => {
    // Como xRel e yRel são sempre cartesianos absolutos da tela inteira, a conversão é única
    const xVis = center + (f.xRel * ratio);
    const yVis = center - (f.yRel * ratio);

    // Ponto pequeno (preciso)
    ctx.beginPath();
    ctx.arc(xVis, yVis, 2.5 * ratio, 0, 2 * Math.PI);
    ctx.fillStyle = "#2ecc71";
    ctx.fill();
    ctx.strokeStyle = "#000000";
    ctx.lineWidth = 1 * ratio;
    ctx.stroke();

    // Cruz de precisão (MOSTRA O CENTRO REAL)
    ctx.beginPath();
    ctx.moveTo(xVis - 6 * ratio, yVis);
    ctx.lineTo(xVis + 6 * ratio, yVis);
    ctx.moveTo(xVis, yVis - 6 * ratio);
    ctx.lineTo(xVis, yVis + 6 * ratio);
    ctx.strokeStyle = "#000000";
    ctx.lineWidth = 1 * ratio;
    ctx.stroke();

    // Número acima (não cobre o ponto)
    ctx.fillStyle = "#000000";
    ctx.font = `bold ${9 * ratio}px Arial`;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(i + 1, xVis, yVis - 8 * ratio);
  });
}


function getCanvasCoordinates(event) {
  const rect = canvas.getBoundingClientRect();
  const clientX = event.clientX !== undefined ? event.clientX : event.touches[0].clientX;
  const clientY = event.clientY !== undefined ? event.clientY : event.touches[0].clientY;
  const centro = rect.width / 2;

  let x = clientX - rect.left;
  let y = clientY - rect.top;

  x = centro + (x - centro) / nivelZoomAtual;
  y = centro + (y - centro) / nivelZoomAtual;
  return { x, y };
}

// ESCUTADOR DE CLIQUES NO ALVO
canvas.addEventListener('click', (e) => {
  if (flechas.length >= maxFlechas) return;

  const rect = canvas.getBoundingClientRect();
  const center = rect.width / 2;
  const ratio = rect.width / 300;
  const { x, y } = getCanvasCoordinates(e);

  const xRel = (x - center) / ratio;
  const yRel = (center - y) / ratio;

  flechas.push({ xRel, yRel });
  atualizarAlvoUI();
  desenharAlvo();
});

canvas.addEventListener('touchstart', (e) => {
  if (flechas.length >= maxFlechas) return;
  e.preventDefault();

  const rect = canvas.getBoundingClientRect();
  const center = rect.width / 2;
  const ratio = rect.width / 300;
  const { x, y } = getCanvasCoordinates(e);

  const xRel = (x - center) / ratio;
  const yRel = (center - y) / ratio;

  flechas.push({ xRel, yRel });
  atualizarAlvoUI();
  desenharAlvo();
});

 function atualizarAlvoUI() {
  // 1. Atualiza o texto do contador usando a variável maxFlechas
  const labelAlvo = document.getElementById('contadorAlvo');
  if (labelAlvo) {
    labelAlvo.innerText = `Flechas no Alvo: ${flechas.length} / ${maxFlechas}`;
  }

  // 2. Redesenha as bolinhas no alvo
  desenharAlvo();

  // 3. Mostra o botão "Enviar" apenas quando atingir o limite definido (maxFlechas)
  const btnEnviar = document.getElementById('btnEnviarAlvo');
  if (btnEnviar) {
    btnEnviar.style.display = flechas.length === maxFlechas ? "block" : "none";
    btnEnviar.disabled = false;
  }
}

  function addPonto(val) {
    if (flechasScore.length >= maxFlechas) return;
    flechasScore.push(val);
    atualizarScoreUI();
  }

  function atualizarScoreUI() {
    const container = document.getElementById('containerFlechasScore');
    if (!container) return;

    container.innerHTML = '';
    let totalScore = 0;

    for (let i = 0; i < maxFlechas; i++) {
      const box = document.createElement('div');
      box.className = 'ponto-box';
      box.style.border = '2px solid #ccc';
      box.style.padding = '10px';
      box.style.minWidth = '30px';
      box.style.textAlign = 'center';
      box.style.fontWeight = 'bold';
      box.style.background = '#f8f9fa';
      box.style.borderRadius = '8px';
      box.style.margin = '2px';

      const valor = flechasScore[i] || '';
      box.innerText = valor || '-';

      if (valor === 'X') {
        totalScore += 10;
      } else if (valor !== '' && valor !== 'M') {
        totalScore += parseInt(valor, 10) || 0;
      }

      container.appendChild(box);
    }

    document.getElementById('scoreTotal').innerText = `Total: ${totalScore}`;
    document.getElementById('contadorScore').innerText = `Pontos Inseridos: ${flechasScore.length} / ${maxFlechas}`;

    const btnEnviar = document.getElementById('btnEnviarScore');
    if (btnEnviar) {
      btnEnviar.style.display = flechasScore.length === maxFlechas ? 'block' : 'none';
      btnEnviar.disabled = false;
    }
  }

  function desfazer(tipo) {
    if (tipo === 'alvo') {
      flechas.pop();
      atualizarAlvoUI();
    } else {
      flechasScore.pop();
      atualizarScoreUI();
    }
  }

  function limparLocal(tipo) {
    if (tipo === 'alvo') {
      flechas = [];
      atualizarAlvoUI();
    } else {
      flechasScore = [];
      atualizarScoreUI();
    }
  }

async function enviarAlvo() {
    if (!validarAtleta()) return;

    if (flechas.length !== maxFlechas) {
      alert(`Marque as ${maxFlechas} flechas no alvo antes de confirmar.`);
      return;
    }

    document.getElementById('btnEnviarAlvo').disabled = true;
    document.getElementById('status').innerText = "Salvando Alvo no Firebase...";

    const idT = document.getElementById('idTreino').value;
    const t = document.getElementById('tempo').value;
    const s = document.getElementById('serie').value;

    const tipoAlvo = tipoAlvoSelecionado || obterTipoAlvoAtivo();
    const pacote = flechas.map((f, i) => ({
      idTreino: idT,
      dataTreino: document.getElementById('dataTreino').value,
      atleta: document.getElementById('atleta').value.trim(),
      tempo: t,
      serie: s,
      serieGlobal: t === "T1" ? parseInt(s) : parseInt(s) + 6,
      flecha: i + 1,
      idDisparo: `${idT}-${t}-S${s}-F${i + 1}`,
      x: f.xRel.toFixed(2).replace('.', ','),
      y: f.yRel.toFixed(2).replace('.', ','),
      v_vento: document.getElementById('v_vento').value || "0",
      d_vento: document.getElementById('d_vento').value,
      clima: document.getElementById('clima').value,
      tipo_alvo: tipoAlvo,
      tipoAlvo: tipoAlvo
    }));

    pacote.forEach(dadosParaEnviar => {
      if (!dadosParaEnviar.tipoAlvo) {
        dadosParaEnviar.tipoAlvo = 'Alvo Unitário';
      }
      if (!dadosParaEnviar.tipo_alvo) {
        dadosParaEnviar.tipo_alvo = dadosParaEnviar.tipoAlvo;
      }
    });

    console.log('Dados indo para o Excel:', pacote);

    try {
      const res = await salvarTreinoNoFirebase(pacote);
      document.getElementById('status').innerText = res + " Agora insira a pontuação.";
      document.getElementById('btnEnviarAlvo').disabled = false;
      document.getElementById('moduloAlvo').style.display = 'none';
      document.getElementById('moduloScore').style.display = 'block';
      limparLocal('score');
    } catch (err) {
      console.error(err);
      alert('Erro ao salvar no Firebase: ' + err.message);
      document.getElementById('btnEnviarAlvo').disabled = false;
      document.getElementById('status').innerText = 'Erro ao salvar no Firebase.';
    }
  }

  async function enviarScore() {
    if (!validarAtleta()) return;

    if (flechasScore.length !== maxFlechas) {
      alert(`Insira os ${maxFlechas} pontos da série antes de finalizar.`);
      return;
    }

    document.getElementById('btnEnviarScore').disabled = true;
    document.getElementById('status').innerText = "Finalizando Série...";

    let total = 0;
    flechasScore.forEach(v => {
      if (v === 'X') total += 10;
      else if (v !== 'M') total += parseInt(v);
    });

    const t = document.getElementById('tempo').value;
    const s = document.getElementById('serie').value;
    const chave = `${t}-S${s}`;

    const tipoAlvo = tipoAlvoSelecionado || obterTipoAlvoAtivo();
    const pacoteScore = {
      idTreino: document.getElementById('idTreino').value,
      dataTreino: document.getElementById('dataTreino').value,
      atleta: document.getElementById('atleta').value.trim(),
      distancia: document.getElementById('distancia').value,
      tempo: t,
      serie: s,
      flechasString: flechasScore.join(" "),
      total: total,
      clima: document.getElementById('clima').value,
      v_vento: document.getElementById('v_vento').value || "0",
      d_vento: document.getElementById('d_vento').value,
      tipo_alvo: tipoAlvo,
      tipoAlvo: tipoAlvo
    };

    if (!pacoteScore.tipoAlvo) {
      pacoteScore.tipoAlvo = 'Alvo Unitário';
    }
    if (!pacoteScore.tipo_alvo) {
      pacoteScore.tipo_alvo = pacoteScore.tipoAlvo;
    }

    console.log('Dados indo para o Firebase:', pacoteScore);

    try {
      const res = await salvarScoreNoFirebase(pacoteScore);
      historicoLocal[chave] = {
        idTreino: document.getElementById('idTreino').value.trim(),
        alvo: [...flechas],
        score: [...flechasScore]
      };

      atualizarListaLateral();

      document.getElementById('status').innerText = `${res} ${chave} concluída com sucesso.`;
      document.getElementById('btnEnviarScore').disabled = false;

      avancarProximaSerie();
    } catch (err) {
      console.error(err);
      alert('Erro ao salvar o score no Firebase: ' + err.message);
      document.getElementById('btnEnviarScore').disabled = false;
      document.getElementById('status').innerText = 'Erro ao salvar o score no Firebase.';
    }
  }

  function atualizarListaLateral() {
    const div = document.getElementById('listaSeries');
    div.innerHTML = "";

    Object.keys(historicoLocal).forEach(chave => {
      div.innerHTML += `
        <div class="serie-item">
          <button class="btn-revisar" onclick="alert('Série ${chave} enviada! Edição via web em breve.')">✔️ ${chave}</button>
          <button class="btn-del-mini" onclick="excluirTotal('${chave}')">X</button>
        </div>`;
    });
  }

  async function excluirTotal(chave) {
    if (!confirm("Excluir esta série inteira do Firebase?")) return;

    document.getElementById('status').innerText = "Deletando do Firebase...";

    try {
      const res = await excluirTreinoDoFirebase(chave);
      delete historicoLocal[chave];
      atualizarListaLateral();
      alert(res);
      document.getElementById('status').innerText = "";
    } catch (err) {
      console.error(err);
      alert('Erro ao excluir do Firebase: ' + err.message);
      document.getElementById('status').innerText = "Erro ao excluir do Firebase.";
    }
  }

window.ativarTreino = ativarTreino;
window.verificarDistancia = verificarDistancia;
window.desenharAlvo = desenharAlvo;
window.desfazer = desfazer;
window.limparLocal = limparLocal;
window.enviarAlvo = enviarAlvo;
window.addPonto = addPonto;
window.enviarScore = enviarScore;
window.excluirTotal = excluirTotal;
window.iniciarApp = iniciarApp;
window.gerarNovoTreino = gerarNovoTreino;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', iniciarApp);
} else {
  iniciarApp();
}