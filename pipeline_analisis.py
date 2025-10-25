# pipeline_analisis.py
"""
Pipeline de Análisis - COMAU-VISION
====================================

Orquestador principal del análisis de juntas en tiempo real.

Filosofía:
- Funciones simples, cada una hace UNA sola cosa
- Validaciones tempranas (early returns) para ahorrar recursos
- Actualización progresiva de resultados al frontend
- Sin estado global, sin cachés, sin flags complejos
- Fácil de testear y mantener

Pipeline completo:
1. Detectar ArUco → Calibración px/mm
2. Detectar junta → Bounding box
3. Detectar agujeros (YOLO) → Validar cantidad (early return)
4. Refinar centros (OpenCV) → Ejecuta N veces
5. Calcular métricas → Validar distancia (early return)
6. Validaciones geométricas → Continúa (genera overlay para debug)
7. Calcular muescas → Solo si TODO pasó
8. Dibujar overlay → Siempre (con o sin muescas)
9. Retornar resultado
"""

import os
import sys
from pathlib import Path

# Agregar src al path de Python (mismo que en illinois-server.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import cv2
import numpy as np
import json

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None
    OPENCV_AVAILABLE = False


# ============================================================
# FUNCIÓN PRINCIPAL - REINTENTOS
# ============================================================

def analizar_con_reintentos(frame, max_intentos=3):
    """
    Intenta analizar un frame hasta obtener un resultado válido.
    
    Estrategia:
    - Loop de 1 a max_intentos
    - Si algún intento es exitoso → retorna imagen con overlay y datos
    - Si todos fallan → retorna None (sin imagen), solo datos para tabla
    
    Args:
        frame: Imagen RGB de OpenCV
        max_intentos: Número máximo de intentos (default: 3)
    
    Returns:
        (exito: bool, imagen_procesada: bytes|None, datos: dict)
        - exito: True si pasó todas las validaciones
        - imagen_procesada: JPEG bytes si exitoso, None si falló
        - datos: Diccionario con resultados del análisis
    """
    
    print(f"[pipeline] ═══════════════════════════════════════════════════════")
    print(f"[pipeline] Iniciando análisis con reintentos (máx: {max_intentos})")
    print(f"[pipeline] ═══════════════════════════════════════════════════════")
    
    ultimos_datos = None
    
    for intento in range(1, max_intentos + 1):
        print(f"\n[pipeline] ─────────────────────────────────────────────────")
        print(f"[pipeline] 🔄 INTENTO {intento}/{max_intentos}")
        print(f"[pipeline] ─────────────────────────────────────────────────")
        
        exito, imagen, datos = analizar_frame_completo(frame)
        
        # SIEMPRE guardar datos (para mostrar en tabla, incluso si falla)
        ultimos_datos = datos
        
        if exito:
            print(f"[pipeline] ✅ ANÁLISIS EXITOSO en intento {intento}")
            print(f"[pipeline] ═══════════════════════════════════════════════════════")
            return True, imagen, datos
        
        print(f"[pipeline] ❌ Intento {intento} falló: {datos.get('error', 'Error desconocido')}")
    
    # Todos los intentos fallaron - NO devolver imagen
    print(f"\n[pipeline] ═══════════════════════════════════════════════════════")
    print(f"[pipeline] ❌ ANÁLISIS FALLIDO después de {max_intentos} intentos")
    print(f"[pipeline] → Sin imagen (solo datos para tabla)")
    print(f"[pipeline] ═══════════════════════════════════════════════════════")
    
    return False, None, ultimos_datos


# ============================================================
# FUNCIÓN PRINCIPAL - ANÁLISIS COMPLETO
# ============================================================

