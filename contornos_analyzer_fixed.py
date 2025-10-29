"""
Análisis de contornos y momentos de Hu para juntas
Versión corregida sin emojis y con detección de agujeros por jerarquía
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional

# Constantes
MM_POR_PIXEL_DEFAULT = 0.1
UMBRAL_CIRCULARIDAD = 80.0
UMBRAL_AREA_GRANDE = 100.0  # mm²

def pixeles_a_mm(pixeles: float, mm_por_pixel: float) -> float:
    """Convierte píxeles a milímetros"""
    return pixeles * mm_por_pixel

def pixeles2_a_mm2(pixeles2: float, mm_por_pixel: float) -> float:
    """Convierte píxeles cuadrados a milímetros cuadrados"""
    return pixeles2 * (mm_por_pixel ** 2)

def calcular_centroide_y_orientacion(moments: Dict, contour: np.ndarray) -> Tuple[float, float, float]:
    """Calcula centroide y ángulo de orientación de un contorno"""
    if moments['m00'] != 0:
        cx = moments['m10'] / moments['m00']
        cy = moments['m01'] / moments['m00']
    else:
        cx = cy = 0.0
    
    # Calcular ángulo de orientación usando el segundo momento central
    mu20 = moments['mu20']
    mu02 = moments['mu02']
    mu11 = moments['mu11']
    
    if mu20 != mu02:
        angle_rad = 0.5 * np.arctan2(2 * mu11, mu20 - mu02)
        angle_degrees = np.degrees(angle_rad)
    else:
        angle_degrees = 0.0
    
    return float(cx), float(cy), float(angle_degrees)

def analizar_agujeros(holes: List[np.ndarray], mm_por_pixel: float) -> List[Dict]:
    """Analiza una lista de agujeros y los clasifica"""
    analisis = []
    
    for i, hole in enumerate(holes):
        area_px = cv2.contourArea(hole)
        perimeter_px = cv2.arcLength(hole, True)
        area_mm2 = pixeles2_a_mm2(area_px, mm_por_pixel)
        perimeter_mm = pixeles_a_mm(perimeter_px, mm_por_pixel)
        
        # Calcular circularidad
        if perimeter_px > 0:
            circularity = (4 * np.pi * area_px) / (perimeter_px ** 2) * 100
        else:
            circularity = 0.0
        
        # Clasificar agujero
        if area_mm2 >= UMBRAL_AREA_GRANDE and circularity >= UMBRAL_CIRCULARIDAD:
            clasificacion = 'Redondo Grande'
        elif circularity >= UMBRAL_CIRCULARIDAD:
            clasificacion = 'Redondo Chico'
        else:
            clasificacion = 'Irregular'
        
        # Calcular centroide
        moments = cv2.moments(hole)
        if moments['m00'] != 0:
            cx = moments['m10'] / moments['m00']
            cy = moments['m01'] / moments['m00']
        else:
            cx = cy = 0.0
        
        analisis.append({
            'id': i + 1,
            'area_px': float(area_px),
            'area_mm2': float(area_mm2),
            'perimeter_px': float(perimeter_px),
            'perimeter_mm': float(perimeter_mm),
            'circularity': float(circularity),
            'clasificacion': clasificacion,
            'centroide_px': (float(cx), float(cy)),
            'contour': hole
        })
    
    return analisis

def encontrar_agujeros_extremos(analisis_agujeros: List[Dict]) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
    """Encuentra los dos agujeros más extremos para calcular línea de referencia"""
    agujeros_grandes = [a for a in analisis_agujeros if a['clasificacion'] == 'Redondo Grande']
    
    if len(agujeros_grandes) < 2:
        return None, None
    
    # Encontrar agujeros con coordenadas x mínima y máxima
    agujero_izq = min(agujeros_grandes, key=lambda a: a['centroide_px'][0])
    agujero_der = max(agujeros_grandes, key=lambda a: a['centroide_px'][0])
    
    return agujero_izq['centroide_px'], agujero_der['centroide_px']

def analizar_imagen_completa(img_fondo_blanco: np.ndarray, mm_por_pixel: float = MM_POR_PIXEL_DEFAULT, verbose: bool = True) -> Dict:
    """
    Analiza una imagen de junta completa (fondo blanco)
    
    Args:
        img_fondo_blanco: Imagen en escala de grises con fondo blanco
        mm_por_pixel: Factor de conversión píxeles a milímetros
    
    Returns:
        Diccionario con todos los datos del análisis
    """
    try:
        if verbose:
            print("\n" + "=" * 80)
            print("ANALISIS DE CONTORNOS Y MOMENTOS DE HU")
            print("=" * 80)
        
        # === PASO 1: Convertir a binario ===
        if verbose:
            print("\n[contornos] PASO 1: Binarizacion...")
        _, imagen_binaria = cv2.threshold(img_fondo_blanco, 127, 255, cv2.THRESH_BINARY_INV)
        if verbose:
            print(f"[contornos] OK Imagen binarizada")
        
        # === PASO 2: Detectar contornos ===
        if verbose:
            print("\n[contornos] PASO 2: Deteccion de contornos...")
        contours, hierarchy = cv2.findContours(imagen_binaria, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            if verbose:
                print("[contornos] WARNING: No se detectaron contornos")
            return {'ok': False, 'error': 'No se detectaron contornos'}
        
        if verbose:
            print(f"[contornos] OK {len(contours)} contornos detectados")
        
        # === PASO 3: Identificar contorno principal (el de mayor área) ===
        if verbose:
            print("\n[contornos] PASO 3: Identificando contorno principal...")
        
        # Encontrar el contorno de mayor área (contorno principal)
        main_contour_idx = 0
        max_area = 0
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if area > max_area:
                max_area = area
                main_contour_idx = i
        
        main_contour = contours[main_contour_idx]
        main_area_px = cv2.contourArea(main_contour)
        main_perimeter_px = cv2.arcLength(main_contour, True)
        
        # Calcular bounding box del contorno principal
        x, y, w, h = cv2.boundingRect(main_contour)
        bbox_width_px = w
        bbox_height_px = h
        
        if verbose:
            print(f"[contornos] OK Contorno principal: Area={main_area_px:.2f} px², Perimetro={main_perimeter_px:.2f} px")
            print(f"[contornos]   Bounding Box: {bbox_width_px}x{bbox_height_px} px")
        
        # === PASO 4: Identificar agujeros (hijos del contorno principal) ===
        if verbose:
            print("\n[contornos] PASO 4: Identificando agujeros por jerarquia...")
        
        holes = []
        
        # Buscar agujeros como hijos del contorno principal
        first_child = hierarchy[0][main_contour_idx][2]  # Primer hijo
        
        if verbose:
            print(f"[contornos] Primer hijo del contorno principal: {first_child}")
        
        if first_child != -1:
            child_idx = first_child
            while child_idx != -1:
                area = cv2.contourArea(contours[child_idx])
                if verbose:
                    print(f"[contornos]   Agujero {len(holes)+1}: contorno {child_idx}, area {area:.1f} px²")
                holes.append(contours[child_idx])
                child_idx = hierarchy[0][child_idx][0]  # Siguiente hermano
        
        if verbose:
            print(f"[contornos] OK {len(holes)} agujeros detectados")
        
        # === PASO 5: Calcular momentos invariantes de Hu ===
        if verbose:
            print("\n[contornos] PASO 5: Calculando momentos de Hu...")
        # Crear máscara de la forma (contorno principal - agujeros)
        mask = np.zeros(img_fondo_blanco.shape, dtype=np.uint8)
        cv2.fillPoly(mask, [main_contour], 255)
        
        for hole in holes:
            cv2.fillPoly(mask, [hole], 0)
        
        # Calcular momentos
        moments = cv2.moments(mask)
        
        # Calcular centroide y ángulo de orientación
        cx_px, cy_px, angle_degrees = calcular_centroide_y_orientacion(moments, main_contour)
        
        hu_moments = cv2.HuMoments(moments).flatten()
        
        if verbose:
            print(f"[contornos] OK Momentos de Hu calculados")
            print(f"[contornos]   Centroide: ({cx_px:.2f}, {cy_px:.2f}) px")
            print(f"[contornos]   Angulo orientacion: {angle_degrees:.2f}°")
        
        # === PASO 6: Análisis de agujeros ===
        if verbose:
            print("\n[contornos] PASO 6: Analizando agujeros...")
        analisis_agujeros = analizar_agujeros(holes, mm_por_pixel)
        
        # Estadísticas de clasificación
        redondos_grandes = sum(1 for item in analisis_agujeros if item['clasificacion'] == 'Redondo Grande')
        redondos_chicos = sum(1 for item in analisis_agujeros if item['clasificacion'] == 'Redondo Chico')
        irregulares = sum(1 for item in analisis_agujeros if item['clasificacion'] == 'Irregular')
        
        if verbose:
            print(f"[contornos] OK Clasificacion de agujeros:")
            print(f"[contornos]   Redondos Grandes: {redondos_grandes}")
            print(f"[contornos]   Redondos Chicos: {redondos_chicos}")
            print(f"[contornos]   Irregulares: {irregulares}")
        
        if verbose and analisis_agujeros:
            print(f"\n[contornos] Analisis detallado:")
            print(f"[contornos] {'ID':<4} {'Area (mm)':>12} {'Perimetro (mm)':>15} {'Circular.':>11} {'Clasificacion':>18}")
            print(f"[contornos] {'-'*65}")
        for item in analisis_agujeros:
            if verbose:
                print(f"[contornos] {item['id']:<4} {item['area_mm2']:>12.2f} {item['perimeter_mm']:>15.2f} {item['circularity']:>10.1f}% {item['clasificacion']:>18}")
        
        # === PASO 7: Línea de referencia ===
        if verbose:
            print("\n[contornos] PASO 7: Calculando linea de referencia...")
        punto1, punto2 = encontrar_agujeros_extremos(analisis_agujeros)
        
        linea_referencia = None
        if punto1 and punto2:
            distancia_px = np.sqrt((punto2[0] - punto1[0])**2 + (punto2[1] - punto1[1])**2)
            distancia_mm = pixeles_a_mm(distancia_px, mm_por_pixel)
            
            punto_medio = ((punto1[0] + punto2[0]) / 2, (punto1[1] + punto2[1]) / 2)
            
            linea_referencia = {
                'punto1_px': (float(punto1[0]), float(punto1[1])),
                'punto2_px': (float(punto2[0]), float(punto2[1])),
                'distancia_px': float(distancia_px),
                'distancia_mm': float(distancia_mm),
                'punto_medio_px': (float(punto_medio[0]), float(punto_medio[1]))
            }
            if verbose:
                print(f"[contornos] OK Linea de referencia calculada")
                print(f"[contornos]   Distancia: {distancia_mm:.2f} mm ({distancia_px:.2f} px)")
                print(f"[contornos]   Punto medio: {punto_medio} px")
        else:
            if verbose:
                print(f"[contornos] INFO: No se pudo calcular linea de referencia (menos de 2 agujeros grandes)")
        
        # === RESULTADOS ===
        if verbose:
            print("\n" + "=" * 80)
            print("RESULTADOS FINALES")
            print("=" * 80)
            print(f"OK Contorno principal: {pixeles2_a_mm2(main_area_px, mm_por_pixel):.2f} mm²")
            print(f"OK Total agujeros: {len(holes)}")
            print(f"OK Momentos de Hu: {len(hu_moments)} valores")
            print(f"OK Factor conversion: {mm_por_pixel} mm/px")
            print("=" * 80 + "\n")
        
        # Preparar datos serializables (sin contornos OpenCV)
        agujeros_serializables = []
        for item in analisis_agujeros:
            agujeros_serializables.append({
                'id': item['id'],
                'area_px': float(item['area_px']),
                'area_mm2': float(item['area_mm2']),
                'perimeter_px': float(item['perimeter_px']),
                'perimeter_mm': float(item['perimeter_mm']),
                'circularity': float(item['circularity']),
                'clasificacion': item['clasificacion'],
                'centroide_px': item['centroide_px']
            })
        
        return {
            'ok': True,
            'contorno_principal': {
                'area_px': float(main_area_px),
                'area_mm2': float(pixeles2_a_mm2(main_area_px, mm_por_pixel)),
                'perimetro_px': float(main_perimeter_px),
                'perimetro_mm': float(pixeles_a_mm(main_perimeter_px, mm_por_pixel)),
                'angulo_orientacion': float(angle_degrees),
                'centroide_px': (float(cx_px), float(cy_px)),
                'centroide_mm': (float(pixeles_a_mm(cx_px, mm_por_pixel)), float(pixeles_a_mm(cy_px, mm_por_pixel))),
                'bbox_width_px': float(bbox_width_px),
                'bbox_height_px': float(bbox_height_px),
                'bbox_width_mm': float(pixeles_a_mm(bbox_width_px, mm_por_pixel)),
                'bbox_height_mm': float(pixeles_a_mm(bbox_height_px, mm_por_pixel))
            },
            'momentos_hu': [float(h) for h in hu_moments],
            'agujeros': agujeros_serializables,
            'linea_referencia': linea_referencia,
            'parametros': {
                'mm_por_pixel': float(mm_por_pixel),
                'umbral_circularidad': UMBRAL_CIRCULARIDAD,
                'umbral_area_grande': UMBRAL_AREA_GRANDE
            },
            # Datos para visualización (contornos originales)
            '_visualization_data': {
                'main_contour': main_contour,
                'analisis_agujeros': analisis_agujeros  # Incluye contornos OpenCV
            }
        }
    
    except Exception as e:
        print(f"[contornos] ERROR: Error en analisis: {e}")
        import traceback
        traceback.print_exc()
        return {'ok': False, 'error': str(e)}

def crear_visualizacion(img_fondo_blanco: np.ndarray, datos_analisis: Dict) -> Optional[np.ndarray]:
    """
    Crea la visualización con contornos y agujeros coloreados
    
    Args:
        img_fondo_blanco: Imagen original en escala de grises con fondo blanco
        datos_analisis: Resultado del análisis completo
    
    Returns:
        Imagen BGR con visualización o None si hay error
    """
    try:
        if not datos_analisis.get('ok') or '_visualization_data' not in datos_analisis:
            return None
        
        vis_data = datos_analisis['_visualization_data']
        main_contour = vis_data['main_contour']
        analisis_agujeros = vis_data['analisis_agujeros']
        linea_ref = datos_analisis.get('linea_referencia')
        
        # Crear imagen con fondo gris claro
        vis_img = np.full((img_fondo_blanco.shape[0], img_fondo_blanco.shape[1], 3), (240, 240, 240), dtype=np.uint8)
        
        # Convertir imagen original a BGR para el fondo
        if len(img_fondo_blanco.shape) == 2:
            vis_img = cv2.cvtColor(img_fondo_blanco, cv2.COLOR_GRAY2BGR)
        
        # Dibujar contorno principal en VERDE
        if main_contour is not None:
            cv2.drawContours(vis_img, [main_contour], -1, (0, 255, 0), 2)
        
        # Rellenar agujeros con colores según clasificación
        if analisis_agujeros:
            for item in analisis_agujeros:
                clasificacion = item['clasificacion']
                hole = item['contour']
                
                # Asignar colores según clasificación
                if clasificacion == 'Redondo Grande':
                    color = (0, 0, 255)  # ROJO para agujeros grandes
                elif clasificacion == 'Redondo Chico':
                    color = (255, 0, 255)  # MAGENTA para agujeros chicos
                else:  # Irregular
                    color = (0, 165, 255)  # NARANJA para irregulares
                
                # Rellenar agujero
                cv2.fillPoly(vis_img, [hole], color)
                # Dibujar borde
                cv2.drawContours(vis_img, [hole], -1, (0, 0, 0), 1)
        
        # Dibujar línea de referencia si existe
        if linea_ref and 'punto1_px' in linea_ref and 'punto2_px' in linea_ref:
            p1 = (int(linea_ref['punto1_px'][0]), int(linea_ref['punto1_px'][1]))
            p2 = (int(linea_ref['punto2_px'][0]), int(linea_ref['punto2_px'][1]))
            cv2.line(vis_img, p1, p2, (255, 0, 0), 3)  # AZUL para línea de referencia
            
            # Dibujar puntos extremos
            cv2.circle(vis_img, p1, 5, (255, 0, 0), -1)
            cv2.circle(vis_img, p2, 5, (255, 0, 0), -1)
        
        return vis_img
        
    except Exception as e:
        print(f"[visualizacion] ERROR: {e}")
        return None
