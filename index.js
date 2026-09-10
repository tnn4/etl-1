const PAGE_SIZE = 100;

// Practical operational risk query combining shipments, DOT road hazards, and NWS alerts
const DEFAULT_OPERATIONAL_QUERY = `
SELECT 
    s.shipment_id AS 'Shipment ID',
    s.carrier_name AS 'Carrier',
    l.lane_id AS 'Lane',
    s.status AS 'Shipment Status',
    COALESCE(h.road_name, 'None') AS 'Highway Hazard',
    COALESCE(h.description, 'No active road blockage') AS 'Road Details',
    COALESCE(a.event, 'Clear') AS 'NWS Weather Alert'
FROM active_shipments s
JOIN surface_lanes l ON s.lane_id = l.lane_id
LEFT JOIN highway_hazards h ON (
    ABS(s.current_lat - h.latitude) < 0.5 
    AND ABS(s.current_lng - h.longitude) < 0.5
)
LEFT JOIN alerts a ON (
    ABS(s.current_lat - a.latitude) < 1.0 
    AND ABS(s.current_lng - a.longitude) < 1.0
);
`.trim();

async function initDatabaseReader() {
  const statusEl = document.getElementById("status");

  try {
    // 1. Initialize sql.js engine with WASM binary URL
    statusEl.innerText = "Loading SQLite WebAssembly engine...";
    const initSqlJs = window.initSqlJs;
    const SQL = await initSqlJs({
      locateFile: (file) =>
        `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/${file}`,
    });

    // 2. Fetch the generated SQLite DB file from your static directory
    statusEl.innerText = "Fetching weather_table.db from public/data/...";
    const response = await fetch("./public/data/weather_table.db");

    if (!response.ok) {
      throw new Error(
        `Failed to load DB file: ${response.status} ${response.statusText}`,
      );
    }

    const buffer = await response.arrayBuffer();

    // 3. Instantiate the Database in browser memory
    const db = new SQL.Database(new Uint8Array(buffer));
    statusEl.innerText = "Database loaded successfully!";

    // 4. Enable Interactive Query Console and execute default Operational Query
    enableCustomQueryConsole(db);
    runQuery(db, DEFAULT_OPERATIONAL_QUERY);

    // 5. Render Leaflet Map Layers
    createMap(db);
  } catch (err) {
    console.error(err);
    statusEl.innerText = `Error: ${err.message}`;
    statusEl.style.color = "#ef4444";
  }
}

function runQuery(db, userQuery) {
  const outputContainer = document.getElementById("custom-output-container");

  try {
    const res = db.exec(userQuery);

    if (res.length === 0) {
      outputContainer.innerHTML =
        "<p style='color: #facc15;'>Query executed successfully. (0 rows returned matching criteria)</p>";
      return;
    }

    const columns = res[0].columns;
    const values = res[0].values;

    let tableHtml = "<table><thead><tr>";
    columns.forEach((col) => (tableHtml += `<th>${col}</th>`));
    tableHtml += "</tr></thead><tbody>";

    values.forEach((row) => {
      tableHtml += "<tr>";
      row.forEach((val) => (tableHtml += `<td>${val ?? "NULL"}</td>`));
      tableHtml += "</tr>";
    });
    tableHtml += "</tbody></table>";

    outputContainer.innerHTML = tableHtml;
  } catch (err) {
    outputContainer.innerHTML = `<p style='color: #ef4444;'>SQL Error: ${err.message}</p>`;
  }
}

function enableCustomQueryConsole(db) {
  const btn = document.getElementById("run-query-btn");
  const input = document.getElementById("sql-input");

  btn.addEventListener("click", () => {
    const userQuery = input.value.trim();
    if (!userQuery) return;
    runQuery(db, userQuery);
  });
}

function startUpdateTimer(intervalMinutes = 30) {
  const timerEl = document.getElementById("countdown-timer");

  function updateClock() {
    const now = new Date();
    const nextUpdate = new Date(now);

    const currentMinutes = now.getMinutes();
    const remainder = currentMinutes % intervalMinutes;
    const minutesToNext = intervalMinutes - remainder;

    nextUpdate.setMinutes(currentMinutes + minutesToNext, 0, 0);

    const diffInSeconds = Math.floor((nextUpdate - now) / 1000);
    const minutes = Math.floor(diffInSeconds / 60);
    const seconds = diffInSeconds % 60;

    const formattedMinutes = String(minutes).padStart(2, "0");
    const formattedSeconds = String(seconds).padStart(2, "0");

    timerEl.innerText = `${formattedMinutes}:${formattedSeconds}`;

    if (diffInSeconds <= 0) {
      timerEl.innerText = "Refreshing feed...";
      setTimeout(() => location.reload(), 5000);
    }
  }

  updateClock();
  setInterval(updateClock, 1000);
}

