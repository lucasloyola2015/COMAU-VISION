from flask import Flask, send_from_directory, jsonify, request, Response
import os
import sys
import signal
import argparse
import subprocess
import threading
import time
import json
import base64
import requests
from datetime import datetime
from flask_socketio import SocketIO, emit
import sockets

from src.vision import camera_manager
from src.vision import yolo_detector
from src.vision.aruco_manager import detect_arucos_in_image, is_frame_detected, is_tool_detected
from src.vision.vision_manager import server_test

# Importar módulos de rendering
import muescas_renderer
import textos_renderer

# ============================================================
# CONFIGURACIÓN GLOBAL
# ============================================================

def get_junta_path(nombre_junta, filename):
    """Genera la ruta correcta para archivos de una junta: imagenes_juntas/{NOMBRE_DE_JUNTA}/{filename}"""
    return os.path.join('imagenes_juntas', nombre_junta, filename)
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEFAULT_PORT = 5000
CONFIG_FILE = 'config.json'
JUNTAS_FILE = 'juntas.json'

# Variables globales para gestión de Chrome
chrome_pid = None
vision_server_process = None  # Proceso del servidor de visión
flask_server = None
_shutting_down = False

# Variables para control de overlay temporal
_overlay_frame = None
_overlay_active_until = None


# ============================================================
# CONFIGURACIÓN DE FLASK
# ============================================================
app = Flask(__name__, 
            static_folder='static',
            static_url_path='/static',
            template_folder='templates')
sockets.init_socketio(app, cors_allowed_origins="*", async_mode="threading")
socketio = sockets.socketio

# Variable global para el proceso del servidor de visión
vision_server_process = None

# ============================================================
# MANEJO DE SEÑALES Y LIMPIEZA AL CERRAR
# ============================================================
import signal
import atexit

def cleanup_vision_server():
    """Limpia el servidor de visión al cerrar la aplicación"""
    global vision_server_process
    if vision_server_process and vision_server_process.poll() is None:
        print(f"[illinois-server] 🧹 Limpiando servidor de visión (PID: {vision_server_process.pid})")
        try:
            vision_server_process.terminate()
            vision_server_process.wait(timeout=3)
            print(f"[illinois-server] ✅ Servidor de visión detenido correctamente")
        except subprocess.TimeoutExpired:
            print(f"[illinois-server] ⚠️ Forzando terminación del servidor de visión")
            vision_server_process.kill()
            vision_server_process.wait()
        except Exception as e:
            print(f"[illinois-server] ❌ Error deteniendo servidor de visión: {e}")
        finally:
            vision_server_process = None

def signal_handler(signum, frame):
    """Manejador de señales para limpieza"""
    print(f"\n[illinois-server] 🛑 Señal {signum} recibida, cerrando aplicación...")
    cleanup_vision_server()
    exit(0)

# Registrar manejadores de señales
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Terminación del sistema

# Registrar función de limpieza al salir
atexit.register(cleanup_vision_server)

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 1

# ============================================================
# RUTAS PRINCIPALES
# ============================================================
@app.route('/')
def index():
    """Página principal con Panel de Control y Dashboard lado a lado"""
    return send_from_directory('templates', 'index.html')

@app.route('/templates/<path:filename>')
def serve_template(filename):
    """Servir archivos HTML de templates"""
    return send_from_directory('templates', filename)

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Servir archivos estáticos (CSS, JS, imágenes)"""
    return send_from_directory('static', filename)

@app.route('/imagenes_juntas/<path:filename>')
def serve_imagenes_juntas(filename):
    """Servir imágenes de juntas"""
    return send_from_directory('imagenes_juntas', filename)

@app.route('/juntas_analisis/<path:filename>')
def serve_juntas_analisis(filename):
    """Servir archivos de análisis y visualizaciones de juntas"""
    return send_from_directory('imagenes_juntas', filename)

# ============================================================
# API BÁSICA
# ============================================================
@app.route('/api/status', methods=['GET'])
def api_status():
    """Estado del servidor"""
    return jsonify({
        'ok': True,
        'status': 'online',
        'timestamp': datetime.now().isoformat(),
        'message': 'Servidor operativo'
    })

# ============================================================
# API CÁMARA
# ============================================================
@app.route('/api/config', methods=['GET'])
def api_get_config():
    """Obtiene la configuración completa"""
    try:
        config = camera_manager.load_config()
        return jsonify({'ok': True, 'data': config})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/connect_camera', methods=['POST'])
def api_connect_camera():
    """Intenta conectarse a la cámara guardada en config.json"""
    try:
        success, message = camera_manager.connectToCamera()
        return jsonify({
            'ok': success,
            'message': message,
            'connected': success
        })
    except Exception as e:
        return jsonify({
            'ok': False,
            'message': f'Error conectando: {str(e)}',
            'connected': False
        }), 500

@app.route('/api/scan_cams', methods=['GET'])
def api_scan_cameras():
    """Escanea cámaras disponibles del sistema"""
    try:
        devices = camera_manager.scan_cameras()
        
        # Convertir formato: {name, vid, pid} -> {name, uid, id}
        result_devices = []
        for idx, cam in enumerate(devices):
            uid = f"VID_{cam['vid']}&PID_{cam['pid']}"
            result_devices.append({
                "id": idx,
                "name": cam['name'],
                "uid": uid,
                "vid": cam['vid'],
                "pid": cam['pid']
            })
        
        return jsonify({
            'ok': True,
            'devices': result_devices
        })
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/cam_resolutions', methods=['GET'])
def api_get_resolutions():
    """Obtiene resoluciones soportadas para una cámara"""
    try:
        vid = request.args.get('vid')
        pid = request.args.get('pid')
        if not vid or not pid:
            return jsonify({'ok': False, 'error': 'VID y PID requeridos'}), 400
        
        resolutions = camera_manager.get_supported_resolutions(vid, pid)
        return jsonify({
            'ok': True,
            'resolutions': resolutions
        })
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/connect_cam', methods=['POST'])
def api_connect_cam():
    """Conecta a una cámara específica y guarda la configuración"""
    try:
        data = request.get_json()
        
        vid = data.get('vid')
        pid = data.get('pid')
        name = data.get('name', '')
        width = data.get('width')
        height = data.get('height')
        
        if not vid or not pid:
            return jsonify({'ok': False, 'error': 'VID y PID requeridos'}), 400
        
        # Conectar a la cámara
        success, error = camera_manager.connect_camera(vid, pid, width, height)
        
        if success:
            # Guardar configuración
            camera_manager.save_camera_config(vid, pid, name, width, height)
            return jsonify({
                'ok': True,
                'message': f'Conectado a {name}'
            })
        else:
            return jsonify({
                'ok': False,
                'error': error
            }), 500
    
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/video_feed')
def video_feed():
    """Stream de video en vivo desde la cámara, o frame estático si hay overlay temporal activo"""
    def generate():
        while True:
            global _overlay_frame, _overlay_active_until
            
            # Chequear si el overlay temporal sigue activo
            if _overlay_active_until is not None and time.time() < _overlay_active_until:
                # Overlay activo: servir la imagen estática
                if _overlay_frame is not None:
                    frame = _overlay_frame
                else:
                    continue
            else:
                # Overlay inactivo: servir stream en vivo
                if _overlay_active_until is not None and time.time() >= _overlay_active_until:
                    _overlay_active_until = None
                    _overlay_frame = None
                    print(f"[video_feed] Overlay temporal expirado, volviendo a stream en vivo")
                
                frame = camera_manager.get_frame()
                if frame is None:
                    continue
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: ' + str(len(frame)).encode() + b'\r\n\r\n'
                   + frame + b'\r\n')
            time.sleep(0.033)  # ~30 FPS
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ============================================================
# FUNCIONES AUXILIARES DE CONFIGURACIÓN
# ============================================================
def load_config():
    """Carga la configuración completa desde config.json"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[vision] Error cargando configuración: {e}")
    return {'vision': {}, 'aruco': {}}

def save_config(config_data):
    """Guarda la configuración completa en config.json"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        print(f"[vision] ✓ Configuración guardada")
        return True
    except Exception as e:
        print(f"[vision] ✗ Error guardando configuración: {e}")
        return False

def load_aruco_config():
    """Carga la configuración de ArUcos desde config.json"""
    config = load_config()
    
    # Configuración por defecto si no existe
    default_aruco = {
        'frame_aruco_id': 0,
        'frame_marker_size_mm': 42.0,
        'tool_aruco_id': 0,
        'tool_marker_size_mm': 42.0,
        'troqueladora_center_x_mm': 0,
        'troqueladora_center_y_mm': 0,
        'show_reference': False,
        'use_saved_reference': False,
        'saved_frame_reference': None,
        'saved_tool_reference': None
    }
    
    return config.get('aruco', default_aruco)

def save_aruco_config(full_config):
    """Guarda la configuración COMPLETA en config.json"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(full_config, f, indent=2)
        return True
    except Exception as e:
        print(f"[aruco] Error guardando config: {e}")
        return False

