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
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEFAULT_PORT = 5000
CONFIG_FILE = 'config.json'
JUNTAS_FILE = 'juntas.json'

# Variables globales para gestión de Chrome
chrome_pid = None
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
    return send_from_directory('juntas_analisis', filename)

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
        'center_x_mm': 0,
        'center_y_mm': 0,
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
        center_x = data.get('center_x_mm', 0.0)
        center_y = data.get('center_y_mm', 0.0)
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
    """Guardar configuración de ArUcos y objetos de renderizado persistentes"""
    try:
        import cv2
        import numpy as np
        from src.vision.frames_manager import get_global_overlay_manager
        
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
        if 'center_x_mm' in data:
            aruco_config['base']['center_x_mm'] = data['center_x_mm']
        if 'center_y_mm' in data:
            aruco_config['base']['center_y_mm'] = data['center_y_mm']
        if 'show_center' in data:
            aruco_config['show_center'] = data['show_center']
        if 'use_saved_reference' in data:
            aruco_config['use_saved_reference'] = data['use_saved_reference']
        
        # Obtener frame actual de la cámara
        cv2_frame = camera_manager.get_frame_raw()
        
        if cv2_frame is None:
            return jsonify({
                'ok': False,
                'error': 'No hay frame disponible de la cámara'
            }), 400
        
        # Obtener instancia global de OverlayManager
        overlay_manager = get_global_overlay_manager()
        
        # Limpiar objetos existentes antes de crear nuevos
        from src.vision.aruco_manager import clear_aruco_objects
        clear_aruco_objects(overlay_manager)
        
        # Detectar ArUcos para obtener frames temporales
        frame_aruco_id = aruco_config.get('base', {}).get('reference_id', 0)
        tool_aruco_id = aruco_config.get('tool', {}).get('reference_id', 0)
        frame_marker_size = aruco_config.get('base', {}).get('marker_size_mm', 70.0)
        tool_marker_size = aruco_config.get('tool', {}).get('marker_size_mm', 50.0)
        
        # Detectar ArUcos
        all_arucos_result = detect_arucos_in_image(cv2_frame, frame_aruco_id, tool_aruco_id, frame_marker_size, tool_marker_size)
        frame_result = all_arucos_result if is_frame_detected(all_arucos_result) else None
        tool_result = all_arucos_result if is_tool_detected(all_arucos_result) else None
        
        frame_detected = frame_result is not None
        tool_detected = tool_result is not None
        
        print(f"[aruco] Guardando configuración:")
        print(f"  - Frame ArUco (ID: {frame_aruco_id}) detectado: {frame_detected}")
        print(f"  - Tool ArUco (ID: {tool_aruco_id}) detectado: {tool_detected}")
        
        # Copiar frames temporales a permanentes si están detectados
        if frame_detected and frame_result:
            detected_arucos = frame_result.get('detected_arucos', {})
            
            if frame_aruco_id in detected_arucos:
                frame_data = detected_arucos[frame_aruco_id]
                frame_center = frame_data['center']
                frame_angle = frame_data['angle_rad']
                frame_px_per_mm = frame_data['px_per_mm']
            
                overlay_manager.define_frame(
                    "base_frame",
                    offset=(frame_center[0], frame_center[1]),
                    rotation=frame_angle,
                    px_per_mm=frame_px_per_mm,
                    parent_frame="Base",
                )
                print(f"[aruco] ✓ Marco base_frame actualizado: center=({frame_center[0]:.1f}, {frame_center[1]:.1f}), angle={frame_angle:.3f}rad, px_per_mm={frame_px_per_mm:.3f}")
        
        if tool_detected and tool_result:
            detected_arucos = tool_result.get('detected_arucos', {})
            
            if tool_aruco_id in detected_arucos:
                tool_data = detected_arucos[tool_aruco_id]
                tool_center = tool_data['center']
                tool_angle = tool_data['angle_rad']
                tool_px_per_mm = tool_data['px_per_mm']
            
                overlay_manager.define_frame(
                    "tool_frame",
                    offset=(tool_center[0], tool_center[1]),
                    rotation=tool_angle,
                    px_per_mm=tool_px_per_mm,
                    parent_frame="Base",
                )
                print(f"[aruco] ✓ Marco tool_frame actualizado: center=({tool_center[0]:.1f}, {tool_center[1]:.1f}), angle={tool_angle:.3f}rad, px_per_mm={tool_px_per_mm:.3f}")
        
        # Crear objetos de renderizado persistentes
        objects_to_save = []
        
        # Objetos del Frame ArUco si está detectado
        if frame_detected and frame_result:
            detected_arucos = frame_result.get('detected_arucos', {})
            
            if frame_aruco_id in detected_arucos:
                frame_data = detected_arucos[frame_aruco_id]
                frame_center = frame_data['center']
                frame_corners = frame_data.get('corners', [])
                frame_angle = frame_data['angle_rad']
            
                overlay_manager.add_polygon(
                    "Base",
                    points=frame_corners,
                    name=f"aruco_contour_{frame_aruco_id}",
                    color=(0, 255, 255),
                    thickness=2
                )
                
                image_height, image_width = cv2_frame.shape[:2]
                axis_length = max(image_width, image_height)
                
                x_end1 = (frame_center[0] + axis_length * np.cos(frame_angle), frame_center[1] + axis_length * np.sin(frame_angle))
                x_end2 = (frame_center[0] - axis_length * np.cos(frame_angle), frame_center[1] - axis_length * np.sin(frame_angle))
                
                y_angle = frame_angle + np.pi / 2
                y_end1 = (frame_center[0] + axis_length * np.cos(y_angle), frame_center[1] + axis_length * np.sin(y_angle))
                y_end2 = (frame_center[0] - axis_length * np.cos(y_angle), frame_center[1] - axis_length * np.sin(y_angle))
                
                overlay_manager.add_line("Base", start=x_end2, end=x_end1, name=f"aruco_x_axis_{frame_aruco_id}", color=(0, 255, 255), thickness=2)
                overlay_manager.add_line("Base", start=y_end2, end=y_end1, name=f"aruco_y_axis_{frame_aruco_id}", color=(0, 255, 255), thickness=2)
                overlay_manager.add_circle("Base", center=frame_center, radius=5, name=f"aruco_center_{frame_aruco_id}", color=(0, 255, 255), filled=True)
                
                objects_to_save.extend([
                    f"aruco_contour_{frame_aruco_id}", 
                    f"aruco_x_axis_{frame_aruco_id}", 
                    f"aruco_y_axis_{frame_aruco_id}", 
                    f"aruco_center_{frame_aruco_id}"
                ])
        
        # Objetos del Tool ArUco si está detectado
        if tool_detected and tool_result:
            detected_arucos = tool_result.get('detected_arucos', {})
            
            if tool_aruco_id in detected_arucos:
                tool_data = detected_arucos[tool_aruco_id]
                tool_center = tool_data['center']
                tool_corners = tool_data.get('corners', [])
                tool_angle = tool_data['angle_rad']
            
                overlay_manager.add_polygon("Base", points=tool_corners, name=f"aruco_contour_{tool_aruco_id}", color=(255, 0, 0), thickness=2)
                
                image_height, image_width = cv2_frame.shape[:2]
                axis_length = max(image_width, image_height)
                
                x_end1 = (tool_center[0] + axis_length * np.cos(tool_angle), tool_center[1] + axis_length * np.sin(tool_angle))
                x_end2 = (tool_center[0] - axis_length * np.cos(tool_angle), tool_center[1] - axis_length * np.sin(tool_angle))
                
                y_angle = tool_angle + np.pi / 2
                y_end1 = (tool_center[0] + axis_length * np.cos(y_angle), tool_center[1] + axis_length * np.sin(y_angle))
                y_end2 = (tool_center[0] - axis_length * np.cos(y_angle), tool_center[1] - axis_length * np.sin(y_angle))
                
                overlay_manager.add_line("Base", start=x_end2, end=x_end1, name=f"aruco_x_axis_{tool_aruco_id}", color=(255, 0, 0), thickness=2)
                overlay_manager.add_line("Base", start=y_end2, end=y_end1, name=f"aruco_y_axis_{tool_aruco_id}", color=(255, 0, 0), thickness=2)
                overlay_manager.add_circle("Base", center=tool_center, radius=5, name=f"aruco_center_{tool_aruco_id}", color=(255, 0, 0), filled=True)
                
                objects_to_save.extend([
                    f"aruco_contour_{tool_aruco_id}", 
                    f"aruco_x_axis_{tool_aruco_id}", 
                    f"aruco_y_axis_{tool_aruco_id}", 
                    f"aruco_center_{tool_aruco_id}"
                ])
        
        # Círculo del centro del troquel
        center_x_mm = aruco_config.get('center_x_mm', 0.0)
        center_y_mm = aruco_config.get('center_y_mm', 0.0)
        
        if frame_detected:
            frame_name = "base_frame"
        else:
            image_height, image_width = cv2_frame.shape[:2]
            assumed_width_mm = 200.0
            assumed_height_mm = 150.0
            px_per_mm = min(image_width / assumed_width_mm, image_height / assumed_height_mm)
            overlay_manager.frames["Base"].px_per_mm = px_per_mm
            frame_name = "Base"
        
        overlay_manager.add_circle(
            frame_name,
            center=(center_x_mm, center_y_mm),
            radius=5.0,
            name="center_circle",
            color=(255, 255, 0),
            filled=True
        )
        
        objects_to_save.append("center_circle")
        
        # Guardar configuración
        overlay_manager.save_persistent_config()
        
        aruco_config['saved_objects'] = {
            'frame_objects': [name for name in objects_to_save if str(frame_aruco_id) in name],
            'tool_objects': [name for name in objects_to_save if str(tool_aruco_id) in name],
            'center_objects': ['center_circle'],
            'descriptions': {
                f'aruco_contour_{frame_aruco_id}': f'Contorno del Frame ArUco (ID: {frame_aruco_id})',
                f'aruco_x_axis_{frame_aruco_id}': f'Eje X del Frame ArUco (ID: {frame_aruco_id})',
                f'aruco_y_axis_{frame_aruco_id}': f'Eje Y del Frame ArUco (ID: {frame_aruco_id})',
                f'aruco_center_{frame_aruco_id}': f'Centro del Frame ArUco (ID: {frame_aruco_id})',
                f'aruco_contour_{tool_aruco_id}': f'Contorno del Tool ArUco (ID: {tool_aruco_id})',
                f'aruco_x_axis_{tool_aruco_id}': f'Eje X del Tool ArUco (ID: {tool_aruco_id})',
                f'aruco_y_axis_{tool_aruco_id}': f'Eje Y del Tool ArUco (ID: {tool_aruco_id})',
                f'aruco_center_{tool_aruco_id}': f'Centro del Tool ArUco (ID: {tool_aruco_id})',
                'center_circle': 'Círculo del centro del troquel (10mm diámetro)'
            }
        }
        
        config['aruco'] = aruco_config
        save_config(config)
        
        print(f"[aruco] ✓ Configuración guardada:")
        print(f"  - Marcos: base_frame, tool_frame")
        print(f"  - Objetos: {len(objects_to_save)} objetos guardados")
        
        return jsonify({
            'ok': True,
            'message': 'Configuración guardada correctamente',
            'data': {
                'frames_saved': ['base_frame', 'tool_frame'],
                'objects_saved': objects_to_save,
                'frame_detected': frame_detected,
                'tool_detected': tool_detected
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
    """Endpoint para verificar el estado del servidor de visión en puerto 8000"""
    try:
        import requests
        
        # Verificar si el servidor de visión en puerto 8000 está respondiendo
        vision_server_url = "http://127.0.0.1:8000"
        
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
                ['python', vision_server_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=vision_server_dir,  # ← Ejecutar desde el directorio del script
                text=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            
            # Guardar el PID para poder detenerlo después
            global vision_server_process
            vision_server_process = process
            
            print(f"[illinois-server] ✅ Servidor de visión iniciado con PID: {process.pid}")
            
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

@app.route('/api/juntas', methods=['GET'])
def api_get_juntas():
    db = load_juntas()
    return jsonify({'ok': True, 'juntas': db.get('juntas', [])})

@app.route('/api/juntas/<int:junta_id>', methods=['GET'])
def api_get_junta(junta_id):
    db = load_juntas()
    junta = next((j for j in db.get('juntas', []) if j['id'] == junta_id), None)
    if junta:
        return jsonify({'ok': True, 'junta': junta})
    return jsonify({'ok': False, 'error': 'Junta no encontrada'}), 404

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
    analisis_path = os.path.join('juntas_analisis', analisis_filename)

    if not os.path.exists(analisis_path):
        return jsonify({'ok': False, 'error': 'Archivo de análisis no encontrado'}), 404

    try:
        with open(analisis_path, 'r', encoding='utf-8') as f:
            analisis_data = json.load(f)
        return jsonify({'ok': True, 'analisis': analisis_data})
    except Exception as e:
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

def close_chrome():
    """Cierra Chrome de manera segura usando el PID guardado."""
    global chrome_pid
    
    if not chrome_pid:
        return
    
    try:
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
            
            app.run(host='0.0.0.0', port=args.port, debug=False, use_reloader=False)
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

if __name__ == '__main__':
    main()