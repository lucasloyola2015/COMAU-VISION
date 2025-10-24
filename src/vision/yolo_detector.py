# yolo_detector.py - Detección de agujeros con YOLO
from typing import List, Tuple, Optional
import numpy as np
import os

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None
    OPENCV_AVAILABLE = False

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO = None
    YOLO_AVAILABLE = False
    print("[yolo] ⚠️  Ultralytics no disponible")

# ============================================================
# CONFIGURACIÓN
# ============================================================

# ============================================================
# ESTADO GLOBAL
# ============================================================
_models = {
    'detection': None,
    'holes': None
}
_model_paths = {
    'detection': None,
    'holes': None
}

# ============================================================
# CARGA DE MODELO
# ============================================================
def load_model(model_type: str, model_path: str) -> bool:
    """
    Carga un modelo YOLO desde un archivo .pt
    
    Args:
        model_type: Tipo de modelo ('detection' o 'holes')
        model_path: Path al archivo del modelo
    
    Returns:
        True si se cargó correctamente, False en caso contrario
    """
    global _models, _model_paths
    
    if not YOLO_AVAILABLE:
        print("[yolo] Ultralytics no disponible")
        return False
    
    if model_type not in _models:
        print(f"[yolo] Tipo de modelo inválido: {model_type}")
        return False
    
    try:
        print(f"[yolo] Intentando cargar modelo {model_type} desde: {model_path}")
        
        # Verificar que el archivo existe
        if not os.path.exists(model_path):
            print(f"[yolo] ❌ Archivo no encontrado: {model_path}")
            return False
        
        # Cargar modelo
        _models[model_type] = YOLO(model_path)
        _model_paths[model_type] = model_path
        print(f"[yolo] ✓ Modelo {model_type} cargado: {model_path}")
        return True
    except Exception as e:
        import traceback
        print(f"[yolo] ❌ Error cargando modelo {model_type}: {e}")
        print(f"[yolo] Traceback completo:")
        traceback.print_exc()
        _models[model_type] = None
        _model_paths[model_type] = None
        return False

def is_model_loaded(model_type: str) -> bool:
    """Verifica si un modelo específico está cargado"""
    return _models.get(model_type) is not None

def get_model_path(model_type: str) -> Optional[str]:
    """Obtiene el path de un modelo específico"""
    return _model_paths.get(model_type)

# ============================================================
# VALIDACIÓN DE FORMA ELÍPTICA
# ============================================================
# FUNCIÓN ELIMINADA: calculate_ellipse_similarity
# Reemplazada por calculate_ellipse_similarity_from_contour
# que usa OpenCV para detectar bordes reales del agujero azul

