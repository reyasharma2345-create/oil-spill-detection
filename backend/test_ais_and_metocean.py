"""
AEGIS-SPILL: Test Suite for Real AIS Ingestion & Metocean Forcing
"""

import sys
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.modules.ais.ais_parser import (
    parse_aivdm_sentence, parse_nmea_log, parse_csv_ais_log, parse_json_ais_feed
)
from app.modules.ais.ais_feed import ais_feed_service
from app.modules.ais.feasibility_engine import evaluate_vessel_feasibility
from app.modules.environment.live_metocean import metocean_service
from app.api.cases import CASES_DB


def test_nmea_parsing():
    print("\n--- 1. Testing NMEA 0183 !AIVDM Parser ---")
    sample_sentence = "!AIVDM,1,1,,B,13u?etPv2;0n:nvKNwo>4?wb00SG,0*26"
    res = parse_aivdm_sentence(sample_sentence)
    assert res is not None, "Failed to parse AIVDM sentence"
    assert res["mmsi"] == "265547250", f"Expected MMSI 265547250, got {res['mmsi']}"
    assert res["speed_knots"] > 0, "Expected positive speed"
    print(f"PASS: MMSI {res['mmsi']} | Lat {res['lat']} | Lon {res['lon']} | Speed {res['speed_knots']} kts")


def test_csv_parsing():
    print("\n--- 2. Testing MarineCadastre CSV Parser ---")
    sample_csv = """MMSI,BaseDateTime,LAT,LON,SOG,COG,Heading,VesselName,VesselType
352001892,2026-09-07T12:00:00,18.92,72.10,12.5,45.0,45.0,MT Pacific Star,Crude Oil Tanker
352001892,2026-09-07T13:00:00,19.05,72.25,12.8,44.0,44.0,MT Pacific Star,Crude Oil Tanker
"""
    tracks = parse_csv_ais_log(sample_csv)
    assert len(tracks) == 1, f"Expected 1 track, got {len(tracks)}"
    assert len(tracks[0].points) == 2, f"Expected 2 points, got {len(tracks[0].points)}"
    print(f"PASS: Track {tracks[0].vessel_name} ({tracks[0].mmsi}) with {len(tracks[0].points)} points")


def test_metocean_service():
    print("\n--- 3. Testing Copernicus / Open-Meteo Live Metocean Service ---")
    data = metocean_service.get_forcing_vectors(18.9, 72.0)
    assert "wind_speed_ms" in data, "Missing wind_speed_ms"
    assert "current_speed_ms" in data, "Missing current_speed_ms"
    print(f"PASS: Wind: {data['wind_speed_ms']} m/s @ {data['wind_dir_deg']}° | Curr: {data['current_speed_ms']} m/s @ {data['current_dir_deg']}°")


def test_candidate_feasibility():
    print("\n--- 4. Testing Reverse-Lagrangian Feasibility Filtering ---")
    case = CASES_DB.get("MUM-2024-0512")
    assert case is not None, "Case MUM-2024-0512 not found"
    
    # Query AOI vessels
    tracks = ais_feed_service.get_vessels_in_bbox(71.5, 18.0, 73.5, 19.8)
    assert len(tracks) > 0, "No tracks generated for AOI"
    
    feasible_count = 0
    for t in tracks:
        f = evaluate_vessel_feasibility(t, case.origin_field)
        if f.is_feasible:
            feasible_count += 1
            print(f"  [FEASIBLE] {t.vessel_name} ({t.mmsi}) - Min Dist: {f.min_distance_to_origin_km} km (Required Speed: {f.required_speed_knots} kts)")
        else:
            print(f"  [EXCLUDED] {t.vessel_name} ({t.mmsi}) - {f.rejection_reasons[0]}")
            
    print(f"PASS: Evaluated {len(tracks)} vessels ({feasible_count} feasible candidates).")


if __name__ == "__main__":
    test_nmea_parsing()
    test_csv_parsing()
    test_metocean_service()
    test_candidate_feasibility()
    print("\nALL AIS & METOCEAN INTEGRATION TESTS PASSED SUCCESSFULLY!")
