# aruco_detector.py - Librería Genérica de Detección de ArUcos
"""
Librería genérica y reutilizable para detección de marcadores ArUco.

IMPORTANTE: Esta librería es GENÉRICA y NO debe ser modificada con:
- Elementos hardcodeados específicos del dominio
- Funciones específicas del proyecto
- Configuraciones específicas del negocio
- Dependencias de marcos de referencia específicos

Para funcionalidades específicas del proyecto, usar aruco_manager.py
"""

from typing import Optional, Tuple, Dict, List, Any
import numpy as np

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None
    OPENCV_AVAILABLE = False

# ============================================================
# DETECCIÓN BÁSICA DE ARUCO
# ============================================================

def detect_aruco_by_id(image, target_id: int, dictionary_id: int, marker_bits: int, marker_size_mm: float) -> Optional[Dict]:
    """
    Detecta un marcador ArUco específico en la imagen y calcula calibración.
    
    Args:
        image: Imagen de OpenCV (numpy array)
        target_id: ID del ArUco a buscar
        dictionary_id: ID del diccionario ArUco (50, 100, 250, 1000)
        marker_bits: Tamaño de matriz del marcador (4, 5, 6, 7)
        marker_size_mm: Tamaño real del marcador en mm
    
    Returns:
        Dict con {center, corners, id, px_per_mm, rotation_matrix, detected_ids} o None
    """
    if not OPENCV_AVAILABLE or image is None:
        return None
    
    try:
        # Mapear dictionary_id y marker_bits a diccionario OpenCV
        dict_mapping = get_dictionary_mapping()
        dict_key = (marker_bits, dictionary_id)
        
        if dict_key not in dict_mapping:
            print(f"[ArUcoDetector] ⚠️ Combinación marker_bits={marker_bits}, dictionary_id={dictionary_id} no soportada")
            return None
        
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_mapping[dict_key])
        aruco_params = cv2.aruco.DetectorParameters()
        
        # Crear detector con parámetros por defecto
        detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
        corners, ids, _ = detector.detectMarkers(image)
        
        # Buscar el marcador objetivo
        if ids is not None:
            detected_ids = ids.flatten().tolist()
            ids_flat = ids.flatten()
            
            for i, marker_id in enumerate(ids_flat):
                if marker_id == target_id:
                    marker_corners = corners[i][0]
                    center_x = int(np.mean(marker_corners[:, 0]))
                    center_y = int(np.mean(marker_corners[:, 1]))
                    
                    # Calcular tamaño
                    side1 = np.linalg.norm(marker_corners[1] - marker_corners[0])
                    side2 = np.linalg.norm(marker_corners[2] - marker_corners[1])
                    side3 = np.linalg.norm(marker_corners[3] - marker_corners[2])
                    side4 = np.linalg.norm(marker_corners[0] - marker_corners[3])
                    avg_side_px = (side1 + side2 + side3 + side4) / 4.0
                    
                    px_per_mm = avg_side_px / marker_size_mm
                    
                    # Calcular matriz de rotación
                    right_side_center = (marker_corners[1] + marker_corners[2]) / 2
                    x_axis = right_side_center - np.array([center_x, center_y])
                    x_axis = x_axis / np.linalg.norm(x_axis)
                    y_axis = np.array([x_axis[1], -x_axis[0]])
                    rotation_matrix = np.array([x_axis, y_axis])
                    
                    return {
                        'id': int(marker_id),
                        'center': (center_x, center_y),
                        'corners': marker_corners.tolist(),
                        'px_per_mm': float(px_per_mm),
                        'rotation_matrix': rotation_matrix.tolist(),
                        'detected_ids': detected_ids
                    }
        
        return None
    
    except Exception as e:
        print(f"[ArUcoDetector] Error detectando ArUco: {e}")
        import traceback
        traceback.print_exc()
        return None

