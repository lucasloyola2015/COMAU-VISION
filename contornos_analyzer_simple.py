"""
Analizador de contornos sin emojis para Windows
"""

import cv2
import numpy as np
import math
from typing import List, Dict, Tuple, Optional

# ============================================================
# PARÁMETROS FIJOS DE CLASIFICACIÓN
# ============================================================
UMBRAL_CIRCULARIDAD = 90   # Porcentaje mínimo para considerar un agujero como redondo (0-100)
UMBRAL_AREA_GRANDE = 0.90  # Fracción del área máxima para clasificar como "Grande" (0.0-1.0)
MM_POR_PIXEL_DEFAULT = 0.1 # Relación milímetros por píxel por defecto


def pixeles_a_mm(pixeles: float, mm_por_pixel: float) -> float:
    """Convierte píxeles a milímetros"""
    return pixeles * mm_por_pixel


def pixeles2_a_mm2(pixeles2: float, mm_por_pixel: float) -> float:
    """Convierte píxeles cuadrados a milímetros cuadrados"""
    return pixeles2 * (mm_por_pixel ** 2)


def calcular_centroide(contour: np.ndarray) -> Optional[Tuple[float, float]]:
    """Calcula el centroide de un contorno"""
    M = cv2.moments(contour)
    if M['m00'] != 0:
        cx = int(M['m10'] / M['m00'])
        cy = int(M['m01'] / M['m00'])
        return (cx, cy)
    return None


def analizar_agujeros(holes: List, mm_por_pixel: float) -> List[Dict]:
    """Analiza todos los agujeros y los clasifica según circularidad y área"""
    if not holes:
        return []
    
    analisis = []
    area_maxima_circular = 0
    
    # Primer pase: calcular circularidad y encontrar el área circular más grande
    for hole in holes:
        area = cv2.contourArea(hole)
        perimeter = cv2.arcLength(hole, True)
        
        # MÉTODO MEJORADO: Usar ajuste de elipse para calcular circularidad
        if len(hole) >= 5:  # fitEllipse requiere mínimo 5 puntos
            try:
                # Ajustar elipse al contorno
                ellipse = cv2.fitEllipse(hole)
                (center, (MA, ma), angle_ellipse) = ellipse
                
                # Calcular circularidad basada en la elipse ajustada
                if MA > 0 and ma > 0:
                    circularity = min(MA, ma) / max(MA, ma)
                    circularity_percentage = circularity * 100
                else:
                    circularity_percentage = 0
            except:
                # Fallback al método simple si falla el ajuste de elipse
                if perimeter > 0:
                    circularity = 4 * math.pi * area / (perimeter * perimeter)
                    circularity_percentage = circularity * 100
                else:
                    circularity_percentage = 0
        else:
            # Método simple para contornos con menos de 5 puntos
            if perimeter > 0:
                circularity = 4 * math.pi * area / (perimeter * perimeter)
                circularity_percentage = circularity * 100
            else:
                circularity_percentage = 0
        
        # Calcular centroide
        centroide = calcular_centroide(hole)
        
        analisis.append({
            'contour': hole,
            'area_px': area,
            'area_mm2': pixeles2_a_mm2(area, mm_por_pixel),
            'perimeter_px': perimeter,
            'perimeter_mm': pixeles_a_mm(perimeter, mm_por_pixel),
            'circularity': circularity_percentage,
            'centroide_px': centroide
        })
        
        # Si es circular (> UMBRAL_CIRCULARIDAD), actualizar área máxima
        if circularity_percentage > UMBRAL_CIRCULARIDAD:
            area_maxima_circular = max(area_maxima_circular, area)
    
    # Calcular umbral del área para clasificar como "Grande"
    umbral_area_grande = area_maxima_circular * UMBRAL_AREA_GRANDE
    
    # Segundo pase: clasificar cada agujero
    for i, item in enumerate(analisis):
        circularity = item['circularity']
        area = item['area_px']
        
        # Clasificar según circularidad y área
        if circularity > UMBRAL_CIRCULARIDAD:
            # Es circular
            if area >= umbral_area_grande:
                item['clasificacion'] = 'Redondo Grande'
            else:
                item['clasificacion'] = 'Redondo Chico'
        else:
            # No es circular
            item['clasificacion'] = 'Irregular'
        
        item['id'] = i + 1
    
    return analisis


def encontrar_agujeros_extremos(analisis_agujeros: List[Dict]) -> Tuple[Optional[Tuple], Optional[Tuple]]:
    """Encuentra los dos agujeros grandes más extremos"""
    # Filtrar solo agujeros grandes
    agujeros_grandes = [item for item in analisis_agujeros if item['clasificacion'] == 'Redondo Grande']
    
    if len(agujeros_grandes) < 2:
        return None, None
    
    # Calcular centroides de todos los agujeros grandes
    centroides_con_datos = []
    for item in agujeros_grandes:
        centroide = item['centroide_px']
        if centroide:
            centroides_con_datos.append({
                'centroide': centroide,
                'item': item
            })
    
    if len(centroides_con_datos) < 2:
        return None, None
    
    # Encontrar los dos puntos más extremos (mayor distancia entre ellos)
    max_distancia = 0
    punto1, punto2 = None, None
    
    for i in range(len(centroides_con_datos)):
        for j in range(i + 1, len(centroides_con_datos)):
            p1 = centroides_con_datos[i]['centroide']
            p2 = centroides_con_datos[j]['centroide']
            distancia = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            
            if distancia > max_distancia:
                max_distancia = distancia
                punto1, punto2 = p1, p2
    
    return punto1, punto2


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
            if verbose:
                print("ANALISIS DE CONTORNOS Y MOMENTOS DE HU")
            if verbose:
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
        hu_moments = cv2.HuMoments(moments).flatten()
        
        # Calcular centroide y ángulo de orientación
        cx_px = moments['m10'] / moments['m00'] if moments['m00'] != 0 else 0
        cy_px = moments['m01'] / moments['m00'] if moments['m00'] != 0 else 0
        
        # Calcular ángulo de orientación
        angle = 0.5 * math.atan2(2 * moments['mu11'], moments['mu20'] - moments['mu02'])
        angle_degrees = math.degrees(angle)
        
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
            print(f"[contornos]   • Redondos Grandes: {redondos_grandes}")
            print(f"[contornos]   • Redondos Chicos: {redondos_chicos}")
            print(f"[contornos]   • Irregulares: {irregulares}")
        
        # Mostrar detalles de cada agujero
        if verbose and analisis_agujeros:
            print(f"\n[contornos] Analisis detallado:")
            print(f"[contornos] {'ID':<4} {'Area (mm²)':>12} {'Perimetro (mm)':>15} {'Circular.':>11} {'Clasificacion':>18}")
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
                'punto1_px': punto1,
                'punto2_px': punto2,
                'distancia_px': distancia_px,
                'distancia_mm': distancia_mm,
                'punto_medio_px': punto_medio
            }
            
            if verbose:
                print(f"[contornos] OK Linea de referencia calculada")
                print(f"[contornos]   Punto 1: {punto1} px")
                print(f"[contornos]   Punto 2: {punto2} px")
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
        if verbose:
            print("=" * 80)
        if verbose:
            print(f"OK Contorno principal: {pixeles2_a_mm2(main_area_px, mm_por_pixel):.2f} mm²")
        if verbose:
            print(f"OK Total agujeros: {len(holes)}")
        if verbose:
            print(f"OK Momentos de Hu: {len(hu_moments)} valores")
        if verbose:
            print(f"OK Factor conversion: {mm_por_pixel} mm/px")
        if verbose:
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
