# step_utils.py
"""
Utilidades para el pipeline de visión
"""

import os
import json
import cv2

CONFIG_FILE = 'config.json'

def load_config():
    """Cargar configuración - compatibilidad con step_2_frames.py"""
    from .step_0_config import load_config as _load_config
    return _load_config()

def save_config(config_data):
    """Guarda la configuración completa en config.json"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def _scale_image_and_coords(image, scale_percent):
    """Redimensionar imagen y calcular factor de escala"""
    import cv2
    
    if scale_percent == 100:
        return image, 1.0
    
    width = int(image.shape[1] * scale_percent / 100)
    height = int(image.shape[0] * scale_percent / 100)
    
    resized = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    scale_factor = 100.0 / scale_percent
    
    return resized, scale_factor

def _scale_rect(rect, scale_factor):
    """Redimensionar rectangle - acepta dict o tupla (x1, y1, x2, y2)"""
    if isinstance(rect, dict):
        return {
            'x': rect['x'] * scale_factor,
            'y': rect['y'] * scale_factor,
            'width': rect['width'] * scale_factor,
            'height': rect['height'] * scale_factor
        }
    else:
        # Tupla (x1, y1, x2, y2)
        return tuple(c * scale_factor for c in rect)