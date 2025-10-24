# 🎯 DISEÑO PIPELINE DE ANÁLISIS - COMAU-VISION

## 📋 Objetivo
Diseñar una rutina **simple, lineal y clara** para analizar juntas con el botón "Analizar" del dashboard.

---

## ✅ DECISIONES TOMADAS

- ✅ **Opción 3:** Pipeline modular con funciones independientes
- ✅ **Archivos nuevos:** pipeline_analisis.py, validaciones_geometricas.py, visualizador.py
- ✅ **overlay_manager.py:** Se mantiene (no se elimina), pero creamos algo nuevo
- ✅ **Estrategia:** NO eliminar nada hasta que el nuevo pipeline funcione
- ✅ **Modularización:** Funciones simples, una tarea específica cada una

---

## 📁 ESTRUCTURA DE ARCHIVOS NUEVOS

```
COMAU-VISION/
├── pipeline_analisis.py         # Orquestador principal
├── validaciones_geometricas.py  # Validaciones de geometría
├── visualizador.py              # Dibuja overlays en imágenes
│
├── aruco_detector.py            # Ya existe - detecta ArUco
├── yolo_detector.py             # Ya existe - detecta con YOLO
├── camera_manager.py            # Ya existe - maneja cámara
├── overlay_manager.py           # Ya existe - NO SE TOCA (compatibilidad)
└── illinois-server.py           # Ya existe - servidor Flask
```

---

## 🎯 PUNTO DE ENTRADA - Botón "Analizar"

### **illinois-server.py** → Endpoint `/api/analyze`

**ANTES:**
```python
@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    analyzed_frame = cam.analyze_frame()  # ← Usa overlay_manager (viejo)
    analysis_data = overlay_manager.get_analysis_data()
    return jsonify({'ok': True, 'data': analysis_data})
```

**DESPUÉS:**
```python
@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    # Redirigir a nuevo pipeline
    import pipeline_analisis
    
    frame = cam.capturar_frame_limpio()  # Frame RGB sin procesar
    exito, imagen, datos = pipeline_analisis.analizar_con_reintentos(frame, max_intentos=3)
    
    if not exito:
        return jsonify({'ok': False, 'error': 'No se pudo obtener análisis válido'})
    
    # Guardar imagen para mostrar
    global _last_analysis
    _last_analysis = imagen
    
    return jsonify({'ok': True, 'data': datos})
```

---

## 🏗️ ARQUITECTURA DEL PIPELINE

### **Filosofía de diseño:**
- Cada función hace **UNA SOLA COSA**
- Retorna datos simples (dict, tupla, bool)
- Sin estado global (cachés, flags, registros)
- Fácil de probar y debuggear

### **🔍 Escalera de Detección - 3 Etapas (YOLO Detection → YOLO Holes → OpenCV)**

```
📸 FRAME COMPLETO (1920x1080)
    ↓
┌─────────────────────────────────────────────────────────────┐
│ ETAPA 1: YOLO Detection Model (detect_gasket)              │
│ ─────────────────────────────────────────────────────────── │
│                                                              │
│ INPUT:  Frame completo RGB                                  │
│ MODELO: models/detection_model.pt                           │
│ OUTPUT: bbox_junta = (x1, y1, x2, y2)                      │
│                                                              │
│ Ejemplo: (500, 300, 1400, 800) ← UN solo bbox             │
└─────────────────────────────────────────────────────────────┘
    ↓
🔲 CROP DE JUNTA + PADDING 10%
    ↓
┌─────────────────────────────────────────────────────────────┐
│ ETAPA 2: YOLO Holes Model (detect_holes_bboxes)           │
│ ─────────────────────────────────────────────────────────── │
│                                                              │
│ INPUT:  Crop de junta (ej: 950x530)                        │
│ MODELO: models/holes_model.pt                               │
│ OUTPUT: Lista de bboxes de agujeros                         │
│                                                              │
│ Ejemplo:                                                     │
│   [                                                          │
│     {'bbox': (10, 20, 50, 60)},    ← Agujero 1            │
│     {'bbox': (100, 25, 140, 65)},  ← Agujero 2            │
│     {'bbox': (200, 22, 240, 62)},  ← Agujero 3            │
│     {'bbox': (300, 20, 340, 60)}   ← Agujero 4            │
│   ]                                                          │
└─────────────────────────────────────────────────────────────┘
    ↓
🔲 CROP DE CADA AGUJERO INDIVIDUAL (40x40 cada uno)
    ↓
┌─────────────────────────────────────────────────────────────┐
│ ETAPA 3: OpenCV (calcular_centro_agujero)                  │
│ ─────────────────────────────────────────────────────────── │
│                                                              │
│ INPUT:  Crop de UN agujero (ej: 40x40)                     │
│ PROCESO:                                                     │
│   1. Detectar azul predominante → Máscara binaria          │
│   2. Encontrar contornos → Contorno del agujero            │
│   3. Ajustar elipse → Elipse perfecta                      │
│   4. Calcular centro → Centro PRECISO                      │
│                                                              │
│ OUTPUT: {                                                    │
│   'center': (20, 20),    ← Coordenadas locales (en crop)   │
│   'contour': [...],                                         │
│   'ellipse': (center, axes, angle)                          │
│ }                                                            │
│                                                              │
│ ⚠️  SE EJECUTA N VECES (una por cada agujero detectado)    │
└─────────────────────────────────────────────────────────────┘
    ↓
📍 AJUSTE DE COORDENADAS
    ↓
┌─────────────────────────────────────────────────────────────┐
│ center_global = center_local + offset_agujero + offset_junta│
│                                                              │
│ Ejemplo:                                                     │
│   center_local   = (20, 20)     ← En crop 40x40            │
│   offset_agujero = (10, 20)     ← Bbox del agujero en crop │
│   offset_junta   = (450, 270)   ← Bbox de junta en frame   │
│   ────────────────────────────────────────────────────────  │
│   center_global  = (480, 310)   ← En frame 1920x1080       │
└─────────────────────────────────────────────────────────────┘
    ↓
✅ LISTA DE AGUJEROS CON COORDENADAS GLOBALES
```

**Resumen:**
- **YOLO Detection:** Localiza la junta completa (1 bbox)
- **YOLO Holes:** Localiza N agujeros dentro de la junta (N bboxes)
- **OpenCV:** Refina cada agujero individualmente para obtener centro preciso (N veces)

---

### **⚡ Validaciones Tempranas (Early Returns) + Actualización Progresiva**