# ============================================================
# DETECCIÓN DE JUNTA (BOUNDING BOX)
# ============================================================
def detect_gasket(frame, conf_threshold: float = 0.5):
    """
    Detecta la junta completa y devuelve su bounding box.
    Compatible con YOLO normal (xyxy) y YOLO-OBB (xywhr).
    
    Args:
        frame: Frame de OpenCV
        conf_threshold: Umbral de confianza
    
    Returns:
        Para YOLO normal: (x1, y1, x2, y2)
        Para YOLO-OBB: {'type': 'obb', 'center': (x, y), 'size': (w, h), 'angle': angle, 'points': pts, 'bbox': (x1, y1, x2, y2)}
        None si no se detecta
    """
    if not OPENCV_AVAILABLE or not YOLO_AVAILABLE or _models['detection'] is None:
        return None
    
    if frame is None:
        return None
    
    try:
        # Ejecutar detección
        results = _models['detection'](frame, conf=conf_threshold, verbose=False)
        
        # Verificar que hay resultados
        if results is None or len(results) == 0:
            print("[yolo] No se recibieron resultados del modelo")
            return None
        
        # Para YOLO-OBB, verificar si hay atributo 'obb' en lugar de 'boxes'
        result = results[0]
        
        # Intentar obtener detecciones de OBB primero, luego boxes
        if hasattr(result, 'obb') and result.obb is not None and len(result.obb) > 0:
            # ⭐ YOLO-OBB: Usar datos de oriented bounding box
            obb = result.obb[0]
            xywhr_data = obb.xywhr[0].cpu().numpy()
            x, y, w, h, angle = xywhr_data
            
            print(f"[yolo] 🔍 DEBUG OBB raw: x={x:.1f}, y={y:.1f}, w={w:.1f}, h={h:.1f}, angle_raw={angle:.4f}")
            
            # YOLO-OBB usa radianes, convertir a grados para OpenCV
            angle_degrees = float(np.degrees(angle))
            print(f"[yolo] 🔍 DEBUG angle converted: {angle_degrees:.1f}°")
            
            # Calcular los 4 puntos del rectángulo rotado
            rect = ((float(x), float(y)), (float(w), float(h)), angle_degrees)
            pts = np.int0(cv2.boxPoints(rect))
            
            print(f"[yolo] 🔍 DEBUG puntos: {pts.tolist()}")
            
            # Calcular bbox alineado a ejes (para compatibilidad)
            x_coords = pts[:, 0]
            y_coords = pts[:, 1]
            x1, y1 = int(x_coords.min()), int(y_coords.min())
            x2, y2 = int(x_coords.max()), int(y_coords.max())
            
            print(f"[yolo] ✓ YOLO-OBB detectado: center=({x:.1f}, {y:.1f}), size=({w:.1f}x{h:.1f}), angle={angle_degrees:.1f}°")
            
            return {
                'type': 'obb',
                'center': (float(x), float(y)),
                'size': (float(w), float(h)),
                'angle': angle_degrees,
                'points': pts,
                'bbox': (x1, y1, x2, y2)  # Bbox alineado a ejes para compatibilidad
            }
        
        elif hasattr(result, 'boxes') and result.boxes is not None and len(result.boxes) > 0:
            # ⭐ YOLO normal: Bounding box recto
            box = result.boxes[0]
            bbox = box.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = map(int, bbox)
            
            print(f"[yolo] ✓ YOLO normal detectado: bbox=({x1}, {y1}, {x2}, {y2})")
            
            return (x1, y1, x2, y2)
        
        else:
            # No se detectó nada
            print("[yolo] No se detectaron objetos (obb y boxes vacíos)")
            return None
    
    except Exception as e:
        print(f"[yolo] Error detectando junta: {e}")
        return None


def detect_gasket_with_mask(frame, conf_threshold: float = 0.5) -> Optional[Tuple[Tuple[int, int, int, int], np.ndarray]]:
    """
    Detecta la junta completa y devuelve su bounding box y máscara de segmentación.
    
    Args:
        frame: Frame de OpenCV
        conf_threshold: Umbral de confianza
    
    Returns:
        ((x1, y1, x2, y2), mask) o None si no se detecta
        mask es un array numpy binario del tamaño del frame
    """
    if not OPENCV_AVAILABLE or not YOLO_AVAILABLE or _models['detection'] is None:
        return None
    
    if frame is None:
        return None
    
    try:
        # Ejecutar detección
        results = _models['detection'](frame, conf=conf_threshold, verbose=False)
        
        # Verificar que se detectó algo
        if len(results[0].boxes) == 0:
            return None
        
        # Obtener primer bbox (mejor detección)
        bbox = results[0].boxes[0].xyxy[0].cpu().numpy()
        x1, y1, x2, y2 = map(int, bbox)
        
        # Intentar obtener máscara de segmentación (si el modelo lo soporta)
        mask = None
        if hasattr(results[0], 'masks') and results[0].masks is not None and len(results[0].masks) > 0:
            # El modelo es de segmentación (YOLOv8-seg)
            mask_data = results[0].masks[0].data.cpu().numpy()[0]  # Primera máscara
            
            # Redimensionar máscara al tamaño del frame
            h, w = frame.shape[:2]
            mask = cv2.resize(mask_data, (w, h), interpolation=cv2.INTER_LINEAR)
            
            # Binarizar (threshold)
            mask = (mask > 0.5).astype(np.uint8)
        else:
            # El modelo es solo de detección, crear máscara simple desde el bbox
            h, w = frame.shape[:2]
            mask = np.zeros((h, w), dtype=np.uint8)
            mask[y1:y2, x1:x2] = 1
        
        return ((x1, y1, x2, y2), mask)
    
    except Exception as e:
        print(f"[yolo] Error detectando junta con máscara: {e}")
        return None

