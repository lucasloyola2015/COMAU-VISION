# validaciones_geometricas.py
"""
Validaciones Geométricas - COMAU-VISION
========================================

Módulo que contiene todas las validaciones geométricas para el análisis de juntas.
Cada función es simple, hace UNA sola validación y retorna un diccionario con resultados.

Validaciones implementadas:
1. Centros múltiples: Verifica consistencia del centro calculado por pares simétricos
2. Colinealidad: Verifica que todos los pistones estén en línea recta
3. Espaciado uniforme: Verifica que el espaciado entre pistones sea consistente
"""

import numpy as np

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None
    OPENCV_AVAILABLE = False


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def validar_todo(datos_agujeros, datos_aruco, metricas):
    """
    Ejecuta todas las validaciones geométricas.
    
    Args:
        datos_agujeros: Lista de agujeros detectados
        datos_aruco: Datos de calibración ArUco
        metricas: Métricas calculadas (línea de referencia, etc.)
    
    Returns:
        dict: {
            'centros_multiples': {...},
            'colinealidad': {...},
            'espaciado_uniforme': {...},
            'todas_ok': bool
        }
    """
    
    # Verificar que tengamos calibración
    if not datos_aruco or not datos_aruco.get('px_per_mm'):
        return {
            'error': 'No hay calibración ArUco',
            'todas_ok': False
        }
    
    px_per_mm = datos_aruco['px_per_mm']
    centros = metricas.get('centros_ordenados', [])
    
    if len(centros) < 2:
        return {
            'error': 'Insuficientes pistones para validaciones',
            'todas_ok': False
        }
    
    # Cargar umbrales de configuración
    import camera_manager
    config = camera_manager.load_config()
    vision_config = config.get('vision', {})
    
    umbral_centros_mm = vision_config.get('umbral_centros_mm', 3.0)
    umbral_colinealidad_mm = vision_config.get('umbral_colinealidad_mm', 2.0)
    umbral_espaciado_cv = vision_config.get('umbral_espaciado_cv', 0.05)
    
    print(f"[validaciones] Ejecutando validaciones con {len(centros)} pistones")
    print(f"[validaciones] Umbrales: centros={umbral_centros_mm}mm, colinealidad={umbral_colinealidad_mm}mm, CV={umbral_espaciado_cv}")
    
    # Ejecutar las 3 validaciones
    val_centros = validar_centros_multiples(centros, px_per_mm, umbral_centros_mm)
    val_colinealidad = validar_colinealidad(centros, px_per_mm, umbral_colinealidad_mm)
    val_espaciado = validar_espaciado_uniforme(centros, px_per_mm, umbral_espaciado_cv)
    
    # Resultado final
    todas_ok = val_centros['ok'] and val_colinealidad['ok'] and val_espaciado['ok']
    
    print(f"[validaciones] Resultado: {'✓ TODAS OK' if todas_ok else '✗ ALGUNA FALLÓ'}")
    
    return {
        'centros_multiples': val_centros,
        'colinealidad': val_colinealidad,
        'espaciado_uniforme': val_espaciado,
        'todas_ok': todas_ok
    }


# ============================================================
# VALIDACIÓN 1: CENTROS MÚLTIPLES
# ============================================================

