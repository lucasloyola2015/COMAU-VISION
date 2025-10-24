"""
Sistema Inteligente de Overlays - COMAU-VISION
==============================================

Sistema completo de gestión de overlays con transformaciones dinámicas entre 
múltiples sistemas de coordenadas.

Características:
- Marcos de coordenadas dinámicos (Base, Frame, Tool, YOLO, etc.)
- Transformaciones bidireccionales automáticas
- Objetos nombrados con consulta de coordenadas
- Actualización dinámica de marcos
- Renderizado con control granular
- Soporte para imágenes de fondo
- Parámetro viewTime para control de visualización

Autor: Sistema COMAU-VISION
"""

import cv2
import numpy as np
import json
import os
from typing import Dict, List, Tuple, Optional, Union, Any
from dataclasses import dataclass
from enum import Enum


class ObjectType(Enum):
    """Tipos de objetos geométricos soportados"""
    LINE = "line"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    SEGMENT = "segment"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"
    TEXT = "text"
    BACKGROUND = "background"


@dataclass
class CoordinateFrame:
    """Marco de coordenadas con offset y rotación"""
    name: str
    offset_x: float
    offset_y: float
    rotation: float  # en radianes
    px_per_mm: float  # Relación píxeles por milímetro
    parent_frame: Optional[str] = None  # None para Base
    is_temporary: bool = False  # Si es marco temporal para calibración


@dataclass
class DrawingObject:
    """Objeto de dibujo con todas sus propiedades"""
    name: str
    type: ObjectType
    original_frame: str
    coordinates: Dict[str, Any]
    properties: Dict[str, Any]
    created_at: float


