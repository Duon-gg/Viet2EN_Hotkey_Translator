const DEFAULTS = {
  enabled: true,
  port: 8765,
  token: "",
  unlockAntiCopy: true,
  hoverFallback: true,
  replaceReadonly: false
};

let socket = null;
let reconnectTimer = null;
let heartbeatTimer = null;
const requestTargets = new Map();

async function loadSettings() {
  return { ...DEFAULTS, ...(await chrome.storage.sync.get(DEFAULTS)) };
}

function scheduleReconnect(delay = 2500) {
  clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(connect, delay);
}

async function connect() {
  const settings = await loadSettings();
  if (!settings.enabled || !settings.token || socket?.readyState === WebSocket.OPEN) {
    return;
  }

  try {
    socket = new WebSocket(
      `ws://127.0.0.1:${Number(settings.port)}/?token=${encodeURIComponent(settings.token)}`
    );
    socket.addEventListener("open", () => {
      socket.send(JSON.stringify({ type: "hello", client: "chrome-extension", version: 1 }));
      clearInterval(heartbeatTimer);
      heartbeatTimer = setInterval(() => send({ type: "ping" }), 20000);
    });
    socket.addEventListener("message", async (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "extract") await handleExtract(message);
        if (message.type === "apply") await handleApply(message);
      } catch (error) {
        console.warn("Viet2EN bridge message failed", error);
      }
    });
    socket.addEventListener("close", () => {
      socket = null;
      clearInterval(heartbeatTimer);
      scheduleReconnect();
    });
    socket.addEventListener("error", () => socket?.close());
  } catch (_error) {
    socket = null;
    scheduleReconnect();
  }
}

function send(message) {
  if (socket?.readyState !== WebSocket.OPEN) return false;
  socket.send(JSON.stringify(message));
  return true;
}

async function handleExtract(message) {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab?.id || !tab.url || !/^(https?|file):/.test(tab.url)) {
    send({ type: "selection", request_id: message.request_id, text: "" });
    return;
  }

  let frames = [{ frameId: 0 }];
  try {
    frames = (await chrome.webNavigation.getAllFrames({ tabId: tab.id })) || frames;
  } catch (_error) {
    // The top frame fallback still works on ordinary pages.
  }

  const responses = await Promise.all(
    frames.map(async ({ frameId }) => {
      try {
        const response = await chrome.tabs.sendMessage(
          tab.id,
          { type: "extract", request_id: message.request_id },
          { frameId }
        );
        return response?.text ? { ...response, frameId } : null;
      } catch (_error) {
        return null;
      }
    })
  );

  const candidates = responses.filter(Boolean).sort((a, b) => (b.priority || 0) - (a.priority || 0));
  const selected = candidates[0];
  if (!selected) {
    send({ type: "selection", request_id: message.request_id, text: "" });
    return;
  }

  requestTargets.set(message.request_id, { tabId: tab.id, frameId: selected.frameId });
  setTimeout(() => requestTargets.delete(message.request_id), 30000);
  send({
    type: "selection",
    request_id: message.request_id,
    text: selected.text,
    source: selected.source || "dom",
    editable: Boolean(selected.editable),
    tab_id: tab.id,
    frame_id: selected.frameId,
    metadata: { title: tab.title || "", url: tab.url }
  });
}

async function handleApply(message) {
  const target = requestTargets.get(message.request_id) || {
    tabId: message.tab_id,
    frameId: message.frame_id
  };
  let response = { success: false };
  if (target.tabId !== undefined && target.frameId !== undefined) {
    try {
      response = await chrome.tabs.sendMessage(
        target.tabId,
        { type: "apply", request_id: message.request_id, text: message.text },
        { frameId: target.frameId }
      );
    } catch (_error) {
      response = { success: false };
    }
  }
  requestTargets.delete(message.request_id);
  send({ type: "applied", request_id: message.request_id, success: Boolean(response?.success) });
}

chrome.runtime.onInstalled.addListener(async () => {
  const settings = await loadSettings();
  await chrome.storage.sync.set(settings);
  if (!settings.token) chrome.runtime.openOptionsPage();
  connect();
});

chrome.runtime.onStartup.addListener(connect);
chrome.storage.onChanged.addListener((_changes, area) => {
  if (area !== "sync") return;
  socket?.close();
  scheduleReconnect(200);
});

connect();