```
Pipeline con validaciones tempranas para NO DESPERDICIAR RECURSOS:

┌─────────────────────────────────────────────────────────────┐
│ PASO 1: Detectar ArUco                                      │
│ ✓ Detectado → Continuar                                     │
│ ✗ No detectado → REINTENTO INMEDIATO                        │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ PASO 2: Detectar Junta                                      │
│ ✓ Detectada → Continuar                                     │
│ ✗ No detectada → REINTENTO INMEDIATO                        │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ PASO 3: YOLO Holes detecta N agujeros                       │
└─────────────────────────────────────────────────────────────┘
    ↓
╔═════════════════════════════════════════════════════════════╗
║ ⚡ VALIDACIÓN TEMPRANA 1: CANTIDAD DE PISTONES              ║
║ ───────────────────────────────────────────────────────────  ║
║ ¿Cantidad detectada == Cantidad esperada?                   ║
║                                                              ║
║ ✗ NO → REINTENTO INMEDIATO                                  ║
║        (No procesar OpenCV, es pérdida de recursos)         ║
║        ├─ Enviar datos parciales al frontend                ║
║        └─ Actualizar tabla: Pistones = N/M ❌                ║
║                                                              ║
║ ✓ SÍ → Continuar con OpenCV                                 ║
╚═════════════════════════════════════════════════════════════╝
    ↓
┌─────────────────────────────────────────────────────────────┐
│ PASO 4: OpenCV refina cada agujero (N veces)                │
│ → Detecta centros precisos                                  │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ PASO 5: Calcular métricas (distancia entre extremos)        │
└─────────────────────────────────────────────────────────────┘
    ↓
╔═════════════════════════════════════════════════════════════╗
║ ⚡ VALIDACIÓN TEMPRANA 2: DISTANCIA EXTREMOS                ║
║ ───────────────────────────────────────────────────────────  ║
║ ¿Distancia dentro de tolerancia (ej: 98%)?                  ║
║                                                              ║
║ ✗ NO → REINTENTO INMEDIATO                                  ║
║        (No hacer validaciones geométricas, no dibujar)       ║
║        ├─ Enviar datos parciales al frontend                ║
║        └─ Actualizar tabla: Distancia = 95% ❌               ║
║                                                              ║
║ ✓ SÍ → Continuar con validaciones geométricas               ║
╚═════════════════════════════════════════════════════════════╝
    ↓
┌─────────────────────────────────────────────────────────────┐
│ PASO 6: Validaciones geométricas                            │
│ ├─ Centros múltiples                                        │
│ ├─ Colinealidad                                             │
│ └─ Espaciado uniforme                                       │
│                                                              │
│ ✗ Alguna falla → Continuar (no early return)                │
│                   ├─ Enviar datos parciales                 │
│                   ├─ Actualizar tabla con resultados        │
│                   └─ Marcar como NO exitoso                 │
│                                                              │
│ ✓ Todas pasan → Marcar como EXITOSO                         │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ PASO 7: Calcular muescas                                    │
│                                                              │
│ ✓ Exitoso → Calcular muescas (para dibujar)                │
│ ✗ Fallo → Omitir muescas (muescas = [])                    │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ PASO 8: Dibujar overlay SIEMPRE (para DEBUG VISUAL)         │
│                                                              │
│ ⚠️  Se dibuja INCLUSO si hubo fallas (para ver qué salió mal)│
│                                                              │
│ Si exitoso:                                                  │
│   → Dibuja ArUco, junta, agujeros, línea, MUESCAS           │
│                                                              │
│ Si falló:                                                    │
│   → Dibuja ArUco, junta, agujeros, línea (SIN muescas)     │
│                                                              │
│ → Imagen final con overlays (con o sin muescas)            │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ PASO 9: Retornar resultado                                  │
│                                                              │
│ ✓ Exitoso → return (True, imagen, datos)                   │
│              └─ NO reintenta                                 │
│                                                              │
│ ✗ Fallo → return (False, imagen, datos)                    │
│            └─ Reintenta (pero con imagen para debug)        │
└─────────────────────────────────────────────────────────────┘
    ↓
Si exitoso:
  ✅ ANÁLISIS EXITOSO
     ├─ Enviar datos completos al frontend
     ├─ Actualizar tabla completa (todo en verde ✓)
     ├─ Mostrar imagen procesada CON muescas
     └─ Enviar mensaje ANALYSIS_SUCCESS

Si falló (después de 3 intentos):
  ❌ ANÁLISIS FALLIDO
     ├─ Enviar últimos datos al frontend
     ├─ Tabla muestra errores específicos ✗
     ├─ Mostrar última imagen SIN muescas (DEBUG VISUAL)
     └─ Enviar mensaje ANALYSIS_FAILED
```

**Ventajas de las validaciones tempranas:**
1. ✅ **Ahorra recursos**: No ejecuta OpenCV si la cantidad es incorrecta
2. ✅ **Más rápido**: Reintenta inmediatamente sin procesar más
3. ✅ **Feedback inmediato**: Frontend ve resultados progresivamente
4. ✅ **Mejor UX**: Usuario ve qué está fallando en cada intento

---

### **📊 Tabla de Validaciones: ¿Cuáles hacen Early Return?**

| Validación | Early Return | ¿Dibuja Overlay? | Razón |
|-----------|--------------|------------------|-------|
| **ArUco no detectado** | ✅ SÍ | ❌ NO | Sin calibración no se puede procesar nada |
| **Junta no detectada** | ✅ SÍ | ❌ NO | Sin junta no hay área para detectar agujeros |
| **Cantidad pistones incorrecta** | ✅ SÍ | ❌ NO | Ahorra recursos (no ejecuta OpenCV) |
| **Distancia fuera de tolerancia** | ✅ SÍ | ❌ NO | Ahorra recursos (no ejecuta validaciones geométricas) |
| **Validaciones geométricas** | ❌ NO | ✅ SÍ | Dibuja overlay para DEBUG VISUAL |

**Explicación:**
```
Validaciones TEMPRANAS (Early Return):
  → Fallan RÁPIDO sin procesar más
  → NO generan imagen (return False, None, datos_parciales)
  → Reintentan inmediatamente

Validaciones FINALES (sin Early Return):
  → Ejecutan TODO el pipeline
  → Generan imagen CON overlay (sin muescas)
  → Imagen ayuda a debuggear qué salió mal
  → Reintentan pero con imagen de debug
```

**Callback de progreso:**
```python
# Se llama después de cada validación crítica
callback_progreso(datos_parciales)

# Frontend escucha y actualiza tabla:
window.addEventListener('message', (event) => {
    if (event.data.type === 'ANALYSIS_READY') {
        actualizarTabla(event.data.data);  // ← Actualiza en cada paso
    }
});
```

### **🎯 Separación de responsabilidades: Análisis vs Visualización**

**Principio fundamental:**
```
ANÁLISIS (pipeline_analisis.py):
  - SIEMPRE ejecuta TODO el análisis completo
  - SIEMPRE llena el diccionario datos_visualizacion con TODOS los datos
  - NO consulta checkboxes de configuración
  - NO decide qué dibujar

VISUALIZACIÓN (visualizador.py):
  - Recibe el diccionario COMPLETO con todos los datos
  - Consulta los checkboxes de las páginas de configuración
  - Decide QUÉ dibujar según configuración
  - Dibuja solo los elementos habilitados
```

**Ejemplo:**
```python
# pipeline_analisis.py
datos_aruco = detectar_aruco(frame)  # ← Siempre detecta
datos_visualizacion['aruco'] = datos_aruco  # ← Siempre agrega

# visualizador.py
show_aruco = config.get('show_reference', False)  # ← Lee checkbox
if show_aruco and datos_visualizacion.get('aruco'):  # ← Decide si dibuja
    resultado = _dibujar_aruco(resultado, datos_aruco)
```

**Checkboxes que controlan la visualización:**
- `aruco.show_reference` → Dibuja ejes y contorno del ArUco
- `vision.show_bbox` → Dibuja bounding box de la junta
- `vision.show_contours` → Dibuja contornos de agujeros
- `vision.show_ellipses` → Dibuja elipses ajustadas de agujeros
- `vision.show_notches` → Dibuja muescas (círculos rojos)

---

## 📦 ARCHIVO 1: `pipeline_analisis.py`

### **Función principal de reintentos**
```python
def analizar_con_reintentos(frame, max_intentos=3):
    """
    Intenta analizar un frame hasta obtener un resultado válido.
    
    Args:
        frame: Imagen RGB de OpenCV
        max_intentos: Número máximo de intentos
    
    Returns:
        (exito: bool, imagen_procesada: bytes, datos: dict)
    """
    
    ultima_imagen = None
    ultimos_datos = None
    
    for intento in range(1, max_intentos + 1):
        exito, imagen, datos = analizar_frame_completo(frame)
        
        # Guardar última imagen y datos (para mostrar si todo falla)
        if imagen:
            ultima_imagen = imagen
            ultimos_datos = datos
        
        if exito:
            print(f"[pipeline] ✓ Análisis exitoso en intento {intento}")
            return True, imagen, datos
        
        print(f"[pipeline] ✗ Intento {intento} falló, reintentando...")
    
    # Todos los intentos fallaron
    # PERO devolvemos la última imagen para DEBUG VISUAL
    print(f"[pipeline] ❌ Análisis falló después de {max_intentos} intentos")
    print(f"[pipeline] → Devolviendo última imagen para debug visual")
    
    return False, ultima_imagen, ultimos_datos
```