class OverlayManager:
    """
    Gestor principal del sistema de overlays.
    
    Maneja marcos de coordenadas, objetos de dibujo, transformaciones
    y renderizado con control granular.
    """
    
    def __init__(self):
        """Inicializar el gestor de overlays"""
        self.frames: Dict[str, CoordinateFrame] = {}
        self.objects: Dict[str, DrawingObject] = {}
        self.renderlists: Dict[str, List[str]] = {}
        self.backgrounds: Dict[str, np.ndarray] = {}
        
        # Definir marco world por defecto
        self.define_frame("world", offset=(0, 0), rotation=0.0, px_per_mm=1.0)
        
        # Definir marcos base_frame, tool_frame y junta_frame por defecto
        self.define_frame("base_frame", offset=(0, 0), rotation=0.0, px_per_mm=1.0)
        self.define_frame("tool_frame", offset=(0, 0), rotation=0.0, px_per_mm=1.0)
        self.define_frame("junta_frame", offset=(0, 0), rotation=0.0, px_per_mm=1.0)
        
        print(f"[OverlayManager] ✓ Marcos inicializados al inicio del sistema:")
        print(f"  - world: offset=(0, 0), px_per_mm=1.0")
        print(f"  - base_frame: offset=(0, 0), px_per_mm=1.0")
        print(f"  - tool_frame: offset=(0, 0), px_per_mm=1.0")
        print(f"  - junta_frame: offset=(0, 0), px_per_mm=1.0")
        
        # Configuración por defecto
        self.default_properties = {
            'color': (0, 255, 0),  # Verde por defecto
            'thickness': 2,
            'line_type': cv2.LINE_AA
        }
        
        # Cargar configuración persistente
        self.load_persistent_config()
    
    # ============================================================
    # GESTIÓN DE MARCOS DE COORDENADAS
    # ============================================================
    
    def define_frame(self, name: str, offset: Tuple[float, float], 
                    rotation: float, px_per_mm: float = 1.0, 
                    parent_frame: str = "world", is_temporary: bool = False) -> None:
        """
        Definir un nuevo marco de coordenadas.
        
        Args:
            name: Nombre del marco
            offset: Desplazamiento (x, y) respecto al marco padre
            rotation: Rotación en radianes
            px_per_mm: Relación píxeles por milímetro
            parent_frame: Marco padre (default: "world")
            is_temporary: Si es marco temporal para calibración
        """
        if name in self.frames:
            print(f"[OverlayManager] ⚠️ Marco '{name}' ya existe, actualizando...")
        
        self.frames[name] = CoordinateFrame(
            name=name,
            offset_x=offset[0],
            offset_y=offset[1],
            rotation=rotation,
            px_per_mm=px_per_mm,
            parent_frame=parent_frame,
            is_temporary=is_temporary
        )
        
        print(f"[OverlayManager] ✓ Marco '{name}' definido: offset={offset}, rotation={rotation:.3f}rad, px_per_mm={px_per_mm:.3f}")
    
    def update_frame(self, name: str, offset: Optional[Tuple[float, float]] = None,
                    rotation: Optional[float] = None) -> None:
        """
        Actualizar un marco de coordenadas existente.
        
        Args:
            name: Nombre del marco a actualizar
            offset: Nuevo desplazamiento (opcional)
            rotation: Nueva rotación en radianes (opcional)
        """
        if name not in self.frames:
            raise ValueError(f"Marco '{name}' no existe")
        
        frame = self.frames[name]
        
        if offset is not None:
            frame.offset_x, frame.offset_y = offset
            print(f"[OverlayManager] ✓ Marco '{name}' actualizado: offset={offset}")
        
        if rotation is not None:
            frame.rotation = rotation
            print(f"[OverlayManager] ✓ Marco '{name}' actualizado: rotation={rotation:.3f}rad")
    
    def get_frame(self, name: str) -> CoordinateFrame:
        """Obtener información de un marco"""
        if name not in self.frames:
            raise ValueError(f"Marco '{name}' no existe")
        return self.frames[name]
    
    def list_frames(self) -> List[str]:
        """Listar todos los marcos definidos"""
        return list(self.frames.keys())
    
    # ============================================================
    # TRANSFORMACIONES DE COORDENADAS
    # ============================================================
    
    def _transform_point(self, point: Tuple[float, float], from_frame: str, 
                        to_frame: str) -> Tuple[float, float]:
        """
        Transformar un punto entre marcos de coordenadas.
        
        Args:
            point: Punto (x, y) a transformar
            from_frame: Marco origen
            to_frame: Marco destino
            
        Returns:
            Punto transformado (x, y)
        """
        if from_frame == to_frame:
            return point
        
        # Obtener marcos
        from_frame_obj = self.frames[from_frame]
        to_frame_obj = self.frames[to_frame]
        
        # Convertir a numpy para cálculos
        point = np.array(point, dtype=float)
        
        # PASO 1: Convertir de mm a píxeles usando px_per_mm del marco origen
        # Las coordenadas vienen en mm, las convertimos a píxeles
        point_px = point * from_frame_obj.px_per_mm
        
        # PASO 2: Aplicar transformación del marco origen
        cos_rot = np.cos(from_frame_obj.rotation)
        sin_rot = np.sin(from_frame_obj.rotation)
        
        # Rotar punto
        rotated_x = point_px[0] * cos_rot - point_px[1] * sin_rot
        rotated_y = point_px[0] * sin_rot + point_px[1] * cos_rot
        
        # Aplicar offset del marco origen
        world_x = rotated_x + from_frame_obj.offset_x
        world_y = rotated_y + from_frame_obj.offset_y
        
        # PASO 3: Transformar al marco destino (transformación inversa)
        cos_rot_dest = np.cos(-to_frame_obj.rotation)
        sin_rot_dest = np.sin(-to_frame_obj.rotation)
        
        # Restar offset del marco destino
        local_x = world_x - to_frame_obj.offset_x
        local_y = world_y - to_frame_obj.offset_y
        
        # Rotar al marco destino
        final_x = local_x * cos_rot_dest - local_y * sin_rot_dest
        final_y = local_x * sin_rot_dest + local_y * cos_rot_dest
        
        # PASO 4: Convertir de píxeles a mm usando px_per_mm del marco destino
        # Solo si el marco destino no es "world" (que siempre está en píxeles)
        if to_frame != "world":
            final_x = final_x / to_frame_obj.px_per_mm
            final_y = final_y / to_frame_obj.px_per_mm
        
        return (float(final_x), float(final_y))
    
    def _transform_coordinates(self, coordinates: Dict[str, Any], 
                              from_frame: str, to_frame: str) -> Dict[str, Any]:
        """
        Transformar todas las coordenadas de un objeto entre marcos.
        
        Args:
            coordinates: Diccionario con coordenadas del objeto
            from_frame: Marco origen
            to_frame: Marco destino
            
        Returns:
            Coordenadas transformadas
        """
        if from_frame == to_frame:
            return coordinates.copy()
        
        transformed = {}
        
        for key, value in coordinates.items():
            if isinstance(value, (list, tuple)) and len(value) == 2:
                # Es un punto (x, y)
                transformed[key] = self._transform_point(value, from_frame, to_frame)
            elif isinstance(value, list) and all(isinstance(p, (list, tuple)) and len(p) == 2 for p in value):
                # Es una lista de puntos
                transformed[key] = [self._transform_point(p, from_frame, to_frame) for p in value]
            else:
                # No es una coordenada, mantener igual
                transformed[key] = value
        
        return transformed
    
    # ============================================================
    # GESTIÓN DE OBJETOS DE DIBUJO
    # ============================================================
    
    def add_line(self, frame: str, start: Tuple[float, float], end: Tuple[float, float],
                 name: str, color: Union[str, Tuple[int, int, int]] = None, 
                 thickness: int = None, **kwargs) -> None:
        """Agregar línea"""
        if name in self.objects:
            raise ValueError(f"Objeto '{name}' ya existe")
        
        # Convertir color a BGR si es string
        if isinstance(color, str):
            color = self._parse_color(color)
        elif color is None:
            color = self.default_properties['color']
        
        obj = DrawingObject(
            name=name,
            type=ObjectType.LINE,
            original_frame=frame,
            coordinates={'start': start, 'end': end},
            properties={
                'color': color,
                'thickness': thickness or self.default_properties['thickness'],
                **kwargs
            },
            created_at=0.0  # TODO: usar timestamp real
        )
        
        self.objects[name] = obj
        print(f"[OverlayManager] ✓ Línea '{name}' agregada en marco '{frame}'")
    
    def add_circle(self, frame: str, center: Tuple[float, float], radius: float,
                   name: str, color: Union[str, Tuple[int, int, int]] = None,
                   thickness: int = None, filled: bool = False, **kwargs) -> None:
        """Agregar círculo"""
        if name in self.objects:
            raise ValueError(f"Objeto '{name}' ya existe")
        
        if isinstance(color, str):
            color = self._parse_color(color)
        elif color is None:
            color = self.default_properties['color']
        
        obj = DrawingObject(
            name=name,
            type=ObjectType.CIRCLE,
            original_frame=frame,
            coordinates={'center': center, 'radius': radius},
            properties={
                'color': color,
                'thickness': -1 if filled else (thickness or self.default_properties['thickness']),
                'filled': filled,
                **kwargs
            },
            created_at=0.0
        )
        
        self.objects[name] = obj
        print(f"[OverlayManager] ✓ Círculo '{name}' agregado en marco '{frame}'")
    
    def add_ellipse(self, frame: str, center: Tuple[float, float], axes: Tuple[float, float],
                    angle: float, name: str, color: Union[str, Tuple[int, int, int]] = None,
                    thickness: int = None, **kwargs) -> None:
        """Agregar elipse"""
        if name in self.objects:
            raise ValueError(f"Objeto '{name}' ya existe")
        
        if isinstance(color, str):
            color = self._parse_color(color)
        elif color is None:
            color = self.default_properties['color']
        
        obj = DrawingObject(
            name=name,
            type=ObjectType.ELLIPSE,
            original_frame=frame,
            coordinates={'center': center, 'axes': axes, 'angle': angle},
            properties={
                'color': color,
                'thickness': thickness or self.default_properties['thickness'],
                **kwargs
            },
            created_at=0.0
        )
        
        self.objects[name] = obj
        print(f"[OverlayManager] ✓ Elipse '{name}' agregada en marco '{frame}'")
    
    def add_segment(self, frame: str, start: Tuple[float, float], end: Tuple[float, float],
                    name: str, color: Union[str, Tuple[int, int, int]] = None,
                    thickness: int = None, **kwargs) -> None:
        """Agregar segmento (línea con puntos extremos)"""
        if name in self.objects:
            raise ValueError(f"Objeto '{name}' ya existe")
        
        if isinstance(color, str):
            color = self._parse_color(color)
        elif color is None:
            color = self.default_properties['color']
        
        obj = DrawingObject(
            name=name,
            type=ObjectType.SEGMENT,
            original_frame=frame,
            coordinates={'start': start, 'end': end},
            properties={
                'color': color,
                'thickness': thickness or self.default_properties['thickness'],
                **kwargs
            },
            created_at=0.0
        )
        
        self.objects[name] = obj
        print(f"[OverlayManager] ✓ Segmento '{name}' agregado en marco '{frame}'")
    
    def add_text(self, frame: str, position: Tuple[float, float], text: str,
                 name: str, color: Union[str, Tuple[int, int, int]] = None,
                 font_scale: float = 1.0, thickness: int = None, **kwargs) -> None:
        """Agregar texto"""
        if name in self.objects:
            raise ValueError(f"Objeto '{name}' ya existe")
        
        if isinstance(color, str):
            color = self._parse_color(color)
        elif color is None:
            color = self.default_properties['color']
        
        obj = DrawingObject(
            name=name,
            type=ObjectType.TEXT,
            original_frame=frame,
            coordinates={'position': position, 'text': text},
            properties={
                'color': color,
                'font_scale': font_scale,
                'thickness': thickness or self.default_properties['thickness'],
                **kwargs
            },
            created_at=0.0
        )
        
        self.objects[name] = obj
        print(f"[OverlayManager] ✓ Texto '{name}' agregado en marco '{frame}'")
    
    def add_background(self, name: str, image_path: str, adjust_container: bool = True) -> None:
        """Agregar imagen de fondo desde archivo"""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Imagen no encontrada: {image_path}")
        
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"No se pudo cargar la imagen: {image_path}")
        
        self.backgrounds[name] = image
        print(f"[OverlayManager] ✓ Fondo '{name}' agregado: {image.shape}")
    
    def set_background(self, name: str, image: np.ndarray) -> None:
        """Establecer imagen de fondo desde array numpy"""
        if image is None:
            raise ValueError("Imagen no puede ser None")
        
        self.backgrounds[name] = image.copy()
        print(f"[OverlayManager] ✓ Fondo '{name}' establecido: {image.shape}")
    
    # ============================================================
    # CONSULTA DE OBJETOS
    # ============================================================
    
    def get_object(self, target_frame: str, name: str) -> Dict[str, Any]:
        """
        Obtener objeto transformado a un marco específico.
        
        Args:
            target_frame: Marco destino para las coordenadas
            name: Nombre del objeto
            
        Returns:
            Diccionario con el objeto transformado
        """
        if name not in self.objects:
            raise ValueError(f"Objeto '{name}' no existe")
        
        obj = self.objects[name]
        
        # Transformar coordenadas al marco destino
        transformed_coords = self._transform_coordinates(
            obj.coordinates, obj.original_frame, target_frame
        )
        
        return {
            'name': obj.name,
            'type': obj.type.value,
            'original_frame': obj.original_frame,
            'target_frame': target_frame,
            'coordinates': transformed_coords,
            'properties': obj.properties.copy()
        }
    
    def get_coordinates(self, target_frame: str, name: str, point: str = None) -> Any:
        """
        Obtener coordenadas específicas de un objeto.
        
        Args:
            target_frame: Marco destino
            name: Nombre del objeto
            point: Punto específico ('start', 'end', 'center', etc.)
            
        Returns:
            Coordenadas del punto o todo el diccionario de coordenadas
        """
        obj_data = self.get_object(target_frame, name)
        
        if point is None:
            return obj_data['coordinates']
        
        if point not in obj_data['coordinates']:
            raise ValueError(f"Punto '{point}' no existe en objeto '{name}'")
        
        return obj_data['coordinates'][point]
    
    def get_properties(self, name: str) -> Dict[str, Any]:
        """Obtener propiedades de un objeto"""
        if name not in self.objects:
            raise ValueError(f"Objeto '{name}' no existe")
        
        return self.objects[name].properties.copy()
    
    def get_object_original_frame(self, name: str) -> str:
        """Obtener marco original de un objeto"""
        if name not in self.objects:
            raise ValueError(f"Objeto '{name}' no existe")
        
        return self.objects[name].original_frame
    
    def list_objects(self) -> List[str]:
        """Listar todos los objetos"""
        return list(self.objects.keys())
    
    def list_objects_by_original_frame(self, frame: str) -> List[str]:
        """Listar objetos por marco original"""
        return [name for name, obj in self.objects.items() if obj.original_frame == frame]
    
    # ============================================================
    # GESTIÓN DE RENDERLISTS
    # ============================================================
    
    def create_renderlist(self, *object_names: str, name: str = None) -> str:
        """
        Crear lista de renderizado.
        
        Args:
            *object_names: Nombres de objetos a incluir
            name: Nombre de la renderlist (opcional)
            
        Returns:
            Nombre de la renderlist creada
        """
        if not object_names:
            raise ValueError("Debe especificar al menos un objeto")
        
        # Validar que todos los objetos existen
        for obj_name in object_names:
            if obj_name not in self.objects:
                raise ValueError(f"Objeto '{obj_name}' no existe")
        
        # Generar nombre automático si no se especifica
        if name is None:
            name = f"renderlist_{len(self.renderlists)}"
        
        self.renderlists[name] = list(object_names)
        print(f"[OverlayManager] ✓ Renderlist '{name}' creada con {len(object_names)} objetos")
        
        return name
    
    def get_renderlist(self, name: str) -> List[str]:
        """Obtener objetos de una renderlist"""
        if name not in self.renderlists:
            raise ValueError(f"Renderlist '{name}' no existe")
        
        return self.renderlists[name].copy()
    
    def list_renderlists(self) -> List[str]:
        """Listar todas las renderlists"""
        return list(self.renderlists.keys())
    
    # ============================================================
    # RENDERIZADO
    # ============================================================
    
    def render(self, background_image: np.ndarray, renderlist: Union[str, List[str]] = None,
               show_frames: List[str] = None, view_time: int = 5000) -> Tuple[np.ndarray, int]:
        """
        Renderizar overlays sobre imagen de fondo.
        
        Args:
            background_image: Imagen de fondo
            renderlist: Lista de objetos a renderizar (str o List[str])
            show_frames: Marcos a mostrar (opcional)
            view_time: Tiempo de visualización en ms
            
        Returns:
            Tupla (imagen_renderizada, view_time)
        """
        # Crear copia de la imagen de fondo
        result = background_image.copy()
        
        # Determinar qué objetos renderizar
        if renderlist is None:
            # Renderizar todos los objetos
            objects_to_render = list(self.objects.keys())
        elif isinstance(renderlist, str):
            # Usar renderlist específica
            objects_to_render = self.get_renderlist(renderlist)
        else:
            # Lista directa de objetos
            objects_to_render = renderlist
        
        # Renderizar cada objeto
        for obj_name in objects_to_render:
            if obj_name not in self.objects:
                print(f"[OverlayManager] ⚠️ Objeto '{obj_name}' no existe, omitiendo...")
                continue
            
            obj = self.objects[obj_name]
            
            # Transformar al marco world para renderizado
            transformed_coords = self._transform_coordinates(
                obj.coordinates, obj.original_frame, "world"
            )
            
            # Dibujar según tipo
            self._draw_object(result, obj.type, transformed_coords, obj.properties)
        
        print(f"[OverlayManager] ✓ Renderizado completado: {len(objects_to_render)} objetos, view_time={view_time}ms")
        
        return result, view_time
    
    def _draw_object(self, image: np.ndarray, obj_type: ObjectType, 
                    coordinates: Dict[str, Any], properties: Dict[str, Any]) -> None:
        """Dibujar objeto específico en la imagen"""
        
        if obj_type == ObjectType.LINE:
            start = tuple(map(int, coordinates['start']))
            end = tuple(map(int, coordinates['end']))
            cv2.line(image, start, end, properties['color'], properties['thickness'])
        
        elif obj_type == ObjectType.CIRCLE:
            center = tuple(map(int, coordinates['center']))
            radius = int(coordinates['radius'])
            cv2.circle(image, center, radius, properties['color'], properties['thickness'])
        
        elif obj_type == ObjectType.ELLIPSE:
            center = tuple(map(int, coordinates['center']))
            axes = tuple(map(int, coordinates['axes']))
            angle = int(coordinates['angle'])
            cv2.ellipse(image, center, axes, angle, 0, 360, properties['color'], properties['thickness'])
        
        elif obj_type == ObjectType.SEGMENT:
            start = tuple(map(int, coordinates['start']))
            end = tuple(map(int, coordinates['end']))
            cv2.line(image, start, end, properties['color'], properties['thickness'])
        
        elif obj_type == ObjectType.TEXT:
            position = tuple(map(int, coordinates['position']))
            text = coordinates['text']
            cv2.putText(image, text, position, cv2.FONT_HERSHEY_SIMPLEX, 
                       properties['font_scale'], properties['color'], properties['thickness'])
        
        elif obj_type == ObjectType.POLYGON:
            points = np.array(coordinates['points'], dtype=np.int32)
            cv2.polylines(image, [points], True, properties['color'], properties['thickness'])
    
    # ============================================================
    # UTILIDADES
    # ============================================================
    
    def _parse_color(self, color_str: str) -> Tuple[int, int, int]:
        """Convertir string de color a BGR"""
        color_map = {
            'red': (0, 0, 255),
            'green': (0, 255, 0),
            'blue': (255, 0, 0),
            'yellow': (0, 255, 255),
            'cyan': (255, 255, 0),
            'magenta': (255, 0, 255),
            'white': (255, 255, 255),
            'black': (0, 0, 0)
        }
        
        if color_str.lower() in color_map:
            return color_map[color_str.lower()]
        else:
            print(f"[OverlayManager] ⚠️ Color '{color_str}' no reconocido, usando verde")
            return (0, 255, 0)
    
    def save_config(self, filepath: str) -> None:
        """Guardar configuración a archivo JSON"""
        config = {
            'frames': {name: {
                'offset_x': frame.offset_x,
                'offset_y': frame.offset_y,
                'rotation': frame.rotation,
                'px_per_mm': frame.px_per_mm,
                'parent_frame': frame.parent_frame,
                'is_temporary': frame.is_temporary
            } for name, frame in self.frames.items()},
            'objects': {name: {
                'type': obj.type.value,
                'original_frame': obj.original_frame,
                'coordinates': obj.coordinates,
                'properties': obj.properties
            } for name, obj in self.objects.items()},
            'renderlists': self.renderlists
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"[OverlayManager] ✓ Configuración guardada en {filepath}")
    
    def save_persistent_config(self) -> None:
        """Guardar configuración persistente (solo marcos no temporales)"""
        persistent_frames = {name: frame for name, frame in self.frames.items() 
                           if not frame.is_temporary}
        
        config = {
            'frames': {name: {
                'offset_x': frame.offset_x,
                'offset_y': frame.offset_y,
                'rotation': frame.rotation,
                'px_per_mm': frame.px_per_mm,
                'parent_frame': frame.parent_frame,
                'is_temporary': False
            } for name, frame in persistent_frames.items()},
            'metadata': {
                'last_updated': 0.0,  # TODO: usar timestamp real
                'version': '1.0'
            }
        }
        
        with open('overlay_frames.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"[OverlayManager] ✓ Configuración persistente guardada")
    
    def load_config(self, filepath: str) -> None:
        """Cargar configuración desde archivo JSON"""
        if not os.path.exists(filepath):
            print(f"[OverlayManager] ⚠️ Archivo {filepath} no existe")
            return
        
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Cargar marcos
        for name, frame_data in config.get('frames', {}).items():
            self.define_frame(
                name, 
                (frame_data['offset_x'], frame_data['offset_y']),
                frame_data['rotation'],
                frame_data.get('px_per_mm', 1.0),
                frame_data.get('parent_frame', 'Base'),
                frame_data.get('is_temporary', False)
            )
        
        # Cargar objetos
        for name, obj_data in config.get('objects', {}).items():
            # Recrear objeto (simplificado)
            obj = DrawingObject(
                name=name,
                type=ObjectType(obj_data['type']),
                original_frame=obj_data['original_frame'],
                coordinates=obj_data['coordinates'],
                properties=obj_data['properties'],
                created_at=0.0
            )
            self.objects[name] = obj
        
        # Cargar renderlists
        self.renderlists = config.get('renderlists', {})
        
        print(f"[OverlayManager] ✓ Configuración cargada desde {filepath}")
    
    def load_persistent_config(self) -> None:
        """Cargar configuración persistente al inicializar"""
        if os.path.exists('overlay_frames.json'):
            self.load_config('overlay_frames.json')
            print(f"[OverlayManager] ✓ Configuración persistente cargada desde overlay_frames.json")
        else:
            print(f"[OverlayManager] ⚠️ No hay configuración persistente, usando valores por defecto")
        
        # Asegurar que base_frame y tool_frame existan con valores por defecto si no se cargaron
        if 'base_frame' not in self.frames:
            self.define_frame("base_frame", offset=(0, 0), rotation=0.0, px_per_mm=1.0)
            print(f"[OverlayManager] ✓ Marco base_frame inicializado con valores por defecto")
        
        if 'tool_frame' not in self.frames:
            self.define_frame("tool_frame", offset=(0, 0), rotation=0.0, px_per_mm=1.0)
            print(f"[OverlayManager] ✓ Marco tool_frame inicializado con valores por defecto")
        
        if 'junta_frame' not in self.frames:
            self.define_frame("junta_frame", offset=(0, 0), rotation=0.0, px_per_mm=1.0)
            print(f"[OverlayManager] ✓ Marco junta_frame inicializado con valores por defecto")
    
    def detect_arucos_in_image(self, image: np.ndarray, frame_aruco_id: int, tool_aruco_id: int) -> Dict[str, Any]:
        """
        Detectar ArUcos en imagen usando OpenCV directo.
        
        Args:
            image: Imagen en escala de grises
            frame_aruco_id: ID del ArUco Frame
            tool_aruco_id: ID del ArUco Tool
            
        Returns:
            Diccionario con información de detección
        """
        try:
            print(f"[OverlayManager] Detectando ArUcos en imagen {image.shape}")
            print(f"[OverlayManager] Buscando Frame ID: {frame_aruco_id}, Tool ID: {tool_aruco_id}")
            
            # Configurar detector ArUco
            aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_50)
            parameters = cv2.aruco.DetectorParameters()
            detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
            
            # Detectar marcadores
            corners, ids, rejected = detector.detectMarkers(image)
            
            print(f"[OverlayManager] Resultado detección:")
            print(f"  - corners: {len(corners) if corners is not None else 0}")
            print(f"  - ids: {ids}")
            print(f"  - rejected: {len(rejected) if rejected is not None else 0}")
            
            detected_arucos = {}
            detected_ids = []
            
            if ids is not None and len(ids) > 0:
                for i, aruco_id in enumerate(ids.flatten()):
                    detected_ids.append(int(aruco_id))
                    
                    # Obtener esquinas del ArUco
                    corner = corners[i][0]
                    
                    # Calcular centro
                    center_x = np.mean(corner[:, 0])
                    center_y = np.mean(corner[:, 1])
                    
                    # Calcular ángulo de rotación
                    dx = corner[1][0] - corner[0][0]
                    dy = corner[1][1] - corner[0][1]
                    angle_rad = np.arctan2(dy, dx)
                    
                    # Calcular px_per_mm (asumiendo tamaño conocido)
                    # TODO: usar tamaño real del marcador
                    marker_size_mm = 42.0  # Tamaño por defecto
                    marker_size_px = np.linalg.norm(corner[1] - corner[0])
                    px_per_mm = marker_size_px / marker_size_mm
                    
                    detected_arucos[int(aruco_id)] = {
                        'center': (float(center_x), float(center_y)),
                        'angle_rad': float(angle_rad),
                        'corners': corner.tolist(),
                        'px_per_mm': float(px_per_mm)
                    }
            
            # Verificar si se detectaron los ArUcos esperados
            frame_detected = frame_aruco_id in detected_arucos
            tool_detected = tool_aruco_id in detected_arucos
            
            return {
                'detected_arucos': detected_arucos,
                'detected_ids': detected_ids,
                'frame_detected': frame_detected,
                'tool_detected': tool_detected,
                'frame_aruco_id': frame_aruco_id,
                'tool_aruco_id': tool_aruco_id
            }
            
        except Exception as e:
            print(f"[OverlayManager] ❌ Error detectando ArUcos: {e}")
            return {
                'detected_arucos': {},
                'detected_ids': [],
                'frame_detected': False,
                'tool_detected': False,
                'error': str(e)
            }
    
    def create_temp_frames_from_arucos(self, detection_result: Dict[str, Any]) -> None:
        """
        Crear marcos temporales basados en detección de ArUcos.
        
        Args:
            detection_result: Resultado de detect_arucos_in_image()
        """
        detected_arucos = detection_result.get('detected_arucos', {})
        frame_aruco_id = detection_result.get('frame_aruco_id', 0)
        tool_aruco_id = detection_result.get('tool_aruco_id', 0)
        
        # Crear/actualizar frame temporal del Frame ArUco
        if frame_aruco_id in detected_arucos:
            frame_data = detected_arucos[frame_aruco_id]
            self.define_frame(
                "base_frame_temp",
                offset=frame_data['center'],
                rotation=frame_data['angle_rad'],
                px_per_mm=frame_data['px_per_mm'],
                is_temporary=True
            )
            print(f"[OverlayManager] ✓ Marco temporal 'base_frame_temp' creado desde ArUco {frame_aruco_id}")
        
        # Crear/actualizar frame temporal del Tool ArUco
        if tool_aruco_id in detected_arucos:
            tool_data = detected_arucos[tool_aruco_id]
            self.define_frame(
                "tool_frame_temp",
                offset=tool_data['center'],
                rotation=tool_data['angle_rad'],
                px_per_mm=tool_data['px_per_mm'],
                is_temporary=True
            )
            print(f"[OverlayManager] ✓ Marco temporal 'tool_frame_temp' creado desde ArUco {tool_aruco_id}")
    
    def create_aruco_overlay_objects(self, detection_result: Dict[str, Any]) -> None:
        """
        Crear objetos de overlay para ArUcos detectados.
        
        Args:
            detection_result: Resultado de detect_arucos_in_image()
        """
        detected_arucos = detection_result.get('detected_arucos', {})
        frame_aruco_id = detection_result.get('frame_aruco_id', 0)
        tool_aruco_id = detection_result.get('tool_aruco_id', 0)
        
        # Limpiar objetos de ArUco existentes
        aruco_objects = [name for name, obj in self.objects.items() 
                        if obj.name.startswith('aruco_')]
        for obj_name in aruco_objects:
            del self.objects[obj_name]
        
        # Crear objetos para cada ArUco detectado
        for aruco_id, aruco_data in detected_arucos.items():
            center = aruco_data['center']
            angle_rad = aruco_data['angle_rad']
            corners = aruco_data['corners']
            
            # Determinar color según tipo
            if aruco_id == frame_aruco_id:
                color = (0, 255, 255)  # Amarillo para Frame
                frame_name = "base_frame_temp"
            elif aruco_id == tool_aruco_id:
                color = (255, 0, 0)  # Azul para Tool
                frame_name = "tool_frame_temp"
            else:
                color = (255, 255, 0)  # Cian para otros
                frame_name = "world"  # Usar marco world para ArUcos no esperados
            
            # Dibujar contorno del ArUco
            self.add_polygon(
                frame_name,
                points=corners,
                name=f"aruco_contour_{aruco_id}",
                color=color,
                thickness=2
            )
            
            # Dibujar ejes (líneas infinitas de borde a borde)
            # Eje X
            axis_length = 1000  # Largo para cubrir toda la imagen
            x_end1 = (
                center[0] + axis_length * np.cos(angle_rad),
                center[1] + axis_length * np.sin(angle_rad)
            )
            x_end2 = (
                center[0] - axis_length * np.cos(angle_rad),
                center[1] - axis_length * np.sin(angle_rad)
            )
            
            # Eje Y
            y_angle_rad = angle_rad + np.pi / 2
            y_end1 = (
                center[0] + axis_length * np.cos(y_angle_rad),
                center[1] + axis_length * np.sin(y_angle_rad)
            )
            y_end2 = (
                center[0] - axis_length * np.cos(y_angle_rad),
                center[1] - axis_length * np.sin(y_angle_rad)
            )
            
            # Agregar líneas de ejes
            self.add_line(
                frame_name,
                start=x_end2,
                end=x_end1,
                name=f"aruco_x_axis_{aruco_id}",
                color=color,
                thickness=2
            )
            
            self.add_line(
                frame_name,
                start=y_end2,
                end=y_end1,
                name=f"aruco_y_axis_{aruco_id}",
                color=color,
                thickness=2
            )
            
            # Agregar centro
            self.add_circle(
                frame_name,
                center=(0, 0),  # Centro relativo al marco
                radius=5,
                name=f"aruco_center_{aruco_id}",
                color=color,
                filled=True
            )
            
            print(f"[OverlayManager] ✓ Objetos de overlay creados para ArUco {aruco_id}")
    
    def add_polygon(self, frame: str, points: List[Tuple[float, float]], 
                   name: str, color: Union[str, Tuple[int, int, int]] = None,
                   thickness: int = None, **kwargs) -> None:
        """Agregar polígono (contorno)"""
        if name in self.objects:
            raise ValueError(f"Objeto '{name}' ya existe")
        
        if isinstance(color, str):
            color = self._parse_color(color)
        elif color is None:
            color = self.default_properties['color']
        
        obj = DrawingObject(
            name=name,
            type=ObjectType.POLYGON,
            original_frame=frame,
            coordinates={'points': points},
            properties={
                'color': color,
                'thickness': thickness or self.default_properties['thickness'],
                **kwargs
            },
            created_at=0.0
        )
        
        self.objects[name] = obj
        print(f"[OverlayManager] ✓ Polígono '{name}' agregado en marco '{frame}'")


