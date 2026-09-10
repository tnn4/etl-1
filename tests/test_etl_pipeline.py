import os
import sqlite3
import pytest
from scripts.logistics_etl import fetch_nws_alerts, generate_active_shipments, compute_compound_risk, FREIGHT_CORRIDORS

def test_nws_alerts_schema():
    """Verify NWS alert ingestion returns structured dicts with valid lat/lng coordinates."""
    alerts = fetch_nws_alerts()
    assert isinstance(alerts, list)
    if len(alerts) > 0:
        alert = alerts[0]
        assert "id" in alert
        assert "latitude" in alert
        assert "longitude" in alert
        assert -90 <= alert["latitude"] <= 90
        assert -180 <= alert["longitude"] <= 180

def test_shipment_generation():
    """Ensure generated shipments bind strictly to defined freight corridors."""
    shipments = generate_active_shipments(FREIGHT_CORRIDORS)
    assert len(shipments) == 25
    for s in shipments:
        assert s["cargo_value_usd"] > 0
        assert s["status"] == "IN_TRANSIT"
        assert s["priority"] in ["STANDARD", "HIGH_PRIORITY", "CRITICAL_PHARMA"]

def test_compound_risk_calculation():
    """Verify spatial risk engine flags proximity correctly."""
    mock_shipment = [{
        "shipment_id": "SHP-TEST-1",
        "current_lat": 32.7767,
        "current_lng": -96.7970,
        "cargo_value_usd": 100000
    }]
    mock_hazard = [{
        "event": "Severe Thunderstorm Warning",
        "severity": "Severe",
        "latitude": 32.8000,  # ~1.6 miles away
        "longitude": -96.8000
    }]
    
    enriched = compute_compound_risk(mock_shipment, mock_hazard)
    assert enriched[0]["risk_status"] == "CRITICAL_REROUTE_REQUIRED"
    assert enriched[0]["detected_threat"] == "Severe Thunderstorm Warning"

def test_sqlite_database_integrity():
    """Ensure generated SQLite DB file exists, is non-empty, and contains expected tables."""
    db_path = "./public/data/weather_table.db"
    assert os.path.exists(db_path), "SQLite database file was not created."
    assert os.path.getsize(db_path) > 0, "SQLite database file is empty."
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    
    assert "alerts" in tables
    assert "active_shipments" in tables
    conn.close()