### **Función de análisis completo (CON VALIDACIONES TEMPRANAS Y ACTUALIZACIÓN PROGRESIVA)**
```python
def analizar_frame_completo(frame, callback_progreso=None):
    """
    Ejecuta el pipeline completo de análisis en un frame.
    
    IMPORTANTE:
    - Usa validaciones TEMPRANAS (early returns) para evitar desperdiciar recursos
    - Actualiza la tabla de resultados PROGRESIVAMENTE en cada paso
    - Llama a callback_progreso() después de cada validación crítica
    
    Args:
        frame: Imagen RGB de OpenCV
        callback_progreso: Función opcional para enviar progreso al frontend
                          callback_progreso(datos_parciales)
    
    Returns:
        (exito: bool, imagen_procesada: bytes, datos: dict)
    """
    import json
    import os
    
    # PASO 0: Crear objeto acumulador para visualización
    datos_visualizacion = {
        'aruco': None,
        'junta': None,
        'agujeros': [],
        'linea_referencia': None,
        'muescas': []
    }
    
    # Cargar junta seleccionada (necesaria para validaciones tempranas)
    junta_esperada = _cargar_junta_seleccionada()
    if junta_esperada is None:
        return False, None, {'error': 'No hay junta seleccionada'}
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 1: Detectar ArUco (calibración)
    # ═══════════════════════════════════════════════════════════════════
    datos_aruco = detectar_aruco(frame)
    if datos_aruco is None:
        return False, None, {'error': 'No se detectó ArUco'}
    
    datos_visualizacion['aruco'] = datos_aruco
    print(f"[pipeline] ✓ ArUco detectado: px_per_mm={datos_aruco['px_per_mm']:.3f}")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 2: Detectar junta (bounding box)
    # ═══════════════════════════════════════════════════════════════════
    datos_junta = detectar_junta(frame)
    if datos_junta is None:
        return False, None, {'error': 'No se detectó junta'}
    
    datos_visualizacion['junta'] = datos_junta
    print(f"[pipeline] ✓ Junta detectada: tipo={datos_junta['tipo']}")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 3: Detectar agujeros con YOLO
    # ═══════════════════════════════════════════════════════════════════
    datos_agujeros = detectar_agujeros(frame, datos_junta)
    
    if not datos_agujeros or len(datos_agujeros) == 0:
        return False, None, {'error': 'No se detectaron agujeros'}
    
    # ╔═══════════════════════════════════════════════════════════════╗
    # ║ VALIDACIÓN TEMPRANA 1: CANTIDAD DE PISTONES (EARLY RETURN)   ║
    # ╚═══════════════════════════════════════════════════════════════╝
    cantidad_detectada = len(datos_agujeros)
    cantidad_esperada = junta_esperada.get('resumen_analisis', {}).get('redondos_grandes', 0)
    
    print(f"[pipeline] Pistones detectados: {cantidad_detectada}, esperados: {cantidad_esperada}")
    
    if cantidad_detectada != cantidad_esperada:
        # ⚠️  CANTIDAD INCORRECTA → REINTENTO INMEDIATO (no procesar más)
        datos_parciales = {
            'aruco': {'detected': True, 'px_per_mm': datos_aruco['px_per_mm']},
            'holes': {
                'total_detected': cantidad_detectada,
                'distancia_extremos_mm': None
            },
            'validacion_temprana': 'cantidad_pistones',
            'error': f'Cantidad incorrecta: esperado {cantidad_esperada}, obtenido {cantidad_detectada}'
        }
        
        # Enviar progreso al frontend
        if callback_progreso:
            callback_progreso(datos_parciales)
        
        return False, None, datos_parciales
    
    datos_visualizacion['agujeros'] = datos_agujeros
    print(f"[pipeline] ✓ Validación temprana 1 PASADA: Cantidad correcta ({cantidad_detectada})")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 4: Calcular métricas (distancias, punto medio)
    # ═══════════════════════════════════════════════════════════════════
    metricas = calcular_metricas(datos_agujeros, datos_aruco)
    datos_visualizacion['linea_referencia'] = metricas
    
    # ╔═══════════════════════════════════════════════════════════════╗
    # ║ VALIDACIÓN TEMPRANA 2: DISTANCIA EXTREMOS (EARLY RETURN)     ║
    # ╚═══════════════════════════════════════════════════════════════╝
    distancia_obtenida_mm = metricas.get('distancia_mm')
    
    # Cargar distancia esperada del análisis de la junta
    analisis_junta = _cargar_analisis_junta(junta_esperada['nombre'])
    distancia_esperada_mm = analisis_junta.get('linea_referencia', {}).get('distancia_mm', 0)
    
    # Cargar umbral de tolerancia
    import camera_manager
    config = camera_manager.load_config()
    umbral_distancia_tol = config.get('vision', {}).get('umbral_distancia_tolerancia', 98.0)
    
    if distancia_obtenida_mm and distancia_esperada_mm:
        acierto_distancia = 100 - abs((distancia_obtenida_mm - distancia_esperada_mm) / distancia_esperada_mm * 100)
        
        print(f"[pipeline] Distancia: {distancia_obtenida_mm:.1f}mm (esperada: {distancia_esperada_mm:.1f}mm)")
        print(f"[pipeline] Acierto: {acierto_distancia:.1f}% (umbral: {umbral_distancia_tol}%)")
        
        if acierto_distancia < umbral_distancia_tol:
            # ⚠️  DISTANCIA FUERA DE TOLERANCIA → REINTENTO INMEDIATO
            datos_parciales = {
                'aruco': {'detected': True, 'px_per_mm': datos_aruco['px_per_mm']},
                'holes': {
                    'total_detected': cantidad_detectada,
                    'distancia_extremos_mm': distancia_obtenida_mm
                },
                'validacion_temprana': 'distancia_extremos',
                'error': f'Distancia fuera de tolerancia: {acierto_distancia:.1f}% (requerido {umbral_distancia_tol}%)'
            }
            
            # Enviar progreso al frontend
            if callback_progreso:
                callback_progreso(datos_parciales)
            
            return False, None, datos_parciales
    
    print(f"[pipeline] ✓ Validación temprana 2 PASADA: Distancia dentro de tolerancia")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 5: Validaciones geométricas (centros, colinealidad, espaciado)
    # ═══════════════════════════════════════════════════════════════════
    import validaciones_geometricas as validaciones
    resultados_validacion = validaciones.validar_todo(datos_agujeros, datos_aruco, metricas)
    
    analisis_exitoso = resultados_validacion['todas_ok']
    
    if not analisis_exitoso:
        print(f"[pipeline] ⚠️ Validaciones geométricas FALLARON")
        
        # Enviar progreso al frontend
        datos_parciales = {
            'aruco': {'detected': True, 'px_per_mm': datos_aruco['px_per_mm']},
            'holes': {
                'total_detected': cantidad_detectada,
                'distancia_extremos_mm': distancia_obtenida_mm
            },
            'validaciones_geometricas': resultados_validacion,
            'error': 'Validaciones geométricas fallaron'
        }
        
        if callback_progreso:
            callback_progreso(datos_parciales)
    else:
        print(f"[pipeline] ✓ Todas las validaciones geométricas PASADAS")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 6: Calcular muescas SOLO SI TODO PASÓ
    # ═══════════════════════════════════════════════════════════════════
    if analisis_exitoso:
        muescas = calcular_posiciones_muescas(metricas, datos_aruco)
        datos_visualizacion['muescas'] = muescas
        print(f"[pipeline] ✓ Muescas calculadas: {len(muescas)}")
    else:
        # NO calcular muescas si hay fallas (no se dibujan en caso de error)
        datos_visualizacion['muescas'] = []
        print(f"[pipeline] ✗ Muescas omitidas (análisis falló)")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 7: Dibujar overlay SIEMPRE (incluso si falló) para DEBUG VISUAL
    # ═══════════════════════════════════════════════════════════════════
    # ⚠️  IMPORTANTE: El overlay se dibuja SIEMPRE para ver qué salió mal
    # - Si pasó todo: dibuja con muescas
    # - Si falló: dibuja sin muescas (debug visual)
    
    import visualizador
    imagen_con_overlays = visualizador.dibujar_todo(frame, datos_visualizacion)
    
    # PASO 8: Codificar imagen a JPEG
    import cv2
    _, buffer = cv2.imencode('.jpg', imagen_con_overlays, [cv2.IMWRITE_JPEG_QUALITY, 95])
    imagen_bytes = buffer.tobytes()
    
    # PASO 9: Preparar datos completos de salida
    datos_completos = {
        'aruco': {
            'detected': True,
            'px_per_mm': datos_aruco['px_per_mm'],
            'center': datos_aruco['center']
        },
        'gasket': datos_junta,
        'holes': {
            'total_detected': cantidad_detectada,
            'distancia_extremos_px': metricas['distancia_px'],
            'distancia_extremos_mm': distancia_obtenida_mm,
            'punto1': metricas['p1'],
            'punto2': metricas['p2'],
            'punto_medio': metricas['punto_medio']
        },
        'validaciones_geometricas': resultados_validacion
    }
    
    # Enviar progreso final al frontend
    if callback_progreso:
        callback_progreso(datos_completos)
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 10: Retornar resultado
    # ═══════════════════════════════════════════════════════════════════
    # SIEMPRE retorna la imagen (incluso si falló) para debug visual
    # El flag 'analisis_exitoso' indica si se debe reintentar o no
    
    if analisis_exitoso:
        return True, imagen_bytes, datos_completos
    else:
        # Retorna imagen para debug, pero marca como falla para reintento
        return False, imagen_bytes, datos_completos


# ═══════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES PRIVADAS
# ═══════════════════════════════════════════════════════════════════════

def _cargar_junta_seleccionada():
    """Carga la junta seleccionada desde juntas.json"""
    import json
    import os
    
    juntas_db_file = 'juntas.json'
    if not os.path.exists(juntas_db_file):
        return None
    
    try:
        with open(juntas_db_file, 'r', encoding='utf-8') as f:
            db = json.load(f)
        
        selected_id = db.get('selected_id')
        if selected_id is None:
            return None
        
        junta = next((j for j in db.get('juntas', []) if j['id'] == selected_id), None)
        return junta
    
    except Exception as e:
        print(f"[pipeline] Error cargando junta seleccionada: {e}")
        return None


def _cargar_analisis_junta(nombre_junta):
    """Carga el análisis detallado de una junta"""
    import json
    import os
    
    analisis_file = os.path.join('juntas_analisis', f"{nombre_junta}_analisis.json")
    
    if not os.path.exists(analisis_file):
        return {}
    
    try:
        with open(analisis_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[pipeline] Error cargando análisis: {e}")
        return {}
```

