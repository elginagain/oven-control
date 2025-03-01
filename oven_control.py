import sys
import time
import threading
import os
from flask import Flask, request, jsonify, render_template
from simple_pid import PID

# ==============================
# ✅ Platform-Specific GPIO Setup
# ==============================

if sys.platform.startswith("linux"):
    import lgpio
    gpio_handle = lgpio.gpiochip_open(0)  # Open GPIO chip

    # Define GPIO pins
    SSR_PIN = 17  # GPIO pin for SSR (Solid State Relay)
    LIGHT_PIN = 27  # GPIO pin for light relay

    try:
        lgpio.gpio_claim_output(gpio_handle, SSR_PIN)
    except lgpio.error:
        print("⚠️ GPIO 17 is busy. Attempting to free and reclaim...")
        lgpio.gpio_free(gpio_handle, SSR_PIN)
        lgpio.gpio_claim_output(gpio_handle, SSR_PIN)

    try:
        lgpio.gpio_claim_output(gpio_handle, LIGHT_PIN)
    except lgpio.error:
        print("⚠️ GPIO 27 is busy. Attempting to free and reclaim...")
        lgpio.gpio_free(gpio_handle, LIGHT_PIN)
        lgpio.gpio_claim_output(gpio_handle, LIGHT_PIN)

else:
    # ✅ Mock lgpio for Windows development
    class MockGPIO:
        def gpiochip_open(self, x): return None
        def gpio_claim_output(self, chip, pin): pass
        def gpio_write(self, chip, pin, value): pass
        def gpio_free(self, chip, pin): pass

    lgpio = MockGPIO()
    gpio_handle = None
    SSR_PIN = None
    LIGHT_PIN = None

# ==============================
# ✅ SPI / Thermocouple Setup (Fixed)
# ==============================

if sys.platform.startswith("linux"):
    import spidev  # Correct library for Raspberry Pi SPI communication

    # SPI Configuration for MAX31855
    SPI_BUS = 0
    SPI_DEVICE = 0

    def read_max31855():
        """Reads temperature from MAX31855 using SPI."""
        spi = spidev.SpiDev()
        spi.open(SPI_BUS, SPI_DEVICE)
        spi.max_speed_hz = 5000000  # Set SPI clock speed

        raw = spi.readbytes(4)  # Read 4 bytes from the sensor
        spi.close()

        # Parse raw data and convert to temperature
        temp_raw = ((raw[0] << 24) | (raw[1] << 16) | (raw[2] << 8) | raw[3]) >> 18
        if temp_raw & 0x2000:  # Check for negative temperature
            temp_raw -= 16384

        temp_c = temp_raw * 0.25  # Convert to Celsius
        temp_f = temp_c * 9.0 / 5.0 + 32.0  # Convert to Fahrenheit
        return temp_f  # Return Fahrenheit

else:
    # ✅ Mock MAX31855 sensor for Windows development
    class MockMAX31855:
        def read_temp_f(self): return 77.0  # Dummy temperature for testing

    read_max31855 = MockMAX31855().read_temp_f  # Assign mock function

# ==============================
# ✅ PID Control Setup
# ==============================

pid = PID(10, 5, 1, setpoint=450)  # Default setpoint: 450°F
pid.output_limits = (0, 1)  # Limit PID output between 0 and 1

# ==============================
# ✅ Global Variables
# ==============================

current_temperature = 0.0
target_temperature = 450
oven_on = False
light_on = False
auto_tuning = False

# ==============================
# ✅ Flask Web App Setup
# ==============================

app = Flask(__name__)

def read_temperature():
    """ Continuously read temperature from the MAX31855 sensor and update global variable. """
    global current_temperature
    while True:
        try:
            current_temperature = read_max31855()  # Use new SPI function
        except Exception as e:
            print(f"❌ Error reading temperature: {e}")
            current_temperature = 0.0  # Set to 0 if read fails
        time.sleep(2)

@app.route('/')
def index():
    """ Serve the main dashboard page. """
    return render_template('index.html')

@app.route('/settings')
def settings():
    """ Serve the settings page. """
    return render_template('settings.html')

@app.route('/status')
def status():
    """ Return current oven status & temperature readings. """
    return jsonify({
        'temperature': current_temperature,
        'target_temperature': target_temperature,
        'oven_on': oven_on,
        'light_on': light_on,
        'auto_tuning': auto_tuning
    })

@app.route('/set_temperature', methods=['POST'])
def set_temperature():
    """ Set a new target temperature for the oven. """
    global target_temperature
    data = request.json
    target_temperature = max(0, min(500, data.get('temperature', 450)))  # Ensure within range
    pid.setpoint = target_temperature  # Update PID setpoint
    return jsonify({'target_temperature': target_temperature})

@app.route('/power', methods=['POST'])
def power():
    """ Toggle the oven ON/OFF. """
    global oven_on
    data = request.json
    oven_on = data.get('oven_on', False)
    return jsonify({'oven_on': oven_on})

@app.route('/toggle_light', methods=['POST'])
def toggle_light():
    """ Toggle the oven light ON/OFF. """
    global light_on
    light_on = not light_on
    lgpio.gpio_write(gpio_handle, LIGHT_PIN, light_on)
    return jsonify({'light_on': light_on})

@app.route('/auto_tune', methods=['POST'])
def auto_tune():
    """ Initiate PID auto-tune process. """
    global auto_tuning
    auto_tuning = True
    threading.Thread(target=perform_auto_tune, daemon=True).start()
    return jsonify({'auto_tuning': auto_tuning})

def perform_auto_tune():
    """ Placeholder for future PID auto-tune logic. """
    global auto_tuning
    time.sleep(10)  # Simulate auto-tune duration
    auto_tuning = False

def control_loop():
    """ Control the oven SSR based on PID output. """
    global oven_on
    while True:
        if oven_on:
            power = pid(current_temperature)  # Get PID output
            lgpio.gpio_write(gpio_handle, SSR_PIN, power > 0.5)  # Toggle SSR
        else:
            lgpio.gpio_write(gpio_handle, SSR_PIN, 0)  # Ensure SSR is OFF
        time.sleep(2)

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """ Shutdown the Raspberry Pi. """
    os.system('sudo shutdown -h now')
    return jsonify({'message': 'Shutting down...'})

# ==============================
# ✅ Start Background Tasks & Flask Server
# ==============================

if __name__ == '__main__':
    temp_thread = threading.Thread(target=read_temperature, daemon=True)
    temp_thread.start()

    control_thread = threading.Thread(target=control_loop, daemon=True)
    control_thread.start()

    app.run(host='0.0.0.0', port=5000)
