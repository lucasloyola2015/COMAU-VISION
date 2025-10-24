# camera_manager.py - Gestión de cámaras
import json
import subprocess
import re
import sys
import threading
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# ============================================================
# CONFIGURACIÓN GLOBAL
# ============================================================
CONFIG_FILE = "config.json"
_lock = threading.Lock()
_cap = None
_cam_vid: Optional[str] = None
_cam_pid: Optional[str] = None
_cam_resolution: Optional[Tuple[int, int]] = None

# ============================================================
# OPENCV IMPORTS
# ============================================================
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None
    OPENCV_AVAILABLE = False
    print("[camera] ⚠️ OpenCV no disponible")

# ============================================================
# CARGAR Y GUARDAR CONFIGURACIÓN
# ============================================================
def load_config() -> dict:
    """Carga configuración desde config.json"""
    if not Path(CONFIG_FILE).exists():
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[camera] Error cargando config: {e}")
        return {}

def save_config(config: dict):
    """Guarda configuración en config.json"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[camera] Error guardando config: {e}")

# ============================================================
# DETECCIÓN DE CÁMARAS (WINDOWS)
# ============================================================
def _get_windows_cameras() -> List[Dict]:
    """Obtiene información de cámaras desde Windows usando PowerShell"""
    if not sys.platform.startswith("win"):
        return []
    
    try:
        ps_command = (
            r"(Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPClass -eq 'Camera'})"
            r" | Select-Object Name,PNPDeviceID | ConvertTo-Json"
        )
        
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if not result.stdout.strip():
            return []
        
        data = json.loads(result.stdout)
        if isinstance(data, dict):
            data = [data]
        
        cameras = []
        for item in data:
            name = (item.get("Name") or "").strip()
            pnp = (item.get("PNPDeviceID") or "").strip()
            
            # Extraer VID y PID
            vid = pid = None
            if "VID_" in pnp and "PID_" in pnp:
                mvid = re.search(r"VID_([0-9A-Fa-f]{4})", pnp)
                mpid = re.search(r"PID_([0-9A-Fa-f]{4})", pnp)
                vid = mvid.group(1) if mvid else None
                pid = mpid.group(1) if mpid else None
            
            if vid and pid:
                cameras.append({
                    "name": name,
                    "vid": vid,
                    "pid": pid
                })
        
        return cameras
    
    except Exception as e:
        print(f"[camera] Error obteniendo cámaras de Windows: {e}")
        return []

def _get_opencv_backends() -> List[Optional[int]]:
    """Devuelve backends de OpenCV a probar según el sistema operativo"""
    if not OPENCV_AVAILABLE:
        return [None]
    
    if sys.platform.startswith("win"):
        backends = []
        if hasattr(cv2, 'CAP_DSHOW'):
            backends.append(cv2.CAP_DSHOW)
        if hasattr(cv2, 'CAP_MSMF'):
            backends.append(cv2.CAP_MSMF)
        return backends if backends else [None]
    
    return [None]

def _try_open_camera(index: int, backend: Optional[int]) -> bool:
    """Intenta abrir una cámara en un índice con un backend específico"""
    if not OPENCV_AVAILABLE:
        return False
    
    try:
        cap = cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)
        if not cap.isOpened():
            cap.release()
            return False
        
        ret, _ = cap.read()
        cap.release()
        return ret
    
    except Exception:
        return False

def _find_camera_index_by_vidpid(target_vid: str, target_pid: str, max_index: int = 20) -> Optional[int]:
    """
    Busca el índice de OpenCV de una cámara por VID:PID.
    Returns: índice de la cámara o None si no la encuentra
    """
    if not OPENCV_AVAILABLE:
        return None
    
    print(f"[camera] Buscando cámara VID_{target_vid}&PID_{target_pid}...")
    
    # Obtener cámaras detectadas en Windows
    win_cameras = _get_windows_cameras()
    target_idx = None
    
    for idx, win_cam in enumerate(win_cameras):
        if win_cam["vid"] == target_vid and win_cam["pid"] == target_pid:
            target_idx = idx
            break
    
    if target_idx is None:
        return None
    
    print(f"[camera] Cámara encontrada en posición {target_idx}, probando índices de OpenCV...")
    
    # Probar índices hasta encontrar la cámara
    found_count = 0
    for i in range(max_index):
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                cap.release()
                
                if ret:
                    if found_count == target_idx:
                        print(f"[camera] ✓ Cámara VID_{target_vid}&PID_{target_pid} en índice {i}")
                        return i
                    found_count += 1
        except Exception:
            pass
    
    return None

# ============================================================
# ESCANEAR CÁMARAS DEL SISTEMA
# ============================================================
def scan_cameras() -> List[Dict]:
    """
    Escanea cámaras disponibles en el sistema.
    SOLO devuelve cámaras detectadas en Windows (confiables con VID:PID).
    
    Returns: [{name, vid, pid}]
    """
    if not OPENCV_AVAILABLE:
        print("[camera] OpenCV no disponible, no se pueden escanear cámaras")
        return []
    
    print(f"[camera] Escaneando cámaras del sistema...")
    
    # Obtener SOLO cámaras de Windows (son las confiables)
    cameras = _get_windows_cameras()
    
    print(f"[camera] Encontradas {len(cameras)} cámara(s) en Windows:")
    for cam in cameras:
        if cam['vid'] and cam['pid']:
            print(f"[camera]   - {cam['name']} (VID_{cam['vid']}&PID_{cam['pid']})")
    
    return cameras

# ============================================================
# RESOLUCIONES
# ============================================================
def get_supported_resolutions(vid: str, pid: str) -> List[Tuple[int, int]]:
    """
    Obtiene resoluciones soportadas para una cámara por VID:PID.
    Returns: [(width, height), ...]
    """
    if not OPENCV_AVAILABLE:
        return []
    
    # Encontrar índice de la cámara
    cam_index = _find_camera_index_by_vidpid(vid, pid)
    if cam_index is None:
        print(f"[camera] ⚠️ No se encontró cámara VID_{vid}&PID_{pid}")
        return []
    
    test_resolutions = [
        (640, 480),
        (1280, 720),
        (1920, 1080),
        (800, 600),
        (1024, 768),
        (320, 240),
    ]
    
    supported = []
    try:
        cap = cv2.VideoCapture(cam_index)
        if not cap.isOpened():
            return []
        
        for width, height in test_resolutions:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if abs(actual_w - width) <= 8 and abs(actual_h - height) <= 8:
                if (width, height) not in supported:
                    supported.append((width, height))
        
        cap.release()
        print(f"[camera] Resoluciones soportadas: {supported}")
        return supported
    
    except Exception as e:
        print(f"[camera] Error obteniendo resoluciones: {e}")
        return [(640, 480), (1280, 720)]

# ============================================================
# CONEXIÓN DE CÁMARA
# ============================================================
def connect_camera(vid: str, pid: str, width: Optional[int] = None, height: Optional[int] = None) -> Tuple[bool, str]:
    """
    Conecta a una cámara por VID:PID.
    Returns: (success, error_message)
    """
    global _cap, _cam_vid, _cam_pid, _cam_resolution
    
    if not OPENCV_AVAILABLE:
        return False, "OpenCV no disponible"
    
    print(f"[camera] Conectando a VID_{vid}&PID_{pid}...")
    
    # Encontrar índice de la cámara
    cam_index = _find_camera_index_by_vidpid(vid, pid)
    if cam_index is None:
        return False, f"Cámara VID_{vid}&PID_{pid} no encontrada en el sistema"
    
    disconnect_camera()
    
    try:
        cap = cv2.VideoCapture(cam_index)
        
        if not cap.isOpened():
            return False, "No se pudo abrir la cámara"
        
        if width and height:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        ret, _ = cap.read()
        if not ret:
            cap.release()
            return False, "No se pueden leer frames de la cámara"
        
        with _lock:
            _cap = cap
            _cam_vid = vid
            _cam_pid = pid
            _cam_resolution = (width, height) if width and height else None
            
            print(f"[camera] ✓ Conectado a VID_{vid}&PID_{pid} en resolución {_cam_resolution}")
            return True, ""
    
    except Exception as e:
        return False, f"Error: {e}"

def disconnect_camera():
    """Desconecta la cámara actual"""
    global _cap, _cam_vid, _cam_pid, _cam_resolution
    
    with _lock:
        if _cap is not None:
            try:
                _cap.release()
            except:
                pass
            _cap = None
            _cam_vid = None
            _cam_pid = None
            _cam_resolution = None
            print("[camera] Cámara desconectada")

def get_frame() -> Optional[bytes]:
    """
    Captura un frame de la cámara y lo devuelve como JPEG para video en vivo.
    Returns: JPEG bytes o None
    """
    if not OPENCV_AVAILABLE:
        return None
    
    with _lock:
        if _cap is None or not _cap.isOpened():
            return None
        
        try:
            ret, frame = _cap.read()
            if not ret or frame is None:
                return None
            
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                return None
            
            return buffer.tobytes()
        
        except Exception as e:
            if "can't grab frame" not in str(e):
                print(f"[camera] Error capturando frame: {e}")
            return None

def get_frame_raw():
    """
    Captura un frame de la cámara y lo devuelve en formato OpenCV (numpy array).
    Returns: numpy array (BGR) o None
    """
    if not OPENCV_AVAILABLE:
        return None
    
    with _lock:
        if _cap is None or not _cap.isOpened():
            return None
        
        try:
            ret, frame = _cap.read()
            if not ret or frame is None:
                return None
            
            return frame
        
        except Exception as e:
            if "can't grab frame" not in str(e):
                print(f"[camera] Error capturando frame raw: {e}")
            return None

# ============================================================
# CONECTAR A CÁMARA GUARDADA
# ============================================================
def connectToCamera() -> Tuple[bool, str]:
    """
    Lee config.json e intenta conectarse a la cámara guardada por VID:PID.
    Returns: (success, message)
    """
    print("[camera] Intentando auto-conexión desde config.json...")
    
    config = load_config()
    cam_config = config.get("camera", {})
    
    vid = cam_config.get("vid")
    pid = cam_config.get("pid")
    name = cam_config.get("name", "Unknown Camera")
    
    if not vid or not pid:
        return False, "No hay VID:PID configurado en config.json"
    
    resolution = cam_config.get("preferred_resolution", {})
    width = resolution.get("width")
    height = resolution.get("height")
    
    print(f"[camera] Conectando a: {name} (VID_{vid}&PID_{pid})")
    
    success, error = connect_camera(vid, pid, width, height)
    
    if success:
        print(f"[camera] ✓ Auto-conexión exitosa: {name}")
        return True, f"Cámara conectada: {name}"
    else:
        print(f"[camera] ✗ Auto-conexión falló: {error}")
        return False, error

def save_camera_config(vid: str, pid: str, name: str, width: Optional[int] = None, height: Optional[int] = None):
    """Guarda configuración de cámara en config.json por VID:PID"""
    config = load_config()
    
    config["camera"] = {
        "vid": vid,
        "pid": pid,
        "name": name
    }
    
    if width and height:
        config["camera"]["preferred_resolution"] = {
            "width": width,
            "height": height
        }
    
    save_config(config)
    print(f"[camera] Configuración guardada: {name} (VID_{vid}&PID_{pid}) @ {width}x{height}")
