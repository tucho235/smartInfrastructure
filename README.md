# smartInfrastructure

Infraestructura central para `smartEnergy` y `smartEnvironmentSensor`.

- Mosquitto recibe las publicaciones MQTT.
- Telegraf transforma los JSON y escribe en InfluxDB 1.8.
- Grafana consulta las bases `tuya` y `smart_environment`.

## Estado y migración

Esta composición consolida los servicios que ya estaban desplegados:

| Servicio | Contenedor actual | Persistencia actual |
|---|---|---|
| Mosquitto | `mosquitto` | `/opt/stacks/mqtt/{config,data,log}` |
| Telegraf | `smart-env-telegraf` | configuración en `/opt/stacks/telegraf-mqtt-to-influx` |
| InfluxDB 1.8 | `influxdb` | volumen `tucho235_influxdb_data` |
| Grafana | `grafana` | volumen `tucho235_grafana_data` |

Los volúmenes de InfluxDB y Grafana están declarados como `external`, por lo
que no se crean volúmenes vacíos ni se pierden los históricos.

Se generó un backup local en
`backups/20260901-111728/`. El archivo recomendado para InfluxDB es
`influxdb-portable.tgz`; `SHA256SUMS` contiene la verificación de integridad.

Antes de iniciar esta composición, detener los proyectos actuales porque usan
los mismos nombres de contenedor y puertos:

```bash
cp .env.example .env
# Completar MQTT_PASSWORD y GRAFANA_ADMIN_PASSWORD.
sudo docker compose --env-file .env config --quiet

sudo docker compose -f /opt/stacks/telegraf-mqtt-to-influx/docker-compose.yml down
sudo docker compose -f /opt/stacks/mqtt/docker-compose.yml down
sudo docker compose -f /home/tucho235/docker-compose.yml down
sudo docker compose --env-file .env up -d
```

En este equipo `sudo` también es necesario para consultar o administrar Docker
(`sudo docker ps`, `sudo docker compose ...`). Los archivos bajo `/opt/stacks`
son propiedad de otro usuario del sistema; no cambiar sus permisos como parte
de esta migración.

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

## Operación

```bash
docker compose logs -f telegraf
docker compose ps
docker compose down                 # detiene, conserva volúmenes
```
