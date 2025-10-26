# aruco_manager.py - Gestión Específica de ArUcos del Proyecto
"""
Gestor específico de ArUcos para el proyecto COMAU-VISION.
Utiliza la librería genérica lib/aruco_detector.py para funcionalidades específicas del dominio.

Funcionalidades específicas:
- Detección de ArUcos Frame y Tool
- Creación de marcos temporales específicos
- Generación de overlays con colores del proyecto
- Integración con overlay_manager del proyecto
"""

import numpy as np
from typing import Dict, Any, Optional
import sys
import os

# Agregar lib al path para importar la librería genérica
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

from aruco import detect_arucos_with_config, get_available_dictionaries, get_available_marker_sizes

# ============================================================
# CONFIGURACIÓN ESPECÍFICA DEL PROYECTO
# ============================================================

# Colores específicos del proyecto
FRAME_COLOR = (0, 255, 255)  # Amarillo para Frame
TOOL_COLOR = (255, 0, 0)     # Azul para Tool
OTHER_COLOR = (255, 255, 0)  # Cian para otros

# Nombres de marcos específicos del proyecto
FRAME_TEMP_NAME = "base_frame_temp"
TOOL_TEMP_NAME = "tool_frame_temp"

def scale_detection_results(result: Dict[str, Any], scale_factor: float) -> Dict[str, Any]:
    """
    Escala las coordenadas de un resultado de detección de ArUcos.
    
    Args:
        result: Diccionario con el resultado de la detección.
        scale_factor: Factor de escala a aplicar (e.g., 0.5 para 50%).
        
    Returns:
        Diccionario con el resultado y las coordenadas escaladas a 100%.
    """
    if scale_factor == 1.0:
        return result

    print(f"[ArUcoManager] 🔧 Escalando coordenadas de {scale_factor:.1%} a 100%")
    detected_arucos = result.get('detected_arucos', {})
    for aruco_id, aruco_data in detected_arucos.items():
        # Escalar center
        if 'center' in aruco_data:
            aruco_data['center'] = (aruco_data['center'][0] / scale_factor, aruco_data['center'][1] / scale_factor)
        
        # Escalar corners
        if 'corners' in aruco_data:
            aruco_data['corners'] = [(c[0] / scale_factor, c[1] / scale_factor) for c in aruco_data['corners']]
        
        # Escalar px_per_mm
        if 'px_per_mm' in aruco_data:
            aruco_data['px_per_mm'] /= scale_factor
            
    return result

def detect_arucos_in_image(image: np.ndarray, frame_aruco_id: int, tool_aruco_id: int, 
                          frame_marker_size_mm: float = 70.0, tool_marker_size_mm: float = 50.0,
                          dictionary_id: int = 50, marker_bits: int = 4, scale_factor: float = 1.0) -> Dict[str, Any]:
    """
    Detectar ArUcos en imagen usando configuración específica del proyecto.
    
    Args:
        image: Imagen en escala de grises
        frame_aruco_id: ID del ArUco Frame
        tool_aruco_id: ID del ArUco Tool
        frame_marker_size_mm: Tamaño del marcador frame en mm
        tool_marker_size_mm: Tamaño del marcador tool en mm
        dictionary_id: ID del diccionario ArUco
        marker_bits: Tamaño de la matriz del marcador
        scale_factor: Factor de escala de la imagen (1.0 = 100%, 0.5 = 50%)
        
    Returns:
        Diccionario con información de detección específica del proyecto.
        Las coordenadas SIEMPRE se devuelven en escala 100% (invariante a scale_factor).
    """
    try:
        print(f"[ArUcoManager] Detectando ArUcos específicos del proyecto")
        print(f"[ArUcoManager] Frame ID: {frame_aruco_id}, Tool ID: {tool_aruco_id}")
        
        # Configuración específica del proyecto
        aruco_configs = [
            {
                'id': frame_aruco_id,
                'name': 'frame',
                'size_mm': frame_marker_size_mm,
                'color': FRAME_COLOR
            },
            {
                'id': tool_aruco_id,
                'name': 'tool',
                'size_mm': tool_marker_size_mm,
                'color': TOOL_COLOR
            }
        ]
        
        # Usar librería genérica
        result = detect_arucos_with_config(image, aruco_configs, dictionary_id, marker_bits)
        
        # Escalar coordenadas de vuelta a 100% si es necesario
        result = scale_detection_results(result, scale_factor)
        
        # Adaptar resultado a formato específico del proyecto
        frame_detected = result.get('detection_status', {}).get('frame', False)
        tool_detected = result.get('detection_status', {}).get('tool', False)
        
        return {
            'detected_arucos': result.get('detected_arucos', {}),
            'detected_ids': result.get('detected_ids', []),
            'frame_detected': frame_detected,
            'tool_detected': tool_detected,
            'frame_aruco_id': frame_aruco_id,
            'tool_aruco_id': tool_aruco_id
        }
        
    except Exception as e:
        print(f"[ArUcoManager] ❌ Error detectando ArUcos: {e}")
        return {
            'detected_arucos': {},
            'detected_ids': [],
            'frame_detected': False,
            'tool_detected': False,
            'error': str(e)
        }

