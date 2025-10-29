import requests
import json
import base64
import cv2
import os

def test_parametrizacion_tc441():
    print("=== PRUEBA DE PARAMETRIZACIÓN TC-441-20 ===")
    
    # URL del servidor
    url = "http://localhost:5001/api/juntas/parametrizar"
    
    # Cargar imagen TC-441-20
    img_path = "imagenes_juntas/TC-441-20.jpg"
    if not os.path.exists(img_path):
        print(f"ERROR: No se encontró la imagen {img_path}")
        return
    
    print(f"Cargando imagen: {img_path}")
    
    # Leer imagen y convertir a base64
    with open(img_path, 'rb') as f:
        img_data = f.read()
    
    img_b64 = base64.b64encode(img_data).decode('utf-8')
    
    # Preparar datos del formulario
    data = {
        'nombre_junta': 'TC-441-20',
        'junta_id': '4',
        'mm_por_pixel_manual': '0.1'
    }
    
    files = {
        'imagen': ('TC-441-20.jpg', img_data, 'image/jpeg')
    }
    
    print("Enviando solicitud de parametrización...")
    
    try:
        response = requests.post(url, data=data, files=files, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('ok'):
                print("✓ Parametrización exitosa!")
                
                # Mostrar información del análisis
                analisis = result.get('analisis', {})
                contorno = analisis.get('contorno_principal', {})
                agujeros = analisis.get('agujeros', [])
                
                print(f"\n=== RESULTADOS DEL ANÁLISIS ===")
                print(f"Contorno principal:")
                print(f"  - Área: {contorno.get('area_mm2', 0):.2f} mm²")
                print(f"  - Dimensiones: {contorno.get('bbox_width_mm', 0):.1f} x {contorno.get('bbox_height_mm', 0):.1f} mm")
                
                print(f"\nAgujeros detectados: {len(agujeros)}")
                for i, agujero in enumerate(agujeros):
                    print(f"  {i+1}. {agujero.get('clasificacion', 'N/A')} - Área: {agujero.get('area_mm2', 0):.2f} mm²")
                
                # Verificar si hay imagen de visualización
                if result.get('imagen_visualizacion'):
                    print(f"\n✓ Imagen de visualización generada")
                else:
                    print(f"\n⚠️ No se generó imagen de visualización")
                
                # Guardar imagen de visualización si existe
                if result.get('imagen_visualizacion'):
                    vis_data = base64.b64decode(result['imagen_visualizacion'])
                    with open('test_visualizacion_tc441.jpg', 'wb') as f:
                        f.write(vis_data)
                    print("✓ Imagen de visualización guardada como test_visualizacion_tc441.jpg")
                
            else:
                print(f"✗ Error en parametrización: {result.get('error', 'Error desconocido')}")
        else:
            print(f"✗ Error HTTP {response.status_code}: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("✗ Error: No se pudo conectar al servidor. ¿Está ejecutándose en puerto 5001?")
    except Exception as e:
        print(f"✗ Error inesperado: {e}")

if __name__ == "__main__":
    test_parametrizacion_tc441()