function createMap(db) {
  const map = L.map("map").setView([32.7767, -96.797], 5); // Centered on Southern US / Texas freight hub
  /*
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors",
  }).addTo(map);
  */
  // Works identically on local dev servers AND live GitHub Pages
  L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
    {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: "abcd",
      maxZoom: 19,
    },
  ).addTo(map);

  // Layer 1: Weather Alerts (Circle Markers)
  try {
    const alertStmt = db.prepare(
      "SELECT id, event, severity, area, latitude, longitude FROM alerts WHERE latitude IS NOT NULL;",
    );
    while (alertStmt.step()) {
      const row = alertStmt.getAsObject();
      const color = getSeverityColor(row.severity);

      const marker = L.circleMarker([row.latitude, row.longitude], {
        radius: 8,
        fillColor: color,
        color: "#000",
        weight: 1,
        fillOpacity: 0.7,
      }).addTo(map);

      marker.bindPopup(`
        <strong>Weather Alert: ${row.event}</strong><br>
        <b>Severity:</b> <span style="color:${color}; font-weight:bold;">${row.severity}</span><br>
        <b>Area:</b> ${row.area}
      `);
    }
    alertStmt.free();
  } catch (err) {
    console.warn("Alerts table query skipped:", err.message);
  }

  // Layer 2: Live TxDOT Highway Hazards (Triangle/Square markers)
  try {
    const hazardStmt = db.prepare(
      "SELECT hazard_id, road_name, event_type, description, latitude, longitude FROM highway_hazards;",
    );
    while (hazardStmt.step()) {
      const row = hazardStmt.getAsObject();

      const hazardMarker = L.circleMarker([row.latitude, row.longitude], {
        radius: 6,
        fillColor: "#ef4444",
        color: "#ffffff",
        weight: 2,
        fillOpacity: 0.9,
      }).addTo(map);

      hazardMarker.bindPopup(`
        <strong style="color: #ef4444;">🚧 Road Hazard: ${row.road_name}</strong><br>
        <b>Type:</b> ${row.event_type}<br>
        <b>Details:</b> ${row.description}
      `);
    }
    hazardStmt.free();
  } catch (err) {
    console.warn("Highway hazards query skipped:", err.message);
  }

  // Layer 3: Active Freight Shipments (Blue Markers)
  try {
    const shipmentStmt = db.prepare(
      "SELECT shipment_id, carrier_name, current_lat, current_lng, status FROM active_shipments;",
    );
    while (shipmentStmt.step()) {
      const row = shipmentStmt.getAsObject();

      const truckIcon = L.divIcon({
        className: "truck-badge",
        html: `<div style="
          background: #0284c7; 
          color: white; 
          padding: 2px 5px; 
          border-radius: 3px; 
          font-size: 10px; 
          font-weight: bold;
          border: 1px solid #ffffff;
          white-space: nowrap;
        ">🚛 ${row.shipment_id}</div>`,
        iconSize: [70, 20],
        iconAnchor: [35, 10],
      });

      const shipmentMarker = L.marker([row.current_lat, row.current_lng], {
        icon: truckIcon,
      }).addTo(map);

      shipmentMarker.bindPopup(`
        <strong>Shipment: ${row.shipment_id}</strong><br>
        <b>Carrier:</b> ${row.carrier_name}<br>
        <b>Status:</b> ${row.status}
      `);
    }
    shipmentStmt.free();
  } catch (err) {
    console.warn("Active shipments query skipped:", err.message);
  }
}

function getSeverityColor(severity) {
  switch ((severity || "").toLowerCase()) {
    case "extreme":
      return "#ef4444";
    case "severe":
      return "#f97316";
    case "moderate":
      return "#eab308";
    default:
      return "#3b82f6";
  }
}

async function main() {
  await initDatabaseReader();
  startUpdateTimer();
}

main();
