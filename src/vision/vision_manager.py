# vision_manager.py
"""
Vision Manager - COMAU-VISION
=============================

Gestor principal para el análisis de visión con el botón "Analizar" (nuevo).
Maneja toda la lógica de configuración de visión, modelos YOLO, umbrales y ROI.
"""

import os
import json
from pathlib import Path

# ============================================================
# CONFIGURACIÓN
# ============================================================

CONFIG_FILE = 'config.json'

# ============================================================
# FUNCIONES DE CONFIGURACIÓN
# ============================================================

def load_config():
    """Carga la configuración completa desde config.json"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[vision_manager] Error cargando configuración: {e}")
    return {}

def save_config(config_data):
    """Guarda la configuración completa en config.json"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        print(f"[vision_manager] ✓ Configuración guardada")
        return True
    except Exception as e:
        print(f"[vision_manager] ✗ Error guardando configuración: {e}")
        return False

def get_vision_config():
    """Obtiene la configuración del sistema de visión"""
    try:
        config = load_config()
        vision_config = config.get('vision', {})
        
        print(f"[vision_manager] GET configuración visión - Retornando: {vision_config}")
        return {'ok': True, 'vision': vision_config}
        
    except Exception as e:
        print(f"[vision_manager] Error obteniendo configuración visión: {e}")
        return {'ok': False, 'error': str(e)}

def set_models_config(data):
    """Guarda configuración de modelos YOLO, visualización y umbrales"""
    try:
        print(f"[vision_manager] POST modelos - Datos recibidos: {data}")
        
        # Cargar configuración actual
        config = load_config()
        vision_config = config.get('vision', {})
        
        # Actualizar configuración con datos del request
        # Configuración general
        if 'use_baseframe' in data:
            vision_config['use_baseframe_guardado'] = data['use_baseframe']
        if 'use_toolframe' in data:
            vision_config['use_toolframe_guardado'] = data['use_toolframe']
        if 'use_roi' in data:
            vision_config['use_roi'] = data['use_roi']
        if 'use_boundingbox' in data:
            vision_config['use_boundingbox'] = data['use_boundingbox']
        
        # Modelos YOLO
        if 'detection_model' in data:
            vision_config['detection_model'] = data['detection_model']
        if 'holes_model' in data:
            vision_config['holes_model'] = data['holes_model']
        if 'enabled' in data:
            vision_config['detection_enabled'] = data['enabled']
        
        # Umbrales de validación
        if 'umbral_distancia_tolerancia' in data:
            vision_config['umbral_distancia_tolerancia'] = data['umbral_distancia_tolerancia']
        if 'umbral_centros_mm' in data:
            vision_config['umbral_centros_mm'] = data['umbral_centros_mm']
        if 'umbral_colinealidad_mm' in data:
            vision_config['umbral_colinealidad_mm'] = data['umbral_colinealidad_mm']
        if 'umbral_espaciado_cv' in data:
            vision_config['umbral_espaciado_cv'] = data['umbral_espaciado_cv']
        
        # Configuración de Visualización
        if 'aruco_base_show' in data:
            vision_config['aruco_base_show'] = data['aruco_base_show']
        if 'aruco_tool_show' in data:
            vision_config['aruco_tool_show'] = data['aruco_tool_show']
        if 'centro_troquel_show' in data:
            vision_config['centro_troquel_show'] = data['centro_troquel_show']
        if 'roi_show' in data:
            vision_config['roi_show'] = data['roi_show']
        if 'bbox_junta_show' in data:
            vision_config['bbox_junta_show'] = data['bbox_junta_show']
        if 'bbox_holes_show' in data:
            vision_config['bbox_holes_show'] = data['bbox_holes_show']
        if 'elipses_show' in data:
            vision_config['elipses_show'] = data['elipses_show']
        if 'segmento_junta_show' in data:
            vision_config['segmento_junta_show'] = data['segmento_junta_show']
        
        # Colores fijos para consistencia (no configurables)
        vision_config['colors'] = {
            'aruco_base': [0, 212, 255],      # Azul cian
            'aruco_tool': [255, 68, 68],     # Rojo
            'centro_troquel': [255, 221, 0], # Amarillo
            'roi': [255, 68, 255],           # Magenta
            'bbox_junta': [68, 255, 68],     # Verde
            'bbox_holes': [255, 136, 68],    # Naranja
            'elipses': [68, 255, 136],       # Verde claro
            'segmento_junta': [136, 68, 255] # Púrpura
        }
        
        # Guardar configuración
        config['vision'] = vision_config
        save_config(config)
        
        print(f"[vision_manager] ✓ Configuración de modelos guardada: {vision_config}")
        
        return {
            'ok': True,
            'message': 'Configuración de modelos guardada correctamente',
            'data': vision_config
        }
        
    except Exception as e:
        print(f"[vision_manager] Error guardando modelos: {e}")
        import traceback
        traceback.print_exc()
        return {'ok': False, 'error': str(e)}

