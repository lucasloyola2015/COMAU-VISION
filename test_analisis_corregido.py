#!/usr/bin/env python3
"""
Script para probar el análisis corregido
"""

import cv2
import numpy as np
from contornos_analyzer_simple import analizar_imagen_completa

def test_analisis():
    print("TEST: Analizando TC-441-20 con lógica corregida...")
    
    # Cargar imagen
    img_path = "imagenes_juntas/TC-441-20.jpg"
    print(f"Cargando imagen: {img_path}")
    
    img = cv2.imread(img_path)
    if img is None:
        print("ERROR: No se pudo cargar la imagen")
        return
    
    # Convertir a escala de grises
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    print(f"Imagen cargada: {img_gray.shape}")
    
    # Verificar el fondo
    pixeles_claros = np.sum(img_gray > 127)
    pixeles_oscuros = np.sum(img_gray <= 127)
    
    if pixeles_oscuros > pixeles_claros:
        print("Fondo OSCURO - invirtiendo para obtener fondo blanco")
        img_para_analisis = 255 - img_gray
    else:
        print("Fondo CLARO - usando imagen original (ya tiene fondo blanco)")
        img_para_analisis = img_gray
    
    # Analizar
    print("\n" + "="*60)
    print("INICIANDO ANÁLISIS CORREGIDO")
    print("="*60)
    
    resultado = analizar_imagen_completa(img_para_analisis, mm_por_pixel=0.1, verbose=True)
    
    print("\n" + "="*60)
    print("RESULTADO FINAL")
    print("="*60)
    
    if resultado['ok']:
        print("ANÁLISIS EXITOSO")
        print(f"Agujeros detectados: {len(resultado['agujeros'])}")
        
        if resultado['agujeros']:
            print("\nDetalles de agujeros:")
            for i, agujero in enumerate(resultado['agujeros']):
                print(f"  {i+1}. {agujero['clasificacion']} - Área: {agujero['area_mm2']:.2f} mm²")
        else:
            print("ADVERTENCIA: No se detectaron agujeros")
            
        print(f"Contorno principal: {resultado['contorno_principal']['area_mm2']:.2f} mm²")
        print(f"Dimensiones: {resultado['contorno_principal']['bbox_width_mm']:.1f} x {resultado['contorno_principal']['bbox_height_mm']:.1f} mm")
    else:
        print(f"ERROR en análisis: {resultado['error']}")

if __name__ == "__main__":
    test_analisis()