def validar_centros_multiples(centros, px_per_mm, umbral_mm):
    """
    Valida que el centro calculado por pares simétricos sea consistente.
    
    Estrategia:
    1. Ordena centros de izquierda a derecha
    2. Calcula centro de cada par simétrico (1-N, 2-(N-1), ...)
    3. Calcula centro probabilístico (promedio de todos los centros de pares)
    4. Mide divergencia máxima de cada centro de par respecto al centro probabilístico
    5. OK si divergencia < umbral
    
    Args:
        centros: Lista de centros [(x, y), ...]
        px_per_mm: Relación píxeles por milímetro
        umbral_mm: Umbral máximo de divergencia en mm
    
    Returns:
        dict: {'ok': bool, 'divergencia_mm': float, 'umbral_mm': float}
    """
    
    if len(centros) < 4:
        # Con menos de 4 pistones no se puede hacer validación de múltiples pares
        return {
            'ok': True,
            'divergencia_mm': 0.0,
            'umbral_mm': float(umbral_mm),
            'nota': 'Menos de 4 pistones, validación omitida'
        }
    
    # PASO 1: Ordenar centros de izquierda a derecha
    centros_sorted = sorted(centros, key=lambda p: (p[0], p[1]))
    n = len(centros_sorted)
    
    # PASO 2: Calcular centros de pares simétricos
    centros_calculados = []
    num_pares = n // 2
    
    for i in range(num_pares):
        p1 = centros_sorted[i]
        p2 = centros_sorted[n - 1 - i]
        centro = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        centros_calculados.append(centro)
        print(f"[validaciones] Par {i+1}: pistón {i} ({p1[0]:.0f},{p1[1]:.0f}) + pistón {n-1-i} ({p2[0]:.0f},{p2[1]:.0f}) → centro ({centro[0]:.1f},{centro[1]:.1f})")
    
    if len(centros_calculados) < 2:
        # Con menos de 2 pares no hay nada que comparar
        return {
            'ok': True,
            'divergencia_mm': 0.0,
            'umbral_mm': float(umbral_mm),
            'nota': 'Menos de 2 pares, validación omitida'
        }
    
    # PASO 3: Calcular centro probabilístico (promedio)
    centro_prob_x = sum(c[0] for c in centros_calculados) / len(centros_calculados)
    centro_prob_y = sum(c[1] for c in centros_calculados) / len(centros_calculados)
    centro_probabilistico = (centro_prob_x, centro_prob_y)
    
    print(f"[validaciones] Centro probabilístico: ({centro_prob_x:.1f}, {centro_prob_y:.1f})")
    
    # PASO 4: Calcular divergencia de cada centro de par
    divergencias = []
    for i, centro_par in enumerate(centros_calculados):
        distancia_px = np.sqrt((centro_par[0] - centro_prob_x)**2 + (centro_par[1] - centro_prob_y)**2)
        distancia_mm = distancia_px / px_per_mm
        divergencias.append(distancia_mm)
        print(f"[validaciones] Centro par {i+1} vs probabilístico: {distancia_mm:.2f}mm")
    
    # PASO 5: Verificar divergencia máxima
    divergencia_maxima = max(divergencias) if divergencias else 0.0
    ok = divergencia_maxima <= umbral_mm
    
    print(f"[validaciones] Divergencia máxima: {divergencia_maxima:.2f}mm (umbral: {umbral_mm}mm) → {'✓ OK' if ok else '✗ FALLO'}")
    
    return {
        'ok': bool(ok),  # ← Convertir a bool nativo de Python
        'divergencia_mm': float(round(divergencia_maxima, 2)),
        'umbral_mm': float(umbral_mm),
        'centro_probabilistico': centro_probabilistico  # ← Agregar centro probabilístico
    }


# ============================================================
# VALIDACIÓN 2: COLINEALIDAD
# ============================================================

