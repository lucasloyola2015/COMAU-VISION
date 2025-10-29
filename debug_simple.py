#!/usr/bin/env python3
"""
Script simple para debuggear el análisis sin emojis
"""

import cv2
import numpy as np

def debug_imagen_simple():
    print("DEBUG: Analizando TC-441-20...")
    
    # Cargar imagen
    img_path = "imagenes_juntas/TC-441-20.jpg"
    print(f"Cargando imagen: {img_path}")
    
    img = cv2.imread(img_path)
    if img is None:
        print("ERROR: No se pudo cargar la imagen")
        return
    
    print(f"Imagen cargada: {img.shape}")
    
    # Convertir a escala de grises
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    print(f"Convertida a escala de grises: {img_gray.shape}")
    
    # Verificar el fondo de la imagen
    print("\n=== VERIFICACION DE FONDO ===")
    print(f"Valor promedio de pixeles: {np.mean(img_gray):.2f}")
    print(f"Valor minimo: {np.min(img_gray)}")
    print(f"Valor maximo: {np.max(img_gray)}")
    
    # Contar pixeles claros vs oscuros
    pixeles_claros = np.sum(img_gray > 127)
    pixeles_oscuros = np.sum(img_gray <= 127)
    total_pixeles = img_gray.size
    
    print(f"Pixeles claros (>127): {pixeles_claros} ({pixeles_claros/total_pixeles*100:.1f}%)")
    print(f"Pixeles oscuros (<=127): {pixeles_oscuros} ({pixeles_oscuros/total_pixeles*100:.1f}%)")
    
    if pixeles_claros > pixeles_oscuros:
        print("CONCLUSION: La imagen tiene fondo CLARO (necesita inversion)")
        img_para_analisis = 255 - img_gray
    else:
        print("CONCLUSION: La imagen tiene fondo OSCURO (usar original)")
        img_para_analisis = img_gray
    
    # Binarizar la imagen
    print("\n=== BINARIZACION ===")
    _, img_binaria = cv2.threshold(img_para_analisis, 127, 255, cv2.THRESH_BINARY_INV)
    print(f"Imagen binarizada: {img_binaria.shape}")
    
    # Guardar imagen binarizada para inspeccionar
    cv2.imwrite("debug_binaria.jpg", img_binaria)
    print("Imagen binarizada guardada como debug_binaria.jpg")
    
    # Mostrar estadisticas de la imagen binarizada
    pixeles_blancos = np.sum(img_binaria == 255)
    pixeles_negros = np.sum(img_binaria == 0)
    print(f"Pixeles blancos en binaria: {pixeles_blancos}")
    print(f"Pixeles negros en binaria: {pixeles_negros}")
    
    # Detectar contornos
    print("\n=== DETECCION DE CONTORNOS ===")
    contours, hierarchy = cv2.findContours(img_binaria, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    print(f"Contornos detectados: {len(contours)}")
    
    if hierarchy is not None:
        print(f"Jerarquia shape: {hierarchy.shape}")
        
        # Buscar contorno principal (sin padre)
        main_contour_idx = -1
        max_area = 0
        
        for i, contour in enumerate(contours):
            parent = hierarchy[0][i][3]
            area = cv2.contourArea(contour)
            
            if parent == -1 and area > max_area:
                max_area = area
                main_contour_idx = i
        
        print(f"Contorno principal encontrado: indice {main_contour_idx}, area {max_area:.2f}")
        
        if main_contour_idx != -1:
            # Buscar agujeros (hijos del contorno principal)
            print("\n=== BUSCANDO AGUJEROS ===")
            holes = []
            first_child = hierarchy[0][main_contour_idx][2]
            
            print(f"Primer hijo del contorno principal: {first_child}")
            print(f"Jerarquia del contorno principal: {hierarchy[0][main_contour_idx]}")
            
            # Mostrar todos los contornos y su jerarquia
            print("\n=== TODOS LOS CONTORNOS ===")
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                parent = hierarchy[0][i][3]
                child = hierarchy[0][i][2]
                if area > 100:  # Solo mostrar contornos con area > 100
                    print(f"Contorno {i}: area={area:.1f}, parent={parent}, child={child}")
            
            if first_child != -1:
                child_idx = first_child
                while child_idx != -1:
                    area = cv2.contourArea(contours[child_idx])
                    print(f"  Agujero {len(holes)+1}: indice {child_idx}, area {area:.2f}")
                    holes.append(contours[child_idx])
                    child_idx = hierarchy[0][child_idx][0]
            
            print(f"Total agujeros encontrados: {len(holes)}")
            
            # Analizar cada agujero
            if holes:
                print("\n=== ANALISIS DE AGUJEROS ===")
                for i, hole in enumerate(holes):
                    area = cv2.contourArea(hole)
                    perimeter = cv2.arcLength(hole, True)
                    
                    # Calcular circularidad simple
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter * perimeter)
                        circularity_percentage = circularity * 100
                    else:
                        circularity_percentage = 0
                    
                    print(f"Agujero {i+1}:")
                    print(f"  Area: {area:.2f} px^2")
                    print(f"  Perimetro: {perimetro:.2f} px")
                    print(f"  Circularidad: {circularity_percentage:.1f}%")
                    
                    if circularity_percentage > 90:
                        print(f"  -> REDONDO")
                    else:
                        print(f"  -> IRREGULAR")
        else:
            print("ERROR: No se encontro contorno principal")
    else:
        print("ERROR: No se pudo obtener jerarquia de contornos")

if __name__ == "__main__":
    debug_imagen_simple()