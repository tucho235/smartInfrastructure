# smartInfrastructure

Infraestructura central de telemetría, visualización e integración Matter para
`smartEnergy`, los sensores ambientales y el monitoreo WAN del router MikroTik.

```text
Sensores / smartEnergy / MikroTik
              |
              v
          Mosquitto
          /       \
         v         v
     Telegraf   matterbridge-adapter
         |            |
         v            v
     InfluxDB      Matterbridge
         |            |
         v            v
      Grafana      SmartThings
```

## Servicios

| Servicio | Contenedor | Función | Persistencia |
|---|---|---|---|
| Mosquitto | `mosquitto` | Broker MQTT autenticado | `./mosquitto/data`, `./mosquitto/log` |
| Telegraf | `smart-env-telegraf` | MQTT → InfluxDB | `./telegraf/telegraf.conf` |
| InfluxDB 1.8 | `influxdb` | Series temporales | Volumen externo `tucho235_influxdb_data` |
| Grafana | `grafana` | Dashboards y datasources | Volumen externo `tucho235_grafana_data` |
| Matterbridge | `matterbridge` | Bridge Matter para SmartThings | `./matterbridge/{Matterbridge,.matterbridge,.mattercert}` |
| Adaptador Matterbridge | `matterbridge-adapter` | Energía MQTT → clusters Matter | Sin estado persistente |

Los volúmenes de InfluxDB y Grafana son externos. `docker compose down` no los
elimina, pero `docker compose down -v` no debe usarse como procedimiento de
operación habitual.

## Configuración inicial

1. Crear los volúmenes persistentes si el host todavía no los tiene:

   ```bash
   docker volume create tucho235_influxdb_data
   docker volume create tucho235_grafana_data
   ```

2. Crear la configuración local:

   ```bash
   cp .env.example .env
   ```

3. Completar en `.env` las contraseñas MQTT, MikroTik y Grafana. `.env` está
   excluido de Git.

4. Crear `mosquitto/config/passwd` con los usuarios declarados en `.env`. El
   broker tiene `allow_anonymous false`; todo publicador y consumidor debe
   autenticarse.

5. Validar y desplegar:

   ```bash
   docker compose config --quiet
   docker compose up -d
   docker compose ps
   ```

## Variables de entorno

| Variable | Predeterminado | Uso |
|---|---|---|
| `MQTT_PORT` | `1883` | Puerto MQTT publicado en el host |
| `MQTT_PASSWORD_FILE` | `./mosquitto/config/passwd` | Usuarios de Mosquitto |
| `MQTT_USERNAME` | `esp32` | Usuario de sensores, energía y Matterbridge |
| `MQTT_PASSWORD` | requerido | Contraseña MQTT general |
| `MQTT_ENV_TOPIC` | `smart-environment-sensor/bme680/state` | Ambiente interior |
| `MQTT_ENV_OUTDOOR_TOPIC` | `smart-environment-sensor/outdoor/state` | Ambiente exterior |
| `MQTT_ENERGY_TOPIC` | `smart-energy/tuya/energia` | Energía general |
| `MQTT_MIKROTIK_TOPIC` | `mikrotik/router/wan` | Estado WAN |
| `MQTT_MIKROTIK_USER` | `mikrotik` | Usuario MQTT del router |
| `MQTT_MIKROTIK_PASSWORD` | requerido | Contraseña MQTT del router |
| `INFLUXDB_ENERGY_DB` | `tuya` | Base de energía |
| `INFLUXDB_ENV_DB` | `smart_environment` | Base ambiental |
| `INFLUXDB_NETWORK_DB` | `network` | Base de red |
| `INFLUXDB_PORT` | `8086` | Puerto InfluxDB del host |
| `GRAFANA_PORT` | `3001` | Puerto Grafana del host |
| `GRAFANA_ADMIN_USER` | `admin` | Administrador inicial |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | Contraseña inicial |

Las contraseñas deben definirse explícitamente en producción. Los valores
predeterminados describen Compose, no son una recomendación de seguridad.

## Acceso local

| Servicio | Dirección |
|---|---|
| MQTT | `localhost:1883` |
| InfluxDB | <http://localhost:8086> |
| Grafana | <http://localhost:3001> |
| Matterbridge | <http://localhost:8283> |

Desde los contenedores, Mosquitto e InfluxDB se alcanzan como
`mosquitto:1883` e `influxdb:8086`. Matterbridge usa la red del host para que
Matter disponga de mDNS e IPv6 local.

## MQTT e InfluxDB

Telegraf mantiene consumidores independientes para no mezclar campos de
sensores distintos. Cada mensaje conserva el tópico como tag `topic`.

| Origen | Tópico MQTT | QoS | Base InfluxDB | Medición |
|---|---|---:|---|---|
| Ambiente interior | `smart-environment-sensor/bme680/state` | 0 | `smart_environment` | `environment` |
| Ambiente exterior | `smart-environment-sensor/outdoor/state` | 0 | `smart_environment` | `environment_outdoor` |
| Energía general | `smart-energy/tuya/energia` | 1 | `tuya` | `energia` |
| MikroTik WAN | `mikrotik/router/wan` | 1 | `network` | `mikrotik_wan` |

### Ambiente interior

El BME680 publica temperatura, humedad y presión:

```json
{
  "temperature_c": 24.32,
  "humidity_percent": 50.44,
  "pressure_hpa": 1011.62
}
```

Tags fijos: `device=esp32c3-supermini` y `sensor=bme680`.

### Ambiente exterior

El sensor exterior publica temperatura y humedad, sin presión:

```json
{
  "temperature_c": 18.75,
  "humidity_percent": 63.2
}
```

Tags fijos: `device=outdoor-sensor` y `location=outdoor`.

### Energía

`smartEnergy` publica:

```json
{
  "voltaje_V": 230.4,
  "corriente_A": 1.2,
  "potencia_W": 250,
  "potencia_VA": 276.48,
  "factor_potencia": 0.9,
  "energia_kWh": 15465.6,
  "alarma_sobrevoltaje": 0,
  "alarma_sobrecorriente": 0
}
```

`energia_kWh` es opcional para Telegraf. Los demás campos forman parte del
contrato esperado por el consumidor actual.

### MikroTik WAN

La medición `mikrotik_wan` guarda como enteros los estados `claro_link` y
`fibertel_link`; las sondas `claro_a`, `claro_b`, `fibertel_a` y `fibertel_b`;
y los estados `main_*` y `fallback_*` de cada enlace.

## Grafana

Los datasources se provisionan desde
`grafana/provisioning/datasources/influxdb.yaml`:

| Datasource | UID | Base |
|---|---|---|
| InfluxDB | `influxdb` | `tuya` |
| InfluxDB Tuya Legacy | `P951FEA4DE68E13C5` | `tuya` |
| InfluxDB Environment | `environment-influxdb` | `smart_environment` |
| InfluxDB Network | `network-influxdb` | `network` |

Los dashboards ambientales versionados se provisionan en la raíz de Grafana:

| Dashboard | UID | Archivo | Paneles |
|---|---|---|---|
| Monitor Ambiental Interior | `addl8nn` | `grafana/provisioning/root-dashboards/environment-interior.json` | Valores actuales y gráficos separados de temperatura, humedad y presión |
| Monitor Ambiental Exterior | `environment-outdoor-v1` | `grafana/provisioning/root-dashboards/environment-outdoor.json` | Valores actuales y gráficos separados de temperatura y humedad |

Los JSON son la fuente de verdad. Un cambio hecho desde Grafana debe exportarse
y versionarse para sobrevivir una reprovisión. Los UID se conservan para que
una actualización reemplace el recurso existente y no cree duplicados.

`grafana/provisioning/dashboards/provider.yml` define los proveedores. El
proveedor `root` administra los dashboards ambientales sin asignarlos a la
carpeta `smartEnergy`.

## Matterbridge

Matterbridge expone el medidor general como un endpoint Matter con los tipos
`OnOffPlugInUnit` y `ElectricalSensor`. `OnOff` permanece encendido virtualmente:
el dispositivo representa un medidor y no controla el suministro.

La configuración inicial de `matterbridge-mqtt` se realiza en
<http://localhost:8283>:

```text
Broker: mqtt://localhost
Puerto: 1883
Usuario: MQTT_USERNAME
Contraseña: MQTT_PASSWORD
Prefijo: matterbridge
```

`matterbridge/matterbridge-mqtt.config.example.json` es una referencia sin
secretos. La configuración efectiva, los certificados y el estado interno
quedan en directorios excluidos de Git bajo `matterbridge/`.

El adaptador consume `smart-energy/tuya/energia`, publica configuración y
estado retenidos bajo `matterbridge/`, y convierte las unidades así:

```text
voltaje_V   -> ElectricalPowerMeasurement.voltage (mV)
corriente_A -> ElectricalPowerMeasurement.activeCurrent (mA)
potencia_W  -> ElectricalPowerMeasurement.activePower (mW)
energia_kWh -> ElectricalEnergyMeasurement.cumulativeEnergyImported (mWh)
```

`matterbridge/node-topology-register.mjs` cambia solo `smart-energy` de
`TreeTopology` a `NodeTopology`, porque representa el consumo total del hogar y
no una jerarquía de endpoints hijos.

## Operación y diagnóstico

```bash
# Estado y logs
docker compose ps
docker compose logs -f telegraf
docker compose logs -f grafana
docker compose logs -f matterbridge matterbridge-adapter

# Validar configuración
docker compose config --quiet
jq empty grafana/provisioning/root-dashboards/*.json

# Aplicar cambios de Telegraf o Grafana
docker compose up -d telegraf grafana

# Detener sin borrar datos
docker compose down
```

Para consultar las mediciones:

```bash
docker exec influxdb influx -database smart_environment -execute 'SHOW MEASUREMENTS'
docker exec influxdb influx -database tuya -execute 'SHOW MEASUREMENTS'
docker exec influxdb influx -database network -execute 'SHOW MEASUREMENTS'
```

Pruebas del adaptador Matterbridge:

```bash
cd matterbridge-adapter
python -m unittest test_adapter.py
```

## Estructura relevante

```text
compose.yaml
telegraf/telegraf.conf
mosquitto/mosquitto.conf
grafana/provisioning/
  dashboards/provider.yml
  datasources/influxdb.yaml
  root-dashboards/
    environment-interior.json
    environment-outdoor.json
matterbridge-adapter/
matterbridge/
```