def create_temp_frames_from_arucos(overlay_manager, detection_result: Dict[str, Any]) -> None:
    """
    Crear marcos temporales específicos del proyecto basados en detección de ArUcos.
    
    Args:
        overlay_manager: Instancia de OverlayManager del proyecto
        detection_result: Resultado de detect_arucos_in_image()
    """
    detected_arucos = detection_result.get('detected_arucos', {})
    frame_aruco_id = detection_result.get('frame_aruco_id', 0)
    tool_aruco_id = detection_result.get('tool_aruco_id', 0)
    
    # Crear/actualizar frame temporal del Frame ArUco
    if frame_aruco_id in detected_arucos:
        frame_data = detected_arucos[frame_aruco_id]
        overlay_manager.define_frame(
            FRAME_TEMP_NAME,
            offset=frame_data['center'],
            rotation=frame_data['angle_rad'],
            px_per_mm=frame_data['px_per_mm'],
            parent_frame="world"
        )
        print(f"[ArUcoManager] ✓ Marco temporal '{FRAME_TEMP_NAME}' creado desde ArUco {frame_aruco_id}")
    
    # Crear/actualizar frame temporal del Tool ArUco
    if tool_aruco_id in detected_arucos:
        tool_data = detected_arucos[tool_aruco_id]
        overlay_manager.define_frame(
            TOOL_TEMP_NAME,
            offset=tool_data['center'],
            rotation=tool_data['angle_rad'],
            px_per_mm=tool_data['px_per_mm'],
            parent_frame="world"
        )
        print(f"[ArUcoManager] ✓ Marco temporal '{TOOL_TEMP_NAME}' creado desde ArUco {tool_aruco_id}")

def clear_aruco_objects(overlay_manager) -> None:
    """
    Limpiar todos los objetos de ArUcos y centro del troquel existentes.
    
    Args:
        overlay_manager: Instancia de OverlayManager del proyecto
    """
    # Limpiar objetos de ArUcos y centro del troquel
    objects_to_remove = []
    for name, obj in overlay_manager.objects.items():
        if name.startswith('aruco_') or name == 'center_circle':
            objects_to_remove.append(name)
    
    for obj_name in objects_to_remove:
        if obj_name in overlay_manager.objects:
            del overlay_manager.objects[obj_name]
    
    # Limpiar listas de renderizado existentes
    if "aruco_overlay" in overlay_manager.renderlists:
        del overlay_manager.renderlists["aruco_overlay"]
    
    print(f"[ArUcoManager] ✓ Objetos limpiados: {len(objects_to_remove)}")
    print(f"[ArUcoManager] Objetos restantes: {list(overlay_manager.objects.keys())}")

