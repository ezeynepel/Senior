const API = "http://127.0.0.1:8000/api/v1";
const WS = "ws://127.0.0.1:8000/ws/dashboard";

let helmets = [];
let allFeedEntries = [];
let selectedUnit = null;
let currentFilter = "all";

function getPriorityLabel(priority) {
  if (priority === "high") return "High Priority";
  if (priority === "medium") return "Moderate Priority";
  if (priority === "low") return "Low Priority";
  return priority;
}

function formatCommandType(commandType) {
  return commandType
    .toLowerCase()
    .split("_")
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

async function loadInitialData() {
  const summary = await fetch(`${API}/status/summary`).then(r => r.json());
  helmets = await fetch(`${API}/helmets`).then(r => r.json());
  allFeedEntries = await fetch(`${API}/logs`).then(r => r.json());

  selectedUnit = null;

  renderSummary(summary);
  renderUnits();
  renderCenterFeed();
  await renderUnitDetails();
  renderOtherUnitsHistory();
  setupFilters();
}

function renderSummary(summary) {
  document.getElementById("totalUnits").textContent = summary.total_units;
  document.getElementById("onlineUnits").textContent = summary.online_units;
  document.getElementById("avgLatency").textContent = `${summary.avg_latency_ms} ms`;
  document.getElementById("totalCommands").textContent = summary.total_commands;
}

function renderUnits() {
  const unitsDiv = document.getElementById("units");

  unitsDiv.innerHTML = `
    <div class="unit ${selectedUnit === null ? "active-unit" : ""}" onclick="window.clearSelection()">
      <div><strong>All Units</strong></div>
      <div class="status-badge status-online">main screen</div>
    </div>
  `;

  helmets.forEach((helmet) => {
    const isActive = helmet.device_id === selectedUnit ? "active-unit" : "";

    unitsDiv.innerHTML += `
      <div class="unit ${isActive}" onclick="window.selectUnit('${helmet.device_id}')">
        <div><strong>${helmet.device_id}</strong></div>
        <div class="status-badge status-${helmet.connection_status}">
          ${helmet.connection_status}
        </div>
      </div>
    `;
  });
}

window.selectUnit = async function (deviceId) {
  if (selectedUnit === deviceId) {
    selectedUnit = null;
  } else {
    selectedUnit = deviceId;
  }

  renderUnits();
  renderCenterFeed();
  await renderUnitDetails();
  renderOtherUnitsHistory();
};
window.clearSelection = async function () {
  selectedUnit = null;

  renderUnits();
  renderCenterFeed();
  await renderUnitDetails();
  renderOtherUnitsHistory();
};

function getCenterFeedEntries() {
  let feed = [...allFeedEntries];

  if (selectedUnit !== null) {
    feed = feed.filter(entry => entry.device_id === selectedUnit);
  }

  if (currentFilter === "high") {
    feed = feed.filter(entry => entry.priority === "high");
  }

  return feed;
}

function getOtherUnitsHistoryEntries() {
  if (selectedUnit === null) {
    return [];
  }

  return allFeedEntries.filter(entry => entry.device_id !== selectedUnit);
}

function renderCenterFeed() {
  const commandsDiv = document.getElementById("commands");
  commandsDiv.innerHTML = "";

  const feedEntries = getCenterFeedEntries();

  if (feedEntries.length === 0) {
    commandsDiv.innerHTML = `<div class="empty-state">No commands available.</div>`;
    return;
  }

  feedEntries.forEach(cmd => {
    commandsDiv.innerHTML += `
      <div class="command-card">
        <div class="row">
          <strong>${cmd.device_id}</strong>
          <span class="priority-badge priority-${cmd.priority}">
            ${getPriorityLabel(cmd.priority)}
          </span>
        </div>

        <div class="command-title">${formatCommandType(cmd.command_type)}</div>
        <div>Source: ${cmd.source}</div>
        <div>Confidence: ${cmd.confidence_score}</div>
        <div class="command-time">${cmd.timestamp}</div>
      </div>
    `;
  });
}

async function fetchHelmetDetail(deviceId) {
  const response = await fetch(`${API}/helmets/${deviceId}`);
  return await response.json();
}

async function renderUnitDetails() {
  const detailsDiv = document.getElementById("details");
  detailsDiv.innerHTML = "";

  if (selectedUnit === null) {
    detailsDiv.innerHTML = `
      <div class="empty-state">
        Select a unit to see details.
      </div>
    `;
    return;
  }

  const detail = await fetchHelmetDetail(selectedUnit);

  if (!detail.telemetry) {
    detailsDiv.innerHTML = `<div class="empty-state">No telemetry available.</div>`;
    return;
  }

  const h = detail.telemetry;

  detailsDiv.innerHTML = `
    <div class="detail-card">
      <div><strong>${detail.device_id}</strong></div>
      <div>Status: ${h.connection_status}</div>
      <div>Battery: ${h.battery_level}%</div>
      <div>Signal: ${h.signal_strength}</div>
      <div>Latency: ${h.latency_ms} ms</div>
      <div>Temp: ${h.temperature_c} °C</div>
      <div>Total Commands: ${detail.total_commands}</div>
      <div>High Priority Count: ${detail.high_priority_count}</div>
    </div>
  `;
}

function renderOtherUnitsHistory() {
  const historyTitle = document.querySelector(".history-title");
  const historyDiv = document.getElementById("history");

  historyDiv.innerHTML = "";

  if (selectedUnit === null) {
    historyTitle.style.display = "none";
    historyDiv.style.display = "none";
    return;
  }

  historyTitle.style.display = "block";
  historyDiv.style.display = "block";

  const otherEntries = getOtherUnitsHistoryEntries().slice(0, 20);

  if (otherEntries.length === 0) {
    historyDiv.innerHTML = `<div class="empty-state">No other unit history available.</div>`;
    return;
  }

  otherEntries.forEach(cmd => {
    historyDiv.innerHTML += `
      <div class="history-card">
        <div><strong>${cmd.device_id}</strong></div>
        <div>${formatCommandType(cmd.command_type)}</div>
        <div>Source: ${cmd.source}</div>
        <div>Confidence: ${cmd.confidence_score}</div>
        <div>${getPriorityLabel(cmd.priority)}</div>
        <div class="command-time">${cmd.timestamp}</div>
      </div>
    `;
  });
}

async function refreshSummary() {
  const summary = await fetch(`${API}/status/summary`).then(r => r.json());
  renderSummary(summary);
}

function setupFilters() {
  const allBtn = document.getElementById("filterAll");
  const highBtn = document.getElementById("filterHigh");

  if (!allBtn || !highBtn) return;

  allBtn.onclick = () => {
    currentFilter = "all";
    allBtn.classList.add("active");
    highBtn.classList.remove("active");
    renderCenterFeed();
  };

  highBtn.onclick = () => {
    currentFilter = "high";
    highBtn.classList.add("active");
    allBtn.classList.remove("active");
    renderCenterFeed();
  };
}

function setupWebSocket() {
  const socket = new WebSocket(WS);

  socket.onopen = () => {
    socket.send("dashboard_connected");
  };

  socket.onmessage = async (event) => {
    const msg = JSON.parse(event.data);

    if (msg.event === "new_command") {
      allFeedEntries.unshift(msg.data);

      renderCenterFeed();
      renderOtherUnitsHistory();
      await refreshSummary();
    }

    if (msg.event === "telemetry_update") {
      const index = helmets.findIndex(h => h.device_id === msg.data.device_id);

      if (index !== -1) {
        helmets[index] = msg.data;
      } else {
        helmets.push(msg.data);
      }

      renderUnits();

      if (selectedUnit === msg.data.device_id) {
        await renderUnitDetails();
      }

      await refreshSummary();
    }
  };

  socket.onerror = () => {
    console.log("WebSocket connection error");
  };
}

loadInitialData();
setupWebSocket();