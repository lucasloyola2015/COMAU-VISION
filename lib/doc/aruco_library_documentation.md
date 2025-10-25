# ArUco Library - Librería Genérica de Detección de ArUcos

## ⚠️ IMPORTANTE: LIBRERÍA GENÉRICA

**Esta librería es GENÉRICA y NO debe ser modificada con:**
- ❌ Elementos hardcodeados específicos del dominio
- ❌ Funciones específicas del proyecto  
- ❌ Configuraciones específicas del negocio
- ❌ Marcos de referencia predefinidos
- ❌ Dependencias de sistemas específicos

**Para funcionalidades específicas del proyecto, usar `aruco_manager.py`**

---

## 📚 **Funciones Disponibles**

### **1. `detect_aruco_by_id()` - Detección Específica**

Detecta un ArUco específico por ID con parámetros explícitos.

```python
def detect_aruco_by_id(image, target_id: int, dictionary_id: int, marker_bits: int, marker_size_mm: float) -> Optional[Dict]
```

**Parámetros:**
- `image`: Imagen de OpenCV (numpy array)
- `target_id`: ID del ArUco a buscar
- `dictionary_id`: ID del diccionario (50, 100, 250, 1000)
- `marker_bits`: Tamaño de matriz (4, 5, 6, 7)
- `marker_size_mm`: Tamaño real en mm

**Retorna:**
```python
{
    'id': int,                    # ID del ArUco encontrado
    'center': (x, y),            # Centro en píxeles
    'corners': [[x1,y1], ...],   # Esquinas del ArUco
    'px_per_mm': float,          # Relación píxeles/mm
    'rotation_matrix': [[...]], # Matriz de rotación
    'detected_ids': [int, ...]   # Todos los IDs detectados
}
```

**Ejemplo:**
```python
from lib.aruco import detect_aruco_by_id

resultado = detect_aruco_by_id(
    image=mi_imagen,
    target_id=23,
    dictionary_id=50,
    marker_bits=4,
    marker_size_mm=70.0
)

if resultado:
    print(f"ArUco {resultado['id']} detectado en {resultado['center']}")
    print(f"px_per_mm: {resultado['px_per_mm']:.3f}")
```

---

### **2. `detect_all_arucos()` - Detección Múltiple**

Detecta TODOS los ArUcos presentes en la imagen.

```python
def detect_all_arucos(image, dictionary_id: int, marker_bits: int, marker_size_mm: float) -> Optional[Dict]
```

**Parámetros:**
- `image`: Imagen de OpenCV (numpy array)
- `dictionary_id`: ID del diccionario (50, 100, 250, 1000)
- `marker_bits`: Tamaño de matriz (4, 5, 6, 7)
- `marker_size_mm`: Tamaño real en mm

**Retorna:**
```python
{
    'detected_ids': [int, ...],           # Lista de IDs detectados
    'markers': [                          # Lista de marcadores
        {
            'id': int,                    # ID del ArUco
            'center': (x, y),             # Centro en píxeles
            'px_per_mm': float           # Relación píxeles/mm
        },
        ...
    ]
}
```

**Ejemplo:**
```python
from lib.aruco import detect_all_arucos

resultado = detect_all_arucos(
    image=mi_imagen,
    dictionary_id=50,
    marker_bits=4,
    marker_size_mm=42.0
)

if resultado:
    print(f"ArUcos detectados: {resultado['detected_ids']}")
    for marker in resultado['markers']:
        print(f"ID {marker['id']}: centro {marker['center']}")
```

---

### **3. `detect_arucos_with_config()` - Detección con Configuración**

Detecta ArUcos usando configuración personalizada.

```python
def detect_arucos_with_config(image: np.ndarray, aruco_configs: List[Dict[str, Any]], 
                             dictionary_id: int, marker_bits: int) -> Dict[str, Any]
```

**Parámetros:**
- `image`: Imagen de OpenCV (numpy array)
- `aruco_configs`: Lista de configuraciones `[{"id": int, "name": str, "size_mm": float, "color": tuple}]`
- `dictionary_id`: ID del diccionario (50, 100, 250, 1000)
- `marker_bits`: Tamaño de matriz (4, 5, 6, 7)