def set_roi_config(data):
    """Guarda configuración de Region de Interés (ROI)"""
    try:
        print(f"[vision_manager] POST ROI - Datos recibidos: {data}")
        
        # Cargar configuración actual
        config = load_config()
        vision_config = config.get('vision', {})
        
        # Actualizar configuración ROI
        if 'roi_enabled' in data:
            vision_config['roi_enabled'] = data['roi_enabled']
        if 'roi_offset_y_mm' in data:
            vision_config['roi_offset_y_mm'] = data['roi_offset_y_mm']
        if 'roi_zoom_x_percent' in data:
            vision_config['roi_zoom_x_percent'] = data['roi_zoom_x_percent']
        if 'roi_zoom_y_percent' in data:
            vision_config['roi_zoom_y_percent'] = data['roi_zoom_y_percent']
        
        # Guardar configuración
        config['vision'] = vision_config
        save_config(config)
        
        print(f"[vision_manager] ✓ Configuración ROI guardada: {vision_config}")
        
        return {
            'ok': True,
            'message': 'Configuración ROI guardada correctamente',
            'data': {
                'roi_enabled': vision_config.get('roi_enabled', False),
                'roi_offset_y_mm': vision_config.get('roi_offset_y_mm', 0.0),
                'roi_zoom_x_percent': vision_config.get('roi_zoom_x_percent', 150),
                'roi_zoom_y_percent': vision_config.get('roi_zoom_y_percent', 150)
            }
        }
        
    except Exception as e:
        print(f"[vision_manager] Error guardando ROI: {e}")
        import traceback
        traceback.print_exc()
        return {'ok': False, 'error': str(e)}

# ============================================================
# RUTINAS DE ANÁLISIS - PASOS INDEPENDIENTES
# ============================================================

def capturar_imagen():
    """
    Paso 1: Capturar imagen de la cámara y convertir a escala de grises.
    Returns:
        dict: {
            'ok': bool,
            'cv2_frame': np.ndarray,      # Imagen a color original
            'gray_frame': np.ndarray,     # Imagen en escala de grises
            'rgb_background': np.ndarray, # Imagen en blanco y negro con canales RGB
            'error': str
        }
    """
    try:
        print("[vision_manager] 📸 Paso 1: Capturando imagen...")
        
        # Importar dependencias
        import cv2
        import numpy as np
        import time
        from vision import camera_manager
        
        # Capturar frame fresco de la cámara
        cv2_frame = None
        for attempt in range(3):
            cv2_frame = camera_manager.get_frame_raw()
            if cv2_frame is not None:
                print(f"[vision_manager] ✓ Frame capturado en intento {attempt + 1}")
                break
            else:
                print(f"[vision_manager] ⚠️ Intento {attempt + 1} falló, reintentando...")
                time.sleep(0.1)
        
        if cv2_frame is None:
            return {
                'ok': False,
                'error': 'No se pudo capturar un frame fresco de la cámara después de 3 intentos'
            }
        
        # Convertir a escala de grises y luego a RGB (copiado de aruco_manager)
        print("[vision_manager] 🎨 Convirtiendo imagen a escala de grises y RGB...")
        gray_frame = cv2.cvtColor(cv2_frame, cv2.COLOR_BGR2GRAY)
        rgb_background = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2RGB)
        
        print("[vision_manager] ✅ Paso 1 completado - 3 imágenes generadas")
        return {
            'ok': True,
            'cv2_frame': cv2_frame,
            'gray_frame': gray_frame,
            'rgb_background': rgb_background
        }
        
    except Exception as e:
        print(f"[vision_manager] ❌ Error en capturar_imagen: {e}")
        return {
            'ok': False,
            'error': str(e)
        }

