# visualizador.py
"""
Visualizador de Overlays - COMAU-VISION
========================================

Módulo que se encarga de dibujar todos los overlays sobre la imagen analizada.

Filosofía:
- Recibe un diccionario acumulador con TODOS los datos del análisis
- Consulta los checkboxes de configuración para decidir QUÉ dibujar
- Dibuja todo en UNA sola pasada
- Es la ÚNICA responsable de consultar configuración visual

Overlays que dibuja:
- Ejes y contorno del ArUco de referencia
- Bounding box de la junta
- Contornos de agujeros
- Elipses ajustadas de agujeros
- Línea de referencia (roja) entre extremos
- Punto medio (azul)
- Muescas (círculos rojos) - solo en caso de éxito
"""

import numpy as np
import sys
import os

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None
    OPENCV_AVAILABLE = False

# Agregar src al path si no está
src_path = os.path.join(os.path.dirname(__file__), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from vision import camera_manager


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def dibujar_todo(frame, datos_visualizacion):
    """
    Dibuja todos los overlays en el frame en UNA SOLA PASADA.
    
    IMPORTANTE:
    - El diccionario datos_visualizacion SIEMPRE contiene todos los datos
    - Esta función es la ÚNICA que decide QUÉ dibujar
    - Consulta los checkboxes de configuración (config.json)
    - Dibuja solo los elementos habilitados
    
    Args:
        frame: Imagen RGB original de OpenCV
        datos_visualizacion: Diccionario completo con datos del análisis {
            'aruco': {...},
            'junta': {...},
            'agujeros': [...],
            'linea_referencia': {...},
            'muescas': [...]
        }
    
    Returns:
        Frame con overlays dibujados según configuración
    """
    
    if not OPENCV_AVAILABLE or frame is None:
        return frame
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 1: Convertir a escala de grises para fondo
    # ═══════════════════════════════════════════════════════════════════
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resultado = cv2.cvtColor(frame_gray, cv2.COLOR_GRAY2BGR)
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 2: Cargar configuración (checkboxes de las páginas)
    # ═══════════════════════════════════════════════════════════════════
    config = camera_manager.load_config()
    vision_config = config.get('vision', {})
    aruco_config = config.get('aruco', {})
    
    # Checkboxes de ArUco (página de configuración ArUco)
    show_aruco = aruco_config.get('show_reference', False)
    
    # Chequear si hay un flag para forzar dibujo del ArUco (ej: desde overlay temporal)
    force_draw_aruco = datos_visualizacion.get('_force_draw_aruco', False)
    show_aruco = show_aruco or force_draw_aruco
    
    # Checkboxes de Vision System (página de configuración Vision)
    show_bbox = vision_config.get('show_bbox', False)
    show_contours = vision_config.get('show_contours', True)
    show_ellipses = vision_config.get('show_ellipses', False)
    show_notches = vision_config.get('show_notches', False)
    
    print(f"[visualizador] Configuración: aruco={show_aruco}, bbox={show_bbox}, contours={show_contours}, ellipses={show_ellipses}, notches={show_notches}")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 3: Dibujar ArUco SOLO SI está habilitado
    # ═══════════════════════════════════════════════════════════════════
    if show_aruco and datos_visualizacion.get('aruco'):
        datos_aruco = datos_visualizacion['aruco']
        resultado = _dibujar_aruco(resultado, datos_aruco)
        print("[visualizador] ✓ ArUco dibujado")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 4: Dibujar bbox de junta SOLO SI está habilitado
    # ═══════════════════════════════════════════════════════════════════
    if show_bbox and datos_visualizacion.get('junta'):
        datos_junta = datos_visualizacion['junta']
        resultado = _dibujar_bbox_junta(resultado, datos_junta)
        print("[visualizador] ✓ Bbox junta dibujado")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 5: Dibujar agujeros según configuración
    # ═══════════════════════════════════════════════════════════════════
    if datos_visualizacion.get('agujeros'):
        agujeros = datos_visualizacion['agujeros']
        resultado = _dibujar_agujeros(resultado, agujeros, show_contours, show_ellipses)
        print(f"[visualizador] ✓ Agujeros dibujados (cantidad: {len(agujeros)}, contours={show_contours}, ellipses={show_ellipses})")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 6: Dibujar línea de referencia (SIEMPRE si existe)
    # ═══════════════════════════════════════════════════════════════════
    if datos_visualizacion.get('linea_referencia'):
        linea = datos_visualizacion['linea_referencia']
        resultado = _dibujar_linea_referencia(resultado, linea)
        print("[visualizador] ✓ Línea de referencia dibujada")
    
    # ═══════════════════════════════════════════════════════════════════
    # PASO 7: Dibujar muescas SOLO SI está habilitado Y hay muescas
    # ═══════════════════════════════════════════════════════════════════
    # ⚠️  Las muescas solo se calculan si el análisis fue exitoso
    if show_notches and datos_visualizacion.get('muescas'):
        muescas = datos_visualizacion['muescas']
        if len(muescas) > 0:
            resultado = _dibujar_muescas(resultado, muescas)
            print(f"[visualizador] ✓ Muescas dibujadas (cantidad: {len(muescas)})")
            
            # ═══════════════════════════════════════════════════════════════
            # PASO 8: Dibujar línea azul del troquel a la primera muesca
            # ═══════════════════════════════════════════════════════════════
            if datos_visualizacion.get('aruco') and len(muescas) > 0:
                linea_ref = datos_visualizacion.get('linea_referencia', {})
                resultado = _dibujar_linea_offset(resultado, datos_visualizacion['aruco'], muescas[0], linea_ref)
                print(f"[visualizador] ✓ Línea offset dibujada (troquel → primera muesca)")
        else:
            print("[visualizador] ✗ No hay muescas para dibujar")
    
    return resultado


# ============================================================
# FUNCIONES AUXILIARES PRIVADAS DE DIBUJO
# ============================================================

def _dibujar_aruco(frame, datos_aruco):
    """
    Dibuja ejes de coordenadas, contorno del ArUco y cruz amarilla en centro del troquel.
    
    Args:
        frame: Imagen BGR
        datos_aruco: {'center', 'angle_rad', 'corners'}
    
    Returns:
        Frame con ArUco dibujado
    """
    
    center = tuple(map(int, datos_aruco['center']))
    angle_rad = datos_aruco['angle_rad']
    corners = np.array(datos_aruco['corners'])
    
    # Cargar configuración del ArUco para obtener coordenadas del centro del troquel
    import json
    import os
    
    try:
        # Intentar leer de aruco_config.json primero
        aruco_config = None
        if os.path.exists('aruco_config.json'):
            with open('aruco_config.json', 'r') as f:
                aruco_data = json.load(f)
                aruco_config = aruco_data.get('aruco', {})
        
        # Si no existe, intentar leer de config.json
        if aruco_config is None:
            if os.path.exists('config.json'):
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    aruco_config = config.get('aruco', {})
            else:
                aruco_config = {}
        
        center_x_mm = aruco_config.get('center_x_mm', 0)
        center_y_mm = aruco_config.get('center_y_mm', 0)
        px_per_mm = datos_aruco.get('px_per_mm', 1.0)
        
        # Convertir coordenadas del centro del troquel de mm a píxeles
        center_troquel_x = center[0] + (center_x_mm * px_per_mm)
        center_troquel_y = center[1] + (center_y_mm * px_per_mm)
        center_troquel = (int(center_troquel_x), int(center_troquel_y))
        
        # Dibujar cruz amarilla en el centro del troquel
        cross_size = 20
        cv2.line(frame, 
                 (center_troquel[0] - cross_size, center_troquel[1]), 
                 (center_troquel[0] + cross_size, center_troquel[1]), 
                 (0, 255, 255), 3)  # Línea horizontal amarilla
        cv2.line(frame, 
                 (center_troquel[0], center_troquel[1] - cross_size), 
                 (center_troquel[0], center_troquel[1] + cross_size), 
                 (0, 255, 255), 3)  # Línea vertical amarilla
        
        print(f"[visualizador] ✓ Cruz amarilla dibujada en centro del troquel: {center_troquel} (offset: {center_x_mm}mm, {center_y_mm}mm)")
        
    except Exception as e:
        print(f"[visualizador] ⚠️ No se pudo dibujar cruz del troquel: {e}")
    
    height, width = frame.shape[:2]
    max_length = max(width, height) * 2
    
    # Calcular puntos finales de los ejes rotados
    # Eje X (rojo) - alineado con el lado superior del ArUco
    x_end1 = (
        int(center[0] + max_length * np.cos(angle_rad)),
        int(center[1] + max_length * np.sin(angle_rad))
    )
    x_end2 = (
        int(center[0] - max_length * np.cos(angle_rad)),
        int(center[1] - max_length * np.sin(angle_rad))
    )
    
    # Eje Y (verde) - perpendicular al eje X
    y_angle_rad = angle_rad + np.pi / 2
    y_end1 = (
        int(center[0] + max_length * np.cos(y_angle_rad)),
        int(center[1] + max_length * np.sin(y_angle_rad))
    )
    y_end2 = (
        int(center[0] - max_length * np.cos(y_angle_rad)),
        int(center[1] - max_length * np.sin(y_angle_rad))
    )
    
    # Dibujar ejes
    cv2.line(frame, x_end2, x_end1, (0, 0, 255), 2)  # Eje X rojo
    cv2.line(frame, y_end2, y_end1, (0, 255, 0), 2)  # Eje Y verde
    
    # Dibujar punto central
    cv2.circle(frame, center, 8, (0, 0, 255), -1)
    cv2.circle(frame, center, 6, (255, 255, 255), -1)
    
    # Dibujar contorno del ArUco (cyan)
    corners_int = corners.astype(np.int32)
    cv2.polylines(frame, [corners_int], True, (0, 255, 255), 2)
    
    return frame


def _dibujar_bbox_junta(frame, datos_junta):
    """
    Dibuja bounding box de la junta (verde).
    
    Args:
        frame: Imagen BGR
        datos_junta: {'tipo': 'obb'|'rect', 'bbox' o 'points'}
    
    Returns:
        Frame con bbox dibujado
    """
    
    if datos_junta['tipo'] == 'obb':
        # Dibujar rectángulo rotado (OBB)
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
    
    Args:
        frame: Imagen BGR
        agujeros: Lista de {'center', 'contour', 'ellipse'}
        show_contours: Si se dibujan los contornos
        show_ellipses: Si se dibujan las elipses
    
    Returns:
        Frame con agujeros dibujados
    """
    
    for agujero in agujeros:
        center = tuple(map(int, agujero['center']))
        contour = agujero.get('contour')
        ellipse = agujero.get('ellipse')
        
        # Dibujar contorno (cyan)
        if show_contours and contour is not None:
            cv2.drawContours(frame, [contour.astype(np.int32)], -1, (255, 255, 0), 2)
        
        # Dibujar elipse ajustada (verde)
        if show_ellipses and ellipse is not None:
            cv2.ellipse(frame, ellipse, (0, 255, 0), 2)
        
        # Dibujar centro: punto verde grande + punto rojo pequeño
        cv2.circle(frame, center, 8, (0, 255, 0), -1)  # Verde
        cv2.circle(frame, center, 2, (0, 0, 255), -1)  # Rojo
    
    return frame


def _dibujar_linea_referencia(frame, linea):
    """
    Dibuja línea roja entre extremos, punto medio azul y todos los centros.
    
    Args:
        frame: Imagen BGR
        linea: {'p1', 'p2', 'punto_medio', 'centros_ordenados'}
    
    Returns:
        Frame con línea de referencia dibujada
    """
    
    p1 = linea.get('p1')
    p2 = linea.get('p2')
    punto_medio = linea.get('punto_medio')
    centros = linea.get('centros_ordenados', [])
    
    if not p1 or not p2 or not punto_medio:
        return frame
    
    # Convertir a tuplas de enteros
    p1 = tuple(map(int, p1))
    p2 = tuple(map(int, p2))
    punto_medio = tuple(map(int, punto_medio))
    
    # Dibujar línea roja entre extremos
    cv2.line(frame, p1, p2, (0, 0, 255), 2)
    
    # Dibujar punto medio azul
    cv2.circle(frame, punto_medio, 5, (255, 0, 0), -1)
    
    # Dibujar puntos verdes en todos los centros
    for centro in centros:
        centro_int = tuple(map(int, centro))
        cv2.circle(frame, centro_int, 3, (0, 255, 0), -1)
    
    return frame


def _dibujar_muescas(frame, muescas):
    """
    Dibuja círculos rojos en las posiciones de las muescas.
    
    ⚠️  Esta función SOLO se llama si el análisis fue exitoso.
    Las muescas son un indicador visual de que TODO pasó.
    
    Args:
        frame: Imagen BGR
        muescas: Lista de {'x_px', 'y_px', 'radio_px'}
    
    Returns:
        Frame con muescas dibujadas
    """
    
    for muesca in muescas:
        x = int(muesca['x_px'])
        y = int(muesca['y_px'])
        radio = int(muesca['radio_px'])
        
        # Círculo rojo relleno
        cv2.circle(frame, (x, y), radio, (0, 0, 255), -1)
        # Borde más oscuro
        cv2.circle(frame, (x, y), radio, (0, 0, 200), 1)
    
    return frame


def _dibujar_linea_offset(frame, datos_aruco, primera_muesca, linea_referencia):
    """
    Dibuja línea azul fina desde el centro del troquel hasta la primera muesca.
    Transforma el center_troquel del sistema del ArUco al sistema de la junta (rotado).
    
    Args:
        frame: Imagen BGR
        datos_aruco: {'center', 'px_per_mm'}
        primera_muesca: {'x_px', 'y_px'} (en sistema de junta rotada)
        linea_referencia: {'punto_medio', 'angle_rad'}
    Returns:
        Frame con línea offset dibujada
    """
    
    import json
    import numpy as np
    
    try:
        # Obtener datos del ArUco
        center_aruco = np.array(datos_aruco['center'], dtype=float)
        px_per_mm = datos_aruco.get('px_per_mm', 1.0)
        
        # Obtener datos de la línea de referencia (segmento)
        punto_medio = np.array(linea_referencia.get('punto_medio', [0, 0]), dtype=float)
        angle_rad = linea_referencia.get('angle_rad', 0)
        
        # Cargar configuración del ArUco para obtener offset del troquel
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        aruco_config = config.get('aruco', {})
        center_x_mm = aruco_config.get('center_x_mm', 0)
        center_y_mm = aruco_config.get('center_y_mm', 0)
        
        # Calcular center_troquel en sistema del ArUco (sin rotación)
        center_troquel = np.array([
            center_aruco[0] + (center_x_mm * px_per_mm),
            center_aruco[1] + (center_y_mm * px_per_mm)
        ], dtype=float)
        
        # Transformar center_troquel al sistema de coordenadas de la junta
        # 1. Calcular offset respecto al punto_medio
        offset_x = center_troquel[0] - punto_medio[0]
        offset_y = center_troquel[1] - punto_medio[1]
        
        # 2. Rotar el offset por el angle_rad del segmento
        cos_angle = np.cos(angle_rad)
        sin_angle = np.sin(angle_rad)
        rotated_x = offset_x * cos_angle - offset_y * sin_angle
        rotated_y = offset_x * sin_angle + offset_y * cos_angle
        
        # 3. Sumar al punto_medio para obtener center_troquel en sistema de junta
        center_troquel_rotated = np.array([
            punto_medio[0] + rotated_x,
            punto_medio[1] + rotated_y
        ], dtype=float)
        
        # Posición de la primera muesca (ya está en sistema de junta)
        muesca_pos = (int(primera_muesca['x_px']), int(primera_muesca['y_px']))
        center_troquel_int = (int(center_troquel_rotated[0]), int(center_troquel_rotated[1]))
        
        # Dibujar línea azul fina
        cv2.line(frame, center_troquel_int, muesca_pos, (255, 0, 0), 2)  # Azul, grosor 2
        
        print(f"[visualizador] ✓ Línea offset: {center_troquel_int} → {muesca_pos} (rotación: {np.degrees(angle_rad):.1f}°)")
        
    except Exception as e:
        print(f"[visualizador] ⚠️ No se pudo dibujar línea offset: {e}")
        import traceback
        traceback.print_exc()
    
    return frame

