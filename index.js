async function initDatabaseReader() {
  const statusEl = document.getElementById("status");
  const tableBody = document.getElementById("table-body");

  try {
    // 1. Initialize sql.js engine with WASM binary URL
    statusEl.innerText = "Loading SQLite WebAssembly...";
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

    // Convert the HTTP response to a binary ArrayBuffer
    const buffer = await response.arrayBuffer();

    // 3. Instantiate the Database in browser memory
    const db = new SQL.Database(new Uint8Array(buffer));
    statusEl.innerText = "Database loaded successfully! Executing query...";

    // 4. Run standard SQL queries directly
    const query =
      "SELECT id, event, severity, area, timestamp FROM alerts LIMIT 20;";
    const stmt = db.prepare(query);

    // 5. Render results into the DOM
    tableBody.innerHTML = "";
    while (stmt.step()) {
      const row = stmt.getAsObject();
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${row.id || "N/A"}</td>
        <td><strong>${row.event || "Unknown"}</strong></td>
        <td>${row.severity || "N/A"}</td>
        <td>${row.area || "N/A"}</td>
        <td>${row.timestamp || "N/A"}</td>
      `;
      tableBody.appendChild(tr);
    }

    // Clean up statement memory
    stmt.free();
    statusEl.innerText = "Query Execution Complete!";

    enableCustomQueryConsole(db);
  } catch (err) {
    console.error(err);
    statusEl.innerText = `Error: ${err.message}`;
    statusEl.style.color = "#ef4444";
  }
}

function startUpdateTimer() {
  const timerEl = document.getElementById("countdown-timer");

  function updateClock() {
    const now = new Date();

    // Target the next top of the hour
    const nextUpdate = new Date(now);
    nextUpdate.setHours(now.getHours() + 1);
    nextUpdate.setMinutes(0);
    nextUpdate.setSeconds(0);
    nextUpdate.setMilliseconds(0);

    // Calculate time difference in seconds
    const diffInSeconds = Math.floor((nextUpdate - now) / 1000);

    const minutes = Math.floor(diffInSeconds / 60);
    const seconds = diffInSeconds % 60;

    // Format with leading zeros (e.g., 05:09)
    const formattedMinutes = String(minutes).padStart(2, "0");
    const formattedSeconds = String(seconds).padStart(2, "0");

    timerEl.innerText = `${formattedMinutes}:${formattedSeconds}`;

    // Optional: Trigger a auto-fetch if timer reaches 00:00
    if (diffInSeconds <= 0) {
      timerEl.innerText = "Refreshing feed...";
      setTimeout(() => {
        location.reload(); // Reload page to fetch updated weather_table.db
      }, 5000);
    }
  }

  // Run immediately and update every 1 second
  updateClock();
  setInterval(updateClock, 1000);
}

// Call the timer on initialization
startUpdateTimer();

// Function to run ad-hoc queries safely
function enableCustomQueryConsole(db) {
  const btn = document.getElementById("run-query-btn");
  const input = document.getElementById("sql-input");
  const outputContainer = document.getElementById("custom-output-container");

  btn.addEventListener("click", () => {
    const userQuery = input.value.trim();
    if (!userQuery) return;

    try {
      // Execute the user's query against the in-memory database
      const res = db.exec(userQuery);

      if (res.length === 0) {
        outputContainer.innerHTML =
          "<p style='color: #facc15;'>Query executed successfully. (0 rows returned)</p>";
        return;
      }

      // Build a dynamic table from returned columns & values
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
      // Show syntax or runtime SQL errors cleanly to the user
      outputContainer.innerHTML = `<p style='color: #ef4444;'>SQL Error: ${err.message}</p>`;
    }
  });
}

// Run reader on page load
function main() {
  initDatabaseReader();
  startUpdateTimer();
}

main();