def analizar_frame_completo(frame):
    """
    Ejecuta el pipeline completo de análisis en un frame.
    
    VALIDACIONES TEMPRANAS (Early Returns):
    - ArUco no detectado → Return inmediato
    - Junta no detectada → Return inmediato
    - Cantidad pistones incorrecta → Return inmediato (ahorra OpenCV)
    - Distancia fuera de tolerancia → Return inmediato (ahorra validaciones geométricas)
    
    VALIDACIONES FINALES (Sin Early Return):
    - Validaciones geométricas → Continúa, genera overlay para debug visual
    
    Args:
        frame: Imagen RGB de OpenCV
    
    Returns:
        (exito: bool, imagen_procesada: bytes, datos: dict)
    """
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 0: Inicialización
    # ═══════════════════════════════════════════════════════════════════
    
    # Crear objeto acumulador para visualización
    # Este diccionario se llena con TODOS los datos del análisis
    # La decisión de QUÉ dibujar la toma visualizador.py
    datos_visualizacion = {
        'aruco': None,
        'junta': None,
        'agujeros': [],
        'linea_referencia': None,
        'muescas': []  # Solo se llena si TODO pasa
    }
    
    # Cargar junta seleccionada (necesaria para validaciones)
    junta_esperada = _cargar_junta_seleccionada()
    if junta_esperada is None:
        print("[pipeline] ❌ No hay junta seleccionada")
        return False, None, {'error': 'No hay junta seleccionada'}
    
    print(f"[pipeline] Junta seleccionada: {junta_esperada['nombre']}")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 1: Detectar ArUco (calibración)
    # ═══════════════════════════════════════════════════════════════════
    
    datos_aruco = detectar_aruco(frame)
    
    if datos_aruco is None:
        print("[pipeline] ❌ ArUco no detectado")
        return False, None, {'error': 'No se detectó ArUco'}
    
    datos_visualizacion['aruco'] = datos_aruco
    print(f"[pipeline] ✓ ArUco detectado: ID={datos_aruco['id']}, px_per_mm={datos_aruco['px_per_mm']:.3f}")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 1.5: Detectar Tool ArUco también
    # ═══════════════════════════════════════════════════════════════════
    
    # Cargar configuración para obtener Tool ArUco
    config = _cargar_config()
    aruco_config = config.get('aruco', {})
    tool_aruco_id = aruco_config.get('tool_aruco_id')
    tool_marker_size_mm = aruco_config.get('tool_marker_size_mm', 50.0)
    
    tool_result = None
    if tool_aruco_id:
        # TODO: Actualizar para usar parámetros explícitos de la librería genérica
        # from lib.aruco import detect_aruco_by_id
        # tool_result = detect_aruco_by_id(frame, tool_aruco_id, dictionary_id, marker_bits, marker_size_mm)
        # if tool_result:
        #     print(f"[pipeline] ✓ Tool ArUco detectado: ID={tool_result['id']}, px_per_mm={tool_result['px_per_mm']:.3f}")
        #     datos_aruco['tool_result'] = tool_result
        print(f"[pipeline] ⚠️ Detección de Tool ArUco temporalmente deshabilitada - requiere parámetros explícitos")
    else:
        print(f"[pipeline] ⚠️ Tool ArUco no detectado (ID: {tool_aruco_id})")
    
    # ═══════════════════════════════════════════════════════════════════
    # CORRECCIÓN DE IMAGEN (Perspectiva según configuración)
    # ═══════════════════════════════════════════════════════════════════
    
    # Verificar si corrección de perspectiva está habilitada
    config = _cargar_config()
    correct_perspective = config.get('aruco', {}).get('correct_perspective', False)
    
    frame_corregido = frame
    transform_matrix = None
    px_per_mm_corregido = datos_aruco.get('px_per_mm', 1.0)
    
    # Aplicar correcciones según configuración
    if correct_perspective:
        print(f"[pipeline] 🔧 Aplicando corrección de perspectiva ArUco")
        frame_corregido, transform_matrix, px_per_mm_corregido = corregir_perspectiva(frame_corregido, datos_aruco)
        print(f"[pipeline] ✓ Corrección de perspectiva aplicada (px_per_mm: {px_per_mm_corregido:.3f})")
    else:
        print(f"[pipeline] 🔧 Corrección de perspectiva deshabilitada (usando px_per_mm original)")
    
    # Actualizar datos del ArUco
    datos_aruco_corregido = datos_aruco.copy()
    if correct_perspective:
        datos_aruco_corregido['px_per_mm'] = px_per_mm_corregido
        datos_aruco_corregido['perspective_corrected'] = True
    
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 2: Detectar junta (bounding box) EN FRAME CORREGIDO
    # ═══════════════════════════════════════════════════════════════════
    
    print(f"[pipeline] 🔍 Detectando junta en frame corregido: {frame_corregido.shape}")
    datos_junta = detectar_junta(frame_corregido)
    
    # Si no se detecta en frame corregido, intentar en frame original
    if datos_junta is None:
        print(f"[pipeline] ⚠️ Junta no detectada en frame corregido, intentando frame original")
        datos_junta = detectar_junta(frame)
        if datos_junta is not None:
            print(f"[pipeline] ✓ Junta detectada en frame original (usando frame original para detección)")
            # Usar frame original para detecciones pero mantener corrección para mediciones
            frame_para_deteccion = frame
        else:
            frame_para_deteccion = frame_corregido
    else:
        print(f"[pipeline] ✓ Junta detectada en frame corregido")
        frame_para_deteccion = frame_corregido
    
    if datos_junta is None:
        print("[pipeline] ❌ Junta no detectada")
        return False, None, {'error': 'No se detectó junta'}
    
    datos_visualizacion['junta'] = datos_junta
    print(f"[pipeline] ✓ Junta detectada: tipo={datos_junta['tipo']}, bbox={datos_junta['bbox']}")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 3: Detectar agujeros con YOLO (solo bboxes)
    # ═══════════════════════════════════════════════════════════════════
    
    print(f"[pipeline] 🔍 Detectando agujeros en frame: {frame_para_deteccion.shape}")
    datos_agujeros = detectar_agujeros(frame_para_deteccion, datos_junta)
    
    if not datos_agujeros or len(datos_agujeros) == 0:
        print("[pipeline] ❌ No se detectaron agujeros")
        return False, None, {'error': 'No se detectaron agujeros'}
    
    # ╔═══════════════════════════════════════════════════════════════╗
    # ║ ⚡ VALIDACIÓN TEMPRANA 1: CANTIDAD DE PISTONES               ║
    # ╚═══════════════════════════════════════════════════════════════╝
    
    cantidad_detectada = len(datos_agujeros)
    cantidad_esperada = junta_esperada.get('resumen_analisis', {}).get('redondos_grandes', 0)
    
    print(f"[pipeline] Pistones: detectados={cantidad_detectada}, esperados={cantidad_esperada}")
    
    if cantidad_detectada != cantidad_esperada:
        print(f"[pipeline] ❌ VALIDACIÓN TEMPRANA 1 FALLÓ: Cantidad incorrecta")
        print(f"[pipeline] → Return inmediato (no ejecutar OpenCV para ahorrar recursos)")
        
        # Retornar datos parciales (sin imagen, para reintento rápido)
        datos_parciales = {
            'aruco': {
                'detected': True,
                'px_per_mm': datos_aruco['px_per_mm'],
                'center': datos_aruco['center']
            },
            'holes': {
                'total_detected': cantidad_detectada,
                'distancia_extremos_mm': None
            },
            'validacion_temprana': 'cantidad_pistones',
            'error': f'Cantidad incorrecta: esperado {cantidad_esperada}, obtenido {cantidad_detectada}'
        }
        
        return False, None, datos_parciales
    
    print(f"[pipeline] ✓ VALIDACIÓN TEMPRANA 1 PASADA: Cantidad correcta")
    
    # Si llegamos aquí, la cantidad es correcta
    # Ahora SÍ vale la pena refinar con OpenCV
    datos_visualizacion['agujeros'] = datos_agujeros
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 4: Calcular métricas (línea de referencia, distancias)
    # ═══════════════════════════════════════════════════════════════════
    
    metricas = calcular_metricas(datos_agujeros, datos_aruco_corregido)
    datos_visualizacion['linea_referencia'] = metricas
    
    print(f"[pipeline] ✓ Métricas calculadas: distancia={metricas.get('distancia_mm')}mm")
    
    # ═══════════════════════════════════════════════════════════════════
    # DEBUG: Análisis de consistencia de medición
    # ═══════════════════════════════════════════════════════════════════
    if metricas.get('distancia_px') and metricas.get('distancia_mm'):
        distancia_px = metricas['distancia_px']
        distancia_mm = metricas['distancia_mm']
        px_per_mm_calculado = distancia_px / distancia_mm if distancia_mm > 0 else 0
        px_per_mm_aruco = datos_aruco.get('px_per_mm', 0)
        
        diferencia_ratio = abs(px_per_mm_calculado - px_per_mm_aruco) / px_per_mm_aruco if px_per_mm_aruco > 0 else 0
        
        print(f"[pipeline] 🔍 DEBUG Consistencia:")
        print(f"[pipeline]    Distancia: {distancia_px:.1f}px = {distancia_mm:.1f}mm")
        print(f"[pipeline]    px_per_mm ArUco: {px_per_mm_aruco:.3f}")
        print(f"[pipeline]    px_per_mm calculado: {px_per_mm_calculado:.3f}")
        print(f"[pipeline]    Diferencia: {diferencia_ratio:.1%}")
        
        if diferencia_ratio > 0.05:  # Más de 5% de diferencia
            print(f"[pipeline] ⚠️  ADVERTENCIA: Inconsistencia en px_per_mm detectada!")
            print(f"[pipeline]    Esto puede indicar deformación en la imagen")
    
    # ╔═══════════════════════════════════════════════════════════════╗
    # ║ ⚡ VALIDACIÓN TEMPRANA 2: DISTANCIA EXTREMOS                 ║
    # ╚═══════════════════════════════════════════════════════════════╝
    
    distancia_obtenida_mm = metricas.get('distancia_mm')
    
    # Cargar distancia esperada del análisis de la junta
    analisis_junta = _cargar_analisis_junta(junta_esperada['nombre'])
    distancia_esperada_mm = analisis_junta.get('linea_referencia', {}).get('distancia_mm', 0)
    
    # Cargar umbral de tolerancia
    from vision.camera_manager import load_config
    config = load_config()
    umbral_distancia_tol = config.get('vision', {}).get('umbral_distancia_tolerancia', 98.0)
    
    if distancia_obtenida_mm and distancia_esperada_mm:
        # Calcular porcentaje de acierto
        diferencia_porcentual = abs((distancia_obtenida_mm - distancia_esperada_mm) / distancia_esperada_mm * 100)
        acierto_distancia = 100 - diferencia_porcentual
        
        print(f"[pipeline] Distancia: obtenida={distancia_obtenida_mm:.1f}mm, esperada={distancia_esperada_mm:.1f}mm")
        print(f"[pipeline] Acierto: {acierto_distancia:.1f}% (umbral: {umbral_distancia_tol}%)")
        
        if acierto_distancia < umbral_distancia_tol:
            print(f"[pipeline] ❌ VALIDACIÓN TEMPRANA 2 FALLÓ: Distancia fuera de tolerancia")
            print(f"[pipeline] → Return inmediato (no ejecutar validaciones geométricas)")
            
            # Retornar datos parciales (sin imagen, para reintento rápido)
            datos_parciales = {
                'aruco': {
                    'detected': True,
                    'px_per_mm': datos_aruco['px_per_mm'],
                    'center': datos_aruco['center']
                },
                'holes': {
                    'total_detected': cantidad_detectada,
                    'distancia_extremos_px': metricas['distancia_px'],
                    'distancia_extremos_mm': distancia_obtenida_mm,
                    'punto1': metricas['p1'],
                    'punto2': metricas['p2'],
                    'punto_medio': metricas['punto_medio']
                },
                'validacion_temprana': 'distancia_extremos',
                'error': f'Distancia fuera de tolerancia: {acierto_distancia:.1f}% (requerido {umbral_distancia_tol}%)'
            }
            
            return False, None, datos_parciales
    
    print(f"[pipeline] ✓ VALIDACIÓN TEMPRANA 2 PASADA: Distancia dentro de tolerancia")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 5: Validaciones geométricas
    # ═══════════════════════════════════════════════════════════════════
    # ⚠️  IMPORTANTE: Esta validación NO hace early return
    # Si falla, igual genera overlay (sin muescas) para debug visual
    
    import validaciones_geometricas
    resultados_validacion = validaciones_geometricas.validar_todo(datos_agujeros, datos_aruco, metricas)
    
    analisis_exitoso = resultados_validacion.get('todas_ok', False)
    
    if analisis_exitoso:
        print(f"[pipeline] ✓ VALIDACIONES GEOMÉTRICAS PASADAS")
        
        # ═══════════════════════════════════════════════════════════════
        # USAR CENTRO PROBABILÍSTICO DE LAS VALIDACIONES
        # ═══════════════════════════════════════════════════════════════
        # Si las validaciones pasaron, usar el centro probabilístico más preciso
        val_centros = resultados_validacion.get('centros_multiples', {})
        if val_centros.get('ok') and 'centro_probabilistico' in val_centros:
            centro_prob = val_centros['centro_probabilistico']
            punto_medio = (int(centro_prob[0]), int(centro_prob[1]))
            print(f"[pipeline] ✓ Usando centro probabilístico de validaciones: {punto_medio}")
        else:
            print(f"[pipeline] ⚠️ Usando centroide simple (validaciones no disponibles)")
    else:
        print(f"[pipeline] ⚠️ VALIDACIONES GEOMÉTRICAS FALLARON")
        print(f"[pipeline] → Continuando para generar overlay de debug (sin muescas)")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 6: Calcular muescas SOLO SI TODO PASÓ
    # ═══════════════════════════════════════════════════════════════════
    
    if analisis_exitoso:
        muescas = calcular_posiciones_muescas(metricas, datos_aruco_corregido)
        datos_visualizacion['muescas'] = muescas
        print(f"[pipeline] ✓ Muescas calculadas: {len(muescas)}")
        
        # ═══════════════════════════════════════════════════════════════════
        # CALCULAR OFFSET VECTOR (ArUco → Primera Muesca)
        # ═══════════════════════════════════════════════════════════════════
        if len(muescas) > 0:
            offset_vector = calcular_offset_vector(datos_aruco_corregido, muescas[0])
            datos_visualizacion['offset_vector'] = offset_vector
            print(f"[pipeline] ✓ Offset vector calculado: X={offset_vector['x_mm']:.2f}mm, Y={offset_vector['y_mm']:.2f}mm, Módulo={offset_vector['modulo_mm']:.2f}mm")
            
            # ═══════════════════════════════════════════════════════════════════
            # CALCULAR COORDENADAS RESPECTO AL TOOL (NUEVA FUNCIONALIDAD)
            # ═══════════════════════════════════════════════════════════════════
            coords_tool = calcular_coords_primera_muesca_respecto_tool(datos_aruco_corregido, muescas[0])
            if coords_tool:
                datos_visualizacion['coords_tool'] = coords_tool
                print(f"[pipeline] ✓ Coordenadas Tool calculadas: X={coords_tool['x_mm']:.2f}mm, Y={coords_tool['y_mm']:.2f}mm")
    else:
        # NO calcular muescas si hay fallas
        datos_visualizacion['muescas'] = []
        datos_visualizacion['offset_vector'] = None
        print(f"[pipeline] ✗ Muescas omitidas (análisis no exitoso)")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 7: Dibujar overlay y codificar SOLO SI ES EXITOSO
    # ═══════════════════════════════════════════════════════════════════
    # ⚠️  Solo generar imagen si el análisis fue exitoso
    
    if analisis_exitoso:
        import visualizador
        # Usar frame original para overlay (mantener perspectiva original para visualización)
        imagen_con_overlays = visualizador.dibujar_todo(frame, datos_visualizacion)
        print(f"[pipeline] ✓ Overlay dibujado (análisis exitoso)")
        
        # Codificar imagen a JPEG
        _, buffer = cv2.imencode('.jpg', imagen_con_overlays, [cv2.IMWRITE_JPEG_QUALITY, 95])
        imagen_bytes = buffer.tobytes()
    else:
        # No generar imagen si el análisis falló
        imagen_bytes = None
        print(f"[pipeline] ✗ Sin imagen (análisis falló)")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 9: Preparar datos completos de salida
    # ═══════════════════════════════════════════════════════════════════
    
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
    
    # Agregar datos de visualización si existen
    if datos_visualizacion.get('offset_vector'):
        datos_completos['offset_vector'] = datos_visualizacion['offset_vector']
    
    if datos_visualizacion.get('coords_tool'):
        datos_completos['coords_tool'] = datos_visualizacion['coords_tool']
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 10: Retornar resultado
    # ═══════════════════════════════════════════════════════════════════
    # SIEMPRE retorna imagen (incluso si falló) para debug visual
    
    if analisis_exitoso:
        print(f"[pipeline] ✓ Retornando resultado EXITOSO (con muescas)")
        return True, imagen_bytes, datos_completos
    else:
        # Agregar mensaje de error específico
        datos_completos['error'] = 'Validaciones geométricas fallaron'
        print(f"[pipeline] ✗ Retornando resultado FALLIDO (sin muescas, para debug)")
        return False, imagen_bytes, datos_completos


