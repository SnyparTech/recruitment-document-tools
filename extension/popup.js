const BACKEND_BASES = [
  "https://recruitment-document-tools.onrender.com",
  "http://127.0.0.1:8001",
  "http://localhost:8001",
];

// Same device-id scheme as content.js (not importable here, Manifest V3 popup
// is a separate script context) — generated once, cached in chrome.storage.local.
async function getDeviceId() {
  const stored = await chrome.storage.local.get("snypar_device_id");
  if (stored.snypar_device_id) return stored.snypar_device_id;
  const generated = crypto.randomUUID();
  await chrome.storage.local.set({ snypar_device_id: generated });
  return generated;
}

async function getDeviceToken() {
  const stored = await chrome.storage.local.get("snypar_device_token");
  return stored.snypar_device_token || null;
}

async function checkBackendStatus() {
  const dot = document.getElementById("dot");
  const text = document.getElementById("status-text");
  const authBox = document.getElementById("device-auth-box");
  const deviceId = await getDeviceId();
  const deviceToken = await getDeviceToken();
  const headers = { "X-Device-Id": deviceId };
  if (deviceToken) headers["X-Device-Token"] = deviceToken;
  let connected = false;
  let unauthorized = false;

  for (const base of BACKEND_BASES) {
    try {
      const res = await fetch(base + "/search/active-plan", { headers });
      if (res.status === 403) {
        unauthorized = true;
        connected = true;
        break;
      }
      if (res.ok) {
        const data = await res.json();
        dot.className = "dot";
        text.innerText = data.has_plan ? "Search Plan Ready" : "Server Online";
        connected = true;
        break;
      }
    } catch (e) {}
  }

  if (!connected) {
    dot.className = "dot offline";
    text.innerText = "Server Offline";
  } else if (unauthorized) {
    dot.className = "dot offline";
    text.innerText = "Device Not Paired";
    authBox.className = "visible";
  }
}

document.getElementById("pair-btn").addEventListener("click", async () => {
  const msg = document.getElementById("device-auth-msg");
  const code = document.getElementById("pairing-code-input").value.trim();
  if (!code) {
    msg.className = "error";
    msg.innerText = "Enter the pairing code from the website.";
    return;
  }
  const deviceId = await getDeviceId();
  msg.className = "";
  msg.innerText = "Pairing...";

  for (const base of BACKEND_BASES) {
    try {
      const res = await fetch(base + "/auth/pair-device", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, device_id: deviceId }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        await chrome.storage.local.set({ snypar_device_token: data.device_token });
        msg.className = "success";
        msg.innerText = "Device paired. Reopen this popup.";
        document.getElementById("device-auth-box").className = "";
        checkBackendStatus();
        return;
      }
      msg.className = "error";
      msg.innerText = (data && data.detail) || "Pairing failed.";
      return;
    } catch (e) {}
  }
  msg.className = "error";
  msg.innerText = "Could not reach the server.";
});

/**
 * Query the content script for real-time fill state.
 * Shows / hides Pause and Resume buttons based on isFilling / isPaused.
 */
function queryFillStatus() {
  const pauseBtn  = document.getElementById("pause-btn");
  const resumeBtn = document.getElementById("resume-btn");

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs[0]) return;
    chrome.tabs.sendMessage(tabs[0].id, { action: "GET_STATUS" }, (res) => {
      if (chrome.runtime.lastError || !res) {
        // Content script not loaded on this tab (not Resdex page)
        if (pauseBtn)  pauseBtn.style.display  = "none";
        if (resumeBtn) resumeBtn.style.display = "none";
        return;
      }

      if (res.isFilling && !res.isPaused) {
        // Bot is actively filling — show Pause, hide Resume
        if (pauseBtn)  pauseBtn.style.display  = "block";
        if (resumeBtn) resumeBtn.style.display = "none";
      } else if (res.isFilling && res.isPaused) {
        // Bot is paused mid-fill — show Resume, hide Pause
        if (pauseBtn)  pauseBtn.style.display  = "none";
        if (resumeBtn) resumeBtn.style.display = "block";
      } else {
        // Idle — hide both
        if (pauseBtn)  pauseBtn.style.display  = "none";
        if (resumeBtn) resumeBtn.style.display = "none";
      }
    });
  });
}

// ── Button wiring ──────────────────────────────────────────────────────────────

document.getElementById("fill-btn").addEventListener("click", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, { action: "TRIGGER_FILL" }, () => window.close());
    }
  });
});

document.getElementById("force-btn").addEventListener("click", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, { action: "FORCE_FILL" }, () => window.close());
    }
  });
});

document.getElementById("pause-btn").addEventListener("click", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, { action: "PAUSE" }, () => queryFillStatus());
    }
  });
});

document.getElementById("resume-btn").addEventListener("click", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, { action: "RESUME" }, () => queryFillStatus());
    }
  });
});

// ── Init ───────────────────────────────────────────────────────────────────────

checkBackendStatus();
queryFillStatus();