def decidir_aruco_frame(gray_frame, frame_type="base"):
    """
    Paso 2/4: Decidir qué ArUco Frame usar según configuración.
    Función unificada para BaseFrame y ToolFrame.
    
    Args:
        gray_frame: Imagen en escala de grises (np.ndarray)
        frame_type: Tipo de frame ("base" o "tool")
    
    Returns:
        dict: {
            'ok': bool,
            'frame_data': dict,          # Datos para actualizar el Frame
            'renderlist_objects': list,  # Objetos para agregar al renderlist
            'frame_source': str,         # 'saved' o 'detected'
            'error': str
        }
    """
    try:
        print(f"[vision_manager] 🔍 Paso 2/4: Decidiendo {frame_type.upper()}Frame...")
        
        # Importar math para conversión de ángulos
        import math
        
        # Leer configuración directamente del JSON
        config = load_config()
        vision_config = config.get('vision', {})
        
        # Configurar parámetros según el tipo de frame
        if frame_type == "base":
            use_guardado = vision_config.get('use_baseframe_guardado', False)
            show_ejes = vision_config.get('aruco_base_show', False)
            color_key = 'aruco_base'
            aruco_section = 'base'
        else:  # tool
            use_guardado = vision_config.get('use_toolframe_guardado', False)
            show_ejes = vision_config.get('aruco_tool_show', False)
            color_key = 'aruco_tool'
            aruco_section = 'tool'
        
        # Obtener color una sola vez y convertir de RGB a BGR para OpenCV
        colors = vision_config.get('colors', {})
        color_rgb = colors.get(color_key, [0, 212, 255])  # RGB del JSON
        color_ejes = (color_rgb[2], color_rgb[1], color_rgb[0])  # Convertir RGB a BGR
        
        print(f"[vision_manager] 📋 Configuración - Usar {frame_type.upper()}Frame guardado: {use_guardado}")
        print(f"[vision_manager] 📋 Configuración - Mostrar ejes ArUco {frame_type.upper()}: {show_ejes}")
        print(f"[vision_manager] 📋 Color de ejes: {color_ejes}")
        
        if use_guardado:
            # Cargar datos guardados del JSON desde la sección aruco
            print(f"[vision_manager] 📁 Cargando {frame_type.upper()}Frame desde configuración guardada...")
            
            aruco_config = config.get('aruco', {})
            frame_config = aruco_config.get(aruco_section, {})
            saved_reference = frame_config.get('saved_reference', {})
            
            if not saved_reference or not saved_reference.get('center'):
                return {
                    'ok': False,
                    'error': f'No hay datos de {frame_type.upper()}Frame guardados en la configuración'
                }
            
            # Convertir datos del formato aruco al formato esperado
            center = saved_reference.get('center', [0, 0])
            angle_deg = saved_reference.get('angle_deg', 0)
            px_per_mm = saved_reference.get('px_per_mm', 1.0)
            
            frame_data = {
                'position': center,
                'angle': math.radians(angle_deg),  # Convertir grados a radianes
                'px_per_mm': px_per_mm,
                'length': 50  # Longitud por defecto
            }
            
            
            # Crear objetos de renderlist si está habilitado mostrar ejes
            renderlist_objects = []
            if show_ejes:
                
                # Crear objeto de ejes para renderlist
                if 'position' in frame_data and 'angle' in frame_data:
                    renderlist_objects.append({
                        'type': 'axes',
                        'position': frame_data['position'],
                        'angle': frame_data['angle'],
                        'color': color_ejes,
                        'length': frame_data.get('length', 50)  # Longitud por defecto
                    })
                    print("[vision_manager] ✅ Objetos de ejes creados para renderlist")
            
            # Actualizar el frame en el overlay manager
            from src.vision.frames_manager import get_global_overlay_manager
            overlay_manager = get_global_overlay_manager()
            frame_name = f"{frame_type}_frame"
            overlay_manager.update_frame(
                name=frame_name,
                offset=frame_data['position'],
                rotation=frame_data['angle'],
                px_per_mm=frame_data['px_per_mm']
            )
            print(f"[vision_manager] 📋 {frame_type.upper()} frame actualizado: pos={frame_data['position']}, angle={frame_data['angle']}, px_per_mm={frame_data['px_per_mm']}")
            
            print(f"[vision_manager] ✅ Paso 2/4 completado - {frame_type.upper()}Frame desde configuración")
            return {
                'ok': True,
                'frame_data': frame_data,
                'renderlist_objects': renderlist_objects,
                'frame_source': 'saved'
            }
            
        else:
            # Detectar ArUco en la imagen
            print(f"[vision_manager] 🔍 Detectando ArUco {frame_type.upper()} en imagen...")
            
            # Importar función de detección de ArUco
            from src.vision.aruco_manager import detect_arucos_in_image
            
            # Obtener parámetros del ArUco desde configuración
            aruco_config = config.get('aruco', {})
            target_aruco_id = aruco_config.get(aruco_section, {}).get('reference_id', 0)
            aruco_size = aruco_config.get(aruco_section, {}).get('marker_size_mm', 50.0)
            
            # Para detección, necesitamos ambos IDs (base y tool)
            base_aruco_id = aruco_config.get('base', {}).get('reference_id', 0)
            tool_aruco_id = aruco_config.get('tool', {}).get('reference_id', 1)
            
            print(f"[vision_manager] 📋 Detectando ArUco {frame_type.upper()} ID: {target_aruco_id}")
            
            # Detectar ArUcos
            detection_result = detect_arucos_in_image(gray_frame, base_aruco_id, tool_aruco_id)
            
            # Verificar si hubo error en la detección
            if 'error' in detection_result:
                return {
                    'ok': False,
                    'error': f'Error detectando ArUcos: {detection_result["error"]}'
                }
            
            # Verificar si se detectó el ArUco target
            if not detection_result.get('frame_detected', False):
                return {
                    'ok': False,
                    'error': f'No se detectó ArUco {frame_type.upper()} ID {target_aruco_id} en la imagen'
                }
            
            # Extraer datos del ArUco target detectado
            detected_arucos = detection_result.get('detected_arucos', {})
            if target_aruco_id not in detected_arucos:
                return {
                    'ok': False,
                    'error': f'ArUco {frame_type.upper()} ID {target_aruco_id} no encontrado en los ArUcos detectados'
                }
            
            # Obtener información del ArUco target
            target_aruco_data = detected_arucos[target_aruco_id]
            position = target_aruco_data.get('center', [0, 0])
            angle = target_aruco_data.get('angle_rad', 0)
            px_per_mm = target_aruco_data.get('px_per_mm', 1.0)
            
            # Crear datos del Frame
            frame_data = {
                'position': position,
                'angle': angle,
                'px_per_mm': px_per_mm,
                'aruco_id': target_aruco_id,
                'aruco_size': aruco_size,
                'detected': True
            }
            
            
            # Crear objetos de renderlist si está habilitado mostrar ejes
            renderlist_objects = []
            if show_ejes:
                
                # Crear objeto de ejes para renderlist
                renderlist_objects.append({
                    'type': 'axes',
                    'position': position,
                    'angle': angle,
                    'color': color_ejes,
                    'length': 50  # Longitud fija
                })
                print("[vision_manager] ✅ Objetos de ejes creados para renderlist")
            
            # Actualizar el frame en el overlay manager
            from src.vision.frames_manager import get_global_overlay_manager
            overlay_manager = get_global_overlay_manager()
            frame_name = f"{frame_type}_frame"
            overlay_manager.update_frame(
                name=frame_name,
                offset=frame_data['position'],
                rotation=frame_data['angle'],
                px_per_mm=frame_data['px_per_mm']
            )
            print(f"[vision_manager] 📋 {frame_type.upper()} frame actualizado: pos={frame_data['position']}, angle={frame_data['angle']}, px_per_mm={frame_data['px_per_mm']}")
            
            print(f"[vision_manager] ✅ Paso 2/4 completado - {frame_type.upper()}Frame detectado")
            return {
                'ok': True,
                'frame_data': frame_data,
                'renderlist_objects': renderlist_objects,
                'frame_source': 'detected'
            }
            
    except Exception as e:
        print(f"[vision_manager] ❌ Error en decidir_aruco_frame: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ok': False,
            'error': str(e)
        }

