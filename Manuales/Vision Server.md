# Manual de API del Servicio de Visión

Este documento describe cómo interactuar con la API del Servicio de Visión por Computador. El objetivo de esta API es recibir una imagen, procesarla para identificar una junta y sus características, y devolver una trayectoria para un robot.

## 1. Información General

- **URL Base**: El servicio se ejecuta localmente. La URL base es `http://127.0.0.1:8000`.
- **Formato de Datos**: La API utiliza JSON para las respuestas y `multipart/form-data` para las solicitudes que incluyen archivos.
- **Interfaz Web**: Puedes acceder a una interfaz de cliente web simple visitando la URL base (`http://127.0.0.1:8000`) en tu navegador.

---

## 2. Endpoints Principales

### Endpoint de Procesamiento de Imagen

### **`POST /process/`**

Procesa una imagen para detectar la trayectoria de una junta.

### Solicitud (Request)

La solicitud debe ser de tipo `POST` y contener los datos de la imagen en formato `multipart/form-data`.

**Parámetros:**

| Campo | Tipo   | Descripción                                                                                             | Requerido |
| :---- | :----- | :------------------------------------------------------------------------------------------------------ | :-------- |
| `file`  | `File` | El archivo de imagen que se va a procesar. Formatos comunes como PNG, JPEG, BMP son soportados. | Sí        |

**Ejemplo de solicitud con `curl`:**

```bash
curl -X POST "http://127.0.0.1:8000/process/" -F "file=@/ruta/a/tu/imagen.png"
```

**Ejemplo de solicitud con Python (`requests`):**

```python
import requests

# URL del endpoint
url = "http://127.0.0.1:8000/process/"

# Ruta de la imagen a enviar
image_path = "imagenes/1.png"

# Abrir la imagen en modo binario y enviarla
with open(image_path, "rb") as image_file:
    files = {"file": (image_path, image_file, "image/png")}
    response = requests.post(url, files=files)

if response.status_code == 200:
    print("Solicitud exitosa!")
    data = response.json()
    # Procesar 'data'
else:
    print(f"Error: {response.status_code}")
    print(response.text)
```

### Respuesta (Response)

Si la solicitud es exitosa, el servidor responderá con un código de estado `200 OK` y un cuerpo de respuesta en formato JSON.

**Estructura del JSON de Respuesta:**

| Clave                    | Tipo                | Descripción                                                                                                                                                                                                                         |
| :----------------------- | :------------------ | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `status`                 | `string`            | Indica el resultado general del procesamiento. Será `"success"` si se pudo generar una trayectoria, o `"failure"` en caso contrario.                                                                                              |
| `junta_detectada`        | `boolean`           | `true` si el modelo YOLO detectó la junta, `false` si no.                                                                                                                                                                           |
| `holes_detectados`       | `integer`           | El número total de agujeros (holes) detectados por el segundo modelo YOLO.                                                                                                                                                          |
| `aruco_base_detectado`   | `boolean`           | `true` si el marcador ArUco de la base fue detectado, `false` si no.                                                                                                                                                                |
| `aruco_tool_detectado`   | `boolean`           | `true` si el marcador ArUco de la herramienta fue detectado, `false` si no.                                                                                                                                                         |
| `overlay_image`          | `string`            | Una imagen en formato PNG, codificada en **Base64**. Esta imagen es un overlay que muestra visualmente los resultados del procesamiento (detecciones, ejes, segmentos, etc.).                                                     |
| `trajectory_vectors`     | `Array<Object>`     | Una lista de objetos, donde cada objeto representa un vector de movimiento de la trayectoria. **Este es el dato principal que debe usar el robot**. Los vectores están ordenados secuencialmente para formar la trayectoria. |

**Estructura del Objeto Vector (`trajectory_vectors`):**

| Clave       | Tipo            | Descripción                                                                                                                                                                                                                                                        |
| :---------- | :-------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `segmento`  | `string`        | Una descripción textual del segmento de la trayectoria (ej: "Muesca 1 -> Troqueladora", "Muesca 2 -> Muesca 1").                                                                                                                                                    |
| `vector_mm` | `Array<number>` | Un array con dos valores `[x, y]` que representan las componentes del vector de movimiento en milímetros. **Importante**: Estas coordenadas están expresadas relativas al sistema de coordenadas `TOOL_FRAME` detectado en la imagen. |

**Ejemplo de Respuesta JSON:**

