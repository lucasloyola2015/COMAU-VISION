# src/vision/vision_steps/step_2_frames.py

import math
from typing import Dict, Any
from .step_utils import load_config

def decidir_aruco_frame(gray_frame, scale_factor, frame_type="base"):
    """
    Paso 2/4: Decidir qué ArUco Frame usar según configuración.
    Función unificada para BaseFrame y ToolFrame.
    """
    try:
        print(f"[vision_manager] 🔍 Paso 2/4: Decidiendo {frame_type.upper()}Frame...")
        
        config = load_config()
        vision_config = config.get('vision', {})
        
        if frame_type == "base":
            use_guardado = vision_config.get('use_baseframe_guardado', False)
            show_ejes = vision_config.get('aruco_base_show', False)
            color_key = 'aruco_base'
            aruco_section = 'base'
        else:
            use_guardado = vision_config.get('use_toolframe_guardado', False)
            show_ejes = vision_config.get('aruco_tool_show', False)
            color_key = 'aruco_tool'
            aruco_section = 'tool'
        
        colors = vision_config.get('colors', {})
        color_rgb = colors.get(color_key, [0, 212, 255])
        color_ejes = (color_rgb[2], color_rgb[1], color_rgb[0])
        
        if use_guardado:
            print(f"[vision_manager] 📁 Cargando {frame_type.upper()}Frame desde config guardada...")
            aruco_config = config.get('aruco', {})
            frame_config = aruco_config.get(aruco_section, {})
            saved_reference = frame_config.get('saved_reference', {})
            
            if not saved_reference or not saved_reference.get('center'):
                return {'ok': False, 'error': f'No hay datos de {frame_type.upper()}Frame guardados'}
            
            center = saved_reference.get('center', [0, 0])
            angle_deg = saved_reference.get('angle_deg', 0)
            px_per_mm = saved_reference.get('px_per_mm', 1.0)
            
            frame_data = {
                'position': center,
                'angle': math.radians(angle_deg),
                'px_per_mm': px_per_mm,
                'length': 50
            }
            
            renderlist_objects = []
            if show_ejes:
                renderlist_objects.append({
                    'type': 'axes',
                    'name': f"{frame_type}_axes",
                    'position': frame_data['position'],
                    'angle': frame_data['angle'],
                    'color': color_ejes,
                    'length': 1000,
                    'frame': 'world',
                    'units': 'px'
                })
            
            from src.vision.frames_manager import get_global_overlay_manager
            overlay_manager = get_global_overlay_manager()
            frame_name = f"{frame_type}_frame"
            overlay_manager.update_frame(
                name=frame_name,
                offset=frame_data['position'],
                rotation=frame_data['angle'],
                px_per_mm=frame_data['px_per_mm']
            )
            
            return {
                'ok': True,
                'frame_data': frame_data,
                'renderlist_objects': renderlist_objects,
                'frame_source': 'saved'
            }
            
        else:
            print(f"[vision_manager] 🔍 Detectando ArUco {frame_type.upper()} en imagen...")
            from src.vision.aruco_manager import detect_arucos_in_image
            
            aruco_config = config.get('aruco', {})
            target_aruco_id = aruco_config.get(aruco_section, {}).get('reference_id', 0)
            aruco_size = aruco_config.get(aruco_section, {}).get('marker_size_mm', 50.0)
            
            base_aruco_id = aruco_config.get('base', {}).get('reference_id', 0)
            tool_aruco_id = aruco_config.get('tool', {}).get('reference_id', 1)
            
            # El 'scale_factor' que recibimos es el inverso (ej: 2.0 para una imagen al 50%).
            # La función detect_arucos_in_image espera el factor directo (ej: 0.5).
            # Lo invertimos para pasarlo correctamente.
            direct_scale_factor = 1.0 / scale_factor if scale_factor != 0 else 1.0
            detection_result = detect_arucos_in_image(gray_frame, base_aruco_id, tool_aruco_id, scale_factor=direct_scale_factor)
            
            if 'error' in detection_result:
                return {'ok': False, 'error': f'Error detectando ArUcos: {detection_result["error"]}'}
            
            detected_arucos = detection_result.get('detected_arucos', {})
            if target_aruco_id not in detected_arucos:
                return {'ok': False, 'error': f'No se detectó ArUco {frame_type.upper()} ID {target_aruco_id}'}
            
            target_aruco_data = detected_arucos[target_aruco_id]
            
            position = target_aruco_data.get('center', [0, 0])
            angle = target_aruco_data.get('angle_rad', 0)
            px_per_mm = target_aruco_data.get('px_per_mm', 1.0)
            
            frame_data = {
                'position': position, # Las coordenadas ya vienen escaladas a 100%
                'angle': angle,
                'px_per_mm': px_per_mm,
                'aruco_id': target_aruco_id,
                'aruco_size': aruco_size,
                'detected': True
            }
            
            renderlist_objects = []
            if show_ejes:
                renderlist_objects.append({
                    'type': 'axes',
                    'name': f"{frame_type}_axes",
                    'position': frame_data['position'], # Usar la posición ya corregida
                    'angle': angle,
                    'color': color_ejes,
                    'length': 1000,
                    'frame': 'world',
                    'units': 'px'
                })
            
            from src.vision.frames_manager import get_global_overlay_manager
            overlay_manager = get_global_overlay_manager()
            frame_name = f"{frame_type}_frame"
            overlay_manager.update_frame(
                name=frame_name,
                offset=frame_data['position'],
                rotation=frame_data['angle'],
                px_per_mm=frame_data['px_per_mm']
            )
            
            return {
                'ok': True,
                'frame_data': frame_data,
                'renderlist_objects': renderlist_objects,
                'frame_source': 'detected'
            }
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'ok': False, 'error': str(e)}