def decidir_base_frame(gray_frame):
    """
    Wrapper para decidir BaseFrame.
    """
    return decidir_aruco_frame(gray_frame, "base")

def decidir_tool_frame(gray_frame):
    """
    Wrapper para decidir ToolFrame.
    """
    return decidir_aruco_frame(gray_frame, "tool")

def ubicar_centro_troqueladora(base_frame_data, overlay_manager, config):
    """
    Paso 3: Ubicar el centro de la troqueladora.
    Lee los datos del JSON y dibuja el punto con referencia al BaseFrame.
    
    Args:
        base_frame_data: Datos del BaseFrame (posición, ángulo, px_per_mm)
        overlay_manager: Instancia del overlay manager
        config: Configuración completa del JSON
    
    Returns:
        dict: {
            'ok': bool,
            'centro_data': dict,      # Datos del centro de la troqueladora
            'renderlist_objects': list,  # Objetos para agregar al renderlist
            'error': str
        }
    """
    try:
        print("[vision_manager] 🎯 Paso 3: Ubicando centro de la troqueladora...")
        
        # Leer configuración de visión
        vision_config = config.get('vision', {})
        show_centro_troquel = vision_config.get('centro_troquel_show', False)
        
        print(f"[vision_manager] 📋 Mostrar centro troqueladora: {show_centro_troquel}")
        
        if not show_centro_troquel:
            print("[vision_manager] ℹ️ Centro de troqueladora deshabilitado")
            return {
                'ok': True,
                'centro_data': None,
                'renderlist_objects': []
            }
        
        # Obtener color del JSON
        colors = vision_config.get('colors', {})
        color_rgb = colors.get('centro_troquel', [255, 221, 0])  # Amarillo por defecto
        color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])  # Convertir RGB a BGR
        
        # Leer coordenadas del centro de la troqueladora desde el JSON
        aruco_config = config.get('aruco', {})
        center_x_mm = aruco_config.get('center_x_mm', 35)  # mm desde el ArUco base
        center_y_mm = aruco_config.get('center_y_mm', 35)  # mm desde el ArUco base
        
        print(f"[vision_manager] 📋 Coordenadas del centro: ({center_x_mm}mm, {center_y_mm}mm)")
        
        # Usar coordenadas en mm directamente (la librería hace la conversión automática)
        print(f"[vision_manager] 📋 Coordenadas en mm: ({center_x_mm}mm, {center_y_mm}mm)")
        
        # Crear datos del centro
        centro_data = {
            'position_mm': [center_x_mm, center_y_mm],
            'base_frame_data': base_frame_data
        }
        
        # Crear objetos de renderlist
        renderlist_objects = []
        
        # NO crear el círculo aquí, solo preparar los datos para el bucle principal
        circle_name = "centro_troqueladora"
        
        renderlist_objects.append({
            'type': 'circle',
            'name': circle_name,
            'center_mm': [center_x_mm, center_y_mm],
            'radius_mm': 5,
            'color': color_bgr
        })
        
        print(f"[vision_manager] ✅ Centro de troqueladora creado: {circle_name}")
        print(f"[vision_manager] 📋 Color: {color_bgr}")
        
        return {
            'ok': True,
            'centro_data': centro_data,
            'renderlist_objects': renderlist_objects
        }
        
    except Exception as e:
        print(f"[vision_manager] ❌ Error en ubicar_centro_troqueladora: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ok': False,
            'error': str(e)
        }

