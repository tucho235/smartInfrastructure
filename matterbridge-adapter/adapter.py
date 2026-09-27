import json
import logging
import os
import time

import paho.mqtt.client as mqtt


SOURCE_TOPIC = os.getenv("MQTT_SOURCE_TOPIC", "smart-energy/tuya/energia")
BASE_TOPIC = os.getenv("MATTERBRIDGE_TOPIC", "matterbridge").strip("/")
DEVICE_ID = os.getenv("MATTERBRIDGE_DEVICE_ID", "smart-energy").strip("/")
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

LEGACY_DEVICE_SUFFIXES = ("voltage", "current", "power")

POWER_ACCURACY = [
    {
        "measurementType": 1,
        "measured": True,
        "minMeasuredValue": 0,
        "maxMeasuredValue": 300000,
        "accuracyRanges": [{"rangeMin": 0, "rangeMax": 300000, "fixedMax": 1000}],
    },
    {
        "measurementType": 2,
        "measured": True,
        "minMeasuredValue": 0,
        "maxMeasuredValue": 100000,
        "accuracyRanges": [{"rangeMin": 0, "rangeMax": 100000, "fixedMax": 1000}],
    },
    {
        "measurementType": 5,
        "measured": True,
        "minMeasuredValue": 0,
        "maxMeasuredValue": 100000000,
        "accuracyRanges": [{"rangeMin": 0, "rangeMax": 100000000, "fixedMax": 1000}],
    },
]

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("matterbridge-adapter")


def device_topic(device_id: str, message_type: str) -> str:
    return f"{BASE_TOPIC}/{device_id}/{message_type}/root"


def remove_legacy_devices(client: mqtt.Client) -> None:
    for suffix in LEGACY_DEVICE_SUFFIXES:
        legacy_device_id = f"{DEVICE_ID}-{suffix}"
        for message_type in ("config", "state", "subscribe"):
            client.publish(device_topic(legacy_device_id, message_type), "", qos=2, retain=True)
        logger.info("Dispositivo Matterbridge anterior retirado: %s", legacy_device_id)


def build_config_payload() -> dict:
    """Build the fixed Matter description for the whole-home energy meter."""
    return {
        "deviceTypes": ["OnOffPlugInUnit", "ElectricalSensor"],
        "clusters": {
            "BridgedDeviceBasicInformation": {
                "nodeLabel": "Consumo total del hogar",
                "serialNumber": DEVICE_ID,
                "productName": "Medidor general MQTT",
            },
            "ElectricalPowerMeasurement": {
                "powerMode": 2,
                "numberOfMeasurementTypes": len(POWER_ACCURACY),
                "accuracy": POWER_ACCURACY,
            },
            "ElectricalEnergyMeasurement": {
                "accuracy": {
                    "measurementType": 14,
                    "measured": True,
                    "minMeasuredValue": 0,
                    "maxMeasuredValue": 9000000000000000,
                    "accuracyRanges": [
                        {"rangeMin": 0, "rangeMax": 9000000000000000, "fixedMax": 1}
                    ],
                },
                "cumulativeEnergyReset": None,
                "cumulativeEnergyImported": None,
                "cumulativeEnergyExported": None,
            },
        },
    }


def publish_config(client: mqtt.Client) -> None:
    payload = build_config_payload()
    topic = device_topic(DEVICE_ID, "config")
    client.publish(topic, json.dumps(payload), qos=2, retain=True)
    logger.info("Matterbridge config publicada en %s", topic)


def to_matter_state(data: dict) -> dict:
    # Matter usa mV, mA, mW y mWh para estas mediciones.
    power_measurement = {}
    if isinstance(data.get("voltaje_V"), (int, float)):
        power_measurement["voltage"] = round(data["voltaje_V"] * 1000)
    if isinstance(data.get("corriente_A"), (int, float)):
        power_measurement["activeCurrent"] = round(data["corriente_A"] * 1000)
    if isinstance(data.get("potencia_W"), (int, float)):
        power_measurement["activePower"] = round(data["potencia_W"] * 1000)
    if not power_measurement:
        raise ValueError("no hay mediciones eléctricas numéricas")

    state = {
        "OnOff": {"onOff": True},
        "ElectricalPowerMeasurement": power_measurement,
    }
    if isinstance(data.get("energia_kWh"), (int, float)) and data["energia_kWh"] >= 0:
        state["ElectricalEnergyMeasurement"] = {
            "cumulativeEnergyImported": {"energy": round(data["energia_kWh"] * 1000000)}
        }
    return state


def on_connect(client: mqtt.Client, _userdata, _flags, reason_code, _properties=None):
    if reason_code != mqtt.MQTT_ERR_SUCCESS:
        logger.error("Error conectando a MQTT: %s", reason_code)
        return
    logger.info("Conectado a MQTT en %s:%s", MQTT_HOST, MQTT_PORT)
    result, _mid = client.subscribe(SOURCE_TOPIC, qos=2)
    if result != mqtt.MQTT_ERR_SUCCESS:
        logger.error("No se pudo suscribir a %s: %s", SOURCE_TOPIC, result)
    else:
        logger.info("Suscripto a %s", SOURCE_TOPIC)
    remove_legacy_devices(client)
    publish_config(client)


def on_message(client: mqtt.Client, _userdata, message):
    try:
        data = json.loads(message.payload.decode("utf-8"))
        state = to_matter_state(data)
        topic = device_topic(DEVICE_ID, "state")
        client.publish(topic, json.dumps(state), qos=2, retain=True)
        logger.info("Estado Matterbridge actualizado: %s", state)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Mensaje inválido en %s: %s", message.topic, exc)


def main() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="smart-energy-matterbridge-adapter")
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.reconnect_delay_set(min_delay=2, max_delay=60)
    client.on_connect = on_connect
    client.on_message = on_message
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_forever()
        except OSError as exc:
            logger.warning("MQTT no disponible: %s; reintentando", exc)
            time.sleep(10)


if __name__ == "__main__":
    main()
