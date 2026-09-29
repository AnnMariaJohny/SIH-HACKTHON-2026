import asyncio
import json
import math
import os
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
codespace_name = os.getenv("CODESPACE_NAME")
forwarding_domain = os.getenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")
if codespace_name and forwarding_domain:
    frontend_origins.append(
        f"https://{codespace_name}-8000.{forwarding_domain}"
    )
CORS(app, resources={r"/api/*": {"origins": frontend_origins}})

AISSTREAM_API_KEY = os.getenv("AISSTREAM_API_KEY")
AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"
AISSTREAM_CAPTURE_SECONDS = 3


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
            [[south, west + 360.0], [north, 180.0]],
            [[south, -180.0], [north, east]]
        ]

    if east > 180.0:
        return [
            [[south, west], [north, 180.0]],
            [[south, -180.0], [north, east - 360.0]]
        ]

    return [[[south, west], [north, east]]]


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


async def collect_aisstream_vessels(target_lat, target_lon, radius):

    vessels = {}
    async with websockets.connect(
        AISSTREAM_URL,
        open_timeout=20,
        close_timeout=5,
        ping_interval=20,
        ping_timeout=20,
        compression="deflate",
    ) as websocket:
        await websocket.send(json.dumps({
            "APIKey": AISSTREAM_API_KEY,
            "BoundingBoxes": aisstream_bounding_boxes(
                target_lat,
                target_lon,
                radius
            ),
            "FilterMessageTypes": ["PositionReport"]
        }))

        loop = asyncio.get_running_loop()
        deadline = loop.time() + AISSTREAM_CAPTURE_SECONDS
        while loop.time() < deadline:
            try:
                message_json = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=deadline - loop.time()
                )
            except asyncio.TimeoutError:
                break

            message = json.loads(message_json)
            if message.get("MessageType") != "PositionReport":
                continue

            vessel = normalize_aisstream_position(message)
            if vessel:
                vessel_id = vessel["mmsi"] or (
                    vessel["last_position"]["latitude"],
                    vessel["last_position"]["longitude"]
                )
                vessels[vessel_id] = vessel

    return list(vessels.values())


def get_aisstream_vessels(
    target_lat: float,
    target_lon: float,
    radius: float,
) -> tuple[list[dict[str, Any]] | None, str | None]:

    if not AISSTREAM_API_KEY:
        return None, "AISstream API key is missing. Set AISSTREAM_API_KEY in backend/.env."

    try:
        return asyncio.run(
            collect_aisstream_vessels(
                target_lat,
                target_lon,
                radius
            )
        ), None
    except Exception as error:
        return None, f"AISstream connection failed: {error}"


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
        score += 20

    return min(
        round(score, 2),
        100
    )


# ============================================================
# DANGER LEVEL
# ============================================================

def danger_level(score):

    if score >= 76:
        return "CRITICAL"

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

        approaching = ship_is_approaching(
            ship_lat,
            ship_lon,
            course,
            target_lat,
            target_lon
        )

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


# ============================================================
# HOME
# ============================================================

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
    radius_arg = request.args.get("radius", default=25, type=float)

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

    vessels, error = get_aisstream_vessels(
        latitude,
        longitude,
        radius
    )


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

        "danger": danger,

        "ships":
            nearby,

        "note":
            "Risk level is a project-level estimate based on vessel proximity, movement, speed and vessel type. It is not an official maritime safety classification."

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
        "&radius=25"
    )

    print()

    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True
    )
