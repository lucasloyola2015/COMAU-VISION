# src/vision/vision_steps/__init__.py

print("[Vision Steps] Módulos del pipeline de visión cargados.")

# Importar funciones de cada paso para que estén disponibles en el paquete
from .step_0_config import load_config, save_config
from .step_1_capture import capturar_imagen
from .step_2_decide_frames import decidir_base_frame, decidir_tool_frame
from .step_3_locate_center import ubicar_centro_troqueladora
from .step_4_roi import dibujar_roi, crear_roi_rectangle_completo, redimensionar_roi_rectangle
from .step_5_crop import hacer_crop_imagen
from .step_6_frames_config import configurar_roi_frame, configurar_junta_frame
from .step_7_detect_gasket import detectar_junta_yolo
from .step_8_detect_holes import detectar_agujeros_yolo
from .step_9_metrics import calcular_metricas_y_segmento

# Importar utilidades si es necesario
from .step_utils import _scale_image_and_coords, _scale_rect