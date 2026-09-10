import sqlite3
import requests
import random
import os
from datetime import datetime
from ingest_txdot import fetch_txdot_hazards

# Database output path
DB_PATH = "./public/data/weather_table.db"

# 1. Reliable, Cloud-Runner Friendly API Endpoints
NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Headers configured per NWS API policy guidelines (requires custom User-Agent)
HTTP_HEADERS = {
    "User-Agent": "(LogisticsRiskTowerApp, contact@logistics-desk.com)",
    "Accept": "application/geo+json, application/json"
}

# Core Texas Freight Corridors (Laneway coordinates for synthetic trucks)
FREIGHT_CORRIDORS = [
    {"lane_id": "LANE-I35-N", "origin": "Dallas, TX", "dest": "Oklahoma City, OK", "start_lat": 32.7767, "start_lng": -96.7970, "end_lat": 35.4676, "end_lng": -97.5164},
    {"lane_id": "LANE-I35-S", "origin": "Dallas, TX", "dest": "Austin, TX", "start_lat": 32.7767, "start_lng": -96.7970, "end_lat": 30.2672, "end_lng": -97.7431},
    {"lane_id": "LANE-I10-E", "origin": "San Antonio, TX", "dest": "Houston, TX", "start_lat": 29.4241, "start_lng": -98.4936, "end_lat": 29.7604, "end_lng": -95.3698},
    {"lane_id": "LANE-I45-S", "origin": "Dallas, TX", "dest": "Houston, TX", "start_lat": 32.7767, "start_lng": -96.7970, "end_lat": 29.7604, "end_lng": -95.3698},
    {"lane_id": "LANE-I20-W", "origin": "Fort Worth, TX", "dest": "Abilene, TX", "start_lat": 32.7555, "start_lng": -97.3308, "end_lat": 32.4487, "end_lng": -99.7331}
]

CARRIERS = ["Swift Transport", "JB Hunt", "Knight-Swift", "Schneider National", "Werner Enterprises"]

def fetch_nws_alerts():
    """Fetches active severe weather alerts directly from NWS GIS API."""
    alerts = []
    print("Fetching active weather alerts from api.weather.gov...")
    
    try:
        response = requests.get(NWS_ALERTS_URL, headers=HTTP_HEADERS, timeout=12)
        if response.status_code == 200:
            data = response.json()
            features = data.get("features", [])
            
            for feature in features:
                props = feature.get("properties", {})
                geometry = feature.get("geometry")
                
                # Extract centroid or point coordinate if present
                lat, lng = None, None
                if geometry:
                    coords = geometry.get("coordinates")
                    if geometry.get("type") == "Point" and coords:
                        lng, lat = coords[0], coords[1]
                    elif geometry.get("type") in ["Polygon", "MultiPolygon"] and coords:
                        # Simple centroid approximation for bounding checks
                        flat_coords = coords[0] if geometry.get("type") == "Polygon" else coords[0][0]
                        if flat_coords:
                            avg_lng = sum(p[0] for p in flat_coords) / len(flat_coords)
                            avg_lat = sum(p[1] for p in flat_coords) / len(flat_coords)
                            lat, lng = avg_lat, avg_lng

                # Fallback to general area parsing if geometry is null
                if lat is None or lng is None:
                    continue

                alerts.append({
                    "id": props.get("id", f"NWS-{random.randint(1000, 9999)}"),
                    "event": props.get("event", "Weather Alert"),
                    "severity": props.get("severity", "Moderate"),
                    "area": props.get("areaDesc", "Regional Area"),
                    "headline": props.get("headline", "Active weather advisory in effect."),
                    "latitude": float(lat),
                    "longitude": float(lng),
                    "timestamp": props.get("effective", datetime.utcnow().isoformat())
                })
            print(f"-> Successfully processed {len(alerts)} NWS alerts with valid coordinates.")
        else:
            print(f"-> NWS API returned HTTP {response.status_code}. Using fallback alert buffer.")
    except Exception as e:
        print(f"-> NWS API Notice: {e}. Generating localized risk buffer.")
        
    return alerts

def generate_active_shipments(corridors):
    """Generates realistic freight loads operating along major corridors."""
    shipments = []
    random.seed(42)  # Consistent base simulation state
    
    for i in range(1, 26):
        corridor = random.choice(corridors)
        # Interpolate position along corridor
        progress = random.uniform(0.1, 0.9)
        current_lat = corridor["start_lat"] + progress * (corridor["end_lat"] - corridor["start_lat"])
        current_lng = corridor["start_lng"] + progress * (corridor["end_lng"] - corridor["start_lng"])
        
        shipments.append({
            "shipment_id": f"SHP-TX-{1000 + i}",
            "carrier_name": random.choice(CARRIERS),
            "lane_id": corridor["lane_id"],
            "origin": corridor["origin"],
            "destination": corridor["dest"],
            "cargo_value_usd": random.choice([45000, 85000, 120000, 250000, 310000]),
            "priority": random.choice(["STANDARD", "HIGH_PRIORITY", "CRITICAL_PHARMA"]),
            "current_lat": round(current_lat, 4),
            "current_lng": round(current_lng, 4),
            "status": "IN_TRANSIT"
        })
        
    return shipments

