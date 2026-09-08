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
  } catch (err) {
    console.error(err);
    statusEl.innerText = `Error: ${err.message}`;
    statusEl.style.color = "#ef4444";
  }
}

// Run reader on page load
initDatabaseReader();