def decidir_base_frame(gray_frame, scale_factor):
    return decidir_aruco_frame(gray_frame, scale_factor, "base")

def decidir_tool_frame(gray_frame, scale_factor):
    return decidir_aruco_frame(gray_frame, scale_factor, "tool")

def corregir_escala_resultados_aruco(result: Dict[str, Any], scale_factor: float) -> Dict[str, Any]:
    """
    Wrapper para escalar las coordenadas de un resultado de detección de ArUcos.
    Llama a la función correspondiente en aruco_manager.
    
    Args:
        result: Diccionario con el resultado de la detección.
        scale_factor: Factor de escala a aplicar (e.g., 0.5 para 50%).
        
    Returns:
        Diccionario con el resultado y las coordenadas escaladas a 100%.
    """
    if scale_factor == 1.0:
        return result
        
    from src.vision.aruco_manager import scale_detection_results
    return scale_detection_results(result, scale_factor)

def ubicar_centro_troqueladora(base_frame_data, overlay_manager, config):
    """
    Paso 3: Ubicar el centro de la troqueladora.
    """
    try:
        print("[vision_manager] 🎯 Paso 3: Ubicando centro de la troqueladora...")
        
        vision_config = config.get('vision', {})
        show_centro_troquel = vision_config.get('centro_troquel_show', False)
        
        if not show_centro_troquel:
            return {'ok': True, 'centro_data': None, 'renderlist_objects': []}
        
        colors = vision_config.get('colors', {})
        color_rgb = colors.get('centro_troquel', [255, 221, 0])
        color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])
        
        aruco_config = config.get('aruco', {})
        center_x_mm = aruco_config.get('center_x_mm', 35)
        center_y_mm = aruco_config.get('center_y_mm', 35)
        
        centro_data = {
            'position_mm': [center_x_mm, center_y_mm],
            'base_frame_data': base_frame_data
        }
        
        renderlist_objects = [{
            'type': 'circle',
            'name': "centro_troqueladora",
            'center_mm': [center_x_mm, center_y_mm],
            'radius_mm': 5,
            'color': color_bgr,
            'frame': 'base_frame',
            'units': 'mm'
        }]
        
        return {
            'ok': True,
            'centro_data': centro_data,
            'renderlist_objects': renderlist_objects
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'ok': False, 'error': str(e)}