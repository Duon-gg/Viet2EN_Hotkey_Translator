const defaults = {
  enabled: true,
  port: 8765,
  token: "",
  unlockAntiCopy: true,
  hoverFallback: true,
  replaceReadonly: false
};

async function restore() {
  const settings = { ...defaults, ...(await chrome.storage.sync.get(defaults)) };
  for (const [key, value] of Object.entries(settings)) {
    const element = document.getElementById(key);
    if (!element) continue;
    if (element.type === "checkbox") element.checked = Boolean(value);
    else element.value = value;
  }
}

document.getElementById("save").addEventListener("click", async () => {
  await chrome.storage.sync.set({
    enabled: document.getElementById("enabled").checked,
    port: Number(document.getElementById("port").value) || 8765,
    token: document.getElementById("token").value.trim(),
    unlockAntiCopy: document.getElementById("unlockAntiCopy").checked,
    hoverFallback: document.getElementById("hoverFallback").checked,
    replaceReadonly: document.getElementById("replaceReadonly").checked
  });
  document.getElementById("status").textContent = "Đã lưu";
  setTimeout(() => document.getElementById("status").textContent = "", 1500);
});

restore();
