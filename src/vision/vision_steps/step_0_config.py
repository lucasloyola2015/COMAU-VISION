# step_0_config.py
"""
Configuración del sistema de visión
"""

import json
import os

CONFIG_FILE = 'config.json'

def load_config():
    """Carga la configuración completa desde config.json"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'vision': {}, 'aruco': {}}
    except Exception as e:
        print(f"[step_0_config] Error cargando configuración: {e}")
        return {'vision': {}, 'aruco': {}}

def save_config(config_data):
    """Guarda la configuración completa en config.json"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        print(f"[step_0_config] ✓ Configuración guardada")
        return True
    except Exception as e:
        print(f"[step_0_config] ✗ Error guardando configuración: {e}")
        return False

