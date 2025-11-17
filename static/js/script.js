// script.js
const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const resultDiv = document.getElementById("result");
const cameraSelect = document.getElementById("cameraSelect");
let currentStream = null;

// 🔹 Lista todas as câmeras disponíveis
async function listarCameras() {
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
  if (currentStream) {
    currentStream.getTracks().forEach((track) => track.stop());
  }

  const constraints = {
    video: { deviceId: deviceId ? { exact: deviceId } : undefined },
  };

  try {
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    video.srcObject = stream;
    currentStream = stream;
  } catch (err) {
    console.error("Erro ao acessar câmera:", err);
  }
}

// 🔹 Captura a imagem do vídeo
function capturarImagem() {
  const context = canvas.getContext("2d");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg");
}

// 🔹 Detecta em qual página estamos e define endpoint
function getEndpoint() {
  if (window.location.pathname.includes("cadastrar")) {
    return "/salvar_cadastro";
  } else {
    return "/capturar_presenca";
  }
}

async function carregarTurmas() {
  try {
    const response = await fetch("/get_turmas");
    const turmas = await response.json();

    const turmaSelect = document.getElementById("turmaSelect");
    turmaSelect.innerHTML = '<option value="">Selecionar...</option>';

    turmas.forEach((t) => {
      const option = document.createElement("option");
      option.value = t.id; // turma_id
      option.textContent = t.nome; // nome da turma
      turmaSelect.appendChild(option);
    });
  } catch (err) {
    console.error("Erro ao carregar turmas:", err);
  }
}

// 🔹 Envia a imagem para o backend
async function enviarImagem() {
  const endpoint = getEndpoint();
  let payload = {};

  if (endpoint === "/salvar_cadastro") {
    const nome = document.getElementById("nome").value.trim();
    const turma_id = document.getElementById("turmaSelect").value;

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
      imagem: capturarImagem(),
    };
  } else {
    payload = { imagem: capturarImagem() };
  }

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    resultDiv.textContent = data.mensagem;
  } catch (err) {
    console.error("Erro ao enviar imagem:", err);
    resultDiv.textContent = "Erro ao enviar imagem.";
  }
}

// 🔹 Inicializa listagem de câmeras e seleciona a primeira
async function init() {
  await listarCameras();
  await carregarTurmas();
  if (cameraSelect.options.length > 0) {
    await startCamera(cameraSelect.value);
  }
}

// 🔹 Eventos dos botões
if (document.getElementById("btnStart")) {
  document.getElementById("btnStart").addEventListener("click", async () => {
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