```json
{
  "status": "success",
  "junta_detectada": true,
  "holes_detectados": 2,
  "aruco_base_detectado": true,
  "aruco_tool_detectado": true,
  "overlay_image": "iVBORw0KGgoAAAANSUhEUgAAB... (cadena base64 muy larga) ...FTkSuQmCC",
  "trajectory_vectors": [
    {
      "segmento": "Muesca 1 -> Troqueladora",
      "vector_mm": [ 15.34, -10.21 ]
    },
    {
      "segmento": "Muesca 2 -> Muesca 1",
      "vector_mm": [ 50.05, 1.12 ]
    }
  ]
}
```

### Manejo de Errores

En caso de un error en el servidor (por ejemplo, si no se puede procesar la imagen), la API devolverá un código de estado HTTP diferente de `200` (como `4xx` o `5xx`) y el cuerpo de la respuesta podría contener detalles sobre el error.

---

## 3. Endpoints de Configuración

Estos endpoints permiten ver y modificar la configuración del servicio (`vision_config.json`) en tiempo real, sin necesidad de reiniciar el servidor.

### **`GET /config/`**

Obtiene la configuración completa que el servicio está utilizando actualmente.

**Ejemplo de solicitud con `curl`:**

```bash
curl -X GET "http://127.0.0.1:8000/config/"
```

**Respuesta:**

El servidor responderá con un código `200 OK` y un cuerpo JSON que es una réplica exacta del archivo `vision_config.json` actual.

### **`PATCH /config/`**

Actualiza uno o más parámetros de la configuración. Puedes enviar solo las claves que deseas modificar.

**Solicitud (Request):**

La solicitud debe ser de tipo `PATCH` con un cuerpo JSON. La estructura del JSON debe seguir la de `vision_config.json`, pero solo incluyendo los campos a actualizar.

**Ejemplo 1: Actualizar un solo valor**

```bash
curl -X PATCH "http://127.0.0.1:8000/config/" \
-H "Content-Type: application/json" \
-d '{
    "vision_params": {
        "blue_threshold": 95
    }
}'
```

**Ejemplo 2: Actualizar múltiples valores anidados**

```bash
curl -X PATCH "http://127.0.0.1:8000/config/" \
-H "Content-Type: application/json" \
-d '{
    "control_flags": {
        "usar_roi": false
    },
    "scale_factors": {
        "scale_factor_yolo": 0.9
    }
}'
```

**Ejemplo 3: Configurar coordenadas de la troqueladora y ArUcos**

```bash
curl -X PATCH "http://127.0.0.1:8000/config/" \
-H "Content-Type: application/json" \
-d '{
    "aruco_config": {
        "aruco_base_id": 23,
        "aruco_base_size_mm": 70.0,
        "aruco_tool_id": 4,
        "aruco_tool_size_mm": 50.0
    },
    "troqueladora": {
        "x_mm": -101,
        "y_mm": -25,
        "diametro_mm": 10
    }
}'
```

**Estructura de configuración para troqueladora:**

| Clave | Tipo | Descripción |
| :---- | :--- | :---------- |
| `x_mm` | `number` | Coordenada X del centro de la troqueladora en milímetros (relativa al ArUco base) |
| `y_mm` | `number` | Coordenada Y del centro de la troqueladora en milímetros (relativa al ArUco base) |
| `diametro_mm` | `number` | Diámetro del círculo que representa el centro del troquel en milímetros |

**Estructura de configuración para ArUcos:**

| Clave | Tipo | Descripción |
| :---- | :--- | :---------- |
| `aruco_base_id` | `integer` | ID del marcador ArUco de la base |
| `aruco_base_size_mm` | `number` | Tamaño del marcador ArUco base en milímetros |
| `aruco_tool_id` | `integer` | ID del marcador ArUco de la herramienta |
| `aruco_tool_size_mm` | `number` | Tamaño del marcador ArUco de la herramienta en milímetros |

**Respuesta:**

Si la actualización es exitosa, el servidor responderá con un código `200 OK` y el cuerpo de la respuesta será la **configuración completa y actualizada**.

---

## 4. Endpoint de Estado del Servidor

### **`GET /health/`**

Verifica si el servicio está en funcionamiento y respondiendo a las solicitudes.

**Ejemplo de solicitud con `curl`:**

```bash
curl -X GET "http://127.0.0.1:8000/health/"
```

**Respuesta:**

Si el servidor está activo, responderá con un código `200 OK` y el siguiente JSON:

```json
{
  "status": "ok",
  "message": "Servicio de Visión funcionando correctamente."
}
```