# vision_manager.py
"""
Vision Manager - COMAU-VISION
=============================

Gestor principal para el análisis de visión con el botón "Analizar" (nuevo).
Maneja toda la lógica de configuración de visión, modelos YOLO, umbrales y ROI.
"""

import os
import json
from . import vision_steps


def get_vision_config():
    """Obtiene la configuración del sistema de visión"""
    try:
        config = vision_steps.step_0_config.load_config()
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
        config = vision_steps.step_0_config.load_config()
        vision_config = config.get('vision', {})
        
        # Actualizar configuración con datos del request
        # Configuración general
        # ... (código existente)
        if 'use_baseframe' in data:
            vision_config['use_baseframe_guardado'] = data['use_baseframe']
        if 'use_toolframe' in data:
            vision_config['use_toolframe_guardado'] = data['use_toolframe']
        if 'use_roi' in data:
            vision_config['use_roi'] = data['use_roi']
        if 'use_boundingbox' in data:
            vision_config['use_boundingbox'] = data['use_boundingbox']

        # Modelos YOLO
        # ... (código existente)
        if 'detection_model' in data:
            vision_config['detection_model'] = data['detection_model']
        if 'holes_model' in data:
            vision_config['holes_model'] = data['holes_model']
        if 'enabled' in data:
            vision_config['detection_enabled'] = data['enabled']
        
        # Umbrales de validación
        # ... (código existente)
        if 'umbral_distancia_tolerancia' in data:
            vision_config['umbral_distancia_tolerancia'] = data['umbral_distancia_tolerancia']
        if 'umbral_centros_mm' in data:
            vision_config['umbral_centros_mm'] = data['umbral_centros_mm']
        if 'umbral_colinealidad_mm' in data:
            vision_config['umbral_colinealidad_mm'] = data['umbral_colinealidad_mm']
        if 'umbral_espaciado_cv' in data:
            vision_config['umbral_espaciado_cv'] = data['umbral_espaciado_cv']

        # Resolución
        # ... (código existente)
        if 'resolution_scale_aruco' in data:
            vision_config['resolution_scale_aruco'] = data['resolution_scale_aruco']
        if 'resolution_scale_yolo' in data:
            vision_config['resolution_scale_yolo'] = data['resolution_scale_yolo']
        if 'resolution_scale_opencv' in data:
            vision_config['resolution_scale_opencv'] = data['resolution_scale_opencv']

        # Configuración de Visualización
        # ... (código existente)
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
        vision_steps.step_0_config.save_config(config)
        
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
        
        # ... (código existente)
        # Cargar configuración actual
        config = vision_steps.step_0_config.load_config()
        vision_config = config.get('vision', {})
        
        # Actualizar configuración ROI
        # ... (código existente)
        if 'roi_enabled' in data:
            vision_config['roi_enabled'] = data['roi_enabled']
        if 'roi_offset_y_mm' in data:
            vision_config['roi_offset_y_mm'] = data['roi_offset_y_mm']
        if 'roi_zoom_x_percent' in data:
            vision_config['roi_zoom_x_percent'] = data['roi_zoom_x_percent']
        if 'roi_zoom_y_percent' in data:
            vision_config['roi_zoom_y_percent'] = data['roi_zoom_y_percent']

        # Guardar configuración
        # ... (código existente)
        config['vision'] = vision_config
        vision_steps.step_0_config.save_config(config)
        
        print(f"[vision_manager] ✓ Configuración ROI guardada: {vision_config}")
        
        # ... (código existente)
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