def dibujar_roi(tool_frame_data, overlay_manager, config, base_px_per_mm=None):
    """
    Paso 5: Dibujar ROI respecto al ToolFrame.
    Rectángulo 100x100mm amplificado con zoom y desplazado según offset.
    
    Args:
        tool_frame_data: Datos del ToolFrame (posición, ángulo, px_per_mm)
        overlay_manager: Instancia del overlay manager
        config: Configuración completa del JSON
    
    Returns:
        dict: {
            'ok': bool,
            'roi_data': dict,           # Datos del ROI
            'renderlist_objects': list, # Objetos para agregar al renderlist
            'error': str
        }
    """
    try:
        print("[vision_manager] 📐 Paso 5: Dibujando ROI...")
        
        # Leer configuración de visión
        vision_config = config.get('vision', {})
        roi_enabled = vision_config.get('use_roi', False)
        roi_show = vision_config.get('roi_show', False)
        
        print(f"[vision_manager] 📋 ROI habilitado: {roi_enabled}")
        print(f"[vision_manager] 📋 ROI visible: {roi_show}")
        
        if not roi_enabled:
            print("[vision_manager] ℹ️ ROI deshabilitado")
            return {
                'ok': True,
                'roi_data': None,
                'renderlist_objects': []
            }
        
        # Obtener color del JSON
        colors = vision_config.get('colors', {})
        color_rgb = colors.get('roi', [255, 0, 0])  # Rojo por defecto
        color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])  # Convertir RGB a BGR
        
        # Leer parámetros del ROI
        zoom_x_percent = vision_config.get('roi_zoom_x_percent', 110)  # %
        zoom_y_percent = vision_config.get('roi_zoom_y_percent', 130)  # %
        offset_y_mm = vision_config.get('roi_offset_y_mm', -80)  # mm
        
        print(f"[vision_manager] 📋 Zoom X: {zoom_x_percent}%, Zoom Y: {zoom_y_percent}%")
        print(f"[vision_manager] 📋 Offset Y: {offset_y_mm}mm")
        
        # Rectángulo base (100x100 mm)
        width_base = 100  # mm
        height_base = 100  # mm
        
        # Aplicar amplificación
        zoom_x = zoom_x_percent / 100.0
        zoom_y = zoom_y_percent / 100.0
        width_amplified = width_base * zoom_x
        height_amplified = height_base * zoom_y
        
        print(f"[vision_manager] 📋 Dimensiones amplificadas: {width_amplified:.1f}x{height_amplified:.1f}mm")
        
        # Calcular desplazamiento Y total
        # Medio rectángulo hacia abajo + offset adicional
        total_offset_y = (height_amplified / 2) + abs(offset_y_mm)  # abs() para asegurar hacia abajo
        
        print(f"[vision_manager] 📋 Desplazamiento Y total: {total_offset_y:.1f}mm")
        
        # Crear datos del ROI
        roi_data = {
            'width_mm': width_amplified,
            'height_mm': height_amplified,
            'offset_y_mm': total_offset_y,
            'zoom_x': zoom_x,
            'zoom_y': zoom_y,
            'tool_reference': tool_frame_data['position']
        }
        
        # Crear objetos de renderlist
        renderlist_objects = []
        
        if roi_show:
            # Crear rectángulo del ROI usando add_polygon
            roi_name = "roi_rectangle"
            
            # Calcular vértices del rectángulo (centrado en 0, -total_offset_y)
            half_width = width_amplified / 2
            half_height = height_amplified / 2
            
            # Vértices del rectángulo (en orden: esquina superior izquierda, superior derecha, inferior derecha, inferior izquierda)
            roi_points = [
                (-half_width, -total_offset_y - half_height),  # Esquina superior izquierda
                (half_width, -total_offset_y - half_height),   # Esquina superior derecha
                (half_width, -total_offset_y + half_height),    # Esquina inferior derecha
                (-half_width, -total_offset_y + half_height)   # Esquina inferior izquierda
            ]
            
            overlay_manager.add_polygon(
                frame="tool_frame",  # Usar el marco tool para coordenadas relativas
                points=roi_points,   # Vértices del rectángulo
                name=roi_name,
                color=color_bgr,
                thickness=2
            )
            
            renderlist_objects.append({
                'type': 'polygon',
                'name': roi_name,
                'points': roi_points,
                'color': color_bgr
            })
            
            # Dibujar ejes del roi_frame en la esquina superior izquierda (origen 0,0)
            # Eje X del roi_frame (línea horizontal desde la esquina)
            roi_axis_x_name = "roi_axis_x"
            
            # Línea horizontal desde la esquina superior izquierda (origen del roi_frame)
            roi_corner_x = -half_width  # Esquina izquierda
            roi_corner_y = -total_offset_y - half_height  # Esquina superior
            
            # Extensión de lado a lado de la imagen (usar coordenadas en píxeles para mayor extensión)
            # Convertir a píxeles para tener líneas que crucen toda la imagen
            px_per_mm = base_px_per_mm if base_px_per_mm is not None else 1.0
            image_width_px = 1920  # Ancho típico de imagen
            image_height_px = 1080  # Alto típico de imagen
            
            # Extensión en mm para cruzar toda la imagen
            axis_extension_x = (image_width_px / px_per_mm) * 0.8  # 80% del ancho de imagen
            axis_extension_y = (image_height_px / px_per_mm) * 0.8  # 80% del alto de imagen
            
            overlay_manager.add_line(
                frame="tool_frame",
                start=(roi_corner_x - axis_extension_x, roi_corner_y),  # Inicio extendido hacia la izquierda
                end=(roi_corner_x + axis_extension_x, roi_corner_y),    # Fin extendido hacia la derecha
                name=roi_axis_x_name,
                color=color_bgr,
                thickness=3  # Más grueso para distinguir del rectángulo
            )
            
            # Eje Y del roi_frame (línea vertical desde la esquina)
            roi_axis_y_name = "roi_axis_y"
            
            # Línea vertical desde la esquina superior izquierda (origen del roi_frame)
            overlay_manager.add_line(
                frame="tool_frame",
                start=(roi_corner_x, roi_corner_y - axis_extension_y),  # Inicio extendido hacia arriba
                end=(roi_corner_x, roi_corner_y + axis_extension_y),     # Fin extendido hacia abajo
                name=roi_axis_y_name,
                color=color_bgr,
                thickness=3  # Más grueso para distinguir del rectángulo
            )
            
            # Agregar ejes a renderlist_objects
            renderlist_objects.append({
                'type': 'line',
                'name': roi_axis_x_name,
                'start': (roi_corner_x - axis_extension_x, roi_corner_y),  # Inicio extendido hacia la izquierda
                'end': (roi_corner_x + axis_extension_x, roi_corner_y),    # Fin extendido hacia la derecha
                'color': color_bgr
            })
            
            renderlist_objects.append({
                'type': 'line',
                'name': roi_axis_y_name,
                'start': (roi_corner_x, roi_corner_y - axis_extension_y),  # Inicio extendido hacia arriba
                'end': (roi_corner_x, roi_corner_y + axis_extension_y),     # Fin extendido hacia abajo
                'color': color_bgr
            })
            
            print(f"[vision_manager] ✅ ROI creado: {roi_name}")
            print(f"[vision_manager] ✅ Ejes del roi_frame creados: {roi_axis_x_name}, {roi_axis_y_name}")
            print(f"[vision_manager] 📋 Color: {color_bgr}")
            print(f"[vision_manager] 📋 Extensión X: {axis_extension_x:.1f}mm, Extensión Y: {axis_extension_y:.1f}mm")
        
        return {
            'ok': True,
            'roi_data': roi_data,
            'renderlist_objects': renderlist_objects
        }
        
    except Exception as e:
        print(f"[vision_manager] ❌ Error en dibujar_roi: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ok': False,
            'error': str(e)
        }


