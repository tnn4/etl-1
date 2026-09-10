# Testing

To test both the Python data processing and the deployment setup locally and on GitHub without breaking your live site or corrupting the `main` branch, use a three-tier testing process.

---

### Tier 1: Local Dry Run (Zero External Impact)

Test the Python code locally using standard environment variables and local web servers.

1. **Verify Python Execution Locally**
   Run the orchestrator locally to generate a fresh `public/data/weather_table.db` file without pushing anything to GitHub:

```bash
uv run scripts/run_all_etl_pipelines.py

```

_To test with live TxDOT endpoints without risking your GitHub Actions runner, set `ENABLE_TXDOT_INGEST=true`:_

```bash
ENABLE_TXDOT_INGEST=true uv run scripts/run_all_etl_pipelines.py

```

2. **Serve the Static Web App Locally**
   Start a local HTTP server from the project root to ensure `index_2.js` correctly loads the updated `weather_table.db` over WASM:

```bash
python3 -m http.server 8000

```

Open `http://localhost:8000` in your browser. Open your Developer Tools (F12) to verify:

- No console errors requesting `index.js` instead of `index_2.js`.

- SQLite WASM loads and populates the table and Leaflet map markers without syntax errors.

---

### Tier 2: Isolated Branch Testing (Safeguard Main)

Avoid pushing directly to `main`. Test the workflow on a dedicated feature branch.

1. **Create a Test Branch**

```bash
git checkout -b test/etl-pipeline-refactor

```

2. **Temporary Workflow Trigger Update**
   Modify `.github/workflows/deploy_pipeline.yml` on your feature branch so it triggers on pushes to _your specific branch_ rather than `main`:

```yaml
on:
  workflow_dispatch:
  push:
    branches:
      - test/etl-pipeline-refactor # Target feature branch while testing
```

3. **Disable Automatic Deployment Step During Testing**
   To ensure you don't overwrite your live GitHub Pages site on `main` while testing the workflow steps, comment out or wrap the deployment step in step 8:

```yaml
# Step 8: Deploy static site live (Disabled on test branch)
# - name: Deploy to GitHub Pages
#   id: deployment
#   uses: actions/deploy-pages@v4
```

4. **Push and Inspect Action Logs**

```bash
git add .
git commit -m "test: isolate workflow execution on test branch"
git push origin test/etl-pipeline-refactor

```

Go to **GitHub -> Actions -> Scheduled Logistics ETL & Deployment Pipeline**. Check the step-by-step logs to ensure `uv run scripts/run_all_etl_pipelines.py` runs cleanly without exiting on errors.

---

### Tier 3: Local GitHub Action Simulation (Optional CLI)

If you want to test GitHub Action execution locally without making remote commits, use **`act`** (a tool that runs GitHub Actions inside a local Docker container).

1. **Install `act**` (via Homebrew/macOS or Linux):

```bash
brew install act

```

2. **Run the Job Locally**

```bash
act workflow_dispatch -j run-etl-and-deploy

```

This executes your workflow in an isolated `ubuntu-latest` container on your machine, catching missing dependencies or path errors before pushing to remote origin.

---

### Final Verification Checklists Before Merging to `main`

Once your test branch passes all checks, revert the temporary triggers before opening a Pull Request:

- Change `branches: [test/etl-pipeline-refactor]` back to `branches: [main]` in `.github/workflows/deploy_pipeline.yml`.

- Uncomment step 8 (`actions/deploy-pages@v4`).

- Ensure `.github/workflows/deploy_pipeline.yml` resides in `.github/workflows/`.

- Ensure `index.html` (or `index_3.html`) references `index_2.js`.