### **Funciones auxiliares de detección**

```python
def detectar_aruco(frame):
    """
    Detecta el marcador ArUco de referencia.
    
    Returns:
        dict: {'id', 'center', 'px_per_mm', 'angle_rad'} o None
    """
    import aruco_detector
    import camera_manager
    
    config = camera_manager.load_config()
    aruco_config = config.get('aruco', {})
    
    reference_id = aruco_config.get('reference_id', 0)
    marker_size_mm = aruco_config.get('marker_size_mm', 42.0)
    dictionary_id = aruco_config.get('dictionary_id', 50)
    
    deteccion = aruco_detector.detect_aruco_by_id(
        frame, 
        reference_id, 
        dictionary_id, 
        marker_size_mm
    )
    
    if deteccion is None:
        return None
    
    # Calcular ángulo de rotación del ArUco
    import numpy as np
    corners = np.array(deteccion['corners'])
    dx = corners[1][0] - corners[0][0]
    dy = corners[1][1] - corners[0][1]
    angle_rad = np.arctan2(dy, dx)
    
    return {
        'id': deteccion['id'],
        'center': deteccion['center'],
        'px_per_mm': deteccion['px_per_mm'],
        'angle_rad': angle_rad,
        'corners': deteccion['corners']
    }


def detectar_junta(frame):
    """
    Detecta la junta completa usando YOLO.
    
    Returns:
        dict: {'bbox', 'tipo', 'dimensiones'} o None
    """
    import yolo_detector
    
    resultado = yolo_detector.detect_gasket(frame, conf_threshold=0.5)
    
    if resultado is None:
        return None
    
    # Procesar según tipo (OBB o bbox normal)
    if isinstance(resultado, dict) and resultado.get('type') == 'obb':
        return {
            'bbox': resultado['bbox'],  # (x1, y1, x2, y2)
            'tipo': 'obb',
            'center': resultado['center'],
            'size': resultado['size'],
            'angle': resultado['angle'],
            'points': resultado['points']
        }
    else:
        # Bbox normal
        x1, y1, x2, y2 = resultado
        return {
            'bbox': (x1, y1, x2, y2),
            'tipo': 'rect',
            'width': x2 - x1,
            'height': y2 - y1
        }


def detectar_agujeros(frame, datos_junta):
    """
    Detecta agujeros en el área de la junta con padding.
    
    ┌─────────────────────────────────────────────────────────────────────┐
    │  SECUENCIA DE DETECCIÓN - 3 ETAPAS                                  │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │  ETAPA 1: YOLO Detection (detect_gasket)                            │
    │  ────────────────────────────────────────                           │
    │  Frame completo (1920x1080)                                         │
    │      ↓                                                               │
    │  [YOLO Detection Model]                                             │
    │      ↓                                                               │
    │  bbox_junta = (x1, y1, x2, y2)  ← UN solo bbox de junta            │
    │                                                                      │
    │  ═══════════════════════════════════════════════════════════════    │
    │                                                                      │
    │  ETAPA 2: YOLO Holes (detect_holes_bboxes)                          │
    │  ──────────────────────────────────────────                         │
    │  Crop de junta con padding 10% (500x300)                            │
    │      ↓                                                               │
    │  [YOLO Holes Model]                                                 │
    │      ↓                                                               │
    │  bboxes_agujeros = [                                                │
    │      {'bbox': (10, 20, 50, 60)},    ← Agujero 1                    │
    │      {'bbox': (100, 25, 140, 65)},  ← Agujero 2                    │
    │      {'bbox': (200, 22, 240, 62)},  ← Agujero 3                    │
    │      ...                                                             │
    │  ]                                                                   │
    │                                                                      │
    │  ═══════════════════════════════════════════════════════════════    │
    │                                                                      │
    │  ETAPA 3: OpenCV (calcular_centro_agujero) - PARA CADA AGUJERO     │
    │  ───────────────────────────────────────────────────────────────    │
    │  Por cada bbox de agujero:                                          │
    │                                                                      │
    │    Crop individual del agujero (40x40)                              │
    │        ↓                                                             │
    │    [OpenCV - Detectar azul predominante]                            │
    │        ↓                                                             │
    │    Máscara binaria del agujero azul                                 │
    │        ↓                                                             │
    │    [OpenCV - Encontrar contornos]                                   │
    │        ↓                                                             │
    │    Contorno del agujero                                             │
    │        ↓                                                             │
    │    [OpenCV - Ajustar elipse]                                        │
    │        ↓                                                             │
    │    {                                                                 │
    │        'center': (20, 20),      ← Centro PRECISO                   │
    │        'contour': [...],                                            │
    │        'ellipse': (center, axes, angle)                             │
    │    }                                                                 │
    │                                                                      │
    │    ↓ Repetir para cada agujero detectado por YOLO                   │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘
    
    NUEVO ENFOQUE MODULAR:
    1. YOLO detecta agujeros (solo localización, bounding boxes)
    2. Por cada agujero, se recorta su área
    3. Se llama a calcular_centro_agujero() para refinamiento con OpenCV
    
    Returns:
        list: [{'center', 'contour', 'ellipse'}, ...]
    """
    import yolo_detector
    import numpy as np
    
    # ═══════════════════════════════════════════════════════════════════════
    # DIAGRAMA VISUAL CON COORDENADAS
    # ═══════════════════════════════════════════════════════════════════════
    #
    #  Frame original (1920x1080)
    #  ┌─────────────────────────────────────────────────────────────┐
    #  │                                                               │
    #  │     ETAPA 1: YOLO Detection                                  │
    #  │     ┌───────────────────────────┐                            │
    #  │     │  Junta detectada          │ ← bbox: (500, 300, 1400, 800)
    #  │     │                           │                            │
    #  │     │  [Area de junta]          │                            │
    #  │     │                           │                            │
    #  │     └───────────────────────────┘                            │
    #  │                                                               │
    #  └─────────────────────────────────────────────────────────────┘
    #                    ↓
    #  Crop de junta + padding 10% (450, 270, 1450, 830)
    #  ┌─────────────────────────────────────────────────┐
    #  │                                                   │
    #  │  ETAPA 2: YOLO Holes                             │
    #  │  ┌──┐      ┌──┐      ┌──┐      ┌──┐            │
    #  │  │A1│      │A2│      │A3│      │A4│  ← 4 agujeros detectados
    #  │  └──┘      └──┘      └──┘      └──┘            │
    #  │  (10,20    (100,25   (200,22   (300,20         │
    #  │   50,60)   140,65)   240,62)   340,60)         │
    #  │                                                   │
    #  └─────────────────────────────────────────────────┘
    #                    ↓
    #  ETAPA 3: OpenCV - Por cada agujero
    #  ┌─────────────────────────────────────────────────┐
    #  │                                                   │
    #  │  Crop A1 (40x40)     Crop A2 (40x40)            │
    #  │  ┌────────┐          ┌────────┐                 │
    #  │  │ ████   │          │  ████  │                 │
    #  │  │█    █  │          │ █    █ │                 │
    #  │  │█  ⊗ █  │          │ █  ⊗ █ │  ⊗ = centro    │
    #  │  │ █  █   │          │  █  █  │                 │
    #  │  │  ████  │          │   ████ │                 │
    #  │  └────────┘          └────────┘                 │
    #  │     ↓                    ↓                       │
    #  │  center:(20,20)      center:(20,20)             │
    #  │                                                   │
    #  └─────────────────────────────────────────────────┘
    #                    ↓
    #  Ajuste de coordenadas al frame original:
    #  center_global = center_local + offset_agujero + offset_junta
    #  
    #  Ejemplo Agujero 1:
    #    center_local   = (20, 20)      ← En crop de 40x40
    #    offset_agujero = (10, 20)      ← Posición en crop de junta
    #    offset_junta   = (450, 270)    ← Posición de junta en frame
    #    ───────────────────────────────
    #    center_global  = (480, 310)    ← Coordenada final en frame 1920x1080
    #
    # ═══════════════════════════════════════════════════════════════════════
    
    # PASO 1: Extraer bbox de junta y calcular padding 10%
    x1, y1, x2, y2 = datos_junta['bbox']
    box_w = x2 - x1
    box_h = y2 - y1
    padding_w = int(box_w * 0.10)
    padding_h = int(box_h * 0.10)
    
    # Calcular coordenadas con padding
    frame_h, frame_w = frame.shape[:2]
    final_x1 = max(0, x1 - padding_w)
    final_y1 = max(0, y1 - padding_h)
    final_x2 = min(frame_w, x2 + padding_w)
    final_y2 = min(frame_h, y2 + padding_h)
    
    # PASO 2: Recortar área de junta
    cropped_frame = frame[final_y1:final_y2, final_x1:final_x2]
    
    # PASO 3: YOLO detecta agujeros (solo ubicación, bounding boxes)
    detecciones_yolo = yolo_detector.detect_holes_bboxes(cropped_frame, conf_threshold=0.5)
    
    if not detecciones_yolo:
        return []
    
    # PASO 4: Por cada agujero detectado por YOLO, refinar con OpenCV
    agujeros_refinados = []
    offset_x = final_x1
    offset_y = final_y1
    
    for idx, det_yolo in enumerate(detecciones_yolo):
        # Extraer bbox del agujero (relativo al crop de junta)
        agujero_bbox = det_yolo['bbox']  # (x1, y1, x2, y2)
        
        # Recortar área del agujero individual
        ax1, ay1, ax2, ay2 = agujero_bbox
        crop_agujero = cropped_frame[ay1:ay2, ax1:ax2]
        
        # PASO 5: Refinar con OpenCV (función separada y reutilizable)
        resultado_opencv = calcular_centro_agujero(crop_agujero)
        
        if resultado_opencv is None:
            print(f"[pipeline] ⚠️ Agujero {idx} no pudo ser refinado con OpenCV")
            continue
        
        # PASO 6: Ajustar coordenadas al frame original
        # Coordenadas locales del agujero → Coordenadas de crop de junta → Coordenadas globales
        center_local = resultado_opencv['center']
        contour_local = resultado_opencv['contour']
        ellipse_local = resultado_opencv.get('ellipse')
        
        # Ajustar centro
        center_global = (
            center_local[0] + ax1 + offset_x,
            center_local[1] + ay1 + offset_y
        )
        
        # Ajustar contorno
        contour_global = contour_local + np.array([ax1 + offset_x, ay1 + offset_y])
        
        # Ajustar elipse
        ellipse_global = None
        if ellipse_local:
            ellipse_global = (
                (ellipse_local[0][0] + ax1 + offset_x, ellipse_local[0][1] + ay1 + offset_y),
                ellipse_local[1],
                ellipse_local[2]
            )
        
        agujeros_refinados.append({
            'center': center_global,
            'contour': contour_global,
            'ellipse': ellipse_global
        })
        
        print(f"[pipeline] ✓ Agujero {idx} refinado: centro={center_global}")
    
    return agujeros_refinados


def calcular_centro_agujero(crop_agujero):
    """
    Función MODULAR y REUTILIZABLE para calcular el centro preciso de un agujero.
    Recibe el crop de UN solo pistón y aplica OpenCV para refinamiento.
    
    ESTRATEGIA:
    1. Detectar píxeles donde AZUL es predominante
    2. Encontrar contornos del agujero
    3. Ajustar elipse al contorno
    4. Calcular centro de la elipse
    
    Args:
        crop_agujero: Imagen RGB del agujero recortado (numpy array)
    
    Returns:
        dict: {'center': (x, y), 'contour': contour, 'ellipse': ellipse_params}
        o None si no se puede calcular
    """
    import cv2
    import numpy as np
    
    if crop_agujero is None or crop_agujero.size == 0:
        return None
    
    try:
        # PASO 1: Extraer canales BGR
        b_channel = crop_agujero[:, :, 0].astype(np.float32)
        g_channel = crop_agujero[:, :, 1].astype(np.float32)
        r_channel = crop_agujero[:, :, 2].astype(np.float32)
        
        # PASO 2: Crear máscara donde azul es predominante
        # Un píxel es "azul" si B > (G + R) * factor
        factor_predominancia = 0.7
        es_azul = b_channel > (g_channel + r_channel) * factor_predominancia
        
        # Máscara binaria: azul → 255, no azul → 0
        blue_mask = np.zeros_like(b_channel, dtype=np.uint8)
        blue_mask[es_azul] = 255
        
        # PASO 3: Encontrar contornos del agujero azul
        contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # PASO 4: Seleccionar contorno de mayor área
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)
        
        if area < 10:  # Filtrar contornos muy pequeños (ruido)
            return None
        
        # PASO 5: Ajustar elipse al contorno
        if len(largest_contour) >= 5:  # Mínimo para fitEllipse
            ellipse = cv2.fitEllipse(largest_contour)
            center_x = int(ellipse[0][0])
            center_y = int(ellipse[0][1])
            
            return {
                'center': (center_x, center_y),
                'contour': largest_contour,
                'ellipse': ellipse
            }
        else:
            # Si no hay suficientes puntos para elipse, usar momentos
            moments = cv2.moments(largest_contour)
            if moments["m00"] != 0:
                center_x = int(moments["m10"] / moments["m00"])
                center_y = int(moments["m01"] / moments["m00"])
                
                return {
                    'center': (center_x, center_y),
                    'contour': largest_contour,
                    'ellipse': None
                }
            else:
                return None
    
    except Exception as e:
        print(f"[pipeline] Error calculando centro de agujero: {e}")
        return None


def calcular_metricas(datos_agujeros, datos_aruco):
    """
    Calcula métricas básicas: línea de referencia, punto medio, distancias.
    
    Returns:
        dict: {'p1', 'p2', 'punto_medio', 'distancia_px', 'distancia_mm'}
    """
    import numpy as np
    
    # Extraer centros
    centros = [ag['center'] for ag in datos_agujeros]
    
    if len(centros) < 2:
        return {
            'p1': None,
            'p2': None,
            'punto_medio': None,
            'distancia_px': None,
            'distancia_mm': None
        }
    
    # Ordenar de izquierda a derecha
    centros_ordenados = sorted(centros, key=lambda p: (p[0], p[1]))
    
    # Extremos
    p1 = centros_ordenados[0]
    p2 = centros_ordenados[-1]
    
    # Punto medio
    punto_medio = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
    
    # Distancia en píxeles
    distancia_px = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
    
    # Distancia en mm (si hay calibración)
    distancia_mm = None
    if datos_aruco and datos_aruco.get('px_per_mm'):
        px_per_mm = datos_aruco['px_per_mm']
        distancia_mm = distancia_px / px_per_mm
    
    return {
        'p1': p1,
        'p2': p2,
        'punto_medio': punto_medio,
        'distancia_px': float(distancia_px),
        'distancia_mm': float(distancia_mm) if distancia_mm else None,
        'centros_ordenados': centros_ordenados
    }


def calcular_posiciones_muescas(metricas, datos_aruco):
    """
    Calcula las posiciones en píxeles de las muescas de la junta seleccionada.
    
    Returns:
        list: [{'x_px', 'y_px', 'radio_px'}, ...] o []
    """
    import json
    import os
    import numpy as np
    
    # Verificar que tengamos punto medio y calibración
    if not metricas.get('punto_medio') or not datos_aruco:
        return []
    
    punto_medio = metricas['punto_medio']
    px_per_mm = datos_aruco.get('px_per_mm')
    angle_rad = datos_aruco.get('angle_rad')
    
    if not px_per_mm or angle_rad is None:
        return []
    
    # Cargar junta seleccionada
    juntas_db_file = 'juntas.json'
    if not os.path.exists(juntas_db_file):
        return []
    
    try:
        with open(juntas_db_file, 'r', encoding='utf-8') as f:
            db = json.load(f)
        
        selected_id = db.get('selected_id')
        if selected_id is None:
            return []
        
        # Buscar junta
        junta = next((j for j in db.get('juntas', []) if j['id'] == selected_id), None)
        
        if not junta or not junta.get('centros_muescas'):
            return []
        
        centros_muescas = junta['centros_muescas']
        
        # Radio de muesca: 4mm diámetro = 2mm radio
        radio_mm = 2.0
        radio_px = int(radio_mm * px_per_mm)
        
        # Convertir cada muesca de mm a px
        muescas_px = []
        for muesca in centros_muescas:
            # Obtener coordenadas en mm
            if 'centro_mm' in muesca and isinstance(muesca['centro_mm'], list):
                x_mm, y_mm = muesca['centro_mm']
            elif 'x' in muesca and 'y' in muesca:
                x_mm = muesca['x']
                y_mm = muesca['y']
            else:
                continue
            
            # Convertir mm → px
            offset_x_px = x_mm * px_per_mm
            offset_y_px = -y_mm * px_per_mm  # Reflejar Y
            
            # Aplicar rotación
            cos_angle = np.cos(angle_rad)
            sin_angle = np.sin(angle_rad)
            
            x_rotated = offset_x_px * cos_angle - offset_y_px * sin_angle
            y_rotated = offset_x_px * sin_angle + offset_y_px * cos_angle
            
            # Calcular posición absoluta
            pos_x = punto_medio[0] + x_rotated
            pos_y = punto_medio[1] + y_rotated
            
            muescas_px.append({
                'x_px': pos_x,
                'y_px': pos_y,
                'radio_px': radio_px
            })
        
        return muescas_px
    
    except Exception as e:
        print(f"[pipeline] Error calculando muescas: {e}")
        return []
```