# ============================================================
# FUNCIONES DE DETECCIÓN
# ============================================================

def detectar_aruco(frame):
    """
    Detecta el marcador ArUco Frame (calibración) y calcula px_per_mm.
    
    MODOS DE OPERACIÓN:
    1. Usar referencia guardada (si use_saved_reference=True)
    2. Detectar en tiempo real (si use_saved_reference=False o no hay guardado)
    
    Args:
        frame: Imagen RGB de OpenCV
    
    Returns:
        dict: {
            'id': int,
            'center': (x, y),
            'px_per_mm': float,
            'angle_rad': float,
            'corners': [[x,y], ...],
            'source': 'saved' | 'detected'
        }
        o None si no se detecta
    """
    
    from lib.aruco import detect_aruco_by_id
    from vision.camera_manager import load_config
    import json

    # Cargar configuración de ArUco
    config = load_config()
    aruco_config = config.get('aruco', {})
    
    use_saved_reference = aruco_config.get('use_saved_reference', False)
    saved_frame_reference = aruco_config.get('saved_frame_reference')
    
    # ═══════════════════════════════════════════════════════════════════
    # MODO 1: Usar referencia guardada del FRAME
    # ═══════════════════════════════════════════════════════════════════
    if use_saved_reference and saved_frame_reference:
        print("[pipeline] 📌 Usando ArUco_Frame de referencia GUARDADA (no se detecta en tiempo real)")
        
        # Obtener marker_size_mm del config para validaciones posteriores
        marker_size_mm = aruco_config.get('frame_marker_size_mm', 70.0)
        
        # Verificar que tenga todos los datos necesarios
        if all(k in saved_frame_reference for k in ['px_per_mm', 'center', 'angle_rad', 'corners']):
            return {
                'id': aruco_config.get('frame_aruco_id', 0),
                'center': saved_frame_reference['center'],
                'px_per_mm': saved_frame_reference['px_per_mm'],
                'marker_size_mm': marker_size_mm,  # Incluir tamaño para validaciones posteriores
                'angle_rad': saved_frame_reference['angle_rad'],
                'corners': saved_frame_reference['corners'],
                'source': 'saved',  # Indica que viene de memoria
                'timestamp': saved_frame_reference.get('timestamp')
            }
        else:
            print("[pipeline] ⚠️ Referencia Frame guardada incompleta, detectando en tiempo real...")
    
    # ═══════════════════════════════════════════════════════════════════
    # MODO 2: Detectar Frame ArUco en tiempo real
    # ═══════════════════════════════════════════════════════════════════
    print("[pipeline] 🔍 Detectando ArUco_Frame en tiempo real...")
    
    frame_aruco_id = aruco_config.get('frame_aruco_id', 23)  # Usar frame_aruco_id
    marker_size_mm = aruco_config.get('frame_marker_size_mm', 70.0)  # Usar frame_marker_size_mm
    dictionary_id = aruco_config.get('dictionary_id', 50)
    
    # Detectar ArUco del Frame
    deteccion = detect_aruco_by_id(
        frame,
        frame_aruco_id,
        dictionary_id,
        marker_size_mm
    )
    
    if deteccion is None:
        return None
    
    # Calcular ángulo de rotación del ArUco
    corners = np.array(deteccion['corners'])
    dx = corners[1][0] - corners[0][0]
    dy = corners[1][1] - corners[0][1]
    angle_rad = np.arctan2(dy, dx)
    
    return {
        'id': deteccion['id'],
        'center': deteccion['center'],
        'px_per_mm': deteccion['px_per_mm'],
        'marker_size_mm': marker_size_mm,  # Incluir tamaño para validaciones posteriores
        'angle_rad': angle_rad,
        'corners': deteccion['corners'],
        'source': 'detected'  # Indica que fue detectado en tiempo real
    }


