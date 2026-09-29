import asyncio
import json
import math
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any
import websockets
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime, timezone


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

app = Flask(__name__)
frontend_origins = [
    "null",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5001",
    "http://127.0.0.1:5001",
]
vercel_frontend_origin = os.getenv("OCEANOVA_FRONTEND_ORIGIN", "").strip().rstrip("/")
if vercel_frontend_origin:
    frontend_origins.append(vercel_frontend_origin)
codespace_name = os.getenv("CODESPACE_NAME")
forwarding_domain = os.getenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")
if codespace_name and forwarding_domain:
    frontend_origins.append(
        f"https://{codespace_name}-8000.{forwarding_domain}"
    )
CORS(app, resources={r"/api/*": {"origins": frontend_origins}})

AISSTREAM_API_KEY = os.getenv("AISSTREAM_API_KEY")
AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"
AISSTREAM_BOUNDING_BOXES = json.loads(os.getenv(
    "AISSTREAM_BOUNDING_BOXES",
    "[[[90, -180], [-90, 180]]]"
))
AISSTREAM_CACHE_TTL_SECONDS = int(os.getenv("AISSTREAM_CACHE_TTL_SECONDS", "300"))
AISSTREAM_CACHE_MAX_VESSELS = int(os.getenv("AISSTREAM_CACHE_MAX_VESSELS", "100000"))
AISSTREAM_RECONNECT_MAX_SECONDS = 30

_vessel_cache = OrderedDict()
_cache_lock = threading.RLock()
_collector_start_lock = threading.Lock()
_collector_thread = None
_collector_state = {
    "status": "stopped",
    "last_message_at": None,
    "last_error": None,
}


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def distance_km(lat1, lon1, lat2, lon2):

    R = 6371.0

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return R * c


# ============================================================
# BEARING FROM SHIP TO TARGET
# ============================================================

def bearing_to_target(
    ship_lat,
    ship_lon,
    target_lat,
    target_lon
):

    lat1 = math.radians(ship_lat)
    lat2 = math.radians(target_lat)

    dlon = math.radians(
        target_lon - ship_lon
    )

    y = (
        math.sin(dlon)
        * math.cos(lat2)
    )

    x = (
        math.cos(lat1)
        * math.sin(lat2)
        -
        math.sin(lat1)
        * math.cos(lat2)
        * math.cos(dlon)
    )

    bearing = math.degrees(
        math.atan2(y, x)
    )

    return (bearing + 360) % 360


# ============================================================
# CHECK MOVEMENT TOWARDS TARGET
# ============================================================

def ship_is_approaching(
    ship_lat,
    ship_lon,
    course,
    target_lat,
    target_lon
):

    required_bearing = bearing_to_target(
        ship_lat,
        ship_lon,
        target_lat,
        target_lon
    )

    difference = abs(
        course - required_bearing
    )

    if difference > 180:
        difference = 360 - difference

    return difference <= 45


# ============================================================
# AISSTREAM API
# ============================================================

def aisstream_bounding_boxes(target_lat, target_lon, radius):

    latitude_delta = radius / 111.0
    longitude_delta = min(
        180.0,
        radius / (
            111.0
            * max(
                abs(math.cos(math.radians(target_lat))),
                0.01
            )
        )
    )

    south = max(-90.0, target_lat - latitude_delta)
    north = min(90.0, target_lat + latitude_delta)
    west = target_lon - longitude_delta
    east = target_lon + longitude_delta

    if west < -180.0:
        return [
            [[north, west + 360.0], [south, 180.0]],
            [[north, -180.0], [south, east]]
        ]

    if east > 180.0:
        return [
            [[north, west], [south, 180.0]],
            [[north, -180.0], [south, east - 360.0]]
        ]

    return [[[north, west], [south, east]]]


