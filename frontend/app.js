const API = "http://127.0.0.1:8000/api/v1";
const WS = "ws://127.0.0.1:8000/ws/dashboard";

let helmets = [];
let commands = [];
let selectedUnitId = null;
let currentFilter = "all";

function getPriorityLabel(priority) {
  if (priority === "high") return "High Priority";
  if (priority === "medium") return "Operational";
  return "Review Required";
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
  commands = await fetch(`${API}/logs`).then(r => r.json());

  if (!selectedUnitId && helmets.length > 0) {
    selectedUnitId = helmets[0].device_id;
  }

  renderSummary(summary);
  renderUnits();
  renderCommands();
  renderDetails();
  renderHistory();
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
  unitsDiv.innerHTML = "";

  helmets.forEach((h) => {
    const unitEl = document.createElement("div");
    unitEl.classList.add("unit");

    if (h.device_id === selectedUnitId) {
      unitEl.classList.add("active-unit");
    }

    unitEl.innerHTML = `
      <div><strong>${h.device_id}</strong></div>
      <div class="status-badge status-${h.connection_status}">
        ${h.connection_status}
      </div>
    `;

    unitEl.addEventListener("click", function () {
      selectedUnitId = h.device_id;
      renderUnits();
      renderDetails();
      renderHistory();
    });

    unitsDiv.appendChild(unitEl);
  });
}

function getFilteredCommands() {
  let filtered = [...commands];

  if (currentFilter === "high") {
    filtered = filtered.filter(cmd => cmd.priority === "high");
  }

  return filtered;
}

function renderCommands() {
  const commandsDiv = document.getElementById("commands");
  commandsDiv.innerHTML = "";

  const filteredCommands = getFilteredCommands();

  filteredCommands.forEach(cmd => {
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

  if (filteredCommands.length === 0) {
    commandsDiv.innerHTML = `<div class="empty-state">No commands match the selected filter.</div>`;
  }
}

function renderDetails() {
  const detailsDiv = document.getElementById("details");
  detailsDiv.innerHTML = "";

  const selectedHelmet = helmets.find(h => h.device_id === selectedUnitId);

  if (!selectedHelmet) {
    detailsDiv.innerHTML = `<div class="empty-state">No unit selected.</div>`;
    return;
  }

  detailsDiv.innerHTML = `
    <div class="detail-card">
      <div><strong>${selectedHelmet.device_id}</strong></div>
      <div>Status: ${selectedHelmet.connection_status}</div>
      <div>Battery: ${selectedHelmet.battery_level}%</div>
      <div>Signal: ${selectedHelmet.signal_strength}</div>
      <div>Latency: ${selectedHelmet.latency_ms} ms</div>
      <div>Temp: ${selectedHelmet.temperature_c} °C</div>
      <div>Confidence: ${selectedHelmet.recognition_confidence}</div>
    </div>
  `;
}

function renderHistory() {
  const historyDiv = document.getElementById("history");
  historyDiv.innerHTML = "";

  if (!selectedUnitId) {
    historyDiv.innerHTML = `<div class="empty-state">No unit selected.</div>`;
    return;
  }

  const unitHistory = commands
    .filter(cmd => cmd.device_id === selectedUnitId)
    .slice(0, 8);

  if (unitHistory.length === 0) {
    historyDiv.innerHTML = `<div class="empty-state">No history available for selected unit.</div>`;
    return;
  }

  unitHistory.forEach(cmd => {
    historyDiv.innerHTML += `
      <div class="history-card">
        <div><strong>${formatCommandType(cmd.command_type)}</strong></div>
        <div>Source: ${cmd.source}</div>
        <div>Confidence: ${cmd.confidence_score}</div>
        <div>${getPriorityLabel(cmd.priority)}</div>
        <div class="command-time">${cmd.timestamp}</div>
      </div>
    `;
  });
}

function selectUnit(deviceId) {
  selectedUnitId = deviceId;
  renderUnits();
  renderDetails();
  renderHistory();
}

async function refreshSummary() {
  const summary = await fetch(`${API}/status/summary`).then(r => r.json());
  renderSummary(summary);
}

function setupFilters() {
  const allBtn = document.getElementById("filterAll");
  const highBtn = document.getElementById("filterHigh");

  allBtn.onclick = () => {
    currentFilter = "all";
    allBtn.classList.add("active");
    highBtn.classList.remove("active");
    renderCommands();
  };

  highBtn.onclick = () => {
    currentFilter = "high";
    highBtn.classList.add("active");
    allBtn.classList.remove("active");
    renderCommands();
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
      commands.unshift(msg.data);
      renderCommands();
      renderHistory();
      await refreshSummary();
    }

    if (msg.event === "telemetry_update") {
      const index = helmets.findIndex(h => h.device_id === msg.data.device_id);

      if (index !== -1) {
        helmets[index] = msg.data;
      } else {
        helmets.push(msg.data);
      }

      if (!selectedUnitId) {
        selectedUnitId = msg.data.device_id;
      }

      renderUnits();
      renderDetails();
      await refreshSummary();
    }
  };
}

loadInitialData();
setupWebSocket();