def _crear_objeto_en_overlay(overlay_manager, obj_data):
    """
    Función auxiliar genérica para crear un objeto en el OverlayManager.
    
    Args:
        overlay_manager: Instancia del OverlayManager.
        obj_data (dict): Diccionario con los datos del objeto a crear.
    
    Returns:
        list: Una lista con los nombres de los objetos creados si fue exitoso, de lo contrario None.
    """
    if not obj_data or not obj_data.get('type') or not obj_data.get('name'):
        return None

    obj_type = obj_data['type']
    name = obj_data['name']
    frame = obj_data.get('frame', 'world')
    units = obj_data.get('units', 'px')
    color = obj_data.get('color', (0, 255, 0))
    thickness = obj_data.get('thickness', 2)

    try:
        if obj_type == 'axes':
            import math
            # Lógica robusta para dibujar ejes:
            # 1. Crear un marco de coordenadas temporal en la posición y ángulo del objeto.
            # 2. Dibujar líneas horizontales y verticales simples en ese marco.
            # La librería se encarga de la transformación compleja.
            
            position = obj_data['position']
            angle = obj_data['angle']
            print(f"[vision_manager] 🔧 DEBUG Ejes {name}: position={position}, angle={angle:.3f} rad")
            
            axes_frame_name = f"{name}_frame"
            overlay_manager.define_frame(
                name=axes_frame_name,
                offset=position,
                rotation=angle,
                px_per_mm=1.0, # La escala no importa para ejes en píxeles
                parent_frame='world'
            )

            length = obj_data.get('length', 1000)

            # Eje X
            # Línea horizontal simple en el marco de los ejes
            overlay_manager.add_line(axes_frame_name, (-length, 0), (length, 0), f"{name}_x", color, thickness, units=units)
            
            # Eje Y
            # Línea vertical simple en el marco de los ejes
            overlay_manager.add_line(axes_frame_name, (0, -length), (0, length), f"{name}_y", color, thickness, units=units)
            
            # Centro
            # Círculo en el origen del marco de los ejes
            overlay_manager.add_circle(axes_frame_name, (0, 0), 5, f"{name}_center", color, -1, units=units)

            return [f"{name}_x", f"{name}_y", f"{name}_center"]

        elif obj_type == 'circle':
            if units == 'mm':
                overlay_manager.add_circle(frame, obj_data['center_mm'], obj_data['radius_mm'], name, color, thickness, units="mm")
            else: # px
                overlay_manager.add_circle(frame, obj_data['center_px'], obj_data['radius_px'], name, color, thickness, units="px")
        
        elif obj_type == 'ellipse':
            overlay_manager.add_ellipse(frame, obj_data['ellipse_data'][0], obj_data['ellipse_data'][1], obj_data['ellipse_data'][2], name, color, thickness, units=units)
        
        elif obj_type == 'polygon':
            overlay_manager.add_polygon(frame, obj_data['points'], name, color, thickness, units=units)
        
        elif obj_type == 'line':
            overlay_manager.add_line(frame, obj_data['start'], obj_data['end'], name, color, thickness, units=units)
        
        return [name]

    except Exception as e:
        print(f"[vision_manager] ⚠️ Error creando objeto '{name}': {e}")
        return None

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
        # Importar dependencias
        import cv2
        import time
        import base64
        from .vision_steps import step_utils
        from src.vision import yolo_detector

        
        # ============================================================
        # INICIALIZACIÓN Y TIMING
        # ============================================================
        start_time = time.time()
        timings = {}
        print("\n" + "="*60)
        print("[vision_manager] 🚀 Iniciando análisis nuevo...")

        # No limpiar log aquí - solo al iniciar el servidor

        # Inicializar overlay manager si no está inicializado
        from src.vision.frames_manager import init_global_frames
        
        overlay_manager = init_global_frames()
        print("[vision_manager] ✓ OverlayManager inicializado/obtenido")

        # ============================================================
        # ESTRUCTURA UNIFICADA DE OBJETOS OVERLAY
        # Se define la estructura al inicio. Cada paso del pipeline la poblará.
        # ============================================================
        overlay_objects = {
            'base_frame': {'config_key': 'aruco_base_show', 'data': None},
            'tool_frame': {'config_key': 'aruco_tool_show', 'data': None},
            'centro_troquel': {'config_key': 'centro_troquel_show', 'data': None},
            'roi': {'config_key': 'roi_show', 'data': []}, # Puede tener múltiples objetos (rect + ejes)
            'junta': {'config_key': 'bbox_junta_show', 'data': None},
            'agujeros': {'config_key': 'bbox_holes_show', 'data': []},
            'elipses': {'config_key': 'elipses_show', 'data': []},
            'segmento_junta': {'config_key': 'segmento_junta_show', 'data': []}
        }
        print("[vision_manager] 📋 Estructura de objetos overlay inicializada")

        # Cargar configuración una sola vez
        config = vision_steps.step_0_config.load_config()
        vision_config = config.get('vision', {})
        # Cargar configuración una sola vez
        config = vision_steps.step_0_config.load_config()

        # Limpiar TODOS los objetos del overlay manager AL INICIO
        print("[vision_manager] 🧹 Limpiando TODOS los objetos del overlay manager...")
        try:
            # Limpiar todos los objetos
            overlay_manager.objects.clear()
            print("[vision_manager] ✅ Todos los objetos eliminados del overlay manager")
        except Exception as e:
            print(f"[vision_manager] ⚠️ Error limpiando objetos: {e}")
        # Paso 1: Capturar imagen
        step_start = time.time()
        captura_result = vision_steps.step_1_capture.capturar_imagen()
        timings['1_captura_imagen'] = (time.time() - step_start) * 1000
        if not captura_result['ok']:
            return captura_result

        # Paso 2: Decidir BaseFrame
        step_start = time.time()
        
        # Redimensionar imagen para ArUco solo si se va a detectar
        use_baseframe_guardado = vision_config.get('use_baseframe_guardado', False)
        use_toolframe_guardado = vision_config.get('use_toolframe_guardado', False)
        
        aruco_image = None
        aruco_scale_factor = 1.0
        
        if not use_baseframe_guardado or not use_toolframe_guardado:
            # Solo redimensionar si al menos uno va a detectar ArUcos
            scale_aruco = vision_config.get('resolution_scale_aruco', 100)
            if scale_aruco != 100:
                aruco_image, aruco_scale_factor = step_utils._scale_image_and_coords(captura_result['gray_frame'], scale_aruco)
                print(f"[vision_manager] 🔬 Imagen para ArUco redimensionada a {scale_aruco}% ({aruco_image.shape[1]}x{aruco_image.shape[0]})")
            else:
                # Scale 100% = no redimensionado, usar imagen original
                aruco_image = captura_result['gray_frame']
                aruco_scale_factor = 1.0
                print("[vision_manager] ⚡ OPTIMIZACIÓN: Scale 100% - usando imagen original sin redimensionado")
        else:
            print("[vision_manager] ⚡ OPTIMIZACIÓN: Omitiendo redimensionado ArUco (ambos frames usan datos guardados)")

        base_frame_result = vision_steps.step_2_frames.decidir_base_frame(aruco_image, aruco_scale_factor)
        timings['2_decidir_base_frame'] = (time.time() - step_start) * 1000
        if not base_frame_result['ok']:
            return base_frame_result

        # Poblar la estructura de datos
        overlay_objects['base_frame']['data'] = next((obj for obj in base_frame_result.get('renderlist_objects', []) if obj['type'] == 'axes'), None)
        
        # Paso 3: Ubicar centro de la troqueladora
        step_start = time.time()
        centro_result = vision_steps.step_2_frames.ubicar_centro_troqueladora(
            base_frame_result['frame_data'], 
            overlay_manager,
            config
        )
        if not centro_result['ok']:
            return centro_result
        timings['3_ubicar_centro_troqueladora'] = (time.time() - step_start) * 1000

        # Actualizar objeto del centro de troqueladora
        if centro_result.get('renderlist_objects'):
            overlay_objects['centro_troquel']['data'] = next((obj for obj in centro_result.get('renderlist_objects', []) if obj['type'] == 'circle'), None)

        # Paso 4: Decidir ToolFrame
        step_start = time.time()
        tool_frame_result = vision_steps.step_2_frames.decidir_tool_frame(aruco_image, aruco_scale_factor)
        timings['4_decidir_tool_frame'] = (time.time() - step_start) * 1000
        if not tool_frame_result['ok']:
            return tool_frame_result

        # Poblar la estructura de datos
        overlay_objects['tool_frame']['data'] = next((obj for obj in tool_frame_result.get('renderlist_objects', []) if obj['type'] == 'axes'), None)
        
        # Crear roi_rectangle con el tamaño completo de la imagen (antes del ROI)
        step_start = time.time()
        roi_rectangle = vision_steps.step_3_roi.crear_roi_rectangle_completo(captura_result['cv2_frame'])
        print(f"[vision_manager] 📦 roi_rectangle creado con tamaño completo: {roi_rectangle['width']}x{roi_rectangle['height']} px")
        

        
        # Paso 5: Dibujar ROI
        roi_result = vision_steps.step_3_roi.dibujar_roi(
            tool_frame_result['frame_data'], 
            overlay_manager, 
            config,
            base_frame_result['frame_data'].get('px_per_mm', 1.0)
        )
        if not roi_result['ok']:
            return roi_result
        timings['5_dibujar_roi'] = (time.time() - step_start) * 1000

        # Poblar la estructura de datos del ROI (puede tener varios objetos)
        overlay_objects['roi']['data'] = roi_result.get('renderlist_objects', [])
        
        # ============================================================
        # CREACIÓN ANTICIPADA DE OBJETOS ROI
        # Es necesario crear los objetos del ROI en el OverlayManager AHORA
        # para que redimensionar_roi_rectangle pueda obtener sus coordenadas en píxeles.
        # ============================================================
        object_names = [] # Inicializar la lista de nombres de objetos aquí

        if vision_config.get('roi_show', False) and overlay_objects['roi']['data']:
            print("[vision_manager] 🎨 Creando objetos del ROI anticipadamente para el cálculo del crop...")
            for obj_data in overlay_objects['roi']['data']:
                created_names = _crear_objeto_en_overlay(overlay_manager, obj_data) # This function is now in vision_manager
                if created_names:
                    # AGREGAR NOMBRES A LA LISTA FINAL DE RENDERIZADO
                    object_names.extend(created_names)
                    print(f"[vision_manager] ✓ Objeto ROI '{created_names}' creado para cálculo de crop.")

        # Redimensionar roi_rectangle al tamaño del ROI (si está activo)
        roi_rectangle = vision_steps.step_3_roi.redimensionar_roi_rectangle(roi_rectangle, roi_result, overlay_manager)
        print(f"[vision_manager] 📦 roi_rectangle redimensionado: {roi_rectangle['width']}x{roi_rectangle['height']} px")

        # ------------------------------------------------------------
        # GESTIÓN DE IMÁGENES PARA YOLO Y OPENCV
        # ------------------------------------------------------------
        step_start = time.time()
        # Imagen para YOLO (puede estar a menor resolución)
        scale_yolo = int(vision_config.get('resolution_scale_yolo', 100))
        yolo_image_full, yolo_scale_factor = step_utils._scale_image_and_coords(captura_result['cv2_frame'], scale_yolo)
        yolo_image_cropped = vision_steps.step_4_yolo.hacer_crop_imagen(yolo_image_full, roi_rectangle, yolo_scale_factor)
        print(f"[vision_manager] ✂️ Imagen para YOLO recortada: {yolo_image_cropped.shape[1]}x{yolo_image_cropped.shape[0]} px")
        
        # Guardar carpeta debug para guardar imágenes
        import os
        debug_folder = "debug"
        if not os.path.exists(debug_folder):
            os.makedirs(debug_folder)
        
        # Guardar imagen YOLO crop para debug (sin bbox)
        cv2.imwrite(os.path.join(debug_folder, "yolo_crop_debug.jpg"), yolo_image_cropped)
        
        # Paso 6: Crear y configurar roi_frame
        roi_frame_result = vision_steps.step_4_yolo.configurar_roi_frame(
            roi_result.get('roi_data'),
            roi_rectangle,
            base_frame_result['frame_data'],
            tool_frame_result['frame_data'],
            overlay_manager,
            config
        )
        if not roi_frame_result['ok']:
            return roi_frame_result
        timings['6_configurar_roi_frame'] = (time.time() - step_start) * 1000

        # Paso 7: Detectar junta con YOLO
        use_boundingbox = vision_config.get('use_boundingbox', False)
        print(f"[vision_manager] 📋 Usar BoundingBox de Junta: {use_boundingbox}")

        step_start = time.time()
        if use_boundingbox:
            # Cargar modelo de detección si es necesario
            detection_model_path = vision_config.get('detection_model', 'models/detection_model.pt')
            if not yolo_detector.is_model_loaded('detection'):
                if not yolo_detector.load_model('detection', detection_model_path):
                    return {'ok': False, 'error': f'No se pudo cargar el modelo de detección: {detection_model_path}'}
            junta_result = vision_steps.step_4_yolo.detectar_junta_yolo(yolo_image_cropped, config, yolo_scale_factor, yolo_detector)
        else:
            print("[vision_manager] ⚡ OPTIMIZACIÓN: Omitiendo detección de junta (Paso 7).")
            junta_result = {'ok': True, 'junta_data': None, 'renderlist_objects': []} # Simular resultado exitoso pero vacío
        timings['7_detectar_junta_yolo'] = (time.time() - step_start) * 1000

        if not junta_result.get('ok', False):
            return junta_result
        
        # Guardar imagen del ROI con bbox de la junta para debug
        if use_boundingbox and junta_result.get('junta_data') and junta_result['junta_data'].get('bbox_in_roi'):
            roi_with_bbox_debug = yolo_image_cropped.copy()
            bbox_in_roi = junta_result['junta_data']['bbox_in_roi']
            if isinstance(bbox_in_roi, (list, tuple)) and len(bbox_in_roi) == 4:
                x1, y1, x2, y2 = bbox_in_roi
                cv2.rectangle(roi_with_bbox_debug, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 3)
                cv2.imwrite(os.path.join(debug_folder, "junta_bbox_debug.jpg"), roi_with_bbox_debug)
        
        # Poblar la estructura de datos de la junta
        overlay_objects['junta']['data'] = next((obj for obj in junta_result.get('renderlist_objects', []) if 'junta' in obj.get('name', '')), None)
        
        # Paso 8: Configurar el junta_frame
        step_start = time.time()
        if use_boundingbox and junta_result.get('junta_data'):
            junta_frame_result = vision_steps.step_4_yolo.configurar_junta_frame(
                junta_result.get('junta_data'),
                roi_rectangle,
                overlay_manager
            )
        else:
            # Si no se usa bbox, alinear junta_frame con roi_frame
            overlay_manager.define_frame("junta_frame", offset=(roi_rectangle['x'], roi_rectangle['y']), rotation=0.0, px_per_mm=(1.0, -1.0))
            junta_frame_result = {'ok': True}

        if not junta_frame_result.get('ok'):
            return junta_frame_result
        timings['8_configurar_junta_frame'] = (time.time() - step_start) * 1000
        # Paso 9: Detectar agujeros con YOLO
        step_start = time.time()
        # Preparamos la imagen para OpenCV (puede tener otra resolución)
        scale_opencv = int(vision_config.get('resolution_scale_opencv', 100))
        opencv_image_full_scaled, opencv_scale_factor = step_utils._scale_image_and_coords(captura_result['cv2_frame'], scale_opencv)
        opencv_image_cropped = vision_steps.step_4_yolo.hacer_crop_imagen(opencv_image_full_scaled, roi_rectangle, 1.0) # La imagen ya está escalada
        
        # Guardar imagen OpenCV crop para debug
        cv2.imwrite(os.path.join(debug_folder, "opencv_crop_debug.jpg"), opencv_image_cropped)

        agujeros_result = vision_steps.step_4_yolo.detectar_agujeros_yolo(
            yolo_image_cropped,
            opencv_image_cropped,
            roi_rectangle,
            junta_result.get('junta_data'),
            config,
            yolo_scale_factor,
            use_boundingbox
        )
        timings['9_detectar_agujeros_yolo'] = (time.time() - step_start) * 1000
        if not agujeros_result.get('ok'):
            return agujeros_result
        overlay_objects['agujeros']['data'] = agujeros_result.get('renderlist_objects', [])
        
        # Extraer datos de elipses si están habilitadas
        if vision_config.get('elipses_show', False):
            elipses_data = [obj for obj in agujeros_result.get('renderlist_objects', []) if obj['type'] == 'ellipse' or obj['type'] == 'circle' and 'elipse_centro' in obj['name']]
            overlay_objects['elipses']['data'] = elipses_data

        # Paso 10: Calcular métricas y segmento de junta
        step_start = time.time()
        centros_refinados = agujeros_result.get('centros_refinados', [])
        metricas_result = vision_steps.step_5_refinement.calcular_metricas_y_segmento(centros_refinados, overlay_manager)
        timings['10_calcular_metricas'] = (time.time() - step_start) * 1000
        if not metricas_result.get('ok'):
            return metricas_result
        
        overlay_objects['segmento_junta']['data'] = metricas_result.get('renderlist_objects', [])

        # ============================================================
        # BUCLE DE RENDERIZADO ÚNICO Y GENÉRICO
        # ============================================================
        step_start = time.time()
        print("[vision_manager] 🎨 Iniciando renderizado unificado...")
        for key, value in overlay_objects.items():
            # Omitir el ROI porque ya se procesó anticipadamente
            if key == 'roi':
                continue

            config_key = value['config_key']
            obj_data_list = value.get('data')

            # Asegurarse de que obj_data_list sea siempre una lista
            if obj_data_list and not isinstance(obj_data_list, list):
                obj_data_list = [obj_data_list]

            if vision_config.get(config_key, False) and obj_data_list:
                print(f"[vision_manager] ✅ Renderizando '{key}' (config '{config_key}'=True)")
                for obj_data in obj_data_list:
                    created_names = _crear_objeto_en_overlay(overlay_manager, obj_data) # This function is now in vision_manager
                    if created_names:
                        object_names.extend(created_names)
            elif not vision_config.get(config_key, False):
                print(f"[vision_manager] ❌ Omitiendo '{key}' (config '{config_key}'=False)")
            elif not obj_data_list:
                print(f"[vision_manager] ❌ Omitiendo '{key}' (sin datos para renderizar)")
            else:
                print(f"[vision_manager] ❌ Omitiendo '{key}' (condición desconocida)")
        
        print(f"[vision_manager] 📋 Objetos renderizados: {len(object_names)}")
        print(f"[vision_manager] 📋 Lista de objetos: {object_names}")
        
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
        timings['11_renderizado_final'] = (time.time() - step_start) * 1000

        # Calcular tiempo total
        total_time = (time.time() - start_time) * 1000

        resultado = {
            'ok': True,
            'mensaje': 'Análisis nuevo ejecutado correctamente',
            'image_base64': image_base64,
            'view_time': 3000,  # 3 segundos
            'tiempo_total': total_time,  # Tiempo total en ms
            'junta_detectada': junta_result.get('junta_data') is not None,  # Si se detectó junta
            'junta_bbox': junta_result.get('junta_data', {}).get('bbox_final') if junta_result.get('junta_data') else None  # Bbox final si existe
        }

        # Imprimir resumen de tiempos
        print("\n" + "="*50)
        print("📊 RESUMEN DE TIEMPOS DE ANÁLISIS")
        print("="*50)
        for step, duration in timings.items():
            print(f"   - {step:<30}: {duration:>7.1f} ms")
        print("-" * 50)
        print(f"   - {'TOTAL':<30}: {total_time:>7.1f} ms")
        print("="*50 + "\n")

        # Escribir log de tiempos
        _escribir_log_tiempos(vision_config, timings, total_time)

        print("[vision_manager] ✅ Análisis nuevo completado - imagen renderizada")
        return resultado

    except Exception as e:
        print(f"[vision_manager] ❌ Error en análisis nuevo: {e}")
        import traceback
        traceback.print_exc()
        total_time = (time.time() - start_time) * 1000
        return {
            'ok': False,
            'error': str(e),
            'tiempo_total': total_time
        }

