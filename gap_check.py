import os
import sys
import json
import urllib.request
from datetime import datetime, timezone
from urllib.error import URLError

API_URL = os.environ.get("API_URL")
if not API_URL:
    print("Error: API_URL environment variable is missing.")
    sys.exit(1)

def check_gap():
    try:
        url = API_URL.replace("/readings/latest", "") + "/readings/latest"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())

        timestamp = data.get("timestamp")
        if not timestamp:
            print("Error: No timestamp in response.")
            sys.exit(1)

        last_seen = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        gap_minutes = (now - last_seen).total_seconds() / 60

        print(f"Last reading: {timestamp} ({gap_minutes:.1f} mins ago)")

        if gap_minutes > 15:
            print(f"🚨 ALERT: No data for {gap_minutes:.1f} minutes!")
            sys.exit(1)
        else:
            print("✅ Data gap within normal range.")
            sys.exit(0)

    except URLError as e:
        print(f"Network error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_gap()