# ============================================================
# API ARUCO
# ============================================================
@app.route('/api/aruco/config', methods=['GET'])
def api_aruco_config():
    """Obtiene la configuración actual de ArUcos"""
    try:
        aruco_config = load_aruco_config()
        print(f"[aruco] GET /api/aruco/config - Retornando: {aruco_config}")
        return jsonify({'ok': True, 'aruco': aruco_config})
    except Exception as e:
        print(f"[aruco] Error en GET /api/aruco/config: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/overlay/render', methods=['POST'])
def api_overlay_render():
    """Endpoint para renderizar overlays con ArUcos"""
    try:
        import cv2
        import numpy as np
        from src.vision.frames_manager import get_global_overlay_manager
        from src.vision.aruco_manager import render_overlay_with_arucos
        
        start_time = time.time()
        
        # Obtener datos dinámicos del request
        data = request.get_json()
        if data is None:
            return jsonify({
                'ok': False,
                'error': 'No se recibieron datos JSON en el request'
            }), 400
        
        # Extraer parámetros dinámicos
        frame_aruco_id = data.get('frame_aruco_id', 0)
        tool_aruco_id = data.get('tool_aruco_id', 0)
        frame_marker_size = data.get('frame_marker_size_mm', 70.0)
        tool_marker_size = data.get('tool_marker_size_mm', 50.0)
        center_x = data.get('troqueladora_center_x_mm', 0.0)
        center_y = data.get('troqueladora_center_y_mm', 0.0)
        show_frame = data.get('show_frame', True)
        show_tool = data.get('show_tool', True)
        show_center = data.get('show_center', True)
        
        # Obtener frame fresco de la cámara
        print(f"[overlay] Capturando frame fresco de la cámara...")
        cv2_frame = None
        for attempt in range(3):
            cv2_frame = camera_manager.get_frame_raw()
            if cv2_frame is not None:
                print(f"[overlay] ✓ Frame capturado en intento {attempt + 1}")
                break
            else:
                print(f"[overlay] ⚠️ Intento {attempt + 1} falló, reintentando...")
                time.sleep(0.1)
        
        if cv2_frame is None:
            return jsonify({
                'ok': False,
                'error': 'No se pudo capturar un frame fresco de la cámara después de 3 intentos'
            }), 400
        
        # Obtener instancia global de OverlayManager
        overlay_manager = get_global_overlay_manager()
        
        # Usar aruco_manager para toda la lógica específica del proyecto
        result = render_overlay_with_arucos(
            overlay_manager, cv2_frame, frame_aruco_id, tool_aruco_id,
            frame_marker_size, tool_marker_size, center_x, center_y,
            show_frame, show_tool, show_center
        )
        
        if not result['ok']:
            return jsonify({
                'ok': False,
                'error': result['error']
            }), 500
        
        # Convertir imagen a escala de grises y luego a RGB para conservar colores de overlays
        gray_frame = cv2.cvtColor(cv2_frame, cv2.COLOR_BGR2GRAY)
        rgb_background = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2RGB)
        
        # Renderizar overlay sobre fondo en escala de grises
        result_image, view_time = overlay_manager.render(
            background_image=rgb_background,
            renderlist="aruco_overlay",
            view_time=3000
        )
        
        # Convertir a base64
        _, buffer = cv2.imencode('.jpg', result_image, [cv2.IMWRITE_JPEG_QUALITY, 75])
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Guardar frame temporalmente y activar overlay en el dashboard
        global _overlay_frame, _overlay_active_until
        _overlay_frame = buffer.tobytes()
        _overlay_active_until = time.time() + (view_time / 1000.0)
        
        print(f"[overlay] ✓ Overlay mostrado por {view_time/1000:.1f} segundos en dashboard")
        
        total_time = time.time() - start_time
        print(f"[TIMING] ⏱️ /api/overlay/render TOTAL: {total_time:.3f}s")
        
        return jsonify({
            'ok': True,
            'base_detected': result['frame_detected'],
            'tool_detected': result['tool_detected'],
            'total_time_ms': int(total_time * 1000),
            'detection_info': {
                'frame_detected': result['frame_detected'],
                'tool_detected': result['tool_detected'],
                'overlay_objects': result['overlay_objects']
            }
        })
        
    except Exception as e:
        print(f"[overlay] Error en renderizado: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/aruco/save_config', methods=['POST'])
def api_aruco_save_config():
    """Guardar configuración de ArUcos"""
    try:
        # Obtener datos del request
        data = request.get_json()
        if data is None:
            return jsonify({
                'ok': False,
                'error': 'No se recibieron datos JSON en el request'
            }), 400
        
        # Obtener configuración actual
        config = load_config()
        aruco_config = config.get('aruco', {})
        
        # Actualizar configuración con datos del request
        # Configuración Base
        if 'frame_aruco_id' in data:
            aruco_config['base']['reference_id'] = data['frame_aruco_id']
        if 'frame_marker_size_mm' in data:
            aruco_config['base']['marker_size_mm'] = data['frame_marker_size_mm']
        if 'frame_dictionary_id' in data:
            aruco_config['base']['dictionary_id'] = data['frame_dictionary_id']
        if 'frame_marker_bits' in data:
            aruco_config['base']['marker_bits'] = data['frame_marker_bits']
        if 'show_frame' in data:
            aruco_config['base']['show_reference'] = data['show_frame']
            
        # Configuración Tool
        if 'tool_aruco_id' in data:
            aruco_config['tool']['reference_id'] = data['tool_aruco_id']
        if 'tool_marker_size_mm' in data:
            aruco_config['tool']['marker_size_mm'] = data['tool_marker_size_mm']
        if 'tool_dictionary_id' in data:
            aruco_config['tool']['dictionary_id'] = data['tool_dictionary_id']
        if 'tool_marker_bits' in data:
            aruco_config['tool']['marker_bits'] = data['tool_marker_bits']
        if 'show_tool' in data:
            aruco_config['tool']['show_reference'] = data['show_tool']
            
        # Configuración general
        if 'troqueladora_center_x_mm' in data:
            aruco_config['base']['troqueladora_center_x_mm'] = data['troqueladora_center_x_mm']
        if 'troqueladora_center_y_mm' in data:
            aruco_config['base']['troqueladora_center_y_mm'] = data['troqueladora_center_y_mm']
        if 'show_center' in data:
            aruco_config['show_center'] = data['show_center']
        if 'use_saved_reference' in data:
            aruco_config['use_saved_reference'] = data['use_saved_reference']
        
        # Guardar configuración
        config['aruco'] = aruco_config
        save_config(config)
        
        print(f"[aruco] ✓ Configuración de ArUcos guardada:")
        print(f"  - Frame ArUco ID: {aruco_config.get('base', {}).get('reference_id', 0)}")
        print(f"  - Tool ArUco ID: {aruco_config.get('tool', {}).get('reference_id', 0)}")
        print(f"  - Centro troquel: ({aruco_config.get('base', {}).get('troqueladora_center_x_mm', 0)}, {aruco_config.get('base', {}).get('troqueladora_center_y_mm', 0)})mm")
        
        # Configurar ArUcos en el servidor de visión después de guardar
        try:
            from src.vision.vision_manager import configure_aruco_vision_server
            vision_config = config.get('vision', {})
            vision_server_port = vision_config.get('vision_server_port', 8000)
            aruco_result = configure_aruco_vision_server('config.json', vision_server_port)
            if aruco_result.get('ok'):
                print(f"[aruco] ✅ Configuración de ArUcos aplicada en servidor de visión")
            else:
                print(f"[aruco] ⚠️ No se pudo configurar ArUcos en servidor de visión: {aruco_result.get('mensaje', 'Error desconocido')}")
        except Exception as e:
            print(f"[aruco] ⚠️ Error configurando ArUcos en servidor de visión: {e}")
        
        return jsonify({
            'ok': True,
            'message': 'Configuración de ArUcos guardada correctamente',
            'data': {
                'frame_aruco_id': aruco_config.get('base', {}).get('reference_id', 0),
                'tool_aruco_id': aruco_config.get('tool', {}).get('reference_id', 0),
                'troqueladora_center_x_mm': aruco_config.get('base', {}).get('troqueladora_center_x_mm', 0),
                'troqueladora_center_y_mm': aruco_config.get('base', {}).get('troqueladora_center_y_mm', 0)
            }
        })
        
    except Exception as e:
        print(f"[aruco] Error en POST /api/aruco/save_config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

# ============================================================
# API VISION
# ============================================================

@app.route('/api/server_test', methods=['POST'])
def api_server_test():
    """Endpoint para el botón de prueba del Dashboard"""
    try:
        resultado = server_test()
        
        if not resultado.get('ok', False):
            return jsonify(resultado), 500

        print(f"[illinois-server] ✓ server_test completado: {resultado.get('mensaje', 'Sin mensaje')}")
        return jsonify(resultado)

    except Exception as e:
        print(f"[illinois-server] ❌ Error en /api/server_test: {e}")
        return jsonify({
            'ok': False,
            'error': f'Error en server_test: {str(e)}'
        }), 500


# ============================================================
# API MQTT
# ============================================================

@app.route('/api/mqtt_icon_status', methods=['GET'])
def api_mqtt_icon_status():
    """Endpoint para obtener el estado del icono MQTT"""
    try:
        from mqtt_manager import get_mqtt_manager
        
        manager = get_mqtt_manager()
        state = manager.state.value
        connected = manager.connected
        
        # Mapear estado a icono
        icon_map = {
            'disconnected': 'default',
            'connecting': 'waiting',
            'connected': 'success',
            'error': 'error',
            'stopping': 'waiting'
        }
        
        return jsonify({
            'ok': True,
            'status': icon_map.get(state, 'default'),
            'icon': icon_map.get(state, 'default'),
            'connected': connected,
            'state': state
        })
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/vision_icon_status', methods=['GET'])
def api_vision_icon_status():
    """Endpoint para verificar el estado del servidor de visión"""
    try:
        import requests
        
        # Leer IP y puerto desde la configuración
        vision_server_ip = '127.0.0.1'
        vision_server_port = 8000  # Puerto por defecto
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                vision_section = config.get('vision', {})
                vision_server_ip = vision_section.get('vision_server_ip', vision_server_ip)
                vision_server_port = vision_section.get('vision_server_port', vision_server_port)
        except:
            pass  # Usar valores por defecto si no se puede leer la configuración
        
        # Verificar si el servidor de visión está respondiendo
        vision_server_url = f"http://{vision_server_ip}:{vision_server_port}"
        
        try:
            # Hacer una petición simple al servidor de visión con timeout de 2 segundos
            response = requests.get(f"{vision_server_url}/", timeout=2)
            
            if response.status_code == 200:
                return jsonify({
                    'ok': True,
                    'status': 'success',  # Verde - Servidor de visión respondiendo
                    'server_status': 'online',
                    'message': 'Servidor de visión funcionando correctamente',
                    'vision_server_url': vision_server_url,
                    'response_code': response.status_code,
                    'timestamp': time.time()
                })
            else:
                return jsonify({
                    'ok': False,
                    'status': 'error',  # Rojo - Servidor responde pero con error
                    'server_status': 'error',
                    'message': f'Servidor de visión responde con código {response.status_code}',
                    'vision_server_url': vision_server_url,
                    'response_code': response.status_code,
                    'timestamp': time.time()
                })
                
        except requests.exceptions.ConnectTimeout:
            return jsonify({
                'ok': False,
                'status': 'error',  # Rojo - Timeout de conexión
                'server_status': 'offline',
                'message': 'Timeout conectando al servidor de visión',
                'vision_server_url': vision_server_url,
                'timestamp': time.time()
            })
        except requests.exceptions.ConnectionError:
            return jsonify({
                'ok': False,
                'status': 'error',  # Rojo - No se puede conectar
                'server_status': 'offline',
                'message': 'No se puede conectar al servidor de visión',
                'vision_server_url': vision_server_url,
                'timestamp': time.time()
            })
        except Exception as e:
            return jsonify({
                'ok': False,
                'status': 'error',  # Rojo - Error general
                'server_status': 'offline',
                'message': f'Error verificando servidor de visión: {str(e)}',
                'vision_server_url': vision_server_url,
                'timestamp': time.time()
            })
            
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e),
            'status': 'error',
            'server_status': 'offline'
        }), 500

@app.route('/api/robot_hello', methods=['POST'])
def api_robot_hello():
    """Endpoint para enviar comando HOLA al robot COMAU via MQTT"""
    try:
        from mqtt_manager import get_mqtt_manager
        
        # Obtener el manager MQTT
        mqtt_manager = get_mqtt_manager()
        
        print(f"[illinois-server] 🔍 Estado MQTT: connected={mqtt_manager.connected}, state={mqtt_manager.state}")
        
        # Verificar si MQTT está conectado
        if not mqtt_manager.connected:
            print(f"[illinois-server] ❌ MQTT no conectado - estado: {mqtt_manager.state}")
            return jsonify({
                'ok': False,
                'error': 'MQTT no conectado',
                'status': 'error',
                'message': 'No se puede comunicar con el robot - MQTT desconectado'
            }), 500
        
        # Crear comando VerifyInstr para verificar comunicación con el robot
        import time
        import uuid
        
        request_id = f"hello_{int(time.time())}_{str(uuid.uuid4())[:8]}"
        
        command = {
            "command": "VerifyInstr",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "args": {},
            "request_id": request_id
        }
        
        print(f"[illinois-server] 🤖 Enviando comando VerifyInstr al robot (ID: {request_id})")
        print(f"[illinois-server] 📤 Comando: {command}")
        
        # Enviar comando y esperar respuesta
        response = mqtt_manager.send_command_and_wait(command, timeout=10)
        
        print(f"[illinois-server] 📥 Respuesta recibida: {response}")
        
        if response:
            # Procesar respuesta del robot
            if response.get('status') == 'success':
                if response.get('found', False):
                    # Robot responde y tiene "Instr:" - comunicación exitosa
                    return jsonify({
                        'ok': True,
                        'status': 'success',
                        'sequence_id': request_id,
                        'context': f"Instr: encontrado en bloque Drive (addr: {response.get('block_address', 'N/A')})",
                        'message': 'Robot COMAU responde correctamente - Instr: detectado',
                        'robot_status': 'active',
                        'instr_found': True,
                        'block_address': response.get('block_address'),
                        'block_size': response.get('block_size')
                    })
                else:
                    # Robot responde pero no tiene "Instr:" - robot inactivo
                    return jsonify({
                        'ok': True,
                        'status': 'warning',
                        'sequence_id': request_id,
                        'context': response.get('message', 'Bloque Drive no encontrado'),
                        'message': 'Robot COMAU responde pero no está activo - Instr: no detectado',
                        'robot_status': 'inactive',
                        'instr_found': False
                    })
            else:
                # Error en la respuesta del robot
                return jsonify({
                    'ok': True,
                    'status': 'error',
                    'sequence_id': request_id,
                    'context': response.get('error_message', 'Error desconocido'),
                    'message': f"Error del robot: {response.get('error_message', 'Error desconocido')}",
                    'robot_status': 'error',
                    'error_code': response.get('error_code', 'UNKNOWN_ERROR')
                })
        else:
            # No hay respuesta del robot
            return jsonify({
                'ok': True,
                'status': 'error',
                'sequence_id': request_id,
                'context': 'Sin respuesta del robot',
                'message': 'Robot COMAU no responde - timeout o error de comunicación',
                'robot_status': 'no_response'
            })
            
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e),
            'status': 'error',
            'message': f'Error interno: {str(e)}'
        }), 500

