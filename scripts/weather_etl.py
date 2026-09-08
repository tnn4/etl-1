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

# List of major population/logistics hubs (NWS Station IDs)
METRO_STATIONS = {
    "KJFK": ("New York City", 40.6413, -73.7781),
    "KORD": ("Chicago", 41.9742, -87.9073),
    "KLAX": ("Los Angeles", 33.9425, -118.4081),
    "KDFW": ("Dallas / Fort Worth", 32.8998, -97.0403),
    "KATL": ("Atlanta", 33.6407, -84.4277),
    "KSEA": ("Seattle", 47.4502, -122.3088),
    "KMIA": ("Miami", 25.7959, -80.2870),
    "KDEN": ("Denver", 39.8561, -104.6737)
}

headers = {"User-Agent": "LogisticsDashboardPrototype/1.0"}

temp_records = []

for station_id, (city_name, lat, lng) in METRO_STATIONS.items():
    try:
        url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            obs = res.json().get("properties", {})
            temp_c = obs.get("temperature", {}).get("value")
            
            # Convert C to F
            temp_f = round((temp_c * 9/5) + 32, 1) if temp_c is not None else None
            
            temp_records.append((station_id, city_name, temp_f, lat, lng))
    except Exception as e:
        print(f"Failed to fetch {station_id}: {e}")

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

schema_temp = """
    CREATE TABLE IF NOT EXISTS metro_temps (
        station_id TEXT PRIMARY KEY,
        city TEXT,
        temp_f REAL,
        latitude REAL,
        longitude REAL
    )
"""

cursor.execute(schema_temp)
cursor.executemany(
    "INSERT OR REPLACE INTO metro_temps VALUES (?,?,?,?,?)", temp_records
)

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
print(f"Updated {len(temp_records)} metro temperatures.")

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