def normalize_aisstream_position(message):

    position = message.get("Message", {}).get("PositionReport")
    if not position:
        return None

    metadata = message.get("MetaData") or {}
    latitude = position.get("Latitude", metadata.get("latitude"))
    longitude = position.get("Longitude", metadata.get("longitude"))

    if latitude is None or longitude is None:
        return None

    speed = position.get("Sog", 0)
    course = position.get("Cog", 0)

    try:
        speed = float(speed)
    except (TypeError, ValueError):
        speed = 0

    try:
        course = float(course)
    except (TypeError, ValueError):
        course = 0

    if speed >= 102.3 or speed < 0:
        speed = 0

    if course >= 360 or course < 0:
        course = 0

    return {
        "imo": None,
        "mmsi": position.get("UserID", metadata.get("MMSI")),
        "name": metadata.get("ShipName") or "Unknown",
        "vessel_type": metadata.get("ShipType") or "Unknown",
        "last_position": {
            "latitude": latitude,
            "longitude": longitude,
            "speed_knots": speed,
            "course_degrees": course,
            "timestamp": metadata.get("time_utc")
        }
    }


def _set_collector_state(**values):

    with _cache_lock:
        _collector_state.update(values)


def _cache_vessel(vessel):

    position = vessel["last_position"]
    vessel_id = vessel.get("mmsi") or (
        position["latitude"],
        position["longitude"]
    )
    vessel_id = str(vessel_id)
    received_at = time.monotonic()

    with _cache_lock:
        _vessel_cache[vessel_id] = (vessel, received_at)
        _vessel_cache.move_to_end(vessel_id)
        while len(_vessel_cache) > AISSTREAM_CACHE_MAX_VESSELS:
            _vessel_cache.popitem(last=False)
        _collector_state.update({
            "status": "connected",
            "last_message_at": datetime.now(timezone.utc).isoformat(),
            "last_error": None,
        })


def get_cached_aisstream_vessels():

    now = time.monotonic()
    with _cache_lock:
        while _vessel_cache:
            _, (_, received_at) = next(iter(_vessel_cache.items()))
            if now - received_at <= AISSTREAM_CACHE_TTL_SECONDS:
                break
            _vessel_cache.popitem(last=False)
        return [vessel for vessel, _ in _vessel_cache.values()]


def get_aisstream_status():

    with _cache_lock:
        status = dict(_collector_state)
        status["cached_positions"] = len(_vessel_cache)
        return status


async def _run_aisstream_collector():

    reconnect_delay = 1
    while True:
        try:
            _set_collector_state(status="connecting", last_error=None)
            async with websockets.connect(
                AISSTREAM_URL,
                open_timeout=8,
                close_timeout=5,
                ping_interval=20,
                ping_timeout=20,
                compression="deflate",
                max_queue=1024,
            ) as websocket:
                await websocket.send(json.dumps({
                    "APIKey": AISSTREAM_API_KEY,
                    "BoundingBoxes": AISSTREAM_BOUNDING_BOXES,
                    "FilterMessageTypes": ["PositionReport"]
                }))
                _set_collector_state(status="subscribing")

                async for message_json in websocket:
                    message = json.loads(message_json)
                    message_type = message.get("MessageType")

                    if message_type == "SubscriptionConfirmation":
                        _set_collector_state(
                            status="connected",
                            last_error=None
                        )
                        reconnect_delay = 1
                    elif message_type == "Error":
                        raise RuntimeError(
                            message.get("Error", "AISstream rejected the subscription.")
                        )
                    elif message_type == "PositionReport":
                        vessel = normalize_aisstream_position(message)
                        if vessel:
                            _cache_vessel(vessel)

                raise ConnectionError("AISstream closed the connection.")
        except Exception as error:
            _set_collector_state(
                status="reconnecting",
                last_error=str(error)
            )
            print(f"AISstream collector reconnecting: {error}")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(
                reconnect_delay * 2,
                AISSTREAM_RECONNECT_MAX_SECONDS
            )


def _collector_thread_main():

    asyncio.run(_run_aisstream_collector())


def start_aisstream_collector():

    global _collector_thread

    if not AISSTREAM_API_KEY:
        _set_collector_state(
            status="missing_key",
            last_error="AISSTREAM_API_KEY is not configured."
        )
        return

    with _collector_start_lock:
        if _collector_thread and _collector_thread.is_alive():
            return
        _collector_thread = threading.Thread(
            target=_collector_thread_main,
            name="aisstream-cache",
            daemon=True,
        )
        _collector_thread.start()


