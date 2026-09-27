# smartInfrastructure

Infraestructura central para `smartEnergy` y `smartEnvironmentSensor`.

- Mosquitto recibe las publicaciones MQTT.
- Telegraf transforma los JSON y escribe en InfluxDB 1.8.
- Grafana consulta las bases `tuya` y `smart_environment`.

Los dashboards y datasources versionados del sistema viven bajo
`grafana/provisioning/`; los repositorios de medición no mantienen copias
locales de esta configuración.

## Estado del despliegue

Esta composición es el despliegue activo y consolida los servicios de
`smartEnergy` y `smartEnvironmentSensor`:

| Servicio | Contenedor actual | Persistencia actual |
|---|---|---|
| Mosquitto | `mosquitto` | `./mosquitto/{config,data,log}` |
| Telegraf | `smart-env-telegraf` | `./telegraf/telegraf.conf` y `.env` local |
| InfluxDB 1.8 | `influxdb` | volumen `tucho235_influxdb_data` |
| Grafana | `grafana` | volumen `tucho235_grafana_data` |
| Matterbridge | `matterbridge` | `./matterbridge/{Matterbridge,.matterbridge,.mattercert}` |
| Adaptador Matterbridge | `matterbridge-adapter` | sin estado persistente |

Los volúmenes de InfluxDB y Grafana están declarados como `external`, por lo
que no se crean volúmenes vacíos ni se pierden los históricos.

Los directorios antiguos de `/opt/stacks/mqtt` y
`/opt/stacks/telegraf-mqtt-to-influx` se conservaron temporalmente como backup
de rollback y ya no son montajes de los contenedores activos. No borrar esos
directorios hasta completar la verificación final.

Se generó un backup local en
`backups/20260901-111728/`. El archivo recomendado para InfluxDB es
`influxdb-portable.tgz`; `SHA256SUMS` contiene la verificación de integridad.

Para desplegar esta composición en otro host:

```bash
cp .env.example .env
# Completar MQTT_PASSWORD y GRAFANA_ADMIN_PASSWORD.
sudo docker compose --env-file .env config --quiet

sudo docker compose --env-file .env up -d
```

En este equipo `sudo` también es necesario para consultar o administrar Docker
(`sudo docker ps`, `sudo docker compose ...`). Los stacks independientes de
`/opt/stacks/hass`, `/opt/stacks/immich`, `/opt/stacks/openwebui` y cualquier
otro stack ajeno a este proyecto no deben detenerse durante esta operación.

No usar `docker compose down -v` durante la migración. Hacer una copia de
seguridad de los volúmenes antes de cambiar el despliegue.

## Acceso

| Servicio | Dirección |
|---|---|
| MQTT | `localhost:1883` |
| InfluxDB | <http://localhost:8086> |
| Grafana | <http://localhost:3001> |

Desde los scripts ejecutados en el host, MQTT es `localhost:1883`. Dentro de
esta composición, el broker es `mosquitto:1883`.

## Contrato MQTT

Tópicos actuales:

```text
smart-energy/tuya/energia
smart-environment-sensor/bme680/state
```

`smartEnergy` publica JSON con campos como:

```json
{
  "voltaje_V": 230.4,
  "corriente_A": 1.2,
  "potencia_W": 250,
  "potencia_VA": 276.48,
  "factor_potencia": 0.9,
  "alarma_sobrevoltaje": 0,
  "alarma_sobrecorriente": 0
}
```

`smartEnvironmentSensor` publica:

```json
{
  "temperature_c": 24.32,
  "humidity_percent": 50.44,
  "pressure_hpa": 1011.62
}
```

Telegraf guarda energía en la medición `energia` de `tuya`, y ambiente en la
medición `environment` de `smart_environment`.

## Matterbridge

Matterbridge expone dispositivos virtuales Matter a partir de dispositivos
MQTT mediante el plugin oficial `matterbridge-mqtt`. Usa el modo de red del
host porque Matter necesita mDNS y conectividad IPv6 local.

El contenedor se administra desde esta composición, pero el primer ajuste del
plugin se realiza en la interfaz web de Matterbridge:

```text
http://<IP_DEL_HOST>:8283
```

Instalar o activar `matterbridge-mqtt` y configurar:

```text
Broker: mqtt://localhost
Puerto: 1883
Usuario: el valor de MQTT_USERNAME en .env
Contraseña: el valor de MQTT_PASSWORD en .env
Prefijo: matterbridge
```

El archivo de ejemplo está en
`matterbridge/matterbridge-mqtt.config.example.json`; no contiene secretos y
se puede usar como referencia. La configuración efectiva queda en
`matterbridge/.matterbridge/` y está excluida de Git.

Para crear el dispositivo eléctrico de `smartEnergy`, el plugin debe recibir
mensajes MQTT retenidos de configuración y estado bajo el prefijo configurado.
El tópico actual `smart-energy/tuya/energia` contiene los datos de origen, pero
no tiene por sí solo el formato de control de Matterbridge. El mapeo
es:

```text
voltaje_V   -> ElectricalPowerMeasurement.voltage (mV)
corriente_A -> ElectricalPowerMeasurement.activeCurrent (mA)
potencia_W  -> ElectricalPowerMeasurement.activePower (mW)
energia_kWh -> ElectricalEnergyMeasurement.cumulativeEnergyImported (mWh)
```

Para mejorar la compatibilidad con SmartThings, el adaptador presenta un único
endpoint Matter con los tipos `OnOffPlugInUnit` y `ElectricalSensor`. El estado
`OnOff` se mantiene encendido de forma virtual: representa un medidor y no
controla físicamente el suministro eléctrico. El endpoint usa `PowerTopology`
con la feature `NodeTopology`, porque sus valores representan el consumo total
del hogar y no el consumo de un endpoint hijo. La extensión localizada
`matterbridge/node-topology-register.mjs` corrige el valor `TreeTopology` que el
plugin MQTT crea por defecto, únicamente para el dispositivo `smart-energy`.
SmartThings debería exponer la potencia y la energía acumulada como capacidades
del enchufe. La tensión y la corriente permanecen en los atributos Matter
estándar, aunque la interfaz actual de SmartThings puede no mostrarlas.

El televisor y otros dispositivos registrados por separado en SmartThings no
son hijos Matter de este medidor. Su consumo físico ya forma parte del total,
pero SmartThings no deduce ni resta automáticamente esos consumos individuales.

El dispositivo Matterbridge se empareja con el hub Matter de forma
independiente de `smartEnvironmentSensor`; una caída de Matterbridge no
interrumpe MQTT, InfluxDB, Grafana ni el dispositivo ESP32.

El adaptador `matterbridge-adapter` transforma el JSON de
`smart-energy/tuya/energia` en mensajes MQTT retenidos bajo el prefijo
`matterbridge/`. Publica un enchufe medidor virtual que combina los clusters
estándar `ElectricalPowerMeasurement` y `ElectricalEnergyMeasurement`.

## Operación

```bash
docker compose logs -f telegraf
docker compose ps
docker compose down                 # detiene, conserva volúmenes
```
