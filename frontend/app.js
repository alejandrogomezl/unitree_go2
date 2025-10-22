const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const gamepadEl = $("gamepad-status");
const logsEl = $("logs");

async function getStatus() {
  const res = await fetch("/api/status");
  const data = await res.json();
  const running = data.running ? "🟢 Ejecutando" : "🔴 Detenido";
  const cfg = data.config ? JSON.stringify(data.config) : "—";
  statusEl.textContent = `Estado: ${running} | Config: ${cfg}`;
  updateGamepad(data.gamepad_connected);
}

function updateGamepad(connected) {
  gamepadEl.innerHTML = connected
    ? `Mando: <span class="ok">🎮 Conectado</span>`
    : `Mando: <span class="warn">⚠️ No detectado</span>`;
}

function appendLog(line) {
  logsEl.textContent += line + "\n";
  logsEl.scrollTop = logsEl.scrollHeight;
  if (logsEl.textContent.split("\n").length > 500)
    logsEl.textContent = logsEl.textContent.split("\n").slice(-500).join("\n");
}

function connectLogs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/logs`);

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === "log") appendLog(msg.data);
      else if (msg.type === "gamepad") updateGamepad(msg.data === "connected");
      else appendLog(e.data);
    } catch {
      appendLog(e.data);
    }
  };
  ws.onopen = () => appendLog("[WS conectado]");
  ws.onclose = () => {
    appendLog("[WS desconectado, reintentando...]");
    setTimeout(connectLogs, 2000);
  };
}

$("btn-connect").addEventListener("click", async () => {
  const method = $("method").value;
  const ip = $("ip").value || null;
  await fetch("/api/connect", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ method, ip })
  });
  await getStatus();
});

$("btn-disconnect").addEventListener("click", async () => {
  await fetch("/api/disconnect", { method: "POST" });
  await getStatus();
});

getStatus();
connectLogs();

(function attachCamera(){
  const img = document.getElementById('go2-cam');
  const status = document.getElementById('cam-status');
  if (!img) return;

  const mjpegUrl = '/api/video/mjpeg';

  function setStatus(t) {
    if (status) status.textContent = t || '';
  }

  // Prueba MJPEG; si falla, cambia a refresco periódico del frame
  const test = new Image();
  let decided = false;

  test.onload = () => {
    if (decided) return;
    decided = true;
    img.src = mjpegUrl;
    setStatus('MJPEG conectado');
  };
  test.onerror = () => {
    if (decided) return;
    decided = true;
    setStatus('MJPEG no disponible, usando refresco periódico…');
    startPolling();
  };
  test.src = mjpegUrl + '?probe=1';

  // Fallback a frame único cada 250ms
  let pollTimer = null;
  function startPolling() {
    stopPolling();
    pollTimer = setInterval(() => {
      img.src = '/api/video/frame?ts=' + Date.now();
    }, 250);
  }
  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  // Si en 1500ms no decidió, haz fallback
  setTimeout(() => {
    if (!decided) {
      decided = true;
      setStatus('MJPEG lento, usando refresco periódico…');
      startPolling();
    }
  }, 1500);
})();
