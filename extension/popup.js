const BACKEND_URLS = [
  "https://recruitment-document-tools.onrender.com/search/active-plan",
  "http://127.0.0.1:8001/search/active-plan",
  "http://localhost:8001/search/active-plan",
];

async function checkStatus() {
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

document.getElementById("fill-btn").addEventListener("click", async () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, { action: "TRIGGER_FILL" }, (res) => {
        window.close();
      });
    }
  });
});

document.getElementById("force-btn").addEventListener("click", async () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, { action: "FORCE_FILL" }, (res) => {
        window.close();
      });
    }
  });
});

checkStatus();