def _get_aisstream_cache():

    if not AISSTREAM_API_KEY:
        return None, "AISstream API key is missing. Set AISSTREAM_API_KEY in backend/.env."

    start_aisstream_collector()
    return get_cached_aisstream_vessels(), None


# ============================================================
# VESSEL TYPE RISK
# ============================================================

def vessel_type_risk(vessel_type):

    vessel_type = str(
        vessel_type
    ).lower()

    if "oil tanker" in vessel_type:
        return 35

    if "tanker" in vessel_type:
        return 30

    if "chemical" in vessel_type:
        return 30

    if "lng" in vessel_type:
        return 25

    if "lpg" in vessel_type:
        return 25

    if "gas" in vessel_type:
        return 20

    if "cargo" in vessel_type:
        return 10

    if "container" in vessel_type:
        return 8

    return 3


# ============================================================
# DISTANCE RISK
# ============================================================

def distance_risk(distance):

    if distance <= 2:
        return 40

    if distance <= 5:
        return 35

    if distance <= 10:
        return 28

    if distance <= 25:
        return 18

    if distance <= 50:
        return 8

    return 0


# ============================================================
# SPEED RISK
# ============================================================

def speed_risk(speed):

    if speed >= 20:
        return 15

    if speed >= 15:
        return 12

    if speed >= 8:
        return 8

    if speed > 0:
        return 3

    return 0


# ============================================================
# SHIP RISK
# ============================================================

def calculate_ship_risk(
    distance,
    speed,
    vessel_type,
    approaching
):

    score = 0

    score += distance_risk(
        distance
    )

    score += speed_risk(
        speed
    )

    score += vessel_type_risk(
        vessel_type
    )

    if approaching:
        score += 30

    return min(
        round(score, 2),
        100
    )


# ============================================================
# DANGER LEVEL
# ============================================================

def danger_level(score):

    if score >= 70:
        return "VERY HIGH"

    if score >= 51:
        return "HIGH"

    if score >= 26:
        return "MEDIUM"

    return "LOW"


# ============================================================
# PROCESS VESSEL
# ============================================================

def process_vessel(
    vessel,
    target_lat,
    target_lon,
    radius
):

    try:

        position = vessel.get(
            "last_position",
            {}
        )

        ship_lat = position.get(
            "latitude"
        )

        ship_lon = position.get(
            "longitude"
        )

        if ship_lat is None:
            return None

        if ship_lon is None:
            return None

        ship_lat = float(
            ship_lat
        )

        ship_lon = float(
            ship_lon
        )

        distance = distance_km(
            target_lat,
            target_lon,
            ship_lat,
            ship_lon
        )

        if distance > radius:
            return None

        speed = float(
            position.get(
                "speed_knots",
                0
            ) or 0
        )

        course = float(
            position.get(
                "course_degrees",
                0
            ) or 0
        )

        vessel_type = vessel.get(
            "vessel_type",
            vessel.get(
                "type",
                "Unknown"
            )
        )

        approaching = speed >= 1 and ship_is_approaching(
            ship_lat,
            ship_lon,
            course,
            target_lat,
            target_lon
        )
        if speed < 1:
            direction_relation = "Unknown / stationary"
        elif approaching:
            direction_relation = "Toward target"
        else:
            direction_relation = "Not toward target"

        risk = calculate_ship_risk(
            distance,
            speed,
            vessel_type,
            approaching
        )

        return {

            "imo":
                vessel.get("imo"),

            "mmsi":
                vessel.get("mmsi"),

            "name":
                vessel.get(
                    "name",
                    "Unknown"
                ),

            "vessel_type":
                vessel_type,

            "flag":
                vessel.get("flag"),

            "latitude":
                ship_lat,

            "longitude":
                ship_lon,

            "distance_km":
                round(
                    distance,
                    2
                ),

            "speed_knots":
                speed,

            "course_degrees":
                course,

            "direction_to_target":
                round(
                    bearing_to_target(
                        ship_lat,
                        ship_lon,
                        target_lat,
                        target_lon
                    ),
                    2
                ),

            "approaching_target":
                approaching,

            "direction_relation":
                direction_relation,

            "risk_score":
                risk,

            "danger_level":
                danger_level(risk),

            "ais_timestamp":
                position.get(
                    "timestamp"
                )
        }

    except Exception as e:

        print(
            "Vessel processing error:",
            e
        )

        return None


