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
        
        # Detectar TODOS los ArUcos en la imagen
        all_arucos_result = detect_all_arucos(cv2_frame, marker_size_mm=frame_marker_size)
        
        # Si no hay ArUcos, retornar error
        if all_arucos_result is None or len(all_arucos_result.get('detected_ids', [])) == 0:
            return jsonify({
                'ok': False,
                'error': 'No se detectó ningún marcador ArUco en el frame'
            }), 400
        
        detected_ids = all_arucos_result.get('detected_ids', [])
        detected_markers = all_arucos_result.get('markers', [])
        
        print(f"[overlay] Todos los ArUcos detectados: {detected_ids}")
        
        # Buscar Frame y Tool en los detectados
        frame_result = detect_aruco_by_id(cv2_frame, frame_aruco_id, marker_size_mm=frame_marker_size)
        tool_result = detect_aruco_by_id(cv2_frame, tool_aruco_id, marker_size_mm=tool_marker_size)
        
        # Se requiere el Frame para la calibración
        if frame_result is None:
            detected_str = ', '.join(str(id) for id in detected_ids)
            return jsonify({
                'ok': False,
                'error': f'ArUco_Frame({frame_aruco_id}) no detectado. Se requiere Frame para la calibración.\nArUcos detectados: [{detected_str}]'
            }), 400
        
        print(f"[overlay] Frame detectado: ID={frame_aruco_id}, px_per_mm={frame_result['px_per_mm']:.3f}")
        if tool_result is not None:
            print(f"[overlay] Tool detectado: ID={tool_aruco_id}, px_per_mm={tool_result['px_per_mm']:.3f}")
        
        # Detectar ArUcos adicionales que no sean Frame ni Tool
        other_arucos = [aruco_id for aruco_id in detected_ids if aruco_id != frame_aruco_id and aruco_id != tool_aruco_id]
        info_message = None
        if other_arucos:
            other_str = ', '.join(str(id) for id in other_arucos)
            info_message = f'Se hallaron ArUcos adicionales: [{other_str}]'
            print(f"[overlay] ⚠️ {info_message}")
        
        # La calibración SIEMPRE viene del Frame
        px_per_mm_frame = frame_result['px_per_mm']
        angle_rad = np.arctan2(frame_result['rotation_matrix'][1][0], frame_result['rotation_matrix'][0][0])
        
        datos_aruco = {
            'center': frame_result['center'],  # Centro del Frame para calibración
            'angle_rad': float(angle_rad),
            'corners': frame_result['corners'],
            'px_per_mm': px_per_mm_frame,  # SIEMPRE del Frame
            'frame_result': frame_result,  # Pasar Frame completo
            'tool_result': tool_result if tool_result is not None else None,  # Pasar Tool si existe
            'all_detected_ids': detected_ids,  # NUEVO: Todos los IDs detectados
            'all_detected_markers': detected_markers  # NUEVO: Todos los marcadores detectados
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
        
        response = {
            'ok': True,
            'message': 'Overlay mostrado en dashboard por 3 segundos'
        }
        
        # Agregar información de ArUcos adicionales si existen
        if info_message:
            response['info'] = info_message
        
        return jsonify(response)
    
    except Exception as e:
        print(f"[aruco] Error en POST /api/aruco/draw_overlay: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

@app.route('/api/overlay/render', methods=['POST'])
def api_overlay_render():
    """Endpoint genérico para renderizar overlays usando OverlayManager"""
    try:
        import cv2
        import numpy as np
        
        # Importar OverlayManager
        from overlay_manager import OverlayManager
        
        # Obtener configuración de ArUcos
        config = load_aruco_config()
        aruco_config = config.get('aruco', {})
        
        frame_aruco_id = aruco_config.get('frame_aruco_id', 0)
        tool_aruco_id = aruco_config.get('tool_aruco_id', 0)
        
        # Obtener frame actual de la cámara
        cv2_frame = camera_manager.get_frame_raw()
        
        if cv2_frame is None:
            return jsonify({
                'ok': False,
                'error': 'No hay frame disponible de la cámara'
            }), 400
        
        # Convertir a escala de grises SOLO para detección de ArUcos
        gray_frame = cv2.cvtColor(cv2_frame, cv2.COLOR_BGR2GRAY)
        
        # Debug: información de la imagen
        print(f"[overlay] Imagen capturada:")
        print(f"  - Dimensiones RGB: {cv2_frame.shape}")
        print(f"  - Dimensiones Gray: {gray_frame.shape}")
        print(f"  - Tipo RGB: {cv2_frame.dtype}, Gray: {gray_frame.dtype}")
        print(f"  - Rango RGB: {cv2_frame.min()} - {cv2_frame.max()}")
        print(f"  - Rango Gray: {gray_frame.min()} - {gray_frame.max()}")
        print(f"  - Canales RGB: {cv2_frame.shape[2] if len(cv2_frame.shape) == 3 else 'N/A'}")
        
        # Crear instancia de OverlayManager
        overlay_manager = OverlayManager()
        
        # Detectar ArUcos usando el mismo método que el código original
        frame_marker_size = aruco_config.get('frame_marker_size_mm', 70.0)
        tool_marker_size = aruco_config.get('tool_marker_size_mm', 50.0)
        
        # Detectar TODOS los ArUcos en la imagen RGB (mismo método que el original)
        all_arucos_result = detect_all_arucos(cv2_frame, marker_size_mm=frame_marker_size)
        
        # Debug: mostrar información de detección
        print(f"[overlay] Detección de ArUcos (método original):")
        if all_arucos_result is not None:
            detected_ids = all_arucos_result.get('detected_ids', [])
            print(f"  - IDs detectados: {detected_ids}")
        else:
            detected_ids = []
            print(f"  - ⚠️ No se detectó ningún ArUco en la imagen")
        
        # Buscar Frame y Tool específicos (mismo método que el original)
        frame_result = detect_aruco_by_id(cv2_frame, frame_aruco_id, marker_size_mm=frame_marker_size)
        tool_result = detect_aruco_by_id(cv2_frame, tool_aruco_id, marker_size_mm=tool_marker_size)
        
        frame_detected = frame_result is not None
        tool_detected = tool_result is not None
        
        print(f"  - Frame ArUco (ID: {frame_aruco_id}) detectado: {frame_detected}")
        print(f"  - Tool ArUco (ID: {tool_aruco_id}) detectado: {tool_detected}")
        
        # Crear resultado en formato compatible con OverlayManager
        detection_result = {
            'detected_arucos': {},
            'detected_ids': detected_ids,
            'frame_detected': frame_detected,
            'tool_detected': tool_detected,
            'frame_aruco_id': frame_aruco_id,
            'tool_aruco_id': tool_aruco_id,
            'frame_result': frame_result,
            'tool_result': tool_result
        }
        
        # Crear marcos temporales si no existen
        if not overlay_manager.frames.get("base_frame_temp"):
            overlay_manager.define_frame("base_frame_temp", offset=(0, 0), rotation=0.0, 
                                       px_per_mm=1.0, is_temporary=True)
        if not overlay_manager.frames.get("tool_frame_temp"):
            overlay_manager.define_frame("tool_frame_temp", offset=(0, 0), rotation=0.0, 
                                       px_per_mm=1.0, is_temporary=True)
        
        # Crear/actualizar marcos temporales desde ArUcos detectados
        if frame_detected and frame_result:
            # Crear marco temporal del Frame ArUco
            frame_center = frame_result['center']
            frame_angle = np.arctan2(frame_result['rotation_matrix'][1][0], frame_result['rotation_matrix'][0][0])
            frame_px_per_mm = frame_result['px_per_mm']
            
            overlay_manager.define_frame(
                "base_frame_temp", 
                offset=(frame_center[0], frame_center[1]), 
                rotation=frame_angle,
                px_per_mm=frame_px_per_mm,
                is_temporary=True
            )
            print(f"[overlay] Marco base_frame_temp creado: center=({frame_center[0]:.1f}, {frame_center[1]:.1f}), angle={frame_angle:.3f}rad, px_per_mm={frame_px_per_mm:.3f}")
        
        if tool_detected and tool_result:
            # Crear marco temporal del Tool ArUco
            tool_center = tool_result['center']
            tool_angle = np.arctan2(tool_result['rotation_matrix'][1][0], tool_result['rotation_matrix'][0][0])
            tool_px_per_mm = tool_result['px_per_mm']
            
            overlay_manager.define_frame(
                "tool_frame_temp", 
                offset=(tool_center[0], tool_center[1]), 
                rotation=tool_angle,
                px_per_mm=tool_px_per_mm,
                is_temporary=True
            )
            print(f"[overlay] Marco tool_frame_temp creado: center=({tool_center[0]:.1f}, {tool_center[1]:.1f}), angle={tool_angle:.3f}rad, px_per_mm={tool_px_per_mm:.3f}")
        
        # Crear objetos de overlay para ArUcos usando coordenadas absolutas
        if frame_detected and frame_result:
            # Crear objetos para Frame ArUco usando coordenadas absolutas
            frame_center = frame_result['center']
            frame_corners = frame_result['corners']
            frame_angle = np.arctan2(frame_result['rotation_matrix'][1][0], frame_result['rotation_matrix'][0][0])
            
            # Contorno del Frame ArUco (coordenadas absolutas)
            overlay_manager.add_polygon(
                "Base",  # Usar marco Base para coordenadas absolutas
                points=frame_corners,
                name=f"aruco_contour_{frame_aruco_id}",
                color=(0, 255, 255),  # Amarillo para Frame
                thickness=2
            )
            
            # Ejes del Frame ArUco (coordenadas absolutas)
            # Hacer ejes muy largos para que lleguen a los bordes de la imagen
            image_height, image_width = cv2_frame.shape[:2]
            axis_length = max(image_width, image_height)  # Largo suficiente para cubrir toda la imagen
            print(f"[overlay] Ejes Frame ArUco: longitud={axis_length}px (imagen: {image_width}x{image_height})")
            x_end1 = (
                frame_center[0] + axis_length * np.cos(frame_angle),
                frame_center[1] + axis_length * np.sin(frame_angle)
            )
            x_end2 = (
                frame_center[0] - axis_length * np.cos(frame_angle),
                frame_center[1] - axis_length * np.sin(frame_angle)
            )
            
            y_angle = frame_angle + np.pi / 2
            y_end1 = (
                frame_center[0] + axis_length * np.cos(y_angle),
                frame_center[1] + axis_length * np.sin(y_angle)
            )
            y_end2 = (
                frame_center[0] - axis_length * np.cos(y_angle),
                frame_center[1] - axis_length * np.sin(y_angle)
            )
            
            overlay_manager.add_line(
                "Base",  # Usar marco Base para coordenadas absolutas
                start=x_end2,
                end=x_end1,
                name=f"aruco_x_axis_{frame_aruco_id}",
                color=(0, 255, 255),
                thickness=2
            )
            
            overlay_manager.add_line(
                "Base",  # Usar marco Base para coordenadas absolutas
                start=y_end2,
                end=y_end1,
                name=f"aruco_y_axis_{frame_aruco_id}",
                color=(0, 255, 255),
                thickness=2
            )
            
            # Centro del Frame ArUco (coordenadas absolutas)
            overlay_manager.add_circle(
                "Base",  # Usar marco Base para coordenadas absolutas
                center=frame_center,  # Centro absoluto
                radius=5,
                name=f"aruco_center_{frame_aruco_id}",
                color=(0, 255, 255),
                filled=True
            )
            
            print(f"[overlay] Objetos de overlay creados para Frame ArUco {frame_aruco_id} en coordenadas absolutas")
        
        if tool_detected and tool_result:
            # Crear objetos para Tool ArUco usando coordenadas absolutas
            tool_center = tool_result['center']
            tool_corners = tool_result['corners']
            tool_angle = np.arctan2(tool_result['rotation_matrix'][1][0], tool_result['rotation_matrix'][0][0])
            
            # Contorno del Tool ArUco (coordenadas absolutas)
            overlay_manager.add_polygon(
                "Base",  # Usar marco Base para coordenadas absolutas
                points=tool_corners,
                name=f"aruco_contour_{tool_aruco_id}",
                color=(255, 0, 0),  # Azul para Tool
                thickness=2
            )
            
            # Ejes del Tool ArUco (coordenadas absolutas)
            # Hacer ejes muy largos para que lleguen a los bordes de la imagen
            image_height, image_width = cv2_frame.shape[:2]
            axis_length = max(image_width, image_height)  # Largo suficiente para cubrir toda la imagen
            print(f"[overlay] Ejes Tool ArUco: longitud={axis_length}px (imagen: {image_width}x{image_height})")
            x_end1 = (
                tool_center[0] + axis_length * np.cos(tool_angle),
                tool_center[1] + axis_length * np.sin(tool_angle)
            )
            x_end2 = (
                tool_center[0] - axis_length * np.cos(tool_angle),
                tool_center[1] - axis_length * np.sin(tool_angle)
            )
            
            y_angle = tool_angle + np.pi / 2
            y_end1 = (
                tool_center[0] + axis_length * np.cos(y_angle),
                tool_center[1] + axis_length * np.sin(y_angle)
            )
            y_end2 = (
                tool_center[0] - axis_length * np.cos(y_angle),
                tool_center[1] - axis_length * np.sin(y_angle)
            )
            
            overlay_manager.add_line(
                "Base",  # Usar marco Base para coordenadas absolutas
                start=x_end2,
                end=x_end1,
                name=f"aruco_x_axis_{tool_aruco_id}",
                color=(255, 0, 0),
                thickness=2
            )
            
            overlay_manager.add_line(
                "Base",  # Usar marco Base para coordenadas absolutas
                start=y_end2,
                end=y_end1,
                name=f"aruco_y_axis_{tool_aruco_id}",
                color=(255, 0, 0),
                thickness=2
            )
            
            # Centro del Tool ArUco (coordenadas absolutas)
            overlay_manager.add_circle(
                "Base",  # Usar marco Base para coordenadas absolutas
                center=tool_center,  # Centro absoluto
                radius=5,
                name=f"aruco_center_{tool_aruco_id}",
                color=(255, 0, 0),
                filled=True
            )
            
            print(f"[overlay] Objetos de overlay creados para Tool ArUco {tool_aruco_id} en coordenadas absolutas")
        
        # Filtrar objetos según configuración de checkboxes
        show_frame = aruco_config.get('show_frame', False)
        show_tool = aruco_config.get('show_tool', False)
        show_center = aruco_config.get('show_center', False)
        
        aruco_objects = []
        
        # Agregar objetos del Frame ArUco si está habilitado
        if show_frame:
            frame_objects = [name for name in overlay_manager.objects.keys() 
                           if name.startswith(f'aruco_') and str(frame_aruco_id) in name]
            aruco_objects.extend(frame_objects)
        
        # Agregar objetos del Tool ArUco si está habilitado
        if show_tool:
            tool_objects = [name for name in overlay_manager.objects.keys() 
                           if name.startswith(f'aruco_') and str(tool_aruco_id) in name]
            aruco_objects.extend(tool_objects)
        
        # Agregar cruz del centro del troquel si está habilitado
        if show_center:
            center_x_mm = aruco_config.get('center_x_mm', 0.0)
            center_y_mm = aruco_config.get('center_y_mm', 0.0)
            
            # SIEMPRE usar el marco del Frame ArUco si está detectado
            if detection_result.get('frame_detected', False):
                frame_name = "base_frame_temp"
                print(f"[overlay] Centro del troquel: usando marco Frame ({center_x_mm}, {center_y_mm}) mm")
                print(f"[overlay] px_per_mm del Frame: {overlay_manager.frames['base_frame_temp'].px_per_mm:.3f}")
                print(f"[overlay] La librería debe transformar automáticamente de base_frame_temp a Base")
            else:
                frame_name = "Base"
                # Calcular px_per_mm basado en la resolución de la imagen
                # Asumiendo que la imagen representa aproximadamente 200x150 mm de área real
                # Esto da un px_per_mm proporcional a la resolución
                image_height, image_width = gray_frame.shape
                assumed_width_mm = 200.0  # Ancho asumido en mm
                assumed_height_mm = 150.0  # Alto asumido en mm
                
                px_per_mm = min(image_width / assumed_width_mm, image_height / assumed_height_mm)
                center_x_px = center_x_mm * px_per_mm
                center_y_px = center_y_mm * px_per_mm
                print(f"[overlay] Centro del troquel: usando marco Base ({center_x_px:.1f}, {center_y_px:.1f}) px")
                print(f"[overlay] px_per_mm calculado: {px_per_mm:.2f} (imagen: {image_width}x{image_height})")
                
                # Actualizar el px_per_mm del marco Base para esta sesión
                overlay_manager.frames["Base"].px_per_mm = px_per_mm
            
            # Crear cruz cyan en las coordenadas del centro del troquel
            # Tamaño: 3cm x 3cm (30mm x 30mm)
            # Color: #00FFFF (cyan) como está definido en la página de configuración
            cross_size_mm = 30.0  # 30mm de tamaño (15mm en cada dirección)
            
            print(f"[overlay] Debug coordenadas del centro del troquel:")
            print(f"  - Coordenadas en mm: ({center_x_mm:.1f}, {center_y_mm:.1f}) mm")
            print(f"  - Marco usado: {frame_name}")
            print(f"  - px_per_mm del marco: {overlay_manager.frames[frame_name].px_per_mm:.3f}")
            print(f"  - Tamaño ArUco Frame: {frame_marker_size}mm")
            print(f"  - La librería convertirá automáticamente mm a px usando px_per_mm")
            
            overlay_manager.add_line(
                frame_name,
                start=(center_x_mm - cross_size_mm/2, center_y_mm),  # Línea horizontal
                end=(center_x_mm + cross_size_mm/2, center_y_mm),
                name="center_cross_h",
                color=(255, 255, 0),  # Cyan en BGR (#00FFFF)
                thickness=4  # Grosor mayor para mejor visibilidad
            )
            
            overlay_manager.add_line(
                frame_name, 
                start=(center_x_mm, center_y_mm - cross_size_mm/2),  # Línea vertical
                end=(center_x_mm, center_y_mm + cross_size_mm/2),
                name="center_cross_v",
                color=(255, 255, 0),  # Cyan en BGR (#00FFFF)
                thickness=4  # Grosor mayor para mejor visibilidad
            )
            
            # Agregar círculo en el centro para mayor visibilidad
            overlay_manager.add_circle(
                frame_name,
                center=(center_x_mm, center_y_mm),
                radius=3.0,  # 3mm de radio (proporcional al tamaño)
                name="center_circle",
                color=(255, 255, 0),  # Cyan en BGR (#00FFFF)
                filled=True
            )
            
            aruco_objects.extend(["center_cross_h", "center_cross_v", "center_circle"])
            
            # ============================================================
            # PRUEBA DE LA LIBRERÍA: 3 SEGMENTOS DE TRANSFORMACIÓN
            # ============================================================
            print(f"[overlay] 🧪 PRUEBA DE LIBRERÍA: Creando 3 segmentos de transformación...")
            
            # SEGMENTO 1: Cruz (base_frame_temp) -> Centro del Frame ArUco (base_frame_temp)
            # Punto de la cruz en el marco base_frame_temp
            cross_point_base = (center_x_mm, center_y_mm)  # (35, 35) mm en base_frame_temp
            
            # Leer coordenadas de la cruz respecto al tool_frame_temp
            cross_point_tool = overlay_manager.get_object("tool_frame_temp", name="center_cross_h")
            print(f"[overlay] Segmento 1: Cruz en base_frame_temp: {cross_point_base} mm")
            print(f"[overlay] Estructura completa de transformación: {cross_point_tool}")
            
            # SEGMENTO 1: Del centro del Frame ArUco (0,0) a la cruz
            overlay_manager.add_line(
                "base_frame_temp",
                start=(0, 0),  # Centro del Frame ArUco
                end=cross_point_base,  # Posición de la cruz
                name="test_segment_1",
                color=(0, 255, 0),  # Verde
                thickness=3
            )
            
            # SEGMENTO 2: Del centro del Tool ArUco (0,0) a la cruz transformada al Tool
            # Usar el centro de la cruz (círculo) en lugar del punto de la línea
            cross_center_tool = overlay_manager.get_object("tool_frame_temp", name="center_circle")
            cross_center_tool_coords = cross_center_tool['coordinates']['center']
            print(f"[overlay] Centro de la cruz en tool_frame_temp: {cross_center_tool_coords} mm")
            overlay_manager.add_line(
                "tool_frame_temp", 
                start=(0, 0),  # Centro del Tool ArUco
                end=cross_center_tool_coords,  # Centro de la cruz transformada al Tool
                name="test_segment_2",
                color=(255, 0, 0),  # Rojo
                thickness=3
            )
            
            # SEGMENTO 3: Del centro del World (0,0) a la cruz transformada al World
            cross_center_world = overlay_manager.get_object("Base", name="center_circle")
            cross_center_world_coords = cross_center_world['coordinates']['center']
            print(f"[overlay] Centro de la cruz en Base (World): {cross_center_world_coords} px")
            overlay_manager.add_line(
                "Base",
                start=(0, 0),  # Centro del World (esquina de la imagen)
                end=cross_center_world_coords,  # Centro de la cruz transformada al World
                name="test_segment_3", 
                color=(0, 0, 255),  # Azul
                thickness=3
            )
            print(f"[overlay] ✅ 3 segmentos de prueba creados:")
            print(f"  - Segmento 1 (Verde): Frame ArUco -> Cruz")
            print(f"  - Segmento 2 (Rojo): Tool ArUco -> Cruz") 
            print(f"  - Segmento 3 (Azul): World -> Cruz")
            
            # Agregar los segmentos de prueba a la lista de objetos
            aruco_objects.extend(["test_segment_1", "test_segment_2", "test_segment_3"])
        
        # Verificar si hay elementos habilitados para mostrar
        if not show_frame and not show_tool and not show_center:
            return jsonify({
                'ok': False,
                'error': 'No hay elementos habilitados para mostrar. Verifica los checkboxes de configuración.'
            }), 400
        
        # Crear renderlist
        renderlist = overlay_manager.create_renderlist(*aruco_objects, name="aruco_overlay")
        
        # Crear imagen de fondo en escala de grises pero manteniendo formato RGB
        gray_background = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2BGR)  # Convertir a RGB pero en grises
        
        # Establecer la imagen de fondo en el OverlayManager
        overlay_manager.set_background("main_background", gray_background)
        
        # Renderizar overlay sobre la imagen de fondo en escala de grises
        print(f"[overlay] Renderizando sobre fondo en escala de grises: {gray_background.shape}, dtype: {gray_background.dtype}")
        result_image, view_time = overlay_manager.render(
            gray_background,  # Usar imagen de fondo en escala de grises
            renderlist=renderlist,
            view_time=3000  # 3 segundos
        )
        print(f"[overlay] Imagen renderizada: {result_image.shape}, dtype: {result_image.dtype}")
        
        # Codificar imagen a base64 para envío
        _, buffer = cv2.imencode('.jpg', result_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Guardar frame temporalmente y activar overlay en el dashboard
        global _overlay_frame, _overlay_active_until
        _overlay_frame = buffer.tobytes()
        _overlay_active_until = time.time() + (view_time / 1000.0)  # Convertir ms a segundos
        
        print(f"[overlay] ✓ Overlay mostrado por {view_time/1000:.1f} segundos en dashboard")
        
        # Preparar información de respuesta
        detected_ids = detection_result.get('detected_ids', [])
        frame_detected = detection_result.get('frame_detected', False)
        tool_detected = detection_result.get('tool_detected', False)
        
        # Crear mensaje informativo
        info_messages = []
        
        # Información sobre Frame ArUco
        if show_frame:
            if frame_detected:
                info_messages.append(f"Frame ArUco (ID: {frame_aruco_id}) detectado - habilitado")
            else:
                info_messages.append(f"Frame ArUco (ID: {frame_aruco_id}) NO detectado - habilitado (no se mostrará)")
        else:
            info_messages.append(f"Frame ArUco (ID: {frame_aruco_id}) deshabilitado en configuración")
            
        # Información sobre Tool ArUco
        if show_tool:
            if tool_detected:
                info_messages.append(f"Tool ArUco (ID: {tool_aruco_id}) detectado - habilitado")
            else:
                info_messages.append(f"Tool ArUco (ID: {tool_aruco_id}) NO detectado - habilitado (no se mostrará)")
        else:
            info_messages.append(f"Tool ArUco (ID: {tool_aruco_id}) deshabilitado en configuración")
        
        # Información sobre centro del troquel
        if show_center:
            center_x = aruco_config.get('center_x_mm', 0.0)
            center_y = aruco_config.get('center_y_mm', 0.0)
            if frame_detected:
                info_messages.append(f"Centro del troquel: ({center_x:.1f}, {center_y:.1f}) mm - habilitado (cruz cyan 3x3cm)")
            else:
                info_messages.append(f"Centro del troquel: ({center_x:.1f}, {center_y:.1f}) mm - habilitado (cruz cyan 3x3cm, coordenadas absolutas)")
        else:
            info_messages.append("Centro del troquel: deshabilitado en configuración")
        
        if detected_ids:
            other_ids = [id for id in detected_ids if id not in [frame_aruco_id, tool_aruco_id]]
            if other_ids:
                info_messages.append(f"ArUcos adicionales detectados: {other_ids}")
        
        return jsonify({
            'ok': True,
            'image': image_base64,
            'view_time': view_time,
            'detection_info': {
                'detected_ids': detected_ids,
                'frame_detected': frame_detected,
                'tool_detected': tool_detected,
                'messages': info_messages
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
        if 'show_frame' in data:
            aruco_config['show_frame'] = bool(data['show_frame'])
        if 'show_tool' in data:
            aruco_config['show_tool'] = bool(data['show_tool'])
        if 'show_center' in data:
            aruco_config['show_center'] = bool(data['show_center'])
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
        
        # ═══════════════════════════════════════════════════════════════════
        # GUARDAR ANÁLISIS EN ARCHIVO SI ES EXITOSO
        # ═══════════════════════════════════════════════════════════════════
        if exito and selected_id:
            try:
                # Obtener nombre de la junta
                juntas = juntas_data.get('juntas', [])
                junta = next((j for j in juntas if j['id'] == selected_id), None)
                
                if junta:
                    junta_nombre = junta.get('nombre')
                    
                    # Crear directorio si no existe
                    os.makedirs('juntas_analisis', exist_ok=True)
                    
                    # Guardar análisis completo
                    analisis_path = f'juntas_analisis/{junta_nombre}_analisis.json'
                    with open(analisis_path, 'w', encoding='utf-8') as f:
                        json.dump(_analisis_serializable_junta_actual, f, indent=2, ensure_ascii=False)
                    print(f"[análisis] ✓ Análisis guardado: {analisis_path}")
            except Exception as e:
                print(f"[análisis] ⚠️ No se pudo guardar análisis en archivo: {e}")
        
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
