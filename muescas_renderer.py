"""
Renderizador de Muescas
========================

Dibuja muescas (círculos de 4mm) sobre la imagen de la junta
usando el punto medio del segmento rojo como origen.
"""

import cv2
import numpy as np
from typing import Tuple, Optional

def dibujar_muescas(img: np.ndarray, 
                    cantidad_muescas: int,
                    muesca_x_mm: float,
                    muesca_y_mm: float,
                    punto_medio_px: Tuple[int, int],
                    mm_por_pixel: float,
                    vertical: bool = False,
                    diametro_muesca_mm: float = 4.0,
                    separacion_muescas_mm: float = 7.0) -> np.ndarray:
    """
    Dibuja muescas en la imagen usando el punto medio como origen
    
    Args:
        img: Imagen sobre la cual dibujar (puede ser grayscale o BGR)
        cantidad_muescas: Número de muescas a dibujar
        muesca_x_mm: Coordenada X de la primera muesca en mm
        muesca_y_mm: Coordenada Y de la primera muesca en mm
        punto_medio_px: Coordenadas del punto medio del segmento rojo (origen)
        mm_por_pixel: Factor de conversión
        diametro_muesca_mm: Diámetro de cada muesca en mm (default: 4mm)
        separacion_muescas_mm: Separación entre centros en mm (default: 7mm)
    
    Returns:
        Imagen con las muescas dibujadas
    """
    if cantidad_muescas <= 0:
        return img
    
    # La imagen siempre viene en COLOR (BGR) desde el servidor
    img_result = img.copy()
    
    # Calcular conversiones
    diametro_muesca_px = diametro_muesca_mm / mm_por_pixel
    radio_muesca_px = int(diametro_muesca_px / 2)
    separacion_muescas_px = separacion_muescas_mm / mm_por_pixel
    
    # Punto medio del segmento rojo (origen de coordenadas)
    origen_x, origen_y = punto_medio_px
    
    # Calcular posición de la primera muesca en píxeles
    # Coordenadas de la imagen: 
    #   - Hacia la derecha: X positivo
    #   - Hacia ARRIBA: Y negativo (porque en imágenes Y crece hacia abajo)
    primera_muesca_x_px = origen_x + (muesca_x_mm / mm_por_pixel)
    primera_muesca_y_px = origen_y - (muesca_y_mm / mm_por_pixel)  # Invertir Y
    
    orientacion = "VERTICAL" if vertical else "HORIZONTAL"
    print(f"[muescas] Dibujando {cantidad_muescas} muescas ({orientacion}):")
    print(f"[muescas]   Origen (punto medio segmento): ({origen_x}, {origen_y}) px")
    print(f"[muescas]   Primera muesca en: ({muesca_x_mm}, {muesca_y_mm}) mm")
    print(f"[muescas]   Primera muesca en: ({primera_muesca_x_px:.1f}, {primera_muesca_y_px:.1f}) px")
    print(f"[muescas]   Diámetro: {diametro_muesca_mm} mm ({diametro_muesca_px:.1f} px)")
    print(f"[muescas]   Separación: {separacion_muescas_mm} mm ({separacion_muescas_px:.1f} px)")
    
    # Dibujar cada muesca
    for i in range(cantidad_muescas):
        # Calcular centro de esta muesca según orientación
        if vertical:
            # Verticalmente hacia abajo
            centro_x = int(primera_muesca_x_px)
            centro_y = int(primera_muesca_y_px + (i * separacion_muescas_px))
        else:
            # Horizontalmente hacia la derecha
            centro_x = int(primera_muesca_x_px + (i * separacion_muescas_px))
            centro_y = int(primera_muesca_y_px)
        
        # Verificar que esté dentro de la imagen
        if (0 <= centro_x < img_result.shape[1] and 
            0 <= centro_y < img_result.shape[0]):
            
            # Dibujar círculo relleno en ROJO
            cv2.circle(img_result, (centro_x, centro_y), radio_muesca_px, (0, 0, 255), -1)
            
            print(f"[muescas]   Muesca {i+1}: ({centro_x}, {centro_y}) px")
        else:
            print(f"[muescas]   Muesca {i+1}: FUERA DE LÍMITES ({centro_x}, {centro_y}) px")
    
    return img_result


def calcular_punto_medio_segmento(analisis_data: dict) -> Optional[Tuple[int, int]]:
    """
    Extrae el punto medio del segmento rojo del análisis
    
    Args:
        analisis_data: Datos del análisis completo
    
    Returns:
        Tupla (x, y) del punto medio o None si no existe
    """
    if not analisis_data or not analisis_data.get('ok'):
        return None
    
    linea_ref = analisis_data.get('linea_referencia')
    if not linea_ref or not linea_ref.get('punto_medio_px'):
        return None
    
    punto_medio = linea_ref['punto_medio_px']
    
    # Puede venir como lista o tupla
    if isinstance(punto_medio, (list, tuple)) and len(punto_medio) == 2:
        return (int(punto_medio[0]), int(punto_medio[1]))
    
    return None