def _limpiar_log_tiempos():
    """Limpiar el archivo de log de tiempos al iniciar el script"""
    try:
        import os
        debug_folder = "debug"
        if not os.path.exists(debug_folder):
            os.makedirs(debug_folder)
        
        log_file = os.path.join(debug_folder, "timer.log")
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("LOG DE TIEMPOS DE ANÁLISIS - COMAU VISION\n")
            f.write("="*80 + "\n\n")
        print(f"[vision_manager] 📝 Log de tiempos limpiado: {log_file}")
    except Exception as e:
        print(f"[vision_manager] ⚠️ Error limpiando log de tiempos: {e}")

def _escribir_log_tiempos(vision_config, timings, total_time):
    """Escribir configuración y tiempos al log incremental"""
    try:
        import os
        from datetime import datetime
        
        debug_folder = "debug"
        log_file = os.path.join(debug_folder, "timer.log")
        
        with open(log_file, 'a', encoding='utf-8') as f:
            # Timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n[{timestamp}] ANÁLISIS EJECUTADO\n")
            f.write("-" * 80 + "\n")
            
            # Configuración
            f.write("CONFIGURACIÓN:\n")
            f.write(f"  - use_baseframe_guardado: {vision_config.get('use_baseframe_guardado', False)}\n")
            f.write(f"  - use_toolframe_guardado: {vision_config.get('use_toolframe_guardado', False)}\n")
            f.write(f"  - use_roi: {vision_config.get('use_roi', False)}\n")
            f.write(f"  - use_boundingbox: {vision_config.get('use_boundingbox', False)}\n")
            f.write(f"  - resolution_scale_aruco: {vision_config.get('resolution_scale_aruco', 100)}%\n")
            f.write(f"  - resolution_scale_yolo: {vision_config.get('resolution_scale_yolo', 100)}%\n")
            f.write(f"  - resolution_scale_opencv: {vision_config.get('resolution_scale_opencv', 100)}%\n")
            f.write(f"  - aruco_base_show: {vision_config.get('aruco_base_show', False)}\n")
            f.write(f"  - aruco_tool_show: {vision_config.get('aruco_tool_show', False)}\n")
            f.write(f"  - bbox_junta_show: {vision_config.get('bbox_junta_show', False)}\n")
            f.write(f"  - bbox_holes_show: {vision_config.get('bbox_holes_show', False)}\n")
            f.write(f"  - elipses_show: {vision_config.get('elipses_show', False)}\n")
            
            # Tiempos
            f.write("\nTIEMPOS DE ANÁLISIS:\n")
            f.write("=" * 50 + "\n")
            for step, duration in timings.items():
                f.write(f"   - {step:<30}: {duration:>7.1f} ms\n")
            f.write("-" * 50 + "\n")
            f.write(f"   - {'TOTAL':<30}: {total_time:>7.1f} ms\n")
            f.write("=" * 50 + "\n")
            
        print(f"[vision_manager] 📝 Tiempos guardados en log: {log_file}")
    except Exception as e:
        print(f"[vision_manager] ⚠️ Error escribiendo log de tiempos: {e}")
