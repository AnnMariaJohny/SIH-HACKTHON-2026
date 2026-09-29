import asyncio
import json
import os
from pathlib import Path

import websockets
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / "backend" / ".env"
load_dotenv(env_path)

API_KEY = os.getenv("AISSTREAM_API_KEY")

print("ENV PATH:", env_path.resolve())
print("API key loaded:", bool(API_KEY))

async def test():
    if not API_KEY:
        print("ERROR: AISSTREAM_API_KEY was not loaded.")
        return

    async with websockets.connect(
        "wss://stream.aisstream.io/v0/stream",
        open_timeout=20,
        close_timeout=5,
    ) as websocket:

        subscription = {
            "APIKey": API_KEY,
            "BoundingBoxes": [
                [
                    [8.0, 76.0],
                    [10.0, 78.0]
                ]
            ],
            "FilterMessageTypes": ["PositionReport"]
        }

        print("Sending subscription...")
        await websocket.send(json.dumps(subscription))

        print("Waiting for AIS data...")

        try:
            message = await asyncio.wait_for(
                websocket.recv(),
                timeout=15
            )

            print("SUCCESS! AISstream responded.")
            print(message[:1000])

        except asyncio.TimeoutError:
            print("Connected, but no AIS message received within 15 seconds.")

asyncio.run(test())
