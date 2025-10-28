# vision_manager.py
"""
Vision Manager - COMAU-VISION
=============================

Gestor de configuración básico para el sistema de visión.
Maneja la carga y guardado de configuraciones desde/hacia config.json.
"""

import os
import json


def _load_config():
    """Cargar configuración desde config.json"""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[vision_manager] Error cargando config.json: {e}")
        return {}


def _save_config(config):
    """Guardar configuración en config.json"""
    try:
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[vision_manager] Error guardando config.json: {e}")
        return False


def server_test():
    """
    Endpoint para el botón del Dashboard.
    Captura un frame del streaming de video y lo procesa.
    
    Returns:
        dict: Resultado con imagen procesada y datos de trayectoria
    """
    try:
        print("[vision_manager] 🧪 Ejecutando server_test...")
        
        # Importar dependencias
        import cv2
        import base64
        import requests
        import numpy as np
        from src.vision import camera_manager
        
        # Capturar frame del streaming
        print("[vision_manager] 📸 Capturando frame del streaming...")
        image = camera_manager.get_frame_raw()
        
        if image is None:
            return {
                'ok': False,
                'error': 'Error capturando imagen',
                'mensaje': 'No se pudo capturar el frame'
            }
        
        # Convertir imagen a bytes para envío
        _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        image_bytes = buffer.tobytes()
        
        # Enviar imagen al servidor de procesamiento
        print("[vision_manager] 📤 Enviando imagen al servidor de procesamiento...")
        url = "http://127.0.0.1:8000/process/"
        
        files = {"file": ("capture.jpg", image_bytes, "image/jpeg")}
        
        try:
            response = requests.post(url, files=files, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # Procesar respuesta
                overlay_image_b64 = data.get('overlay_image', '')
                trajectory_vectors = data.get('trajectory_vectors', [])
                junta_segment_length_mm = data.get('junta_segment_length_mm', 0)
                holes_detectados = data.get('holes_detectados', 0)
                
                print(f"[vision_manager] ✅ Procesamiento exitoso - {len(trajectory_vectors)} vectores recibidos")

                return {
                    'ok': True,
                    'mensaje': 'Procesamiento completado',
                    'overlay_image': overlay_image_b64,
                    'trajectory_vectors': trajectory_vectors,
                    'data': {
                        'status': 'success',
                        'vectors_count': len(trajectory_vectors),
                        'junta_detectada': data.get('junta_detectada', False),
                        'holes_detectados': holes_detectados,
                        'aruco_base_detectado': data.get('aruco_base_detectado', False),
                        'aruco_tool_detectado': data.get('aruco_tool_detectado', False),
                        'junta_segment_length_mm': junta_segment_length_mm
                    }
                }
                
            else:
                print(f"[vision_manager] ❌ Error del servidor: {response.status_code}")
                return {
                    'ok': False,
                    'error': f'Error del servidor: {response.status_code}',
                    'mensaje': 'Error en el procesamiento'
                }
                
        except requests.exceptions.RequestException as e:
            print(f"[vision_manager] ❌ Error de conexión: {e}")
            return {
                'ok': False,
                'error': f'Error de conexión: {str(e)}',
                'mensaje': 'No se pudo conectar al servidor'
            }

    except Exception as e:
        print(f"[vision_manager] ❌ Error en server_test: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ok': False,
            'error': str(e),
            'mensaje': 'Error en prueba'
        }