**Retorna:**
```python
{
    'detected_arucos': {                  # Diccionario por ID
        aruco_id: {
            'center': (x, y),            # Centro en píxeles
            'angle_rad': float,          # Ángulo en radianes
            'corners': [[x1,y1],        # Esquinas del ArUco
            'px_per_mm': float,         # Relación píxeles/mm
            'config': {...}             # Configuración original
        }
    },
    'detected_ids': [int, ...],          # Lista de IDs detectados
    'detection_status': {                # Estado de detección por nombre
        'frame': bool,                   # Si se detectó el frame
        'tool': bool                     # Si se detectó el tool
    },
    'aruco_configs': [...]               # Configuraciones originales
}
```

**Ejemplo:**
```python
from lib.aruco import detect_arucos_with_config

configs = [
    {"id": 23, "name": "frame", "size_mm": 70.0, "color": (0, 255, 255)},
    {"id": 4, "name": "tool", "size_mm": 50.0, "color": (255, 0, 0)}
]

resultado = detect_arucos_with_config(
    image=mi_imagen,
    aruco_configs=configs,
    dictionary_id=50,
    marker_bits=4
)

if resultado['detection_status']['frame']:
    print("Frame ArUco detectado")
if resultado['detection_status']['tool']:
    print("Tool ArUco detectado")
```

---

## 🔧 **Funciones de Utilidad**

### **`get_available_dictionaries()` - Diccionarios Disponibles**

```python
def get_available_dictionaries() -> Dict[int, str]
```

**Retorna:**
```python
{
    50: "DICT_4X4_50", 100: "DICT_4X4_100", 250: "DICT_4X4_250", 1000: "DICT_4X4_1000",
    51: "DICT_5X5_50", 101: "DICT_5X5_100", 251: "DICT_5X5_250", 1001: "DICT_5X5_1000",
    52: "DICT_6X6_50", 102: "DICT_6X6_100", 252: "DICT_6X6_250", 1002: "DICT_6X6_1000",
    53: "DICT_7X7_50", 103: "DICT_7X7_100", 253: "DICT_7X7_250", 1003: "DICT_7X7_1000"
}
```

### **`get_available_marker_sizes()` - Tamaños de Matriz**

```python
def get_available_marker_sizes() -> Dict[int, str]
```

**Retorna:**
```python
{
    4: "4x4", 5: "5x5", 6: "6x6", 7: "7x7"
}
```

### **`get_dictionary_mapping()` - Mapeo Interno**

```python
def get_dictionary_mapping() -> Dict[Tuple[int, int], int]
```

**Retorna:** Mapeo de `(marker_bits, dictionary_id)` a constantes OpenCV.

---

## 📋 **Combinaciones Válidas**

### **Diccionarios y Bits Soportados:**

| `dictionary_id` | `marker_bits` | Resultado OpenCV |
|-----------------|---------------|------------------|
| 50 | 4 | `DICT_4X4_50` |
| 50 | 5 | `DICT_5X5_50` |
| 50 | 6 | `DICT_6X6_50` |
| 50 | 7 | `DICT_7X7_50` |
| 100 | 4 | `DICT_4X4_100` |
| 100 | 5 | `DICT_5X5_100` |
| 100 | 6 | `DICT_6X6_100` |
| 100 | 7 | `DICT_7X7_100` |
| 250 | 4 | `DICT_4X4_250` |
| 250 | 5 | `DICT_5X5_250` |
| 250 | 6 | `DICT_6X6_250` |
| 250 | 7 | `DICT_7X7_250` |
| 1000 | 4 | `DICT_4X4_1000` |
| 1000 | 5 | `DICT_5X5_1000` |
| 1000 | 6 | `DICT_6X6_1000` |
| 1000 | 7 | `DICT_7X7_1000` |

---

## 🎯 **Casos de Uso**

### **✅ Detección Simple:**
```python
# Buscar un ArUco específico
resultado = detect_aruco_by_id(
    image=imagen,
    target_id=23,
    dictionary_id=50,
    marker_bits=4,
    marker_size_mm=70.0
)
```

### **✅ Exploración:**
```python
# Ver todos los ArUcos en la imagen
resultado = detect_all_arucos(
    image=imagen,
    dictionary_id=50,
    marker_bits=4,
    marker_size_mm=42.0
)
```

