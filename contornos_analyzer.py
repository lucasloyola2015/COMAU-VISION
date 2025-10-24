"""
Analizador de Contornos y Agujeros para Juntas
==============================================

Basado en detector_contornos.py
Analiza formas, contornos y agujeros en imágenes de juntas.
"""

import cv2
import numpy as np
import math
from typing import Dict, List, Tuple, Optional

# ============================================================
# PARÁMETROS FIJOS DE CLASIFICACIÓN
# ============================================================
UMBRAL_CIRCULARIDAD = 90   # Porcentaje mínimo para considerar un agujero como redondo (0-100)
UMBRAL_AREA_GRANDE = 0.90  # Fracción del área máxima para clasificar como "Grande" (0.0-1.0)
MM_POR_PIXEL_DEFAULT = 0.1 # Relación milímetros por píxel por defecto


def calcular_angulo_orientacion(moments: Dict) -> float:
    """Calcula el ángulo de orientación principal de la forma"""
    try:
        mu20 = moments['mu20']
        mu02 = moments['mu02']
        mu11 = moments['mu11']
        
        if mu20 == mu02:
            angle = 0
        else:
            angle = 0.5 * math.atan2(2 * mu11, mu20 - mu02)
        
        return math.degrees(angle)
    except:
        return 0.0


def pixeles_a_mm(pixeles: float, mm_por_pixel: float) -> float:
    """Convierte una medida lineal de píxeles a milímetros (precisión 0.1mm)"""
    return round(pixeles * mm_por_pixel, 1)


def pixeles2_a_mm2(pixeles_cuadrados: float, mm_por_pixel: float) -> float:
    """Convierte un área de píxeles² a milímetros² (precisión 0.1mm²)"""
    return round(pixeles_cuadrados * (mm_por_pixel ** 2), 1)


