"""
OverlayManager - Librería Genérica de Overlays
==============================================

Librería genérica y reutilizable para gestión de overlays con transformaciones 
dinámicas entre múltiples sistemas de coordenadas.

IMPORTANTE: Esta librería es GENÉRICA y NO debe ser modificada con:
- Elementos hardcodeados específicos del dominio
- Funciones específicas del proyecto
- Marcos de referencia predefinidos
- Configuraciones específicas del negocio

Características:
- Marcos de coordenadas dinámicos y genéricos
- Transformaciones bidireccionales automáticas (mm ↔ píxeles)
- Objetos nombrados con consulta de coordenadas
- Actualización dinámica de marcos
- Renderizado con control granular
- Soporte para imágenes de fondo
- Parámetro viewTime para control de visualización
- Soporte para coordenadas en mm y píxeles
- Conversión automática de unidades

Uso:
- Solo define el marco "world" por defecto
- Los marcos específicos deben definirse externamente
- Los scripts del dominio deben usar frames_manager.py
- Completamente reutilizable para cualquier proyecto

Autor: Sistema COMAU-VISION
Versión: 1.1 (Soporte para px_per_mm no uniforme)
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
    px_per_mm: Union[float, Tuple[float, float]]  # Relación píxeles por milímetro (puede ser no uniforme)
    parent_frame: Optional[str] = None  # None para world


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
    Gestor genérico del sistema de overlays.
    
    Librería genérica y reutilizable que maneja:
    - Marcos de coordenadas dinámicos
    - Objetos de dibujo con transformaciones automáticas
    - Conversión automática mm ↔ píxeles
    - Renderizado con control granular
    - Soporte para coordenadas en mm y píxeles
    
    IMPORTANTE: Esta clase es GENÉRICA y NO debe ser modificada con:
    - Marcos específicos del dominio
    - Funciones específicas del proyecto
    - Configuraciones hardcodeadas
    
    Los marcos específicos deben definirse en scripts externos
    usando frames_manager.py o similar.
    """
    
    def __init__(self):
        """
        Inicializar el gestor genérico de overlays.
        
        Solo define el marco "world" genérico. Los marcos específicos
        del dominio deben definirse externamente usando frames_manager.py
        o scripts similares.
        """
        self.frames: Dict[str, CoordinateFrame] = {}
        self.objects: Dict[str, DrawingObject] = {}
        self.renderlists: Dict[str, List[str]] = {}
        self.backgrounds: Dict[str, np.ndarray] = {}
        
        # Definir marco world por defecto (único marco genérico)
        self.define_frame("world", offset=(0, 0), rotation=0.0, px_per_mm=1.0)
        
        print(f"[OverlayManager] ✓ Marco genérico 'world' inicializado")
        
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
                    rotation: float, px_per_mm: Union[float, Tuple[float, float]] = 1.0, 
                    parent_frame: str = "world") -> None:
        """
        Definir un nuevo marco de coordenadas.
        
        Args:
            name: Nombre del marco
            offset: Desplazamiento (x, y) respecto al marco padre
            rotation: Rotación en radianes
            px_per_mm: Relación píxeles por milímetro (uniforme o no)
            parent_frame: Marco padre (default: "world")
        """
        if name in self.frames:
            print(f"[OverlayManager] ⚠️ Marco '{name}' ya existe, actualizando...")
        
        self.frames[name] = CoordinateFrame(
            name=name,
            offset_x=offset[0],
            offset_y=offset[1],
            rotation=rotation,
            px_per_mm=px_per_mm,
            parent_frame=parent_frame
        )
        
        print(f"[OverlayManager] ✓ Marco '{name}' definido: offset={offset}, rotation={rotation:.3f}rad, px_per_mm={px_per_mm}")
    
    def update_frame(self, name: str, offset: Optional[Tuple[float, float]] = None,
                    rotation: Optional[float] = None, px_per_mm: Optional[Union[float, Tuple[float, float]]] = None) -> None:
        """
        Actualizar un marco de coordenadas existente.
        
        Args:
            name: Nombre del marco a actualizar
            offset: Nuevo desplazamiento (opcional)
            rotation: Nueva rotación en radianes (opcional)
            px_per_mm: Nueva relación píxeles por milímetro (opcional)
        """
        if name not in self.frames:
            raise ValueError(f"Marco '{name}' no existe")
        
        frame = self.frames[name]
        
        if offset is not None:
            frame.offset_x, frame.offset_y = offset
            print(f"[OverlayManager] ✓ Marco '{name}' actualizado: offset=({offset[0]:.1f}, {offset[1]:.1f})")
        
        if rotation is not None:
            frame.rotation = rotation
            print(f"[OverlayManager] ✓ Marco '{name}' actualizado: rotation={rotation:.3f}rad")
        
        if px_per_mm is not None:
            frame.px_per_mm = px_per_mm 
            # Imprimir sin formato específico para soportar tuplas
            print(f"[OverlayManager] ✓ Marco '{name}' actualizado: px_per_mm={px_per_mm}")
    
    def get_frame(self, name: str) -> CoordinateFrame:
        """Obtener información de un marco"""
        if name not in self.frames:
            raise ValueError(f"Marco '{name}' no existe")
        return self.frames[name]
    
    def list_frames(self) -> List[str]:
        """Listar todos los marcos definidos"""
        return list(self.frames.keys())

    def _get_px_per_mm_vec(self, frame_obj: CoordinateFrame) -> np.ndarray:
        """Convierte px_per_mm a un vector numpy [x, y]"""
        if isinstance(frame_obj.px_per_mm, (list, tuple)):
            return np.array(frame_obj.px_per_mm, dtype=float)
        else:
            return np.array([frame_obj.px_per_mm, frame_obj.px_per_mm], dtype=float)

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
        
        # PASO 1: Convertir de mm a píxeles.
        # Si las unidades originales eran 'px', el objeto se guardó en "pseudo-mm"
        # (dividiendo por px_per_mm). Este paso revierte esa operación,
        # devolviendo el punto a su valor original en píxeles relativos al frame.
        point_px = point
        if from_frame_obj.name != 'world':
            px_per_mm_vec = self._get_px_per_mm_vec(from_frame_obj)
            point_px = point * px_per_mm_vec
        
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
            to_px_per_mm_vec = self._get_px_per_mm_vec(to_frame_obj)
            final_x = final_x / to_px_per_mm_vec[0]
            final_y = final_y / to_px_per_mm_vec[1]
        
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
        
        obj_type = coordinates.get('_obj_type_for_transform', None)
        transformed = {}

        if obj_type == ObjectType.ELLIPSE:
            # Tratamiento especial para elipses
            transformed['center'] = self._transform_point(coordinates['center'], from_frame, to_frame)
            
            # Los ejes (tamaño) no se rotan ni se trasladan, solo se escalan si es necesario.
            # Como aquí trabajamos con píxeles, se mantienen igual.
            transformed['axes'] = coordinates['axes']
            
            # El ángulo se suma al del frame.
            from_frame_obj = self.frames[from_frame]
            transformed['angle'] = coordinates['angle'] + np.degrees(from_frame_obj.rotation)
        else:
            # Lógica general para otros objetos
            for key, value in coordinates.items():
                if key == '_obj_type_for_transform': continue

                if isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value):
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
                 thickness: int = None, units: str = "mm", **kwargs) -> None:
        """
        Agregar línea
        
        Args:
            frame: Marco de referencia
            start: Punto inicio
            end: Punto fin
            name: Nombre único
            color: Color del objeto
            thickness: Grosor de línea
            units: Unidades de las coordenadas ("mm" por defecto o "px")
        """
        if name in self.objects:
            raise ValueError(f"Objeto '{name}' ya existe")
        
        # Convertir coordenadas si vienen en píxeles
        if units == "px":
            frame_obj = self.frames[frame]
            px_per_mm_vec = self._get_px_per_mm_vec(frame_obj)
            start = (start[0] / px_per_mm_vec[0], start[1] / px_per_mm_vec[1])
            end = (end[0] / px_per_mm_vec[0], end[1] / px_per_mm_vec[1])
        
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
            created_at=time.time()
        )
        
        self.objects[name] = obj
        print(f"[OverlayManager] ✓ Línea '{name}' agregada en marco '{frame}' ({units})")
    
    def add_circle(self, frame: str, center: Tuple[float, float], radius: float,
                   name: str, color: Union[str, Tuple[int, int, int]] = None,
                   thickness: int = None, filled: bool = False, units: str = "mm", **kwargs) -> None:
        """
        Agregar círculo
        
        Args:
            frame: Marco de referencia
            center: Centro del círculo
            radius: Radio del círculo
            name: Nombre único
            color: Color del objeto
            thickness: Grosor de línea
            filled: Si está relleno
            units: Unidades de las coordenadas ("mm" o "px")
        """
        if name in self.objects:
            raise ValueError(f"Objeto '{name}' ya existe")
        
        # Convertir coordenadas si vienen en píxeles
        if units == "px":
            frame_obj = self.frames[frame]
            px_per_mm_vec = self._get_px_per_mm_vec(frame_obj)
            center = (center[0] / px_per_mm_vec[0], center[1] / px_per_mm_vec[1])
            radius = radius / px_per_mm_vec[0] # El radio es uniforme
        
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
            created_at=time.time()
        )
        
        self.objects[name] = obj
        print(f"[OverlayManager] ✓ Círculo '{name}' agregado en marco '{frame}' ({units})")
    
    def add_ellipse(self, frame: str, center: Tuple[float, float], axes: Tuple[float, float],
                    angle: float, name: str, color: Union[str, Tuple[int, int, int]] = None,
                    thickness: int = None, units: str = "mm", **kwargs) -> None:
        """
        Agregar elipse
        
        Args:
            frame: Marco de referencia
            center: Centro de la elipse
            axes: Ejes mayor y menor
            angle: Ángulo de rotación
            name: Nombre único
            color: Color del objeto
            thickness: Grosor de línea
            units: Unidades de las coordenadas ("mm" o "px")
        """
        if name in self.objects:
            raise ValueError(f"Objeto '{name}' ya existe")
        
        # Convertir coordenadas si vienen en píxeles
        if units == "px":
            # Para que la transformación funcione, debemos "simular" que están en mm
            # dividiendo por el px_per_mm. El motor de renderizado lo revertirá.
            frame_obj = self.frames[frame]
            px_per_mm_vec = self._get_px_per_mm_vec(frame_obj)
            center = (center[0] / px_per_mm_vec[0], center[1] / px_per_mm_vec[1])
            axes = (axes[0] / abs(px_per_mm_vec[0]), axes[1] / abs(px_per_mm_vec[1]))
        
        if isinstance(color, str):
            color = self._parse_color(color)
        elif color is None:
            color = self.default_properties['color']
        
        obj = DrawingObject(
            name=name,
            type=ObjectType.ELLIPSE,
            original_frame=frame,
            coordinates={'center': center, 'axes': axes, 'angle': angle, '_obj_type_for_transform': ObjectType.ELLIPSE},
            properties={
                'color': color,
                'thickness': thickness or self.default_properties['thickness'],
                **kwargs
            },
            created_at=time.time()
        )
        
        self.objects[name] = obj
        print(f"[OverlayManager] ✓ Elipse '{name}' agregada en marco '{frame}' ({units})")
    
    def add_segment(self, frame: str, start: Tuple[float, float], end: Tuple[float, float],
                    name: str, color: Union[str, Tuple[int, int, int]] = None,
                    thickness: int = None, units: str = "mm", **kwargs) -> None:
        """
        Agregar segmento (línea con puntos extremos)
        
        Args:
            frame: Marco de referencia
            start: Punto inicio
            end: Punto fin
            name: Nombre único
            color: Color del objeto
            thickness: Grosor de línea
            units: Unidades de las coordenadas ("mm" o "px")
        """
        if name in self.objects:
            raise ValueError(f"Objeto '{name}' ya existe")
        
        # Convertir coordenadas si vienen en píxeles
        if units == "px":
            frame_obj = self.frames[frame]
            px_per_mm_vec = self._get_px_per_mm_vec(frame_obj)
            start = (start[0] / px_per_mm_vec[0], start[1] / px_per_mm_vec[1])
            end = (end[0] / px_per_mm_vec[0], end[1] / px_per_mm_vec[1])
        
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
            created_at=time.time()
        )
        
        self.objects[name] = obj
        print(f"[OverlayManager] ✓ Segmento '{name}' agregado en marco '{frame}' ({units})")
    
    def add_text(self, frame: str, position: Tuple[float, float], text: str,
                 name: str, color: Union[str, Tuple[int, int, int]] = None,
                 font_scale: float = 1.0, thickness: int = None, units: str = "mm", **kwargs) -> None:
        """
        Agregar texto
        
        Args:
            frame: Marco de referencia
            position: Posición del texto
            text: Texto a mostrar
            name: Nombre único
            color: Color del texto
            font_scale: Escala de fuente
            thickness: Grosor de línea
            units: Unidades de las coordenadas ("mm" o "px")
        """
        if name in self.objects:
            raise ValueError(f"Objeto '{name}' ya existe")
        
        # Convertir coordenadas si vienen en píxeles
        if units == "px":
            frame_obj = self.frames[frame]
            px_per_mm_vec = self._get_px_per_mm_vec(frame_obj)
            position = (position[0] / px_per_mm_vec[0], position[1] / px_per_mm_vec[1])
        
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
            created_at=time.time()
        )
        
        self.objects[name] = obj
        print(f"[OverlayManager] ✓ Texto '{name}' agregado en marco '{frame}' ({units})")
    
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
                'parent_frame': frame.parent_frame
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
    
    def save_persistent_config(self, filepath: str = 'overlay_frames.json') -> None:
        """Guardar configuración persistente"""
        config = {
            'frames': {name: {
                'offset_x': frame.offset_x,
                'offset_y': frame.offset_y,
                'rotation': frame.rotation,
                'px_per_mm': frame.px_per_mm,
                'parent_frame': frame.parent_frame
            } for name, frame in self.frames.items()},
            'metadata': {
                'last_updated': time.time(),
                'version': '1.0'
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"[OverlayManager] ✓ Configuración persistente guardada en {filepath}")
    
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
                frame_data.get('parent_frame', 'world')
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
    
    def load_persistent_config(self, filepath: str = 'overlay_frames.json') -> None:
        """Cargar configuración persistente al inicializar"""
        if os.path.exists(filepath):
            self.load_config(filepath)
            print(f"[OverlayManager] ✓ Configuración persistente cargada desde {filepath}")
        else:
            print(f"[OverlayManager] ⚠️ No hay configuración persistente, usando valores por defecto")
        
        # La librería genérica no debe asumir marcos específicos del dominio
        # Los marcos específicos deben ser definidos por scripts externos
    
    def add_polygon(self, frame: str, points: List[Tuple[float, float]], 
                   name: str, color: Union[str, Tuple[int, int, int]] = None,
                   thickness: int = None, units: str = "mm", **kwargs) -> None:
        """
        Agregar polígono (contorno)
        
        Args:
            frame: Marco de referencia
            points: Lista de puntos del polígono
            name: Nombre único
            color: Color del objeto
            thickness: Grosor de línea
            units: Unidades de las coordenadas ("mm" o "px")
        """
        if name in self.objects:
            raise ValueError(f"Objeto '{name}' ya existe")
        
        # Convertir coordenadas si vienen en píxeles
        if units == "px":
            frame_obj = self.frames[frame]
            px_per_mm_vec = self._get_px_per_mm_vec(frame_obj)
            points = [(p[0] / px_per_mm_vec[0], p[1] / px_per_mm_vec[1]) for p in points]
        
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
            created_at=time.time()
        )
        
        self.objects[name] = obj
        print(f"[OverlayManager] ✓ Polígono '{name}' agregado en marco '{frame}' ({units})")


