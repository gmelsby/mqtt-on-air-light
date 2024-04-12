import board
import digitalio
import os
import ipaddress
import socketpool
import time
import wifi
import adafruit_minimqtt.adafruit_minimqtt as MQTT


class LightClient(MQTT.MQTT):
    """
    Extension of MQTT class that helps with encapsulation
    """
    
    def __init__(self, broker, port, username, password, socket_pool, light_feed, on_air_led, on_camera_led, initial_state='off'):
        super().__init__(broker=broker, port=port, username=username, password=password, socket_pool=socket_pool)
        print("Creating new client")
        
        self.current_state = initial_state
        self.light_feed = light_feed
        self.on_air_led=on_air_led
        self.on_camera_led=on_camera_led

        # make sure we have last will and testament set
        self.will_set(light_feed, "offline", qos=1, retain=True)

        print(f"attempting to connect to mqtt at {broker} on port {port}")
        self.connect()
        self.subscribe(light_feed, 1)
    
    # define callback functions
    def on_connect(self, mqtt_client, userdata, flags, rc):
        print("Connected to MQTT Broker!")
        print("Flags: {0}\n RC: {1}".format(flags, rc))


    def on_disconnect(self, mqtt_client, userdata, rc):
        print("Disconnected from MQTT Broker! Attempting to reconnect")
        while not self.is_connected():
            self.reconnect()


    def on_message(self, client, topic, message):
        print("New message on topic {0}: {1}".format(topic, message))
        if not (topic == self.light_feed):
            return
        self.process_message(message)

    def process_message(self, message):
        if message == "offline":
            self.publish(self.light_feed, self.current_state, qos=1, retain=True)
            return
        
        self.current_state = message
        if message == "off":
            self.on_air_led.value = False
            self.on_camera_led.value = False
        elif message == "on-air":
            self.on_air_led.value = True
            self.on_camera_led.value = False
        elif message == "on-camera":
            self.on_camera_led.value = True
            self.on_air_led.value = False
            
            
    # adjusts leds to display current state        
    def display_current_state(self):
        self.process_message(self.current_state)

# retrieve mqtt info from settings.toml
mqtt_info = {
    'port': os.getenv("MQTT_PORT"),
    'broker': os.getenv("MQTT_ADDRESS"),
    'username': os.getenv("MQTT_USER"),
    'password': os.getenv("MQTT_PASS"),
    'password': os.getenv("MQTT_PASS"),
    'light_feed': f'{os.getenv("MQTT_USER")}/status',
}

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
        # time for error_flash can be 0 because the try takes about half a second it seemss
        error_flash(0)

pool = socketpool.SocketPool(wifi.radio)
print('connected to wifi')

#  prints IP address to REPL
print("My IP address is", wifi.radio.ipv4_address)





mqtt_client = LightClient(**mqtt_info, socket_pool=pool, on_air_led=on_air_led, on_camera_led=on_camera_led)


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
        mqtt_client.display_current_state()
        disconnect_flag = False

    try:
        mqtt_client.loop()
    except (MQTT.MMQTTException) as e:
        print(f"MMQTTException: {e}")
        mqtt_client = LightClient(**mqtt_info, socket_pool=pool, on_air_led=on_air_led, on_camera_led=on_camera_led, initial_state=mqtt_client.current_state)
    except (BrokenPipeError) as e:
        print(f"BrokenPipeError: {e}")
        mqtt_client = LightClient(**mqtt_info, socket_pool=pool, on_air_led=on_air_led, on_camera_led=on_camera_led, initial_state=mqtt_client.current_state)