---

---

## 📝 MODIFICACIÓN NECESARIA: `yolo_detector.py`

### **Nueva función requerida: `detect_holes_bboxes()`**

```python
def detect_holes_bboxes(frame, conf_threshold=0.5):
    """
    Detecta agujeros usando YOLO y retorna SOLO bounding boxes.
    NO hace refinamiento con OpenCV (eso se delega a pipeline_analisis.py).
    
    Args:
        frame: Frame de OpenCV (numpy array)
        conf_threshold: Umbral de confianza
    
    Returns:
        list: [{'bbox': (x1, y1, x2, y2)}, ...]
    """
    if not YOLO_AVAILABLE or _models['holes'] is None:
        return []
    
    try:
        # Ejecutar detección YOLO
        results = _models['holes'](frame, conf=conf_threshold, verbose=False)
        
        if results[0].boxes is None or len(results[0].boxes) == 0:
            return []
        
        detecciones = []
        
        # Por cada detección, extraer solo el bounding box
        for box in results[0].boxes:
            bbox = box.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = map(int, bbox)
            
            detecciones.append({
                'bbox': (x1, y1, x2, y2)
            })
        
        print(f"[yolo] Detectados {len(detecciones)} agujeros (bboxes)")
        return detecciones
    
    except Exception as e:
        print(f"[yolo] Error detectando agujeros: {e}")
        return []
```

