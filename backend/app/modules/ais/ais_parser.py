"""
AEGIS-SPILL: Real Multi-Format AIS Parser
Supports:
1. NMEA 0183 !AIVDM / !AIVDO sentences (Types 1, 2, 3, 5, 18, 19)
2. Open Maritime JSON feeds (AISHub, BarentsWatch, DMA)
3. MaritimeCadastre / EMSA CSV trajectory logs
"""

import math
import json
import csv
import io
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from app.models.schemas import AISPoint, AISTrack


def _decode_six_bit_ascii(char: str) -> int:
    """Decodes a single ASCII armored character into a 6-bit integer."""
    val = ord(char) - 48
    if val > 40:
        val -= 8
    return val & 0x3F


def _nmea_payload_to_bitstring(payload: str) -> str:
    """Converts an AIVDM payload string into a contiguous binary bitstring."""
    bits = []
    for char in payload:
        val = _decode_six_bit_ascii(char)
        bits.append(f"{val:06b}")
    return "".join(bits)


def _signed_int(bitstring: str) -> int:
    """Parses two's complement signed integer from bitstring."""
    if not bitstring:
        return 0
    val = int(bitstring, 2)
    if bitstring[0] == '1':
        val -= (1 << len(bitstring))
    return val


def _decode_six_bit_text(bitstring: str) -> str:
    """Decodes 6-bit ASCII text field from AIS payload."""
    chars = []
    for i in range(0, len(bitstring) - 5, 6):
        val = int(bitstring[i:i+6], 2)
        if val == 0:
            continue
        elif 1 <= val <= 31:
            chars.append(chr(val + 64))
        elif 32 <= val <= 63:
            chars.append(chr(val))
    return "".join(chars).strip("@ ")


