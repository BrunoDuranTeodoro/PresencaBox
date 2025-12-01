// script.js

const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const resultDiv = document.getElementById("result");
const cameraSelect = document.getElementById("cameraSelect");
let currentStream = null;

// 🔹 Lista todas as câmeras disponíveis
async function listarCameras() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
    console.error("API de mídia não suportada neste navegador.");
    return;
  }

  if (!cameraSelect) return;

  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const cameras = devices.filter((device) => device.kind === "videoinput");

    cameraSelect.innerHTML = "";
    cameras.forEach((camera, index) => {
      const option = document.createElement("option");
      option.value = camera.deviceId;
      option.text = camera.label || `Câmera ${index + 1}`;
      cameraSelect.appendChild(option);
    });
  } catch (err) {
    console.error("Erro ao listar câmeras:", err);
  }
}

// 🔹 Inicia a câmera selecionada
async function startCamera(deviceId) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    console.error("getUserMedia não suportado neste navegador.");
    return;
  }

  if (!video) return;

  if (currentStream) {
    currentStream.getTracks().forEach((track) => track.stop());
  }

  const constraints = {
    video: deviceId ? { deviceId: { exact: deviceId } } : true,
  };

  try {
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    video.srcObject = stream;
    currentStream = stream;
  } catch (err) {
    console.error("Erro ao acessar câmera:", err);
    if (resultDiv) {
      resultDiv.textContent = "Não foi possível acessar a câmera.";
    }
  }
}

// 🔹 Captura a imagem do vídeo
function capturarImagem() {
  if (!video || !canvas) return null;

  // Garante que o vídeo tem dimensões válidas
  if (!video.videoWidth || !video.videoHeight) {
    console.warn("Vídeo ainda não carregou para capturar.");
    return null;
  }

  const context = canvas.getContext("2d");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg");
}

// 🔹 Detecta em qual página estamos e define endpoint
function getEndpoint() {
  if (window.location.pathname.includes("cadastrar")) {
    return "/salvar_cadastro";      // uso exclusivo da página do professor
  } else {
    return "/capturar_presenca";    // página pública de presença (index)
  }
}

// 🔹 Carrega turmas (apenas na página de cadastro)
async function carregarTurmas() {
  const turmaSelect = document.getElementById("turmaSelect");
  if (!turmaSelect) return; // se não existe, estamos na tela de presença

  try {
    const response = await fetch("/get_turmas");
    const turmas = await response.json();

    turmaSelect.innerHTML = '<option value="">Selecionar...</option>';

    turmas.forEach((t) => {
      const option = document.createElement("option");
      option.value = t.id;          // turma_id
      option.textContent = t.nome;  // nome da turma
      turmaSelect.appendChild(option);
    });
  } catch (err) {
    console.error("Erro ao carregar turmas:", err);
  }
}

// 🔹 Envia a imagem para o backend
async function enviarImagem() {
  if (!resultDiv) return;

  const endpoint = getEndpoint();
  const imagemBase64 = capturarImagem();

  if (!imagemBase64) {
    resultDiv.textContent = "Não foi possível capturar a imagem. Aguarde o vídeo carregar.";
    return;
  }

  let payload = {};

  if (endpoint === "/salvar_cadastro") {
    const nomeInput = document.getElementById("nome");
    const turmaSelect = document.getElementById("turmaSelect");

    const nome = nomeInput ? nomeInput.value.trim() : "";
    const turma_id = turmaSelect ? turmaSelect.value : "";

    if (!nome) {
      alert("Digite o nome do aluno!");
      return;
    }

    if (!turma_id) {
      alert("Selecione a turma do aluno!");
      return;
    }

    payload = {
      nome: nome,
      turma_id: turma_id,
      imagem: imagemBase64,
    };
  } else {
    // Página de presença (index)
    payload = { imagem: imagemBase64 };
  }

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    resultDiv.textContent = data.mensagem || "Operação realizada.";
  } catch (err) {
    console.error("Erro ao enviar imagem:", err);
    resultDiv.textContent = "Erro ao enviar imagem.";
  }
}

// 🔹 Inicializa listagem de câmeras e demais recursos
async function init() {
  // Se não tem elementos de câmera na página, não faz nada
  if (!cameraSelect || !video || !canvas) {
    return;
  }

  await listarCameras();

  // Só carrega turmas na tela de cadastro (quando existe turmaSelect)
  if (document.getElementById("turmaSelect")) {
    await carregarTurmas();
  }

  if (cameraSelect.options.length > 0) {
    await startCamera(cameraSelect.value);
  }
}

// 🔹 Eventos dos botões
if (document.getElementById("btnStart")) {
  document.getElementById("btnStart").addEventListener("click", async () => {
    if (!cameraSelect) return;
    await startCamera(cameraSelect.value);
  });
}

if (document.getElementById("btnSnapshot")) {
  document
    .getElementById("btnSnapshot")
    .addEventListener("click", enviarImagem);
}

// 🔹 Inicia tudo
init();
