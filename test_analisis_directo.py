import cv2
import numpy as np
from contornos_analyzer_fixed import analizar_imagen_completa, crear_visualizacion

def test_analisis_directo():
    print("=== PRUEBA DIRECTA DE ANÁLISIS TC-441-20 ===")
    
    # Cargar imagen TC-441-20
    img_path = "imagenes_juntas/TC-441-20.jpg"
    print(f"Cargando imagen: {img_path}")
    
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print("ERROR: No se pudo cargar la imagen")
        return
    
    print(f"Imagen cargada: {img.shape}")
    
    # Detectar fondo
    pixeles_claros = np.sum(img > 127)
    pixeles_oscuros = np.sum(img <= 127)
    
    print(f"Píxeles claros: {pixeles_claros}")
    print(f"Píxeles oscuros: {pixeles_oscuros}")
    
    if pixeles_oscuros > pixeles_claros:
        print("Fondo OSCURO - invirtiendo para obtener fondo blanco")
        img_para_analisis = 255 - img
    else:
        print("Fondo CLARO - usando imagen original")
        img_para_analisis = img
    
    # Analizar imagen
    print("\nIniciando análisis...")
    analisis = analizar_imagen_completa(img_para_analisis, mm_por_pixel=0.1, verbose=True)
    
    if analisis.get('ok'):
        print("\n=== RESULTADOS ===")
        
        contorno = analisis.get('contorno_principal', {})
        print(f"Contorno principal:")
        print(f"  - Área: {contorno.get('area_mm2', 0):.2f} mm²")
        print(f"  - Dimensiones: {contorno.get('bbox_width_mm', 0):.1f} x {contorno.get('bbox_height_mm', 0):.1f} mm")
        
        agujeros = analisis.get('agujeros', [])
        print(f"\nAgujeros detectados: {len(agujeros)}")
        for i, agujero in enumerate(agujeros):
            print(f"  {i+1}. {agujero.get('clasificacion', 'N/A')} - Área: {agujero.get('area_mm2', 0):.2f} mm²")
        
        # Crear visualización
        print("\nCreando visualización...")
        img_visualizacion = crear_visualizacion(img_para_analisis, analisis)
        
        if img_visualizacion is not None:
            output_path = "test_visualizacion_directa.jpg"
            cv2.imwrite(output_path, img_visualizacion)
            print(f"OK Visualización guardada como {output_path}")
        else:
            print("ERROR No se pudo crear la visualización")
            
    else:
        print(f"ERROR en análisis: {analisis.get('error', 'Error desconocido')}")

if __name__ == "__main__":
    test_analisis_directo()
