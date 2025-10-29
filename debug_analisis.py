#!/usr/bin/env python3
"""
Script para debuggear el análisis de la imagen TC-441-20
"""

import cv2
import numpy as np
from contornos_analyzer import analizar_imagen_completa

def debug_imagen():
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
    print(f"Valor promedio de píxeles: {np.mean(img_gray):.2f}")
    print(f"Valor mínimo: {np.min(img_gray)}")
    print(f"Valor máximo: {np.max(img_gray)}")
    
    # Contar píxeles claros vs oscuros
    píxeles_claros = np.sum(img_gray > 127)
    píxeles_oscuros = np.sum(img_gray <= 127)
    total_píxeles = img_gray.size
    
    print(f"Píxeles claros (>127): {píxeles_claros} ({píxeles_claros/total_píxeles*100:.1f}%)")
    print(f"Píxeles oscuros (<=127): {píxeles_oscuros} ({píxeles_oscuros/total_píxeles*100:.1f}%)")
    
    if píxeles_claros > píxeles_oscuros:
        print("CONCLUSION: La imagen tiene fondo CLARO (necesita inversión)")
        img_fondo_blanco = img_gray
        img_fondo_negro = 255 - img_gray
    else:
        print("CONCLUSION: La imagen tiene fondo OSCURO (no necesita inversión)")
        img_fondo_negro = img_gray
        img_fondo_blanco = 255 - img_gray
    
    # Analizar con verbose=True para ver todos los pasos
    print("\n" + "="*60)
    print("INICIANDO ANÁLISIS COMPLETO")
    print("="*60)
    
    resultado = analizar_imagen_completa(img_fondo_negro, mm_por_pixel=0.1, verbose=True)
    
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
    debug_imagen()
