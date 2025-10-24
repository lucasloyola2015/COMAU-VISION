# aruco_detector.py - Detección de marcadores ArUco
from typing import Optional, Tuple, Dict
import numpy as np

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None
    OPENCV_AVAILABLE = False

# ============================================================
# DETECCIÓN DE ARUCO
# ============================================================
def detect_aruco_by_id(frame, target_id: int, dictionary_id: int = 50, marker_size_mm: float = 42.0) -> Optional[Dict]:
    """
    Detecta un marcador ArUco específico en el frame y calcula calibración.
    
    Args:
        frame: Frame de OpenCV (numpy array)
        target_id: ID del ArUco a buscar
        dictionary_id: ID del diccionario ArUco (default: 50 = DICT_4X4_50)
        marker_size_mm: Tamaño real del marcador en mm (default: 42.0)
    
    Returns:
        Dict con {center, corners, id, px_per_mm, rotation_matrix, detected_ids} o None
        detected_ids: lista de IDs encontrados en el frame (incluso si no es el target_id)
    """
    if not OPENCV_AVAILABLE or frame is None:
        return None
    
    try:
        # Seleccionar diccionario ArUco
        aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_id)
        aruco_params = cv2.aruco.DetectorParameters()
        
        # Crear detector (nueva API de OpenCV 4.8+)
        detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
        
        # Detectar marcadores
        corners, ids, _ = detector.detectMarkers(frame)
        
        # Preparar lista de IDs detectados para reporte
        detected_ids = []
        if ids is not None:
            detected_ids = ids.flatten().tolist()
        
        # Buscar el marcador objetivo
        if ids is not None:
            ids_flat = ids.flatten()
            
            for i, marker_id in enumerate(ids_flat):
                if marker_id == target_id:
                    # Calcular centro del marcador
                    marker_corners = corners[i][0]
                    center_x = int(np.mean(marker_corners[:, 0]))
                    center_y = int(np.mean(marker_corners[:, 1]))
                    
                    # Calcular tamaño del marcador en píxeles (promedio de 4 lados)
                    side1 = np.linalg.norm(marker_corners[1] - marker_corners[0])
                    side2 = np.linalg.norm(marker_corners[2] - marker_corners[1])
                    side3 = np.linalg.norm(marker_corners[3] - marker_corners[2])
                    side4 = np.linalg.norm(marker_corners[0] - marker_corners[3])
                    avg_side_px = (side1 + side2 + side3 + side4) / 4.0
                    
                    # Calcular relación px/mm
                    px_per_mm = avg_side_px / marker_size_mm
                    
                    # Calcular matriz de rotación (ejes X e Y del ArUco)
                    # Eje X: desde centro hacia punto medio del lado derecho
                    right_side_center = (marker_corners[1] + marker_corners[2]) / 2
                    x_axis = right_side_center - np.array([center_x, center_y])
                    x_axis = x_axis / np.linalg.norm(x_axis)
                    
                    # Eje Y: perpendicular a X
                    y_axis = np.array([x_axis[1], -x_axis[0]])
                    
                    rotation_matrix = np.array([x_axis, y_axis])
                    
                    return {
                        'id': int(marker_id),
                        'center': (center_x, center_y),
                        'corners': marker_corners.tolist(),
                        'px_per_mm': float(px_per_mm),
                        'rotation_matrix': rotation_matrix.tolist(),
                        'detected_ids': detected_ids  # Lista de todos los IDs detectados
                    }
        
        # Si llegamos aquí, el target_id no se encontró pero podemos retornar información
        # sobre qué IDs sí se detectaron
        return None
    
    except Exception as e:
        print(f"[aruco] Error detectando ArUco: {e}")
        return None

def detect_all_arucos(frame, dictionary_id: int = 50, marker_size_mm: float = 42.0) -> Optional[Dict]:
    """
    Detecta TODOS los marcadores ArUco en el frame.
    
    Args:
        frame: Frame de OpenCV (numpy array)
        dictionary_id: ID del diccionario ArUco (default: 50 = DICT_4X4_50)
        marker_size_mm: Tamaño real del marcador en mm (default: 42.0)
    
    Returns:
        Dict con {detected_ids, markers} o None si no hay ArUcos
        markers: lista de dicts con info de cada marcador
    """
    if not OPENCV_AVAILABLE or frame is None:
        return None
    
    try:
        # Seleccionar diccionario ArUco
        aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_id)
        aruco_params = cv2.aruco.DetectorParameters()
        
        # Crear detector
        detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
        
        # Detectar marcadores
        corners, ids, _ = detector.detectMarkers(frame)
        
        if ids is None or len(ids) == 0:
            return None
        
        detected_ids = ids.flatten().tolist()
        markers = []
        
        for i, marker_id in enumerate(ids.flatten()):
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
        print(f"[aruco] Error detectando ArUcos: {e}")
        return None

def get_available_dictionaries() -> Dict[int, str]:
    """Devuelve diccionarios ArUco disponibles"""
    return {
        50: "DICT_4X4_50",
        100: "DICT_4X4_100",
        250: "DICT_4X4_250",
        1000: "DICT_4X4_1000"
    }

