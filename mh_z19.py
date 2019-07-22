#!/usr/bin/python3
from flask import Flask, jsonify
from threading import Thread
import mh_z19
from board import SCL, SDA
import busio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
import subprocess
import time
from datetime import datetime

# Create the I2C interface.
i2c = busio.I2C(SCL, SDA)

# Create the SSD1306 OLED class.
# The first two parameters are the pixel width and pixel height.  Change these
# to the right size for your display!
disp = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)

# Clear display.
disp.fill(0)
disp.show()

# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
width = disp.width
height = disp.height
image = Image.new('1', (width, height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0, 0, width, height), outline=0, fill=0)

# Draw some shapes.
# First define some constants to allow easy resizing of shapes.
padding = -2
top = padding
bottom = height - padding
# Move left to right keeping track of the current x position for drawing shapes.
x = 0

# Load nice silkscreen font
font = ImageFont.truetype('/home/pi/slkscr.ttf', 8)

app = Flask(__name__)
mh_z19_latest_reading = mh_z19.read_all()
last_change = time.time()
last_ppm = 0
current_ip = subprocess.check_output("hostname -I | cut -d\' \' -f1", shell=True).decode("utf-8")

display_off_on_wifi = False

effects = [
    (0, "Normal background concentration in outdoor ambient air"),
    (350, "Concentrations typical of occupied indoor spaces with good air exchange"),
    (1000, "Complaints of drowsiness and poor air."),
    (2000, "Headaches, sleepiness and stagnant, stale, stuffy air. Poor concentration, loss of attention, increased heart rate and slight nausea may also be present."),
    (5000, "Workplace exposure limit (as 8-hour TWA) in most jurisdictions."),
]


@app.route("/")
def get_sensor_values():
    return jsonify(mh_z19_latest_reading)


def trimmed_string(full_string, starting_point=0, wrapped=False):
    all_from_starting = full_string[starting_point:]
    if len(all_from_starting) < width:
        if wrapped:
            return trimmed_string("".join(all_from_starting) + " " + full_string, 0)
        else:
            return "".join(all_from_starting)
    else:
        return full_string[:width]


def populate_display():
    while True:
        draw.rectangle((0, 0, width, height), outline=0, fill=0)
        if not display_off_on_wifi and current_ip:
            initial_ppm = mh_z19_latest_reading["co2"]
            current_effect = [effect for min_ppm, effect in effects if initial_ppm >= min_ppm][-1]

            # draw.text((x, top + 16), CPU, font=font, fill=255)
            # draw.text((x, top + 24), "IP: " + current_ip, font=font, fill=255)
            for starting, char in enumerate(current_effect + " " * 5):
                actual_ppm = mh_z19_latest_reading["co2"]
                if initial_ppm != actual_ppm:
                    actual_effect = [effect for min_ppm, effect in effects if actual_ppm >= min_ppm][-1]
                    if current_effect != actual_effect:
                        break

                time_since_last_change = int(time.time() - last_change)
                chevron = ""
                if time_since_last_change < 30:
                    chevron = " +" if mh_z19_latest_reading["co2"] > last_ppm else " -"
                for _ in range(5 if starting == 0 else 1):
                    draw.rectangle((0, 0, width, height), outline=0, fill=0)
                    draw.text((x, top + 0), "Current PPM: " + str(actual_ppm) + chevron, font=font, fill=255)
                    draw.text((x, top + 8), "Changed: " + str(time_since_last_change) + " seconds ago", font=font, fill=255)
                    draw.text((x, top + 16), "Effects:", font=font, fill=255)
                    draw.text((x, top + 24), trimmed_string(current_effect, starting), font=font, fill=255)
                    disp.image(image)
                    disp.show()
                    time.sleep(.03)
        else:
            disp.image(image)
            disp.show()
            time.sleep(5)


def main():
    global mh_z19_latest_reading, last_change, last_ppm, current_ip
    while True:
        mh_z19_latest_reading = mh_z19.read_all()
        current_ip = subprocess.check_output("hostname -I | cut -d\' \' -f1", shell=True).decode("utf-8")
        current_ppm = mh_z19_latest_reading["co2"]
        if current_ppm != last_ppm:
            last_ppm = current_ppm
            last_change = time.time()
        time.sleep(0.1)


if __name__ == "__main__":
    # Configure Flask Server Thread
    threads = [
        Thread(name='Flask Thread', target=app.run, kwargs=({'host': '0.0.0.0', 'port': 80})),
        Thread(name='Display Thread', target=populate_display)
    ]

    for thread in threads:
        thread.daemon = True
        thread.start()
    main()
