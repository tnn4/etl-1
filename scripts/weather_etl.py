import os
import json
import sqlite3
import requests

# Ensure the directory exists on the runnder
os.makedirs("public/data", exist_ok=True)

TABLE_NAME="weather_table.db"

# 1. Pull Open Weather/Transit Alert JSON
# Example: Fetch ONLY Severe/Extreme alerts to get full coverage without bloated payloads
URL_ALERTS_BY_RELEVANCE = "https://api.weather.gov/alerts/active?status=actual&message_type=alert&severity=Moderate,Severe,Extreme"
URL = "https://api.weather.gov/alerts/active?status=actual&message_type=alert"
headers = {"User-Agent": "LogisticsDashboardPrototype/1.0"}

response = requests.get(URL_ALERTS_BY_RELEVANCE, headers=headers)
data = response.json()

# 2. Extract key fields
# 100 seems like a lightweight number
NUMBER_OF_ALERTS=100
records = []
for feature in data.get("features", [])[:NUMBER_OF_ALERTS]:  # Cap to top NUMBER_OF_ALERTS
    props = feature.get("properties")
    geom = feature.get("geometry")

    lat, lng = None, None
    if geom and geom.get("type") == "Polygon":
        # Extract the first point of the boundary polygon as a rough coordinate
        coords = geom["coordinates"][0][0]
        lng, lat = coords[0], coords[1]
    elif geom and geom.get("type") == "Point":
        lng, lat = geom["coordinates"][0], geom["coordinates"][1]

    records.append(
        (
            props.get("id"),
            props.get("event"),
            props.get("severity"),
            props.get("areaDesc"),
            props.get("effective"),
            lat,
            lng
        )
    )
print(f"Ingested {NUMBER_OF_ALERTS} alerts.");

# 3. Store into SQLite Database

conn = sqlite3.connect(f"public/data/{TABLE_NAME}")
cursor = conn.cursor()

# Isolate the DDL schema definition string into a variable
schema = """
    CREATE TABLE IF NOT EXISTS alerts (
        id TEXT PRIMARY KEY,
        event TEXT,
        severity TEXT,
        area TEXT,
        timestamp TEXT
    )
"""
cursor.execute(schema)

# 2. Safely migrate existing tables by adding missing columns
cursor.execute("PRAGMA table_info(alerts)")
existing_columns = [col[1] for col in cursor.fetchall()]

if "latitude" not in existing_columns:
    cursor.execute("ALTER TABLE alerts ADD COLUMN latitude REAL")
if "longitude" not in existing_columns:
    cursor.execute("ALTER TABLE alerts ADD COLUMN longitude REAL")

cursor.executemany(
    "INSERT OR REPLACE INTO alerts VALUES (?, ?, ?, ?, ?, ?, ?)", records
)
conn.commit()
conn.close()
print(f"Successfully updated public/data/{TABLE_NAME}")