# ============================================================
# AREA RISK
# ============================================================

def calculate_area_risk(ships):

    if not ships:

        return {
            "score": 0,
            "level": "LOW",
            "reason":
                "No vessels found in the selected radius."
        }

    tanker_count = 0
    approaching_count = 0

    highest_ship_risk = 0

    for ship in ships:

        if "tanker" in str(
            ship["vessel_type"]
        ).lower():

            tanker_count += 1

        if ship[
            "approaching_target"
        ]:

            approaching_count += 1

        highest_ship_risk = max(
            highest_ship_risk,
            ship["risk_score"]
        )


    # --------------------------------------------------------
    # Vessel density
    # --------------------------------------------------------

    density_score = min(
        len(ships) * 2,
        15
    )


    # --------------------------------------------------------
    # Tanker density
    # --------------------------------------------------------

    tanker_score = min(
        tanker_count * 5,
        15
    )


    # --------------------------------------------------------
    # Approaching vessels
    # --------------------------------------------------------

    approaching_score = min(
        approaching_count * 3,
        15
    )


    final_score = (
        highest_ship_risk
        +
        density_score
        +
        tanker_score
        +
        approaching_score
    )

    final_score = min(
        final_score,
        100
    )


    reasons = []

    if tanker_count > 0:

        reasons.append(
            f"{tanker_count} tanker-type vessel(s) detected"
        )

    if approaching_count > 0:

        reasons.append(
            f"{approaching_count} vessel(s) moving toward target"
        )

    if len(ships) > 5:

        reasons.append(
            "High vessel density"
        )

    if not reasons:

        reasons.append(
            "No major vessel-risk indicators detected"
        )


    return {

        "score":
            round(
                final_score,
                2
            ),

        "level":
            danger_level(
                final_score
            ),

        "reason":
            "; ".join(reasons)
    }


def build_evidence_factors(ships, radius):

    if ships:
        nearest_ship = min(ships, key=lambda ship: ship["distance_km"])
        approaching_count = sum(
            1 for ship in ships if ship["approaching_target"]
        )
        vessel_types = sorted({
            ship["vessel_type"] for ship in ships
            if ship.get("vessel_type") and ship["vessel_type"] != "Unknown"
        })
        distance_status = "observed"
        distance_summary = (
            f"{len(ships)} AIS report(s) within {radius:g} km; "
            f"nearest is {nearest_ship['distance_km']:.1f} km away."
        )
        direction_status = "observed"
        direction_summary = (
            f"{approaching_count} of {len(ships)} reported heading(s) "
            "point toward the search point."
        )
        type_status = "observed" if vessel_types else "no_data"
        type_summary = (
            ", ".join(vessel_types) if vessel_types
            else "AIS vessel-type details were not available."
        )
    else:
        distance_status = "no_data"
        distance_summary = "No AIS positions arrived during this live sample."
        direction_status = "no_data"
        direction_summary = "No current vessel headings are available to assess."
        type_status = "no_data"
        type_summary = "No vessel-type details arrived during this live sample."

    return [
        {"name": "Distance", "status": distance_status, "summary": distance_summary},
        {"name": "Ship direction", "status": direction_status, "summary": direction_summary},
        {"name": "Ship track", "status": "unavailable", "summary": "Recent AIS tracks are not stored; this is a live position sample."},
        {"name": "Time and drift", "status": "unavailable", "summary": "No spill time or oil-drift model is configured."},
        {"name": "Wind", "status": "unavailable", "summary": "No wind data source is configured."},
        {"name": "Ocean current", "status": "unavailable", "summary": "No ocean-current data source is configured."},
        {"name": "Ship type", "status": type_status, "summary": type_summary},
        {"name": "Historical position", "status": "unavailable", "summary": "Historical AIS positions are not available in this app."},
    ]


# ============================================================
# HOME
# ============================================================