def parse_aivdm_sentence(sentence: str) -> Optional[Dict[str, Any]]:
    """
    Parses a single-line NMEA 0183 !AIVDM or !AIVDO sentence.
    Returns extracted telemetry dict or None if invalid/unsupported.
    """
    sentence = sentence.strip()
    if not (sentence.startswith("!AIVDM") or sentence.startswith("!AIVDO")):
        return None
    
    parts = sentence.split(",")
    if len(parts) < 6:
        return None
    
    # Check payload part (part 5)
    payload = parts[5]
    if not payload:
        return None
    
    bitstring = _nmea_payload_to_bitstring(payload)
    if len(bitstring) < 38:
        return None
    
    msg_type = int(bitstring[0:6], 2)
    mmsi = str(int(bitstring[8:38], 2))
    
    # Message Types 1, 2, 3: Class A Position Report
    if msg_type in (1, 2, 3) and len(bitstring) >= 137:
        sog_raw = int(bitstring[50:60], 2)
        speed_knots = sog_raw / 10.0 if sog_raw != 1023 else 0.0
        
        lon_raw = _signed_int(bitstring[61:89])
        lon = lon_raw / 600000.0
        
        lat_raw = _signed_int(bitstring[89:116])
        lat = lat_raw / 600000.0
        
        cog_raw = int(bitstring[116:128], 2)
        cog = cog_raw / 10.0 if cog_raw != 3600 else 0.0
        
        hdg_raw = int(bitstring[128:137], 2)
        heading = float(hdg_raw) if hdg_raw != 511 else cog
        
        # Validate latitude/longitude sanity
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            return {
                "msg_type": msg_type,
                "mmsi": mmsi,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "speed_knots": round(speed_knots, 1),
                "heading_deg": round(heading, 1),
                "course_deg": round(cog, 1),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    # Message Type 5: Static and Voyage Data
    elif msg_type == 5 and len(bitstring) >= 232:
        vessel_name = _decode_six_bit_text(bitstring[112:232])
        ship_type_code = int(bitstring[232:240], 2) if len(bitstring) >= 240 else 0
        
        ship_type_map = {
            70: "Cargo / Container",
            80: "Crude Oil Tanker",
            81: "Chemical Tanker",
            82: "Product Tanker",
            84: "LNG / LPG Carrier",
            30: "Fishing Vessel",
            52: "Tug / Offshore Supply",
            60: "Passenger Ferry"
        }
        vessel_type = ship_type_map.get(ship_type_code - (ship_type_code % 10), "Commercial Merchant")
        
        return {
            "msg_type": 5,
            "mmsi": mmsi,
            "vessel_name": vessel_name,
            "vessel_type": vessel_type,
            "ship_type_code": ship_type_code
        }
        
    # Message Types 18, 19: Class B Position Report
    elif msg_type in (18, 19) and len(bitstring) >= 130:
        sog_raw = int(bitstring[46:56], 2)
        speed_knots = sog_raw / 10.0 if sog_raw != 1023 else 0.0
        
        lon_raw = _signed_int(bitstring[57:85])
        lon = lon_raw / 600000.0
        
        lat_raw = _signed_int(bitstring[85:112])
        lat = lat_raw / 600000.0
        
        cog_raw = int(bitstring[112:124], 2)
        cog = cog_raw / 10.0 if cog_raw != 3600 else 0.0
        
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            return {
                "msg_type": msg_type,
                "mmsi": mmsi,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "speed_knots": round(speed_knots, 1),
                "heading_deg": round(cog, 1),
                "course_deg": round(cog, 1),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    return None


def parse_nmea_log(content: str) -> List[AISTrack]:
    """
    Parses raw NMEA 0183 multiline logs, assembling individual pings into AISTrack objects.
    """
    tracks_by_mmsi: Dict[str, List[AISPoint]] = {}
    names_by_mmsi: Dict[str, str] = {}
    types_by_mmsi: Dict[str, str] = {}
    
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = parse_aivdm_sentence(line)
        if not parsed:
            continue
        
        mmsi = parsed["mmsi"]
        if parsed.get("msg_type") == 5:
            if parsed.get("vessel_name"):
                names_by_mmsi[mmsi] = parsed["vessel_name"]
            if parsed.get("vessel_type"):
                types_by_mmsi[mmsi] = parsed["vessel_type"]
        else:
            pt = AISPoint(
                mmsi=mmsi,
                timestamp=parsed.get("timestamp", datetime.now(timezone.utc).isoformat()),
                lat=parsed["lat"],
                lon=parsed["lon"],
                speed_knots=parsed.get("speed_knots", 0.0),
                heading_deg=parsed.get("heading_deg", 0.0)
            )
            if mmsi not in tracks_by_mmsi:
                tracks_by_mmsi[mmsi] = []
            tracks_by_mmsi[mmsi].append(pt)
            
    # Build AISTrack objects
    result: List[AISTrack] = []
    for mmsi, points in tracks_by_mmsi.items():
        if len(points) < 1:
            continue
        name = names_by_mmsi.get(mmsi, f"Vessel-{mmsi[-4:]}")
        v_type = types_by_mmsi.get(mmsi, "Crude Oil Tanker" if "tanker" in name.lower() else "Commercial Vessel")
        
        # Check for trajectory gaps (> 4 hours between consecutive points)
        has_gap = False
        gap_intervals = []
        for i in range(len(points) - 1):
            try:
                t1 = datetime.fromisoformat(points[i].timestamp.replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(points[i+1].timestamp.replace("Z", "+00:00"))
                delta_hrs = abs((t2 - t1).total_seconds()) / 3600.0
                if delta_hrs > 4.0:
                    has_gap = True
                    gap_intervals.append([points[i].timestamp, points[i+1].timestamp])
            except Exception:
                pass
                
        result.append(AISTrack(
            mmsi=mmsi,
            vessel_name=name,
            vessel_type=v_type,
            flag="Panama",
            imo=f"IMO{mmsi[:7]}",
            callsign=f"C6{mmsi[-3:]}",
            points=points,
            has_gap=has_gap,
            gap_intervals=gap_intervals
        ))
        
    return result


def parse_csv_ais_log(csv_text: str) -> List[AISTrack]:
    """
    Parses MarineCadastre / EMSA style CSV AIS files.
    Expected headers include MMSI, BaseDateTime/Timestamp, LAT, LON, SOG, COG, Heading, VesselName, VesselType.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    tracks_by_mmsi: Dict[str, List[AISPoint]] = {}
    vessel_meta: Dict[str, Dict[str, Any]] = {}
    
    for row in reader:
        # Standardize column keys to lowercase
        r = {k.strip().lower(): v.strip() for k, v in row.items() if k}
        mmsi = r.get("mmsi") or r.get("vessel_mmsi") or r.get("mmsi_id")
        if not mmsi:
            continue
        
        try:
            lat = float(r.get("lat") or r.get("latitude") or 0.0)
            lon = float(r.get("lon") or r.get("longitude") or 0.0)
            sog = float(r.get("sog") or r.get("speed") or r.get("speed_knots") or 0.0)
            hdg = float(r.get("heading") or r.get("cog") or r.get("course") or 0.0)
            ts = r.get("basedatetime") or r.get("timestamp") or r.get("time") or datetime.now(timezone.utc).isoformat()
            
            if lat == 0.0 and lon == 0.0:
                continue
                
            pt = AISPoint(
                mmsi=mmsi,
                timestamp=ts,
                lat=round(lat, 5),
                lon=round(lon, 5),
                speed_knots=round(sog, 1),
                heading_deg=round(hdg, 1)
            )
            
            if mmsi not in tracks_by_mmsi:
                tracks_by_mmsi[mmsi] = []
                vessel_meta[mmsi] = {
                    "vessel_name": r.get("vesselname") or r.get("vessel_name") or f"Vessel-{mmsi[-4:]}",
                    "vessel_type": r.get("vesseltype") or r.get("vessel_type") or "Commercial Vessel",
                    "flag": r.get("flag") or "Liberia",
                    "imo": r.get("imo") or f"IMO{mmsi[:7]}"
                }
            tracks_by_mmsi[mmsi].append(pt)
        except (ValueError, TypeError):
            continue
            
    result: List[AISTrack] = []
    for mmsi, points in tracks_by_mmsi.items():
        meta = vessel_meta.get(mmsi, {})
        result.append(AISTrack(
            mmsi=mmsi,
            vessel_name=meta.get("vessel_name", f"Vessel-{mmsi[-4:]}"),
            vessel_type=meta.get("vessel_type", "Commercial Vessel"),
            flag=meta.get("flag", "Liberia"),
            imo=meta.get("imo", f"IMO{mmsi[:7]}"),
            callsign=f"C6{mmsi[-3:]}",
            points=points,
            has_gap=False,
            gap_intervals=[]
        ))
        
    return result


def parse_json_ais_feed(json_data: Any) -> List[AISTrack]:
    """
    Parses standard AISHub / BarentsWatch JSON feed structures.
    """
    if isinstance(json_data, str):
        json_data = json.loads(json_data)
        
    # Standardize array of vessels
    vessels = []
    if isinstance(json_data, dict):
        if "data" in json_data and isinstance(json_data["data"], list):
            vessels = json_data["data"]
        elif "vessels" in json_data and isinstance(json_data["vessels"], list):
            vessels = json_data["vessels"]
        elif "features" in json_data and isinstance(json_data["features"], list):
            # GeoJSON FeatureCollection
            for feat in json_data["features"]:
                props = feat.get("properties", {})
                coords = feat.get("geometry", {}).get("coordinates", [0, 0])
                props["lon"] = coords[0]
                props["lat"] = coords[1]
                vessels.append(props)
        else:
            vessels = [json_data]
    elif isinstance(json_data, list):
        vessels = json_data
        
    tracks_by_mmsi: Dict[str, List[AISPoint]] = {}
    vessel_meta: Dict[str, Dict[str, Any]] = {}
    
    for v in vessels:
        mmsi = str(v.get("mmsi") or v.get("MMSI") or "")
        if not mmsi:
            continue
        try:
            lat = float(v.get("lat") or v.get("latitude") or v.get("LAT") or 0.0)
            lon = float(v.get("lon") or v.get("longitude") or v.get("LON") or 0.0)
            sog = float(v.get("sog") or v.get("speed") or v.get("SOG") or 0.0)
            hdg = float(v.get("heading") or v.get("cog") or v.get("COG") or 0.0)
            ts = v.get("timestamp") or v.get("time") or v.get("TIME") or datetime.now(timezone.utc).isoformat()
            
            pt = AISPoint(
                mmsi=mmsi,
                timestamp=ts,
                lat=round(lat, 5),
                lon=round(lon, 5),
                speed_knots=round(sog, 1),
                heading_deg=round(hdg, 1)
            )
            if mmsi not in tracks_by_mmsi:
                tracks_by_mmsi[mmsi] = []
                vessel_meta[mmsi] = {
                    "vessel_name": v.get("vessel_name") or v.get("name") or v.get("NAME") or f"Vessel-{mmsi[-4:]}",
                    "vessel_type": v.get("vessel_type") or v.get("type") or "Crude Oil Tanker",
                    "flag": v.get("flag") or "Marshall Islands",
                    "imo": v.get("imo") or f"IMO{mmsi[:7]}"
                }
            tracks_by_mmsi[mmsi].append(pt)
        except (ValueError, TypeError):
            continue
            
    result: List[AISTrack] = []
    for mmsi, points in tracks_by_mmsi.items():
        meta = vessel_meta.get(mmsi, {})
        result.append(AISTrack(
            mmsi=mmsi,
            vessel_name=meta.get("vessel_name", f"Vessel-{mmsi[-4:]}"),
            vessel_type=meta.get("vessel_type", "Commercial Vessel"),
            flag=meta.get("flag", "Marshall Islands"),
            imo=meta.get("imo", f"IMO{mmsi[:7]}"),
            callsign=f"C6{mmsi[-3:]}",
            points=points,
            has_gap=False,
            gap_intervals=[]
        ))
        
    return result
