import os
import random
import sqlite3
import requests
from datetime import datetime, timedelta

os.makedirs("public/data", exist_ok=True)
DB_PATH = "public/data/weather_table.db"

# Public TxDOT Live Incidents Feed
TXDOT_INCIDENTS_URL = "https://its.txdot.gov/ITS_API/api/Incidents"

HUBS = {
    "DFW": ("Dallas / Fort Worth Hub", 32.8998, -97.0403),
    "ORD": ("Chicago O'Hare Hub", 41.9742, -87.9073),
    "LAX": ("Los Angeles Gateway", 33.9425, -118.4081),
    "HOU": ("Houston Intermodal Hub", 29.7604, -95.3698),
    "SAT": ("San Antonio Freight Hub", 29.4241, -98.4936)
}

CARRIERS = ["Swift Transport", "FedEx Freight", "JB Hunt", "Knight Transportation", "XPO Logistics"]

def fetch_txdot_hazards(proxy_url=None):
    """Fetches real-time highway hazards and road closures from TxDOT."""
    hazards = []
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    
    try:
        response = requests.get(TXDOT_INCIDENTS_URL, proxies=proxies, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for item in data:
                lat = item.get("Latitude")
                lng = item.get("Longitude")
                if lat and lng:
                    hazards.append({
                        "id": str(item.get("ID", random.randint(1000, 9999))),
                        "event": item.get("Name", "Traffic Incident"),
                        "severity": "Moderate",
                        "area": item.get("MainRoad", "Unknown Highway"),
                        "headline": item.get("Description", "No details provided."),
                        "latitude": float(lat),
                        "longitude": float(lng),
                        "timestamp": datetime.utcnow().isoformat()
                    })
    except Exception as e:
        print(f"Warning: Could not fetch TxDOT incident feed ({e}). Proceeding with empty hazard table.")
    return hazards

def build_logistics_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS highway_hazards (
            hazard_id TEXT PRIMARY KEY,
            road_name TEXT,
            event_type TEXT,
            description TEXT,
            latitude REAL,
            longitude REAL,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS surface_lanes (
            lane_id TEXT PRIMARY KEY,
            origin_hub TEXT,
            dest_hub TEXT,
            origin_lat REAL,
            origin_lng REAL,
            dest_lat REAL,
            dest_lng REAL,
            target_transit_hours INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_shipments (
            shipment_id TEXT PRIMARY KEY,
            lane_id TEXT,
            carrier_name TEXT,
            cargo_value_usd REAL,
            current_lat REAL,
            current_lng REAL,
            eta_timestamp TEXT,
            status TEXT,
            FOREIGN KEY(lane_id) REFERENCES surface_lanes(lane_id)
        )
    """)

    hazards = fetch_txdot_hazards()
    if hazards:
        cursor.executemany(
            "INSERT OR REPLACE INTO highway_hazards VALUES (?,?,?,?,?,?,?)", 
            [(h["id"], h["area"], h["event"], h["headline"], h["latitude"], h["longitude"], h["timestamp"]) for h in hazards]
        )
        print(f"Successfully ingested {len(hazards)} live road hazards from TxDOT.")

    lanes = [
        ("LANE-DFW-HOU", "DFW", "HOU", 32.8998, -97.0403, 29.7604, -95.3698, 4),
        ("LANE-DFW-SAT", "DFW", "SAT", 32.8998, -97.0403, 29.4241, -98.4936, 5),
        ("LANE-DFW-ORD", "DFW", "ORD", 32.8998, -97.0403, 41.9742, -87.9073, 18),
        ("LANE-LAX-DFW", "LAX", "DFW", 33.9425, -118.4081, 32.8998, -97.0403, 24)
    ]
    
    cursor.executemany("INSERT OR REPLACE INTO surface_lanes VALUES (?,?,?,?,?,?,?,?)", lanes)

    shipments = []
    now = datetime.utcnow()
    
    for idx, (lane_id, orig, dest, o_lat, o_lng, d_lat, d_lng, hrs) in enumerate(lanes):
        for s_idx in range(3):
            shp_id = f"SHP-{orig}{dest}-{100 + idx * 3 + s_idx}"
            carrier = random.choice(CARRIERS)
            value = round(random.uniform(25000.0, 150000.0), 2)
            
            progress = random.uniform(0.15, 0.85)
            c_lat = round(o_lat + (d_lat - o_lat) * progress, 4)
            c_lng = round(o_lng + (d_lng - o_lng) * progress, 4)
            
            eta = (now + timedelta(hours=random.randint(1, hrs))).strftime("%Y-%m-%d %H:%M UTC")
            shipments.append((shp_id, lane_id, carrier, value, c_lat, c_lng, eta, "IN_TRANSIT"))

    cursor.executemany("INSERT OR REPLACE INTO active_shipments VALUES (?,?,?,?,?,?,?,?)", shipments)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    build_logistics_database()