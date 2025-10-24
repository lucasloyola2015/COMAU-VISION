# camera_manager.py - Gestión de cámaras
import json
import subprocess
import re
import sys
import threading
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Configurar OpenCV antes de importarlo
try:
    import opencv_config  # Esto configura variables de entorno
except ImportError:
    pass

# Estado global
_lock = threading.Lock()
_cap = None
_cam_uid: Optional[str] = None
_cam_resolution: Optional[Tuple[int, int]] = None

CONFIG_FILE = "config.json"

# ============================================================
# OPENCV IMPORTS
# ============================================================
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None
    OPENCV_AVAILABLE = False
    print("[camera] ⚠️  OpenCV no disponible")

# ============================================================
# CONFIGURACIÓN
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
            
            cameras.append({
                "name": name,
                "pnp": pnp,
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
        # En Windows probar DSHOW y MSMF
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

def scan_cameras(max_index: int = 20) -> List[Dict]:
    """
    Escanea cámaras disponibles probando múltiples backends.
    Returns: [{id, name, uid}]
    """
    global _cap, _cam_uid
    
    if not OPENCV_AVAILABLE:
        print("[camera] OpenCV no disponible, no se pueden escanear cámaras")
        return []
    
    print(f"[camera] Escaneando cámaras (índices 0-{max_index-1})...")
    
    # CRÍTICO: Desconectar cámara actual temporalmente para escaneo completo
    was_connected = False
    saved_uid = None
    saved_resolution = None
    
    with _lock:
        if _cap is not None:
            was_connected = True
            saved_uid = _cam_uid
            saved_resolution = _cam_resolution
            print(f"[camera] Desconectando cámara temporalmente ({saved_uid}) para escaneo completo...")
    
    if was_connected:
        disconnect_camera()
        import time
        time.sleep(0.5)  # Dar tiempo para liberar el recurso
    
    # Obtener info de Windows
    win_cameras = _get_windows_cameras()
    print(f"[camera] Windows detectó {len(win_cameras)} cámara(s)")
    
    # Obtener backends disponibles
    backends = _get_opencv_backends()
    print(f"[camera] Backends a probar: {backends}")
    
    # Probar índices de OpenCV con diferentes backends
    available = []
    for i in range(max_index):
        # Delay entre intentos para no saturar
        if i > 0:
            import time
            time.sleep(0.05)
        
        found = False
        for backend in backends:
            if _try_open_camera(i, backend):
                if i not in available:
                    available.append(i)
                    backend_name = f"backend {backend}" if backend else "default backend"
                    print(f"[camera] ✓ Cámara encontrada en índice {i} ({backend_name})")
                    found = True
                break
        
        if not found and i < 5:  # Solo mostrar para primeros índices
            print(f"[camera] ✗ Índice {i} no disponible")
    
    print(f"[camera] OpenCV encontró {len(available)} cámara(s) en índices: {available}")
    
    # Mapear índices a información de Windows
    devices = []
    for idx, cam_id in enumerate(available):
        name = f"Webcam {cam_id}"
        uid = f"CAM_{cam_id}"
        
        # Intentar obtener info de Windows
        if idx < len(win_cameras):
            win_cam = win_cameras[idx]
            name = win_cam["name"] or name
            
            # Crear UID estable desde VID/PID
            if win_cam["vid"] and win_cam["pid"]:
                uid = f"VID_{win_cam['vid']}&PID_{win_cam['pid']}"
            elif win_cam["pnp"]:
                uid = win_cam["pnp"]
        
        devices.append({
            "id": cam_id,
            "name": name,
            "uid": uid
        })
    
    print(f"[camera] Dispositivos mapeados: {devices}")
    
    # CRÍTICO: Reconectar cámara si estaba en uso
    if was_connected and saved_uid:
        print(f"[camera] Reconectando cámara original ({saved_uid})...")
        import time
        time.sleep(0.3)
        try:
            width, height = saved_resolution if saved_resolution else (None, None)
            success, _ = connect_camera(saved_uid, width, height)
            if success:
                print(f"[camera] ✓ Cámara reconectada exitosamente")
            else:
                print(f"[camera] ⚠️ No se pudo reconectar la cámara")
        except Exception as e:
            print(f"[camera] Error reconectando: {e}")
    
    return devices

# ============================================================
# RESOLUCIONES
# ============================================================
def get_supported_resolutions(uid: str) -> List[Tuple[int, int]]:
    """
    Obtiene resoluciones soportadas para una cámara.
    Returns: [(width, height), ...]
    """
    if not OPENCV_AVAILABLE:
        return []
    
    # Mapear UID a índice
    cam_id = _uid_to_index(uid)
    if cam_id is None:
        return []
    
    # Resoluciones comunes a probar
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
        cap = cv2.VideoCapture(cam_id)
        if not cap.isOpened():
            return []
        
        for width, height in test_resolutions:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Tolerancia de ±8 píxeles
            if abs(actual_w - width) <= 8 and abs(actual_h - height) <= 8:
                if (width, height) not in supported:
                    supported.append((width, height))
        
        cap.release()
        print(f"[camera] Resoluciones soportadas para {uid}: {supported}")
        return supported
    
    except Exception as e:
        print(f"[camera] Error obteniendo resoluciones: {e}")
        return [(640, 480), (1280, 720)]  # Fallback

def _uid_to_index(uid: str) -> Optional[int]:
    """Mapea UID a índice de cámara"""
    devices = scan_cameras()
    for dev in devices:
        if dev["uid"] == uid:
            return dev["id"]
    return None

# ============================================================
# CONEXIÓN DE CÁMARA
# ============================================================
def connect_camera(uid: str, width: Optional[int] = None, height: Optional[int] = None) -> Tuple[bool, str]:
    """
    Conecta a una cámara por UID probando múltiples backends.
    Returns: (success, error_message)
    """
    global _cap, _cam_uid, _cam_resolution
    
    if not OPENCV_AVAILABLE:
        return False, "OpenCV no disponible"
    
    # Mapear UID a índice
    cam_id = _uid_to_index(uid)
    if cam_id is None:
        return False, f"Cámara con UID {uid} no encontrada"
    
    # Cerrar cámara anterior si existe
    disconnect_camera()
    
    # Probar con diferentes backends
    backends = _get_opencv_backends()
    cap = None
    
    for backend in backends:
        try:
            test_cap = cv2.VideoCapture(cam_id, backend) if backend is not None else cv2.VideoCapture(cam_id)
            
            if not test_cap.isOpened():
                test_cap.release()
                continue
            
            # Configurar resolución si se especificó
            if width and height:
                test_cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                test_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            # Verificar que funciona leyendo un frame
            ret, _ = test_cap.read()
            if ret:
                cap = test_cap
                backend_name = f"backend {backend}" if backend else "default"
                print(f"[camera] ✓ Cámara abierta con {backend_name}")
                break
            else:
                test_cap.release()
        
        except Exception:
            continue
    
    if cap is None:
        return False, "No se pudo abrir la cámara con ningún backend"
    
    try:
        with _lock:
            _cap = cap
            _cam_uid = uid
            _cam_resolution = (width, height) if width and height else None
            
            print(f"[camera] ✓ Conectado a {uid} en resolución {_cam_resolution}")
            return True, ""
    
    except Exception as e:
        if cap:
            cap.release()
        return False, f"Error: {e}"

def disconnect_camera():
    """Desconecta la cámara actual"""
    global _cap, _cam_uid, _cam_resolution
    
    with _lock:
        if _cap is not None:
            try:
                _cap.release()
            except:
                pass
            _cap = None
            _cam_uid = None
            _cam_resolution = None
            print("[camera] Cámara desconectada")

def get_frame() -> Optional[bytes]:
    """
    Captura un frame de la cámara y lo devuelve como JPEG SIN overlays (video en vivo).
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
            
            # NO aplicar overlays - video crudo para dashboard
            
            # Convertir a JPEG
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                return None
            
            return buffer.tobytes()
        
        except Exception as e:
            # Suprimir warnings repetitivos de MSMF
            if "can't grab frame" not in str(e):
                print(f"[camera] Error capturando frame: {e}")
            return None

def is_connected() -> bool:
    """Verifica si hay una cámara conectada"""
    with _lock:
        return _cap is not None

def capturar_frame_limpio():
    """
    Captura un frame LIMPIO de la cámara (RGB, sin overlays).
    
    Esta función es usada por el NUEVO pipeline de análisis.
    
    Returns:
        numpy.ndarray: Frame RGB de OpenCV o None
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
            print(f"[camera] Error capturando frame limpio: {e}")
            return None

# ============================================================
# AUTO-CONEXIÓN
# ============================================================
def auto_connect_from_config() -> Tuple[bool, str]:
    """
    Intenta conectar automáticamente usando config.json
    Returns: (success, message)
    """
    print("[camera] Intentando auto-conexión desde config.json...")
    
    config = load_config()
    cam_config = config.get("camera", {})
    
    uid = cam_config.get("uid")
    if not uid:
        return False, "No hay cámara configurada"
    
    resolution = cam_config.get("preferred_resolution", {})
    width = resolution.get("width")
    height = resolution.get("height")
    
    success, error = connect_camera(uid, width, height)
    
    if success:
        print(f"[camera] ✓ Auto-conexión exitosa: {uid}")
        return True, "Cámara conectada automáticamente"
    else:
        print(f"[camera] ✗ Auto-conexión falló: {error}")
        return False, error

def save_camera_config(uid: str, name: str, width: Optional[int] = None, height: Optional[int] = None):
    """Guarda configuración de cámara en config.json"""
    config = load_config()
    
    config["camera"] = {
        "uid": uid,
        "name": name
    }
    
    if width and height:
        config["camera"]["preferred_resolution"] = {
            "width": width,
            "height": height
        }
    
    save_config(config)
    print(f"[camera] Configuración guardada: {uid} @ {width}x{height}")