def create_aruco_overlay_objects(overlay_manager, detection_result: Dict[str, Any], show_frame: bool = True, show_tool: bool = True) -> None:
    """
    Crear objetos de overlay específicos del proyecto para ArUcos detectados.
    
    Args:
        overlay_manager: Instancia de OverlayManager del proyecto
        detection_result: Resultado de detect_arucos_in_image()
        show_frame: Si mostrar el ArUco Frame
        show_tool: Si mostrar el ArUco Tool
    """
    detected_arucos = detection_result.get('detected_arucos', {})
    frame_aruco_id = detection_result.get('frame_aruco_id', 0)
    tool_aruco_id = detection_result.get('tool_aruco_id', 0)
    
    # Crear objetos solo para ArUcos que deben mostrarse
    for aruco_id, aruco_data in detected_arucos.items():
        center = aruco_data['center']
        angle_rad = aruco_data['angle_rad']
        corners = aruco_data['corners']
        px_per_mm = aruco_data['px_per_mm']
        
        # Determinar si este ArUco debe mostrarse
        should_show = False
        if aruco_id == frame_aruco_id and show_frame:
            should_show = True
            color = FRAME_COLOR
            frame_name = FRAME_TEMP_NAME
        elif aruco_id == tool_aruco_id and show_tool:
            should_show = True
            color = TOOL_COLOR
            frame_name = TOOL_TEMP_NAME
        elif aruco_id != frame_aruco_id and aruco_id != tool_aruco_id:
            # ArUcos no esperados siempre se muestran
            should_show = True
            color = OTHER_COLOR
            frame_name = "world"
        
        # Solo crear objetos si debe mostrarse
        if not should_show:
            print(f"[ArUcoManager] ⚡ ArUco {aruco_id} OMITIDO (checkbox deshabilitado)")
            continue
        
        # Dibujar contorno del ArUco
        overlay_manager.add_polygon(
            frame_name,
            points=corners,
            name=f"aruco_contour_{aruco_id}",
            color=color,
            thickness=2
        )
        
        # Dibujar ejes usando el marco temporal del ArUco.
        # Se definen como líneas simples en el sistema de coordenadas del ArUco,
        # y la librería se encarga de la rotación y traslación.
        axis_length_mm = 1000  # Un valor grande para que cruce toda la imagen
        
        # Eje X - desde el centro del marco temporal
        overlay_manager.add_line(
            frame_name,  # Usar el marco temporal del ArUco
            start=(-axis_length_mm, 0),  # Coordenadas relativas al marco
            end=(axis_length_mm, 0),
            name=f"aruco_x_axis_{aruco_id}",
            color=(0, 0, 255),  # Eje X siempre ROJO
            thickness=2,
            units="mm"
        )
        
        # Eje Y - desde el centro del marco temporal
        overlay_manager.add_line(
            frame_name,  # Usar el marco temporal del ArUco
            start=(0, -axis_length_mm),  # Coordenadas relativas al marco
            end=(0, axis_length_mm),
            name=f"aruco_y_axis_{aruco_id}",
            color=(0, 255, 0),  # Eje Y siempre VERDE
            thickness=2,
            units="mm"
        )
        
        # Agregar centro
        overlay_manager.add_circle(
            frame_name,
            center=(0, 0),  # Centro relativo al marco
            radius=5,
            name=f"aruco_center_{aruco_id}",
            color=color,
            filled=True
        )
        
        print(f"[ArUcoManager] ✓ Objetos de overlay creados para ArUco {aruco_id} en marco {frame_name}")
        
        print(f"[ArUcoManager] ✓ Objetos de overlay creados para ArUco {aruco_id}")

def create_center_reference(overlay_manager, center_x: float, center_y: float, 
                          frame_aruco_id: int, is_frame_detected: bool) -> None:
    """
    Crear centro del troquel usando coordenadas dinámicas.
    Las coordenadas son relativas al marco temporal del ArUco Base.
    
    Args:
        overlay_manager: Instancia de OverlayManager del proyecto
        center_x: Coordenada X del centro en mm (relativa al base_frame_temp)
        center_y: Coordenada Y del centro en mm (relativa al base_frame_temp)
        frame_aruco_id: ID del ArUco Base
        is_frame_detected: Si el ArUco Base fue detectado
    """
    # Usar marco temporal del ArUco Base si está disponible
    if is_frame_detected:
        frame_name = FRAME_TEMP_NAME  # "base_frame_temp"
        print(f"[ArUcoManager] Centro del troquel: usando marco base_frame_temp ({center_x}, {center_y}) mm")
    else:
        frame_name = "base_frame"  # Marco base_frame como fallback
        print(f"[ArUcoManager] Centro del troquel: usando marco base_frame ({center_x}, {center_y}) mm")
    
    overlay_manager.add_circle(
        frame_name,
        center=(center_x, center_y),  # Coordenadas en mm relativas al marco
        radius=5.0,  # 5mm de radio
        name="center_circle",
        color=(255, 255, 0),  # Cyan
        filled=True
    )
    print(f"[ArUcoManager] ✓ Centro del troquel creado")

def create_renderlist(overlay_manager, overlay_objects: list) -> str:
    """
    Crear lista de renderizado con objetos habilitados.
    
    Args:
        overlay_manager: Instancia de OverlayManager del proyecto
        overlay_objects: Lista de objetos a renderizar
        
    Returns:
        Nombre de la renderlist creada
    """
    # create_renderlist espera *args, no una lista
    renderlist_name = overlay_manager.create_renderlist(*overlay_objects, name="aruco_overlay")
    print(f"[ArUcoManager] ✓ Lista de renderizado '{renderlist_name}' creada con {len(overlay_objects)} objetos")
    return renderlist_name