**Nota:** La función actual `detect_holes_with_contours()` se mantiene para compatibilidad con código viejo, pero el nuevo pipeline usa `detect_holes_bboxes()`.

---

## 📦 ARCHIVO 2: `validaciones_geometricas.py`

### **Función principal**
```python
def validar_todo(datos_agujeros, datos_aruco, metricas):
    """
    Ejecuta todas las validaciones geométricas.
    
    Returns:
        dict: {
            'centros_multiples': {...},
            'colinealidad': {...},
            'espaciado_uniforme': {...},
            'todas_ok': bool
        }
    """
    
    if not datos_aruco or not datos_aruco.get('px_per_mm'):
        return {
            'error': 'No hay calibración ArUco',
            'todas_ok': False
        }
    
    px_per_mm = datos_aruco['px_per_mm']
    centros = metricas['centros_ordenados']
    
    # Cargar umbrales de configuración
    import camera_manager
    config = camera_manager.load_config()
    vision_config = config.get('vision', {})
    
    umbral_centros_mm = vision_config.get('umbral_centros_mm', 3.0)
    umbral_colinealidad_mm = vision_config.get('umbral_colinealidad_mm', 2.0)
    umbral_espaciado_cv = vision_config.get('umbral_espaciado_cv', 0.05)
    
    # Ejecutar validaciones
    val_centros = validar_centros_multiples(centros, px_per_mm, umbral_centros_mm)
    val_colinealidad = validar_colinealidad(centros, px_per_mm, umbral_colinealidad_mm)
    val_espaciado = validar_espaciado_uniforme(centros, px_per_mm, umbral_espaciado_cv)
    
    # Resultado final
    todas_ok = val_centros['ok'] and val_colinealidad['ok'] and val_espaciado['ok']
    
    return {
        'centros_multiples': val_centros,
        'colinealidad': val_colinealidad,
        'espaciado_uniforme': val_espaciado,
        'todas_ok': todas_ok
    }
```

### **Validación 1: Centros múltiples**
```python
def validar_centros_multiples(centros, px_per_mm, umbral_mm):
    """
    Valida que el centro calculado por pares simétricos sea consistente.
    
    Returns:
        dict: {'ok': bool, 'divergencia_mm': float, 'umbral_mm': float}
    """
    # TODO: Implementar
    pass
```

### **Validación 2: Colinealidad**
```python
def validar_colinealidad(centros, px_per_mm, umbral_mm):
    """
    Valida que todos los centros estén alineados en línea recta.
    
    Returns:
        dict: {'ok': bool, 'desviacion_maxima_mm': float, 'umbral_mm': float}
    """
    # TODO: Implementar
    pass
```

### **Validación 3: Espaciado uniforme**
```python
def validar_espaciado_uniforme(centros, px_per_mm, cv_maximo):
    """
    Valida que el espaciado entre pistones vecinos sea uniforme.
    
    Returns:
        dict: {'ok': bool, 'coeficiente_variacion': float, 'cv_maximo': float}
    """
    # TODO: Implementar
    pass
```

---

## 📦 ARCHIVO 3: `visualizador.py`

### **🎨 NUEVO ENFOQUE: Objeto acumulador + Una sola función de dibujo**

**Idea:** En lugar de pasar múltiples parámetros, usamos un **objeto/diccionario acumulador** que se va llenando durante el análisis. Al final, UNA sola función dibuja todo leyendo el objeto.

### **Estructura del objeto acumulador**
```python
# Objeto que se llena durante el análisis
datos_visualizacion = {
    'aruco': None,           # Datos del ArUco detectado
    'junta': None,           # Datos de la junta (bbox)
    'agujeros': [],          # Lista de agujeros detectados
    'linea_referencia': None,# Línea entre extremos + punto medio
    'muescas': []            # Posiciones de muescas (si aplica)
}
```

