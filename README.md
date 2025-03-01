<<<<<<< HEAD
# oven-control
A Raspberry Pi based Powder Coating Oven controller.
=======
import os
import time
import threading
import board
import digitalio
import adafruit_max31855
import RPi.GPIO as GPIO
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from simple_pid import PID

# Raspberry Pi GPIO Setup
SSR_PIN = 17  # Single SSR for heating elements
LIGHT_PIN = 27  # Relay for lights
GPIO.setmode(GPIO.BCM)
GPIO.setup(SSR_PIN, GPIO.OUT)
GPIO.setup(LIGHT_PIN, GPIO.OUT)
GPIO.output(SSR_PIN, GPIO.LOW)
GPIO.output(LIGHT_PIN, GPIO.LOW)

# MAX31855 Thermocouple Setup
spi = board.SPI()
cs = digitalio.DigitalInOut(board.D8)
thermocouple = adafruit_max31855.MAX31855(spi, cs)

# PID Controller Setup
pid = PID(1.5, 0.1, 0.05, setpoint=450)  # Default to 450°F
pid.output_limits = (0, 1)  # 0 = OFF, 1 = ON

# Flask Web Server Setup
app = Flask(__name__)
socketio = SocketIO(app)

# Global Variables
current_temp = 0
oven_running = False
light_on = False
temp_history = []

# Read temperature function
def read_temperature():
    return thermocouple.temperature * 9/5 + 32  # Convert to Fahrenheit

# PID Control Loop
def control_loop():
    global current_temp, oven_running
    while True:
        if oven_running:
            current_temp = read_temperature()
            output = pid(current_temp)
            GPIO.output(SSR_PIN, GPIO.HIGH if output > 0.5 else GPIO.LOW)

            # Store temperature for graphing
            if len(temp_history) > 100:
                temp_history.pop(0)
            temp_history.append(current_temp)

            # Send updates to the UI
            socketio.emit('update_temp', {'temp': round(current_temp, 2), 'history': temp_history})
        
        time.sleep(2)

# Start Control Loop in Background
threading.Thread(target=control_loop, daemon=True).start()

# Web Interface
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/set_temp', methods=['POST'])
def set_temp():
    global pid
    data = request.json
    new_temp = min(max(int(data['temp']), 0), 500)  # Clamp between 0-500°F
    pid.setpoint = new_temp
    return jsonify({'status': 'success'})

@app.route('/start_oven', methods=['POST'])
def start_oven():
    global oven_running
    oven_running = True
    return jsonify({'status': 'started'})

@app.route('/stop_oven', methods=['POST'])
def stop_oven():
    global oven_running
    oven_running = False
    GPIO.output(SSR_PIN, GPIO.LOW)
    return jsonify({'status': 'stopped'})

@app.route('/toggle_light', methods=['POST'])
def toggle_light():
    global light_on
    light_on = not light_on
    GPIO.output(LIGHT_PIN, GPIO.HIGH if light_on else GPIO.LOW)
    return jsonify({'status': 'on' if light_on else 'off'})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    os.system("sudo shutdown -h now")
    return jsonify({'status': 'shutting down'})

# Start Flask Server
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
>>>>>>> ad28017 (Initial commit)