def save_aruco_configuration(overlay_manager, cv2_frame, aruco_config):
    """
    Guardar configuración de ArUcos y objetos de renderizado persistentes.
    
    Args:
        overlay_manager: Instancia de OverlayManager del proyecto
        cv2_frame: Frame actual de la cámara
        aruco_config: Configuración de ArUcos desde config.json
        
    Returns:
        Dict con información del guardado
    """
    # Detectar ArUcos para obtener frames temporales
    frame_aruco_id = aruco_config.get('base', {}).get('reference_id', 0)
    tool_aruco_id = aruco_config.get('tool', {}).get('reference_id', 0)
    frame_marker_size = aruco_config.get('base', {}).get('marker_size_mm', 70.0)
    tool_marker_size = aruco_config.get('tool', {}).get('marker_size_mm', 50.0)
    
    # Detectar ArUcos usando aruco_manager
    detection_result = detect_arucos_in_image(
        image=cv2_frame,
        frame_aruco_id=frame_aruco_id,
        tool_aruco_id=tool_aruco_id,
        frame_marker_size_mm=frame_marker_size,
        tool_marker_size_mm=tool_marker_size,
        dictionary_id=aruco_config.get('base', {}).get('dictionary_id', 50),
        marker_bits=aruco_config.get('base', {}).get('marker_bits', 4),
        scale_factor=1.0  # Siempre 100% para overlays
    )
    
    base_detected = is_frame_detected(detection_result)
    tool_detected = is_tool_detected(detection_result)
    
    print(f"[ArUcoManager] Guardando configuración:")
    print(f"  - Base ArUco (ID: {frame_aruco_id}) detectado: {base_detected}")
    print(f"  - Tool ArUco (ID: {tool_aruco_id}) detectado: {tool_detected}")
    
    # Crear marcos temporales si están detectados
    if base_detected or tool_detected:
        create_temp_frames_from_arucos(overlay_manager, detection_result)
        print(f"[ArUcoManager] ✓ Marcos temporales creados")
    
    # Crear objetos de overlay persistentes
    objects_to_save = []
    
    if base_detected or tool_detected:
        create_aruco_overlay_objects(overlay_manager, detection_result)
        
        # Recopilar objetos creados
        aruco_objects = [name for name, obj in overlay_manager.objects.items() 
                        if obj.name.startswith('aruco_')]
        objects_to_save.extend(aruco_objects)
        print(f"[ArUcoManager] ✓ Objetos de ArUcos creados: {len(aruco_objects)}")
    
    # Crear centro del troquel si está habilitado
    if aruco_config.get('show_center', False):
        center_x = aruco_config.get('base', {}).get('center_x_mm', 0.0)
        center_y = aruco_config.get('base', {}).get('center_y_mm', 0.0)
        create_center_reference(overlay_manager, center_x, center_y, base_detected, base_detected)
        objects_to_save.append("center_circle")
        print(f"[ArUcoManager] ✓ Centro del troquel creado")
    
    return {
        'base_detected': base_detected,
        'tool_detected': tool_detected,
        'objects_created': len(objects_to_save),
        'objects_list': objects_to_save
    }

# ============================================================
# FUNCIONES DE UTILIDAD ESPECÍFICAS
# ============================================================

