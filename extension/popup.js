const BACKEND_URLS = [
  "https://recruitment-document-tools.onrender.com/search/active-plan",
  "http://127.0.0.1:8001/search/active-plan",
  "http://localhost:8001/search/active-plan",
];

async function checkBackendStatus() {
  const dot = document.getElementById("dot");
  const text = document.getElementById("status-text");
  let connected = false;

  for (const url of BACKEND_URLS) {
    try {
      const res = await fetch(url);
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
  }
}

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
