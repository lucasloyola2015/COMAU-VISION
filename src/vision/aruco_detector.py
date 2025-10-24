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
def detect_aruco_by_id(frame, target_id: int, dictionary_id: int = 50, marker_size_mm: float = 42.0, enable_preprocessing: bool = True) -> Optional[Dict]:
    """
    Detecta un marcador ArUco específico en el frame y calcula calibración.
    
    Utiliza preprocesamiento agresivo optimizado para fondos de color variable.
    
    Args:
        frame: Frame de OpenCV (numpy array)
        target_id: ID del ArUco a buscar
        dictionary_id: ID del diccionario ArUco (default: 50 = DICT_4X4_50)
        marker_size_mm: Tamaño real del marcador en mm (default: 42.0)
        enable_preprocessing: Usar preprocesamiento agresivo (default: True)
    
    Returns:
        Dict con {center, corners, id, px_per_mm, rotation_matrix, detected_ids} o None
    """
    if not OPENCV_AVAILABLE or frame is None:
        return None
    
    try:
        # Aplicar preprocesamiento agresivo si está habilitado
        if enable_preprocessing:
            frame_for_detection = apply_aggressive_preprocessing(frame)
        else:
            frame_for_detection = frame
        
        # Seleccionar diccionario y configurar parámetros
        aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_id)
        aruco_params = cv2.aruco.DetectorParameters()
        _configure_aruco_params(aruco_params)
        
        # Crear detector y detectar
        detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
        corners, ids, _ = detector.detectMarkers(frame_for_detection)
        
        # Buscar el marcador objetivo
        result = _find_target_in_detection_results(corners, ids, target_id, marker_size_mm)
        return result
    
    except Exception as e:
        print(f"[aruco] Error detectando ArUco: {e}")
        import traceback
        traceback.print_exc()
        return None

def _configure_aruco_params(aruco_params):
    """Configura los parámetros óptimos de detección de ArUco"""
    aruco_params.adaptiveThreshConstant = 10
    aruco_params.polygonalApproxAccuracyRate = 0.05
    aruco_params.errorCorrectionRate = 0.8
    aruco_params.cornerRefinementMethod = 1  # CORNER_REFINE_SUBPIX
    aruco_params.minMarkerPerimeterRate = 0.03
    aruco_params.maxMarkerPerimeterRate = 4.0
    aruco_params.minOtsuStdDev = 5.0

def _find_target_in_detection_results(corners, ids, target_id, marker_size_mm):
    """
    Busca el target_id en los resultados de detección.
    
    Returns:
        Dict con info del marcador o None
    """
    if ids is None:
        return None
    
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

def apply_aggressive_preprocessing(frame):
    """
    Preprocesamiento agresivo OPTIMIZADO para detección rápida de ArUcos.
    Solo usa operaciones rápidas: CLAHE + EqualizeHist.
    
    Args:
        frame: Frame de OpenCV
    
    Returns:
        Frame procesado para detección robusta
    """
    if not OPENCV_AVAILABLE or frame is None:
        return frame
    
    try:
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame.copy()
        
        # PASO 1: CLAHE - Mejora contraste local (rápido)
        clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(5, 5))
        enhanced = clahe.apply(gray)
        
        # PASO 2: EqualizeHist - Mejora contraste global (rápido)
        result_gray = cv2.equalizeHist(enhanced)
        
        # Convertir a BGR si entrada era BGR
        if len(frame.shape) == 3:
            result = cv2.cvtColor(result_gray, cv2.COLOR_GRAY2BGR)
        else:
            result = result_gray
        
        return result
    
    except Exception as e:
        print(f"[aruco] Error en preprocesamiento: {e}")
        return frame

def detect_all_arucos(frame, dictionary_id: int = 50, marker_size_mm: float = 42.0, enable_preprocessing: bool = True) -> Optional[Dict]:
    """
    Detecta TODOS los marcadores ArUco en el frame.
    
    Utiliza preprocesamiento agresivo optimizado para fondos de color variable.
    
    Args:
        frame: Frame de OpenCV (numpy array)
        dictionary_id: ID del diccionario ArUco (default: 50 = DICT_4X4_50)
        marker_size_mm: Tamaño real del marcador en mm (default: 42.0)
        enable_preprocessing: Usar preprocesamiento agresivo (default: True)
    
    Returns:
        Dict con {detected_ids, markers} o None si no hay ArUcos
        markers: lista de dicts con info de cada marcador
    """
    if not OPENCV_AVAILABLE or frame is None:
        return None
    
    try:
        # Aplicar preprocesamiento agresivo si está habilitado
        if enable_preprocessing:
            frame_for_detection = apply_aggressive_preprocessing(frame)
        else:
            frame_for_detection = frame
        
        # Seleccionar diccionario y configurar parámetros
        aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_id)
        aruco_params = cv2.aruco.DetectorParameters()
        _configure_aruco_params(aruco_params)
        
        # Crear detector y detectar
        detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
        corners, ids, _ = detector.detectMarkers(frame_for_detection)
        
        # Construir resultado si hay detecciones
        if ids is not None and len(ids) > 0:
            return _build_arucos_result(corners, ids, marker_size_mm)
        
        return None
    
    except Exception as e:
        print(f"[aruco] Error detectando todos los ArUcos: {e}")
        return None

def _build_arucos_result(corners, ids, marker_size_mm):
    """Construye el resultado de detección múltiple"""
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

def get_available_dictionaries() -> Dict[int, str]:
    """Devuelve diccionarios ArUco disponibles"""
    return {
        50: "DICT_4X4_50",
        100: "DICT_4X4_100",
        250: "DICT_4X4_250",
        1000: "DICT_4X4_1000"
    }

