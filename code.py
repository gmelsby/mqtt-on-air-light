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
state_history = ["off"]

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
        # time for error_flash can be 0 because the try takes about half a second it seemss
        error_flash(0)

pool = socketpool.SocketPool(wifi.radio)
print('connected to wifi')

#  prints IP address to REPL
print("My IP address is", wifi.radio.ipv4_address)

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
    process_message(message)

def process_message(message):
    if message != "offline":
        state_history[0] = message
    if message == "off":
        on_air_led.value = False
        on_camera_led.value = False
    elif message == "on-air":
        on_air_led.value = True
        on_camera_led.value = False
    elif message == "on-camera":
        on_camera_led.value = True
        on_air_led.value = False

def new_mqtt_client():
    print("Creating new client")
    
    new_client = MQTT.MQTT(
        broker=mqtt_address,
        port=mqtt_port,
        username=mqtt_username,
        password=mqtt_password,
        socket_pool=pool,
    )

    # setup callback methods
    new_client.on_connect = connect
    new_client.on_disconnect = disconnect
    new_client.on_message = on_message
    
    # make sure we have last will and testament set
    new_client.will_set(light_feed, "offline", qos=1, retain=True)
    
    print(f"attempting to connect to mqtt at {new_client.broker} on port {new_client.port}")
    new_client.connect()
    while not new_client.is_connected():
        error_flash(0.5, mqtt_err=True)
    new_client.subscribe(light_feed, 1)
    time.sleep(2)
    new_client.publish(light_feed, state_history[0], qos=1, retain=True)
    return new_client
    
mqtt_client = new_mqtt_client()


# flash on both leds to signal we have connected
on_air_led.value = True
on_camera_led.value = True
time.sleep(1)
on_air_led.value = False
on_camera_led.value = False

disconnect_flag = False # for indicating that led should be reset to last state
while True:
    # make sure we are connected to wifi, if not show error blink
    while not wifi.radio.connected:
        disconnect_flag = True
        error_flash(0.5)

    # make sure we are connected to mqtt, if not show error blink
    while not mqtt_client.is_connected():
        disconnect_flag = True
        error_flash(0.5, mqtt_err=True)
        
    # reset led from error flashing to prior state
    if disconnect_flag:
        process_message(state_history[0])
        disconnect_flag = False
    
    try:
        mqtt_client.loop()
    except (MQTT.MMQTTException) as e:
        print(f"MMQTTException: {e}")
        mqtt_client = new_mqtt_client()
    except (BrokenPipeError) as e:
        print(f"BrokenPipeError: {e}")
        mqtt_client = new_mqtt_client()