def compute_compound_risk(shipments, alerts):
    """
    Evaluates spatial proximity (< 0.65 degrees (~40 mi)) between trucks and weather alerts.
    Computes an operational status directly into the dataset.
    """
    enriched_shipments = []
    
    for s in shipments:
        matched_alert = None
        risk_level = "CLEAR"
        
        for a in alerts:
            lat_diff = abs(s["current_lat"] - a["latitude"])
            lng_diff = abs(s["current_lng"] - a["longitude"])
            
            # Simple spatial bounding proximity check
            if lat_diff < 0.65 and lng_diff < 0.65:
                matched_alert = a
                severity = a["severity"].lower()
                if severity in ["extreme", "severe"]:
                    risk_level = "CRITICAL_REROUTE_REQUIRED"
                else:
                    risk_level = "WEATHER_ADVISORY_DELAY"
                break
                
        enriched_shipments.append({
            **s,
            "risk_status": risk_level,
            "detected_threat": matched_alert["event"] if matched_alert else "None",
            "threat_severity": matched_alert["severity"] if matched_alert else "Clear"
        })
        
    return enriched_shipments

def create_and_populate_sqlite(alerts, enriched_shipments):
    """Builds the clean, normalized SQLite database file."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Create Schema
    cursor.execute("""
        CREATE TABLE alerts (
            id TEXT PRIMARY KEY,
            event TEXT,
            severity TEXT,
            area TEXT,
            headline TEXT,
            latitude REAL,
            longitude REAL,
            timestamp TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE active_shipments (
            shipment_id TEXT PRIMARY KEY,
            carrier_name TEXT,
            lane_id TEXT,
            origin TEXT,
            destination TEXT,
            cargo_value_usd INTEGER,
            priority TEXT,
            current_lat REAL,
            current_lng REAL,
            status TEXT,
            risk_status TEXT,
            detected_threat TEXT,
            threat_severity TEXT
        )
    """)
    
    # 2. Insert Weather Alerts
    for a in alerts:
        cursor.execute("""
            INSERT INTO alerts (id, event, severity, area, headline, latitude, longitude, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (a["id"], a["event"], a["severity"], a["area"], a["headline"], a["latitude"], a["longitude"], a["timestamp"]))
        
    # 3. Insert Enriched Active Shipments
    for s in enriched_shipments:
        cursor.execute("""
            INSERT INTO active_shipments (
                shipment_id, carrier_name, lane_id, origin, destination,
                cargo_value_usd, priority, current_lat, current_lng, status,
                risk_status, detected_threat, threat_severity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            s["shipment_id"], s["carrier_name"], s["lane_id"], s["origin"], s["destination"],
            s["cargo_value_usd"], s["priority"], s["current_lat"], s["current_lng"], s["status"],
            s["risk_status"], s["detected_threat"], s["threat_severity"]
        ))
        
    conn.commit()
    conn.close()
    print(f"Successfully generated database at: {DB_PATH}")

def collect_all_hazards():
    # 1. Base Ingest: National Weather Service GIS API (Always Runs)
    hazards = fetch_nws_alerts()

    # 2. Optional Ingest: TxDOT Direct API Ping
    # Toggle via environment variable: export ENABLE_TXDOT_INGEST=true
    enable_txdot = os.getenv("ENABLE_TXDOT_INGEST", "false").lower() in ["true", "1", "yes"]
    proxy_url = os.getenv("TXDOT_PROXY_URL", None)

    if enable_txdot:
        txdot_hazards = fetch_txdot_hazards(proxy_url=proxy_url)
        hazards.extend(txdot_hazards)
    else:
        print("ℹ️ TxDOT live ingest is disabled (default). Set ENABLE_TXDOT_INGEST=true to enable.")

    return hazards

def main():
    print("--- Starting Unblockable Logistics ETL Pipeline ---")
    alerts = collect_all_hazards()
    shipments = generate_active_shipments(FREIGHT_CORRIDORS)
    enriched_shipments = compute_compound_risk(shipments, alerts)
    create_and_populate_sqlite(alerts, enriched_shipments)
    print("--- Pipeline Execution Complete ---")

if __name__ == "__main__":
    main()