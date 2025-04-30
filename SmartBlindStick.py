import serial
import time
import pynmea2
import requests
import re
import math
import pyttsx3
import RPi.GPIO as GPIO

# ------------------- Text-to-Speech Setup -------------------
engine = pyttsx3.init()
def speak(text):
    engine.setProperty('rate', 125)
    engine.say(text)
    engine.runAndWait()

# ------------------- Ultrasonic Sensor Setup -------------------
TRIG = 23
ECHO = 24
GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

def get_distance_cm():
    GPIO.output(TRIG, False)
    time.sleep(0.05)

    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)

    while GPIO.input(ECHO) == 0:
        pulse_start = time.time()
    while GPIO.input(ECHO) == 1:
        pulse_end = time.time()

    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150
    return round(distance, 2)

# ------------------- GPS Reading -------------------
def get_current_location_from_gps(last_position=None):
    try:
        port = serial.Serial("/dev/serial0", baudrate=9600, timeout=1)
        print("📡 Getting GPS fix...")
        speak("Getting GPS fix.")
        timeout = time.time() + 15
        while True:
            if time.time() > timeout:
                print("❌ Timeout: No GPS fix.")
                speak("Timeout. No GPS fix.")
                return None

            port.flushInput()
            data = port.readline().decode('ascii', errors='replace').strip()
            if data.startswith('$GPGGA'):
                try:
                    msg = pynmea2.parse(data)
                    if msg.latitude != 0 and msg.longitude != 0:
                        current = (msg.latitude, msg.longitude)
                        if last_position:
                            dist = calculate_distance(current[0], current[1], last_position[0], last_position[1])
                            if dist < 1.5:
                                print("🚶 Waiting for movement...")
                                continue
                        print(f"📍 Fresh GPS: {current}")
                        return current
                except pynmea2.ParseError:
                    continue
            time.sleep(0.2)
    except Exception as e:
        print("❌ GPS Error:", e)
        speak("Error reading from GPS.")
        return None

# ------------------- Google Maps Directions -------------------
def get_directions(origin, destination, api_key):
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "mode": "walking",
        "key": api_key
    }
    response = requests.get(url, params=params)
    directions = response.json()

    if directions['status'] != 'OK':
        print("❌ Directions API error:", directions['status'])
        speak("Error fetching directions.")
        return []

    steps = directions['routes'][0]['legs'][0]['steps']
    coordinates = []
    for step in steps:
        lat = step['end_location']['lat']
        lon = step['end_location']['lng']
        maneuver = step.get('maneuver', 'straight')
        coordinates.append((lat, lon, maneuver))
    return coordinates

# ------------------- Distance Calculation -------------------
def calculate_distance(lat1, lon1, lat2, lon2):
    radius = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radius * c

# ------------------- Voice Directions -------------------
def speak_maneuver(maneuver):
    if maneuver == "turn-left":
        speak("Turn left")
    elif maneuver == "turn-right":
        speak("Turn right")
    elif maneuver == "turn-slight-left":
        speak("Slight left")
    elif maneuver == "turn-slight-right":
        speak("Slight right")
    elif maneuver in ["uturn-left", "uturn-right"]:
        speak("Turn back")
    else:
        speak("Walk straight")

# ------------------- Main -------------------
def main():
    try:
        print("🧭 Smart Blind Stick - Navigation + Obstacle")
        speak("Welcome to Smart Blind Stick Navigation.")

        api_key = "YOUR_GOOGLE_MAPS_API_KEY"  # Replace with your actual key

        last_position = None
        origin = get_current_location_from_gps()
        if not origin:
            print("❌ No GPS. Exiting.")
            return

        destination = input("🎯 Enter destination address: ")
        if not destination:
            print("❌ No destination entered.")
            return

        directions = get_directions(f"{origin[0]},{origin[1]}", destination, api_key)
        if not directions:
            print("❌ No directions found.")
            return

        print("✅ Starting navigation.")
        speak("Starting navigation.")
        current_step = 0

        while current_step < len(directions):
            gps = get_current_location_from_gps(last_position)
            if not gps:
                continue

            distance_to_obstacle = get_distance_cm()
            if distance_to_obstacle < 500:
                print(f"🚧 Obstacle at {distance_to_obstacle} cm ahead!")
                speak("Warning! Obstacle ahead.")
                time.sleep(2)

            target_lat, target_lon, maneuver = directions[current_step]
            distance = calculate_distance(gps[0], gps[1], target_lat, target_lon)

            print(f"📏 Distance to next point: {int(distance)} meters")
            last_position = gps

            if distance < 7:
                speak_maneuver(maneuver)
                current_step += 1
                time.sleep(3)
            else:
                speak("Walk straight")
                time.sleep(5)

        print("🏁 You have reached your destination!")
        speak("You have reached your destination.")
    
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