def configurar_roi_frame(roi_data, base_frame_data, overlay_manager, config):
    """
    Paso 6: Crear y configurar roi_frame.
    
    IMPORTANTE: El roi_frame se inicializa alineado con 'world' (origen 0,0, sin rotación)
    y luego se actualiza con la posición y rotación del ROI. La relación px/mm se toma
    del base_frame para mantener consistencia en las conversiones.
    
    Args:
        roi_data: Datos del ROI calculado (posición, dimensiones, etc.)
        base_frame_data: Datos del BaseFrame (para obtener px_per_mm)
        overlay_manager: Instancia del overlay manager
        config: Configuración completa del JSON
    
    Returns:
        dict: {
            'ok': bool,
            'roi_frame_data': dict,     # Datos del roi_frame creado
            'error': str
        }
    """
    try:
        print("[vision_manager] 📐 Paso 6: Configurando roi_frame...")
        
        # Verificar que tenemos los datos necesarios
        if not roi_data:
            print("[vision_manager] ⚠️ No hay datos de ROI para configurar el frame")
            return {
                'ok': True,
                'roi_frame_data': None
            }
        
        # Obtener la relación px/mm del BaseFrame (IMPORTANTE: usar la del base_frame)
        base_px_per_mm = base_frame_data.get('px_per_mm', 1.0)
        print(f"[vision_manager] 📋 Usando px_per_mm del BaseFrame: {base_px_per_mm:.3f}")
        
        # Obtener las dimensiones del ROI para calcular la esquina
        roi_width = roi_data['width_mm']
        roi_height = roi_data['height_mm']
        roi_offset_y = roi_data['offset_y_mm']
        
        print(f"[vision_manager] 📋 Dimensiones del ROI: {roi_width:.1f}x{roi_height:.1f} mm")
        print(f"[vision_manager] 📋 Offset Y del ROI: {roi_offset_y:.1f} mm")
        
        # Posicionar el roi_frame en la esquina superior izquierda del rectángulo ROI
        # Esto facilita el crop y la detección de YOLO
        half_width = roi_width / 2
        half_height = roi_height / 2
        
        # Esquina superior izquierda del ROI relativa al tool_frame
        roi_corner_x = -half_width  # Esquina izquierda
        roi_corner_y = -roi_offset_y - half_height  # Esquina superior
        
        print(f"[vision_manager] 📋 Esquina superior izquierda del ROI relativa al tool_frame: ({roi_corner_x:.1f}, {roi_corner_y:.1f}) mm")
        
        # Obtener la posición y rotación del tool_frame para calcular la posición absoluta
        tool_position = roi_data.get('tool_reference', [0, 0])  # Posición del tool_frame
        tool_angle = base_frame_data.get('angle', 0)  # Ángulo del tool_frame (mismo que base_frame)
        
        print(f"[vision_manager] 📋 ToolFrame posición: {tool_position}")
        print(f"[vision_manager] 📋 ToolFrame ángulo: {tool_angle:.3f} rad")
        
        # Calcular la posición absoluta de la esquina del ROI en el mundo
        # Convertir coordenadas de la esquina desde tool_frame a world
        import math
        
        # Rotar las coordenadas de la esquina según el ángulo del tool_frame
        cos_angle = math.cos(tool_angle)
        sin_angle = math.sin(tool_angle)
        
        # Aplicar rotación y traslación para obtener la posición absoluta de la esquina
        roi_world_x = tool_position[0] + (roi_corner_x * cos_angle - roi_corner_y * sin_angle)
        roi_world_y = tool_position[1] + (roi_corner_x * sin_angle + roi_corner_y * cos_angle)
        
        print(f"[vision_manager] 📋 Posición absoluta de la esquina del ROI: ({roi_world_x:.1f}, {roi_world_y:.1f}) mm")
        
        # El roi_frame ya está creado en frames_manager.py
        # Solo necesitamos actualizarlo con la posición y rotación del ROI
        roi_frame_name = "roi_frame"
        
        print(f"[vision_manager] 📋 roi_frame ya existe, actualizando con datos del ROI")
        print(f"[vision_manager] 📋 Origen actual: (0, 0), Rotación: 0°, px_per_mm: 1.0")
        
        # Actualizar el roi_frame con la posición y rotación del ROI
        overlay_manager.update_frame(
            name=roi_frame_name,
            offset=(roi_world_x, roi_world_y),  # Posición absoluta del ROI
            rotation=tool_angle,                # Rotación del tool_frame (misma que base_frame)
            px_per_mm=base_px_per_mm           # Usar la relación del BaseFrame
        )
        
        print(f"[vision_manager] ✅ roi_frame actualizado con posición y rotación del ROI")
        print(f"[vision_manager] 📋 Posición final (esquina superior izquierda): ({roi_world_x:.1f}, {roi_world_y:.1f}) mm")
        print(f"[vision_manager] 📋 Rotación final: {math.degrees(tool_angle):.1f}°")
        print(f"[vision_manager] 📋 Dimensiones del ROI: {roi_width:.1f}x{roi_height:.1f} mm")
        
        # Crear datos del roi_frame para retorno
        roi_frame_data = {
            'name': roi_frame_name,
            'position': (roi_world_x, roi_world_y),  # Esquina superior izquierda
            'angle': tool_angle,
            'px_per_mm': base_px_per_mm,
            'parent': 'world',
            'roi_corner_relative': (roi_corner_x, roi_corner_y),  # Esquina relativa al tool_frame
            'roi_dimensions': (roi_width, roi_height)  # Dimensiones del ROI
        }
        
        return {
            'ok': True,
            'roi_frame_data': roi_frame_data
        }
        
    except Exception as e:
        print(f"[vision_manager] ❌ Error en configurar_roi_frame: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ok': False,
            'error': str(e)
        }

