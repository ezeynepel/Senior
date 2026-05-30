const API = "http://127.0.0.1:8000/api/v1";
const WS = "ws://127.0.0.1:8000/ws/dashboard";

let helmets = [];
let allFeedEntries = [];
let selectedUnit = null;
let currentFilter = "all";
let socket = null;
let reconnectTimer = null;

function getPriorityLabel(priority) {
  if (priority === "high") return "High Priority";
  if (priority === "medium") return "Moderate Priority";
  if (priority === "low") return "Low Priority";
  return priority || "N/A";
}

function formatCommandType(commandType) {
  if (!commandType) return "Waiting...";
  return commandType
    .toLowerCase()
    .split("_")
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

async function fetchJson(path) {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`Request failed: ${path}`);
  return response.json();
}

async function loadInitialData() {
  try {
    const [summary, helmetList, logs] = await Promise.all([
      fetchJson("/status/summary"),
      fetchJson("/helmets"),
      fetchJson("/logs"),
    ]);

    helmets = helmetList;
    allFeedEntries = logs;
    selectedUnit = null;

    renderSummary(summary);
    renderUnits();
    renderCenterFeed();
    await renderUnitDetails();
    renderOtherUnitsHistory();
    setupFilters();
    updateCameraStatus("online");
  } catch (error) {
    console.error(error);
    document.getElementById("commands").innerHTML = `
      <div class="empty-state">
        Backend connection failed. Start FastAPI with uvicorn main:app --reload.
      </div>
    `;
    updateCameraStatus("offline");
  }
}

function renderSummary(summary) {
  document.getElementById("totalUnits").textContent = summary.total_units ?? 0;
  document.getElementById("onlineUnits").textContent = summary.online_units ?? 0;
  document.getElementById("avgLatency").textContent = `${summary.avg_latency_ms ?? 0} ms`;

  const totalEl = document.getElementById("totalCommands") || document.getElementById("totalEvents");
  if (totalEl) totalEl.textContent = summary.total_commands ?? 0;
}

function updateCameraStatus(status) {
  const statusEl = document.getElementById("cameraStatus");
  if (!statusEl) return;

  statusEl.textContent = status;
  statusEl.className = `status-badge status-${status}`;
}

function renderUnits() {
  const unitsDiv = document.getElementById("units");

  let html = `
    <div class="unit ${selectedUnit === null ? "active-unit" : ""}" id="allUnitsBtn">
      <div><strong>All Units</strong></div>
      <div class="status-badge status-online">main screen</div>
    </div>
  `;

  helmets.forEach((helmet) => {
    const status = helmet.connection_status || "offline";
    const isActive = helmet.device_id === selectedUnit ? "active-unit" : "";

    html += `
      <div class="unit ${isActive}" data-device="${helmet.device_id}">
        <div><strong>${helmet.device_id}</strong></div>
        <div class="status-badge status-${status}">${status}</div>
      </div>
    `;
  });

  unitsDiv.innerHTML = html;

  document.getElementById("allUnitsBtn").onclick = async () => {
    await clearSelection();
  };

  document.querySelectorAll("[data-device]").forEach((el) => {
    el.onclick = async () => {
      await selectUnit(el.dataset.device);
    };
  });
}

async function selectUnit(deviceId) {
  selectedUnit = selectedUnit === deviceId ? null : deviceId;

  renderUnits();
  renderCenterFeed();
  await renderUnitDetails();
  renderOtherUnitsHistory();
}

async function clearSelection() {
  selectedUnit = null;

  renderUnits();
  renderCenterFeed();
  await renderUnitDetails();
  renderOtherUnitsHistory();
}

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

function renderCenterFeed() {
  const commandsDiv = document.getElementById("commands");
  commandsDiv.innerHTML = "";

  const feedEntries = getCenterFeedEntries();

  if (feedEntries.length === 0) {
    commandsDiv.innerHTML = `<div class="empty-state">Waiting for predicted text...</div>`;
    return;
  }

  feedEntries.forEach(event => {
    commandsDiv.innerHTML += `
      <div class="command-card">
        <div class="row">
          <strong>${event.device_id}</strong>
          <span class="priority-badge priority-${event.priority}">
            ${getPriorityLabel(event.priority)}
          </span>
        </div>

        <div class="command-title">${formatCommandType(event.command_type)}</div>
        <div>Source: ${event.source || "gesture"}</div>
        <div>Confidence: ${event.confidence_score ?? "N/A"}</div>
        <div>Status: ${event.status || "validated"}</div>
        <div class="command-time">${event.timestamp || ""}</div>
      </div>
    `;
  });
}

async function fetchHelmetDetail(deviceId) {
  return fetchJson(`/helmets/${deviceId}`);
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
  const h = detail.telemetry;

  detailsDiv.innerHTML = `
    <div class="detail-card">
      <div><strong>${detail.device_id}</strong></div>
      <div>Status: ${h.connection_status}</div>
      <div>Battery: ${h.battery_level}%</div>
      <div>Signal: ${h.signal_strength}</div>
      <div>Latency: ${h.latency_ms} ms</div>
      <div>Temp: ${h.temperature_c} °C</div>
      <div>Recognition Confidence: ${h.recognition_confidence}</div>
      <div>Total Outputs: ${detail.total_commands}</div>
      <div>High Priority Count: ${detail.high_priority_count}</div>
    </div>
  `;
}

function renderOtherUnitsHistory() {
  const historyTitle = document.querySelector(".history-title");
  const historyDiv = document.getElementById("history");

  if (!historyTitle || !historyDiv) return;

  historyDiv.innerHTML = "";

  if (selectedUnit === null) {
    historyTitle.style.display = "none";
    historyDiv.style.display = "none";
    return;
  }

  historyTitle.style.display = "block";
  historyDiv.style.display = "block";

  const otherEntries = allFeedEntries
    .filter(entry => entry.device_id !== selectedUnit)
    .slice(0, 20);

  if (otherEntries.length === 0) {
    historyDiv.innerHTML = `<div class="empty-state">No other unit history available.</div>`;
    return;
  }

  otherEntries.forEach(event => {
    historyDiv.innerHTML += `
      <div class="history-card">
        <div><strong>${event.device_id}</strong></div>
        <div>${formatCommandType(event.command_type)}</div>
        <div>Source: ${event.source || "gesture"}</div>
        <div>Confidence: ${event.confidence_score ?? "N/A"}</div>
        <div>${getPriorityLabel(event.priority)}</div>
        <div class="command-time">${event.timestamp || ""}</div>
      </div>
    `;
  });
}

async function refreshSummary() {
  const summary = await fetchJson("/status/summary");
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
  socket = new WebSocket(WS);

  socket.onopen = () => {
    socket.send("dashboard_connected");
    updateCameraStatus("online");
  };

  socket.onmessage = async (event) => {
    const msg = JSON.parse(event.data);

    if (msg.event === "new_command") {
      allFeedEntries.unshift(msg.data);
      allFeedEntries = allFeedEntries.slice(0, 100);

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

      updateCameraStatus(msg.data.connection_status || "online");
      renderUnits();

      if (selectedUnit === msg.data.device_id) {
        await renderUnitDetails();
      }

      await refreshSummary();
    }
  };

  socket.onerror = () => {
    updateCameraStatus("offline");
  };

  socket.onclose = () => {
    updateCameraStatus("offline");
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(setupWebSocket, 2000);
  };
}

loadInitialData();
setupWebSocket();