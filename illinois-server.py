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
from datetime import datetime

# Agregar src al path de Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from vision import camera_manager
from vision.aruco_detector import detect_aruco_by_id, detect_all_arucos
from vision import yolo_detector
import visualizador
import pipeline_analisis

# Importar módulos de rendering
import muescas_renderer
import textos_renderer

# ============================================================
# CONFIGURACIÓN GLOBAL
# ============================================================
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEFAULT_PORT = 5000

# Variables globales para gestión de Chrome
chrome_pid = None
flask_server = None
_shutting_down = False

# Variables para control de overlay temporal
_overlay_frame = None
_overlay_active_until = None

# Variables globales para almacenar resultados del análisis
_analisis_junta_actual = None
_visualizacion_junta_actual = None
_fondo_detectado_junta_actual = None
_analisis_serializable_junta_actual = None

app = Flask(__name__, 
            static_folder='static',
            static_url_path='/static',
            template_folder='templates')

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
# API ARUCO
# ============================================================

def load_aruco_config():
    """Carga la configuración de ArUcos desde config.json"""
    try:
        with open('config.json', 'r') as f:
            full_config = json.load(f)
            return full_config
    except:
        pass
    
    # Configuración por defecto
    return {
        'aruco': {
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
    }

def save_aruco_config(config):
    """Guarda la configuración COMPLETA en config.json"""
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"[aruco] Error guardando config: {e}")
        return False

