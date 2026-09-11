const API_URL = "http://127.0.0.1:8001/search/active-plan";

async function checkStatus() {
  const dot = document.getElementById("dot");
  const text = document.getElementById("status-text");
  try {
    const res = await fetch(API_URL);
    if (res.ok) {
      const data = await res.json();
      dot.className = "dot";
      text.innerText = data.has_plan ? "Search Plan Ready" : "Server Online";
    } else {
      throw new Error();
    }
  } catch (e) {
    dot.className = "dot offline";
    text.innerText = "Server Offline (port 8001)";
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

checkStatus();
