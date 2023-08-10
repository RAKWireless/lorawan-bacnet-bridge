LoRaWAN to BACnet Bridge
==========================

The LoRaWAN to BACnet Bridge is a service to forward LoRaWAN messages from sensors to a BACnet BMS.

The service fetches the data form the LNS via MQTT, processes it and publishes it as BACnet objects on the specified LAN using BACnet/IP.

## Configuration

The service gets the configuration information from a `config.yml` file in the `config` folder. You have an example of that file down below. Alternatively you can overwrite settings in the `config.yml` file with environment variables. This configuration file has the following options:

|Section.Key|Environment|Description|Default|
|---|---|---|---|
|bacnet.ip|BACNET_IP|IP of the local devices publishing the BACnet objects|LAN IP|
|bacnet.port|BACNET_PORT|Port to listen to connections|47808|
|bacnet.mask|BACNET_MASK|IP mask to accepts whois queries from|24|
|mqtt.server|MQTT_SERVER|IP or hostname of the MQTT broker to connect to|localhost|
|mqtt.port|MQTT_PORT|Port of the MQTT server|1883|
|mqtt.username|MQTT_USERNAME|Username to use in the MQTT connection||
|mqtt.password|MQTT_PASSWORD|Password to use in the MQTT connection||
|mqtt.topic|MQTT_TOPIC|MQTT Topic to subscribe to|`v3/+/devices/+/up`|
|logging.level|LOGGING_LEVEL|Logging level (10:debug, 20:info, 30:warning, 40:error)|20|
|datatypes.filename|DATATYPES_FILENAME|Default datatypes definition file|`datatypes.yml`|
|devices.\<device\>.decode||Force decoding payload instead of using existing decoded payload if any|True|
|devices.\<device\>.decoder||Decoder to use for the specific device_id (see decoders folder)|`cayenne.js`|
|devices.\<device\>.objects.\<name\>.type||BACnet object type||
|devices.\<device\>.objects.\<name\>.name||BACnet object name||
|devices.\<device\>.objects.\<name\>.value||BACnet object last value||
|devices.\<device\>.objects.\<name\>.units||BACnet object unit type||

The `Section.Key` field in the table above is a flattened version of the YAML file. So if you have a YAML file with:

```
section:
    key: 10
    objects: 
        first: 20
        second: 30
```

`section.key` has a value of `10` and `section.objects.first` is 20.

The minimal configuration file is (basically the connection to the LNS via MQTT):

```
mqtt:
  password: NNSXS.Z6.....FF6YYQ
  port: 1883
  server: eu1.cloud.thethings.network
  topic: v3/+/devices/+/up
  username: my-app02@ttn

```

After running the service, it will connect to the LNS via MQTT and start receiving messages from actual sensors. If the payload of the messages is compatible (i.e. CayenneLPP) then it will populate new BACnet devices and objects in the `config.yml` file. If you now stop the service your `config.yml` file might look like this:

```
bacnet:
  ip: 192.168.1.132
  mask: 24
  port: 47808
datatypes:
  filename: datatypes.yml
devices:
  wisblock-01:
    decode: true
    decoder: cayenne.js
    objects:
      field-001-temperature:
        name: wisblock-01-field-001-temperature
        type: AnalogInputObject
        units: degreesCelsius
        value: 24.3
      field-002-humidity:
        name: wisblock-01-field-002-humidity
        type: AnalogInputObject
        units: percentRelativeHumidity
        value: 49
      field-003-barometer:
        name: wisblock-01-field-003-barometer
        type: AnalogInputObject
        units: hectopascals
        value: 988.8
      rssi:
        name: wisblock-01-rssi
        type: AnalogInputObject
        units: decibels
        value: -53
      snr:
        name: wisblock-01-snr
        type: AnalogInputObject
        units: decibels
        value: 13.75
logging:
  level: 20
mqtt:
  password: NNSXS.Z6.....FF6YYQ
  port: 1883
  server: eu1.cloud.thethings.network
  topic: v3/+/devices/+/up
  username: my-app02@ttn

```

Of course you can start with a complete `config.yml` file upfront. Only remember not to edit the `config.yml` file while running the service since the changes will be overwritten.

## Usage

### Python virtual environment 

The recommended way to run the script is by using a virtual environment to install the dependencies in `requirements.txt`. We provide a custom `Makefile` to help you run it in an isolated python environment by typing:

```
make run
```

This will create the virtual environment and install dependencies the first time it's run and then run the service.

### Docker

You can also use docker to run the service isolated from your system. We provide a custom `Dockerfile` and `docker-compose.yml` files for this. Please check the `docker-compose.yml` file for an example on the different ways to configure the service (mount a `config` folder and/or use environment variables).

```
docker compose up
```

You can also build the image directly on your target machine by uncommenting the `build` option (and suboptions) from the provided `docker-compose.yml` file and do a `docker compose build` first.

## How does it work

### Default configuration

The service will look for the configuration files (`config.yml`, `datatypes.yml` and any `*.js` files under the `decoders` subfolder) under the `config` folder. If this folder does not exist, or any of the required files do not exist, it will get the default ones from the `templates` folder and copy them over the `config` folder. Files in the `templates` folder are never changed.

The `config.yml` file is populated with defaults on each run (does not overwrite existing settings). You can then stop the service and edit the `config.yml` file to check the default values.

### Device discovery

The LoRaWAN to BACnet Bridge listens to messages from the LNS sent via MQTT. Currently, it understands The Things Stack v2 (TTN/TTI) and ChirpStack v3 and v4 payloads.

Similar to what different LNS do, the service decodes the raw payload using Javascript decoders in the `decoders` folder (alternatively you can set it to use the pre-decoded object from the LNS). Either way it expects a cayenne-like output to map new magnitudes from different sensors to BACnet objects. 

These decoders are very similar to the ones in The Things Stack or ChirpStack. Check the `templates/decoders/template.js` file for an example of the input and output interface for the decoders. 

### Manually edit object list

After running the service, the `config.yml` file will contain all default values as well as information for discovered objects. You can edit this file manually with the service stopped. Make sure you define the object type and units correctly using the values from the `BACNET.md` file.

### Copyright and license

Copyright (c) 2023 RAKwireless, under MIT License.