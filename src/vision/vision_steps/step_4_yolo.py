# src/vision/vision_steps/step_4_yolo.py

def hacer_crop_imagen(image, roi_rectangle, scale_factor):
    """Hacer crop de la imagen según ROI"""
    try:
        x = int(roi_rectangle['x'] * scale_factor)
        y = int(roi_rectangle['y'] * scale_factor)
        w = int(roi_rectangle['width'] * scale_factor)
        h = int(roi_rectangle['height'] * scale_factor)
        
        return image[y:y+h, x:x+w]
    except Exception as e:
        return image  # Retornar imagen original si hay error

def configurar_roi_frame(roi_data, roi_rectangle, base_frame_data, tool_frame_data, overlay_manager, config):
    """Configurar roi_frame"""
    try:
        from src.vision.frames_manager import get_global_overlay_manager
        overlay_manager = get_global_overlay_manager()
        
        # Configurar roi_frame
        overlay_manager.define_frame(
            "roi_frame",
            offset=(roi_rectangle['x'], roi_rectangle['y']),
            rotation=0.0,
            px_per_mm=(1.0, -1.0)
        )
        
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def configurar_junta_frame(junta_data, roi_rectangle, overlay_manager):
    """Configurar junta_frame"""
    try:
        from src.vision.frames_manager import get_global_overlay_manager
        overlay_manager = get_global_overlay_manager()
        
        # Configurar junta_frame
        overlay_manager.define_frame(
            "junta_frame",
            offset=(roi_rectangle['x'], roi_rectangle['y']),
            rotation=0.0,
            px_per_mm=(1.0, -1.0)
        )
        
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


import os
import cv2
from .step_utils import _scale_rect
from .step_5_refinement import _refinar_agujero_opencv

def detectar_junta_yolo(yolo_image_cropped, config, yolo_scale_factor, yolo_detector):
    """
    Paso 7: Detectar junta con YOLO usando imagen recortada.
    """
    try:
        print("[vision_manager] 📐 Paso 7: Detectando junta con YOLO...")
        
        vision_config = config.get('vision', {})
        use_boundingbox = vision_config.get('use_boundingbox', False)
        bbox_junta_show = vision_config.get('bbox_junta_show', False)
        
        if not use_boundingbox:
            return {'ok': True, 'junta_data': None, 'renderlist_objects': []}
        
        from src.vision import yolo_detector
        
        detection_model_path = vision_config.get('detection_model', 'models/detection_model.pt')
        if not yolo_detector.is_model_loaded('detection'):
            if not yolo_detector.load_model('detection', detection_model_path):
                return {'ok': False, 'error': f'No se pudo cargar el modelo YOLO desde {detection_model_path}'}
        
        resultado_yolo = yolo_detector.detect_gasket(yolo_image_cropped, conf_threshold=0.5)
        
        if resultado_yolo is None:
            return {'ok': True, 'junta_data': None, 'renderlist_objects': []}
        
        if isinstance(resultado_yolo, dict) and resultado_yolo.get('type') == 'obb':
            junta_data = {
                'bbox': resultado_yolo['bbox'], 'tipo': 'obb', 'center': resultado_yolo['center'],
                'size': resultado_yolo['size'], 'angle': resultado_yolo['angle'], 'points': resultado_yolo['points']
            }
        else:
            x1, y1, x2, y2 = resultado_yolo
            junta_data = {'bbox': (x1, y1, x2, y2), 'tipo': 'rect', 'width': x2 - x1, 'height': y2 - y1}
        
        x1, y1, x2, y2 = junta_data['bbox']
        img_width, img_height = yolo_image_cropped.shape[1], yolo_image_cropped.shape[0]
        
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(img_width, x2), min(img_height, y2)
        
        bbox_low_res = (x1, y1, x2, y2)
        bbox_in_roi = _scale_rect(bbox_low_res, 1.0 / yolo_scale_factor)
        
        renderlist_objects = []
        if bbox_junta_show:
            colors = vision_config.get('colors', {})
            color_rgb = colors.get('bbox_junta', [0, 255, 0])
            color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])
            
            bbox_points = [(bbox_in_roi[0], bbox_in_roi[1]), (bbox_in_roi[2], bbox_in_roi[1]),
                           (bbox_in_roi[2], bbox_in_roi[3]), (bbox_in_roi[0], bbox_in_roi[3])]
            
            renderlist_objects.append({'type': 'polygon', 'name': "junta_bbox", 'points': bbox_points,
                                       'color': color_bgr, 'frame': 'roi_frame', 'units': 'px'})
        
        return {
            'ok': True,
            'junta_data': {'bbox_in_roi': bbox_in_roi, 'tipo': junta_data['tipo']},
            'renderlist_objects': renderlist_objects
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'ok': False, 'error': str(e)}