def validar_colinealidad(centros, px_per_mm, umbral_mm):
    """
    Valida que todos los centros estén alineados en línea recta.
    
    Estrategia:
    1. Ajusta una línea recta con cv2.fitLine (método robusto)
    2. Calcula distancia perpendicular de cada punto a la línea
    3. OK si desviación máxima < umbral
    
    Args:
        centros: Lista de centros [(x, y), ...]
        px_per_mm: Relación píxeles por milímetro
        umbral_mm: Umbral máximo de desviación en mm
    
    Returns:
        dict: {'ok': bool, 'desviacion_maxima_mm': float, 'umbral_mm': float}
    """
    
    if len(centros) < 3:
        # Con menos de 3 puntos no se puede validar colinealidad
        return {
            'ok': True,
            'desviacion_maxima_mm': 0.0,
            'umbral_mm': float(umbral_mm),
            'nota': 'Menos de 3 pistones, validación omitida'
        }
    
    if not OPENCV_AVAILABLE:
        return {
            'ok': False,
            'error': 'OpenCV no disponible',
            'umbral_mm': float(umbral_mm)
        }
    
    # PASO 1: Convertir a numpy array
    points = np.array(centros, dtype=np.float32)
    
    # PASO 2: Ajustar línea recta con cv2.fitLine
    # vx, vy: dirección de la línea
    # x0, y0: punto en la línea
    [vx, vy, x0, y0] = cv2.fitLine(points, cv2.DIST_L2, 0, 0.01, 0.01)
    
    # PASO 3: Calcular distancia perpendicular de cada punto a la línea
    desviaciones = []
    for point in points:
        px, py = point
        # Distancia punto-línea: |vy*(x - x0) - vx*(y - y0)|
        distancia_px = abs(vy[0] * (px - x0[0]) - vx[0] * (py - y0[0]))
        distancia_mm = distancia_px / px_per_mm
        desviaciones.append(distancia_mm)
    
    # PASO 4: Verificar desviación máxima
    desviacion_maxima = max(desviaciones) if desviaciones else 0.0
    ok = desviacion_maxima <= umbral_mm
    
    print(f"[validaciones] Colinealidad: desviación máxima={desviacion_maxima:.2f}mm (umbral: {umbral_mm}mm) → {'✓ OK' if ok else '✗ FALLO'}")
    
    return {
        'ok': bool(ok),  # ← Convertir a bool nativo de Python
        'desviacion_maxima_mm': float(round(desviacion_maxima, 2)),
        'umbral_mm': float(umbral_mm)
    }


# ============================================================
# VALIDACIÓN 3: ESPACIADO UNIFORME
# ============================================================

def validar_espaciado_uniforme(centros, px_per_mm, cv_maximo):
    """
    Valida que el espaciado entre pistones vecinos sea uniforme.
    
    Estrategia:
    1. Calcula distancia entre cada par de vecinos
    2. Calcula coeficiente de variación (CV = desviación / media)
    3. OK si CV < umbral
    
    Args:
        centros: Lista de centros [(x, y), ...] (ya ordenados)
        px_per_mm: Relación píxeles por milímetro
        cv_maximo: Coeficiente de variación máximo permitido
    
    Returns:
        dict: {'ok': bool, 'coeficiente_variacion': float, 'cv_maximo': float}
    """
    
    if len(centros) < 2:
        return {
            'ok': True,
            'coeficiente_variacion': 0.0,
            'cv_maximo': float(cv_maximo),
            'nota': 'Menos de 2 pistones, validación omitida'
        }
    
    # PASO 1: Calcular distancias entre vecinos
    distancias_px = []
    for i in range(len(centros) - 1):
        p1 = centros[i]
        p2 = centros[i + 1]
        dist = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
        distancias_px.append(dist)
    
    if not distancias_px:
        return {
            'ok': True,
            'coeficiente_variacion': 0.0,
            'cv_maximo': float(cv_maximo)
        }
    
    # PASO 2: Calcular coeficiente de variación
    media = np.mean(distancias_px)
    desviacion = np.std(distancias_px)
    cv = desviacion / media if media > 0 else 0.0
    
    # PASO 3: Verificar umbral
    ok = cv <= cv_maximo
    
    print(f"[validaciones] Espaciado uniforme: CV={cv:.3f} (máximo: {cv_maximo}) → {'✓ OK' if ok else '✗ FALLO'}")
    print(f"[validaciones] Distancias entre vecinos: {[f'{d:.1f}px' for d in distancias_px]}")
    
    return {
        'ok': bool(ok),  # ← Convertir a bool nativo de Python
        'coeficiente_variacion': float(round(cv, 3)),
        'cv_maximo': float(cv_maximo)
    }

