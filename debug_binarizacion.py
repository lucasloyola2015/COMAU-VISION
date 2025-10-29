import cv2
import numpy as np

def debug_binarizacion():
    print("=== DEBUG DE BINARIZACIÓN TC-441-20 ===")
    
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
    
    # Binarizar la imagen
    print("\nBinarizando imagen...")
    _, img_binaria = cv2.threshold(img_para_analisis, 127, 255, cv2.THRESH_BINARY_INV)
    
    # Guardar imagen binarizada
    cv2.imwrite("debug_binaria_tc441.jpg", img_binaria)
    print("Imagen binarizada guardada como debug_binaria_tc441.jpg")
    
    # Mostrar estadísticas
    pixeles_blancos = np.sum(img_binaria == 255)
    pixeles_negros = np.sum(img_binaria == 0)
    print(f"Píxeles blancos en binaria: {pixeles_blancos}")
    print(f"Píxeles negros en binaria: {pixeles_negros}")
    
    # Detectar contornos
    print("\nDetectando contornos...")
    contours, _ = cv2.findContours(img_binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"Contornos detectados: {len(contours)}")
    
    # Mostrar información de cada contorno
    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        print(f"  Contorno {i}: área = {area:.1f} px²")
    
    # Probar con RETR_TREE para ver si hay jerarquía
    print("\nProbando con RETR_TREE...")
    contours_tree, hierarchy = cv2.findContours(img_binaria, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    print(f"Contornos con TREE: {len(contours_tree)}")
    print(f"Jerarquía shape: {hierarchy.shape}")
    
    # Mostrar jerarquía
    for i, contour in enumerate(contours_tree):
        area = cv2.contourArea(contour)
        parent = hierarchy[0][i][3]
        child = hierarchy[0][i][2]
        print(f"  Contorno {i}: área = {area:.1f}, parent = {parent}, child = {child}")

if __name__ == "__main__":
    debug_binarizacion()
