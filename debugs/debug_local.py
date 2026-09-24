"""Diagnostic script cho GoodWe local connectivity.

Usage:
    python debug_goodwe.py <dongle_ip>
    python debug_goodwe.py            # for defined ip down below
"""
import asyncio
import logging
import sys
import json

import goodwe

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.28"

async def main():
    print(f"Debugging GoodWe local connectivity to {HOST}...")
    print("\n--- Modbus/TCP port 502 ---")
    
    try:
        inverter = await goodwe.connect(HOST, port=502, timeout=5, retries=3)
        print("Successfully connected to inverter via Modbus/TCP.")
        print("Model:", inverter.model_name, "Serial:", inverter.serial_number)
        print("Starting polling loop (every 5s)... Press Ctrl+C to stop.")
        
        while True:
            try:
                data = await inverter.read_runtime_data()
                # Convert data from dict to JSON string for backend and frontend in future use
                data["timestamp"] = data["timestamp"].isoformat()  # Convert datetime to ISO format string
                data_json = json.dumps(data, indent=4)
                print("Runtime Data (JSON):")
                # print(data_json)
                # Get only the metrics needed for the dashboard
                metrics = {
                    "pv_power_w": data.get("ppv"),
                    "load_power_w": data.get("load_ptotal"),
                    "grid_power_w": data.get("house_consumption"),
                    "battery_power_w": data.get("pbattery1"),
                    "battery_soc": data.get("battery_soc"),
                }
                print("Metrics:")
                for key, value in metrics.items():
                    print(f"  {key}: {value}")
            except Exception as e:
                print("Failed to connect or fetch data:", e)
                
            # Wait for 5s before the next poll
            await asyncio.sleep(5)
    
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print("Failed to connect to inverter:", e)
        
if __name__ == "__main__":
    asyncio.run(main())