def detect_all_arucos(image, dictionary_id: int, marker_bits: int, marker_size_mm: float) -> Optional[Dict]:
    """
    Detecta TODOS los marcadores ArUco en la imagen.
    
    Args:
        image: Imagen de OpenCV (numpy array)
        dictionary_id: ID del diccionario ArUco (50, 100, 250, 1000)
        marker_bits: Tamaño de matriz del marcador (4, 5, 6, 7)
        marker_size_mm: Tamaño real del marcador en mm
    
    Returns:
        Dict con {detected_ids, markers} o None si no hay ArUcos
    """
    if not OPENCV_AVAILABLE or image is None:
        return None
    
    try:
        # Mapear dictionary_id y marker_bits a diccionario OpenCV
        dict_mapping = get_dictionary_mapping()
        dict_key = (marker_bits, dictionary_id)
        
        if dict_key not in dict_mapping:
            print(f"[ArUcoDetector] ⚠️ Combinación marker_bits={marker_bits}, dictionary_id={dictionary_id} no soportada")
            return None
        
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_mapping[dict_key])
        aruco_params = cv2.aruco.DetectorParameters()
        
        detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
        corners, ids, _ = detector.detectMarkers(image)
        
        if ids is None or len(ids) == 0:
            return None
        
        detected_ids = ids.flatten().tolist()
        markers = []
        
        for i, marker_id in enumerate(ids.flatten()):
            marker_corners = corners[i][0]
            center_x = int(np.mean(marker_corners[:, 0]))
            center_y = int(np.mean(marker_corners[:, 1]))
            
            side1 = np.linalg.norm(marker_corners[1] - marker_corners[0])
            side2 = np.linalg.norm(marker_corners[2] - marker_corners[1])
            side3 = np.linalg.norm(marker_corners[3] - marker_corners[2])
            side4 = np.linalg.norm(marker_corners[0] - marker_corners[3])
            avg_side_px = (side1 + side2 + side3 + side4) / 4.0
            
            px_per_mm = avg_side_px / marker_size_mm
            
            markers.append({
                'id': int(marker_id),
                'center': (center_x, center_y),
                'px_per_mm': float(px_per_mm)
            })
        
        return {
            'detected_ids': detected_ids,
            'markers': markers
        }
    
    except Exception as e:
        print(f"[ArUcoDetector] Error detectando todos los ArUcos: {e}")
        return None

# ============================================================
# DETECCIÓN GENÉRICA CON CONFIGURACIÓN
# ============================================================

def detect_arucos_with_config(image: np.ndarray, aruco_configs: List[Dict[str, Any]], 
                             dictionary_id: int, marker_bits: int) -> Dict[str, Any]:
    """
    Detecta ArUcos en imagen usando configuración genérica.
    
    Args:
        image: Imagen de OpenCV (numpy array)
        aruco_configs: Lista de configuraciones de ArUcos
                      [{"id": int, "name": str, "size_mm": float, "color": tuple}]
        dictionary_id: ID del diccionario ArUco (50, 100, 250, 1000)
        marker_bits: Tamaño de matriz del marcador (4, 5, 6, 7)
        
    Returns:
        Diccionario con información de detección genérica
    """
    try:
        print(f"[ArUcoDetector] Detectando ArUcos en imagen {image.shape}")
        
        # Configurar detector ArUco
        dict_mapping = {
            (4, 50): cv2.aruco.DICT_4X4_50,
            (4, 100): cv2.aruco.DICT_4X4_100,
            (4, 250): cv2.aruco.DICT_4X4_250,
            (4, 1000): cv2.aruco.DICT_4X4_1000,
            (5, 50): cv2.aruco.DICT_5X5_50,
            (5, 100): cv2.aruco.DICT_5X5_100,
            (5, 250): cv2.aruco.DICT_5X5_250,
            (5, 1000): cv2.aruco.DICT_5X5_1000,
            (6, 50): cv2.aruco.DICT_6X6_50,
            (6, 100): cv2.aruco.DICT_6X6_100,
            (6, 250): cv2.aruco.DICT_6X6_250,
            (6, 1000): cv2.aruco.DICT_6X6_1000,
            (7, 50): cv2.aruco.DICT_7X7_50,
            (7, 100): cv2.aruco.DICT_7X7_100,
            (7, 250): cv2.aruco.DICT_7X7_250,
            (7, 1000): cv2.aruco.DICT_7X7_1000
        }
        
        dict_key = (marker_bits, dictionary_id)
        if dict_key not in dict_mapping:
            print(f"[ArUcoDetector] ⚠️ Combinación marker_bits={marker_bits}, dictionary_id={dictionary_id} no soportada, usando 4x4_50")
            dict_key = (4, 50)
        
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_mapping[dict_key])
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
        
        # Detectar marcadores
        corners, ids, rejected = detector.detectMarkers(image)
        
        print(f"[ArUcoDetector] Resultado detección:")
        print(f"  - corners: {len(corners) if corners is not None else 0}")
        print(f"  - ids: {ids}")
        print(f"  - rejected: {len(rejected) if rejected is not None else 0}")
        
        detected_arucos = {}
        detected_ids = []
        
        if ids is not None and len(ids) > 0:
            for i, aruco_id in enumerate(ids.flatten()):
                detected_ids.append(int(aruco_id))
                
                # Obtener esquinas del ArUco
                corner = corners[i][0]
                
                # Calcular centro
                center_x = np.mean(corner[:, 0])
                center_y = np.mean(corner[:, 1])
                
                # Calcular ángulo de rotación
                dx = corner[1][0] - corner[0][0]
                dy = corner[1][1] - corner[0][1]
                angle_rad = np.arctan2(dy, dx)
                
                # Buscar configuración para este ArUco
                aruco_config = None
                for config in aruco_configs:
                    if config.get('id') == int(aruco_id):
                        aruco_config = config
                        break
                
                # Usar tamaño de configuración o por defecto
                if aruco_config:
                    marker_size_mm = aruco_config.get('size_mm', 42.0)
                else:
                    marker_size_mm = 42.0  # Tamaño por defecto
                
                marker_size_px = np.linalg.norm(corner[1] - corner[0])
                px_per_mm = marker_size_px / marker_size_mm
                
                detected_arucos[int(aruco_id)] = {
                    'center': (float(center_x), float(center_y)),
                    'angle_rad': float(angle_rad),
                    'corners': corner.tolist(),
                    'px_per_mm': float(px_per_mm),
                    'config': aruco_config
                }
        
        # Verificar detección según configuración
        detection_status = {}
        for config in aruco_configs:
            aruco_id = config.get('id')
            aruco_name = config.get('name', f'aruco_{aruco_id}')
            detection_status[aruco_name] = aruco_id in detected_arucos
        
        return {
            'detected_arucos': detected_arucos,
            'detected_ids': detected_ids,
            'detection_status': detection_status,
            'aruco_configs': aruco_configs
        }
        
    except Exception as e:
        print(f"[ArUcoDetector] ❌ Error detectando ArUcos: {e}")
        return {
            'detected_arucos': {},
            'detected_ids': [],
            'detection_status': {},
            'error': str(e)
        }