def get_frame_aruco_info(detection_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Obtiene información específica del ArUco Frame"""
    frame_aruco_id = detection_result.get('frame_aruco_id', 0)
    detected_arucos = detection_result.get('detected_arucos', {})
    return detected_arucos.get(frame_aruco_id)

def get_tool_aruco_info(detection_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Obtiene información específica del ArUco Tool"""
    tool_aruco_id = detection_result.get('tool_aruco_id', 0)
    detected_arucos = detection_result.get('detected_arucos', {})
    return detected_arucos.get(tool_aruco_id)

def is_frame_detected(detection_result: Dict[str, Any]) -> bool:
    """Verifica si el ArUco Frame fue detectado"""
    return detection_result.get('frame_detected', False)

def is_tool_detected(detection_result: Dict[str, Any]) -> bool:
    """Verifica si el ArUco Tool fue detectado"""
    return detection_result.get('tool_detected', False)

# ============================================================
# FUNCIONES DE CONFIGURACIÓN
# ============================================================

def get_available_dictionaries() -> Dict[int, str]:
    """Devuelve diccionarios ArUco disponibles (wrapper de la librería genérica)"""
    return get_available_dictionaries()

def get_available_marker_sizes() -> Dict[int, str]:
    """Devuelve tamaños de matriz ArUco disponibles (wrapper de la librería genérica)"""
    return get_available_marker_sizes()

def render_overlay_with_arucos(overlay_manager, cv2_frame, frame_aruco_id, tool_aruco_id, 
                              frame_marker_size, tool_marker_size, center_x, center_y,
                              show_frame, show_tool, show_center):
    """
    Renderizar overlay con ArUcos detectados - función principal para el endpoint /api/overlay/render
    
    Args:
        overlay_manager: Instancia global de OverlayManager
        cv2_frame: Frame de la cámara
        frame_aruco_id: ID del ArUco Frame
        tool_aruco_id: ID del ArUco Tool
        frame_marker_size: Tamaño del marcador frame en mm
        tool_marker_size: Tamaño del marcador tool en mm
        center_x: Coordenada X del centro del troquel en mm
        center_y: Coordenada Y del centro del troquel en mm
        show_frame: Mostrar ArUco Frame
        show_tool: Mostrar ArUco Tool
        show_center: Mostrar centro del troquel
        
    Returns:
        Dict con resultado del renderizado
    """
    try:
        print(f"[ArUcoManager] Renderizando overlay con ArUcos")
        print(f"[ArUcoManager] Frame ID: {frame_aruco_id}, Tool ID: {tool_aruco_id}")
        print(f"[ArUcoManager] Show Frame: {show_frame}, Show Tool: {show_tool}, Show Center: {show_center}")
        
        # Limpiar objetos existentes
        clear_aruco_objects(overlay_manager)
        
        # Detectar ArUcos SIEMPRE (independiente de checkboxes)
        detection_result = detect_arucos_in_image(
            image=cv2_frame,
            frame_aruco_id=frame_aruco_id,
            tool_aruco_id=tool_aruco_id,
            frame_marker_size_mm=frame_marker_size,
            tool_marker_size_mm=tool_marker_size,
            scale_factor=1.0  # Siempre 100% para overlays
        )
        
        # Crear marcos temporales si están detectados
        if detection_result and (is_frame_detected(detection_result) or is_tool_detected(detection_result)):
            create_temp_frames_from_arucos(overlay_manager, detection_result)
        
        # Crear objetos de overlay
        overlay_objects = []
        
        # Crear objetos de ArUcos
        create_aruco_overlay_objects(overlay_manager, detection_result, show_frame, show_tool)
        
        # Agregar objetos a la lista SOLO si sus checkboxes están habilitados
        if show_frame and is_frame_detected(detection_result):
            frame_aruco_id = detection_result.get('frame_aruco_id', 0)
            overlay_objects.append(f"aruco_contour_{frame_aruco_id}")
            overlay_objects.append(f"aruco_x_axis_{frame_aruco_id}")
            overlay_objects.append(f"aruco_y_axis_{frame_aruco_id}")
            overlay_objects.append(f"aruco_center_{frame_aruco_id}")
            print(f"[ArUcoManager] ✓ Frame ArUco {frame_aruco_id} agregado a renderlist")
        
        if show_tool and is_tool_detected(detection_result):
            tool_aruco_id = detection_result.get('tool_aruco_id', 0)
            overlay_objects.append(f"aruco_contour_{tool_aruco_id}")
            overlay_objects.append(f"aruco_x_axis_{tool_aruco_id}")
            overlay_objects.append(f"aruco_y_axis_{tool_aruco_id}")
            overlay_objects.append(f"aruco_center_{tool_aruco_id}")
            print(f"[ArUcoManager] ✓ Tool ArUco {tool_aruco_id} agregado a renderlist")
        
        if show_center:
            frame_aruco_id = detection_result.get('frame_aruco_id', 0)
            frame_detected = is_frame_detected(detection_result)
            create_center_reference(overlay_manager, center_x, center_y, frame_aruco_id, frame_detected)
            overlay_objects.append("center_circle")
            print(f"[ArUcoManager] ✓ Centro del troquel agregado a renderlist")
        
        # Crear lista de renderizado solo si hay objetos
        if overlay_objects:
            create_renderlist(overlay_manager, overlay_objects)
            print(f"[ArUcoManager] ✓ Renderlist creada con {len(overlay_objects)} objetos")
        else:
            print(f"[ArUcoManager] ⚠️ No hay objetos para renderizar - solo imagen en escala de grises")
        
        return {
            'ok': True,
            'detection_result': detection_result,
            'overlay_objects': overlay_objects,
            'frame_detected': is_frame_detected(detection_result) if detection_result else False,
            'tool_detected': is_tool_detected(detection_result) if detection_result else False,
            'has_objects': len(overlay_objects) > 0
        }
        
    except Exception as e:
        print(f"[ArUcoManager] ❌ Error renderizando overlay: {e}")
        return {
            'ok': False,
            'error': str(e)
        }
