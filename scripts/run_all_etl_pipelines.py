#!/usr/bin/env python3
import os
import sys
import subprocess

def run_step(step_name, command, env_vars=None):
    """Executes a pipeline step and streams output. Stops if an error occurs."""
    print(f"\n==========================================")
    print(f"🚀 [ETL Orchestrator] Running: {step_name}")
    print(f"==========================================")
    
    # Merge current system environment with any custom flags
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
        
    try:
        # Run command and stream logs directly to console
        process = subprocess.run(command, check=True, env=env)
        print(f"✅ {step_name} completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ ERROR: {step_name} failed with exit code {e.returncode}.")
        sys.exit(e.returncode)

def main():
    # 1. Flag to control optional APIs (e.g., set ENABLE_TXDOT_INGEST=true for live TxDOT)
    enable_txdot = os.getenv("ENABLE_TXDOT_INGEST", "false")
    
    pipeline_env = {
        "ENABLE_TXDOT_INGEST": enable_txdot
    }

    # 2. Define your ETL execution sequence
    steps = [
        # Example Step A: Optional pre-processing or secondary data downloads
        # ("Pre-flight Check", ["uv", "run", "python", "-c", "import requests; print('Network OK')"]),
        
        # Core Step: Main Logistics ETL Execution
        ("Logistics & Weather ETL Engine", ["uv", "run", "scripts/logistics_etl.py"]),
    ]

    # 3. Execute all steps sequentially
    for name, cmd in steps:
        run_step(name, cmd, env_vars=pipeline_env)

    print("\n🎉 All required ETL pipelines executed and SQLite DB updated successfully!\n")

if __name__ == "__main__":
    main()