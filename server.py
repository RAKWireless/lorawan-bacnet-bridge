import os
import sys
import time
import flatdict
import yaml
import logging
import json
import base64
import binascii
import math
import quickjs
import socket
import shutil
from pathlib import Path

from paho.mqtt.client import Client
import BAC0
from BAC0.core.devices.local.models import ObjectFactory
from bacpypes.object import BinaryInputObject, BinaryOutputObject, AnalogInputObject, AnalogOutputObject, AnalogValueObject

# -----------------------------------------------------------------------------
# Globals
# -----------------------------------------------------------------------------

APP_NAME = "LoRaWAN to BACnet Bridge"
APP_VERSION = "v1.0.0"

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

class Config():

    _data = flatdict.FlatDict({})
    _file = "config/config.yml"
    _dirty = False

    def __init__(self):
        try:
            with open(self._file, "r") as f:
                _data =  yaml.load(f, Loader=yaml.loader.SafeLoader)
        except FileNotFoundError:
            _data = {'logging': {'level' : logging.INFO}}
        self._data =  flatdict.FlatDict(_data, delimiter='.')

    def get(self, name, default=None):
        
        # Environment variables have precedence over `config.yml` but do not get persisted
        env_name = name.upper().replace('.', '_').replace('-', '_')
        value = os.environ.get(env_name)
        
        # Get the value from `config.yml` or the default, and persist
        if not value:
            value = self._data.get(name, default)
            self.set(name, value)

        return value

    def set(self, name, value):
        if self._data.get(name) != value:
            self._data[name] = value
            self._dirty = True

    def save(self):
        if self._dirty:
            try:
                with open(self._file, "w") as f:
                    yaml.dump(self._data.as_dict(), f, default_flow_style=False)
                self._dirty = False
            except FileNotFoundError:
                None

    def unflat(self):
        return self._data.as_dict()

    def dump(self):
        print(json.dumps(self._data.as_dict(), sort_keys=True, indent=4))


# -----------------------------------------------------------------------------
# MQTT
# -----------------------------------------------------------------------------

class MQTTClient(Client):

    MQTTv31 = 3
    MQTTv311 = 4
    MQTTv5 = 5

    def __init__(self, broker="localhost", port=1883, username=None, password=None, userdata=None):

        def connect_callback_default(client, userdata, flags, rc):
            if rc == 0:
                logging.debug("[MQTT] Connected to MQTT Broker!")
            else:
                logging.error("[MQTT] Failed to connect, return code %d", rc)

        def message_callback_default(client, userdata, msg):
            logging.debug("[MQTT] Received `%s` from `%s` topic", msg.payload, msg.topic)
            
        def subscribe_callback_default(client, userdata, mid, granted_qos):
            logging.debug("[MQTT] Subscribed")

        def disconnect_callback_default(client, userdata, rc):
            logging.debug("[MQTT] Disconnected from MQTT Broker!")

        Client.__init__(self,
            client_id = "",
            clean_session = None,
            userdata = userdata,
            protocol = self.MQTTv311,
            transport = "tcp",
            reconnect_on_failure = True
        )

        self.on_connect = connect_callback_default
        self.on_disconnect = disconnect_callback_default
        self.on_message = message_callback_default
        self.on_subscribe = subscribe_callback_default
        if username and password:
            self.username_pw_set(username, password)
        self.connect(broker, port)

    def run(self):
        self.loop_start()

# -----------------------------------------------------------------------------
# BACnet
# -----------------------------------------------------------------------------

class BACnetApp():

    id = 1
    
    def __init__(self):
        self.objects = None
        self.device = None

    def create_device(self, ip=None, port=None, mask=24, name='BAC0', id=None, **params):
        self.device = BAC0.lite(ip=ip, port=port, mask=mask, localObjName=name, deviceId=id, **params)

    def setLoggingLevel(self, level):
        self.device._log.setLevel(level)
        self.device._update_local_cov_task.task._log.setLevel(level)

    def add_object(self, type, name, description, value, units, id=0):
        if 0 == id:
            id = self.id
            self.id += 1
        self.objects = ObjectFactory(
            type, id, name, 
            properties = {"units": units},
            description = description,
            presentValue = value
        )
        return id

    def clear_objects(self):
        if self.objects:
            self.objects.clear_objects()
        self.id = 1

    def list(self):
        for obj in self.device.this_application.iter_objects():
            print(obj.objectName)

    def unload(self):
        if self.objects:
            for k, v in self.objects.objects.items():
                self.device.this_application.delete_object(v)

    def load(self):
        if self.objects:
            self.objects.add_objects_to_application(self.device)
    
    def run(self):
        self.setLoggingLevel(logging.INFO)
        while True:
            time.sleep(0.1)

# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def get_data(msg, force_decode=False, decoder='cayenne.js'):

    # Get payload in JSON
    payload = json.loads(msg.payload)

    # Find out what LNS we have
    if "uplink_message" in payload:
        payload_raw = base64.b64decode(payload['uplink_message']['frm_payload'])
        payload_decoded = payload['uplink_message'].get('decoded_payload', False)
        port = payload['uplink_message']['f_port']
        gateways = payload['uplink_message']['rx_metadata']
    else:
        payload_raw = base64.b64decode(payload['data'])
        payload_decoded = payload.get('object', False)
        port = payload['fPort']
        gateways = payload['rxInfo']

    if (force_decode) or (payload_decoded == False):
        
        # Decode raw payload
        decoder_file = f'config/decoders/{decoder}'
        with open(decoder_file) as f:
            decoder = f.readlines()
        context = quickjs.Context()
        context.eval(''.join(decoder))
        context.eval("""
            function f(bytes, port) {
                input = {'bytes': bytes, 'fPort': port};
                return decodeUplink(input);
            }
        """)
        command = "f([{}], {})".format(",".join([str(b) for b in payload_raw]), port)
        response = json.loads(context.eval(command).json())
        response = response['data']

    else:
        
        # get the pre-decoded payload
        response = payload_decoded

    # Add metadata objects
    best_rssi = -200
    best_snr = -20
    for gateway in gateways:
        best_rssi = max(gateway.get('rssi', best_rssi), best_rssi)
        best_snr = max(gateway.get('snr', gateway.get('loRaSNR', best_snr)), best_snr)
    response.append({'name': 'rssi', 'type': 250, 'value': best_rssi})
    response.append({'name': 'snr', 'type': 250, 'value': best_snr})
    
    return response

def get_device_id(msg):
    return msg.topic.split('/')[3]

def load_bacnet_devices():

    # Unload them all first
    bacnet_app.unload()
    bacnet_app.clear_objects()

    devices = (config.unflat()).get('devices', {})
    for device_id in devices:
        for key in devices[device_id].get('objects', {}):
            obj = devices[device_id]['objects'][key]
            name = obj.get('name', f"{device_id}-{key}")
            logging.debug(f"[BACNET] Loading {name}")
            bacnet_app.add_object(
                type = globals()[obj.get("type", "AnalogInputObject")],
                id = int(obj.get('id', 0)),
                name = name,
                description= "",
                value = obj.get("value", 0),
                units = obj.get("units", "noUnits")
            )

    bacnet_app.load()

def update_object(device, device_id, element):

    save = False
    name = element.get('name')
    datatype = element.get('type', 0)
    value = element.get('value', 0)

    # Recursive call for dict values
    if isinstance(value, dict):
        for key in value:
            sub_element = {}
            sub_element['type'] = datatype
            sub_element['name'] = f"{name}-{key}"
            sub_element['value'] = value[key]
            save |= update_object(device, device_id, sub_element)
        return save
    
    object_name = f"{device_id}-{name}"

    try:
        
        # Update the BACnet object value
        device[object_name].presentValue = value
        
        # We are updating the current value but not saving it to disk just yet (lazysaving)
        config.set(f"devices.{device_id}.objects.{name}.value", value)
    
    except:
        
        logging.debug(f"[BACNET] Object {object_name} not found, creating it")
        
        if datatype in datatypes:

            # Get BACnet object characteristics
            bacnet_type = datatypes[datatype].get('type')
            bacnet_units = datatypes[datatype].get('units', 'noUnits')
            
            # Add it to bacnet app
            object_id = bacnet_app.add_object(
                type = globals()[bacnet_type],
                name = object_name,
                description = name,
                value = value,
                units = bacnet_units
            )
            
            # Add object to configuration
            config.set(f"devices.{device_id}.objects.{name}.type", bacnet_type)
            config.set(f"devices.{device_id}.objects.{name}.id", object_id)
            config.set(f"devices.{device_id}.objects.{name}.name", object_name)
            config.set(f"devices.{device_id}.objects.{name}.units", bacnet_units)
            config.set(f"devices.{device_id}.objects.{name}.value", value)

            # Flag to save & reload objects
            save = True

    return save