### **Función principal de dibujo**
```python
def dibujar_todo(frame, datos_visualizacion):
    """
    Dibuja todos los overlays en el frame en UNA SOLA PASADA.
    
    IMPORTANTE: El diccionario datos_visualizacion SIEMPRE contiene todos los datos
    (generados por las funciones de análisis). Esta función es la ÚNICA responsable
    de decidir QUÉ dibujar, consultando los checkboxes de configuración.
    
    Args:
        frame: Imagen RGB original
        datos_visualizacion: Diccionario con TODOS los datos generados en el análisis
    
    Returns:
        frame con overlays dibujados según configuración
    """
    import cv2
    import numpy as np
    import camera_manager
    
    # PASO 1: Convertir a escala de grises para fondo
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resultado = cv2.cvtColor(frame_gray, cv2.COLOR_GRAY2BGR)
    
    # PASO 2: Leer configuración (checkboxes de las páginas)
    config = camera_manager.load_config()
    vision_config = config.get('vision', {})
    aruco_config = config.get('aruco', {})
    
    # Checkboxes de ArUco (página de configuración ArUco)
    show_aruco = aruco_config.get('show_reference', False)
    
    # Checkboxes de Vision System (página de configuración Vision)
    show_bbox = vision_config.get('show_bbox', False)
    show_contours = vision_config.get('show_contours', True)
    show_ellipses = vision_config.get('show_ellipses', False)
    show_notches = vision_config.get('show_notches', False)
    
    # PASO 3: Dibujar ArUco SOLO SI está habilitado
    if show_aruco and datos_visualizacion.get('aruco'):
        datos_aruco = datos_visualizacion['aruco']
        resultado = _dibujar_aruco(resultado, datos_aruco)
        print("[visualizador] ✓ ArUco dibujado (show_reference=True)")
    else:
        print(f"[visualizador] ✗ ArUco omitido (show_reference={show_aruco})")
    
    # PASO 4: Dibujar bbox de junta SOLO SI está habilitado
    if show_bbox and datos_visualizacion.get('junta'):
        datos_junta = datos_visualizacion['junta']
        resultado = _dibujar_bbox_junta(resultado, datos_junta)
        print("[visualizador] ✓ Bbox junta dibujado (show_bbox=True)")
    else:
        print(f"[visualizador] ✗ Bbox junta omitido (show_bbox={show_bbox})")
    
    # PASO 5: Dibujar agujeros según configuración
    if datos_visualizacion.get('agujeros'):
        agujeros = datos_visualizacion['agujeros']
        # Pasar flags de configuración a la función
        resultado = _dibujar_agujeros(resultado, agujeros, show_contours, show_ellipses)
        print(f"[visualizador] ✓ Agujeros dibujados (contours={show_contours}, ellipses={show_ellipses})")
    else:
        print("[visualizador] ✗ No hay agujeros para dibujar")
    
    # PASO 6: Dibujar línea de referencia (SIEMPRE se dibuja si existe)
    if datos_visualizacion.get('linea_referencia'):
        linea = datos_visualizacion['linea_referencia']
        resultado = _dibujar_linea_referencia(resultado, linea)
        print("[visualizador] ✓ Línea de referencia dibujada")
    
    # PASO 7: Dibujar muescas SOLO SI está habilitado
    if show_notches and datos_visualizacion.get('muescas'):
        muescas = datos_visualizacion['muescas']
        resultado = _dibujar_muescas(resultado, muescas)
        print(f"[visualizador] ✓ Muescas dibujadas (show_notches=True, cantidad={len(muescas)})")
    else:
        print(f"[visualizador] ✗ Muescas omitidas (show_notches={show_notches})")
    
    return resultado
```

### **Funciones auxiliares privadas de dibujo**

```python
def _dibujar_aruco(frame, datos_aruco):
    """
    Dibuja ejes y contorno del ArUco.
    
    datos_aruco debe contener: {center, angle_rad, corners}
    """
    import cv2
    import numpy as np
    
    center = datos_aruco['center']
    angle_rad = datos_aruco['angle_rad']
    corners = np.array(datos_aruco['corners'])
    
    height, width = frame.shape[:2]
    max_length = max(width, height) * 2
    
    # Calcular puntos finales de los ejes
    # Eje X (rojo) - alineado con ArUco
    x_end1 = (int(center[0] + max_length * np.cos(angle_rad)), 
              int(center[1] + max_length * np.sin(angle_rad)))
    x_end2 = (int(center[0] - max_length * np.cos(angle_rad)), 
              int(center[1] - max_length * np.sin(angle_rad)))
    
    # Eje Y (verde) - perpendicular
    y_angle_rad = angle_rad + np.pi / 2
    y_end1 = (int(center[0] + max_length * np.cos(y_angle_rad)), 
              int(center[1] + max_length * np.sin(y_angle_rad)))
    y_end2 = (int(center[0] - max_length * np.cos(y_angle_rad)), 
              int(center[1] - max_length * np.sin(y_angle_rad)))
    
    # Dibujar ejes
    cv2.line(frame, x_end2, x_end1, (0, 0, 255), 2)  # Eje X rojo
    cv2.line(frame, y_end2, y_end1, (0, 255, 0), 2)  # Eje Y verde
    
    # Dibujar punto central
    cv2.circle(frame, tuple(center), 8, (0, 0, 255), -1)
    cv2.circle(frame, tuple(center), 6, (255, 255, 255), -1)
    
    # Dibujar contorno del ArUco
    corners_int = corners.astype(np.int32)
    cv2.polylines(frame, [corners_int], True, (0, 255, 255), 2)
    
    return frame


def _dibujar_bbox_junta(frame, datos_junta):
    """
    Dibuja bounding box de la junta.
    
    datos_junta debe contener: {tipo: 'obb'|'rect', bbox o points}
    """
    import cv2
    
    if datos_junta['tipo'] == 'obb':
        # Dibujar rectángulo rotado
        points = datos_junta['points']
        cv2.drawContours(frame, [points], 0, (0, 255, 0), 2)
    else:
        # Dibujar rectángulo normal
        x1, y1, x2, y2 = datos_junta['bbox']
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    
    return frame


def _dibujar_agujeros(frame, agujeros, show_contours, show_ellipses):
    """
    Dibuja contornos y/o elipses de agujeros.
    
    agujeros: lista de {'center', 'contour', 'ellipse'}
    """
    import cv2
    import numpy as np
    
    for agujero in agujeros:
        center = agujero['center']
        contour = agujero['contour']
        ellipse = agujero.get('ellipse')
        
        # Dibujar contorno (cyan)
        if show_contours and contour is not None:
            cv2.drawContours(frame, [contour.astype(np.int32)], -1, (255, 255, 0), 2)
        
        # Dibujar elipse (verde)
        if show_ellipses and ellipse is not None:
            cv2.ellipse(frame, ellipse, (0, 255, 0), 2)
        
        # Dibujar centro (verde + rojo)
        cv2.circle(frame, tuple(center), 8, (0, 255, 0), -1)
        cv2.circle(frame, tuple(center), 2, (0, 0, 255), -1)
    
    return frame


def _dibujar_linea_referencia(frame, linea):
    """
    Dibuja línea roja entre extremos y punto medio azul.
    
    linea debe contener: {p1, p2, punto_medio, centros_ordenados}
    """
    import cv2
    
    p1 = linea['p1']
    p2 = linea['p2']
    punto_medio = linea['punto_medio']
    centros = linea.get('centros_ordenados', [])
    
    # Línea roja entre extremos
    cv2.line(frame, tuple(p1), tuple(p2), (0, 0, 255), 2)
    
    # Punto medio azul
    cv2.circle(frame, tuple(punto_medio), 5, (255, 0, 0), -1)
    
    # Puntos verdes en todos los centros
    for centro in centros:
        cv2.circle(frame, tuple(centro), 3, (0, 255, 0), -1)
    
    return frame


def _dibujar_muescas(frame, muescas):
    """
    Dibuja círculos rojos en posiciones de muescas.
    
    muescas: lista de {x_px, y_px, radio_px}
    """
    import cv2
    
    for muesca in muescas:
        x = int(muesca['x_px'])
        y = int(muesca['y_px'])
        radio = int(muesca['radio_px'])
        
        # Círculo rojo relleno
        cv2.circle(frame, (x, y), radio, (0, 0, 255), -1)
        # Borde más oscuro
        cv2.circle(frame, (x, y), radio, (0, 0, 200), 1)
    
    return frame
```

---

## 🔄 FLUJO DE EJECUCIÓN VISUAL