@app.route('/api/robot_move_to_home', methods=['POST'])
def api_robot_move_to_home():
    """Endpoint para enviar comando MOVE TO HOME al robot COMAU via MQTT"""
    try:
        # Agregar directorio COMAU al path para importaciones
        comau_path = os.path.join(os.path.dirname(__file__), 'COMAU')
        if comau_path not in sys.path:
            sys.path.insert(0, comau_path)
        from comandos.cmd_move_to_home import move_to_home
        
        print(f"[illinois-server] 🤖 Recibida solicitud MOVE TO HOME")
        
        # Ejecutar comando MOVE TO HOME
        result = move_to_home()
        
        print(f"[illinois-server] 📥 Resultado MOVE TO HOME: {result}")
        
        # Retornar resultado
        if result.get('ok', False):
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        print(f"[illinois-server] ❌ Error en MOVE TO HOME: {str(e)}")
        return jsonify({
            'ok': False,
            'error': str(e),
            'status': 'error',
            'message': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/robot_test_routine', methods=['POST'])
def api_robot_test_routine():
    """Endpoint para enviar comando RUTINA DE PRUEBA al robot COMAU via MQTT"""
    try:
        # Agregar directorio COMAU al path para importaciones
        comau_path = os.path.join(os.path.dirname(__file__), 'COMAU')
        if comau_path not in sys.path:
            sys.path.insert(0, comau_path)
        from comandos.testRoutine import testRoutine
        
        print(f"[illinois-server] 🤖 Recibida solicitud RUTINA DE PRUEBA")
        
        # Ejecutar comando RUTINA DE PRUEBA
        result = testRoutine()
        
        # Log detallado del resultado eliminado para mantener consola limpia
        
        # Retornar resultado
        if result.get('ok', False):
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        print(f"[illinois-server] ❌ Error en RUTINA DE PRUEBA: {str(e)}")
        return jsonify({
            'ok': False,
            'error': str(e),
            'status': 'error',
            'message': f'Error interno: {str(e)}'
        }), 500

@app.route('/api/vision/config', methods=['GET'])
def api_vision_config():
    """Endpoint para obtener la configuración de visión"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        return jsonify({
            'ok': True,
            'vision': config.get('vision', {})
        })
        
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/vision/set_models', methods=['POST'])
def api_vision_set_models():
    """Endpoint para guardar configuración de modelos y visualización"""
    try:
        data = request.get_json()
        
        # Cargar configuración actual
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        # Actualizar configuración de visión
        if 'vision' not in config:
            config['vision'] = {}
            
        # Actualizar campos
        for key, value in data.items():
            config['vision'][key] = value
        
        # Guardar configuración
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({
            'ok': True,
            'message': 'Configuración guardada correctamente'
        })
        
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/vision/set_roi', methods=['POST'])
def api_vision_set_roi():
    """Endpoint para guardar configuración ROI"""
    try:
        data = request.get_json()
        
        # Cargar configuración actual
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        # Actualizar configuración de visión
        if 'vision' not in config:
            config['vision'] = {}
            
        # Actualizar campos ROI
        for key, value in data.items():
            config['vision'][key] = value
        
        # Guardar configuración
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({
            'ok': True,
            'message': 'Configuración ROI guardada correctamente'
        })
        
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/vision_server/configure', methods=['POST'])
def api_vision_server_configure():
    """Endpoint para configurar el servidor de visión con muescas y ROI"""
    try:
        from src.vision.vision_manager import configure_vision_server
        
        data = request.get_json()
        print(f"[illinois-server] 📥 Configuración recibida: {data}")
        
        lista_muescas_mm = data.get('lista_muescas_mm', [])
        roi_rectangulo = data.get('roi_rectangulo', {})
        
        # Leer el puerto desde la configuración
        vision_server_port = 8000  # Puerto por defecto
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                vision_server_port = config.get('vision', {}).get('vision_server_port', 8000)
        except:
            pass  # Usar puerto por defecto si no se puede leer la configuración
        
        print(f"[illinois-server] 🔧 Configurando servidor de visión en puerto {vision_server_port}")
        print(f"[illinois-server] 📍 Muescas: {len(lista_muescas_mm)}")
        print(f"[illinois-server] 📐 ROI: {roi_rectangulo}")
        
        # Llamar a la función de configuración
        resultado = configure_vision_server(
            lista_muescas_mm=lista_muescas_mm,
            roi_rectangulo=roi_rectangulo,
            vision_server_port=vision_server_port
        )
        
        if resultado['ok']:
            print(f"[illinois-server] ✅ Configuración aplicada exitosamente")
            
            # Configurar también las coordenadas de la troqueladora
            try:
                from src.vision.vision_manager import configure_aruco_vision_server
                print(f"[illinois-server] 🔧 Configurando coordenadas de la troqueladora...")
                aruco_result = configure_aruco_vision_server('config.json', vision_server_port)
                if aruco_result.get('ok'):
                    print(f"[illinois-server] ✅ Coordenadas de la troqueladora configuradas")
                else:
                    print(f"[illinois-server] ⚠️ No se pudieron configurar las coordenadas de la troqueladora: {aruco_result.get('mensaje', 'Error desconocido')}")
            except Exception as e:
                print(f"[illinois-server] ⚠️ Error configurando coordenadas de la troqueladora: {e}")
            
            return jsonify({
                'ok': True,
                'message': 'Configuración aplicada correctamente',
                'muescas_count': len(lista_muescas_mm),
                'roi': roi_rectangulo
            })
        else:
            print(f"[illinois-server] ❌ Error aplicando configuración: {resultado['error']}")
            return jsonify({
                'ok': False,
                'error': resultado['error'],
                'message': resultado['mensaje']
            }), 500
            
    except Exception as e:
        print(f"[illinois-server] ❌ Error en configuración del servidor de visión: {e}")
        return jsonify({
            'ok': False,
            'error': str(e),
            'message': 'Error interno del servidor'
        }), 500

@app.route('/api/vision_server/configure_roi', methods=['POST'])
def api_vision_server_configure_roi():
    """Endpoint para configurar ROI en el servidor de visión"""
    try:
        from src.vision.vision_manager import configure_roi_vision_server
        
        # Leer el puerto desde la configuración
        vision_server_port = 8000  # Puerto por defecto
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                vision_server_port = config.get('vision', {}).get('vision_server_port', 8000)
        except:
            pass
        
        # Configurar ROI en el servidor de visión
        result = configure_roi_vision_server('config.json', vision_server_port)
        
        if result.get('ok'):
            print(f"[illinois-server] ✅ Configuración de ROI aplicada en servidor de visión")
            return jsonify({
                'ok': True,
                'message': 'Configuración de ROI aplicada correctamente',
                'data': result.get('config', {})
            })
        else:
            print(f"[illinois-server] ❌ Error configurando ROI: {result.get('mensaje', 'Error desconocido')}")
            return jsonify({
                'ok': False,
                'error': result.get('error', 'Error desconocido'),
                'message': result.get('mensaje', 'Error configurando ROI')
            }), 500
        
    except Exception as e:
        print(f"[illinois-server] ❌ Error en configure_roi: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'ok': False,
            'error': str(e),
            'message': 'Error interno del servidor'
        }), 500

@app.route('/api/vision_server/start', methods=['POST'])
def api_vision_server_start():
    """Endpoint para iniciar el servidor de visión"""
    try:
        import subprocess
        import os
        import signal
        
        data = request.get_json()
        print(f"[illinois-server] 📥 Datos recibidos: {data}")
        
        vision_server_path = data.get('path')
        vision_server_port = data.get('port', 8000)  # Puerto por defecto 8000
        
        # Si no se proporciona path, intentar leer desde config.json
        if not vision_server_path:
            try:
                with open('config.json', 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    vision_server_path = config.get('vision', {}).get('vision_server_path')
                    if not vision_server_port or vision_server_port == 8000:
                        vision_server_port = config.get('vision', {}).get('vision_server_port', 8000)
            except:
                pass
        
        if not vision_server_path:
            print(f"[illinois-server] ❌ No se proporcionó ruta del servidor")
            return jsonify({
                'ok': False,
                'error': 'Ruta del servidor de visión no proporcionada'
            }), 400
        
        # Verificar si el archivo existe
        full_path = os.path.abspath(vision_server_path)
        print(f"[illinois-server] 🔍 Ruta completa: {full_path}")
        print(f"[illinois-server] 🔍 Directorio actual: {os.getcwd()}")
        
        if not os.path.exists(vision_server_path):
            print(f"[illinois-server] ❌ Archivo no encontrado: {vision_server_path}")
            return jsonify({
                'ok': False,
                'error': f'Archivo no encontrado: {vision_server_path}'
            }), 400
        
        print(f"[illinois-server] ✅ Archivo encontrado: {vision_server_path}")
        print(f"[illinois-server] 🚀 Iniciando servidor de visión: {vision_server_path}")
        
        # Iniciar el proceso Python
        try:
            print(f"[illinois-server] 📝 Comando a ejecutar: python {vision_server_path}")
            print(f"[illinois-server] 📁 Directorio de trabajo: {os.getcwd()}")
            
            # Verificar que el archivo existe y es ejecutable
            if not os.path.exists(vision_server_path):
                print(f"[illinois-server] ❌ Archivo no existe: {vision_server_path}")
                return jsonify({
                    'ok': False,
                    'error': f'Archivo no existe: {vision_server_path}'
                }), 400
            
            print(f"[illinois-server] ✅ Archivo existe, iniciando proceso...")
            
            # Obtener el directorio del script de visión
            vision_server_dir = os.path.dirname(os.path.abspath(vision_server_path))
            print(f"[illinois-server] 📁 Directorio del script de visión: {vision_server_dir}")
            
            process = subprocess.Popen(
                ['pythonw', vision_server_path, '-p', str(vision_server_port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=vision_server_dir,  # ← Ejecutar desde el directorio del script
                text=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            
            # Guardar el PID para poder detenerlo después
            global vision_server_process
            vision_server_process = process
            
            print(f"[illinois-server] ✅ Servidor de visión iniciado con PID: {process.pid} en puerto: {vision_server_port}")
            
            # Esperar un poco para que el proceso se inicie
            import time
            time.sleep(1)
            
            # Verificar si el proceso sigue ejecutándose
            if process.poll() is not None:
                print(f"[illinois-server] ❌ El proceso terminó inmediatamente con código: {process.returncode}")
                # Leer la salida para ver el error
                try:
                    stdout, stderr = process.communicate(timeout=1)
                    if stdout:
                        print(f"[illinois-server] 📤 STDOUT: {stdout}")
                    if stderr:
                        print(f"[illinois-server] ❌ STDERR: {stderr}")
                except:
                    pass
                return jsonify({
                    'ok': False,
                    'error': f'El proceso terminó inmediatamente. Código de salida: {process.returncode}'
                }), 500
            else:
                print(f"[illinois-server] ✅ Proceso ejecutándose correctamente (PID: {process.pid})")
            
            # Configurar ArUcos en el servidor de visión después de iniciarlo
            # Esperar un poco más para que el servidor esté completamente listo
            time.sleep(2)
            try:
                from src.vision.vision_manager import configure_aruco_vision_server
                aruco_result = configure_aruco_vision_server('config.json', vision_server_port)
                if aruco_result.get('ok'):
                    print(f"[illinois-server] ✅ Configuración de ArUcos aplicada en servidor de visión")
                else:
                    print(f"[illinois-server] ⚠️ No se pudo configurar ArUcos: {aruco_result.get('mensaje', 'Error desconocido')}")
            except Exception as e:
                print(f"[illinois-server] ⚠️ Error configurando ArUcos: {e}")
            
            return jsonify({
                'ok': True,
                'message': 'Servidor de visión iniciado correctamente',
                'path': vision_server_path,
                'pid': process.pid
            })
            
        except Exception as e:
            return jsonify({
                'ok': False,
                'error': f'Error iniciando proceso: {str(e)}'
            }), 500
        
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/vision_server/stop', methods=['POST'])
def api_vision_server_stop():
    """Endpoint para detener el servidor de visión"""
    try:
        import signal
        
        print(f"[illinois-server] 🛑 Deteniendo servidor de visión")
        
        global vision_server_process
        if vision_server_process and vision_server_process.poll() is None:
            # El proceso está ejecutándose, terminarlo
            try:
                vision_server_process.terminate()
                vision_server_process.wait(timeout=5)  # Esperar hasta 5 segundos
                print(f"[illinois-server] ✅ Servidor de visión detenido (PID: {vision_server_process.pid})")
            except subprocess.TimeoutExpired:
                # Si no termina en 5 segundos, forzar terminación
                vision_server_process.kill()
                vision_server_process.wait()
                print(f"[illinois-server] ⚠️ Servidor de visión forzado a terminar (PID: {vision_server_process.pid})")
            
            vision_server_process = None
            
            return jsonify({
                'ok': True,
                'message': 'Servidor de visión detenido correctamente'
            })
        else:
            return jsonify({
                'ok': True,
                'message': 'Servidor de visión no estaba ejecutándose'
            })
        
    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/mqtt_config', methods=['GET'])
def api_mqtt_config():
    """Endpoint para obtener la configuración MQTT actual"""
    try:
        from mqtt_manager import get_mqtt_manager
        
        manager = get_mqtt_manager()
        config = manager.get_config()
        
        return jsonify({
            'ok': True,
            'config': config
        })
    except Exception as e:
        print(f"[illinois-server] Error en /api/mqtt_config: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/mqtt_test', methods=['POST'])
def api_mqtt_test():
    """Endpoint para probar la conexión con un broker MQTT"""
    try:
        from mqtt_manager import get_mqtt_manager
        
        data = request.get_json()
        broker_ip = data.get('broker_ip')
        broker_port = data.get('broker_port', 1883)
        
        if not broker_ip:
            return jsonify({
                'ok': False,
                'error': 'broker_ip es requerido'
            }), 400
        
        manager = get_mqtt_manager()
        success, message = manager.test_connection(broker_ip, broker_port, timeout=10)
        
        return jsonify({
            'ok': success,
            'message': message
        })
    except Exception as e:
        print(f"[illinois-server] Error en /api/mqtt_test: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/mqtt_save', methods=['POST'])
def api_mqtt_save():
    """Endpoint para guardar la configuración MQTT"""
    try:
        from mqtt_manager import get_mqtt_manager
        
        data = request.get_json()
        broker_ip = data.get('broker_ip')
        broker_port = data.get('broker_port', 1883)
        topic_commands = data.get('topic_commands', 'COMAU/commands')
        topic_keyboard = data.get('topic_keyboard', 'COMAU/toRobot')
        topic_responses = data.get('topic_responses', 'COMAU/memoryData')
        connect_on_start = data.get('connect_on_start', True)
        
        if not broker_ip:
            return jsonify({
                'ok': False,
                'error': 'broker_ip es requerido'
            }), 400
        
        manager = get_mqtt_manager()
        success = manager.save_config(
            broker_ip=broker_ip,
            broker_port=broker_port,
            topic_commands=topic_commands,
            topic_keyboard=topic_keyboard,
            topic_responses=topic_responses,
            connect_on_start=connect_on_start
        )
        
        if success:
            return jsonify({
                'ok': True,
                'message': 'Configuración MQTT guardada correctamente'
            })
        else:
            return jsonify({
                'ok': False,
                'error': 'Error al guardar la configuración'
            }), 500
            
    except Exception as e:
        print(f"[illinois-server] Error en /api/mqtt_save: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/mqtt_init_winc5g', methods=['POST'])
def api_mqtt_init_winc5g():
    """Endpoint para inicializar WinC5G via MQTT"""
    try:
        from mqtt_manager import get_mqtt_manager
        
        data = request.get_json()
        command_data = {
            'command': 'InitWinC5G',
            'timestamp': data.get('timestamp', ''),
            'args': data.get('args', {}),
            'request_id': data.get('request_id', f'init_{int(time.time())}')
        }
        
        manager = get_mqtt_manager()
        
        if not manager.connected:
            return jsonify({
                'ok': False,
                'error': 'No hay conexión MQTT activa'
            }), 400
        
        # Enviar comando y esperar respuesta
        response = manager.send_command_and_wait(command_data, timeout=30)
        
        if response:
            return jsonify({
                'ok': True,
                'status': response.get('status'),
                'message': response.get('message', 'Comando ejecutado'),
                'data': response
            })
        else:
            return jsonify({
                'ok': False,
                'error': 'Timeout esperando respuesta del comando'
            }), 408
            
    except Exception as e:
        print(f"[illinois-server] Error en /api/mqtt_init_winc5g: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

# ============================================================
# API JUNTAS
# ============================================================
def load_juntas():
    """Carga todas las juntas desde juntas.json"""
    if os.path.exists(JUNTAS_FILE):
        try:
            with open(JUNTAS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[juntas] Error cargando juntas: {e}")
    return {'juntas': [], 'selected_id': None}

def save_juntas(data):
    """Guarda juntas en juntas.json"""
    try:
        with open(JUNTAS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[juntas] Error guardando juntas: {e}")
        return False

@app.route('/api/juntas', methods=['GET', 'POST'])
def api_juntas():
    if request.method == 'GET':
        db = load_juntas()
        return jsonify({'ok': True, 'juntas': db.get('juntas', [])})

    elif request.method == 'POST':
        """Crea una nueva junta"""
        try:
            db = load_juntas()
            
            # Obtener datos del formulario
            nombre = request.form.get('nombre')
            if not nombre:
                return jsonify({'ok': False, 'error': 'Nombre es requerido'}), 400
            
            # Generar nuevo ID
            max_id = max([j['id'] for j in db.get('juntas', [])], default=0)
            nuevo_id = max_id + 1
            
            # Crear nueva junta
            nueva_junta = {
                'id': nuevo_id,
                'nombre': nombre,
                'fecha_creacion': datetime.now().isoformat(),
                'cantidad_muescas': 0,
                'muesca_x': 0,
                'muesca_y': 0,
                'muescas_vertical': False,
                'illinois_x': 0,
                'illinois_y': 0,
                'illinois_vertical': False,
                'codigo_x': 0,
                'codigo_y': 0,
                'codigo_vertical': False,
                'lote_x': 0,
                'lote_y': 0,
                'lote_vertical': False,
                'tiene_analisis': False,
                'imagen': None,
                # Nuevos campos para el sistema de parámetros proporcionales
                'parametrizado': False,
                'px_mm': 1.0,
                'parametros_proporcionales': None
            }
            
            # Actualizar datos de muescas
            cantidad_muescas = request.form.get('cantidadMuescas')
            if cantidad_muescas:
                nueva_junta['cantidad_muescas'] = int(cantidad_muescas)
            
            muesca_x = request.form.get('muescaX')
            muesca_y = request.form.get('muescaY')
            muescas_vertical = request.form.get('muescasVertical') == 'true'
            
            if muesca_x:
                nueva_junta['muesca_x'] = float(muesca_x)
            if muesca_y:
                nueva_junta['muesca_y'] = float(muesca_y)
            nueva_junta['muescas_vertical'] = muescas_vertical
            
            # Actualizar array centros_muescas basado en muesca_x, muesca_y y cantidad_muescas
            cantidad_muescas = nueva_junta.get('cantidad_muescas', 0)
            if cantidad_muescas > 0 and muesca_x and muesca_y:
                separacion = 7.0  # 7mm de separación entre muescas
                centros_muescas = []
                for i in range(cantidad_muescas):
                    if muescas_vertical:
                        # Muescas verticales: misma X, Y incrementa
                        centro_x = float(muesca_x)
                        centro_y = float(muesca_y) + (i * separacion)
                    else:
                        # Muescas horizontales: misma Y, X incrementa
                        centro_x = float(muesca_x) + (i * separacion)
                        centro_y = float(muesca_y)
                    centros_muescas.append({
                        'id': i + 1,
                        'centro_mm': [centro_x, centro_y]
                    })
                nueva_junta['centros_muescas'] = centros_muescas
                print(f"[juntas] ✓ Creado centros_muescas: {len(centros_muescas)} muescas")
            
            # Actualizar datos de ILLINOIS
            illinois_x = request.form.get('illinoisX')
            illinois_y = request.form.get('illinoisY')
            illinois_vertical = request.form.get('illinoisVertical') == 'true'
            
            if illinois_x:
                nueva_junta['illinois_x'] = float(illinois_x)
            if illinois_y:
                nueva_junta['illinois_y'] = float(illinois_y)
            nueva_junta['illinois_vertical'] = illinois_vertical
            
            # Actualizar datos de Código
            codigo_x = request.form.get('codigoX')
            codigo_y = request.form.get('codigoY')
            codigo_vertical = request.form.get('codigoVertical') == 'true'
            
            if codigo_x:
                nueva_junta['codigo_x'] = float(codigo_x)
            if codigo_y:
                nueva_junta['codigo_y'] = float(codigo_y)
            nueva_junta['codigo_vertical'] = codigo_vertical
            
            # Actualizar datos de Lote
            lote_x = request.form.get('loteX')
            lote_y = request.form.get('loteY')
            lote_vertical = request.form.get('loteVertical') == 'true'
            
            if lote_x:
                nueva_junta['lote_x'] = float(lote_x)
            if lote_y:
                nueva_junta['lote_y'] = float(lote_y)
            nueva_junta['lote_vertical'] = lote_vertical
            
            # Guardar imagen si se proporciona
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file.filename != '':
                    # Crear directorio si no existe
                    os.makedirs('imagenes_juntas', exist_ok=True)
                    
                    # Guardar imagen
                    filename = f"{nombre}.jpg"
                    filepath = os.path.join('imagenes_juntas', filename)
                    file.save(filepath)
                    nueva_junta['imagen'] = filename
            
            # Actualizar análisis si se proporciona
            analisis_json = request.form.get('analisis')
            if analisis_json:
                try:
                    analisis_data = json.loads(analisis_json)
                    nueva_junta['tiene_analisis'] = True
                    
                    # Guardar análisis en archivo
                    analisis_filename = f"{nombre}_analisis.json"
                    analisis_path = get_junta_path(nombre, analisis_filename)
                    os.makedirs(os.path.dirname(analisis_path), exist_ok=True)
                    
                    with open(analisis_path, 'w', encoding='utf-8') as f:
                        json.dump(analisis_data, f, indent=2, ensure_ascii=False)
                    
                    # Actualizar resumen de análisis
                    if 'agujeros' in analisis_data:
                        agujeros = analisis_data['agujeros']
                        redondos_grandes = sum(1 for a in agujeros if a.get('clasificacion') == 'Redondo Grande')
                        redondos_chicos = sum(1 for a in agujeros if a.get('clasificacion') == 'Redondo Chico')
                        irregulares = sum(1 for a in agujeros if a.get('clasificacion') == 'Irregular')
                        
                        nueva_junta['resumen_analisis'] = {
                            'total_agujeros': len(agujeros),
                            'redondos_grandes': redondos_grandes,
                            'redondos_chicos': redondos_chicos,
                            'irregulares': irregulares
                        }
                    
                    # Actualizar escala si está disponible
                    if 'parametros' in analisis_data and 'mm_por_pixel' in analisis_data['parametros']:
                        nueva_junta['mm_por_pixel'] = analisis_data['parametros']['mm_por_pixel']
                    
                except json.JSONDecodeError:
                    print(f"[juntas] Error decodificando análisis JSON")
            
            # Agregar a la base de datos
            if 'juntas' not in db:
                db['juntas'] = []
            db['juntas'].append(nueva_junta)
            
            # Guardar cambios
            if save_juntas(db):
                print(f"[juntas] ✓ Nueva junta creada: {nombre} (ID: {nuevo_id})")
                return jsonify({
                    'ok': True,
                    'message': 'Junta creada correctamente',
                    'junta': nueva_junta
                })
            else:
                return jsonify({'ok': False, 'error': 'Error guardando cambios'}), 500
                
        except Exception as e:
            print(f"[juntas] Error creando junta: {e}")
            return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/juntas/<int:junta_id>', methods=['GET', 'PUT', 'DELETE'])
def api_junta(junta_id):
    if request.method == 'GET':
        db = load_juntas()
        junta = next((j for j in db.get('juntas', []) if j['id'] == junta_id), None)
        if junta:
            return jsonify({'ok': True, 'junta': junta})
        return jsonify({'ok': False, 'error': 'Junta no encontrada'}), 404
    
    elif request.method == 'PUT':
        """Actualiza una junta existente"""
        try:
            db = load_juntas()
            junta = next((j for j in db.get('juntas', []) if j['id'] == junta_id), None)
            if not junta:
                return jsonify({'ok': False, 'error': 'Junta no encontrada'}), 404
            
            # Obtener datos del formulario
            nombre = request.form.get('nombre')
            if not nombre:
                return jsonify({'ok': False, 'error': 'Nombre es requerido'}), 400
            
            # Actualizar datos básicos
            junta['nombre'] = nombre
            junta['fecha_modificacion'] = datetime.now().isoformat()
            
            # Actualizar datos de muescas
            cantidad_muescas = request.form.get('cantidadMuescas')
            if cantidad_muescas:
                junta['cantidad_muescas'] = int(cantidad_muescas)
            
            muesca_x = request.form.get('muescaX')
            muesca_y = request.form.get('muescaY')
            muescas_vertical = request.form.get('muescasVertical') == 'true'
            
            if muesca_x:
                junta['muesca_x'] = float(muesca_x)
            if muesca_y:
                junta['muesca_y'] = float(muesca_y)
            junta['muescas_vertical'] = muescas_vertical
            
            # Actualizar array centros_muescas basado en muesca_x, muesca_y y cantidad_muescas
            cantidad_muescas = junta.get('cantidad_muescas', 0)
            if cantidad_muescas > 0 and muesca_x and muesca_y:
                separacion = 7.0  # 7mm de separación entre muescas
                centros_muescas = []
                for i in range(cantidad_muescas):
                    if muescas_vertical:
                        # Muescas verticales: misma X, Y incrementa
                        centro_x = float(muesca_x)
                        centro_y = float(muesca_y) + (i * separacion)
                    else:
                        # Muescas horizontales: misma Y, X incrementa
                        centro_x = float(muesca_x) + (i * separacion)
                        centro_y = float(muesca_y)
                    centros_muescas.append({
                        'id': i + 1,
                        'centro_mm': [centro_x, centro_y]
                    })
                junta['centros_muescas'] = centros_muescas
                print(f"[juntas] ✓ Actualizado centros_muescas: {len(centros_muescas)} muescas")
            
            # Actualizar datos de ILLINOIS
            illinois_x = request.form.get('illinoisX')
            illinois_y = request.form.get('illinoisY')
            illinois_vertical = request.form.get('illinoisVertical') == 'true'
            
            if illinois_x:
                junta['illinois_x'] = float(illinois_x)
            if illinois_y:
                junta['illinois_y'] = float(illinois_y)
            junta['illinois_vertical'] = illinois_vertical
            
            # Actualizar datos de Código
            codigo_x = request.form.get('codigoX')
            codigo_y = request.form.get('codigoY')
            codigo_vertical = request.form.get('codigoVertical') == 'true'
            
            if codigo_x:
                junta['codigo_x'] = float(codigo_x)
            if codigo_y:
                junta['codigo_y'] = float(codigo_y)
            junta['codigo_vertical'] = codigo_vertical
            
            # Actualizar datos de Lote
            lote_x = request.form.get('loteX')
            lote_y = request.form.get('loteY')
            lote_vertical = request.form.get('loteVertical') == 'true'
            
            if lote_x:
                junta['lote_x'] = float(lote_x)
            if lote_y:
                junta['lote_y'] = float(lote_y)
            junta['lote_vertical'] = lote_vertical
            
            # Actualizar imagen si se proporciona
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file.filename != '':
                    # Guardar nueva imagen
                    filename = f"{nombre}.jpg"
                    filepath = os.path.join('imagenes_juntas', filename)
                    file.save(filepath)
                    junta['imagen'] = filename
            
            # Actualizar análisis si se proporciona
            analisis_json = request.form.get('analisis')
            if analisis_json:
                try:
                    analisis_data = json.loads(analisis_json)
                    junta['tiene_analisis'] = True
                    
                    # Guardar análisis en archivo
                    analisis_filename = f"{nombre}_analisis.json"
                    analisis_path = get_junta_path(nombre, analisis_filename)
                    os.makedirs(os.path.dirname(analisis_path), exist_ok=True)
                    
                    with open(analisis_path, 'w', encoding='utf-8') as f:
                        json.dump(analisis_data, f, indent=2, ensure_ascii=False)
                    
                    # Actualizar resumen de análisis
                    if 'agujeros' in analisis_data:
                        agujeros = analisis_data['agujeros']
                        redondos_grandes = sum(1 for a in agujeros if a.get('clasificacion') == 'Redondo Grande')
                        redondos_chicos = sum(1 for a in agujeros if a.get('clasificacion') == 'Redondo Chico')
                        irregulares = sum(1 for a in agujeros if a.get('clasificacion') == 'Irregular')
                        
                        junta['resumen_analisis'] = {
                            'total_agujeros': len(agujeros),
                            'redondos_grandes': redondos_grandes,
                            'redondos_chicos': redondos_chicos,
                            'irregulares': irregulares
                        }
                    
                    # Actualizar escala si está disponible
                    if 'parametros' in analisis_data and 'mm_por_pixel' in analisis_data['parametros']:
                        junta['mm_por_pixel'] = analisis_data['parametros']['mm_por_pixel']
                    
                except json.JSONDecodeError:
                    print(f"[juntas] Error decodificando análisis JSON")
            
            # Actualizar px_mm y parametros_proporcionales si se proporcionan
            px_mm_str = request.form.get('px_mm')
            if px_mm_str:
                try:
                    junta['px_mm'] = float(px_mm_str)
                    print(f"[juntas] px_mm actualizado: {junta['px_mm']}")
                except ValueError:
                    print(f"[juntas] ⚠️ Error convirtiendo px_mm: {px_mm_str}")
            
            parametros_proporcionales_str = request.form.get('parametros_proporcionales')
            if parametros_proporcionales_str:
                try:
                    junta['parametros_proporcionales'] = json.loads(parametros_proporcionales_str)
                    print(f"[juntas] parametros_proporcionales actualizados")
                except json.JSONDecodeError:
                    print(f"[juntas] ⚠️ Error decodificando parametros_proporcionales JSON")
            
            # Marcar como parametrizada si tiene px_mm y parametros_proporcionales
            if 'px_mm' in junta and 'parametros_proporcionales' in junta and junta['parametros_proporcionales']:
                junta['parametrizado'] = True
            
            # Generar y guardar imagen con overlay (muescas y labels)
            try:
                import cv2
                import numpy as np
                from muescas_renderer import dibujar_muescas, calcular_punto_medio_segmento
                from textos_renderer import dibujar_texto_simple
                
                # Cargar imagen original
                imagen_path = get_junta_path(junta['nombre'], junta['imagen'])
                print(f"[juntas] Intentando cargar imagen desde: {imagen_path}")
                
                if os.path.exists(imagen_path):
                    img_bgr = cv2.imread(imagen_path)
                    if img_bgr is not None:
                        print(f"[juntas] ✓ Imagen cargada correctamente: {img_bgr.shape}")
                        # Usar la imagen original (BGR) para el overlay
                        img_con_overlay = img_bgr.copy()
                        
                        # Cargar análisis para obtener punto de referencia
                        analisis_filename = f"{nombre}_analisis.json"
                        analisis_path = get_junta_path(nombre, analisis_filename)
                        print(f"[juntas] Intentando cargar análisis desde: {analisis_path}")
                        
                        if os.path.exists(analisis_path):
                            with open(analisis_path, 'r', encoding='utf-8') as f:
                                analisis_data = json.load(f)
                            
                            if analisis_data.get('linea_referencia'):
                                # Calcular punto medio del segmento rojo (origen)
                                punto_medio = analisis_data['linea_referencia']['punto_medio_px']
                                origen_x = int(punto_medio[0])
                                origen_y = int(punto_medio[1])
                                print(f"[juntas] Punto medio del segmento: ({origen_x}, {origen_y})")
                                
                                # Obtener escala: usar px_mm de la junta si está disponible, sino usar mm_por_pixel del análisis
                                # px_mm es píxeles por milímetro, necesitamos convertir a mm_por_pixel (milímetros por píxel)
                                if 'px_mm' in junta and junta['px_mm'] > 0:
                                    mm_por_pixel = 1.0 / junta['px_mm']
                                    print(f"[juntas] Usando px_mm de la junta ({junta['px_mm']}) para overlay: {mm_por_pixel:.6f} mm/px")
                                else:
                                    mm_por_pixel = analisis_data.get('parametros', {}).get('mm_por_pixel', 0.1)
                                    print(f"[juntas] Usando mm_por_pixel del análisis para overlay: {mm_por_pixel}")
                                
                                # Dibujar muescas si hay datos
                                cantidad_muescas = junta.get('cantidad_muescas', 0)
                                if cantidad_muescas > 0:
                                    muesca_x = junta.get('muesca_x', 0)
                                    muesca_y = junta.get('muesca_y', 0)
                                    vertical = junta.get('muescas_vertical', False)
                                    
                                    print(f"[juntas] Dibujando {cantidad_muescas} muescas en ({muesca_x}, {muesca_y}) mm, vertical: {vertical}")
                                    img_con_overlay = dibujar_muescas(
                                        img_con_overlay, 
                                        cantidad_muescas, muesca_x, muesca_y,
                                        (origen_x, origen_y), mm_por_pixel, vertical
                                    )
                                else:
                                    print(f"[juntas] No hay muescas para dibujar (cantidad_muescas = {cantidad_muescas})")
                                
                                # Dibujar textos si hay datos
                                textos = []
                                
                                # ILLINOIS
                                illinois_x = junta.get('illinois_x', 0)
                                illinois_y = junta.get('illinois_y', 0)
                                if illinois_x != 0 or illinois_y != 0:
                                    textos.append({
                                        'texto': 'ILLINOIS',
                                        'x': illinois_x,
                                        'y': illinois_y,
                                        'vertical': junta.get('illinois_vertical', False)
                                    })
                                
                                # Código
                                codigo_x = junta.get('codigo_x', 0)
                                codigo_y = junta.get('codigo_y', 0)
                                if codigo_x != 0 or codigo_y != 0:
                                    textos.append({
                                        'texto': '123456',
                                        'x': codigo_x,
                                        'y': codigo_y,
                                        'vertical': junta.get('codigo_vertical', False)
                                    })
                                
                                # Lote
                                lote_x = junta.get('lote_x', 0)
                                lote_y = junta.get('lote_y', 0)
                                if lote_x != 0 or lote_y != 0:
                                    textos.append({
                                        'texto': '23-45',
                                        'x': lote_x,
                                        'y': lote_y,
                                        'vertical': junta.get('lote_vertical', False)
                                    })
                                
                                # Dibujar todos los textos
                                print(f"[juntas] Dibujando {len(textos)} textos")
                                for texto_data in textos:
                                    print(f"[juntas]   - {texto_data['texto']} en ({texto_data['x']}, {texto_data['y']}) mm")
                                    img_con_overlay = dibujar_texto_simple(
                                        img_con_overlay,
                                        texto_data['texto'], 
                                        texto_data['x'], 
                                        texto_data['y'], 
                                        (origen_x, origen_y), 
                                        mm_por_pixel, 
                                        texto_data['vertical']
                                    )
                                
                                # Guardar imagen con overlay (para control.html)
                                overlay_filename = f"{nombre}_overlay.jpg"
                                overlay_path = get_junta_path(nombre, overlay_filename)
                                os.makedirs(os.path.dirname(overlay_path), exist_ok=True)
                                cv2.imwrite(overlay_path, img_con_overlay)
                                print(f"[juntas] ✓ Imagen con overlay guardada: {overlay_path}")
                                
                                # NO actualizar la referencia de la imagen - mantener la imagen original para junta.html
                                print(f"[juntas] ✓ Imagen original mantenida: {junta['imagen']}")
                                print(f"[juntas] ✓ Overlay guardado para control.html: {overlay_filename}")
                            else:
                                print(f"[juntas] ⚠️ No se encontró línea_referencia en el análisis")
                        else:
                            print(f"[juntas] ⚠️ Archivo de análisis no encontrado: {analisis_path}")
                    else:
                        print(f"[juntas] ⚠️ No se pudo cargar la imagen desde: {imagen_path}")
                else:
                    print(f"[juntas] ⚠️ Archivo de imagen no encontrado: {imagen_path}")
                        
            except Exception as e:
                print(f"[juntas] ⚠️ Error generando imagen con overlay: {e}")
            
            # Procesar imagen de overlay enviada desde el frontend
            if 'imagen_overlay' in request.files:
                try:
                    overlay_file = request.files['imagen_overlay']
                    if overlay_file and overlay_file.filename:
                        # Guardar imagen de overlay
                        overlay_filename = f"{nombre}_overlay.jpg"
                        overlay_path = get_junta_path(nombre, overlay_filename)
                        os.makedirs(os.path.dirname(overlay_path), exist_ok=True)
                        overlay_file.save(overlay_path)
                        print(f"[juntas] ✓ Imagen de overlay guardada desde frontend: {overlay_path}")
                except Exception as e:
                    print(f"[juntas] ⚠️ Error guardando imagen de overlay: {e}")
            
            # Guardar cambios
            if save_juntas(db):
                print(f"[juntas] ✓ Junta {junta_id} actualizada: {nombre}")
                return jsonify({
                    'ok': True,
                    'message': 'Junta actualizada correctamente',
                    'junta': junta
                })
            else:
                return jsonify({'ok': False, 'error': 'Error guardando cambios'}), 500
                
        except Exception as e:
            print(f"[juntas] Error actualizando junta {junta_id}: {e}")
            return jsonify({'ok': False, 'error': str(e)}), 500
    
    elif request.method == 'DELETE':
        """Elimina una junta existente"""
        try:
            db = load_juntas()
            juntas = db.get('juntas', [])
            junta = next((j for j in juntas if j['id'] == junta_id), None)
            
            if not junta:
                return jsonify({'ok': False, 'error': 'Junta no encontrada'}), 404
            
            # Eliminar archivos asociados si existen
            nombre = junta.get('nombre', '')
            if nombre:
                # Eliminar imagen de la junta
                imagen_path = os.path.join('imagenes_juntas', f"{nombre}.jpg")
                if os.path.exists(imagen_path):
                    try:
                        os.remove(imagen_path)
                        print(f"[juntas] Imagen eliminada: {imagen_path}")
                    except Exception as e:
                        print(f"[juntas] ⚠️ Error eliminando imagen: {e}")
                
                # Eliminar archivos de análisis
                analisis_path = get_junta_path(nombre, f"{nombre}_analisis.json")
                if os.path.exists(analisis_path):
                    try:
                        os.remove(analisis_path)
                        print(f"[juntas] Archivo de análisis eliminado: {analisis_path}")
                    except Exception as e:
                        print(f"[juntas] ⚠️ Error eliminando archivo de análisis: {e}")
                
                visualizacion_path = get_junta_path(nombre, f"{nombre}_visualizacion.jpg")
                if os.path.exists(visualizacion_path):
                    try:
                        os.remove(visualizacion_path)
                        print(f"[juntas] Visualización eliminada: {visualizacion_path}")
                    except Exception as e:
                        print(f"[juntas] ⚠️ Error eliminando visualización: {e}")
            
            # Eliminar la junta de la lista
            juntas = [j for j in juntas if j['id'] != junta_id]
            db['juntas'] = juntas
            
            # Si la junta eliminada era la seleccionada, limpiar selected_id
            if db.get('selected_id') == junta_id:
                db['selected_id'] = None
            
            # Guardar cambios
            if save_juntas(db):
                return jsonify({'ok': True, 'message': 'Junta eliminada correctamente'})
            else:
                return jsonify({'ok': False, 'error': 'Error guardando cambios'}), 500
                
        except Exception as e:
            print(f"[juntas] Error eliminando junta {junta_id}: {e}")
            return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/juntas/selected', methods=['GET'])
def api_get_selected_junta():
    """Obtiene la junta actualmente seleccionada."""
    print("\n[SERVER] GET /api/juntas/selected - Solicitud recibida.")
    try:
        db = load_juntas()
        selected_id = db.get('selected_id')
        
        print(f"[SERVER] ID seleccionado en juntas.json: {selected_id}")

        if selected_id is None:
            print("[SERVER] ❌ Error: No hay 'selected_id' en juntas.json.")
            return jsonify({'ok': False, 'error': 'No hay junta seleccionada'}), 404
        
        junta = next((j for j in db.get('juntas', []) if j['id'] == selected_id), None)
        
        if junta:
            print(f"[SERVER] ✓ Junta encontrada: ID={junta['id']}, Nombre='{junta['nombre']}'")
            return jsonify({'ok': True, 'junta': junta})
        else:
            print(f"[SERVER] ❌ Error: Junta con ID {selected_id} no encontrada en la lista de juntas.")
            return jsonify({'ok': False, 'error': f'Junta con ID {selected_id} no encontrada'}), 404
    except Exception as e:
        print(f"[SERVER] ❌ Excepción en api_get_selected_junta: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/juntas/select', methods=['POST'])
def api_select_junta():
    """Selecciona una junta por su ID."""
    data = request.get_json()
    junta_id = data.get('id')
    if junta_id is None:
        return jsonify({'ok': False, 'error': 'Falta el ID de la junta'}), 400
    
    try:
        db = load_juntas()
        # Verificar que la junta exista
        if not any(j['id'] == junta_id for j in db.get('juntas', [])):
            return jsonify({'ok': False, 'error': f'Junta con ID {junta_id} no existe'}), 404
            
        db['selected_id'] = junta_id
        save_juntas(db)
        print(f"✓ Junta seleccionada cambiada a ID: {junta_id}")
        return jsonify({'ok': True, 'message': f'Junta {junta_id} seleccionada'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/juntas/<int:junta_id>/analisis', methods=['GET'])
def api_get_junta_analisis(junta_id):
    """Obtiene el archivo de análisis detallado de una junta."""
    db = load_juntas()
    junta = next((j for j in db.get('juntas', []) if j['id'] == junta_id), None)
    if not junta:
        return jsonify({'ok': False, 'error': 'Junta no encontrada'}), 404

    analisis_filename = f"{junta['nombre']}_analisis.json"
    analisis_path = get_junta_path(junta['nombre'], analisis_filename)

    if not os.path.exists(analisis_path):
        return jsonify({'ok': False, 'error': 'Archivo de análisis no encontrado'}), 404

    try:
        with open(analisis_path, 'r', encoding='utf-8') as f:
            analisis_data = json.load(f)
        return jsonify({'ok': True, 'analisis': analisis_data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/juntas/parametrizar', methods=['POST'])
def api_juntas_parametrizar():
    """Procesa una imagen de junta y genera análisis completo"""
    try:
        import cv2
        import numpy as np
        from contornos_analyzer_fixed import analizar_imagen_completa, crear_visualizacion
        
        # Obtener datos del formulario
        nombre_junta = request.form.get('nombre_junta')
        junta_id = request.form.get('junta_id')
        mm_por_pixel_manual = request.form.get('mm_por_pixel_manual')
        
        # Obtener archivo de imagen
        if 'imagen' not in request.files:
            return jsonify({'ok': False, 'error': 'No se proporcionó imagen'}), 400
        
        file = request.files['imagen']
        if file.filename == '':
            return jsonify({'ok': False, 'error': 'No se seleccionó archivo'}), 400
        
        # Leer imagen
        file_bytes = file.read()
        nparr = np.frombuffer(file_bytes, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img_bgr is None:
            return jsonify({'ok': False, 'error': 'No se pudo decodificar la imagen'}), 400
        
        # Convertir a escala de grises
        img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        
        # Usar escala manual si se proporciona
        mm_por_pixel = 0.1  # Default
        if mm_por_pixel_manual:
            try:
                mm_por_pixel = float(mm_por_pixel_manual)
            except ValueError:
                pass
        
        print(f"[juntas] Procesando imagen para junta: {nombre_junta}")
        print(f"[juntas] Escala: {mm_por_pixel} mm/px")
        
        # Detectar fondo y preparar imagen para análisis
        pixeles_claros = np.sum(img_gray > 127)
        pixeles_oscuros = np.sum(img_gray <= 127)
        
        if pixeles_oscuros > pixeles_claros:
            print(f"[juntas] Fondo OSCURO - invirtiendo para obtener fondo blanco")
            img_para_analisis = 255 - img_gray
            imagen_fondo_negro = img_gray
            imagen_fondo_blanco = 255 - img_gray
        else:
            print(f"[juntas] Fondo CLARO - usando imagen original (ya tiene fondo blanco)")
            img_para_analisis = img_gray
            imagen_fondo_negro = 255 - img_gray
            imagen_fondo_blanco = img_gray
        
        # Analizar imagen
        analisis = analizar_imagen_completa(img_para_analisis, mm_por_pixel, verbose=True)
        
        if not analisis.get('ok'):
            return jsonify({'ok': False, 'error': analisis.get('error', 'Error en análisis')}), 500
        
        # Crear visualización
        img_visualizacion = crear_visualizacion(img_para_analisis, analisis)
        
        # Convertir imágenes a base64
        _, buffer_negro = cv2.imencode('.jpg', imagen_fondo_negro)
        imagen_fondo_negro_b64 = base64.b64encode(buffer_negro).decode('utf-8')
        
        _, buffer_blanco = cv2.imencode('.jpg', imagen_fondo_blanco)
        imagen_fondo_blanco_b64 = base64.b64encode(buffer_blanco).decode('utf-8')
        
        imagen_visualizacion = None
        if img_visualizacion is not None:
            _, buffer_vis = cv2.imencode('.jpg', img_visualizacion)
            imagen_visualizacion = base64.b64encode(buffer_vis).decode('utf-8')
        
        # Guardar análisis si se proporciona ID de junta
        if junta_id and nombre_junta:
            try:
                analisis_filename = f"{nombre_junta}_analisis.json"
                analisis_path = get_junta_path(nombre_junta, analisis_filename)
                
                # Crear directorio si no existe
                os.makedirs(os.path.dirname(analisis_path), exist_ok=True)
                
                # Guardar análisis (sin datos de visualización)
                analisis_para_guardar = analisis.copy()
                if '_visualization_data' in analisis_para_guardar:
                    del analisis_para_guardar['_visualization_data']
                
                with open(analisis_path, 'w', encoding='utf-8') as f:
                    json.dump(analisis_para_guardar, f, indent=2, ensure_ascii=False)
                
                # Guardar visualización
                if img_visualizacion is not None:
                    vis_filename = f"{nombre_junta}_visualizacion.jpg"
                    vis_path = get_junta_path(nombre_junta, vis_filename)
                    cv2.imwrite(vis_path, img_visualizacion)
                
                print(f"[juntas] ✓ Análisis guardado: {analisis_path}")
                
            except Exception as e:
                print(f"[juntas] ⚠️ Error guardando análisis: {e}")
        
        # Crear una copia del análisis sin datos de visualización para JSON
        analisis_serializable = analisis.copy()
        if '_visualization_data' in analisis_serializable:
            del analisis_serializable['_visualization_data']
        
        return jsonify({
            'ok': True,
            'imagen_fondo_negro': imagen_fondo_negro_b64,
            'imagen_fondo_blanco': imagen_fondo_blanco_b64,
            'imagen_visualizacion': imagen_visualizacion,
            'analisis': analisis_serializable,
            'fondo_detectado': True
        })
        
    except Exception as e:
        print(f"[juntas] Error en parametrizar: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/juntas/visualizar', methods=['POST'])
def api_juntas_visualizar():
    """Genera imagen de visualización con overlays"""
    try:
        import cv2
        import numpy as np
        from contornos_analyzer import crear_visualizacion
        
        data = request.get_json()
        imagen_fondo_blanco = data.get('imagen_fondo_blanco')
        analisis = data.get('analisis')
        
        if not imagen_fondo_blanco or not analisis:
            return jsonify({'ok': False, 'error': 'Datos incompletos'}), 400
        
        # Decodificar imagen
        img_bytes = base64.b64decode(imagen_fondo_blanco)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img_gray = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        if img_gray is None:
            return jsonify({'ok': False, 'error': 'No se pudo decodificar la imagen'}), 400
        
        # Crear visualización
        img_visualizacion = crear_visualizacion(img_gray, analisis)
        
        if img_visualizacion is None:
            return jsonify({'ok': False, 'error': 'No se pudo crear la visualización'}), 500
        
        # Convertir a base64
        _, buffer = cv2.imencode('.jpg', img_visualizacion)
        imagen_visualizacion = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'ok': True,
            'imagen_visualizacion': imagen_visualizacion
        })
        
    except Exception as e:
        print(f"[juntas] Error en visualizar: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/juntas/<int:junta_id>/imagen_con_muescas', methods=['GET', 'POST'])
def api_juntas_imagen_con_muescas(junta_id):
    """Genera imagen con muescas y textos dibujados"""
    try:
        import cv2
        import numpy as np
        from muescas_renderer import dibujar_muescas, calcular_punto_medio_segmento
        from textos_renderer import dibujar_texto_simple
        
        # Obtener datos de la junta
        db = load_juntas()
        junta = next((j for j in db.get('juntas', []) if j['id'] == junta_id), None)
        if not junta:
            return jsonify({'ok': False, 'error': 'Junta no encontrada'}), 404
        
        # Cargar análisis
        analisis_filename = f"{junta['nombre']}_analisis.json"
        analisis_path = get_junta_path(junta['nombre'], analisis_filename)
        
        if not os.path.exists(analisis_path):
            return jsonify({'ok': False, 'error': 'Análisis no encontrado'}), 404
        
        with open(analisis_path, 'r', encoding='utf-8') as f:
            analisis_data = json.load(f)
        
        # Obtener parámetros
        if request.method == 'POST':
            # Parámetros personalizados del request
            data = request.get_json()
            cantidad_muescas = data.get('cantidad_muescas', 0)
            muesca_x = data.get('muesca_x', 0)
            muesca_y = data.get('muesca_y', 0)
            vertical = data.get('vertical', False)
            illinois_x = data.get('illinois_x', 0)
            illinois_y = data.get('illinois_y', 0)
            illinois_vertical = data.get('illinois_vertical', False)
            codigo_x = data.get('codigo_x', 0)
            codigo_y = data.get('codigo_y', 0)
            codigo_vertical = data.get('codigo_vertical', False)
            lote_x = data.get('lote_x', 0)
            lote_y = data.get('lote_y', 0)
            lote_vertical = data.get('lote_vertical', False)
        else:
            # Parámetros de la base de datos
            cantidad_muescas = junta.get('cantidad_muescas', 0)
            muesca_x = junta.get('muesca_x', 0)
            muesca_y = junta.get('muesca_y', 0)
            vertical = junta.get('muescas_vertical', False)
            illinois_x = junta.get('illinois_x', 0)
            illinois_y = junta.get('illinois_y', 0)
            illinois_vertical = junta.get('illinois_vertical', False)
            codigo_x = junta.get('codigo_x', 0)
            codigo_y = junta.get('codigo_y', 0)
            codigo_vertical = junta.get('codigo_vertical', False)
            lote_x = junta.get('lote_x', 0)
            lote_y = junta.get('lote_y', 0)
            lote_vertical = junta.get('lote_vertical', False)
        
        # Cargar imagen original
        imagen_filename = junta.get('imagen')
        if not imagen_filename:
            return jsonify({'ok': False, 'error': 'No hay imagen asociada'}), 404
        
        # Usar solo la carpeta juntas_analisis
        img_path = get_junta_path(junta['nombre'], imagen_filename)
        
        if not os.path.exists(img_path):
            return jsonify({'ok': False, 'error': 'Imagen no encontrada'}), 404
        
        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            return jsonify({'ok': False, 'error': 'No se pudo cargar la imagen'}), 500
        
        # Obtener punto medio del segmento
        punto_medio = calcular_punto_medio_segmento(analisis_data)
        if not punto_medio:
            return jsonify({'ok': False, 'error': 'No se encontró punto medio del segmento'}), 500
        
        # Obtener escala: usar px_mm de la junta si está disponible, sino usar mm_por_pixel del análisis
        # px_mm es píxeles por milímetro, necesitamos convertir a mm_por_pixel (milímetros por píxel)
        if 'px_mm' in junta and junta['px_mm'] > 0:
            mm_por_pixel = 1.0 / junta['px_mm']
            print(f"[juntas] imagen_con_muescas: Usando px_mm de la junta ({junta['px_mm']}) → {mm_por_pixel:.6f} mm/px")
        else:
            mm_por_pixel = analisis_data.get('parametros', {}).get('mm_por_pixel', 0.1)
            print(f"[juntas] imagen_con_muescas: Usando mm_por_pixel del análisis: {mm_por_pixel}")
        
        # Dibujar muescas
        if cantidad_muescas > 0:
            img_bgr = dibujar_muescas(
                img_bgr, cantidad_muescas, muesca_x, muesca_y,
                punto_medio, mm_por_pixel, vertical
            )
        
        # Dibujar textos
        if illinois_x != 0 or illinois_y != 0:
            img_bgr = dibujar_texto_simple(
                img_bgr, "ILLINOIS", illinois_x, illinois_y,
                punto_medio, mm_por_pixel, illinois_vertical
            )
        
        if codigo_x != 0 or codigo_y != 0:
            img_bgr = dibujar_texto_simple(
                img_bgr, "123456", codigo_x, codigo_y,
                punto_medio, mm_por_pixel, codigo_vertical
            )
        
        if lote_x != 0 or lote_y != 0:
            img_bgr = dibujar_texto_simple(
                img_bgr, "23-45", lote_x, lote_y,
                punto_medio, mm_por_pixel, lote_vertical
            )
        
        # Convertir a base64
        _, buffer = cv2.imencode('.jpg', img_bgr)
        imagen_con_muescas = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'ok': True,
            'imagen_con_muescas': imagen_con_muescas
        })
        
    except Exception as e:
        print(f"[juntas] Error en imagen_con_muescas: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/juntas/<int:junta_id>/visualizacion', methods=['GET'])
def api_juntas_visualizacion(junta_id):
    """Obtiene la imagen de visualización guardada"""
    try:
        # Obtener datos de la junta
        db = load_juntas()
        junta = next((j for j in db.get('juntas', []) if j['id'] == junta_id), None)
        if not junta:
            return jsonify({'ok': False, 'error': 'Junta no encontrada'}), 404
        
        # Buscar archivo de visualización
        vis_filename = f"{junta['nombre']}_visualizacion.jpg"
        vis_path = get_junta_path(junta['nombre'], vis_filename)
        
        if not os.path.exists(vis_path):
            return jsonify({'ok': False, 'error': 'Visualización no encontrada'}), 404
        
        # Leer imagen y convertir a base64
        import cv2
        img = cv2.imread(vis_path)
        if img is None:
            return jsonify({'ok': False, 'error': 'No se pudo cargar la visualización'}), 500
        
        _, buffer = cv2.imencode('.jpg', img)
        imagen_visualizacion = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'ok': True,
            'imagen_visualizacion': imagen_visualizacion
        })
        
    except Exception as e:
        print(f"[juntas] Error en visualizacion: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/juntas/<int:junta_id>/overlay', methods=['GET'])
def api_juntas_overlay(junta_id):
    """Obtiene la imagen con overlay (muescas y labels) guardada"""
    try:
        # Obtener datos de la junta
        db = load_juntas()
        junta = next((j for j in db.get('juntas', []) if j['id'] == junta_id), None)
        
        if not junta:
            return jsonify({'ok': False, 'error': 'Junta no encontrada'}), 404
        
        # Buscar archivo de overlay
        overlay_filename = f"{junta['nombre']}_overlay.jpg"
        overlay_path = get_junta_path(junta['nombre'], overlay_filename)
        
        if not os.path.exists(overlay_path):
            # Si no existe la imagen con overlay, devolver la imagen original desde juntas_analisis
            original_path = get_junta_path(junta['nombre'], junta['imagen'])
            if os.path.exists(original_path):
                with open(original_path, 'rb') as f:
                    img_data = f.read()
                img_b64 = base64.b64encode(img_data).decode('utf-8')
                return jsonify({
                    'ok': True,
                    'imagen_overlay': img_b64,
                    'es_original': True
                })
            else:
                return jsonify({'ok': False, 'error': 'Imagen no encontrada'}), 404
        
        # Leer y convertir a base64
        with open(overlay_path, 'rb') as f:
            img_data = f.read()
        
        img_b64 = base64.b64encode(img_data).decode('utf-8')
        
        return jsonify({
            'ok': True,
            'imagen_overlay': img_b64,
            'es_original': False
        })
        
    except Exception as e:
        print(f"[juntas] Error en overlay: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

# ============================================================
# GESTIÓN DE CHROME
# ============================================================
def launch_chrome(url: str, kiosk: bool = False):
    """Lanza Chrome con la URL especificada y guarda el PID."""
    global chrome_pid
    
    try:
        # Verificar si Chrome existe
        if not os.path.exists(CHROME_PATH):
            print(f"✗ Chrome no encontrado en: {CHROME_PATH}")
            return None
        
        # Crear directorio de perfil aislado
        profile_dir = os.path.join(os.getcwd(), ".chrome_profile")
        os.makedirs(profile_dir, exist_ok=True)
        
        # Argumentos de Chrome
        args = [
            CHROME_PATH,
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=Translate",
            "--disable-infobars",
            "--disable-notifications",
        ]
        
        # Agregar argumentos de kiosco si está activado
        if kiosk:
            print("🖥️  Modo Kiosk: ventana a pantalla completa")
            args += ["--kiosk", "--start-fullscreen", f"--app={url}"]
        else:
            print("🖥️  Modo Ventana: ventana normal")
            args += ["--new-window", url]
        
        # Lanzar Chrome
        process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        chrome_pid = process.pid
        print(f"✅ Chrome lanzado con PID: {chrome_pid}")
        
        return process
    
    except FileNotFoundError:
        print(f"✗ Chrome no encontrado en: {CHROME_PATH}")
        return None
    except Exception as e:
        print(f"✗ Error lanzando Chrome: {e}")
        return None

def close_vision_server():
    """Cierra el servidor de visión si está ejecutándose"""
    global vision_server_process
    
    if vision_server_process and vision_server_process.poll() is None:
        print(f"[vision-manager] 🛑 Cerrando servidor de visión (PID: {vision_server_process.pid})...")
        try:
            vision_server_process.terminate()
            # Esperar un poco para que termine gracefully
            import time
            time.sleep(2)
            
            # Si no terminó, forzar el cierre
            if vision_server_process.poll() is None:
                print(f"[vision-manager] ⚠️ Forzando cierre del servidor de visión...")
                vision_server_process.kill()
                time.sleep(1)
            
            print(f"[vision-manager] ✅ Servidor de visión cerrado")
        except Exception as e:
            print(f"[vision-manager] ❌ Error cerrando servidor de visión: {e}")
        finally:
            vision_server_process = None
    else:
        print(f"[vision-manager] ℹ️ Servidor de visión no estaba ejecutándose")

def close_chrome():
    """Cierra Chrome de manera segura usando el PID guardado."""
    global chrome_pid
    
    if not chrome_pid:
        return
    
    try:
        # Cerrar el servidor de visión primero
        close_vision_server()
        
        # Intentar usar taskkill en Windows
        subprocess.run(
            f'taskkill /PID {chrome_pid} /F',
            shell=True,
            capture_output=True,
            timeout=5
        )
        print(f"✅ Chrome cerrado (PID: {chrome_pid})")
    
    except subprocess.TimeoutExpired:
        print("⚠️  Timeout al cerrar Chrome")
    except Exception as e:
        print(f"✗ Error cerrando Chrome: {e}")

# ============================================================
# CIERRE ORDENADO DEL SISTEMA
# ============================================================
def shutdown_system():
    """Cierra el sistema de manera ordenada."""
    global chrome_pid, _shutting_down
    
    print("\n" + "=" * 60)
    print("Iniciando cierre ordenado del sistema...")
    print("=" * 60)
    
    try:
        # Señalar que estamos cerrando
        _shutting_down = True
        time.sleep(0.5)
        
        # Cerrar Chrome
        if chrome_pid:
            print("🔄 Cerrando Chrome...")
            close_chrome()
            print("✅ Chrome cerrado")
        
        # Esperar un momento
        time.sleep(0.3)
        
        print("✅ Sistema cerrado correctamente")
        print("=" * 60)
    
    except Exception as e:
        print(f"✗ Error durante el cierre: {e}")
    
    finally:
        # Salir del proceso
        print("👋 Adiós!")
        sys.exit(0)

# ============================================================
# INICIALIZACIÓN DE MODELOS YOLO (GLOBAL)
# ============================================================
def initialize_yolo_models():
    """Carga los modelos YOLO globalmente al iniciar el servidor"""
    print("\n[yolo] 🚀 Inicializando modelos YOLO...")
    
    config = load_config()
    vision_config = config.get('vision', {})
    
    detection_model_path = vision_config.get('detection_model')
    holes_model_path = vision_config.get('holes_model')
    
    # Cargar modelo de detección
    if detection_model_path:
        if os.path.exists(detection_model_path):
            success = yolo_detector.load_model('detection', detection_model_path)
            if success:
                print(f"[yolo] ✓ Modelo Detection cargado: {detection_model_path}")
            else:
                print(f"[yolo] ✗ Error cargando Detection: {detection_model_path}")
        else:
            print(f"[yolo] ⚠️ Archivo no encontrado: {detection_model_path}")
    else:
        print(f"[yolo] ⚠️ No configurado modelo Detection en config.json")
    
    # Cargar modelo de agujeros
    if holes_model_path:
        if os.path.exists(holes_model_path):
            success = yolo_detector.load_model('holes', holes_model_path)
            if success:
                print(f"[yolo] ✓ Modelo Holes cargado: {holes_model_path}")
            else:
                print(f"[yolo] ✗ Error cargando Holes: {holes_model_path}")
        else:
            print(f"[yolo] ⚠️ Archivo no encontrado: {holes_model_path}")
    else:
        print(f"[yolo] ⚠️ No configurado modelo Holes en config.json")

# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================
def main():
    """Función principal del servidor."""
    global chrome_pid
    
    # Parsear argumentos
    parser = argparse.ArgumentParser(
        description="COMAU-VISION Web Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python illinois-server.py              # Modo normal
  python illinois-server.py -k           # Modo kiosco (fullscreen)
  python illinois-server.py -p 8000      # Puerto personalizado
        """
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Puerto del servidor (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "-k", "--kiosk",
        action="store_true",
        help="Lanzar Chrome en modo kiosco (fullscreen)"
    )
    
    args = parser.parse_args()
    
    # Banner de inicio
    print("\n" + "=" * 60)
    print("COMAU-VISION Server (Reconstruido)")
    print("=" * 60)
    print(f"Directorio de trabajo: {os.getcwd()}")
    print(f"Static folder: {os.path.abspath('static')}")
    print(f"Template folder: {os.path.abspath('templates')}")
    print(f"Puerto: {args.port}")
    print(f"Modo kiosco: {'Sí' if args.kiosk else 'No'}")
    print("=" * 60)
    
    # ════════════════════════════════════════════════════════════
    # PASO 1: Iniciar Flask en un thread daemon
    # ════════════════════════════════════════════════════════════
    print(f"\n🔄 Iniciando servidor Flask en thread daemon...")
    
    def run_flask():
        """Ejecutar Flask en thread separado"""
        try:
            # Deshabilitar logging de peticiones HTTP
            import logging
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)
            
            socketio.run(app, host='0.0.0.0', port=args.port, debug=False, use_reloader=False)
        except Exception as e:
            print(f"✗ Error en Flask: {e}")
    
    flask_thread = threading.Thread(target=run_flask, daemon=True, name="FlaskServer")
    flask_thread.start()
    
    # Esperar a que Flask inicie
    time.sleep(1)
    print(f"✅ Flask iniciado en thread daemon")
    
    # ════════════════════════════════════════════════════════════
    # PASO 1.5: Intentar conectar a la cámara
    # ════════════════════════════════════════════════════════════
    print(f"\n🎥 Intentando conectar a la cámara...")
    try:
        success, message = camera_manager.connectToCamera()
        if success:
            print(f"✅ {message}")
        else:
            print(f"⚠️  {message}")
    except Exception as e:
        print(f"✗ Error conectando a cámara: {e}")
    
    # ════════════════════════════════════════════════════════════
    # PASO 1.6: Inicializar MQTT Manager
    # ════════════════════════════════════════════════════════════
    print(f"\n📡 Inicializando MQTT Manager...")
    try:
        from mqtt_manager import get_mqtt_manager
        
        mqtt_manager = get_mqtt_manager()
        config = mqtt_manager.get_config()
        
        if config.get('broker_ip') and config.get('connect_on_start', True):
            print(f"🔌 Broker configurado: {config['broker_ip']}:{config['broker_port']}")
            print(f"📋 Topics: {config['topics']}")
            
            # Iniciar conexión MQTT
            print(f"🔌 Intentando conectar a MQTT...")
            if mqtt_manager.start():
                print(f"✅ MQTT Manager iniciado")
                print(f"🔍 Estado MQTT después de iniciar: connected={mqtt_manager.connected}, state={mqtt_manager.state}")
            else:
                print(f"⚠️  MQTT Manager no pudo iniciar")
                print(f"🔍 Estado MQTT después de fallo: connected={mqtt_manager.connected}, state={mqtt_manager.state}")
        else:
            print(f"ℹ️  MQTT no configurado o deshabilitado")
            
    except Exception as e:
        print(f"✗ Error inicializando MQTT: {e}")
    
    # ════════════════════════════════════════════════════════════
    # PASO 1.6.5: Inicializar gestión automática del servidor de visión
    # ════════════════════════════════════════════════════════════
    print(f"\n👁️ Inicializando gestión automática del servidor de visión...")
    
    def vision_server_manager():
        """Thread para gestionar automáticamente el servidor de visión"""
        import requests
        import subprocess
        import time
        
        global vision_server_process
        last_check_time = 0
        check_interval = 10  # Verificar cada 10 segundos
        
        print(f"[vision-manager] 🚀 Thread de gestión iniciado")
        
        while True:
            try:
                current_time = time.time()
                
                # Solo verificar si han pasado suficientes segundos
                if current_time - last_check_time < check_interval:
                    time.sleep(1)
                    continue
                
                last_check_time = current_time
                print(f"[vision-manager] 🔍 Verificando estado del servidor de visión...")
                
                # Leer configuración del servidor de visión
                try:
                    with open('config.json', 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        vision_config = config.get('vision', {})
                        vision_server_path = vision_config.get('vision_server_path')
                        vision_server_port = vision_config.get('vision_server_port', 8000)
                    print(f"[vision-manager] 📋 Configuración leída: ruta={vision_server_path}, puerto={vision_server_port}")
                except Exception as e:
                    print(f"[vision-manager] ❌ Error leyendo configuración: {e}")
                    vision_server_path = None
                    vision_server_port = 8000
                
                # Si no hay configuración, esperar
                if not vision_server_path:
                    print(f"[vision-manager] ⚠️ No hay configuración de ruta, esperando...")
                    time.sleep(5)
                    continue
                
                # Verificar si el proceso sigue ejecutándose
                if vision_server_process and vision_server_process.poll() is not None:
                    print(f"[vision-manager] ⚠️ Proceso del servidor de visión terminó (código: {vision_server_process.returncode})")
                    vision_server_process = None
                
                # Verificar si el servidor responde
                vision_server_url = f"http://127.0.0.1:{vision_server_port}"
                server_responding = False
                
                try:
                    response = requests.get(f"{vision_server_url}/", timeout=2)
                    if response.status_code == 200:
                        server_responding = True
                        print(f"[vision-manager] ✅ Servidor respondiendo correctamente")
                except Exception as e:
                    print(f"[vision-manager] ❌ Servidor no responde: {e}")
                    server_responding = False
                
                # Si no responde y no hay proceso, iniciarlo
                if not server_responding and not vision_server_process:
                    print(f"[vision-manager] 🚀 Servidor de visión no responde, iniciando...")
                    print(f"[vision-manager] 📁 Ruta: {vision_server_path}")
                    print(f"[vision-manager] 🔌 Puerto: {vision_server_port}")
                    
                    try:
                        # Verificar que el archivo existe
                        if not os.path.exists(vision_server_path):
                            print(f"[vision-manager] ❌ Archivo no encontrado: {vision_server_path}")
                            time.sleep(30)  # Esperar más tiempo si no existe
                            continue
                        
                        # Obtener el directorio del script
                        vision_server_dir = os.path.dirname(os.path.abspath(vision_server_path))
                        print(f"[vision-manager] 📁 Directorio: {vision_server_dir}")
                        
                        # Iniciar el proceso
                        print(f"[vision-manager] 🚀 Ejecutando: pythonw {vision_server_path} -p {vision_server_port}")
                        vision_server_process = subprocess.Popen(
                            ['pythonw', vision_server_path, '-p', str(vision_server_port)],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=vision_server_dir,
                            text=True,
                            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                        )
                        
                        print(f"[vision-manager] ✅ Servidor de visión iniciado con PID: {vision_server_process.pid}")
                        
                        # Esperar un poco para que se inicie
                        time.sleep(3)
                        
                        # Verificar si se inició correctamente
                        if vision_server_process.poll() is not None:
                            print(f"[vision-manager] ❌ El proceso terminó inmediatamente (código: {vision_server_process.returncode})")
                            vision_server_process = None
                        else:
                            print(f"[vision-manager] ✅ Servidor de visión funcionando correctamente")
                            
                    except Exception as e:
                        print(f"[vision-manager] ❌ Error iniciando servidor de visión: {e}")
                        vision_server_process = None
                
                elif server_responding:
                    # Servidor funcionando correctamente
                    if vision_server_process:
                        print(f"[vision-manager] ✅ Servidor de visión funcionando (PID: {vision_server_process.pid})")
                    else:
                        print(f"[vision-manager] ✅ Servidor de visión funcionando (proceso externo)")
                
                time.sleep(1)
                
            except Exception as e:
                print(f"[vision-manager] ❌ Error en gestión del servidor de visión: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)
    
    # Gestión automática del servidor de visión deshabilitada
    # (Se utiliza IP y puerto configurados para comunicarse con un servidor ya en ejecución)
    
    # ════════════════════════════════════════════════════════════
    # PASO 1.7: Inicializar modelos YOLO (GLOBAL)
    # ════════════════════════════════════════════════════════════
    initialize_yolo_models()
    
    # ════════════════════════════════════════════════════════════
    # PASO 2: Lanzar Chrome
    # ════════════════════════════════════════════════════════════
    print(f"\n🟢 Iniciando servidor en http://127.0.0.1:{args.port}")
    
    url = f"http://127.0.0.1:{args.port}"
    chrome_process = launch_chrome(url, kiosk=args.kiosk)
    
    if not chrome_process:
        print("⚠️  No se pudo lanzar Chrome automáticamente")
        print(f"💡 Abre manualmente: {url}")
        print("💡 Presiona Ctrl+C para cerrar el servidor")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nCtrl+C detectado. Cerrando...")
            sys.exit(0)
    else:
        mode_text = "modo kiosco" if args.kiosk else "modo normal"
        print(f"✅ Chrome lanzado en {mode_text}")
        print("💡 Al cerrar Chrome, el servidor se detendrá automáticamente")
        print("=" * 60)
        
        # ════════════════════════════════════════════════════════════
        # PASO 3: Monitorear Chrome - BLOQUEANTE
        # ════════════════════════════════════════════════════════════
        try:
            print(f"🔄 Monitoreando proceso Chrome (PID: {chrome_process.pid})...")
            print("   Esperando a que Chrome se cierre...")
            
            # BLOQUEANTE: Esperar a que Chrome termine
            chrome_process.wait()
            
            # Chrome cerró - detener todo
            print("\n" + "=" * 60)
            print("Chrome cerrado - iniciando cierre del sistema...")
            print("=" * 60)
            time.sleep(0.5)
            
            print("✅ Sistema cerrado correctamente")
            print("👋 Adiós!")
            sys.exit(0)
        
        except KeyboardInterrupt:
            print("\n\nCtrl+C detectado...")
            print("Cerrando Chrome...")
            close_chrome()
            time.sleep(0.5)
            print("✅ Sistema cerrado correctamente")
            print("👋 Adiós!")
            sys.exit(0)
        
        except Exception as e:
            print(f"✗ Error: {e}")
            close_chrome()
            sys.exit(1)

@socketio.on('AUTO_ANALYZE')
def handle_auto_analyze():
    print('[socketio] 📩 Evento AUTO_ANALYZE recibido desde frontend. Ejecutando server_test()...')
    result = server_test()
    if isinstance(result, dict):
        result_to_log = dict(result)
        result_to_log.pop('overlay_image', None)
        print('[socketio] 📤 Respuesta de análisis para emitir (sin imagen):', result_to_log)
        # Enviar full payload con imagen sólo al frontend
        emit('SERVER_TEST_RESULT', result)
    else:
        print('[socketio] ❌ Respuesta inesperada:', result)
        emit('SERVER_TEST_RESULT', { 'ok': False, 'error': 'Respuesta inesperada', 'data': str(result) })

if __name__ == '__main__':
    main()