# ============================================================
# FUNCIONES DE CONVENIENCIA
# ============================================================

def create_default_overlay_manager() -> OverlayManager:
    """Crear OverlayManager con configuración por defecto"""
    manager = OverlayManager()
    
    # Definir marcos comunes
    manager.define_frame("Frame", offset=(0, 0), rotation=0.0)
    manager.define_frame("Tool", offset=(0, 0), rotation=0.0)
    
    return manager


# ============================================================
# EJEMPLO DE USO
# ============================================================

if __name__ == "__main__":
    # Ejemplo de uso básico
    print("=== Ejemplo de OverlayManager ===")
    
    # Crear gestor
    overlay = OverlayManager()
    
    # Definir marcos
    overlay.define_frame("Frame", offset=(100, 50), rotation=0.5)
    overlay.define_frame("Tool", offset=(200, 150), rotation=-0.3)
    
    # Agregar objetos
    overlay.add_line("Tool", start=(10, 20), end=(30, 40), color="red", name="linea_tool_1")
    overlay.add_circle("Frame", center=(15, 25), radius=5, color="blue", name="circulo_frame_1")
    
    # Crear renderlist
    renderlist = overlay.create_renderlist("linea_tool_1", "circulo_frame_1")
    
    # Consultar coordenadas
    coords = overlay.get_object("world", name="linea_tool_1")
    print(f"Coordenadas en Base: {coords}")
    
    # Actualizar marco
    overlay.update_frame("world", offset=(200, 250), rotation=0.4)
    
    # Consultar coordenadas después del cambio
    coords2 = overlay.get_object("world", name="linea_tool_1")
    print(f"Coordenadas después del cambio: {coords2}")
    
    print("=== Ejemplo completado ===")