@app.route('/api/aruco/config', methods=['GET'])
def api_aruco_config():
    """Obtiene la configuración actual de ArUcos"""
    try:
        config = load_aruco_config()
        print(f"[aruco] GET /api/aruco/config - Retornando: {config}")
        return jsonify({'ok': True, 'aruco': config.get('aruco', {})})
    except Exception as e:
        print(f"[aruco] Error en GET /api/aruco/config: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/aruco/capture_reference', methods=['POST'])
def api_aruco_capture_reference():
    """Captura el ArUco de referencia del stream de video en vivo"""
    try:
        import cv2
        import numpy as np
        
        config = load_aruco_config()
        aruco_config = config.get('aruco', {})
        
        reference_id = aruco_config.get('reference_id', 0)
        marker_size_mm = aruco_config.get('marker_size_mm', 42.0)
        
        # Obtener frame actual de la cámara en formato OpenCV
        cv2_frame = camera_manager.get_frame_raw()
        
        if cv2_frame is None:
            return jsonify({
                'ok': False,
                'error': 'No hay frame disponible de la cámara'
            }), 400
        
        # Importar numpy para operaciones
        import numpy as np
        
        # Detectar ArUco específico
        result = detect_aruco_by_id(cv2_frame, reference_id, marker_size_mm=marker_size_mm)
        
        if result is None:
            # El ArUco específico no se encontró, ahora detectar todos para dar mejor mensaje
            all_arucos = detect_all_arucos(cv2_frame, marker_size_mm=marker_size_mm)
            
            if all_arucos is None or len(all_arucos.get('detected_ids', [])) == 0:
                # No se detectó NINGÚN ArUco
                error_msg = f'No se detectó ningún marcador ArUco en el frame'
                print(f"[aruco] ❌ {error_msg}")
            else:
                # Se detectaron ArUcos, pero no el ID específico
                detected = all_arucos.get('detected_ids', [])
                detected_str = ', '.join(str(id) for id in detected)
                error_msg = f'ArUco ID {reference_id} no detectado.\n🔍 ArUcos detectados: [{detected_str}]'
                print(f"[aruco] ❌ {error_msg}")
            
            return jsonify({
                'ok': False,
                'error': error_msg
            }), 400
        
        # Guardar datos de referencia
        saved_reference = {
            'px_per_mm': result['px_per_mm'],
            'angle_deg': float(np.arctan2(result['rotation_matrix'][1][0], result['rotation_matrix'][0][0]) * 180 / np.pi),
            'timestamp': datetime.now().isoformat(),
            'center': result['center'],
            'corners': result['corners']
        }
        
        aruco_config['saved_reference'] = saved_reference
        config['aruco'] = aruco_config
        save_aruco_config(config)
        
        return jsonify({
            'ok': True,
            'data': {
                'px_per_mm': result['px_per_mm'],
                'angle_deg': float(np.arctan2(result['rotation_matrix'][1][0], result['rotation_matrix'][0][0]) * 180 / np.pi),
                'timestamp': saved_reference['timestamp']
            },
            'message': 'Referencia ArUco capturada y guardada'
        })
    
    except Exception as e:
        print(f"[aruco] Error en POST /api/aruco/capture_reference: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/aruco/draw_overlay', methods=['POST'])
def api_aruco_draw_overlay():
    """Genera un frame con overlay de ArUcos y lo muestra por 3 segundos en el dashboard.
    Detecta ambos ArUcos (Frame y Tool). Solo actualiza los que se encuentran."""
    global _overlay_frame, _overlay_active_until
    
    try:
        import cv2
        import numpy as np
        
        config = load_aruco_config()
        aruco_config = config.get('aruco', {})
        
        # Obtener IDs y tamaños de ambos ArUcos
        frame_aruco_id = aruco_config.get('frame_aruco_id', 0)
        frame_marker_size = aruco_config.get('frame_marker_size_mm', 42.0)
        tool_aruco_id = aruco_config.get('tool_aruco_id', 0)
        tool_marker_size = aruco_config.get('tool_marker_size_mm', 42.0)
        
        # Obtener frame actual de la cámara en formato OpenCV
        cv2_frame = camera_manager.get_frame_raw()
        
        if cv2_frame is None:
            return jsonify({
                'ok': False,
                'error': 'No hay frame disponible de la cámara'
            }), 400
        
        # Detectar ambos ArUcos
        frame_result = detect_aruco_by_id(cv2_frame, frame_aruco_id, marker_size_mm=frame_marker_size)
        tool_result = detect_aruco_by_id(cv2_frame, tool_aruco_id, marker_size_mm=tool_marker_size)
        
        # Verificar si al menos uno se detectó
        if frame_result is None and tool_result is None:
            all_arucos = detect_all_arucos(cv2_frame, marker_size_mm=max(frame_marker_size, tool_marker_size))
            if all_arucos is None or len(all_arucos.get('detected_ids', [])) == 0:
                error_msg = f'No se detectó ningún marcador ArUco en el frame'
            else:
                detected = all_arucos.get('detected_ids', [])
                detected_str = ', '.join(str(id) for id in detected)
                error_msg = f'ArUcos Frame({frame_aruco_id}) y Tool({tool_aruco_id}) no detectados.\nArUcos detectados: [{detected_str}]'
            
            return jsonify({
                'ok': False,
                'error': error_msg
            }), 400
        
        # Preparar datos para el visualizador (usar el primero que se encuentre para dibujar)
        result_to_draw = frame_result if frame_result is not None else tool_result
        
        angle_rad = np.arctan2(result_to_draw['rotation_matrix'][1][0], result_to_draw['rotation_matrix'][0][0])
        
        datos_aruco = {
            'center': result_to_draw['center'],
            'angle_rad': float(angle_rad),
            'corners': result_to_draw['corners'],
            'px_per_mm': result_to_draw['px_per_mm']
        }
        
        datos_visualizacion = {
            'aruco': datos_aruco,
            '_force_draw_aruco': True
        }
        
        # Dibujar overlay usando visualizador
        frame_con_overlay = visualizador.dibujar_todo(cv2_frame, datos_visualizacion)
        
        if frame_con_overlay is None:
            return jsonify({
                'ok': False,
                'error': 'Error dibujando overlay'
            }), 500
        
        # Convertir imagen a JPEG
        ret, buffer = cv2.imencode('.jpg', frame_con_overlay, [cv2.IMWRITE_JPEG_QUALITY, 90])
        
        if not ret:
            return jsonify({
                'ok': False,
                'error': 'Error codificando imagen'
            }), 500
        
        # Actualizar config solo con los ArUcos que se encontraron
        if frame_result is not None:
            print(f"[aruco] ✓ ArUco_Frame detectado (ID: {frame_aruco_id})")
            aruco_config['saved_frame_reference'] = {
                'px_per_mm': float(frame_result['px_per_mm']),
                'center': list(frame_result['center']),
                'angle_rad': float(angle_rad),
                'corners': frame_result['corners'],
                'timestamp': datetime.now().isoformat()
            }
        
        if tool_result is not None:
            print(f"[aruco] ✓ ArUco_Tool detectado (ID: {tool_aruco_id})")
            angle_tool = np.arctan2(tool_result['rotation_matrix'][1][0], tool_result['rotation_matrix'][0][0])
            aruco_config['saved_tool_reference'] = {
                'px_per_mm': float(tool_result['px_per_mm']),
                'center': list(tool_result['center']),
                'angle_rad': float(angle_tool),
                'corners': tool_result['corners'],
                'timestamp': datetime.now().isoformat()
            }
        
        # Guardar config actualizada
        config['aruco'] = aruco_config
        save_aruco_config(config)
        
        # Guardar frame temporalmente y activar overlay por 3 segundos
        _overlay_frame = buffer.tobytes()
        _overlay_active_until = time.time() + 3.0  # 3 segundos
        
        print(f"[aruco] ✓ Overlay mostrado por 3 segundos en dashboard")
        
        return jsonify({
            'ok': True,
            'message': 'Overlay mostrado en dashboard por 3 segundos'
        })
    
    except Exception as e:
        print(f"[aruco] Error en POST /api/aruco/draw_overlay: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/aruco/set_reference', methods=['POST'])
def api_aruco_set_reference():
    """Aplica la configuración de ArUcos"""
    try:
        data = request.get_json()
        
        config = load_aruco_config()
        aruco_config = config.get('aruco', {})
        
        # Actualizar valores desde el request
        if 'frame_aruco_id' in data:
            aruco_config['frame_aruco_id'] = int(data['frame_aruco_id'])
        if 'frame_marker_size_mm' in data:
            aruco_config['frame_marker_size_mm'] = float(data['frame_marker_size_mm'])
        if 'tool_aruco_id' in data:
            aruco_config['tool_aruco_id'] = int(data['tool_aruco_id'])
        if 'tool_marker_size_mm' in data:
            aruco_config['tool_marker_size_mm'] = float(data['tool_marker_size_mm'])
        if 'center_x_mm' in data:
            aruco_config['center_x_mm'] = float(data['center_x_mm'])
        if 'center_y_mm' in data:
            aruco_config['center_y_mm'] = float(data['center_y_mm'])
        if 'show_reference' in data:
            aruco_config['show_reference'] = bool(data['show_reference'])
        if 'use_saved_reference' in data:
            aruco_config['use_saved_reference'] = bool(data['use_saved_reference'])
        
        config['aruco'] = aruco_config
        
        print(f"[aruco] POST /api/aruco/set_reference - Guardando: {config}")
        
        if save_aruco_config(config):
            print(f"[aruco] ✓ Configuración guardada correctamente")
            return jsonify({
                'ok': True,
                'message': 'Configuración de ArUco aplicada correctamente'
            })
        else:
            return jsonify({
                'ok': False,
                'error': 'Error guardando configuración'
            }), 500
    
    except Exception as e:
        print(f"[aruco] Error en POST /api/aruco/set_reference: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

# ============================================================
# API JUNTAS
# ============================================================
JUNTAS_FILE = 'juntas.json'

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
    """Retorna lista de todas las juntas"""
    try:
        data = load_juntas()
        juntas = data.get('juntas', [])
        
        # Retornar lista simple de juntas
        return jsonify({
            'ok': True,
            'juntas': juntas
        })
    except Exception as e:
        print(f"[juntas] Error en GET /api/juntas: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/juntas/selected', methods=['GET'])
def api_get_selected_junta():
    """Retorna la junta actualmente seleccionada"""
    try:
        data = load_juntas()
        selected_id = data.get('selected_id')
        juntas = data.get('juntas', [])
        
        if selected_id is None:
            return jsonify({
                'ok': True,
                'junta': None,
                'message': 'No hay junta seleccionada'
            })
        
        # Buscar junta por ID
        junta = next((j for j in juntas if j.get('id') == selected_id), None)
        
        if junta:
            print(f"[juntas] ✓ Junta seleccionada: {junta.get('nombre')} (ID: {selected_id})")
            return jsonify({
                'ok': True,
                'junta': junta
            })
        else:
            print(f"[juntas] ⚠️ ID seleccionado {selected_id} no encontrado en la lista")
            return jsonify({
                'ok': True,
                'junta': None,
                'message': f'ID {selected_id} no encontrado'
            })
    
    except Exception as e:
        print(f"[juntas] Error en GET /api/juntas/selected: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/juntas/select', methods=['POST'])
def api_select_junta():
    """Selecciona una junta y guarda su ID en juntas.json"""
    try:
        data = request.get_json()
        junta_id = data.get('id')
        
        if junta_id is None:
            return jsonify({
                'ok': False,
                'error': 'ID de junta requerido'
            }), 400
        
        # Cargar juntas
        juntas_data = load_juntas()
        juntas = juntas_data.get('juntas', [])
        
        # Verificar que la junta existe
        junta = next((j for j in juntas if j.get('id') == junta_id), None)
        
        if not junta:
            return jsonify({
                'ok': False,
                'error': f'Junta con ID {junta_id} no encontrada'
            }), 404
        
        # Guardar ID seleccionado
        juntas_data['selected_id'] = junta_id
        
        if save_juntas(juntas_data):
            print(f"[juntas] ✓ Junta seleccionada: {junta.get('nombre')} (ID: {junta_id})")
            return jsonify({
                'ok': True,
                'message': f'Junta {junta.get("nombre")} seleccionada',
                'junta_id': junta_id,
                'junta_nombre': junta.get('nombre')
            })
        else:
            return jsonify({
                'ok': False,
                'error': 'Error guardando junta seleccionada'
            }), 500
    
    except Exception as e:
        print(f"[juntas] Error en POST /api/juntas/select: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/juntas/<int:junta_id>/analisis', methods=['GET'])
def api_get_junta_analisis(junta_id):
    """Retorna el análisis de una junta específica"""
    try:
        data = load_juntas()
        juntas = data.get('juntas', [])
        
        # Buscar junta por ID
        junta = next((j for j in juntas if j.get('id') == junta_id), None)
        
        if not junta:
            return jsonify({
                'ok': False,
                'error': f'Junta con ID {junta_id} no encontrada'
            }), 404
        
        # Obtener nombre de la junta para buscar el análisis
        junta_nombre = junta.get('nombre')
        analisis_file = f'juntas_analisis/{junta_nombre}_analisis.json'
        
        # Intentar leer el archivo de análisis para obtener distancia y punto medio
        if os.path.exists(analisis_file):
            try:
                with open(analisis_file, 'r', encoding='utf-8') as f:
                    analisis_completo = json.load(f)
                
                # Si el archivo existe, usar TODOS los datos del análisis completo
                # y solo complementar con datos de juntas.json si faltan
                analisis = analisis_completo
                
                # Asegurar que los campos necesarios existan
                if 'id' not in analisis:
                    analisis['id'] = junta.get('id')
                if 'nombre' not in analisis:
                    analisis['nombre'] = junta.get('nombre')
                if 'tiene_analisis' not in analisis:
                    analisis['tiene_analisis'] = True
                
                print(f"[juntas] ✓ Análisis completo cargado desde {analisis_file}")
                print(f"[juntas] Campos principales: {list(analisis.keys())}")
            except Exception as e:
                print(f"[juntas] ⚠️ Error leyendo análisis {analisis_file}: {e}")
                # Si falla, usar los datos básicos
                pass
        else:
            print(f"[juntas] ⚠️ Archivo de análisis no encontrado: {analisis_file}")
        
        print(f"[juntas] ✓ Análisis obtenido para junta {junta.get('nombre')} (ID: {junta_id})")
        
        # Asegurar que 'ok' sea True si existe el análisis
        analisis['ok'] = True
        
        return jsonify({
            'ok': True,
            'analisis': analisis
        })
    
    except Exception as e:
        print(f"[juntas] Error en GET /api/juntas/{{id}}/analisis: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/juntas/<int:junta_id>/full', methods=['GET'])
def api_get_junta_full(junta_id):
    """Retorna los datos completos de una junta específica para junta.html"""
    try:
        data = load_juntas()
        juntas = data.get('juntas', [])
        
        # Buscar junta por ID
        junta = next((j for j in juntas if j.get('id') == junta_id), None)
        
        if not junta:
            return jsonify({
                'ok': False,
                'error': f'Junta con ID {junta_id} no encontrada'
            }), 404
        
        print(f"[juntas] ✓ Datos completos de junta {junta.get('nombre')} (ID: {junta_id})")
        
        return jsonify({
            'ok': True,
            'junta': junta
        })
    
    except Exception as e:
        print(f"[juntas] Error en GET /api/juntas/{{id}}/full: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/juntas/<int:junta_id>', methods=['GET'])
def api_get_junta_by_id(junta_id):
    """Retorna los datos de una junta específica"""
    try:
        data = load_juntas()
        juntas = data.get('juntas', [])
        
        # Buscar junta por ID
        junta = next((j for j in juntas if j.get('id') == junta_id), None)
        
        if not junta:
            return jsonify({
                'ok': False,
                'error': f'Junta con ID {junta_id} no encontrada'
            }), 404
        
        print(f"[juntas] ✓ Junta obtenida: {junta.get('nombre')} (ID: {junta_id})")
        
        return jsonify({
            'ok': True,
            'junta': junta
        })
    
    except Exception as e:
        print(f"[juntas] Error en GET /api/juntas/{{id}}: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/juntas/<int:junta_id>', methods=['PUT'])
def api_update_junta_by_id(junta_id):
    """Actualiza una junta existente"""
    try:
        data = load_juntas()
        juntas = data.get('juntas', [])
        
        # Buscar junta por ID
        junta = next((j for j in juntas if j.get('id') == junta_id), None)
        
        if not junta:
            return jsonify({
                'ok': False,
                'error': f'Junta con ID {junta_id} no encontrada'
            }), 404
        
        # Obtener datos del request (FormData)
        form_data = request.form.to_dict()
        
        print(f"[juntas] Actualizando junta ID {junta_id} con campos: {list(form_data.keys())}")
        
        # Actualizar campos de la junta
        if 'nombre' in form_data:
            junta['nombre'] = form_data['nombre']
        
        if 'cantidad_muescas' in form_data:
            junta['cantidad_muescas'] = int(form_data.get('cantidad_muescas', 0))
        
        if 'muescaX' in form_data and form_data['muescaX']:
            if 'centros_muescas' not in junta:
                junta['centros_muescas'] = []
            if len(junta['centros_muescas']) == 0:
                junta['centros_muescas'].append({})
            junta['centros_muescas'][0]['centro_mm'] = [
                float(form_data.get('muescaX', 0)),
                float(form_data.get('muescaY', 0))
            ]
        
        if 'muescasVertical' in form_data:
            junta['muescas_vertical'] = form_data.get('muescasVertical') == 'on'
        
        # Actualizar Illinois
        if 'illinoisX' in form_data and form_data['illinoisX']:
            junta['illinois_x'] = float(form_data.get('illinoisX'))
            junta['illinois_y'] = float(form_data.get('illinoisY', 0))
            junta['illinois_vertical'] = form_data.get('illinoisVertical') == 'on'
        
        # Actualizar Código
        if 'codigoX' in form_data and form_data['codigoX']:
            junta['codigo_x'] = float(form_data.get('codigoX'))
            junta['codigo_y'] = float(form_data.get('codigoY', 0))
            junta['codigo_vertical'] = form_data.get('codigoVertical') == 'on'
        
        # Actualizar Lote
        if 'loteX' in form_data and form_data['loteX']:
            junta['lote_x'] = float(form_data.get('loteX'))
            junta['lote_y'] = float(form_data.get('loteY', 0))
            junta['lote_vertical'] = form_data.get('loteVertical') == 'on'
        
        # Guardar cambios
        if save_juntas(data):
            print(f"[juntas] ✓ Junta actualizada: {junta.get('nombre')} (ID: {junta_id})")
            return jsonify({
                'ok': True,
                'message': 'Junta actualizada correctamente',
                'junta': junta
            })
        else:
            return jsonify({
                'ok': False,
                'error': 'Error guardando junta'
            }), 500
    
    except Exception as e:
        print(f"[juntas] ❌ Error en PUT /api/juntas/{{id}}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/juntas/<int:junta_id>/imagen_con_muescas', methods=['GET', 'POST'])
def api_get_junta_imagen_con_muescas(junta_id):
    """Genera una imagen con los overlays (muescas, illinois, código y lote)"""
    try:
        import cv2
        import numpy as np
        
        # Obtener parámetros
        if request.method == 'POST':
            params = request.get_json() or {}
            print(f"[juntas] POST /api/juntas/{junta_id}/imagen_con_muescas con parámetros: {list(params.keys())}")
        else:
            params = {}
            print(f"[juntas] GET /api/juntas/{junta_id}/imagen_con_muescas (sin parámetros)")
        
        data = load_juntas()
        juntas = data.get('juntas', [])
        
        # Buscar junta por ID
        junta = next((j for j in juntas if j.get('id') == junta_id), None)
        
        if not junta:
            return jsonify({
                'ok': False,
                'error': f'Junta con ID {junta_id} no encontrada'
            }), 404
        
        # Obtener imagen de la junta
        imagen_path = f'imagenes_juntas/{junta.get("imagen")}'
        if not os.path.exists(imagen_path):
            print(f"[juntas] ❌ Imagen no encontrada: {imagen_path}")
            return jsonify({
                'ok': False,
                'error': f'Imagen no encontrada: {imagen_path}'
            }), 404
        
        # Leer imagen
        img = cv2.imread(imagen_path)
        if img is None:
            print(f"[juntas] ❌ Error leyendo imagen")
            return jsonify({
                'ok': False,
                'error': 'Error leyendo imagen'
            }), 500
        
        print(f"[juntas] ✓ Imagen cargada: {imagen_path}")
        
        # Obtener datos del análisis para el punto medio
        junta_nombre = junta.get('nombre')
        analisis_file = f'juntas_analisis/{junta_nombre}_analisis.json'
        
        punto_medio_px = None
        mm_por_pixel = junta.get('mm_por_pixel', 1.0)
        
        if os.path.exists(analisis_file):
            try:
                with open(analisis_file, 'r', encoding='utf-8') as f:
                    analisis_data = json.load(f)
                
                if 'linea_referencia' in analisis_data:
                    punto_medio = analisis_data['linea_referencia'].get('punto_medio_px')
                    if punto_medio:
                        punto_medio_px = tuple(punto_medio)
                        print(f"[juntas] ✓ Punto medio encontrado: {punto_medio_px}")
                    mm_por_pixel = analisis_data.get('parametros', {}).get('mm_por_pixel', mm_por_pixel)
                    print(f"[juntas] ✓ Escala: {mm_por_pixel} mm/px")
            except Exception as e:
                print(f"[juntas] ❌ Error leyendo análisis: {e}")
        else:
            print(f"[juntas] ❌ Archivo de análisis no encontrado: {analisis_file}")
        
        if punto_medio_px is None:
            print(f"[juntas] ❌ No se encontró punto medio del segmento")
            return jsonify({
                'ok': False,
                'error': 'No se encontró punto medio del segmento en el análisis'
            }), 400
        
        # Si es GET, usar valores guardados de la junta
        if request.method == 'GET':
            params = {
                'cantidad_muescas': junta.get('cantidad_muescas', 0),
                'muesca_x': None,
                'muesca_y': None,
                'vertical': junta.get('muescas_vertical', False),
                'illinois_x': junta.get('illinois_x'),
                'illinois_y': junta.get('illinois_y'),
                'illinois_vertical': junta.get('illinois_vertical', False),
                'codigo_x': junta.get('codigo_x'),
                'codigo_y': junta.get('codigo_y'),
                'codigo_vertical': junta.get('codigo_vertical', False),
                'lote_x': junta.get('lote_x'),
                'lote_y': junta.get('lote_y'),
                'lote_vertical': junta.get('lote_vertical', False)
            }
            
            # Obtener coordenadas de la primera muesca
            if junta.get('centros_muescas') and len(junta.get('centros_muescas', [])) > 0:
                primer_centro = junta['centros_muescas'][0].get('centro_mm')
                if primer_centro:
                    params['muesca_x'] = primer_centro[0]
                    params['muesca_y'] = primer_centro[1]
            
            print(f"[juntas] GET: Usando valores guardados: cantidad={params['cantidad_muescas']}")
        else:
            # Si es POST, hacer fallback a valores guardados para parámetros null
            saved_muescas = 0
            saved_muesca_x = None
            saved_muesca_y = None
            if junta.get('centros_muescas') and len(junta.get('centros_muescas', [])) > 0:
                saved_muescas = junta.get('cantidad_muescas', 0)
                primer_centro = junta['centros_muescas'][0].get('centro_mm')
                if primer_centro:
                    saved_muesca_x = primer_centro[0]
                    saved_muesca_y = primer_centro[1]
            
            # Aplicar fallback para valores null
            if params.get('cantidad_muescas') is None:
                params['cantidad_muescas'] = saved_muescas
            if params.get('muesca_x') is None:
                params['muesca_x'] = saved_muesca_x
            if params.get('muesca_y') is None:
                params['muesca_y'] = saved_muesca_y
            
            if params.get('illinois_x') is None:
                params['illinois_x'] = junta.get('illinois_x')
            if params.get('illinois_y') is None:
                params['illinois_y'] = junta.get('illinois_y')
            if params.get('illinois_vertical') is None:
                params['illinois_vertical'] = junta.get('illinois_vertical', False)
            
            if params.get('codigo_x') is None:
                params['codigo_x'] = junta.get('codigo_x')
            if params.get('codigo_y') is None:
                params['codigo_y'] = junta.get('codigo_y')
            if params.get('codigo_vertical') is None:
                params['codigo_vertical'] = junta.get('codigo_vertical', False)
            
            if params.get('lote_x') is None:
                params['lote_x'] = junta.get('lote_x')
            if params.get('lote_y') is None:
                params['lote_y'] = junta.get('lote_y')
            if params.get('lote_vertical') is None:
                params['lote_vertical'] = junta.get('lote_vertical', False)
            
            print(f"[juntas] POST: Aplicando fallback a valores guardados")
        
        # Dibujar muescas si hay parámetros
        if params.get('cantidad_muescas', 0) > 0 and params.get('muesca_x') is not None:
            print(f"[juntas] Dibujando {params['cantidad_muescas']} muescas")
            img = muescas_renderer.dibujar_muescas(
                img,
                cantidad_muescas=params.get('cantidad_muescas', 0),
                muesca_x_mm=params.get('muesca_x', 0),
                muesca_y_mm=params.get('muesca_y', 0),
                punto_medio_px=punto_medio_px,
                mm_por_pixel=mm_por_pixel,
                vertical=params.get('vertical', False)
            )
        
        # Dibujar textos (Illinois, Código, Lote)
        if params.get('illinois_x') is not None and params.get('illinois_y') is not None:
            print(f"[juntas] Dibujando ILLINOIS en ({params['illinois_x']}, {params['illinois_y']})")
            img = textos_renderer.dibujar_texto_simple(
                img,
                'ILLINOIS',
                x_mm=params.get('illinois_x', 0),
                y_mm=params.get('illinois_y', 0),
                punto_medio_px=punto_medio_px,
                mm_por_pixel=mm_por_pixel,
                vertical=params.get('illinois_vertical', False)
            )
        
        if params.get('codigo_x') is not None and params.get('codigo_y') is not None:
            print(f"[juntas] Dibujando CODIGO en ({params['codigo_x']}, {params['codigo_y']})")
            img = textos_renderer.dibujar_texto_simple(
                img,
                'CODIGO',
                x_mm=params.get('codigo_x', 0),
                y_mm=params.get('codigo_y', 0),
                punto_medio_px=punto_medio_px,
                mm_por_pixel=mm_por_pixel,
                vertical=params.get('codigo_vertical', False)
            )
        
        if params.get('lote_x') is not None and params.get('lote_y') is not None:
            print(f"[juntas] Dibujando LOTE en ({params['lote_x']}, {params['lote_y']})")
            img = textos_renderer.dibujar_texto_simple(
                img,
                'LOTE',
                x_mm=params.get('lote_x', 0),
                y_mm=params.get('lote_y', 0),
                punto_medio_px=punto_medio_px,
                mm_por_pixel=mm_por_pixel,
                vertical=params.get('lote_vertical', False)
            )
        
        # Convertir imagen a JPEG base64
        ret, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ret:
            print(f"[juntas] ❌ Error codificando imagen")
            return jsonify({
                'ok': False,
                'error': 'Error codificando imagen'
            }), 500
        
        imagen_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
        
        print(f"[juntas] ✓ Imagen con overlays generada exitosamente")
        
        return jsonify({
            'ok': True,
            'imagen_con_muescas': imagen_base64
        })
    
    except Exception as e:
        print(f"[juntas] ❌ Error en /api/juntas/{junta_id}/imagen_con_muescas: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/juntas/parametrizar', methods=['POST'])
def api_juntas_parametrizar():
    """Parametriza una imagen: detecta junta, hace análisis y guarda visualización"""
    try:
        import cv2
        import numpy as np
        from io import BytesIO
        
        print(f"[parametrizar] ▶ Iniciando parametrización...")
        
        # Obtener imagen del request
        imagen_file = request.files.get('imagen')
        if not imagen_file:
            return jsonify({'ok': False, 'error': 'No se proporcionó imagen'}), 400
        
        # Parámetros
        nombre_junta = request.form.get('nombre_junta')
        junta_id = request.form.get('junta_id', type=int)
        mm_por_pixel_manual = request.form.get('mm_por_pixel_manual', type=float)
        
        print(f"[parametrizar] Junta: {nombre_junta}, ID: {junta_id}")
        
        # Leer imagen
        imagen_bytes = imagen_file.read()
        nparr = np.frombuffer(imagen_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({'ok': False, 'error': 'Error decodificando imagen'}), 400
        
        print(f"[parametrizar] ✓ Imagen cargada: {img.shape}")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 1: Detectar fondo (negro/blanco)
        # ═══════════════════════════════════════════════════════════════════
        
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Contar píxeles oscuros (fondo negro) vs claros (fondo blanco)
        oscuros = np.sum(img_gray < 50)
        claros = np.sum(img_gray > 200)
        
        fondo_negro = oscuros > claros
        fondo_detectado = "Negro" if fondo_negro else "Blanco"
        
        print(f"[parametrizar] ✓ Fondo detectado: {fondo_detectado}")
        
        # Crear versión con fondo negro y blanco
        if fondo_negro:
            img_fondo_blanco = cv2.bitwise_not(img)
            img_fondo_negro = img.copy()
        else:
            img_fondo_negro = cv2.bitwise_not(img)
            img_fondo_blanco = img.copy()
        
        # Convertir a escala de grises para análisis
        img_fondo_blanco_gray = cv2.cvtColor(img_fondo_blanco, cv2.COLOR_BGR2GRAY)
        img_fondo_negro_gray = cv2.cvtColor(img_fondo_negro, cv2.COLOR_BGR2GRAY)
        
        # Codificar imágenes
        _, buf_negro = cv2.imencode('.jpg', img_fondo_negro, [cv2.IMWRITE_JPEG_QUALITY, 90])
        imagen_fondo_negro_b64 = base64.b64encode(buf_negro.tobytes()).decode('utf-8')
        
        _, buf_blanco = cv2.imencode('.jpg', img_fondo_blanco, [cv2.IMWRITE_JPEG_QUALITY, 90])
        imagen_fondo_blanco_b64 = base64.b64encode(buf_blanco.tobytes()).decode('utf-8')
        
        print(f"[parametrizar] ✓ Imágenes con fondos generadas")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 2: Ejecutar análisis de contornos
        # ═══════════════════════════════════════════════════════════════════
        
        import contornos_analyzer
        
        # Usar imagen con fondo blanco para análisis
        mm_por_pixel = mm_por_pixel_manual if mm_por_pixel_manual else 0.1
        
        analisis_data = contornos_analyzer.analizar_imagen_completa(img_fondo_blanco_gray, mm_por_pixel, verbose=False)
        
        if not analisis_data.get('ok'):
            print(f"[parametrizar] ⚠️ Análisis no completado: {analisis_data.get('error')}")
            return jsonify({
                'ok': True,
                'imagen_fondo_negro': imagen_fondo_negro_b64,
                'imagen_fondo_blanco': imagen_fondo_blanco_b64,
                'fondo_detectado': fondo_detectado,
                'analisis': {'ok': False, 'error': analisis_data.get('error', 'Análisis no completado')}
            })
        
        print(f"[parametrizar] ✓ Análisis completado")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 3: Convertir numpy arrays a listas (para serialización JSON)
        # ═══════════════════════════════════════════════════════════════════
        
        def convert_numpy_to_python(obj):
            """Convierte recursivamente numpy arrays y tipos a tipos Python"""
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, dict):
                return {k: convert_numpy_to_python(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_numpy_to_python(item) for item in obj]
            else:
                return obj
        
        # Convertir el análisis
        analisis_data_serializable = convert_numpy_to_python(analisis_data)
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 4: Crear visualización con contornos clasificados
        # ═══════════════════════════════════════════════════════════════════
        
        imagen_visualization = contornos_analyzer.crear_visualizacion(img_fondo_blanco_gray, analisis_data)
        
        if imagen_visualization is None:
            print(f"[parametrizar] ⚠️ No se pudo crear visualización")
            imagen_visualization_b64 = None
            imagen_visualization_bytes = None
        else:
            _, buf_viz = cv2.imencode('.jpg', imagen_visualization, [cv2.IMWRITE_JPEG_QUALITY, 95])
            imagen_visualization_bytes = buf_viz.tobytes()
            imagen_visualization_b64 = base64.b64encode(imagen_visualization_bytes).decode('utf-8')
            print(f"[parametrizar] ✓ Visualización con contornos generada")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 5: Guardar visualización y análisis a disco
        # ═══════════════════════════════════════════════════════════════════
        
        if nombre_junta and imagen_visualization_bytes:
            # Crear directorio si no existe
            os.makedirs('juntas_analisis', exist_ok=True)
            
            # Guardar imagen de visualización
            viz_path = f'juntas_analisis/{nombre_junta}_visualizacion.jpg'
            cv2.imwrite(viz_path, imagen_visualization)
            print(f"[parametrizar] ✓ Visualización guardada: {viz_path}")
            
            # Guardar análisis completo
            analisis_path = f'juntas_analisis/{nombre_junta}_analisis.json'
            with open(analisis_path, 'w', encoding='utf-8') as f:
                json.dump(analisis_data_serializable, f, indent=2, ensure_ascii=False)
            print(f"[parametrizar] ✓ Análisis guardado: {analisis_path}")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 6: Actualizar juntas.json con datos del análisis
        # ═══════════════════════════════════════════════════════════════════
        
        if junta_id:
            try:
                juntas_data = load_juntas()
                juntas = juntas_data.get('juntas', [])
                
                # Buscar y actualizar la junta
                for junta in juntas:
                    if junta.get('id') == junta_id:
                        # Guardar datos del análisis en la junta
                        junta['tiene_analisis'] = True
                        junta['mm_por_pixel'] = analisis_data_serializable.get('parametros', {}).get('mm_por_pixel', mm_por_pixel)
                        
                        # Guardar momentos de Hu
                        if 'momentos_hu' in analisis_data_serializable:
                            junta['momentos_hu'] = analisis_data_serializable['momentos_hu']
                        
                        # Guardar contorno principal
                        if 'contorno_principal' in analisis_data_serializable:
                            junta['contorno_principal'] = analisis_data_serializable['contorno_principal']
                        
                        # Guardar agujeros analizados
                        if 'agujeros' in analisis_data_serializable:
                            junta['agujeros'] = analisis_data_serializable['agujeros']
                        
                        # Guardar línea de referencia
                        if 'linea_referencia' in analisis_data_serializable:
                            junta['linea_referencia'] = analisis_data_serializable['linea_referencia']
                        
                        # Guardar resumen del análisis
                        if 'resumen_analisis' in analisis_data_serializable:
                            junta['resumen_analisis'] = analisis_data_serializable['resumen_analisis']
                        
                        # Guardar cantidad de muescas
                        if 'cantidad_muescas' in analisis_data_serializable:
                            junta['cantidad_muescas'] = analisis_data_serializable['cantidad_muescas']
                        
                        # Guardar centros de muescas
                        if 'centros_muescas' in analisis_data_serializable:
                            junta['centros_muescas'] = analisis_data_serializable['centros_muescas']
                        
                        print(f"[parametrizar] ✓ Actualizando datos de junta ID {junta_id}")
                        break
                
                # Guardar cambios en juntas.json
                if save_juntas(juntas_data):
                    print(f"[parametrizar] ✓ juntas.json actualizado")
                else:
                    print(f"[parametrizar] ⚠️ Error guardando juntas.json")
            
            except Exception as e:
                print(f"[parametrizar] ⚠️ Error actualizando juntas.json: {e}")
        
        print(f"[parametrizar] ✓ Parametrización completada exitosamente")
        
        return jsonify({
            'ok': True,
            'imagen_fondo_negro': imagen_fondo_negro_b64,
            'imagen_fondo_blanco': imagen_fondo_blanco_b64,
            'imagen_visualizacion': imagen_visualization_b64,
            'fondo_detectado': fondo_detectado,
            'analisis': analisis_data_serializable
        })
    
    except Exception as e:
        print(f"[parametrizar] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

# ============================================================
# API VISIÓN
# ============================================================
CONFIG_FILE = 'config.json'

def load_config():
    """Carga la configuración completa desde config.json"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[vision] Error cargando configuración: {e}")
    return {'vision': {}}

def save_config(config_data):
    """Guarda la configuración completa en config.json"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        print(f"[vision] ✓ Configuración guardada")
        return True
    except Exception as e:
        print(f"[vision] ❌ Error guardando configuración: {e}")
        return False

@app.route('/api/vision/config', methods=['GET'])
def api_get_vision_config():
    """Obtiene la configuración actual de visión"""
    try:
        config = load_config()
        vision_config = config.get('vision', {})
        
        print(f"[vision] ✓ Configuración cargada: {list(vision_config.keys())}")
        
        return jsonify({
            'ok': True,
            'vision': vision_config
        })
    
    except Exception as e:
        print(f"[vision] ❌ Error en GET /api/vision/config: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/vision/set_models', methods=['POST'])
def api_set_vision_models():
    """Actualiza la configuración de modelos y opciones de visión"""
    try:
        data = request.get_json()
        
        # Cargar configuración actual
        config = load_config()
        
        # Asegurar que existe la sección vision
        if 'vision' not in config:
            config['vision'] = {}
        
        # Actualizar campos de visión
        if 'detection_model' in data:
            config['vision']['detection_model'] = data['detection_model']
        
        if 'holes_model' in data:
            config['vision']['holes_model'] = data['holes_model']
        
        if 'enabled' in data:
            config['vision']['detection_enabled'] = data['enabled']
        
        if 'show_bbox' in data:
            config['vision']['show_bbox'] = data['show_bbox']
        
        if 'show_contours' in data:
            config['vision']['show_contours'] = data['show_contours']
        
        if 'show_ellipses' in data:
            config['vision']['show_ellipses'] = data['show_ellipses']
        
        if 'show_notches' in data:
            config['vision']['show_notches'] = data['show_notches']
        
        # Umbrales de validación
        if 'umbral_distancia_tolerancia' in data:
            config['vision']['umbral_distancia_tolerancia'] = data['umbral_distancia_tolerancia']
        
        if 'umbral_centros_mm' in data:
            config['vision']['umbral_centros_mm'] = data['umbral_centros_mm']
        
        if 'umbral_colinealidad_mm' in data:
            config['vision']['umbral_colinealidad_mm'] = data['umbral_colinealidad_mm']
        
        if 'umbral_espaciado_cv' in data:
            config['vision']['umbral_espaciado_cv'] = data['umbral_espaciado_cv']
        
        # Guardar configuración
        if save_config(config):
            print(f"[vision] ✓ Configuración de modelos actualizada")
            return jsonify({
                'ok': True,
                'message': 'Configuración guardada correctamente'
            })
        else:
            return jsonify({
                'ok': False,
                'error': 'Error guardando configuración'
            }), 500
    
    except Exception as e:
        print(f"[vision] ❌ Error en POST /api/vision/set_models: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

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
                print(f"[yolo] ❌ Error cargando Detection: {detection_model_path}")
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
                print(f"[yolo] ❌ Error cargando Holes: {holes_model_path}")
        else:
            print(f"[yolo] ⚠️ Archivo no encontrado: {holes_model_path}")
    else:
        print(f"[yolo] ⚠️ No configurado modelo Holes en config.json")

@app.route('/api/vision/models_status', methods=['GET'])
def api_get_models_status():
    """Retorna el estado de carga de los modelos YOLO"""
    try:
        detection_loaded = yolo_detector.is_model_loaded('detection')
        holes_loaded = yolo_detector.is_model_loaded('holes')
        detection_path = yolo_detector.get_model_path('detection')
        holes_path = yolo_detector.get_model_path('holes')
        
        print(f"[yolo] Estado de modelos - Detection: {detection_loaded}, Holes: {holes_loaded}")
        
        return jsonify({
            'ok': True,
            'models': {
                'detection': {
                    'loaded': detection_loaded,
                    'path': detection_path
                },
                'holes': {
                    'loaded': holes_loaded,
                    'path': holes_path
                }
            }
        })
    
    except Exception as e:
        print(f"[yolo] ❌ Error en GET /api/vision/models_status: {e}")
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

# ============================================================
# API ANÁLISIS DE JUNTAS
# ============================================================

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """Ejecuta análisis completo de la junta seleccionada con reintentos"""
    global _analisis_junta_actual, _visualizacion_junta_actual, _fondo_detectado_junta_actual, _analisis_serializable_junta_actual
    
    try:
        print("\n[análisis] 🚀 POST /api/analyze iniciado")
        
        # Obtener junta seleccionada
        juntas_data = load_juntas()
        selected_id = juntas_data.get('selected_id')
        
        if not selected_id:
            print("[análisis] ❌ No hay junta seleccionada")
            return jsonify({
                'ok': False,
                'error': 'No hay junta seleccionada'
            }), 400
        
        # Obtener frame actual de la cámara
        frame = camera_manager.get_frame_raw()
        if frame is None:
            print("[análisis] ❌ No se pudo obtener frame de la cámara")
            return jsonify({
                'ok': False,
                'error': 'Cámara no disponible'
            }), 500
        
        print(f"[análisis] ✓ Frame capturado: {frame.shape}")
        
        # Ejecutar análisis con reintentos
        exito, imagen_bytes, datos = pipeline_analisis.analizar_con_reintentos(frame, max_intentos=3)
        
        print(f"[análisis] 📊 Análisis completado - Exitoso: {exito}")
        print(f"[análisis] 📊 Datos obtenidos: {list(datos.keys())}")
        
        # Guardar globalmente para /api/analyze_result
        _analisis_junta_actual = datos
        _visualizacion_junta_actual = imagen_bytes
        _analisis_serializable_junta_actual = _convertir_numpy_a_python(datos)
        
        # Retornar resultado
        return jsonify({
            'ok': True,
            'analisis_exitoso': exito,
            'error': datos.get('error'),
            'data': _analisis_serializable_junta_actual
        })
    
    except Exception as e:
        print(f"[análisis] ❌ Error en POST /api/analyze: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/analyze_result', methods=['GET'])
def api_analyze_result():
    """Retorna la imagen del último análisis en base64"""
    global _visualizacion_junta_actual
    
    try:
        print("[análisis] GET /api/analyze_result solicitado")
        
        if _visualizacion_junta_actual is None:
            print("[análisis] ⚠️ No hay imagen analizada disponible")
            return jsonify({
                'ok': False,
                'error': 'No hay imagen analizada disponible'
            }), 400
        
        # Convertir bytes a base64 si es necesario
        if isinstance(_visualizacion_junta_actual, bytes):
            image_b64 = base64.b64encode(_visualizacion_junta_actual).decode('utf-8')
        else:
            image_b64 = _visualizacion_junta_actual
        
        print(f"[análisis] ✓ Imagen retornada ({len(image_b64)} caracteres en base64)")
        
        return jsonify({
            'ok': True,
            'image': f'data:image/jpeg;base64,{image_b64}'
        })
    
    except Exception as e:
        print(f"[análisis] ❌ Error en GET /api/analyze_result: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

# ============================================================
# UTILIDADES
# ============================================================

def _convertir_numpy_a_python(obj):
    """Convierte arrays numpy a listas Python para JSON serialization"""
    import numpy as np
    
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convertir_numpy_a_python(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convertir_numpy_a_python(item) for item in obj]
    else:
        return obj

# ============================================================
# GESTIÓN DE CHROME
# ============================================================
def launch_chrome(url: str, kiosk: bool = False):
    """Lanza Chrome con la URL especificada y guarda el PID."""
    global chrome_pid
    
    try:
        # Verificar si Chrome existe
        if not os.path.exists(CHROME_PATH):
            print(f"❌ Chrome no encontrado en: {CHROME_PATH}")
            return None
        
        # Crear directorio de perfil aislado
        profile_dir = os.path.join(os.getcwd(), ".chrome_profile")
        os.makedirs(profile_dir, exist_ok=True)
        
        # Argumentos de Chrome
        window_name = "COMAU-VISION"
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
        print(f"❌ Chrome no encontrado en: {CHROME_PATH}")
        return None
    except Exception as e:
        print(f"❌ Error lanzando Chrome: {e}")
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
        print(f"❌ Error cerrando Chrome: {e}")

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
        print(f"❌ Error durante el cierre: {e}")
    
    finally:
        # Salir del proceso
        print("👋 Adiós!")
        sys.exit(0)

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
    
    # ═══════════════════════════════════════════════════════════════
    # PASO 1: Iniciar Flask en un thread daemon
    # ═══════════════════════════════════════════════════════════════
    print(f"\n🔄 Iniciando servidor Flask en thread daemon...")
    
    def run_flask():
        """Ejecutar Flask en thread separado"""
        try:
            app.run(host='0.0.0.0', port=args.port, debug=False, use_reloader=False)
        except Exception as e:
            print(f"❌ Error en Flask: {e}")
    
    flask_thread = threading.Thread(target=run_flask, daemon=True, name="FlaskServer")
    flask_thread.start()
    
    # Esperar a que Flask inicie
    time.sleep(1)
    print(f"✅ Flask iniciado en thread daemon")
    
    # ═══════════════════════════════════════════════════════════════
    # PASO 1.5: Intentar conectar a la cámara
    # ═══════════════════════════════════════════════════════════════
    print(f"\n🎥 Intentando conectar a la cámara...")
    try:
        success, message = camera_manager.connectToCamera()
        if success:
            print(f"✅ {message}")
        else:
            print(f"⚠️  {message}")
    except Exception as e:
        print(f"❌ Error conectando a cámara: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # PASO 1.7: Inicializar modelos YOLO (GLOBAL)
    # ═══════════════════════════════════════════════════════════════
    initialize_yolo_models()
    
    # ═══════════════════════════════════════════════════════════════
    # PASO 2: Lanzar Chrome
    # ═══════════════════════════════════════════════════════════════
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
        
        # ═══════════════════════════════════════════════════════════════
        # PASO 3: Monitorear Chrome - BLOQUEANTE
        # ═══════════════════════════════════════════════════════════════
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
            print(f"❌ Error: {e}")
            close_chrome()
            sys.exit(1)

if __name__ == '__main__':
    main()
