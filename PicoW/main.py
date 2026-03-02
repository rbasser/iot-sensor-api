from machine import Pin, I2C, reset
import network
import urequests
import time
from breakout_bme68x import BreakoutBME68X
from personalDetails import *

led = Pin("LED", Pin.OUT)

# Sensor initialisation
sensor = BreakoutBME68X(I2C(0, sda=Pin(16), scl=Pin(17), freq=400000))

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

def ensure_wifi_connected(timeout_seconds=30):
    """
    Scans available networks, connects if a known SSID is found.
    Flashes LED during both scanning and connection attempts.
    Keeps scanning if no known networks are found; reboots if it hangs during a connection attempt.
    Returns the name of the connected SSID.
    """
    if wlan.isconnected():
        led.off()
        try:
            current_ssid = wlan.config('ssid')
        except:
            current_ssid = "Unknown Network"
        return current_ssid

    print("Wi-Fi not connected. Scanning for networks...")
    
    # Initialize LED state
    led_state = False
    
    while not wlan.isconnected():
        available_networks = wlan.scan()
        
        target_ssid = None
        target_password = None
        
        for network_info in available_networks:
            ssid_str = network_info[0].decode('utf-8')
            
            if ssid_str in SAVED_NETWORKS:
                target_ssid = ssid_str
                target_password = SAVED_NETWORKS[ssid_str]
                print(f"Found known network: '{target_ssid}'")
                break 
                
        if target_ssid:
            print(f"Attempting to connect to {target_ssid}...")
            wlan.connect(target_ssid, target_password)
            
            start_time = time.time()
            
            # Flashing while actively negotiating IP address with router
            while not wlan.isconnected():
                if time.time() - start_time >= timeout_seconds:
                    print(f"Failed to connect within {timeout_seconds} seconds. Rebooting...")
                    time.sleep(1) 
                    reset() 
                    
                led_state = not led_state
                led.value(led_state)
                
                try:
                    temperature, raw_pressure, humidity, raw_gas, status, gas_index, meas_index = sensor.read(heater_temp=0, heater_duration=0)
                    pressure = int(round(raw_pressure))
                    print(f"Connecting... Temperature: {temperature:0.2f}C, Humidity: {humidity:0.2f}%, Pressure: {pressure}Pa")
                except Exception as e:
                    print("Error reading sensor during connection: ", e)
                    pass 
                
                # Faster 1-second blink
                time.sleep(1)
                
            led.off()
            print("Connected to Wi-Fi!")
            print(f"Network config: {wlan.ifconfig()}")
            
            return target_ssid
            
        else:
            print("No known networks found. Scanning again in 5 seconds...")
            # Flashing while the router is missing/offline (wait 5 seconds total)
            for _ in range(5):
                led_state = not led_state
                led.value(led_state)
                time.sleep(1)

# Initialise pico
active_network = ensure_wifi_connected()

print("=" * 60)
print(f"SYSTEM READY. Currently connected to: {active_network}")
print("=" * 60)

# Main loop - determine if heater is to be used, collect data accordingly, format into a payload then attempt to upload using HTTP
HEATED_INTERVAL = 600  
last_heated_time = time.time()   

just_rebooted = True

while True:
    # 1. Verify connection
    ensure_wifi_connected()
    
    # 2. Determine if it's time for a heated reading
    current_time = time.time()
    is_heated_run = False
    
    if current_time - last_heated_time >= HEATED_INTERVAL:
        h_temp = 220
        h_dur = 50
        last_heated_time = current_time
        is_heated_run = True
        print("--> Taking 10-minute heated reading...")
    else:
        h_temp = 0
        h_dur = 0
    
    # 3. Read sensor data
    temperature, raw_pressure, humidity, raw_gas, status, gas_index, meas_index = sensor.read(heater_temp=h_temp, heater_duration=h_dur)
    
    # 4. Format payload to match schemas.py (Lowercase keys!)
    pressure = int(round(raw_pressure))
    gas_resistance = int(round(raw_gas)) if is_heated_run else None
    
    # Matches ReadingCreate schema in schemas.py
    payload = {
        "temperature": temperature,
        "humidity": humidity,
        "pressure": pressure,
        "gas_resistance": gas_resistance,
        "reboot_flag": "rebooted" if just_rebooted else None
    }
    
    print(f"Sending to Render -> Temp: {temperature:0.1f}C, Humidity: {humidity: 0.1f} Press: {pressure}Pa")
    
    # 5. Simplified headers for FastAPI
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": RENDER_API_KEY
    }
    
    # 6. Attempt to send data
    try:
        # Use the specific /readings/ endpoint
        response = urequests.post(RENDER_URL, json=payload, headers=headers, timeout=10.0)
        
        # FastAPI returns 200 OK for successful POST by default
        if response.status_code == 200:
            print("Successfully posted to Render API\n")
            just_rebooted = False
        else:
            print(f"API Error ({response.status_code}): {response.text}\n")
        
        response.close()

    except Exception as e:
        print(f"Connection failed: {e}\n")

    # 7. Wait for next cycle
    time.sleep(30)

