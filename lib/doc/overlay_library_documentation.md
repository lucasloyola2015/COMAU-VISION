# OverlayManager - Librería Genérica de Overlays

## ⚠️ IMPORTANTE: LIBRERÍA GENÉRICA

**Esta librería es GENÉRICA y NO debe ser modificada con:**
- ❌ Elementos hardcodeados específicos del dominio
- ❌ Funciones específicas del proyecto  
- ❌ Marcos de referencia predefinidos
- ❌ Configuraciones específicas del negocio

**Para marcos específicos del dominio, usar `frames_manager.py`**

## 📋 Índice
1. [Introducción](#introducción)
2. [Arquitectura Genérica](#arquitectura-genérica)
3. [Instalación y Configuración](#instalación-y-configuración)
4. [Conceptos Fundamentales](#conceptos-fundamentales)
5. [API de la Librería](#api-de-la-librería)
6. [Soporte para Unidades](#soporte-para-unidades)
7. [Ejemplos Prácticos](#ejemplos-prácticos)
8. [Troubleshooting](#troubleshooting)

## 🎯 Introducción

`OverlayManager` es una **librería genérica y reutilizable** para manejar sistemas de coordenadas múltiples y renderizar overlays gráficos de manera inteligente. Permite definir objetos en diferentes marcos de referencia y transformarlos automáticamente entre sistemas de coordenadas.

### Características Principales
- ✅ **Librería genérica** - Completamente reutilizable
- ✅ **Múltiples sistemas de coordenadas** con transformaciones bidireccionales
- ✅ **Conversión automática** de mm a píxeles usando `px_per_mm`
- ✅ **Soporte para coordenadas en mm y píxeles**
- ✅ **Objetos nombrados** para consultas y transformaciones
- ✅ **Renderizado inteligente** con listas de objetos
- ✅ **Persistencia** de configuraciones de marcos
- ✅ **Solo define marco "world"** por defecto

## 🏗️ Arquitectura Genérica

### **Separación de Responsabilidades:**

```
┌─────────────────────────────────────┐
│               overlay.py             │
│        (Librería Genérica)           │
│                                     │
│ ✅ Solo define marco "world"        │
│ ✅ Funciones genéricas              │
│ ✅ NO marcos específicos            │
│ ✅ NO funciones del dominio         │
└─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────┐
│           frames_manager.py         │
│      (Marcos Específicos)           │
│                                     │
│ ✅ base_frame, tool_frame, etc.     │
│ ✅ Funciones específicas del dominio│
│ ✅ Acceso global a marcos           │
└─────────────────────────────────────┘
```

### **Reglas de Uso:**

1. **NO modificar `overlay.py`** con elementos específicos
2. **Usar `frames_manager.py`** para marcos del dominio
3. **Scripts del proyecto** deben usar `frames_manager.py`
4. **Librería genérica** para cualquier proyecto

## 🚀 Instalación y Configuración

### Dependencias
```python
import numpy as np
import cv2
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union, Any
```

### Inicialización
```python
from lib.overlay import OverlayManager
from frames_manager import init_global_frames

# Crear instancia genérica
overlay_manager = OverlayManager()

# Inicializar marcos específicos del dominio
init_global_frames()  # Define base_frame, tool_frame, junta_frame

# El marco 'world' se crea automáticamente
# offset=(0, 0), rotation=0, px_per_mm=1.0
```

## 🧠 Conceptos Fundamentales

### Marcos de Coordenadas (Frames)
Un marco es un sistema de coordenadas con:
- **Offset**: Posición (x, y) en píxeles
- **Rotación**: Ángulo en radianes
- **px_per_mm**: Relación píxeles por milímetro
- **Parent**: Marco padre (opcional)

```python
# Ejemplo de marco
frame = CoordinateFrame(
    name="Frame_ArUco",
    offset_x=1284.0,      # Posición en píxeles
    offset_y=172.0,       # Posición en píxeles
    rotation=2.939,       # Rotación en radianes
    px_per_mm=2.989,     # Escala: 2.989 px por mm
    parent="Base",        # Marco padre
    is_temporary=False    # Persistente
)
```

### Objetos de Dibujo
Cada objeto tiene:
- **Tipo**: Línea, círculo, elipse, polígono, texto
- **Coordenadas**: Definidas en su marco de referencia
- **Propiedades**: Color, grosor, etc.
- **Nombre único**: Para consultas y transformaciones

## 🔧 API de la Librería

### 1. Gestión de Marcos

#### `define_frame(name, offset, rotation, px_per_mm, parent)`
```python
# Crear marco de referencia
overlay_manager.define_frame(
    name="Frame_ArUco",
    offset=(1284, 172),           # Posición en píxeles
    rotation=2.939,              # Rotación en radianes
    px_per_mm=2.989,            # Escala
    parent="Base"               # Marco padre
)

# Crear marco temporal para calibración
overlay_manager.define_frame(
    name="temp_frame",
    offset=(500, 300),
    rotation=0.5,
    px_per_mm=3.2,
    parent="Base"
)
```

#### `update_frame(name, offset, rotation, px_per_mm)`
```python
# Actualizar marco existente
overlay_manager.update_frame(
    name="Frame_ArUco",
    offset=(1300, 180),         # Nueva posición
    rotation=3.0,              # Nueva rotación
    px_per_mm=3.1              # Nueva escala
)
```

### 2. Soporte para Unidades

#### **Parámetro `units` en todas las funciones `add_*`**

Todas las funciones de agregar objetos soportan el parámetro `units`:

```python
# Coordenadas en milímetros (por defecto)
overlay_manager.add_line(
    frame="base_frame",
    start=(10, 20),              # mm
    end=(30, 20),                # mm
    name="linea_mm",
    units="mm"                   # Por defecto
)

# Coordenadas en píxeles (cuando sea necesario)
overlay_manager.add_line(
    frame="base_frame", 
    start=(29.9, 59.8),          # px
    end=(89.7, 59.8),            # px
    name="linea_px",
    units="px"                   # Conversión automática
)
```

#### **Conversión Automática:**
- `units="mm"` (por defecto): Coordenadas en milímetros
- `units="px"`: Coordenadas en píxeles → se convierten a mm automáticamente

### 3. Objetos de Dibujo

#### `add_line(frame, start, end, name, color, thickness, units)`
```python
# Línea horizontal en milímetros
overlay_manager.add_line(
    frame="Frame_ArUco",        # Marco de referencia
    start=(10, 20),            # Punto inicio (mm)
    end=(30, 20),              # Punto fin (mm)
    name="linea_horizontal",    # Nombre único
    color=(255, 0, 0),         # Rojo (BGR)
    thickness=2,               # Grosor
    units="mm"                 # Milímetros (por defecto)
)

# Línea en píxeles
overlay_manager.add_line(
    frame="Frame_ArUco",
    start=(29.9, 59.8),        # Píxeles
    end=(89.7, 59.8),          # Píxeles
    name="linea_px",
    color=(0, 255, 0),
    thickness=3,
    units="px"                 # Píxeles → conversión automática
)

# Línea con coordenadas en píxeles
overlay_manager.add_line(
    frame="Base",               # Marco Base (píxeles)
    start=(100, 200),          # Punto inicio (px)
    end=(300, 200),            # Punto fin (px)
    name="linea_base",
    color=(0, 255, 0),         # Verde
    thickness=3
)
```

#### `add_circle(frame, center, radius, name, color, thickness, filled)`
```python
# Círculo en marco con escala
overlay_manager.add_circle(
    frame="Frame_ArUco",
    center=(25, 25),           # Centro (mm)
    radius=5.0,                 # Radio (mm)
    name="circulo_centro",
    color=(0, 0, 255),         # Azul
    thickness=2,
    filled=False                # Solo contorno
)

# Círculo relleno
overlay_manager.add_circle(
    frame="Base",
    center=(500, 300),         # Centro (px)
    radius=20,                  # Radio (px)
    name="punto_importante",
    color=(255, 255, 0),       # Cyan
    thickness=-1,              # Relleno completo
    filled=True
)
```

#### `add_ellipse(frame, center, axes, angle, name, color, thickness)`
```python
# Elipse rotada
overlay_manager.add_ellipse(
    frame="Frame_ArUco",
    center=(15, 15),            # Centro (mm)
    axes=(10, 5),              # Ejes mayor y menor (mm)
    angle=45,                  # Rotación en grados
    name="elipse_rotada",
    color=(255, 0, 255),       # Magenta
    thickness=2
)
```

#### `add_polygon(frame, points, name, color, thickness)`
```python
# Polígono (triángulo)
overlay_manager.add_polygon(
    frame="Frame_ArUco",
    points=[(0, 0), (10, 0), (5, 10)],  # Puntos (mm)
    name="triangulo",
    color=(0, 255, 255),       # Amarillo
    thickness=2
)

# Polígono complejo
overlay_manager.add_polygon(
    frame="Base",
    points=[(100, 100), (200, 100), (200, 200), (100, 200)],  # Rectángulo (px)
    name="rectangulo_base",
    color=(128, 128, 128),     # Gris
    thickness=1
)
```

#### `add_text(frame, position, text, name, color, font_scale, thickness)`
```python
# Texto en posición específica
overlay_manager.add_text(
    frame="Frame_ArUco",
    position=(10, 30),         # Posición (mm)
    text="ArUco Frame",        # Texto
    name="etiqueta_frame",
    color=(255, 255, 255),     # Blanco
    font_scale=0.5,            # Escala de fuente
    thickness=1
)
```

### 3. Consultas y Transformaciones

#### `get_object(target_frame, name)`
```python
# Obtener objeto transformado a otro marco
cruz_en_tool = overlay_manager.get_object(
    target_frame="Tool_ArUco",  # Marco destino
    name="center_cross_h"       # Nombre del objeto
)

# Resultado:
# {
#     'name': 'center_cross_h',
#     'type': 'line',
#     'coordinates': {
#         'start': (x, y),      # Coordenadas transformadas
#         'end': (x, y)
#     },
#     'properties': {...}
# }

# Usar coordenadas transformadas
coords = cruz_en_tool['coordinates']['start']
print(f"Cruz en Tool: {coords}")
```

#### `list_objects()`
```python
# Listar todos los objetos
objetos = overlay_manager.list_objects()
print(f"Objetos disponibles: {objetos}")
# Resultado: ['linea_horizontal', 'circulo_centro', 'triangulo', ...]
```

### 4. Renderizado

#### `render(background_image, renderlist, show_frames, view_time)`
```python
# Renderizar todos los objetos
result_image, view_time = overlay_manager.render(
    background_image=imagen_fondo,
    renderlist=None,            # Todos los objetos
    show_frames=None,          # Todos los marcos
    view_time=5000             # 5 segundos
)

# Renderizar lista específica
result_image, view_time = overlay_manager.render(
    background_image=imagen_fondo,
    renderlist=["linea_horizontal", "circulo_centro"],
    view_time=3000
)

# Renderizar con lista predefinida
overlay_manager.create_renderlist("mi_lista", ["objeto1", "objeto2"])
result_image, view_time = overlay_manager.render(
    background_image=imagen_fondo,
    renderlist="mi_lista"
)
```

### 5. Gestión de Listas de Renderizado

#### `create_renderlist(name, objects)`
```python
# Crear lista de objetos para renderizar
overlay_manager.create_renderlist(
    name="arucos_overlay",
    objects=["aruco_contour_23", "aruco_x_axis_23", "center_cross_h"]
)
```

#### `get_renderlist(name)`
```python
# Obtener lista de renderizado
lista = overlay_manager.get_renderlist("arucos_overlay")
print(f"Objetos en lista: {lista}")
```

### 6. Persistencia

#### `save_persistent_config(filename)`
```python
# Guardar marcos persistentes
overlay_manager.save_persistent_config("frames_config.json")
```

#### `load_persistent_config(filename)`
```python
# Cargar marcos persistentes
overlay_manager.load_persistent_config("frames_config.json")
```

## 🎯 Uso Correcto de la Librería Genérica

### **✅ Uso Correcto:**
```python
# 1. Importar librería genérica
from lib.overlay import OverlayManager
from frames_manager import init_global_frames, get_global_overlay_manager

# 2. Inicializar marcos específicos del dominio
init_global_frames()

# 3. Obtener instancia global
overlay = get_global_overlay_manager()

# 4. Usar funciones genéricas
overlay.add_line("base_frame", start=(10, 20), end=(30, 20), name="linea")
```

### **❌ Uso Incorrecto:**
```python
# NO modificar overlay.py con:
# - Marcos específicos del dominio
# - Funciones específicas del proyecto
# - Configuraciones hardcodeadas
# - Elementos específicos del negocio
```

### **🏗️ Arquitectura Recomendada:**
```
overlay.py     → Librería genérica (NO modificar)
frames_manager.py      → Marcos específicos del dominio
mi_script.py          → Usar frames_manager.py
```

## 🎯 Ejemplos Prácticos

### Ejemplo 1: Sistema de ArUcos
```python
# 1. Definir marcos de ArUcos
overlay_manager.define_frame(
    name="Frame_ArUco",
    offset=(1284, 172),
    rotation=2.939,
    px_per_mm=2.989,
    parent="Base"
)

overlay_manager.define_frame(
    name="Tool_ArUco", 
    offset=(944, 836),
    rotation=-0.025,
    px_per_mm=3.286,
    parent="Base"
)

# 2. Crear cruz del troquel en Frame ArUco
overlay_manager.add_line(
    "Frame_ArUco",
    start=(20, 40),           # 20mm desde centro
    end=(50, 40),             # 30mm de largo
    name="cruz_horizontal",
    color=(255, 255, 0),      # Cyan
    thickness=4
)

overlay_manager.add_line(
    "Frame_ArUco",
    start=(35, 25),           # 15mm arriba
    end=(35, 55),             # 30mm de alto
    name="cruz_vertical", 
    color=(255, 255, 0),      # Cyan
    thickness=4
)

# 3. Crear círculo central
overlay_manager.add_circle(
    "Frame_ArUco",
    center=(35, 40),          # Centro de la cruz
    radius=3.0,               # 3mm de radio
    name="centro_cruz",
    color=(255, 255, 0),      # Cyan
    thickness=2
)

# 4. Crear lista de renderizado
overlay_manager.create_renderlist(
    "aruco_overlay",
    ["cruz_horizontal", "cruz_vertical", "centro_cruz"]
)

# 5. Renderizar
result_image, view_time = overlay_manager.render(
    background_image=imagen_camara,
    renderlist="aruco_overlay",
    view_time=3000
)
```

### Ejemplo 2: Prueba de Transformaciones
```python
# 1. Crear objeto en un marco
overlay_manager.add_circle(
    "Frame_ArUco",
    center=(35, 35),          # Centro (mm)
    radius=5.0,               # Radio (mm)
    name="punto_prueba",
    color=(255, 0, 0),        # Rojo
    thickness=2
)

# 2. Leer en diferentes marcos
punto_en_tool = overlay_manager.get_object("Tool_ArUco", "punto_prueba")
punto_en_base = overlay_manager.get_object("Base", "punto_prueba")

print(f"Punto en Tool: {punto_en_tool['coordinates']['center']}")
print(f"Punto en Base: {punto_en_base['coordinates']['center']}")

# 3. Crear segmentos de prueba
overlay_manager.add_line(
    "Frame_ArUco",
    start=(0, 0),             # Centro del Frame
    end=(35, 35),             # Al punto
    name="segmento_frame",
    color=(0, 255, 0),        # Verde
    thickness=3
)

overlay_manager.add_line(
    "Tool_ArUco",
    start=(0, 0),             # Centro del Tool
    end=punto_en_tool['coordinates']['center'],  # Punto transformado
    name="segmento_tool",
    color=(255, 0, 0),        # Rojo
    thickness=3
)

overlay_manager.add_line(
    "Base",
    start=(0, 0),             # Esquina de imagen
    end=punto_en_base['coordinates']['center'],  # Punto transformado
    name="segmento_base",
    color=(0, 0, 255),        # Azul
    thickness=3
)
```

## 🔬 Casos de Uso Avanzados

### Caso 1: Calibración con ArUcos
```python
# 1. Detectar ArUcos y crear marcos temporales
arucos_detectados = detect_arucos(imagen)
for aruco in arucos_detectados:
    overlay_manager.define_frame(
        name=f"aruco_temp_{aruco.id}",
        offset=aruco.center,
        rotation=aruco.angle,
        px_per_mm=aruco.px_per_mm,
        parent="Base",
        is_temporary=True
    )

# 2. Crear objetos de calibración
overlay_manager.add_circle(
    "aruco_temp_23",
    center=(0, 0),            # Centro del ArUco
    radius=10.0,              # 10mm de radio
    name="calibracion_frame",
    color=(0, 255, 0),        # Verde
    thickness=2
)

# 3. Si calibración es exitosa, hacer permanente
if calibracion_exitosa:
    overlay_manager.update_frame(
        "aruco_temp_23",
        is_temporary=False
    )
    overlay_manager.save_persistent_config("calibracion.json")
```

### Caso 2: Sistema de Medición
```python
# 1. Crear líneas de medición
overlay_manager.add_line(
    "Frame_ArUco",
    start=(0, 0),             # Origen
    end=(100, 0),             # 100mm horizontal
    name="medida_horizontal",
    color=(255, 255, 0),      # Amarillo
    thickness=2
)

# 2. Crear etiquetas de medición
overlay_manager.add_text(
    "Frame_ArUco",
    position=(50, -5),        # Centro de la línea
    text="100mm",
    name="etiqueta_medida",
    color=(255, 255, 255),    # Blanco
    font_scale=0.5
)

# 3. Crear cuadrícula de medición
for i in range(0, 101, 10):  # Cada 10mm
    overlay_manager.add_line(
        "Frame_ArUco",
        start=(i, -2),        # Marca pequeña
        end=(i, 2),
        name=f"marca_{i}",
        color=(200, 200, 200), # Gris claro
        thickness=1
    )
```

### Caso 3: Análisis de Errores
```python
# 1. Crear círculos de tolerancia
overlay_manager.add_circle(
    "Frame_ArUco",
    center=(35, 40),          # Posición esperada
    radius=2.0,               # 2mm de tolerancia
    name="tolerancia_positiva",
    color=(0, 255, 0),      # Verde
    thickness=1
)

overlay_manager.add_circle(
    "Frame_ArUco", 
    center=(35, 40),
    radius=1.0,               # 1mm de tolerancia
    name="tolerancia_negativa",
    color=(0, 0, 255),        # Azul
    thickness=1
)

# 2. Crear vector de error
overlay_manager.add_line(
    "Frame_ArUco",
    start=(35, 40),           # Posición esperada
    end=(37, 42),             # Posición real
    name="vector_error",
    color=(255, 0, 0),        # Rojo
    thickness=3
)

# 3. Crear etiqueta de error
error_mm = calcular_error(35, 40, 37, 42)
overlay_manager.add_text(
    "Frame_ArUco",
    position=(36, 38),        # Centro del vector
    text=f"Error: {error_mm:.2f}mm",
    name="etiqueta_error",
    color=(255, 0, 0),        # Rojo
    font_scale=0.4
)
```

## 🐛 Troubleshooting

### ⚠️ Problemas con Librería Genérica

#### **Error: "No se puede modificar overlay.py"**
```python
# ❌ INCORRECTO - NO hacer esto
# Modificar overlay.py con marcos específicos

# ✅ CORRECTO - Usar frames_manager.py
from frames_manager import init_global_frames
init_global_frames()
```

#### **Error: "Marco no encontrado"**
```python
# ❌ INCORRECTO - overlay.py solo tiene "world"
overlay = OverlayManager()
overlay.add_line("base_frame", ...)  # Error: base_frame no existe

# ✅ CORRECTO - Inicializar marcos específicos
from frames_manager import init_global_frames, get_global_overlay_manager
init_global_frames()
overlay = get_global_overlay_manager()
overlay.add_line("base_frame", ...)  # OK: base_frame existe
```

#### **Error: "Unidades incorrectas"**
```python
# ❌ INCORRECTO - Coordenadas en píxeles sin especificar units
overlay.add_line("base_frame", start=(29.9, 59.8), end=(89.7, 59.8), name="linea")

# ✅ CORRECTO - Especificar units="px"
overlay.add_line("base_frame", start=(29.9, 59.8), end=(89.7, 59.8), name="linea", units="px")
```

### Problema 1: Objetos no aparecen
**Síntomas**: Los objetos se crean pero no se ven en el renderizado
**Causas**:
- Coordenadas fuera de la imagen
- Marco incorrecto
- Lista de renderizado vacía

**Solución**:
```python
# Verificar coordenadas
coords = overlay_manager.get_object("Base", "mi_objeto")
print(f"Coordenadas en Base: {coords}")

# Verificar lista de renderizado
lista = overlay_manager.get_renderlist("mi_lista")
print(f"Objetos en lista: {lista}")

# Renderizar con debug
result_image, view_time = overlay_manager.render(
    background_image=imagen,
    renderlist=["mi_objeto"],  # Lista explícita
    view_time=5000
)
```

### Problema 2: Escalas incorrectas
**Síntomas**: Los objetos aparecen muy grandes o muy pequeños
**Causas**:
- `px_per_mm` incorrecto
- Mezcla de unidades (mm vs px)

**Solución**:
```python
# Verificar px_per_mm del marco
frame = overlay_manager.frames["mi_marco"]
print(f"px_per_mm: {frame.px_per_mm}")

# Recalcular px_per_mm
nuevo_px_per_mm = calcular_px_per_mm(aruco_size_mm, aruco_size_px)
overlay_manager.update_frame(
    "mi_marco",
    px_per_mm=nuevo_px_per_mm
)
```

### Problema 3: Transformaciones incorrectas
**Síntomas**: Los objetos aparecen en posiciones incorrectas
**Causas**:
- Offset o rotación incorrectos
- Marco padre incorrecto

**Solución**:
```python
# Verificar transformación paso a paso
punto_original = (35, 35)
punto_transformado = overlay_manager.get_object("Base", "mi_objeto")
print(f"Original: {punto_original}")
print(f"Transformado: {punto_transformado}")

# Verificar marco
frame = overlay_manager.frames["mi_marco"]
print(f"Offset: {frame.offset_x}, {frame.offset_y}")
print(f"Rotación: {frame.rotation}")
print(f"Parent: {frame.parent}")
```

### Problema 4: Rendimiento lento
**Síntomas**: El renderizado es lento
**Causas**:
- Demasiados objetos
- Imagen muy grande
- Transformaciones complejas

**Solución**:
```python
# Usar listas de renderizado específicas
overlay_manager.create_renderlist(
    "objetos_esenciales",
    ["objeto1", "objeto2"]  # Solo objetos necesarios
)

# Renderizar con lista específica
result_image, view_time = overlay_manager.render(
    background_image=imagen,
    renderlist="objetos_esenciales"
)
```

## 📚 Referencias

### Estructura de Datos
```python
@dataclass
class CoordinateFrame:
    name: str
    offset_x: float
    offset_y: float
    rotation: float
    px_per_mm: float
    parent: str = "Base"
    is_temporary: bool = False

@dataclass
class DrawingObject:
    name: str
    type: ObjectType
    coordinates: Dict[str, Any]
    properties: Dict[str, Any]
    original_frame: str
```

### Constantes de Color (BGR)
```python
COLORES = {
    'rojo': (0, 0, 255),
    'verde': (0, 255, 0),
    'azul': (255, 0, 0),
    'amarillo': (0, 255, 255),
    'cyan': (255, 255, 0),
    'magenta': (255, 0, 255),
    'blanco': (255, 255, 255),
    'negro': (0, 0, 0)
}
```

### Tipos de Objetos
```python
class ObjectType(Enum):
    LINE = "line"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    POLYGON = "polygon"
    TEXT = "text"
    SEGMENT = "segment"
```

---

## 🔄 Actualización de Marcos

### `update_frame(name, offset, rotation, px_per_mm)`

Actualizar un marco de coordenadas existente con nuevos valores.

```python
# Actualizar solo la posición
overlay_manager.update_frame(
    name="base_frame",
    offset=(100, 200)  # Nueva posición
)

# Actualizar solo la rotación
overlay_manager.update_frame(
    name="base_frame", 
    rotation=1.57  # 90 grados en radianes
)

# Actualizar solo la escala
overlay_manager.update_frame(
    name="base_frame",
    px_per_mm=2.5  # Nueva relación píxeles/mm
)

# Actualizar múltiples parámetros
overlay_manager.update_frame(
    name="base_frame",
    offset=(150, 250),    # Nueva posición
    rotation=0.785,       # 45 grados
    px_per_mm=3.0         # Nueva escala
)
```

**Parámetros:**
- `name`: Nombre del marco a actualizar
- `offset`: Nuevo desplazamiento (x, y) - opcional
- `rotation`: Nueva rotación en radianes - opcional  
- `px_per_mm`: Nueva relación píxeles por milímetro - opcional

**Uso típico:**
```python
# Actualizar marco con datos de ArUco detectado
overlay_manager.update_frame(
    name="base_frame",
    offset=aruco_position,    # Posición detectada
    rotation=aruco_angle,     # Ángulo detectado
    px_per_mm=aruco_scale     # Escala detectada
)
```

---

## 📋 Resumen - Librería Genérica

### **✅ Características Principales:**
- **Librería genérica** - Completamente reutilizable
- **Solo define marco "world"** por defecto
- **Soporte para unidades** mm y px
- **NO modificable** con elementos específicos del dominio

### **🏗️ Arquitectura:**
```
overlay.py     → Librería genérica (NO modificar)
frames_manager.py      → Marcos específicos del dominio
mi_script.py          → Usar frames_manager.py
```

### **🚀 Uso Recomendado:**
```python
from frames_manager import init_global_frames, get_global_overlay_manager

# Inicializar marcos específicos
init_global_frames()

# Obtener instancia global
overlay = get_global_overlay_manager()

# Usar funciones genéricas
overlay.add_line("base_frame", start=(10, 20), end=(30, 20), name="linea")
```

### **⚠️ Reglas Importantes:**
1. **NO modificar `overlay.py`** con elementos específicos
2. **Usar `frames_manager.py`** para marcos del dominio
3. **Especificar `units="px"`** cuando las coordenadas estén en píxeles
4. **Mantener la librería genérica** para reutilización

---

**OverlayManager** - Librería genérica de overlays con transformaciones de coordenadas múltiples