# ============================================================
# DETECCIÓN DE AGUJEROS
# ============================================================
def detect_holes(frame, conf_threshold: float = 0.5) -> List[Tuple[int, int]]:
    """
    Detecta agujeros en el frame usando YOLO y calcula sus centros geométricos.
    
    Args:
        frame: Frame de OpenCV (numpy array)
        conf_threshold: Umbral de confianza (default: 0.5)
    
    Returns:
        Lista de centros [(x1, y1), (x2, y2), ...]
    """
    if not OPENCV_AVAILABLE or not YOLO_AVAILABLE or _models['holes'] is None:
        return []
    
    if frame is None:
        return []
    
    try:
        # Ejecutar detección YOLO
        results = _models['holes'](frame, conf=conf_threshold, verbose=False)
        
        # Verificar que hay máscaras detectadas
        if results[0].masks is None:
            return []
        
        centers = []
        
        # Procesar cada máscara detectada
        for mask_tensor in results[0].masks.data:
            # Convertir tensor a numpy array
            float_mask = mask_tensor.cpu().numpy()
            
            # Convertir a máscara binaria (0 o 255)
            binary_mask = (float_mask > 0.5).astype(np.uint8) * 255
            
            # Redimensionar al tamaño del frame
            mask_resized = cv2.resize(binary_mask, (frame.shape[1], frame.shape[0]))
            
            # Encontrar contornos
            contours, _ = cv2.findContours(mask_resized, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Seleccionar contorno de mayor área
                largest_contour = max(contours, key=cv2.contourArea)
                
                # Calcular centro geométrico usando momentos
                moments = cv2.moments(largest_contour)
                
                if moments["m00"] != 0:  # Evitar división por cero
                    center_x = int(moments["m10"] / moments["m00"])
                    center_y = int(moments["m01"] / moments["m00"])
                    centers.append((center_x, center_y))
        
        return centers
    
    except Exception as e:
        print(f"[yolo] Error detectando agujeros: {e}")
        return []

# ============================================================
# DETECCIÓN DE AGUJEROS - VERSIÓN MODULAR
# ============================================================
def detect_holes_bboxes(frame, conf_threshold: float = 0.5) -> List[dict]:
    """
    Detecta agujeros usando YOLO y retorna SOLO bounding boxes.
    
    NUEVO ENFOQUE MODULAR:
    - YOLO solo hace localización (bboxes)
    - NO hace refinamiento con OpenCV
    - El refinamiento se delega a pipeline_analisis.calcular_centro_agujero()
    
    Esta función es simple y hace UNA sola cosa: detectar ubicaciones.
    
    Args:
        frame: Frame de OpenCV (numpy array)
        conf_threshold: Umbral de confianza (default: 0.5)
    
    Returns:
        list: [{'bbox': (x1, y1, x2, y2)}, ...]
        Lista vacía si no se detecta nada
    """
    
    if not OPENCV_AVAILABLE or not YOLO_AVAILABLE or _models['holes'] is None:
        return []
    
    if frame is None:
        return []
    
    try:
        # Ejecutar detección YOLO
        results = _models['holes'](frame, conf=conf_threshold, verbose=False)
        
        # Verificar que hay detecciones
        if results is None or len(results) == 0:
            return []
        
        result = results[0]
        
        # Verificar si el modelo retorna boxes
        if not hasattr(result, 'boxes') or result.boxes is None or len(result.boxes) == 0:
            return []
        
        detecciones = []
        
        # Por cada detección, extraer solo el bounding box
        for box in result.boxes:
            bbox = box.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = map(int, bbox)
            
            detecciones.append({
                'bbox': (x1, y1, x2, y2)
            })
        
        print(f"[yolo] ✓ Detectados {len(detecciones)} agujeros (solo bboxes)")
        return detecciones
    
    except Exception as e:
        print(f"[yolo] Error detectando agujeros (bboxes): {e}")
        return []