```
Usuario presiona "Analizar"
    ↓
POST /api/analyze
    ↓
pipeline_analisis.analizar_con_reintentos(frame, max_intentos=3)
    ↓
    ┌─────────────────────────────────────┐
    │  Loop: Intento 1, 2, 3              │
    │                                     │
    │  analizar_frame_completo(frame)    │
    │      ↓                              │
    │  1. detectar_aruco(frame)          │
    │  2. detectar_junta(frame)          │
    │  3. detectar_agujeros(frame, junta)│
    │  4. calcular_metricas(agujeros)    │
    │  5. validar_todo(agujeros, aruco)  │
    │      ↓                              │
    │  ¿Validaciones OK?                 │
    │      ↓ SI                           │
    │  6. visualizador.dibujar_todo()    │
    │  7. Codificar JPEG                 │
    │      ↓                              │
    │  Return (True, imagen, datos)      │
    │                                     │
    │  ¿Validaciones OK?                 │
    │      ↓ NO                           │
    │  Return (False, None, None)        │
    │  Continuar loop (siguiente intento)│
    └─────────────────────────────────────┘
    ↓
Si algún intento fue exitoso:
    → Retornar imagen + datos al frontend
    → Frontend muestra imagen y envía ANALYSIS_SUCCESS

Si todos los intentos fallaron:
    → Retornar error al frontend
    → Frontend muestra ANALYSIS_FAILED
```

---

## ✅ MAPEO COMPLETO - Pipeline Actual vs Nuevo

### **Funcionalidades del Pipeline Actual:**

| # | Funcionalidad Actual | Archivo Actual | Nueva Ubicación | Estado |
|---|---------------------|----------------|-----------------|--------|
| 1 | Detección ArUco | `aruco_detector.py` | `detectar_aruco()` | ✅ Mapeado |
| 2 | Calibración px/mm | `aruco_detector.py` | Retornado por `detectar_aruco()` | ✅ Mapeado |
| 3 | Detección junta (YOLO) | `yolo_detector.detect_gasket()` | `detectar_junta()` | ✅ Mapeado |
| 4 | Soporte OBB vs bbox | `yolo_detector.detect_gasket()` | `detectar_junta()` | ✅ Mapeado |
| 5 | Crop con padding 10% | `overlay_manager._overlay_holes_detection()` | `detectar_agujeros()` | ✅ Mapeado |
| 6 | Detección YOLO Holes | `yolo_detector.detect_holes_with_contours()` | `detect_holes_bboxes()` (nuevo) | ✅ Mapeado |
| 7 | Refinamiento OpenCV | `yolo_detector.detect_holes_with_contours()` | `calcular_centro_agujero()` (modular) | ✅ Mejorado |
| 8 | Detección azul predominante | Mezclado en `detect_holes_with_contours()` | `calcular_centro_agujero()` | ✅ Mapeado |
| 9 | Ajuste de elipses | Mezclado en `detect_holes_with_contours()` | `calcular_centro_agujero()` | ✅ Mapeado |
| 10 | Ajuste de coordenadas | `overlay_manager._overlay_holes_detection()` | `detectar_agujeros()` | ✅ Mapeado |
| 11 | Cálculo línea referencia | `overlay_manager._overlay_holes_detection()` | `calcular_metricas()` | ✅ Mapeado |
| 12 | Cálculo punto medio | `overlay_manager._overlay_holes_detection()` | `calcular_metricas()` | ✅ Mapeado |
| 13 | Validación centros múltiples | `overlay_manager._validar_centros_multiples()` | `validaciones_geometricas.validar_centros_multiples()` | ✅ Mapeado |
| 14 | Validación colinealidad | `overlay_manager._validar_colinealidad()` | `validaciones_geometricas.validar_colinealidad()` | ✅ Mapeado |
| 15 | Validación espaciado | `overlay_manager._validar_espaciado_uniforme()` | `validaciones_geometricas.validar_espaciado_uniforme()` | ✅ Mapeado |
| 16 | Validar cantidad esperada | `templates/dashboard.html` (validarResultados) | Validación temprana 1 | ✅ Movido a backend |
| 17 | Validar distancia esperada | `templates/dashboard.html` (validarResultados) | Validación temprana 2 | ✅ Movido a backend |
| 18 | Cálculo muescas | `overlay_manager._overlay_holes_detection()` | `calcular_posiciones_muescas()` | ✅ Mapeado |
| 19 | Conversión mm→px muescas | Mezclado en overlay | `calcular_posiciones_muescas()` | ✅ Mapeado |
| 20 | Rotación coordenadas | Mezclado en overlay | `calcular_posiciones_muescas()` | ✅ Mapeado |
| 21 | Dibujar ejes ArUco | `overlay_manager._overlay_aruco_reference()` | `visualizador._dibujar_aruco()` | ✅ Mapeado |
| 22 | Dibujar bbox junta | `overlay_manager._overlay_holes_detection()` | `visualizador._dibujar_bbox_junta()` | ✅ Mapeado |
| 23 | Dibujar contornos agujeros | `overlay_manager._overlay_holes_detection()` | `visualizador._dibujar_agujeros()` | ✅ Mapeado |
| 24 | Dibujar elipses | `overlay_manager._overlay_holes_detection()` | `visualizador._dibujar_agujeros()` | ✅ Mapeado |
| 25 | Dibujar línea roja | `overlay_manager._overlay_holes_detection()` | `visualizador._dibujar_linea_referencia()` | ✅ Mapeado |
| 26 | Dibujar punto medio | `overlay_manager._overlay_holes_detection()` | `visualizador._dibujar_linea_referencia()` | ✅ Mapeado |
| 27 | Dibujar muescas | `overlay_manager._overlay_holes_detection()` | `visualizador._dibujar_muescas()` | ✅ Mapeado |
| 28 | Convertir a escala grises | `overlay_manager.apply_overlays()` | `visualizador.dibujar_todo()` | ✅ Mapeado |
| 29 | Sistema de reintentos (3x) | `templates/dashboard.html` | `analizar_con_reintentos()` | ✅ Movido a backend |
| 30 | Actualización tabla progresiva | `templates/control.html` | `callback_progreso()` | ✅ Mejorado |
| 31 | Conversión NumPy→JSON | `illinois-server.py` (convert_numpy_types) | Parte del retorno | ✅ Mapeado |
| 32 | Cache de detecciones | `overlay_manager._analysis_data['_detections_cache']` | ❌ Eliminado | ✅ Ya no necesario |
| 33 | Doble pasada (análisis/dibujo) | `overlay_manager.apply_overlays()` | ❌ Eliminado | ✅ Una sola pasada |
| 34 | Flags `should_draw` | `overlay_manager` | ❌ Eliminado | ✅ Ya no necesario |
| 35 | Registro de overlays | `overlay_manager.register_overlay()` | ❌ Eliminado | ✅ Ya no necesario |

### **🎯 Resumen:**
- **35 funcionalidades** identificadas en el pipeline actual
- **31 mapeadas** al nuevo diseño (89%)
- **4 eliminadas** (cachés, doble pasada, flags) porque ya no son necesarias
- **0 funcionalidades perdidas** - TODO lo útil está mapeado

---

### **🆕 Mejoras en el Nuevo Diseño:**

| Mejora | Beneficio |
|--------|-----------|
| **Validaciones tempranas** | Ahorra recursos, reintentos más rápidos |
| **Actualización progresiva** | Usuario ve avance en tiempo real |
| **Función modular OpenCV** | `calcular_centro_agujero()` reutilizable |
| **Objeto acumulador** | Menos parámetros, más claro |
| **Overlay para debug** | Se dibuja incluso en fallos (sin muescas) |
| **Muescas solo en éxito** | Indicador visual claro de análisis completo |
| **Sin cachés ni flags** | Código más simple y mantenible |

---

## 📝 PRÓXIMOS PASOS

1. ✅ **Diseño completo** ← Estamos aquí
2. ⏳ **Aprobación final del diseño** ← Validar con usuario
3. ⏳ **Implementar código**
4. ⏳ **Probar nuevo pipeline**
5. ⏳ **Eliminar código viejo**

---

## ❓ VALIDACIÓN FINAL

**¿Falta algo del pipeline actual que NO esté en esta tabla?**
- Revisé `overlay_manager.py`, `yolo_detector.py`, `aruco_detector.py`, `camera_manager.py`
- Revisé validaciones en `dashboard.html` y actualización de tabla en `control.html`
- Revisé cálculo de muescas y textos

**TODO está mapeado.** ¿Procedemos a escribir el código? 🚀