# ============================================================
# DOCUMENTACIÓN DE USO
# ============================================================

"""
DOCUMENTACIÓN DE USO - OverlayManager Genérico
==============================================

IMPORTANTE: Esta librería es GENÉRICA y NO debe ser modificada.

1. INICIALIZACIÓN:
   overlay = OverlayManager()  # Solo define marco "world"

2. MARCOS ESPECÍFICOS:
   # NO agregar marcos específicos aquí
   # Usar frames_manager.py para marcos del dominio
   from frames_manager import init_global_frames
   init_global_frames()

3. AGREGAR OBJETOS:
   # En milímetros (por defecto)
   overlay.add_line("base_frame", start=(10, 20), end=(30, 20), name="linea_mm")
   
   # En píxeles (cuando sea necesario)
   overlay.add_line("base_frame", start=(29.9, 59.8), end=(89.7, 59.8), name="linea_px", units="px")

4. RENDERIZADO:
   result_image, view_time = overlay.render(background_image)

5. ARQUITECTURA:
   - overlay_manager.py: Librería genérica (NO modificar)
   - frames_manager.py: Marcos específicos del dominio
   - Scripts del proyecto: Usar frames_manager.py

NO MODIFICAR ESTA LIBRERÍA CON:
- Marcos específicos del dominio
- Funciones específicas del proyecto
- Configuraciones hardcodeadas
- Elementos específicos del negocio
"""

# ============================================================
# FUNCIONES DE CONVENIENCIA
# ============================================================
import time