@app.before_request
def ensure_aisstream_collector():

    start_aisstream_collector()

@app.route("/")
def home():

    return jsonify({

        "system":
            "Marine Oil Spill Monitoring and Risk Prediction",

        "backend":
            "Python Flask",

        "data_source":
            "AISstream AIS WebSocket",

        "status":
            "ONLINE",

        "endpoint":
            "/api/ships?lat=10.0000&lon=76.0000&radius=25"

    })


# ============================================================
# HEALTH
# ============================================================

@app.route("/api/health")
def health():

    return jsonify({

        "status":
            "healthy",

        "aisstream": get_aisstream_status(),

        "timestamp":
            datetime.now(
                timezone.utc
            ).isoformat()

    })


# ============================================================
# MAIN API
# ============================================================

@app.route(
    "/api/ships",
    methods=["GET"]
)
def ships():

    # --------------------------------------------------------
    # READ INPUT
    # --------------------------------------------------------

    latitude_arg = request.args.get("lat", type=float)
    longitude_arg = request.args.get("lon", type=float)
    radius_arg = request.args.get("radius", default=100, type=float)

    if latitude_arg is None or longitude_arg is None or radius_arg is None:

        return jsonify({

            "success":
                False,

            "error":
                "Provide numeric lat and lon values, and an optional numeric radius. "
                "Example: /api/ships?lat=10&lon=76&radius=25"

        }), 400

    latitude = latitude_arg
    longitude = longitude_arg
    radius = radius_arg


    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not -90 <= latitude <= 90:

        return jsonify({

            "success":
                False,

            "error":
                "Latitude must be between -90 and 90."

        }), 400


    if not -180 <= longitude <= 180:

        return jsonify({

            "success":
                False,

            "error":
                "Longitude must be between -180 and 180."

        }), 400


    if radius <= 0 or radius > 500:

        return jsonify({

            "success":
                False,

            "error":
                "Radius must be between 1 and 500 km."

        }), 400


    # --------------------------------------------------------
    # AISSTREAM
    # --------------------------------------------------------

    vessels, error = _get_aisstream_cache()


    if error or vessels is None:

        return jsonify({

            "success":
                False,

            "error":
                error or "AISstream did not return vessel data."

        }), 502


    # --------------------------------------------------------
    # FIND NEARBY VESSELS
    # --------------------------------------------------------

    nearby = []


    for vessel in vessels:

        result = process_vessel(
            vessel,
            latitude,
            longitude,
            radius
        )

        if result:

            nearby.append(
                result
            )


    # --------------------------------------------------------
    # SORT BY DISTANCE
    # --------------------------------------------------------

    nearby.sort(
        key=lambda x:
        x["distance_km"]
    )


    # --------------------------------------------------------
    # AREA DANGER
    # --------------------------------------------------------

    danger = calculate_area_risk(
        nearby
    )


    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return jsonify({

        "success":
            True,

        "system":
            "Marine Oil Spill Monitoring",

        "target": {

            "latitude":
                latitude,

            "longitude":
                longitude,

            "radius_km":
                radius
        },

        "updated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "ship_count":
            len(nearby),

        "stream_status": get_aisstream_status(),

        "danger": danger,

        "evidence_factors": build_evidence_factors(nearby, radius),

        "ships":
            nearby,

        "note":
            "Risk level is a project-level estimate based on current AIS data. It does not confirm an oil spill or identify its source."

    })


# ============================================================
# ERROR HANDLER
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return jsonify({

        "success":
            False,

        "error":
            "Endpoint not found."

    }), 404


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print()
    print(
        "=============================================="
    )
    print(
        " MARINE OIL SPILL MONITORING SYSTEM"
    )
    print(
        " Python + Flask + AISstream AIS"
    )
    print(
        "=============================================="
    )

    print()
    print(
        "Server: http://localhost:5001"
    )

    print()
    print(
        "Test:"
    )

    print(
        "http://localhost:5001/api/ships"
        "?lat=10.0000"
        "&lon=76.0000"
        "&radius=100"
    )

    print()

    start_aisstream_collector()
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True,
        use_reloader=False
    )
