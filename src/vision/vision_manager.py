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
        cfg = _load_config().get('vision', {})
        vision_ip = cfg.get('vision_server_ip', '127.0.0.1')
        vision_port = cfg.get('vision_server_port', 8000)
        url = f"http://{vision_ip}:{vision_port}/process/"
        
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


def configure_vision_server(lista_muescas_mm=None, roi_rectangulo=None, vision_server_port=8000):
    """
    Configura variables específicas en el servidor de visión usando PATCH /config/
    
    Args:
        lista_muescas_mm (list): Lista de muescas en formato [{"x": int, "y": int}, ...]
        roi_rectangulo (dict): Configuración ROI en formato {"x_mm": int, "y_mm": int, ...}
        vision_server_port (int): Puerto del servidor de visión (default: 8000)
    
    Returns:
        dict: Resultado de la configuración
    """
    try:
        print("[vision_manager] 🔧 Configurando servidor de visión...")
        
        import requests
        
        # Construir payload para PATCH
        payload = {}
        
        if lista_muescas_mm is not None:
            payload["lista_muescas_mm"] = lista_muescas_mm
            print(f"[vision_manager] 📍 Configurando {len(lista_muescas_mm)} muescas")
        
        if roi_rectangulo is not None:
            payload["roi_rectangulo"] = roi_rectangulo
            print(f"[vision_manager] 📐 Configurando ROI: {roi_rectangulo}")
        
        if not payload:
            return {
                'ok': False,
                'error': 'No se proporcionaron datos para configurar',
                'mensaje': 'Debe especificar lista_muescas_mm o roi_rectangulo'
            }
        
        # Enviar configuración al servidor
        cfg = _load_config().get('vision', {})
        vision_ip = cfg.get('vision_server_ip', '127.0.0.1')
        vision_port = cfg.get('vision_server_port', vision_server_port)
        url = f"http://{vision_ip}:{vision_port}/config/"
        
        try:
            response = requests.patch(
                url, 
                json=payload, 
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            
            if response.status_code == 200:
                config_data = response.json()
                print(f"[vision_manager] ✅ Configuración aplicada exitosamente")
                
                return {
                    'ok': True,
                    'mensaje': 'Configuración aplicada correctamente',
                    'config': config_data
                }
                
            else:
                print(f"[vision_manager] ❌ Error del servidor: {response.status_code}")
                return {
                    'ok': False,
                    'error': f'Error del servidor: {response.status_code}',
                    'mensaje': 'Error aplicando configuración'
                }
                
        except requests.exceptions.RequestException as e:
            print(f"[vision_manager] ❌ Error de conexión: {e}")
            return {
                'ok': False,
                'error': f'Error de conexión: {str(e)}',
                'mensaje': 'No se pudo conectar al servidor de visión'
            }

    except Exception as e:
        print(f"[vision_manager] ❌ Error en configure_vision_server: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ok': False,
            'error': str(e),
            'mensaje': 'Error en configuración'
        }


def get_vision_server_config(vision_server_port=8000):
    """
    Obtiene la configuración actual del servidor de visión usando GET /config/
    
    Args:
        vision_server_port (int): Puerto del servidor de visión (default: 8000)
    
    Returns:
        dict: Configuración del servidor
    """
    try:
        print("[vision_manager] 📥 Obteniendo configuración del servidor de visión...")
        
        import requests
        
        cfg = _load_config().get('vision', {})
        vision_ip = cfg.get('vision_server_ip', '127.0.0.1')
        vision_port = cfg.get('vision_server_port', vision_server_port)
        url = f"http://{vision_ip}:{vision_port}/config/"
        
        try:
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                config_data = response.json()
                print(f"[vision_manager] ✅ Configuración obtenida exitosamente")
                
                return {
                    'ok': True,
                    'mensaje': 'Configuración obtenida correctamente',
                    'config': config_data
                }
                
            else:
                print(f"[vision_manager] ❌ Error del servidor: {response.status_code}")
                return {
                    'ok': False,
                    'error': f'Error del servidor: {response.status_code}',
                    'mensaje': 'Error obteniendo configuración'
                }
                
        except requests.exceptions.RequestException as e:
            print(f"[vision_manager] ❌ Error de conexión: {e}")
            return {
                'ok': False,
                'error': f'Error de conexión: {str(e)}',
                'mensaje': 'No se pudo conectar al servidor de visión'
            }

    except Exception as e:
        print(f"[vision_manager] ❌ Error en get_vision_server_config: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ok': False,
            'error': str(e),
            'mensaje': 'Error obteniendo configuración'
        }


def configure_aruco_vision_server(config_path='config.json', vision_server_port=8000):
    """
    Configura los parámetros de ArUcos en el servidor de visión usando PATCH /config/
    Lee los datos desde config.json y los envía al servidor de visión.
    
    Args:
        config_path (str): Ruta al archivo config.json (default: 'config.json')
        vision_server_port (int): Puerto del servidor de visión (default: 8000)
    
    Returns:
        dict: Resultado de la configuración
    """
    try:
        print("[vision_manager] 🔧 Configurando ArUcos en servidor de visión...")
        
        import requests
        import json
        import os
        
        # Cargar configuración desde config.json
        if not os.path.exists(config_path):
            return {
                'ok': False,
                'error': f'Archivo de configuración no encontrado: {config_path}',
                'mensaje': 'No se pudo leer la configuración'
            }
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        aruco_config = config.get('aruco', {})
        base_config = aruco_config.get('base', {})
        tool_config = aruco_config.get('tool', {})
        
        # Construir payload para PATCH con la estructura que espera el servidor de visión
        troqueladora_x = int(round(base_config.get('troqueladora_center_x_mm', 0)))
        troqueladora_y = int(round(base_config.get('troqueladora_center_y_mm', 0)))
        
        payload = {
            'aruco_config': {
                'aruco_base_id': base_config.get('reference_id', 0),
                'aruco_base_size_mm': base_config.get('marker_size_mm', 70.0),
                'aruco_tool_id': tool_config.get('reference_id', 0),
                'aruco_tool_size_mm': tool_config.get('marker_size_mm', 50.0)
            },
            'troqueladora': {
                'x_mm': troqueladora_x,
                'y_mm': troqueladora_y,
                'diametro_mm': 10  # Diámetro por defecto del círculo del centro del troquel
            }
        }
        
        print(f"[vision_manager] 📋 Configuración ArUcos a enviar:")
        print(f"  - Base ArUco ID: {payload['aruco_config']['aruco_base_id']}")
        print(f"  - Tamaño Base: {payload['aruco_config']['aruco_base_size_mm']}mm")
        print(f"  - Tool ArUco ID: {payload['aruco_config']['aruco_tool_id']}")
        print(f"  - Tamaño Tool: {payload['aruco_config']['aruco_tool_size_mm']}mm")
        print(f"  - Centro Troqueladora: ({payload['troqueladora']['x_mm']}, {payload['troqueladora']['y_mm']})mm")
        print(f"  - Diámetro Troqueladora: {payload['troqueladora']['diametro_mm']}mm")
        
        # Enviar configuración al servidor
        cfg = _load_config().get('vision', {})
        vision_ip = cfg.get('vision_server_ip', '127.0.0.1')
        vision_port = cfg.get('vision_server_port', vision_server_port)
        url = f"http://{vision_ip}:{vision_port}/config/"
        
        try:
            response = requests.patch(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            
            if response.status_code == 200:
                config_data = response.json()
                print(f"[vision_manager] ✅ Configuración de ArUcos aplicada exitosamente")
                print(f"[vision_manager] 📥 Respuesta del servidor:")
                print(f"  - Status: {response.status_code}")
                print(f"  - Respuesta completa: {config_data}")
                print(f"  - Configuración ArUcos recibida:")
                if 'aruco_config' in config_data:
                    aruco_resp = config_data['aruco_config']
                    print(f"    - Base ID: {aruco_resp.get('aruco_base_id', 'N/A')}")
                    print(f"    - Tamaño Base: {aruco_resp.get('aruco_base_size_mm', 'N/A')}mm")
                    print(f"    - Tool ID: {aruco_resp.get('aruco_tool_id', 'N/A')}")
                    print(f"    - Tamaño Tool: {aruco_resp.get('aruco_tool_size_mm', 'N/A')}mm")
                
                if 'troqueladora' in config_data:
                    troqueladora_resp = config_data['troqueladora']
                    print(f"    - Centro Troqueladora: ({troqueladora_resp.get('x_mm', 'N/A')}, {troqueladora_resp.get('y_mm', 'N/A')})mm")
                    print(f"    - Diámetro: {troqueladora_resp.get('diametro_mm', 'N/A')}mm")
                else:
                    print(f"    - No se encontró configuración de troqueladora en la respuesta")
                
                return {
                    'ok': True,
                    'mensaje': 'Configuración de ArUcos aplicada correctamente',
                    'config': config_data
                }
            
            else:
                print(f"[vision_manager] ❌ Error del servidor: {response.status_code}")
                print(f"[vision_manager] Respuesta: {response.text}")
                return {
                    'ok': False,
                    'error': f'Error del servidor: {response.status_code}',
                    'mensaje': 'Error aplicando configuración de ArUcos'
                }
                
        except requests.exceptions.RequestException as e:
            print(f"[vision_manager] ❌ Error de conexión: {e}")
            return {
                'ok': False,
                'error': f'Error de conexión: {str(e)}',
                'mensaje': 'No se pudo conectar al servidor de visión'
            }
    
    except Exception as e:
        print(f"[vision_manager] ❌ Error en configure_aruco_vision_server: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ok': False,
            'error': str(e),
            'mensaje': 'Error en configuración de ArUcos'
        }


def configure_roi_vision_server(config_path='config.json', vision_server_port=8000):
    """
    Configura los parámetros de ROI en el servidor de visión usando PATCH /config/
    Lee los datos desde config.json y los envía al servidor de visión.
    
    Args:
        config_path (str): Ruta al archivo config.json (default: 'config.json')
        vision_server_port (int): Puerto del servidor de visión (default: 8000)
    
    Returns:
        dict: Resultado de la configuración
    """
    try:
        print("[vision_manager] 🔧 Configurando ROI en servidor de visión...")
        
        import requests
        import json
        import os
        
        # Cargar configuración desde config.json
        if not os.path.exists(config_path):
            return {
                'ok': False,
                'error': f'Archivo de configuración no encontrado: {config_path}',
                'mensaje': 'No se pudo leer la configuración'
            }
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        vision_config = config.get('vision', {})
        
        # Obtener dimensiones base de la junta seleccionada
        width_base_mm = 200  # Valor por defecto
        height_base_mm = 150  # Valor por defecto
        
        try:
            # Intentar obtener la junta seleccionada desde juntas.json
            # Buscar juntas.json en el mismo directorio que config.json o en el directorio actual
            juntas_path = None
            if os.path.dirname(config_path):
                juntas_path = os.path.join(os.path.dirname(config_path), 'juntas.json')
            else:
                juntas_path = 'juntas.json'
            
            if not os.path.exists(juntas_path):
                # Intentar en el directorio actual
                juntas_path = os.path.join(os.getcwd(), 'juntas.json')
            
            if os.path.exists(juntas_path):
                with open(juntas_path, 'r', encoding='utf-8') as f:
                    juntas_db = json.load(f)
                
                selected_id = juntas_db.get('selected_id')
                if selected_id is not None:
                    juntas = juntas_db.get('juntas', [])
                    junta = next((j for j in juntas if j.get('id') == selected_id), None)
                    
                    if junta:
                        # Verificar si la junta está parametrizada
                        if junta.get('parametrizado') and junta.get('parametros_proporcionales'):
                            px_mm = junta.get('px_mm', 1.0)
                            parametros = junta.get('parametros_proporcionales', {})
                            
                            # Obtener ancho y alto desde parametros_proporcionales
                            ancho_junta_px = parametros.get('ancho_junta_px')
                            alto_junta_px = parametros.get('alto_junta_px')
                            
                            if ancho_junta_px is not None and alto_junta_px is not None:
                                # Calcular dimensiones en mm (igual que parametrosManager.get_valor)
                                width_base_mm = ancho_junta_px / px_mm
                                height_base_mm = alto_junta_px / px_mm
                                print(f"[vision_manager] 📐 Dimensiones obtenidas de junta seleccionada ({junta.get('nombre', 'Unknown')}): {width_base_mm:.1f}mm x {height_base_mm:.1f}mm")
                            else:
                                print(f"[vision_manager] ⚠️ Junta parametrizada pero no tiene ancho_junta_px/alto_junta_px, usando valores por defecto")
                        else:
                            print(f"[vision_manager] ⚠️ Junta no parametrizada, usando valores por defecto")
        except Exception as e:
            print(f"[vision_manager] ⚠️ No se pudo obtener junta seleccionada, usando valores por defecto: {e}")
        
        # Obtener valores de zoom
        roi_zoom_x_percent = vision_config.get('roi_zoom_x_percent', 100)
        roi_zoom_y_percent = vision_config.get('roi_zoom_y_percent', 100)
        
        # Calcular dimensiones finales aplicando zoom
        width_final = int((roi_zoom_x_percent * width_base_mm) / 100)
        height_final = int((roi_zoom_y_percent * height_base_mm) / 100)
        
        # Construir payload para PATCH con la estructura de ROI
        payload = {
            'roi_rectangulo': {
                'x_mm': vision_config.get('roi_offset_x_mm', 0),
                'y_mm': vision_config.get('roi_offset_y_mm', 0),
                'width_mm': width_final,
                'height_mm': height_final,
                'rotation': 0
            }
        }
        
        print(f"[vision_manager] 📋 Configuración ROI a enviar:")
        print(f"  - Offset: ({payload['roi_rectangulo']['x_mm']}, {payload['roi_rectangulo']['y_mm']})mm")
        print(f"  - Dimensiones base: {width_base_mm}mm x {height_base_mm}mm")
        print(f"  - Zoom aplicado: {roi_zoom_x_percent}% x {roi_zoom_y_percent}%")
        print(f"  - Dimensiones finales: {width_final}mm x {height_final}mm")
        print(f"  - Rotación: {payload['roi_rectangulo']['rotation']}°")
        
        # Enviar configuración al servidor
        url = f"http://127.0.0.1:{vision_server_port}/config/"
        
        try:
            response = requests.patch(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            
            if response.status_code == 200:
                config_data = response.json()
                print(f"[vision_manager] ✅ Configuración de ROI aplicada exitosamente")
                
                return {
                    'ok': True,
                    'mensaje': 'Configuración de ROI aplicada correctamente',
                    'config': config_data
                }
            
            else:
                print(f"[vision_manager] ❌ Error del servidor: {response.status_code}")
                print(f"[vision_manager] Respuesta: {response.text}")
                return {
                    'ok': False,
                    'error': f'Error del servidor: {response.status_code}',
                    'mensaje': 'Error aplicando configuración de ROI'
                }
                
        except requests.exceptions.RequestException as e:
            print(f"[vision_manager] ❌ Error de conexión: {e}")
            return {
                'ok': False,
                'error': f'Error de conexión: {str(e)}',
                'mensaje': 'No se pudo conectar al servidor de visión'
            }
    
    except Exception as e:
        print(f"[vision_manager] ❌ Error en configure_roi_vision_server: {e}")
        import traceback
        traceback.print_exc()
        return {
            'ok': False,
            'error': str(e),
            'mensaje': 'Error en configuración de ROI'
        }