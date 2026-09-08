import os
import json
import sqlite3
import requests

# Ensure the directory exists on the runnder
os.makedirs("public/data", exists_ok=True)

TABLE_NAME="weather_table.db"

# 1. Pull Open Weather/Transit Alert JSON
URL = "https://api.weather.gov/alerts/active?status=actual&message_type=alert"
headers = {"User-Agent": "LogisticsDashboardPrototype/1.0"}

response = requests.get(URL, headers=headers)
data = response.json()

# 2. Extract key fields
records = []
for feature in data.get("features", [])[:50]:  # Cap to top 50
    props = feature["properties"]
    records.append(
        (
            props.get("id"),
            props.get("event"),
            props.get("severity"),
            props.get("areaDesc"),
            props.get("effective"),
        )
    )

# 3. Store into SQLite Database

conn = sqlite3.connect(f"public/data/{TABLE_NAME}")
cursor = conn.cursor()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS alerts (
        id TEXT PRIMARY KEY,
        event TEXT,
        severity TEXT,
        area TEXT,
        timestamp TEXT
    )
"""
)
cursor.executemany(
    "INSERT OR REPLACE INTO alerts VALUES (?, ?, ?, ?, ?)", records
)
conn.commit()
conn.close()
print(f"Successfully updated public/data/{TABLE_NAME}")