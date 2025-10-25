"""
Frames Manager - Gestión de Marcos de Referencia Específicos del Dominio
=====================================================================

Este script maneja los marcos de referencia específicos del proyecto COMAU-VISION.
La librería overlay_manager.py es genérica y no debe conocer estos marcos específicos.

Implementa un patrón singleton para acceso global a los marcos de referencia.
Lee dinámicamente los marcos desde un archivo JSON de configuración.

Autor: Sistema COMAU-VISION
"""

import json
import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path para imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.overlay import OverlayManager
from typing import Optional, Tuple, Dict, Any

# Instancia global del OverlayManager
_global_overlay_manager: Optional[OverlayManager] = None

# Ruta por defecto del archivo de configuración
DEFAULT_CONFIG_PATH = "overlay_frames.json"


def load_frames_config(config_path: str = DEFAULT_CONFIG_PATH) -> Dict[str, dict]:
    """
    Cargar configuración de marcos desde archivo JSON.
    
    Args:
        config_path: Ruta al archivo JSON de configuración
        
    Returns:
        Diccionario con la configuración de marcos
        
    Raises:
        FileNotFoundError: Si el archivo no existe
        json.JSONDecodeError: Si el JSON es inválido
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    if 'frames' not in config:
        raise ValueError("El archivo JSON debe contener una sección 'frames'")
    
    return config['frames']


def init_global_frames(config_path: str = DEFAULT_CONFIG_PATH) -> OverlayManager:
    """
    Inicializar la instancia global de OverlayManager con marcos específicos del proyecto.
    Lee dinámicamente los marcos desde el archivo JSON de configuración.
    
    Args:
        config_path: Ruta al archivo JSON de configuración
        
    Returns:
        Instancia global de OverlayManager
    """
    global _global_overlay_manager
    
    if _global_overlay_manager is None:
        print(f"[FramesManager] Inicializando instancia global de OverlayManager...")
        _global_overlay_manager = OverlayManager()
        
        # Cargar configuración desde JSON
        try:
            frames_config = load_frames_config(config_path)
            print(f"[FramesManager] ✓ Configuración cargada desde: {config_path}")
            
            # Inicializar marcos dinámicamente desde JSON
            init_frames_from_config(_global_overlay_manager, frames_config)
            print(f"[FramesManager] ✓ Instancia global inicializada")
            
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            print(f"[FramesManager] ⚠️ Error cargando configuración: {e}")
            print(f"[FramesManager] ⚠️ Usando configuración por defecto...")
            
            # Fallback: usar configuración por defecto
            init_project_frames_default(_global_overlay_manager)
            print(f"[FramesManager] ✓ Instancia global inicializada con configuración por defecto")
    
    return _global_overlay_manager


def get_global_overlay_manager() -> OverlayManager:
    """
    Obtener la instancia global de OverlayManager.
    
    Returns:
        Instancia global de OverlayManager
        
    Raises:
        RuntimeError: Si no se ha inicializado la instancia global
    """
    global _global_overlay_manager
    
    if _global_overlay_manager is None:
        raise RuntimeError("OverlayManager global no inicializado. Llama a init_global_frames() primero.")
    
    return _global_overlay_manager


def init_frames_from_config(overlay_manager: OverlayManager, frames_config: Dict[str, dict]) -> None:
    """
    Inicializar marcos de referencia dinámicamente desde configuración JSON.
    
    Args:
        overlay_manager: Instancia de OverlayManager ya inicializada
        frames_config: Diccionario con configuración de marcos desde JSON
    """
    print(f"[FramesManager] Inicializando marcos desde configuración JSON...")
    
    frames_created = 0
    for frame_name, frame_data in frames_config.items():
        try:
            # Extraer datos del marco
            offset_x = frame_data.get('offset_x', 0)
            offset_y = frame_data.get('offset_y', 0)
            rotation = frame_data.get('rotation', 0.0)
            px_per_mm = frame_data.get('px_per_mm', 1.0)
            parent_frame = frame_data.get('parent_frame', 'world')
            
            # Crear el marco
            overlay_manager.define_frame(
                name=frame_name,
                offset=(offset_x, offset_y),
                rotation=rotation,
                px_per_mm=px_per_mm,
                parent_frame=parent_frame
            )
            
            frames_created += 1
            print(f"[FramesManager] ✓ Marco '{frame_name}' inicializado: offset=({offset_x}, {offset_y}), rotation={rotation:.3f}rad, px_per_mm={px_per_mm:.3f}")
            
        except Exception as e:
            print(f"[FramesManager] ⚠️ Error inicializando marco '{frame_name}': {e}")
    
    print(f"[FramesManager] ✓ {frames_created} marcos inicializados desde JSON")


def init_project_frames_default(overlay_manager: OverlayManager) -> None:
    """
    Inicializar marcos de referencia con configuración por defecto (fallback).
    
    Args:
        overlay_manager: Instancia de OverlayManager ya inicializada
    """
    print(f"[FramesManager] Inicializando marcos con configuración por defecto...")
    
    # Marcos por defecto si no se puede cargar el JSON
    default_frames = {
        'base_frame': {'offset_x': 0, 'offset_y': 0, 'rotation': 0.0, 'px_per_mm': 1.0, 'parent_frame': 'world'},
        'tool_frame': {'offset_x': 0, 'offset_y': 0, 'rotation': 0.0, 'px_per_mm': 1.0, 'parent_frame': 'world'},
        'junta_frame': {'offset_x': 0, 'offset_y': 0, 'rotation': 0.0, 'px_per_mm': 1.0, 'parent_frame': 'world'},
        'roi_frame': {'offset_x': 0, 'offset_y': 0, 'rotation': 0.0, 'px_per_mm': 1.0, 'parent_frame': 'world'}
    }
    
    init_frames_from_config(overlay_manager, default_frames)


def init_project_frames(overlay_manager: OverlayManager) -> None:
    """
    Inicializar marcos de referencia específicos del proyecto COMAU-VISION.
    
    Args:
        overlay_manager: Instancia de OverlayManager ya inicializada
    """
    print(f"[FramesManager] Inicializando marcos específicos del proyecto...")
    
    # Marco de referencia base (Frame ArUco)
    overlay_manager.define_frame(
        name="base_frame",
        offset=(0, 0),
        rotation=0.0,
        px_per_mm=1.0,
        parent_frame="world"
    )
    print(f"[FramesManager] ✓ Marco 'base_frame' inicializado")
    
    # Marco de referencia de herramienta (Tool ArUco)
    overlay_manager.define_frame(
        name="tool_frame", 
        offset=(0, 0),
        rotation=0.0,
        px_per_mm=1.0,
        parent_frame="world"
    )
    print(f"[FramesManager] ✓ Marco 'tool_frame' inicializado")
    
    # Marco de referencia de junta
    overlay_manager.define_frame(
        name="junta_frame",
        offset=(0, 0),
        rotation=0.0,
        px_per_mm=1.0,
        parent_frame="world"
    )
    print(f"[FramesManager] ✓ Marco 'junta_frame' inicializado")
    
    # Marco de referencia de ROI (Region of Interest)
    overlay_manager.define_frame(
        name="roi_frame",
        offset=(0, 0),
        rotation=0.0,
        px_per_mm=1.0,
        parent_frame="world"
    )
    print(f"[FramesManager] ✓ Marco 'roi_frame' inicializado")
    
    print(f"[FramesManager] ✓ Todos los marcos del proyecto inicializados")


def update_frame(frame_name: str, offset: Tuple[float, float], 
                rotation: float, px_per_mm: float) -> None:
    """
    Actualizar cualquier marco con valores de calibración.
    
    Args:
        frame_name: Nombre del marco a actualizar
        offset: Posición (x, y) en píxeles
        rotation: Rotación en radianes
        px_per_mm: Relación píxeles por milímetro
    """
    overlay_manager = get_global_overlay_manager()
    
    overlay_manager.update_frame(
        name=frame_name,
        offset=offset,
        rotation=rotation
    )
    
    # Actualizar px_per_mm requiere redefinir el marco
    overlay_manager.define_frame(
        name=frame_name,
        offset=offset,
        rotation=rotation,
        px_per_mm=px_per_mm,
        parent_frame="world"
    )
    print(f"[FramesManager] ✓ Marco '{frame_name}' actualizado: offset={offset}, rotation={rotation:.3f}rad, px_per_mm={px_per_mm:.3f}")


def get_frame_info(frame_name: str) -> Optional[dict]:
    """
    Obtener información de un marco específico.
    
    Args:
        frame_name: Nombre del marco
        
    Returns:
        Diccionario con información del marco o None si no existe
    """
    overlay_manager = get_global_overlay_manager()
    
    try:
        frame = overlay_manager.get_frame(frame_name)
        return {
            'name': frame.name,
            'offset': (frame.offset_x, frame.offset_y),
            'rotation': frame.rotation,
            'px_per_mm': frame.px_per_mm,
            'parent_frame': frame.parent_frame
        }
    except ValueError:
        return None


def list_project_frames() -> list:
    """
    Listar todos los marcos específicos del proyecto.
    Excluye el marco 'world' que es genérico.
        
    Returns:
        Lista de nombres de marcos del proyecto
    """
    overlay_manager = get_global_overlay_manager()
    all_frames = overlay_manager.list_frames()
    
    # Excluir el marco 'world' que es genérico
    project_frames = [frame for frame in all_frames if frame != 'world']
    return project_frames


# ============================================================
# FUNCIONES DE CONVENIENCIA PARA ACCESO GLOBAL
# ============================================================

def add_line_to_frame(frame_name: str, start: Tuple[float, float], end: Tuple[float, float],
                     name: str, color=None, thickness=None, **kwargs) -> None:
    """Agregar línea a un marco específico usando la instancia global"""
    overlay_manager = get_global_overlay_manager()
    overlay_manager.add_line(frame_name, start, end, name, color, thickness, **kwargs)


def add_circle_to_frame(frame_name: str, center: Tuple[float, float], radius: float,
                       name: str, color=None, thickness=None, filled=False, **kwargs) -> None:
    """Agregar círculo a un marco específico usando la instancia global"""
    overlay_manager = get_global_overlay_manager()
    overlay_manager.add_circle(frame_name, center, radius, name, color, thickness, filled, **kwargs)


def add_text_to_frame(frame_name: str, position: Tuple[float, float], text: str,
                     name: str, color=None, font_scale=1.0, thickness=None, **kwargs) -> None:
    """Agregar texto a un marco específico usando la instancia global"""
    overlay_manager = get_global_overlay_manager()
    overlay_manager.add_text(frame_name, position, text, name, color, font_scale, thickness, **kwargs)


def render_global(background_image, renderlist=None, show_frames=None, view_time=5000):
    """Renderizar usando la instancia global"""
    overlay_manager = get_global_overlay_manager()
    return overlay_manager.render(background_image, renderlist, show_frames, view_time)