### **✅ Sistemas Complejos:**
```python
# Detección con múltiples configuraciones
configs = [
    {"id": 23, "name": "frame", "size_mm": 70.0},
    {"id": 4, "name": "tool", "size_mm": 50.0}
]

resultado = detect_arucos_with_config(
    image=imagen,
    aruco_configs=configs,
    dictionary_id=50,
    marker_bits=4
)
```

---

## 🚨 **Reglas de Uso**

### **✅ Uso Correcto:**
- **Parámetros explícitos** - Siempre especificar `dictionary_id` y `marker_bits`
- **Sin valores por defecto** - Todos los parámetros son obligatorios
- **Validación de combinaciones** - Verificar que la combinación sea válida
- **Manejo de errores** - Verificar que el resultado no sea `None`

### **❌ Uso Incorrecto:**
```python
# ❌ NO hacer - Valores por defecto hardcodeados
resultado = detect_aruco_by_id(imagen, 23)  # Faltan parámetros

# ❌ NO hacer - Combinación inválida
resultado = detect_aruco_by_id(imagen, 23, 999, 8, 70.0)  # dictionary_id=999, marker_bits=8

# ❌ NO hacer - Sin verificación de errores
resultado = detect_aruco_by_id(imagen, 23, 50, 4, 70.0)
centro = resultado['center']  # Error si resultado es None
```

### **✅ Uso Correcto:**
```python
# ✅ CORRECTO - Parámetros explícitos
resultado = detect_aruco_by_id(imagen, 23, 50, 4, 70.0)

# ✅ CORRECTO - Verificación de errores
if resultado:
    centro = resultado['center']
    print(f"ArUco detectado en {centro}")
else:
    print("ArUco no detectado")
```

---

## 🏗️ **Arquitectura Recomendada**

### **Separación de Responsabilidades:**

```
┌─────────────────────────────────────┐
│               aruco.py              │
│        (Librería Genérica)         │
│                                     │
│ ✅ Funciones de detección          │
│ ✅ Parámetros explícitos           │
│ ✅ Sin configuración hardcodeada   │
│ ✅ Sin dependencias específicas    │
└─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────┐
│           aruco_manager.py          │
│      (Gestor Específico)            │
│                                     │
│ ✅ Configuración del proyecto      │
│ ✅ Colores específicos             │
│ ✅ Nombres de marcos               │
│ ✅ Integración con overlay_manager │
└─────────────────────────────────────┘
```

### **Flujo de Trabajo:**

1. **Librería genérica** (`aruco.py`) - Detección pura
2. **Gestor específico** (`aruco_manager.py`) - Configuración del proyecto
3. **Scripts del proyecto** - Usar `aruco_manager.py`

---

## 🔍 **Troubleshooting**

### **Error: "Combinación no soportada"**
```python
# ❌ Problema
resultado = detect_aruco_by_id(imagen, 23, 999, 8, 70.0)

# ✅ Solución
resultado = detect_aruco_by_id(imagen, 23, 50, 4, 70.0)
```

### **Error: "ArUco no detectado"**
```python
# Verificar parámetros
if not resultado:
    print("Verificar:")
    print("- ID del ArUco")
    print("- Diccionario correcto")
    print("- Bits correctos")
    print("- Tamaño en mm")
```

### **Error: "OpenCV no disponible"**
```python
# Verificar instalación
try:
    import cv2
    print("OpenCV disponible")
except ImportError:
    print("Instalar OpenCV: pip install opencv-python")
```

---

## 📝 **Notas Importantes**

1. **Librería genérica** - NO modificar con elementos específicos
2. **Parámetros explícitos** - Sin valores por defecto hardcodeados
3. **Validación** - Verificar combinaciones válidas
4. **Manejo de errores** - Siempre verificar resultados
5. **Separación** - Usar `aruco_manager.py` para funcionalidades específicas

---

## 🎯 **Resumen**

Esta librería proporciona **detección pura de ArUcos** con **parámetros explícitos** y **sin configuración hardcodeada**. Para funcionalidades específicas del proyecto, usar `aruco_manager.py` que actúa como wrapper de esta librería genérica.
