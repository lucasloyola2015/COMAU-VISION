# src/vision/vision_steps/step_3_roi.py

def dibujar_roi(tool_frame_data, overlay_manager, config, px_per_mm):
    """Dibujar ROI"""
    try:
        vision_config = config.get('vision', {})
        roi_enabled = vision_config.get('roi_enabled', False)
        
        if not roi_enabled:
            return {'ok': True, 'roi_data': None, 'renderlist_objects': []}
        
        # TODO: Implementar lógica de ROI
        return {
            'ok': True,
            'roi_data': {},
            'renderlist_objects': []
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def crear_roi_rectangle_completo(cv2_frame):
    """Crear ROI rectangle con el tamaño completo de la imagen"""
    h, w = cv2_frame.shape[:2]
    return {
        'x': 0,
        'y': 0,
        'width': w,
        'height': h
    }

def redimensionar_roi_rectangle(roi_rectangle, roi_result, overlay_manager):
    """Redimensionar roi_rectangle al tamaño del ROI"""
    # TODO: Implementar lógica de redimensionamiento
    return roi_rectangle

import cv2
import os
from datetime import datetime

def dibujar_roi(tool_frame_data, overlay_manager, config, base_px_per_mm=None):
    """
    Paso 5: Dibujar ROI respecto al ToolFrame.
    """
    try:
        print("[vision_manager] 📐 Paso 5: Dibujando ROI...")
        
        vision_config = config.get('vision', {})
        roi_enabled = vision_config.get('use_roi', False)
        roi_show = vision_config.get('roi_show', False)
        
        if not roi_enabled:
            return {'ok': True, 'roi_data': None, 'renderlist_objects': []}
        
        colors = vision_config.get('colors', {})
        color_rgb = colors.get('roi', [255, 0, 0])
        color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])
        
        zoom_x_percent = vision_config.get('roi_zoom_x_percent', 110)
        zoom_y_percent = vision_config.get('roi_zoom_y_percent', 130)
        offset_y_mm = vision_config.get('roi_offset_y_mm', -80)
        
        width_base = 100
        height_base = 100
        
        zoom_x = zoom_x_percent / 100.0
        zoom_y = zoom_y_percent / 100.0
        width_amplified = width_base * zoom_x
        height_amplified = height_base * zoom_y
        
        total_offset_y = (height_amplified / 2) + abs(offset_y_mm)
        
        roi_data = {
            'width_mm': width_amplified,
            'height_mm': height_amplified,
            'offset_y_mm': total_offset_y,
            'zoom_x': zoom_x,
            'zoom_y': zoom_y,
            'tool_reference': tool_frame_data['position']
        }
        
        renderlist_objects = []
        if roi_show:
            half_width = width_amplified / 2
            half_height = height_amplified / 2
            
            roi_points = [
                (-half_width, -total_offset_y - half_height),
                (half_width, -total_offset_y - half_height),
                (half_width, -total_offset_y + half_height),
                (-half_width, -total_offset_y + half_height)
            ]
            
            renderlist_objects.append({
                'type': 'polygon', 'name': "roi_rectangle", 'points': roi_points,
                'color': color_bgr, 'frame': 'tool_frame', 'units': 'mm'
            })
        
        return {
            'ok': True,
            'roi_data': roi_data,
            'renderlist_objects': renderlist_objects
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'ok': False, 'error': str(e)}

def crear_roi_rectangle_completo(imagen_cv2):
    """
    Crear roi_rectangle con el tamaño completo de la imagen.
    """
    try:
        height, width = imagen_cv2.shape[:2]
        return {'x': 0, 'y': 0, 'width': width, 'height': height, 'tipo': 'completo'}
    except Exception as e:
        return {'x': 0, 'y': 0, 'width': 0, 'height': 0, 'tipo': 'error'}

def redimensionar_roi_rectangle(roi_rectangle, roi_result, overlay_manager):
    """
    Redimensionar roi_rectangle al tamaño del ROI si está activo.
    """
    try:
        roi_data = roi_result.get('roi_data')
        if not roi_data:
            return roi_rectangle
        
        roi_object = overlay_manager.get_object(target_frame="world", name="roi_rectangle")
        if roi_object and 'coordinates' in roi_object:
            roi_points = roi_object['coordinates']['points']
            x_coords = [p[0] for p in roi_points]
            y_coords = [p[1] for p in roi_points]
            
            roi_x = int(min(x_coords))
            roi_y = int(min(y_coords))
            roi_width_px = int(max(x_coords) - roi_x)
            roi_height_px = int(max(y_coords) - roi_y)
            
            if roi_width_px > 0 and roi_height_px > 0:
                roi_rectangle['x'] = max(0, roi_x)
                roi_rectangle['y'] = max(0, roi_y)
                roi_rectangle['width'] = min(roi_width_px, roi_rectangle['width'] - roi_rectangle['x'])
                roi_rectangle['height'] = min(roi_height_px, roi_rectangle['height'] - roi_rectangle['y'])
                roi_rectangle['tipo'] = 'roi'
        
        return roi_rectangle
    except Exception as e:
        print(f"[vision_manager] ❌ Error redimensionando roi_rectangle: {e}")
        return roi_rectangle

def hacer_crop_imagen(imagen_cv2, roi_rectangle, scale_factor=1.0):
    """
    Hacer crop de la imagen usando roi_rectangle.
    """
    try:
        x = int(roi_rectangle['x'] * scale_factor)
        y = int(roi_rectangle['y'] * scale_factor)
        width = int(roi_rectangle['width'] * scale_factor)
        height = int(roi_rectangle['height'] * scale_factor)
        
        imagen_recortada = imagen_cv2[y:y+height, x:x+width]
        
        debug_folder = "debug"
        if not os.path.exists(debug_folder):
            os.makedirs(debug_folder)
        
        filename = "roi_crop_debug.jpg"
        filepath = os.path.join(debug_folder, filename)
        cv2.imwrite(filepath, imagen_recortada)
        
        info_filename = "roi_info_debug.txt"
        info_filepath = os.path.join(debug_folder, info_filename)
        with open(info_filepath, 'w') as f:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            f.write(f"ROI Rectangle Info - {timestamp}\n")
            f.write(f"================================\n")
            f.write(f"Tipo: {roi_rectangle.get('tipo', 'unknown')}\n")
            f.write(f"Posición: ({x}, {y})\n")
            f.write(f"Dimensiones: {width}x{height}\n")
            f.write(f"Imagen original: {imagen_cv2.shape[1]}x{imagen_cv2.shape[0]}\n")
            f.write(f"Imagen recortada: {imagen_recortada.shape[1]}x{imagen_recortada.shape[0]}\n")
        
        return imagen_recortada
    except Exception as e:
        print(f"[vision_manager] ❌ Error haciendo crop: {e}")
        return imagen_cv2