def detectar_agujeros_yolo(yolo_image_cropped, opencv_image_cropped, roi_rectangle, junta_data, config, yolo_scale_factor, use_boundingbox):
    """
    Paso 9: Detectar agujeros con YOLO.
    """
    try:
        print("[vision_manager] 🕳️ Paso 9: Detectando agujeros con YOLO...")

        vision_config = config.get('vision', {})
        bbox_holes_show = vision_config.get('bbox_holes_show', False)
        elipses_show = vision_config.get('elipses_show', False)

        # Obtener opencv_scale_factor
        scale_opencv = vision_config.get('resolution_scale_opencv', 100)
        opencv_scale_factor = 100.0 / scale_opencv if scale_opencv != 100 else 1.0

        # Detección de agujeros con YOLO
        from src.vision import yolo_detector
        
        holes_model_path = vision_config.get('holes_model', 'models/holes_model.pt')
        if not yolo_detector.is_model_loaded('holes'):
            if not yolo_detector.load_model('holes', holes_model_path):
                return {'ok': False, 'error': f'No se pudo cargar el modelo de agujeros: {holes_model_path}'}

        detecciones_yolo = yolo_detector.detect_holes_bboxes(yolo_image_cropped, conf_threshold=0.5)
        if not detecciones_yolo:
            return {'ok': True, 'centros_refinados': [], 'renderlist_objects': []}

        print(f"[vision_manager] ✅ {len(detecciones_yolo)} agujeros detectados por YOLO.")
        print(f"[vision_manager] 🔍 bbox_holes_show={bbox_holes_show}, elipses_show={elipses_show}")

        renderlist_objects = []
        centros_refinados = []

        for i, deteccion in enumerate(detecciones_yolo):
            bbox = deteccion['bbox']
            x1, y1, x2, y2 = bbox
            
            # Dibujar bbox de YOLO holes si está habilitado
            if bbox_holes_show:
                colors = vision_config.get('colors', {})
                color_rgb = colors.get('bbox_holes', [255, 0, 0])
                color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])
                
                # Escalar bbox a coordenadas de ROI
                bbox_x1 = x1 / yolo_scale_factor
                bbox_y1 = y1 / yolo_scale_factor
                bbox_x2 = x2 / yolo_scale_factor
                bbox_y2 = y2 / yolo_scale_factor
                
                bbox_points = [(bbox_x1, bbox_y1), (bbox_x2, bbox_y1), 
                              (bbox_x2, bbox_y2), (bbox_x1, bbox_y2)]
                
                renderlist_objects.append({
                    'type': 'polygon',
                    'name': f"hole_bbox_{i}",
                    'points': bbox_points,
                    'color': color_bgr,
                    'frame': 'roi_frame',
                    'units': 'px'
                })

            # Calcular coordenadas en la imagen opencv
            width = x2 - x1
            height = y2 - y1
            padding_x = width * 0.10
            padding_y = height * 0.10

            img_h, img_w = opencv_image_cropped.shape[:2]
            crop_x1 = int(max(0, (x1 / yolo_scale_factor) * opencv_scale_factor - padding_x))
            crop_y1 = int(max(0, (y1 / yolo_scale_factor) * opencv_scale_factor - padding_y))
            crop_x2 = int(min(img_w, (x2 / yolo_scale_factor) * opencv_scale_factor + padding_x))
            crop_y2 = int(min(img_h, (y2 / yolo_scale_factor) * opencv_scale_factor + padding_y))

            crop_agujero = opencv_image_cropped[crop_y1:crop_y2, crop_x1:crop_x2]
            
            # Refinar agujero con OpenCV (esto guarda las imágenes de debug)
            resultado_opencv = _refinar_agujero_opencv(crop_agujero, i)

            if resultado_opencv:
                center_local = (resultado_opencv['center'][0] + crop_x1, resultado_opencv['center'][1] + crop_y1)
                center_in_roi = (center_local[0] / opencv_scale_factor, center_local[1] / opencv_scale_factor)
                center_refinado_abs = (center_in_roi[0] + roi_rectangle['x'], center_in_roi[1] + roi_rectangle['y'])
                centros_refinados.append(center_refinado_abs)
                
                # Dibujar elipse si está habilitada
                if elipses_show and resultado_opencv.get('ellipse'):
                    colors = vision_config.get('colors', {})
                    color_rgb = colors.get('elipses', [0, 0, 255])
                    color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])
                    
                    ellipse = resultado_opencv['ellipse']
                    center_ellipse = ellipse[0]
                    axes = ellipse[1]
                    angle = ellipse[2]
                    
                    # Convertir elipse a coordenadas de ROI
                    center_x_roi = center_in_roi[0]
                    center_y_roi = center_in_roi[1]
                    axes_x = (axes[0] / opencv_scale_factor) / 2  # OpenCV devuelve diámetros, necesitamos radios
                    axes_y = (axes[1] / opencv_scale_factor) / 2  # OpenCV devuelve diámetros, necesitamos radios
                    
                    renderlist_objects.append({
                        'type': 'ellipse',
                        'name': f"elipse_centro_{i}",
                        'ellipse_data': ((center_x_roi, center_y_roi), (axes_x, axes_y), angle),
                        'color': color_bgr,
                        'frame': 'roi_frame',
                        'units': 'px'
                    })

        print(f"[vision_manager] 🎨 Total objetos en renderlist_objects: {len(renderlist_objects)}")
        for i, obj in enumerate(renderlist_objects):
            print(f"[vision_manager]   - Objeto {i}: type={obj.get('type')}, name={obj.get('name')}")
        
        return {
            'ok': True,
            'centros_refinados': centros_refinados,
            'renderlist_objects': renderlist_objects
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'ok': False, 'error': str(e)}