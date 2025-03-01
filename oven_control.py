import lgpio
import Adafruit_GPIO.SPI as SPI
import Adafruit_MAX31855.MAX31855 as MAX31855
from flask import Flask, request, jsonify, render_template
from simple_pid import PID
import threading
import time

# GPIO setup
SSR_PIN = 17  # GPIO pin connected to the SSR
LIGHT_PIN = 27  # GPIO pin for lights
gpio_handle = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(gpio_handle, SSR_PIN)
lgpio.gpio_claim_output(gpio_handle, LIGHT_PIN)

# Thermocouple setup
SPI_PORT = 0
SPI_DEVICE = 0
sensor = MAX31855.MAX31855(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE))

# PID setup
pid = PID(10, 5, 1, setpoint=450)
pid.output_limits = (0, 1)  # Limit PID output to control SSR effectively

# Global variables
current_temperature = 0.0  # Store the current temperature reading
target_temperature = 450  # Default target temperature in Fahrenheit
oven_on = False  # Track oven power state
light_on = False  # Track light power state
auto_tuning = False  # Track if auto-tune is in progress

# Flask setup for web interface
app = Flask(__name__)

def read_temperature():
    """Continuously read temperature from the MAX31855 sensor."""
    global current_temperature
    while True:
        current_temperature = sensor.readTempC() * 9.0 / 5.0 + 32.0  # Convert Celsius to Fahrenheit
        time.sleep(2)

@app.route('/')
def index():
    """Serve the main dashboard page."""
    return render_template('index.html')

@app.route('/settings')
def settings():
    """Serve the settings page."""
    return render_template('settings.html')

@app.route('/status')
def status():
    """Return the current status of the oven and temperature readings."""
    return jsonify({
        'temperature': current_temperature,
        'target_temperature': target_temperature,
        'oven_on': oven_on,
        'light_on': light_on,
        'auto_tuning': auto_tuning
    })

@app.route('/set_temperature', methods=['POST'])
def set_temperature():
    """Set a new target temperature for the oven."""
    global target_temperature
    data = request.json
    target_temperature = max(0, min(500, data.get('temperature', 450)))  # Ensure temperature stays within range
    pid.setpoint = target_temperature  # Update PID setpoint
    return jsonify({'target_temperature': target_temperature})

@app.route('/power', methods=['POST'])
def power():
    """Turn the oven on or off."""
    global oven_on
    data = request.json
    oven_on = data.get('oven_on', False)
    return jsonify({'oven_on': oven_on})

@app.route('/toggle_light', methods=['POST'])
def toggle_light():
    """Toggle the oven light on or off."""
    global light_on
    light_on = not light_on
    lgpio.gpio_write(gpio_handle, LIGHT_PIN, light_on)
    return jsonify({'light_on': light_on})

@app.route('/auto_tune', methods=['POST'])
def auto_tune():
    """Initiate the PID auto-tune process."""
    global auto_tuning
    auto_tuning = True
    threading.Thread(target=perform_auto_tune, daemon=True).start()
    return jsonify({'auto_tuning': auto_tuning})

def perform_auto_tune():
    """Perform auto-tuning of the PID controller (placeholder for logic)."""
    global auto_tuning
    time.sleep(10)  # Simulate auto-tuning duration
    auto_tuning = False  # Reset flag after tuning completes

def control_loop():
    """Continuously control the oven's SSR based on PID output."""
    global oven_on
    while True:
        if oven_on:
            power = pid(current_temperature)  # Get PID output
            lgpio.gpio_write(gpio_handle, SSR_PIN, power > 0.5)  # Turn SSR on/off based on PID output
        else:
            lgpio.gpio_write(gpio_handle, SSR_PIN, 0)  # Ensure SSR is off when oven is off
        time.sleep(2)

import os

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the Raspberry Pi."""
    os.system('sudo shutdown -h now')
    return jsonify({'message': 'Shutting down...'})

if __name__ == '__main__':
    # Start background threads for reading temperature and controlling the oven
    temp_thread = threading.Thread(target=read_temperature, daemon=True)
    temp_thread.start()
    control_thread = threading.Thread(target=control_loop, daemon=True)
    control_thread.start()
    
    # Start Flask web server
    app.run(host='0.0.0.0', port=5000)