# ============================================================
# UTILIDADES GENÉRICAS
# ============================================================

def get_available_dictionaries() -> Dict[int, str]:
    """Devuelve diccionarios ArUco disponibles"""
    return {
        50: "DICT_4X4_50", 100: "DICT_4X4_100", 250: "DICT_4X4_250", 1000: "DICT_4X4_1000",
        51: "DICT_5X5_50", 101: "DICT_5X5_100", 251: "DICT_5X5_250", 1001: "DICT_5X5_1000",
        52: "DICT_6X6_50", 102: "DICT_6X6_100", 252: "DICT_6X6_250", 1002: "DICT_6X6_1000",
        53: "DICT_7X7_50", 103: "DICT_7X7_100", 253: "DICT_7X7_250", 1003: "DICT_7X7_1000"
    }

def get_available_marker_sizes() -> Dict[int, str]:
    """Devuelve tamaños de matriz ArUco disponibles"""
    return {
        4: "4x4", 5: "5x5", 6: "6x6", 7: "7x7"
    }

def get_dictionary_mapping() -> Dict[Tuple[int, int], int]:
    """Devuelve mapeo de (marker_bits, dictionary_id) a constantes OpenCV"""
    return {
        (4, 50): cv2.aruco.DICT_4X4_50,
        (4, 100): cv2.aruco.DICT_4X4_100,
        (4, 250): cv2.aruco.DICT_4X4_250,
        (4, 1000): cv2.aruco.DICT_4X4_1000,
        (5, 50): cv2.aruco.DICT_5X5_50,
        (5, 100): cv2.aruco.DICT_5X5_100,
        (5, 250): cv2.aruco.DICT_5X5_250,
        (5, 1000): cv2.aruco.DICT_5X5_1000,
        (6, 50): cv2.aruco.DICT_6X6_50,
        (6, 100): cv2.aruco.DICT_6X6_100,
        (6, 250): cv2.aruco.DICT_6X6_250,
        (6, 1000): cv2.aruco.DICT_6X6_1000,
        (7, 50): cv2.aruco.DICT_7X7_50,
        (7, 100): cv2.aruco.DICT_7X7_100,
        (7, 250): cv2.aruco.DICT_7X7_250,
        (7, 1000): cv2.aruco.DICT_7X7_1000
    }
