#!/usr/bin/env python3
"""
Script para probar la generación de imagen coloreada
"""

import cv2
import numpy as np
from contornos_analyzer_simple import analizar_imagen_completa, crear_visualizacion

def test_visualizacion():
    print("TEST: Generando imagen coloreada de TC-441-20...")
    
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
    
    # DEBUG: Probar ambas versiones
    print(f"\nDEBUG: Probando ambas versiones...")
    print(f"Píxeles claros: {pixeles_claros} ({pixeles_claros/(pixeles_claros+pixeles_oscuros)*100:.1f}%)")
    print(f"Píxeles oscuros: {pixeles_oscuros} ({pixeles_oscuros/(pixeles_claros+pixeles_oscuros)*100:.1f}%)")
    
    # Probar con imagen original (sin invertir)
    print("\n--- PROBANDO CON IMAGEN ORIGINAL ---")
    resultado_original = analizar_imagen_completa(img_gray, mm_por_pixel=0.1, verbose=False)
    if resultado_original['ok']:
        print(f"Imagen original: {len(resultado_original['agujeros'])} agujeros detectados")
    else:
        print(f"Imagen original: ERROR - {resultado_original['error']}")
    
    # Probar con imagen invertida
    print("\n--- PROBANDO CON IMAGEN INVERTIDA ---")
    resultado_invertida = analizar_imagen_completa(255 - img_gray, mm_por_pixel=0.1, verbose=False)
    if resultado_invertida['ok']:
        print(f"Imagen invertida: {len(resultado_invertida['agujeros'])} agujeros detectados")
    else:
        print(f"Imagen invertida: ERROR - {resultado_invertida['error']}")
    
    # Usar la que detecte más agujeros
    if resultado_original['ok'] and resultado_invertida['ok']:
        if len(resultado_original['agujeros']) >= len(resultado_invertida['agujeros']):
            print("\nUsando imagen ORIGINAL (más agujeros detectados)")
            resultado = resultado_original
            img_para_analisis = img_gray
        else:
            print("\nUsando imagen INVERTIDA (más agujeros detectados)")
            resultado = resultado_invertida
            img_para_analisis = 255 - img_gray
    elif resultado_original['ok']:
        print("\nUsando imagen ORIGINAL (única que funciona)")
        resultado = resultado_original
        img_para_analisis = img_gray
    elif resultado_invertida['ok']:
        print("\nUsando imagen INVERTIDA (única que funciona)")
        resultado = resultado_invertida
        img_para_analisis = 255 - img_gray
    else:
        print("ERROR: Ninguna versión funciona")
        return
    
    # Analizar
    print("\nAnalizando imagen...")
    resultado = analizar_imagen_completa(img_para_analisis, mm_por_pixel=0.1, verbose=False)
    
    if not resultado['ok']:
        print(f"ERROR en análisis: {resultado['error']}")
        return
    
    print(f"Análisis exitoso - {len(resultado['agujeros'])} agujeros detectados")
    
    # Crear visualización
    print("Generando imagen coloreada...")
    img_visualizacion = crear_visualizacion(img_para_analisis, resultado)
    
    if img_visualizacion is not None:
        # Guardar imagen coloreada
        cv2.imwrite("debug_visualizacion.jpg", img_visualizacion)
        print("Imagen coloreada guardada como debug_visualizacion.jpg")
        
        # Mostrar estadísticas
        print("\nColores en la imagen:")
        print("- VERDE: Contorno principal de la junta")
        print("- ROJO: Agujeros grandes (Redondo Grande)")
        print("- MAGENTA: Agujeros chicos (Redondo Chico)")
        print("- NARANJA: Agujeros irregulares")
        print("- AZUL: Línea de referencia entre agujeros extremos")
        
        # Mostrar detalles de agujeros
        if resultado['agujeros']:
            print(f"\nAgujeros detectados:")
            for i, agujero in enumerate(resultado['agujeros']):
                print(f"  {i+1}. {agujero['clasificacion']} - Área: {agujero['area_mm2']:.2f} mm²")
    else:
        print("ERROR: No se pudo generar la visualización")

if __name__ == "__main__":
    test_visualizacion()
