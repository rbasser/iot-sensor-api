import os
import sys
import json
import urllib.request
from urllib.error import URLError

if not API_URL:
    print("Error: API_URL environment variable is missing.")
    sys.exit(1)

def check_humidity():
    try:
        print(f"Fetching latest data from {API_URL}...")
        req = urllib.request.Request(API_URL)
        
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                print(f"Error fetching data: HTTP {response.status}")
                sys.exit(1)
            data = json.loads(response.read().decode())
            
        humidity = data.get("humidity")
        timestamp = data.get("timestamp")

        if humidity is None:
            print("Error: Could not parse humidity from the API response.")
            sys.exit(1)

        print(f"Latest reading at {timestamp} -> Humidity: {humidity}%")

        if float(humidity) > 70.0:
            print(f"🚨 ALERT: High humidity detected! ({humidity}%)")
            sys.exit(1)
        else:
            print("✅ Humidity is within the normal range.")
            sys.exit(0)

    except URLError as e:
        print(f"Network error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_humidity()