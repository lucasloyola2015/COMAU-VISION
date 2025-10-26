# src/vision/vision_steps/__init__.py

print("[Vision Module] Paquete de visión cargado.")

# Importar funciones de cada paso para que estén disponibles en el paquete
from . import step_0_config
from . import step_1_capture
from . import step_2_frames
from . import step_3_roi
from . import step_4_yolo
from . import step_5_refinement

# Importar utilidades si es necesario
from . import step_utils