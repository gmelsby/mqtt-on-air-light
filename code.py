import board
import digitalio
import os
import ipaddress
import socketpool
import time
import wifi
import adafruit_minimqtt.adafruit_minimqtt as MQTT


# retrieve mqtt info
mqtt_port = os.getenv("MQTT_PORT")
mqtt_address = os.getenv("MQTT_ADDRESS")
mqtt_username = os.getenv("MQTT_USER")
mqtt_password = os.getenv("MQTT_PASS")
light_feed = f'{mqtt_username}/status'

# set up lights
on_air_led = digitalio.DigitalInOut(board.GP4)
on_camera_led = digitalio.DigitalInOut(board.GP3)
on_air_led.direction = digitalio.Direction.OUTPUT
on_camera_led.direction = digitalio.Direction.OUTPUT

on_air_led.value = True
on_camera_led.value = False

# pattern that indicates something has gone wrong with wifi/mqtt connection
def error_flash(sleep_time, mqtt_err=False):
    leds = [on_air_led, on_camera_led]
    # blink other led if mqtt err is true
    if mqtt_err:
        leds.reverse()
    leds[0].value = False
    leds[1].value = not leds[1].value
    time.sleep(sleep_time)

# Get wifi info
# Loop until able to connect
while not wifi.radio.connected:
    try:
        wifi.radio.connect(os.getenv('MY_SSID'), os.getenv('MY_PASS'))
    except (ConnectionError) as e:
        print(f"ConnectionError: {e}")
        error_flash(0.5)

pool = socketpool.SocketPool(wifi.radio)
print('connected to wifi')

#  prints IP address to REPL
print("My IP address is", wifi.radio.ipv4_address)

# connect to mqtt server
mqtt_client = MQTT.MQTT(
    broker=mqtt_address,
    port=mqtt_port,
    username=mqtt_username,
    password=mqtt_password,
    socket_pool=pool,
)

# define callback functions
def connect(mqtt_client, userdata, flags, rc):
    print("Connected to MQTT Broker!")
    print("Flags: {0}\n RC: {1}".format(flags, rc))


def disconnect(mqtt_client, userdata, rc):
    print("Disconnected from MQTT Broker! Attempting to reconnect")
    while not mqtt_client.is_connected():
        mqtt_client.reconnect()


def subscribe(mqtt_client, userdata, topic, granted_qos):
    print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))


def on_message(client, topic, message):
    print("New message on topic {0}: {1}".format(topic, message))
    if not (topic == light_feed):
        return
    if message == "off":
        on_air_led.value = False
        on_camera_led.value = False
    elif message == "on-air":
        on_air_led.value = True
        on_camera_led.value = False
    elif message == "on-camera":
        on_camera_led.value = True
        on_air_led.value = False

# setup callback methods
mqtt_client.on_connect = connect
mqtt_client.on_disconnect = disconnect
mqtt_client.on_message = on_message

# make sure we have last will and testament set before connecting
mqtt_client.will_set(light_feed, "offline", qos=1, retain=True)
print(f"attempting to connect to mqtt at {mqtt_client.broker} on port {mqtt_client.port}")
mqtt_client.connect()
while not mqtt_client.is_connected():
    error_flash(0.5, mqtt_err=True)
mqtt_client.publish(light_feed, "off", qos=1, retain=True)
mqtt_client.subscribe(light_feed, 1)

# flash on both leds to signal we have connected to wifi
on_air_led.value = True
on_camera_led.value = True
time.sleep(1)
on_air_led.value = False
on_camera_led.value = False

while True:
    # make sure we are connected to wifi, if not show error blink
    while not wifi.radio.connected:
        error_flash(0.5)
    # make sure we are connected to mqtt, if not show error blink
    while not mqtt_client.is_connected():
        error_flash(0.5, mqtt_err=True)
    try:
        mqtt_client.loop()
    except (MQTT.MMQTTException) as e:
        print(f"MMQTTException: {e}")
        error_flash(0.5, mqtt_err=True)
    except (BrokenPipeError) as e:
        print(f"BrokenPipeError: {e}")
        error_flash(0.5, mqtt_err=True)
