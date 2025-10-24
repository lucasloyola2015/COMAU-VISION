# Máquina de Estados MQTT

## Estados Implementados

```
┌─────────────────┐
│  DISCONNECTED   │ ◄── Estado inicial
└────────┬────────┘
         │
         │ start()
         ▼
┌─────────────────┐
│   CONNECTING    │ ◄── Intentando conectar al broker
└────┬────────┬───┘
     │        │
     │ OK     │ ERROR
     ▼        ▼
┌─────────────────┐     ┌─────────────────┐
│    CONNECTED    │     │      ERROR      │
│                 │     │ (auto-reconect) │
└────────┬────────┘     └────────┬────────┘
         │                       │
         │ stop() o              │ reconnect()
         │ disconnect            │
         ▼                       ▼
┌─────────────────┐         (vuelve a
│    STOPPING     │         CONNECTING)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DISCONNECTED   │
└─────────────────┘
```

## Transiciones de Estado

| Estado Actual | Evento | Estado Siguiente | Acción |
|--------------|--------|------------------|--------|
| DISCONNECTED | `start()` | CONNECTING | Crear cliente, llamar `connect()` |
| CONNECTING | Conexión OK (rc=0) | CONNECTED | Auto-suscripción a topics |
| CONNECTING | Conexión ERROR (rc≠0) | ERROR | Log del error |
| CONNECTED | `stop()` | STOPPING | Desconectar ordenadamente |
| CONNECTED | Desconexión inesperada | ERROR | Intentar reconexión |
| ERROR | Auto-reconexión | CONNECTING | `client.reconnect()` |
| ERROR | `stop()` | STOPPING | Detener thread |
| STOPPING | Desconexión completa | DISCONNECTED | Thread finaliza |

## Características Actuales

### ✅ Implementado

1. **Thread dedicado** (`_mqtt_worker`)
   - Loop independiente que no bloquea el programa principal
   - Gestión automática del ciclo de vida

2. **Thread-safety**
   - Lock para cambios de estado
   - Event para señal de stop
   - Properties para acceso seguro

3. **Auto-reconexión**
   - Cuando está en estado ERROR
   - Espera 5 segundos entre reintentos
   - Continúa hasta que se llame `stop()`

4. **API limpia**
   - `start()` - Inicia el thread
   - `stop()` - Detiene ordenadamente
   - `state` - Property para leer estado actual
   - `connected` - Property booleana
   - `is_running` - Verifica si el thread está vivo

5. **Auto-suscripción**
   - Se suscribe automáticamente a `topic_subscribe` con QoS 2
   - Ocurre en el callback `on_connect`

### 🔧 Pendiente (esperando guía del usuario)

- Timeouts configurables
- Backoff exponencial en reconexión
- Máximo de reintentos
- Callbacks de cambio de estado
- Buffer de mensajes offline
- Métricas de conexión
- ...

## Configuración de Topics

El sistema usa 3 topics MQTT basados en el patrón COMAU:

| Topic | Propósito | QoS |
|-------|-----------|-----|
| `COMAU/commands` | Recibir comandos JSON estructurados | 2 |
| `COMAU/toRobot` | Recibir texto plano (emulación teclado) | 2 |
| `COMAU/memoryData` | Enviar respuestas y datos de análisis | 2 |

Estos topics se configuran en `config.json`:

```json
{
  "mqtt": {
    "broker_ip": "192.168.1.65",
    "broker_port": 1883,
    "topics": {
      "commands": "COMAU/commands",
      "keyboard": "COMAU/toRobot",
      "responses": "COMAU/memoryData"
    }
  }
}
```

## Uso Básico

```python
import mqtt_manager

# Obtener instancia (singleton)
manager = mqtt_manager.get_mqtt_manager()

# Configurar callbacks (opcional)
manager.on_connect_callback = lambda c, u, f, rc: print("Conectado!")
manager.on_message_callback = lambda c, u, msg: print(f"Mensaje: {msg.payload}")

# Iniciar thread MQTT
manager.start()

# Esperar conexión
while not manager.connected:
    time.sleep(0.1)

# Publicar respuesta (usa topic_responses)
manager.publish(
    manager.topic_responses,
    '{"status": "success", "data": {...}}',
    qos=2
)

# Detener al finalizar
manager.stop()
```

## Probando

```bash
# Asegurarse de tener un broker MQTT corriendo
# Por ejemplo, mosquitto en localhost:1883

python test_mqtt.py
```

