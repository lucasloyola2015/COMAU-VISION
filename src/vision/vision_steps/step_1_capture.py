# src/vision/vision_steps/step_1_capture.py

def capturar_imagen():
    """
    Paso 1: Capturar imagen de la cámara y convertir a escala de grises.
    Returns:
        dict: {
            'ok': bool,
            'cv2_frame': np.ndarray,      # Imagen a color original
            'gray_frame': np.ndarray,     # Imagen en escala de grises
            'rgb_background': np.ndarray, # Imagen en blanco y negro con canales RGB
            'error': str
        }
    """
    try:
        print("[vision_manager] 📸 Paso 1: Capturando imagen...")
        
        # Importar dependencias
        import cv2
        import numpy as np
        import time
        from src.vision import camera_manager
        
        # Capturar frame fresco de la cámara
        cv2_frame = None
        for attempt in range(3):
            cv2_frame = camera_manager.get_frame_raw()
            if cv2_frame is not None:
                print(f"[vision_manager] ✓ Frame capturado en intento {attempt + 1}")
                break
            else:
                print(f"[vision_manager] ⚠️ Intento {attempt + 1} falló, reintentando...")
                time.sleep(0.1)
        
        if cv2_frame is None:
            return {
                'ok': False,
                'error': 'No se pudo capturar un frame fresco de la cámara después de 3 intentos'
            }
        
        gray_frame = cv2.cvtColor(cv2_frame, cv2.COLOR_BGR2GRAY)
        rgb_background = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2RGB)
        
        return {
            'ok': True,
            'cv2_frame': cv2_frame,
            'gray_frame': gray_frame,
            'rgb_background': rgb_background
        }
        
    except Exception as e:
        return {'ok': False, 'error': str(e)}