def detectar_junta(frame):
    """
    Detecta la junta completa usando YOLO Detection Model.
    Soporta tanto YOLO normal (bbox) como YOLO-OBB (rotado).
    
    Args:
        frame: Imagen RGB de OpenCV
    
    Returns:
        dict: {
            'bbox': (x1, y1, x2, y2),
            'tipo': 'obb' | 'rect',
            ... otros campos según tipo
        }
        o None si no se detecta
    """
    
    from vision import yolo_detector
    
    resultado = yolo_detector.detect_gasket(frame, conf_threshold=0.5)
    
    if resultado is None:
        return None
    
    # Procesar según tipo de detección
    if isinstance(resultado, dict) and resultado.get('type') == 'obb':
        # YOLO-OBB: Rectángulo rotado
        return {
            'bbox': resultado['bbox'],  # (x1, y1, x2, y2) alineado a ejes
            'tipo': 'obb',
            'center': resultado['center'],
            'size': resultado['size'],
            'angle': resultado['angle'],
            'points': resultado['points']
        }
    else:
        # YOLO normal: Bounding box recto
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
    
    SECUENCIA DE 3 ETAPAS:
    1. YOLO Detection detectó la junta → datos_junta
    2. YOLO Holes detecta agujeros → bboxes
    3. OpenCV refina cada agujero → centros precisos
    
    Args:
        frame: Imagen RGB de OpenCV
        datos_junta: Datos de la junta detectada
    
    Returns:
        list: [{'center': (x, y), 'contour': contour, 'ellipse': ellipse}, ...]
    """
    
    from vision import yolo_detector
    
    # ═══════════════════════════════════════════════════════════════════
    # ETAPA 1: Preparar crop de junta con padding 10%
    # ═══════════════════════════════════════════════════════════════════
    
    x1, y1, x2, y2 = datos_junta['bbox']
    box_w = x2 - x1
    box_h = y2 - y1
    padding_w = int(box_w * 0.10)
    padding_h = int(box_h * 0.10)
    
    # Calcular coordenadas con padding (respetando límites del frame)
    frame_h, frame_w = frame.shape[:2]
    final_x1 = max(0, x1 - padding_w)
    final_y1 = max(0, y1 - padding_h)
    final_x2 = min(frame_w, x2 + padding_w)
    final_y2 = min(frame_h, y2 + padding_h)
    
    # Recortar área de junta
    cropped_frame = frame[final_y1:final_y2, final_x1:final_x2]
    
    print(f"[pipeline] Crop de junta: ({final_x1}, {final_y1}) → ({final_x2}, {final_y2}), tamaño: {final_x2-final_x1}x{final_y2-final_y1}")
    
    # ═══════════════════════════════════════════════════════════════════
    # ETAPA 2: YOLO Holes detecta agujeros (solo bboxes)
    # ═══════════════════════════════════════════════════════════════════
    
    detecciones_yolo = yolo_detector.detect_holes_bboxes(cropped_frame, conf_threshold=0.5)
    
    if not detecciones_yolo:
        print("[pipeline] ❌ YOLO Holes no detectó agujeros")
        return []
    
    print(f"[pipeline] ✓ YOLO Holes detectó {len(detecciones_yolo)} agujeros (bboxes)")
    
    # ═══════════════════════════════════════════════════════════════════
    # ETAPA 3: OpenCV refina cada agujero individualmente
    # ═══════════════════════════════════════════════════════════════════
    
    agujeros_refinados = []
    offset_x = final_x1
    offset_y = final_y1
    
    for idx, det_yolo in enumerate(detecciones_yolo):
        # Extraer bbox del agujero (relativo al crop de junta)
        agujero_bbox = det_yolo['bbox']
        ax1, ay1, ax2, ay2 = agujero_bbox
        
        # Recortar área del agujero individual
        crop_agujero = cropped_frame[ay1:ay2, ax1:ax2]
        
        print(f"[pipeline] Procesando agujero {idx+1}/{len(detecciones_yolo)}: bbox={agujero_bbox}, tamaño={ax2-ax1}x{ay2-ay1}")
        
        # Refinar con OpenCV (función modular y reutilizable)
        resultado_opencv = calcular_centro_agujero(crop_agujero)
        
        if resultado_opencv is None:
            print(f"[pipeline] ⚠️ Agujero {idx+1} no pudo ser refinado con OpenCV")
            continue
        
        # Ajustar coordenadas al frame original
        # Coordenadas locales → Coordenadas de bbox agujero → Coordenadas globales
        center_local = resultado_opencv['center']
        contour_local = resultado_opencv['contour']
        ellipse_local = resultado_opencv.get('ellipse')
        
        # Centro global
        center_global = (
            center_local[0] + ax1 + offset_x,
            center_local[1] + ay1 + offset_y
        )
        
        # Contorno global
        contour_global = contour_local + np.array([ax1 + offset_x, ay1 + offset_y])
        
        # Elipse global
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
        
        print(f"[pipeline] ✓ Agujero {idx+1} refinado: centro global={center_global}")
    
    print(f"[pipeline] ✓ Total agujeros refinados: {len(agujeros_refinados)}")
    
    return agujeros_refinados


def calcular_centro_agujero(crop_agujero):
    """
    Función MODULAR y REUTILIZABLE para calcular el centro preciso de un agujero.
    
    Recibe el crop de UN solo pistón y aplica OpenCV para refinamiento.
    Se puede llamar N veces (una por cada detección YOLO).
    Se puede testear independientemente.
    
    ESTRATEGIA:
    1. Detectar píxeles donde AZUL es predominante
    2. Crear máscara binaria
    3. Encontrar contornos
    4. Seleccionar contorno de mayor área
    5. Ajustar elipse al contorno
    6. Calcular centro de la elipse
    
    Args:
        crop_agujero: Imagen RGB del agujero recortado (numpy array)
    
    Returns:
        dict: {
            'center': (x, y),
            'contour': contour,
            'ellipse': ellipse_params
        }
        o None si no se puede calcular
    """
    
    if not OPENCV_AVAILABLE or crop_agujero is None or crop_agujero.size == 0:
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


# ============================================================
# FUNCIONES DE CÁLCULO
# ============================================================

def calcular_metricas(datos_agujeros, datos_aruco):
    """
    Calcula métricas básicas: línea de referencia, punto medio, distancias.
    
    Args:
        datos_agujeros: Lista de agujeros detectados
        datos_aruco: Datos de calibración ArUco
    
    Returns:
        dict: {
            'p1': (x, y),
            'p2': (x, y),
            'punto_medio': (x, y),
            'distancia_px': float,
            'distancia_mm': float,
            'angle_rad': float,  ← Ángulo del segmento (para rotación de muescas)
            'centros_ordenados': [...]
        }
    """
    
    # Extraer centros
    centros = [ag['center'] for ag in datos_agujeros]
    
    if len(centros) < 2:
        return {
            'p1': None,
            'p2': None,
            'punto_medio': None,
            'distancia_px': None,
            'distancia_mm': None,
            'angle_rad': None,
            'centros_ordenados': centros
        }
    
    # Ordenar de izquierda a derecha
    centros_ordenados = sorted(centros, key=lambda p: (p[0], p[1]))
    
    # Extremos (para la línea de referencia)
    p1 = centros_ordenados[0]
    p2 = centros_ordenados[-1]
    
    # DEBUG: Mostrar información detallada
    print(f"[DEBUG] Centros originales: {centros}")
    print(f"[DEBUG] Centros ordenados: {centros_ordenados}")
    print(f"[DEBUG] P1 seleccionado (más a la izquierda): {p1}")
    print(f"[DEBUG] P2 seleccionado (más a la derecha): {p2}")
    
    # Calcular punto medio entre extremos
    punto_medio_extremos = (
        int((p1[0] + p2[0]) / 2),
        int((p1[1] + p2[1]) / 2)
    )
    
    # Calcular centroide de todos los centros
    centro_x = sum(p[0] for p in centros) / len(centros)
    centro_y = sum(p[1] for p in centros) / len(centros)
    punto_medio_centroide = (int(centro_x), int(centro_y))
    
    print(f"[DEBUG] Punto medio entre extremos: {punto_medio_extremos}")
    print(f"[DEBUG] Punto medio centroide: {punto_medio_centroide}")
    
    # Usar el centroide de todos los centros (más preciso para agujeros no perfectamente equiespaciados)
    punto_medio = punto_medio_centroide
    
    # Calcular ángulo de rotación del segmento (respecto al eje X horizontal)
    # ⚠️  IMPORTANTE: Este es el ángulo del SEGMENTO, no del ArUco
    angle_rad = np.arctan2(p2[1] - p1[1], p2[0] - p1[0])
    angle_deg = np.degrees(angle_rad)
    
    print(f"[pipeline] Ángulo del segmento: {angle_deg:.2f}° ({angle_rad:.4f} rad)")
    
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
        'distancia_px': round(distancia_px, 1),
        'distancia_mm': round(distancia_mm, 1) if distancia_mm else None,
        'angle_rad': angle_rad,  # ← Ángulo del segmento para rotar muescas
        'centros_ordenados': centros_ordenados
    }


def corregir_perspectiva(frame, datos_aruco):
    """
    Corrige la perspectiva de la imagen usando el ArUco como referencia.
    
    Args:
        frame: Imagen original
        datos_aruco: {'corners', 'px_per_mm', 'marker_size_mm'}
    
    Returns:
        (frame_corregido, matriz_transformacion, px_per_mm_corregido)
    """
    
    if not datos_aruco.get('corners'):
        return frame, None, datos_aruco.get('px_per_mm', 1.0)
    
    corners = np.array(datos_aruco['corners'], dtype=np.float32)
    marker_size_mm = datos_aruco.get('marker_size_mm', 70.0)
    
    # Definir esquinas del ArUco en un cuadrado perfecto (en mm)
    # Orden: esquina superior-izquierda, superior-derecha, inferior-derecha, inferior-izquierda
    size_mm = marker_size_mm
    dst_corners = np.array([
        [0, 0],                    # Superior-izquierda
        [size_mm, 0],             # Superior-derecha  
        [size_mm, size_mm],       # Inferior-derecha
        [0, size_mm]              # Inferior-izquierda
    ], dtype=np.float32)
    
    # Calcular matriz de transformación de perspectiva
    transform_matrix = cv2.getPerspectiveTransform(corners, dst_corners)
    
    # Aplicar corrección de perspectiva
    height, width = frame.shape[:2]
    frame_corregido = cv2.warpPerspective(frame, transform_matrix, (width, height))
    
    # Calcular nuevo px_per_mm (ahora debería ser consistente)
    # En la imagen corregida, el ArUco es un cuadrado perfecto
    px_per_mm_corregido = size_mm / size_mm  # 1.0 px/mm en la imagen corregida
    
    # Pero necesitamos escalar a la resolución original
    # Calcular el factor de escala basado en el tamaño del ArUco corregido
    aruco_corregido_size_px = np.linalg.norm(corners[1] - corners[0])  # Tamaño en píxeles originales
    scale_factor = aruco_corregido_size_px / size_mm
    px_per_mm_corregido = scale_factor
    
    print(f"[pipeline] 🔧 Corrección de perspectiva aplicada:")
    print(f"[pipeline]    px_per_mm original: {datos_aruco.get('px_per_mm', 0):.3f}")
    print(f"[pipeline]    px_per_mm corregido: {px_per_mm_corregido:.3f}")
    
    return frame_corregido, transform_matrix, px_per_mm_corregido


def aplicar_correccion_perspectiva_a_puntos(puntos, transform_matrix):
    """
    Aplica la corrección de perspectiva a una lista de puntos.
    
    Args:
        puntos: Lista de puntos [(x, y), ...]
        transform_matrix: Matriz de transformación de perspectiva
    
    Returns:
        Lista de puntos corregidos
    """
    
    if transform_matrix is None or len(puntos) == 0:
        return puntos
    
    puntos_array = np.array(puntos, dtype=np.float32).reshape(-1, 1, 2)
    puntos_corregidos = cv2.perspectiveTransform(puntos_array, transform_matrix)
    
    return puntos_corregidos.reshape(-1, 2).tolist()


def calcular_offset_vector(datos_aruco, primera_muesca):
    """
    Calcula el vector offset desde el centro del troquel (cruz amarilla) hasta la primera muesca.
    
    Args:
        datos_aruco: {'center', 'px_per_mm'}
        primera_muesca: {'x_px', 'y_px'}
    
    Returns:
        {'x_mm', 'y_mm', 'modulo_mm'}
    """
    
    # Centro del ArUco
    center_aruco = datos_aruco['center']
    px_per_mm = datos_aruco['px_per_mm']
    
    # Cargar configuración del centro del troquel desde config.json
    import json
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        aruco_config = config.get('aruco', {})
        center_x_mm = aruco_config.get('center_x_mm', 0)
        center_y_mm = aruco_config.get('center_y_mm', 0)
        
        # Convertir coordenadas del centro del troquel de mm a píxeles
        center_troquel_x = center_aruco[0] + (center_x_mm * px_per_mm)
        center_troquel_y = center_aruco[1] + (center_y_mm * px_per_mm)
        
        print(f"[pipeline] 📍 Centro del troquel: ({center_troquel_x:.1f}, {center_troquel_y:.1f}) px")
        
    except Exception as e:
        print(f"[pipeline] ⚠️ No se pudo cargar config.json, usando centro del ArUco: {e}")
        # Fallback al centro del ArUco si no se puede cargar la configuración
        center_troquel_x = center_aruco[0]
        center_troquel_y = center_aruco[1]
    
    # Posición de la primera muesca en píxeles
    muesca_x_px = primera_muesca['x_px']
    muesca_y_px = primera_muesca['y_px']
    
    # Calcular diferencia en píxeles (desde centro del troquel hasta primera muesca)
    delta_x_px = muesca_x_px - center_troquel_x
    delta_y_px = muesca_y_px - center_troquel_y
    
    # Convertir a mm
    delta_x_mm = delta_x_px / px_per_mm
    delta_y_mm = delta_y_px / px_per_mm
    
    # Calcular módulo usando Pitágoras
    modulo_mm = (delta_x_mm**2 + delta_y_mm**2)**0.5
    
    print(f"[pipeline] 📐 Vector offset: Centro Troquel → Primera Muesca")
    print(f"[pipeline] 📐 Delta X: {delta_x_mm:.2f}mm, Delta Y: {delta_y_mm:.2f}mm, Módulo: {modulo_mm:.2f}mm")
    
    return {
        'x_mm': delta_x_mm,
        'y_mm': delta_y_mm,
        'modulo_mm': modulo_mm
    }


def calcular_coords_primera_muesca_respecto_tool(datos_aruco, primera_muesca):
    """
    Calcula las coordenadas de la primera muesca respecto al centro del Tool ArUco.
    
    Args:
        datos_aruco: {'center', 'px_per_mm', 'tool_result'}
        primera_muesca: {'x_px', 'y_px'}
    
    Returns:
        {'x_mm', 'y_mm', 'x_px', 'y_px', 'pixel_pos'}
        o None si no hay Tool detectado
    """
    
    # Verificar si hay Tool ArUco detectado
    tool_result = datos_aruco.get('tool_result')
    if tool_result is None:
        print("[pipeline] ⚠️ No hay Tool ArUco detectado para calcular coordenadas")
        return None
    
    # Centro del Tool ArUco
    tool_center = tool_result.get('center')
    if tool_center is None:
        return None
    
    px_per_mm = datos_aruco.get('px_per_mm', 1.0)
    
    # Posición de la primera muesca en píxeles
    muesca_x_px = primera_muesca['x_px']
    muesca_y_px = primera_muesca['y_px']
    
    # Calcular diferencia en píxeles (desde centro del Tool hasta primera muesca)
    delta_x_px = muesca_x_px - tool_center[0]
    delta_y_px = muesca_y_px - tool_center[1]
    
    # Convertir a mm
    delta_x_mm = delta_x_px / px_per_mm
    delta_y_mm = delta_y_px / px_per_mm
    
    print(f"[pipeline] 🔧 Coordenadas primera muesca respecto al Tool:")
    print(f"[pipeline] 🔧 Delta X: {delta_x_mm:.2f}mm, Delta Y: {delta_y_mm:.2f}mm")
    print(f"[pipeline] 🔧 Posición pixel en frame: ({int(muesca_x_px)}, {int(muesca_y_px)})")
    
    return {
        'x_mm': delta_x_mm,
        'y_mm': delta_y_mm,
        'x_px': muesca_x_px,
        'y_px': muesca_y_px,
        'pixel_pos': f"({int(muesca_x_px)}, {int(muesca_y_px)})"
    }


def calcular_posiciones_muescas(metricas, datos_aruco):
    """
    Calcula las posiciones en píxeles de las muescas de la junta seleccionada.
    
    ⚠️  Esta función SOLO se llama si el análisis fue exitoso.
    
    IMPORTANTE: Usa el ángulo del SEGMENTO de pistones, no del ArUco.
    Las muescas se rotan según la orientación de la junta (segmento rojo).
    
    Args:
        metricas: Métricas calculadas (con punto_medio y angle_rad del segmento)
        datos_aruco: Datos de calibración ArUco (con px_per_mm)
    
    Returns:
        list: [{'x_px': float, 'y_px': float, 'radio_px': int}, ...]
        o [] si no hay muescas o no se puede calcular
    """
    
    # Verificar que tengamos los datos necesarios
    if not metricas.get('punto_medio') or not datos_aruco:
        return []
    
    punto_medio = metricas['punto_medio']
    px_per_mm = datos_aruco.get('px_per_mm')
    angle_rad = metricas.get('angle_rad')  # ← Ángulo del SEGMENTO, no del ArUco
    
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
            # Obtener coordenadas en mm (soportar diferentes formatos)
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
            
            # Aplicar rotación según orientación del ArUco
            cos_angle = np.cos(angle_rad)
            sin_angle = np.sin(angle_rad)
            
            x_rotated = offset_x_px * cos_angle - offset_y_px * sin_angle
            y_rotated = offset_x_px * sin_angle + offset_y_px * cos_angle
            
            # Calcular posición absoluta (punto medio + offset rotado)
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


# ============================================================
# FUNCIONES AUXILIARES PRIVADAS
# ============================================================

def _cargar_config():
    """
    Carga la configuración desde config.json.
    
    Returns:
        dict con configuración o {}
    """
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def _cargar_junta_seleccionada():
    """
    Carga la junta seleccionada desde juntas.json.
    
    Returns:
        dict con datos de la junta o None
    """
    
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
    """
    Carga el análisis detallado de una junta desde juntas_analisis/.
    
    Args:
        nombre_junta: Nombre de la junta
    
    Returns:
        dict con datos del análisis o {}
    """
    
    analisis_file = os.path.join('juntas_analisis', f"{nombre_junta}_analisis.json")
    
    if not os.path.exists(analisis_file):
        return {}
    
    try:
        with open(analisis_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[pipeline] Error cargando análisis: {e}")
        return {}

