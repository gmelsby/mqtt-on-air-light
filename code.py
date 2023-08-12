# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

"""
This test will initialize the display using displayio and draw a solid green
background, a smaller purple rectangle, and some yellow text.
"""
import board
import digitalio
import os
import ipaddress
import time
import wifi

# set up lights
on_air_led = digitalio.DigitalInOut(board.A3)
on_camera_led = digitalio.DigitalInOut(board.A2)
on_air_led.direction = digitalio.Direction.OUTPUT
on_camera_led.direction = digitalio.Direction.OUTPUT

on_air_led.value = True
on_camera_led.value = False

# Get wifi info
wifi.radio.connect(os.getenv('MY_SSID'), os.getenv('MY_PASS'))
print('connected to wifi')

#  prints IP address to REPL
print("My IP address is", wifi.radio.ipv4_address)

while True:
    time.sleep(1)
    on_air_led.value, on_camera_led.value = on_camera_led.value, on_air_led.value