def update_objects(device, msg):

    logging.debug(f"[MQTT] Message received for {msg.topic}")
    
    device_id = get_device_id(msg)
    decode = config.get(f"devices.{device_id}.decode", True)
    decoder = config.get(f"devices.{device_id}.decoder", "cayenne.js")
    data = get_data(msg, decode, decoder)
    logging.debug(f"[MQTT] Message from {device_id}: {data}")
    save = False

    for element in data:
        save |= update_object(device, device_id, element)

    if save:
        config.set(f"devices.{device_id}.decode", decode)
        config.set(f"devices.{device_id}.decoder", decoder)
        config.save()
        bacnet_app.load()

def load_datatypes():
    datatypes_filename = config.get('datatypes.filename', 'datatypes.yml')
    try:
        with open(f'config/{datatypes_filename}', "r") as f:
            data =  yaml.load(f, Loader=yaml.loader.SafeLoader)
        return data['datatypes']
    except FileNotFoundError:
        logging.error(f"[MAIN] Could not load {datatypes_filename} file")

    return None

def copy_recursive(source_base_path, target_base_path):

    for item in os.listdir(source_base_path):
        
        # Directory
        if os.path.isdir(os.path.join(source_base_path, item)):
            
            # Create destination directory if needed
            new_target_dir = os.path.join(target_base_path, item)
            try:
                os.mkdir(new_target_dir)
            except OSError:
                None

            # Recurse
            new_source_dir = os.path.join(source_base_path, item)
            copy_recursive(new_source_dir, new_target_dir)
        
        # File
        else:
            # Copy file over (not overwriting)
            source_name = os.path.join(source_base_path, item)
            target_name = os.path.join(target_base_path, item)
            if not Path(target_name).is_file():
                shutil.copy(source_name, target_name)


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    
    run = True

    # Copy defaults
    copy_recursive("./templates", "./config")

    # Load configuration file
    config = Config()

    # Set logging level based on settings (10=DEBUG, 20=INFO, ...)
    level=config.get("logging.level", logging.INFO)
    logging.basicConfig(format='[%(asctime)s] %(message)s', level=level)
    logging.info(f"[MAIN] {APP_NAME} {APP_VERSION}")
    logging.debug(f"[MAIN] Setting logging level to {level}")

    # BACnet setup
    try:
        bacnet_app = BACnetApp()
        bacnet_app.create_device(
            ip=config.get('bacnet.ip', get_ip()), 
            port=config.get('bacnet.port', 47808), 
            mask=config.get('bacnet.mask', 24),
            name=config.get('bacnet.name', "LBB"),
            id=config.get('bacnet.id', 0x200001),
        )
        load_bacnet_devices()
    except:
        logging.error(f"[BACNET] Error defining BACnet interface at {config.get('bacnet.ip', get_ip())}:{config.get('bacnet.port', 47808)}")
        run = False
  
    # MQTT setup
    try:
        def mqtt_message_callback(client, userdata, msg):
            update_objects(userdata, msg)
        mqtt_client = MQTTClient(
            config.get('mqtt.server', 'localhost'),
            int(config.get('mqtt.port', 1883)),
            config.get('mqtt.username'),
            config.get('mqtt.password'),
            userdata=bacnet_app.device
        )
        mqtt_client.subscribe(config.get('mqtt.topic', 'v3/+/devices/+/up'))
        mqtt_client.on_message = mqtt_message_callback
    except:
        logging.error(f"[MQTT] Error connecting to MQTT server at {config.get('mqtt.server', 'localhost')}:{config.get('mqtt.port', 1883)}")
        run = False

    # Load default datatypes
    datatypes = load_datatypes()
    if datatypes == None:
        run = False

    # Save defaults
    config.save()

    # Run application
    if run:
        mqtt_client.run()
        bacnet_app.run()
