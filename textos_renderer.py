"""
Renderizador de Textos
======================

Dibuja textos (ILLINOIS, Código, Lote) sobre la imagen de la junta
usando el punto medio del segmento rojo como origen.
"""

import cv2
import numpy as np
from typing import Tuple

def dibujar_texto_simple(img: np.ndarray,
                        texto: str,
                        x_mm: float,
                        y_mm: float,
                        punto_medio_px: Tuple[int, int],
                        mm_por_pixel: float,
                        vertical: bool = False,
                        altura_mm: float = 4.0) -> np.ndarray:
    """
    Dibuja un texto en la imagen usando el punto medio como origen
    
    Args:
        img: Imagen sobre la cual dibujar
        texto: Texto a dibujar
        x_mm: Coordenada X en mm
        y_mm: Coordenada Y en mm
        punto_medio_px: Coordenadas del punto medio del segmento rojo (origen)
        mm_por_pixel: Factor de conversión
        vertical: True para texto vertical
        altura_mm: Altura del texto en mm
    
    Returns:
        Imagen con el texto dibujado
    """
    # La imagen siempre viene en COLOR (BGR) desde el servidor
    img_result = img.copy()
    
    # Punto medio del segmento rojo (origen de coordenadas)
    origen_x, origen_y = punto_medio_px
    
    # Calcular posición del texto en píxeles
    texto_x_px = origen_x + (x_mm / mm_por_pixel)
    texto_y_px = origen_y - (y_mm / mm_por_pixel)  # Invertir Y
    
    # Calcular escala del texto basada en la altura deseada
    # cv2.putText con FONT_HERSHEY_SIMPLEX y thickness=2 da aprox 20px de altura con scale=1
    altura_px = altura_mm / mm_por_pixel
    font_scale = altura_px / 20.0
    thickness = max(1, int(font_scale * 2))
    
    # Color ROJO en BGR
    color_rojo = (0, 0, 255)
    
    # Obtener tamaño del texto
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_width, text_height), baseline = cv2.getTextSize(texto, font, font_scale, thickness)
    
    if vertical:
        # VERTICAL: Rotar texto 90 grados (crear imagen temporal, rotar y pegar)
        
        # Crear una imagen temporal para el texto
        padding = 10
        temp_w = text_width + 2 * padding
        temp_h = text_height + baseline + 2 * padding
        temp_img = np.zeros((temp_h, temp_w, 3), dtype=np.uint8)
        
        # Dibujar el texto en la imagen temporal
        cv2.putText(temp_img, texto, (padding, text_height + padding), 
                   font, font_scale, color_rojo, thickness, cv2.LINE_AA)
        
        # Rotar la imagen temporal 90 grados en sentido antihorario
        temp_img_rotada = cv2.rotate(temp_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        # Calcular posición donde pegar (centrado en la posición especificada)
        h_rot, w_rot = temp_img_rotada.shape[:2]
        start_x = int(texto_x_px - w_rot // 2)
        start_y = int(texto_y_px - h_rot // 2)
        
        # Pegar la imagen rotada en la imagen principal
        # Asegurar que no se salga de los límites
        end_x = min(start_x + w_rot, img_result.shape[1])
        end_y = min(start_y + h_rot, img_result.shape[0])
        start_x = max(0, start_x)
        start_y = max(0, start_y)
        
        if start_x < end_x and start_y < end_y:
            # Calcular dimensiones de la región a copiar
            region_w = end_x - start_x
            region_h = end_y - start_y
            
            # Extraer región de la imagen rotada
            temp_region = temp_img_rotada[0:region_h, 0:region_w]
            
            # Crear máscara (donde hay texto rojo)
            mask = cv2.cvtColor(temp_region, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(mask, 1, 255, cv2.THRESH_BINARY)
            
            # Copiar solo el texto (usando la máscara)
            img_result[start_y:end_y, start_x:end_x][mask > 0] = temp_region[mask > 0]
        
        print(f"[texto] '{texto}' dibujado en ({x_mm:.1f}, {y_mm:.1f}) mm - VERTICAL (rotado 90°)")
    else:
        # HORIZONTAL: Dibujar normalmente
        pos_x = int(texto_x_px)
        pos_y = int(texto_y_px)
        
        cv2.putText(img_result, texto, (pos_x, pos_y), 
                   font, font_scale, color_rojo, thickness, cv2.LINE_AA)
        
        print(f"[texto] '{texto}' dibujado en ({x_mm:.1f}, {y_mm:.1f}) mm - HORIZONTAL")
    
    return img_result

