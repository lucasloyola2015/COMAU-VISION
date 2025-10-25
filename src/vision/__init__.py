# Vision module - Gestión de cámaras, detección de objetos y análisis visual
from src.vision.camera_manager import *
from src.vision.aruco_manager import *
from src.vision.yolo_detector import *
from src.vision.opencv_config import *
from src.vision.frames_manager import *

# Inicialización automática de marcos al importar el módulo
try:
    print("[Vision Module] Inicializando marcos de referencia...")
    init_global_frames()
    print("[Vision Module] ✓ Marcos de referencia inicializados automáticamente")
except Exception as e:
    print(f"[Vision Module] ⚠️ Error inicializando marcos: {e}")
    print("[Vision Module] ⚠️ Los marcos se inicializarán manualmente cuando sea necesario")
