# src/vision/vision_steps/step_5_refinement.py

import cv2
import numpy as np
import os

def _refinar_agujero_opencv(crop_agujero, index):
    """
    Función modular para calcular el centro preciso de un agujero usando OpenCV.
    """
    if crop_agujero is None or crop_agujero.size == 0:
        return None

    try:
        b_channel = crop_agujero[:, :, 0].astype(np.float32)
        g_channel = crop_agujero[:, :, 1].astype(np.float32)
        r_channel = crop_agujero[:, :, 2].astype(np.float32)
        
        factor_predominancia = 0.7
        es_azul = b_channel > (g_channel + r_channel) * factor_predominancia
        
        blue_mask = np.zeros_like(b_channel, dtype=np.uint8)
        blue_mask[es_azul] = 255
        
        debug_folder = "debug"
        if not os.path.exists(debug_folder):
            os.makedirs(debug_folder)
        cv2.imwrite(os.path.join(debug_folder, f"hole_mask_debug_{index}.jpg"), blue_mask)

        contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        
        largest_contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest_contour) < 10:
            return None
            
        img_contour_debug = crop_agujero.copy()
        cv2.drawContours(img_contour_debug, [largest_contour], -1, (255, 255, 0), 2)
        cv2.imwrite(os.path.join(debug_folder, f"hole_contour_debug_{index}.jpg"), img_contour_debug)

        if len(largest_contour) >= 5:
            ellipse = cv2.fitEllipse(largest_contour)
            center = (int(ellipse[0][0]), int(ellipse[0][1]))
            
            img_ellipse_debug = crop_agujero.copy()
            cv2.ellipse(img_ellipse_debug, ellipse, (0, 255, 255), 2)
            cv2.imwrite(os.path.join(debug_folder, f"hole_ellipse_debug_{index}.jpg"), img_ellipse_debug)
            
            return {'center': center, 'contour': largest_contour, 'ellipse': ellipse}
        else:
            moments = cv2.moments(largest_contour)
            if moments["m00"] != 0:
                center = (int(moments["m10"] / moments["m00"]), int(moments["m01"] / moments["m00"]))
                return {'center': center, 'contour': largest_contour, 'ellipse': None}
            return None

    except Exception as e:
        print(f"[vision_manager] ⚠️ Error en _refinar_agujero_opencv: {e}")
        return None

def calcular_metricas_y_segmento(centros_refinados, overlay_manager):
    """Paso 10: Calcula la línea de referencia y el punto medio a partir de los centros refinados."""
    try:
        print("[vision_manager] 📏 Paso 10: Calculando métricas y segmento...")
        if not centros_refinados or len(centros_refinados) < 2:
            return {'ok': True, 'renderlist_objects': []}

        centros_ordenados = sorted(centros_refinados, key=lambda p: p[0])
        p1 = centros_ordenados[0]
        p2 = centros_ordenados[-1]

        punto_medio = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)

        renderlist_objects = [
            {
                'type': 'line',
                'name': 'segmento_junta',
                'start': p1,
                'end': p2,
                'color': (255, 0, 0),
                'frame': 'world',
                'units': 'px'
            },
            {
                'type': 'circle',
                'name': 'centro_junta',
                'center_px': punto_medio,
                'radius_px': 8,
                'color': (255, 0, 0),
                'frame': 'world',
                'units': 'px'
            }
        ]

        return {'ok': True, 'renderlist_objects': renderlist_objects}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'ok': False, 'error': str(e)}