def calcular_centroide(contour) -> Optional[Tuple[int, int]]:
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
                
                # Calcular relación de aspecto (aspect ratio)
                # Círculo perfecto: MA ≈ ma → ratio ≈ 1
                if MA > 0 and ma > 0:
                    aspect_ratio = min(MA, ma) / max(MA, ma)
                    circularity_percentage = aspect_ratio * 100
                else:
                    circularity_percentage = 0
            except:
                # Si falla fitEllipse, usar método tradicional
                if perimeter == 0 or area == 0:
                    circularity_percentage = 0
                else:
                    circularity = (4 * math.pi * area) / (perimeter * perimeter)
                    circularity_percentage = min(circularity * 100, 100)
        else:
            # Muy pocos puntos, usar método tradicional
            if perimeter == 0 or area == 0:
                circularity_percentage = 0
            else:
                circularity = (4 * math.pi * area) / (perimeter * perimeter)
                circularity_percentage = min(circularity * 100, 100)
        
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
    
    # Encontrar los dos más extremos calculando todas las distancias
    max_distancia = 0
    punto1 = None
    punto2 = None
    
    for i in range(len(centroides_con_datos)):
        for j in range(i + 1, len(centroides_con_datos)):
            c1 = centroides_con_datos[i]['centroide']
            c2 = centroides_con_datos[j]['centroide']
            
            # Calcular distancia euclidiana
            distancia = np.sqrt((c2[0] - c1[0])**2 + (c2[1] - c1[1])**2)
            
            if distancia > max_distancia:
                max_distancia = distancia
                punto1 = c1
                punto2 = c2
    
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
                print("ANÁLISIS DE CONTORNOS Y MOMENTOS DE HU")
            if verbose:
                print("=" * 80)
        
        # === PASO 1: Convertir a binario ===
        if verbose:
            print("\n[contornos] PASO 1: Binarización...")
        _, imagen_binaria = cv2.threshold(img_fondo_blanco, 127, 255, cv2.THRESH_BINARY_INV)
        if verbose:
            print(f"[contornos] ✓ Imagen binarizada")
        
        # === PASO 2: Detectar contornos con jerarquía ===
        if verbose:
            print("\n[contornos] PASO 2: Detección de contornos con jerarquía...")
        contours, hierarchy = cv2.findContours(imagen_binaria, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours or hierarchy is None:
            if verbose:
                print("[contornos] ⚠️ No se detectaron contornos")
            return {'ok': False, 'error': 'No se detectaron contornos'}
        
        if verbose:
            print(f"[contornos] ✓ {len(contours)} contornos detectados")
        
        # === PASO 3: Identificar contorno principal ===
        if verbose:
            print("\n[contornos] PASO 3: Identificando contorno principal...")
        main_contour_idx = -1
        max_area = 0
        
        for i, contour in enumerate(contours):
            parent = hierarchy[0][i][3]
            area = cv2.contourArea(contour)
            
            # Buscar el contorno más grande sin padre (contorno externo)
            if parent == -1 and area > max_area:
                max_area = area
                main_contour_idx = i
        
        if main_contour_idx == -1:
            if verbose:
                print("[contornos] ⚠️ No se encontró contorno principal")
            return {'ok': False, 'error': 'No se encontró contorno principal'}
        
        main_contour = contours[main_contour_idx]
        main_area_px = cv2.contourArea(main_contour)
        main_perimeter_px = cv2.arcLength(main_contour, True)
        
        # Calcular bounding box del contorno principal
        x, y, w, h = cv2.boundingRect(main_contour)
        bbox_width_px = w
        bbox_height_px = h
        
        if verbose:
            print(f"[contornos] ✓ Contorno principal: Área={main_area_px:.2f} px², Perímetro={main_perimeter_px:.2f} px")
            if verbose:
                print(f"[contornos]   Bounding Box: {bbox_width_px}x{bbox_height_px} px")
        
        # === PASO 4: Identificar agujeros internos (hijos del contorno principal) ===
        if verbose:
            print("\n[contornos] PASO 4: Identificando agujeros internos...")
        holes = []
        first_child = hierarchy[0][main_contour_idx][2]
        
        if first_child != -1:
            child_idx = first_child
            while child_idx != -1:
                holes.append(contours[child_idx])
                child_idx = hierarchy[0][child_idx][0]
        
        if verbose:
            print(f"[contornos] ✓ {len(holes)} agujeros detectados")
        
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
        
        if moments['m00'] == 0:
            if verbose:
                print("[contornos] ⚠️ No se pudieron calcular los momentos")
            return {'ok': False, 'error': 'No se pudieron calcular los momentos'}
        
        # Calcular momentos de Hu
        hu_moments = cv2.HuMoments(moments).flatten()
        
        # Calcular ángulo de orientación
        angle = calcular_angulo_orientacion(moments)
        
        # Calcular centroide
        cx_px = moments['m10'] / moments['m00']
        cy_px = moments['m01'] / moments['m00']
        
        if verbose:
            print(f"[contornos] ✓ Momentos de Hu calculados")
        if verbose:
            print(f"[contornos]   Centroide: ({cx_px:.2f}, {cy_px:.2f}) px")
        if verbose:
            print(f"[contornos]   Ángulo orientación: {angle:.2f}°")
        
        # === PASO 6: Análisis de agujeros ===
        if verbose:
            print("\n[contornos] PASO 6: Analizando agujeros...")
        analisis_agujeros = analizar_agujeros(holes, mm_por_pixel)
        
        # Estadísticas de clasificación
        redondos_grandes = sum(1 for item in analisis_agujeros if item['clasificacion'] == 'Redondo Grande')
        redondos_chicos = sum(1 for item in analisis_agujeros if item['clasificacion'] == 'Redondo Chico')
        irregulares = sum(1 for item in analisis_agujeros if item['clasificacion'] == 'Irregular')
        
        if verbose:
            print(f"[contornos] ✓ Clasificación de agujeros:")
        if verbose:
            print(f"[contornos]   • Redondos Grandes: {redondos_grandes}")
        if verbose:
            print(f"[contornos]   • Redondos Chicos: {redondos_chicos}")
        if verbose:
            print(f"[contornos]   • Irregulares: {irregulares}")
        
        # Tabla detallada
        if verbose:
            print(f"\n[contornos] Análisis detallado:")
        if verbose:
            print(f"[contornos] {'ID':<4} {'Área (mm²)':>12} {'Perímetro (mm)':>15} {'Circular.':>11} {'Clasificación':>18}")
        if verbose:
            print(f"[contornos] {'-'*65}")
        for item in analisis_agujeros:
            if verbose:
                print(f"[contornos] {item['id']:<4} {item['area_mm2']:>12.2f} {item['perimeter_mm']:>15.2f} {item['circularity']:>10.1f}% {item['clasificacion']:>18}")
        
        # === PASO 7: Línea de referencia ===
        if verbose:
            print("\n[contornos] PASO 7: Calculando línea de referencia...")
        punto1, punto2 = encontrar_agujeros_extremos(analisis_agujeros)
        
        linea_referencia = None
        if punto1 and punto2:
            distancia_px = np.sqrt((punto2[0] - punto1[0])**2 + (punto2[1] - punto1[1])**2)
            distancia_mm = pixeles_a_mm(distancia_px, mm_por_pixel)
            punto_medio = (
                (punto1[0] + punto2[0]) // 2,
                (punto1[1] + punto2[1]) // 2
            )
            
            linea_referencia = {
                'punto1_px': punto1,
                'punto2_px': punto2,
                'distancia_px': distancia_px,
                'distancia_mm': distancia_mm,
                'punto_medio_px': punto_medio
            }
            
            if verbose:
                print(f"[contornos] ✓ Línea de referencia calculada:")
            if verbose:
                print(f"[contornos]   Punto 1: {punto1} px")
            if verbose:
                print(f"[contornos]   Punto 2: {punto2} px")
            if verbose:
                print(f"[contornos]   Distancia: {distancia_mm:.2f} mm ({distancia_px:.2f} px)")
            if verbose:
                print(f"[contornos]   Punto medio: {punto_medio} px")
        else:
            if verbose:
                print(f"[contornos] ℹ️ No se pudo calcular línea de referencia (menos de 2 agujeros grandes)")
        
        # === RESULTADOS ===
        if verbose:
            print("\n" + "=" * 80)
        if verbose:
            print("RESUMEN DE ANÁLISIS")
        if verbose:
            print("=" * 80)
        if verbose:
            print(f"✓ Contorno principal: {pixeles2_a_mm2(main_area_px, mm_por_pixel):.2f} mm²")
        if verbose:
            print(f"✓ Total agujeros: {len(holes)}")
        if verbose:
            print(f"✓ Momentos de Hu: {len(hu_moments)} valores")
        if verbose:
            print(f"✓ Factor conversión: {mm_por_pixel} mm/px")
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
                'centroide_px': item['centroide_px'] if item['centroide_px'] else None
            })
        
        return {
            'ok': True,
            'contorno_principal': {
                'area_px': float(main_area_px),
                'area_mm2': float(pixeles2_a_mm2(main_area_px, mm_por_pixel)),
                'perimetro_px': float(main_perimeter_px),
                'perimetro_mm': float(pixeles_a_mm(main_perimeter_px, mm_por_pixel)),
                'angulo_orientacion': float(angle),
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
        print(f"[contornos] ❌ Error en análisis: {e}")
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
        
        # Superponer imagen original
        img_color = cv2.cvtColor(img_fondo_blanco, cv2.COLOR_GRAY2BGR)
        mask = img_fondo_blanco < 250
        vis_img[mask] = img_color[mask]
        
        # Dibujar contorno principal en VERDE
        if main_contour is not None:
            cv2.drawContours(vis_img, [main_contour], -1, (0, 255, 0), 1)
        
        # Rellenar agujeros con colores según clasificación
        if analisis_agujeros:
            for item in analisis_agujeros:
                clasificacion = item['clasificacion']
                hole = item['contour']
                
                # Definir color según clasificación (BGR)
                if clasificacion == "Redondo Grande":
                    hole_color = (255, 150, 0)     # Azul oscuro
                elif clasificacion == "Redondo Chico":
                    hole_color = (255, 230, 150)   # Celeste claro
                else:  # Irregular
                    hole_color = (150, 150, 255)   # Rosa/rojo claro
                
                # Rellenar agujero
                cv2.fillPoly(vis_img, [hole], hole_color)
                
                # Borde más oscuro
                border_color = tuple(int(c * 0.7) for c in hole_color)
                cv2.drawContours(vis_img, [hole], -1, border_color, 1)
        
        # Dibujar línea de referencia
        if linea_ref:
            punto1 = linea_ref['punto1_px']
            punto2 = linea_ref['punto2_px']
            punto_medio = linea_ref['punto_medio_px']
            
            # Dibujar línea ROJA entre los dos puntos
            cv2.line(vis_img, punto1, punto2, (0, 0, 255), 1)
            
            # Dibujar punto AMARILLO en el centro del segmento (más fino)
            cv2.circle(vis_img, punto_medio, 6, (0, 255, 255), -1)  # Relleno
            cv2.circle(vis_img, punto_medio, 6, (0, 180, 180), 1)   # Borde más oscuro
        
        return vis_img
    
    except Exception as e:
        print(f"[contornos] ❌ Error creando visualización: {e}")
        return None