# ============================================================
# FUNCIÓN PRINCIPAL - RUTINA DE ANÁLISIS
# ============================================================

def ejecutar_analisis_nuevo():
    """
    Rutina principal para el análisis con el botón "Analizar" (nuevo).
    Utiliza las rutinas independientes para cada paso del análisis.
    
    Returns:
        dict: Resultado del análisis
    """
    try:
        print("[vision_manager] 🚀 Iniciando análisis nuevo...")
        
        # Importar dependencias
        import cv2
        import time
        import base64
        
        # Inicializar overlay manager si no está inicializado
        from src.vision.frames_manager import init_global_frames
        
        overlay_manager = init_global_frames()
        print("[vision_manager] ✓ OverlayManager inicializado/obtenido")
        
        # Paso 1: Capturar imagen
        captura_result = capturar_imagen()
        if not captura_result['ok']:
            return captura_result
        
        # Paso 2: Decidir BaseFrame
        base_frame_result = decidir_base_frame(captura_result['gray_frame'])
        if not base_frame_result['ok']:
            return base_frame_result
        
        # Cargar configuración para el paso 3
        config = load_config()
        
        # Paso 3: Ubicar centro de la troqueladora
        centro_result = ubicar_centro_troqueladora(
            base_frame_result['frame_data'], 
            overlay_manager, 
            config
        )
        if not centro_result['ok']:
            return centro_result
        
        # Paso 4: Decidir ToolFrame
        tool_frame_result = decidir_tool_frame(captura_result['gray_frame'])
        if not tool_frame_result['ok']:
            return tool_frame_result
        
        # Limpiar TODOS los objetos del overlay manager AL INICIO
        print("[vision_manager] 🧹 Limpiando TODOS los objetos del overlay manager...")
        try:
            # Limpiar todos los objetos
            overlay_manager.objects.clear()
            print("[vision_manager] ✅ Todos los objetos eliminados del overlay manager")
        except Exception as e:
            print(f"[vision_manager] ⚠️ Error limpiando objetos: {e}")
        
        # Paso 5: Dibujar ROI
        roi_result = dibujar_roi(
            tool_frame_result['frame_data'], 
            overlay_manager, 
            config,
            base_frame_result['frame_data'].get('px_per_mm', 1.0)
        )
        if not roi_result['ok']:
            return roi_result
        
        # Paso 6: Crear y configurar roi_frame
        roi_frame_result = configurar_roi_frame(
            roi_result['roi_data'],
            base_frame_result['frame_data'],
            overlay_manager,
            config
        )
        if not roi_frame_result['ok']:
            return roi_frame_result
        
        # Crear objetos de overlay directamente
        base_objects = base_frame_result.get('renderlist_objects', [])
        centro_objects = centro_result.get('renderlist_objects', [])
        tool_objects = tool_frame_result.get('renderlist_objects', [])
        roi_objects = roi_result.get('renderlist_objects', [])
        
        # Combinar todos los objetos
        all_objects = base_objects + centro_objects + tool_objects + roi_objects
        
        print(f"[vision_manager] 📋 Objetos de BaseFrame: {len(base_objects)}")
        print(f"[vision_manager] 📋 Objetos de centro: {len(centro_objects)}")
        print(f"[vision_manager] 📋 Objetos de ToolFrame: {len(tool_objects)}")
        print(f"[vision_manager] 📋 Objetos de ROI: {len(roi_objects)}")
        print(f"[vision_manager] 📋 Total de objetos: {len(all_objects)}")
        print(f"[vision_manager] 📋 Contenido de todos los objetos: {all_objects}")
        
        # Lista de nombres de objetos para el render
        object_names = []
        
        if all_objects:
            # Crear objetos reales de todos los pasos
            for i, obj in enumerate(all_objects):
                if obj['type'] == 'axes':
                    # Crear ejes X e Y del ArUco
                    import math
                    
                    # Posición del ArUco
                    center_x, center_y = obj['position']
                    angle = obj['angle']
                    color = obj['color']
                    
                    # Obtener dimensiones de la imagen para ejes que atraviesen toda la imagen
                    image_height, image_width = captura_result['gray_frame'].shape[:2]
                    max_dimension = max(image_width, image_height)
                    
                    # Calcular puntos de los ejes que atraviesen toda la imagen
                    # Eje X (horizontal) - desde un extremo al otro
                    end_x_x = center_x + max_dimension * math.cos(angle)
                    end_y_x = center_y + max_dimension * math.sin(angle)
                    start_x_x = center_x - max_dimension * math.cos(angle)
                    start_y_x = center_y - max_dimension * math.sin(angle)
                    
                    # Eje Y (vertical, perpendicular al X) - desde un extremo al otro
                    end_x_y = center_x + max_dimension * math.cos(angle + math.pi/2)
                    end_y_y = center_y + max_dimension * math.sin(angle + math.pi/2)
                    start_x_y = center_x - max_dimension * math.cos(angle + math.pi/2)
                    start_y_y = center_y - max_dimension * math.sin(angle + math.pi/2)
                    
                    # Crear eje X (coordenadas en píxeles)
                    axis_x_name = f"analisis_axis_x_{i}"
                    overlay_manager.add_line(
                        frame="world",
                        start=(start_x_x, start_y_x),
                        end=(end_x_x, end_y_x),
                        color=color,
                        thickness=3,
                        name=axis_x_name,
                        units="px"  # Coordenadas en píxeles
                    )
                    object_names.append(axis_x_name)
                    
                    # Crear eje Y (coordenadas en píxeles)
                    axis_y_name = f"analisis_axis_y_{i}"
                    overlay_manager.add_line(
                        frame="world",
                        start=(start_x_y, start_y_y),
                        end=(end_x_y, end_y_y),
                        color=color,
                        thickness=3,
                        name=axis_y_name,
                        units="px"  # Coordenadas en píxeles
                    )
                    object_names.append(axis_y_name)
                    
                    print(f"[vision_manager] ✅ Ejes del ArUco creados: {axis_x_name}, {axis_y_name}")
                
                elif obj['type'] == 'circle':
                    # Crear el círculo del centro de la troqueladora
                    print(f"[vision_manager] 🔍 Procesando círculo: {obj}")
                    
                    # El base_frame ya fue actualizado en el Paso 2
                    overlay_manager.add_circle(
                        frame="base_frame",  # Usar el marco base actualizado en el Paso 2
                        center=(obj['center_mm'][0], obj['center_mm'][1]),  # Coordenadas en mm
                        radius=obj['radius_mm'],  # Radio en mm
                        color=obj['color'],
                        thickness=3,
                        name=obj['name'],
                        units="mm"  # Especificar que las coordenadas están en mm
                    )
                    
                    object_names.append(obj['name'])
                    print(f"[vision_manager] ✅ Círculo del centro creado: {obj['name']}")
                
                elif obj['type'] == 'polygon':
                    # El polígono ya fue creado en dibujar_roi, solo agregar a la lista
                    print(f"[vision_manager] 🔍 Procesando polígono: {obj}")
                    object_names.append(obj['name'])
                    print(f"[vision_manager] ✅ Polígono ROI agregado: {obj['name']}")
                
                elif obj['type'] == 'line':
                    # Las líneas ya fueron creadas en dibujar_roi, solo agregar a la lista
                    print(f"[vision_manager] 🔍 Procesando línea: {obj}")
                    object_names.append(obj['name'])
                    print(f"[vision_manager] ✅ Línea agregada: {obj['name']}")
        else:
            # No hay objetos de renderlist, no crear nada
            print("[vision_manager] ℹ️ No hay objetos de renderlist para mostrar")
        
        print(f"[vision_manager] 📋 Objetos creados: {object_names}")
        
        # Renderizar la imagen con los objetos creados
        print("[vision_manager] 🖼️ Renderizando imagen...")
        result_image, view_time = overlay_manager.render(
            background_image=captura_result['rgb_background'],
            renderlist=object_names,  # Usar lista directa de nombres de objetos
            view_time=3000  # 3 segundos
        )
        
        # Convertir a base64 para enviar al frontend
        _, buffer = cv2.imencode('.jpg', result_image, [cv2.IMWRITE_JPEG_QUALITY, 75])
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        
        resultado = {
            'ok': True,
            'mensaje': f'Análisis nuevo ejecutado correctamente - BaseFrame: {base_frame_result["frame_source"]}',
            'image_base64': image_base64,
            'view_time': view_time,
            'timestamp': time.time(),
            'base_frame_source': base_frame_result['frame_source'],
            'objects_rendered': len(base_frame_result.get('renderlist_objects', []))
        }
        
        print("[vision_manager] ✅ Análisis nuevo completado - imagen renderizada")
        return resultado
        
    except Exception as e:
        print(f"[vision_manager] ❌ Error en análisis nuevo: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ok': False,
            'error': str(e),
            'timestamp': __import__('time').time()
        }