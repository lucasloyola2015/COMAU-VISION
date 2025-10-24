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



@app.route('/api/overlay/render', methods=['POST'])
def api_overlay_render():
    """Endpoint genérico para renderizar overlays usando OverlayManager"""
    try:
        import cv2
        import numpy as np
        import time
        
        # ═══════════════════════════════════════════════════════════════════
        # OPTIMIZACIÓN: Detectar si es llamada desde análisis
        # ═══════════════════════════════════════════════════════════════════
        start_time = time.time()
        
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
        
        # ═══════════════════════════════════════════════════════════════════
        # OPTIMIZACIÓN: Detectar ArUcos solo si es necesario
        # ═══════════════════════════════════════════════════════════════════
        
        # Verificar si necesitamos detectar ArUcos (solo si hay elementos habilitados)
        show_frame = aruco_config.get('show_frame', True)
        show_tool = aruco_config.get('show_tool', True)
        show_center = aruco_config.get('show_center', True)
        
        # Solo detectar ArUcos si hay elementos que requieren detección
        all_arucos_result = None
        if show_frame or show_tool:
            print(f"[overlay] Detección de ArUcos (método original):")
            all_arucos_result = detect_all_arucos(cv2_frame, marker_size_mm=frame_marker_size)
        else:
            print(f"[overlay] ⚡ Detección de ArUcos OMITIDA (no hay elementos que requieran detección)")
        
        # Debug: mostrar información de detección
        if all_arucos_result is not None:
            detected_ids = all_arucos_result.get('detected_ids', [])
            print(f"  - IDs detectados: {detected_ids}")
        else:
            detected_ids = []
            print(f"  - No se detectaron ArUcos (detección omitida)")
        
        # ═══════════════════════════════════════════════════════════════════
        # OPTIMIZACIÓN: Detectar ArUcos específicos solo si es necesario
        # ═══════════════════════════════════════════════════════════════════
        
        # Solo detectar ArUcos específicos si hay elementos que los requieren
        frame_result = None
        tool_result = None
        
        if show_frame:
            frame_result = detect_aruco_by_id(cv2_frame, frame_aruco_id, marker_size_mm=frame_marker_size)
        else:
            print(f"[overlay] ⚡ Frame ArUco OMITIDO (show_frame=False)")
            
        if show_tool:
            tool_result = detect_aruco_by_id(cv2_frame, tool_aruco_id, marker_size_mm=tool_marker_size)
        else:
            print(f"[overlay] ⚡ Tool ArUco OMITIDO (show_tool=False)")
        
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
            
            # Crear círculo cyan en las coordenadas del centro del troquel
            # Diámetro: 6mm (radio: 3mm)
            # Color: #00FFFF (cyan) como está definido en la página de configuración
            
            print(f"[overlay] Debug coordenadas del centro del troquel:")
            print(f"  - Coordenadas en mm: ({center_x_mm:.1f}, {center_y_mm:.1f}) mm")
            print(f"  - Marco usado: {frame_name}")
            print(f"  - px_per_mm del marco: {overlay_manager.frames[frame_name].px_per_mm:.3f}")
            print(f"  - Tamaño ArUco Frame: {frame_marker_size}mm")
            print(f"  - La librería convertirá automáticamente mm a px usando px_per_mm")
            
            # Agregar círculo en el centro del troquel (10mm de diámetro)
            overlay_manager.add_circle(
                frame_name,
                center=(center_x_mm, center_y_mm),
                radius=5.0,  # 5mm de radio (10mm de diámetro)
                name="center_circle",
                color=(255, 255, 0),  # Cyan en BGR (#00FFFF)
                filled=True
            )
            
            aruco_objects.extend(["center_circle"])
        
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
        
        # ═══════════════════════════════════════════════════════════════════
        # OPTIMIZACIÓN: Renderizado más rápido
        # ═══════════════════════════════════════════════════════════════════
        
        # Renderizar overlay sobre la imagen de fondo en escala de grises
        print(f"[overlay] Renderizando sobre fondo en escala de grises: {gray_background.shape}, dtype: {gray_background.dtype}")
        result_image, view_time = overlay_manager.render(
            gray_background,  # Usar imagen de fondo en escala de grises
            renderlist=renderlist,
            view_time=500  # ⚡ Reducido de 3000ms a 500ms (6x más rápido)
        )
        print(f"[overlay] Imagen renderizada: {result_image.shape}, dtype: {result_image.dtype}")
        
        # ═══════════════════════════════════════════════════════════════════
        # OPTIMIZACIÓN: Compresión más agresiva para análisis
        # ═══════════════════════════════════════════════════════════════════
        
        # Codificar imagen a base64 para envío (calidad reducida para análisis)
        _, buffer = cv2.imencode('.jpg', result_image, [cv2.IMWRITE_JPEG_QUALITY, 75])  # ⚡ Reducido de 95 a 75
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
        
        # ═══════════════════════════════════════════════════════════════════
        # TIMING: Mostrar tiempo total del endpoint
        # ═══════════════════════════════════════════════════════════════════
        total_time = time.time() - start_time
        print(f"[TIMING] ⏱️  /api/overlay/render TOTAL: {total_time:.3f}s")
        
        return jsonify({
            'ok': True,
            'image': image_base64,
            'view_time': view_time,
            'total_time_ms': int(total_time * 1000),  # Agregar tiempo total
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

@app.route('/api/aruco/save_config', methods=['POST'])
def api_aruco_save_config():
    """Guardar configuración de ArUcos y objetos de renderizado persistentes"""
    try:
        import cv2
        import numpy as np
        from overlay_manager import OverlayManager
        
        # Obtener configuración actual
        config = load_aruco_config()
        aruco_config = config.get('aruco', {})
        
        # Obtener frame actual de la cámara
        cv2_frame = camera_manager.get_frame_raw()
        
        if cv2_frame is None:
            return jsonify({
                'ok': False,
                'error': 'No hay frame disponible de la cámara'
            }), 400
        
        # Crear instancia de OverlayManager
        overlay_manager = OverlayManager()
        
        # Detectar ArUcos para obtener frames temporales
        frame_aruco_id = aruco_config.get('frame_aruco_id', 0)
        tool_aruco_id = aruco_config.get('tool_aruco_id', 0)
        frame_marker_size = aruco_config.get('frame_marker_size_mm', 70.0)
        tool_marker_size = aruco_config.get('tool_marker_size_mm', 50.0)
        
        # Detectar ArUcos
        all_arucos_result = detect_all_arucos(cv2_frame, marker_size_mm=frame_marker_size)
        frame_result = detect_aruco_by_id(cv2_frame, frame_aruco_id, marker_size_mm=frame_marker_size)
        tool_result = detect_aruco_by_id(cv2_frame, tool_aruco_id, marker_size_mm=tool_marker_size)
        
        frame_detected = frame_result is not None
        tool_detected = tool_result is not None
        
        print(f"[aruco] Guardando configuración:")
        print(f"  - Frame ArUco (ID: {frame_aruco_id}) detectado: {frame_detected}")
        print(f"  - Tool ArUco (ID: {tool_aruco_id}) detectado: {tool_detected}")
        
        # Copiar frames temporales a permanentes si están detectados
        if frame_detected and frame_result:
            frame_center = frame_result['center']
            frame_angle = np.arctan2(frame_result['rotation_matrix'][1][0], frame_result['rotation_matrix'][0][0])
            frame_px_per_mm = frame_result['px_per_mm']
            
            # Actualizar marco base_frame permanente
            overlay_manager.define_frame(
                "base_frame",
                offset=(frame_center[0], frame_center[1]),
                rotation=frame_angle,
                px_per_mm=frame_px_per_mm,
                parent_frame="Base",
                is_temporary=False
            )
            print(f"[aruco] ✓ Marco base_frame actualizado: center=({frame_center[0]:.1f}, {frame_center[1]:.1f}), angle={frame_angle:.3f}rad, px_per_mm={frame_px_per_mm:.3f}")
        
        if tool_detected and tool_result:
            tool_center = tool_result['center']
            tool_angle = np.arctan2(tool_result['rotation_matrix'][1][0], tool_result['rotation_matrix'][0][0])
            tool_px_per_mm = tool_result['px_per_mm']
            
            # Actualizar marco tool_frame permanente
            overlay_manager.define_frame(
                "tool_frame",
                offset=(tool_center[0], tool_center[1]),
                rotation=tool_angle,
                px_per_mm=tool_px_per_mm,
                parent_frame="Base",
                is_temporary=False
            )
            print(f"[aruco] ✓ Marco tool_frame actualizado: center=({tool_center[0]:.1f}, {tool_center[1]:.1f}), angle={tool_angle:.3f}rad, px_per_mm={tool_px_per_mm:.3f}")
        
        # Crear objetos de renderizado persistentes
        objects_to_save = []
        
        # Objetos del Frame ArUco si está detectado
        if frame_detected and frame_result:
            frame_center = frame_result['center']
            frame_corners = frame_result['corners']
            frame_angle = np.arctan2(frame_result['rotation_matrix'][1][0], frame_result['rotation_matrix'][0][0])
            
            # Contorno del Frame ArUco
            overlay_manager.add_polygon(
                "Base",
                points=frame_corners,
                name=f"aruco_contour_{frame_aruco_id}",
                color=(0, 255, 255),  # Amarillo
                thickness=2
            )
            
            # Ejes del Frame ArUco
            image_height, image_width = cv2_frame.shape[:2]
            axis_length = max(image_width, image_height)
            
            x_end1 = (frame_center[0] + axis_length * np.cos(frame_angle), frame_center[1] + axis_length * np.sin(frame_angle))
            x_end2 = (frame_center[0] - axis_length * np.cos(frame_angle), frame_center[1] - axis_length * np.sin(frame_angle))
            
            y_angle = frame_angle + np.pi / 2
            y_end1 = (frame_center[0] + axis_length * np.cos(y_angle), frame_center[1] + axis_length * np.sin(y_angle))
            y_end2 = (frame_center[0] - axis_length * np.cos(y_angle), frame_center[1] - axis_length * np.sin(y_angle))
            
            overlay_manager.add_line("Base", start=x_end2, end=x_end1, name=f"aruco_x_axis_{frame_aruco_id}", color=(0, 255, 255), thickness=2)
            overlay_manager.add_line("Base", start=y_end2, end=y_end1, name=f"aruco_y_axis_{frame_aruco_id}", color=(0, 255, 255), thickness=2)
            
            # Centro del Frame ArUco
            overlay_manager.add_circle("Base", center=frame_center, radius=5, name=f"aruco_center_{frame_aruco_id}", color=(0, 255, 255), filled=True)
            
            objects_to_save.extend([f"aruco_contour_{frame_aruco_id}", f"aruco_x_axis_{frame_aruco_id}", f"aruco_y_axis_{frame_aruco_id}", f"aruco_center_{frame_aruco_id}"])
        
        # Objetos del Tool ArUco si está detectado
        if tool_detected and tool_result:
            tool_center = tool_result['center']
            tool_corners = tool_result['corners']
            tool_angle = np.arctan2(tool_result['rotation_matrix'][1][0], tool_result['rotation_matrix'][0][0])
            
            # Contorno del Tool ArUco
            overlay_manager.add_polygon("Base", points=tool_corners, name=f"aruco_contour_{tool_aruco_id}", color=(255, 0, 0), thickness=2)
            
            # Ejes del Tool ArUco
            image_height, image_width = cv2_frame.shape[:2]
            axis_length = max(image_width, image_height)
            
            x_end1 = (tool_center[0] + axis_length * np.cos(tool_angle), tool_center[1] + axis_length * np.sin(tool_angle))
            x_end2 = (tool_center[0] - axis_length * np.cos(tool_angle), tool_center[1] - axis_length * np.sin(tool_angle))
            
            y_angle = tool_angle + np.pi / 2
            y_end1 = (tool_center[0] + axis_length * np.cos(y_angle), tool_center[1] + axis_length * np.sin(y_angle))
            y_end2 = (tool_center[0] - axis_length * np.cos(y_angle), tool_center[1] - axis_length * np.sin(y_angle))
            
            overlay_manager.add_line("Base", start=x_end2, end=x_end1, name=f"aruco_x_axis_{tool_aruco_id}", color=(255, 0, 0), thickness=2)
            overlay_manager.add_line("Base", start=y_end2, end=y_end1, name=f"aruco_y_axis_{tool_aruco_id}", color=(255, 0, 0), thickness=2)
            
            # Centro del Tool ArUco
            overlay_manager.add_circle("Base", center=tool_center, radius=5, name=f"aruco_center_{tool_aruco_id}", color=(255, 0, 0), filled=True)
            
            objects_to_save.extend([f"aruco_contour_{tool_aruco_id}", f"aruco_x_axis_{tool_aruco_id}", f"aruco_y_axis_{tool_aruco_id}", f"aruco_center_{tool_aruco_id}"])
        
        # Círculo del centro del troquel
        center_x_mm = aruco_config.get('center_x_mm', 0.0)
        center_y_mm = aruco_config.get('center_y_mm', 0.0)
        
        if frame_detected:
            # Usar marco del Frame ArUco
            frame_name = "base_frame"
        else:
            # Usar marco Base con px_per_mm calculado
            image_height, image_width = cv2_frame.shape[:2]
            assumed_width_mm = 200.0
            assumed_height_mm = 150.0
            px_per_mm = min(image_width / assumed_width_mm, image_height / assumed_height_mm)
            overlay_manager.frames["Base"].px_per_mm = px_per_mm
            frame_name = "Base"
        
        # Crear círculo del centro del troquel (10mm de diámetro)
        overlay_manager.add_circle(
            frame_name,
            center=(center_x_mm, center_y_mm),
            radius=5.0,  # 5mm de radio (10mm de diámetro)
            name="center_circle",
            color=(255, 255, 0),  # Cyan
            filled=True
        )
        
        objects_to_save.append("center_circle")
        
        # Guardar configuración en overlay_frames.json
        overlay_manager.save_persistent_config()
        
        # Guardar nombres de objetos en aruco_config.json
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
        save_aruco_config(config)
        
        print(f"[aruco] ✓ Configuración guardada:")
        print(f"  - Marcos: base_frame, tool_frame")
        print(f"  - Objetos: {len(objects_to_save)} objetos guardados")
        print(f"  - Archivos: overlay_frames.json, aruco_config.json")
        
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

@app.route('/api/vision/set_roi', methods=['POST'])
def api_set_roi_config():
    """Guardar configuración ROI"""
    try:
        data = request.get_json()
        print(f"[ROI] 🚀 Guardando configuración ROI...")
        print(f"[ROI] 📊 Datos recibidos: {data}")
        
        # Validar datos
        roi_enabled = data.get('roi_enabled', False)
        roi_offset_y_mm = float(data.get('roi_offset_y_mm', 0.0))
        roi_zoom_x_percent = float(data.get('roi_zoom_x_percent', 150))
        roi_zoom_y_percent = float(data.get('roi_zoom_y_percent', 150))
        
        print(f"[ROI] 📋 Configuración validada:")
        print(f"  - ROI habilitado: {roi_enabled}")
        print(f"  - Offset Y: {roi_offset_y_mm} mm")
        print(f"  - Zoom X: {roi_zoom_x_percent}%")
        print(f"  - Zoom Y: {roi_zoom_y_percent}%")
        
        # Cargar configuración actual
        config = load_config()
        
        # Actualizar configuración ROI
        if 'vision' not in config:
            config['vision'] = {}
        
        config['vision']['roi_enabled'] = roi_enabled
        config['vision']['roi_offset_y_mm'] = roi_offset_y_mm
        config['vision']['roi_zoom_x_percent'] = roi_zoom_x_percent
        config['vision']['roi_zoom_y_percent'] = roi_zoom_y_percent
        
        # Guardar configuración
        save_config(config)
        
        print(f"[ROI] ✅ Configuración ROI guardada exitosamente")
        
        return jsonify({
            'ok': True,
            'message': 'Configuración ROI guardada correctamente',
            'roi_config': {
                'enabled': roi_enabled,
                'offset_y_mm': roi_offset_y_mm,
                'zoom_x_percent': roi_zoom_x_percent,
                'zoom_y_percent': roi_zoom_y_percent
            }
        })
        
    except Exception as e:
        print(f"[ROI] ❌ Error guardando configuración ROI: {e}")
        return jsonify({
            'ok': False,
            'error': f'Error guardando configuración ROI: {str(e)}'
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

@app.route('/api/analyze_new', methods=['POST'])
def api_analyze_new():
    """Nuevo endpoint de análisis con OverlayManager (placeholder)"""
    import time
    start_time = time.time()
    
    try:
        print("\n[análisis] 🚀 POST /api/analyze_new iniciado")
        print(f"[TIMING] ⏱️  Inicio total: {time.time() - start_time:.3f}s")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 1: Verificar junta seleccionada
        # ═══════════════════════════════════════════════════════════════════
        step_start = time.time()
        juntas_data = load_juntas()
        selected_id = juntas_data.get('selected_id')
        print(f"[TIMING] ⏱️  Verificar junta: {time.time() - step_start:.3f}s")
        
        if not selected_id:
            print("[análisis] ❌ No hay junta seleccionada")
            return jsonify({
                'ok': False,
                'error': 'No hay junta seleccionada'
            }), 400
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 2: Obtener frame de la cámara
        # ═══════════════════════════════════════════════════════════════════
        step_start = time.time()
        frame = camera_manager.get_frame_raw()
        print(f"[TIMING] ⏱️  Capturar frame: {time.time() - step_start:.3f}s")
        
        if frame is None:
            print("[análisis] ❌ No se pudo obtener frame de la cámara")
            return jsonify({
                'ok': False,
                'error': 'Cámara no disponible'
            }), 500
        
        print(f"[análisis] ✓ Frame capturado: {frame.shape}")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 3: Optimizar resolución para reducir lag
        # ═══════════════════════════════════════════════════════════════════
        step_start = time.time()
        import cv2
        
        # Reducir resolución para detección más rápida
        original_height, original_width = frame.shape[:2]
        scale_factor = 0.5  # Reducir a 50% de la resolución original (ajustable: 0.3-0.7)
        
        # Calcular nuevas dimensiones
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        
        # Redimensionar frame para detección
        frame_resized = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
        print(f"[TIMING] ⏱️  Optimizar resolución: {time.time() - step_start:.3f}s")
        
        print(f"[análisis] ✓ Frame optimizado: {frame.shape} → {frame_resized.shape} (factor: {scale_factor})")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 4: Crear OverlayManager y objetos de prueba
        # ═══════════════════════════════════════════════════════════════════
        step_start = time.time()
        from overlay_manager import OverlayManager
        overlay_manager = OverlayManager()
        print(f"[TIMING] ⏱️  Crear OverlayManager: {time.time() - step_start:.3f}s")
        
        # ⚡ OPTIMIZACIÓN: Solo crear objetos necesarios (no objetos de prueba)
        print(f"[análisis] ✓ OverlayManager creado, esperando objetos de análisis")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 5: Renderizar UNA SOLA VEZ al final (optimizado)
        # ═══════════════════════════════════════════════════════════════════
        step_start = time.time()
        
        # ⚡ OPTIMIZACIÓN: Renderizar directamente sin HTTP
        import base64
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 6: Detectar ArUcos para obtener referencia de escala
        # ═══════════════════════════════════════════════════════════════════
        step_start = time.time()
        
        # Detectar ArUcos para obtener marcos de referencia
        import numpy as np
        from src.vision.aruco_detector import detect_all_arucos, detect_aruco_by_id
        
        # Obtener configuración de ArUcos
        config = load_aruco_config()
        aruco_config = config.get('aruco', {})
        frame_aruco_id = aruco_config.get('frame_aruco_id', 0)
        tool_aruco_id = aruco_config.get('tool_aruco_id', 0)
        frame_marker_size = aruco_config.get('frame_marker_size_mm', 70.0)
        tool_marker_size = aruco_config.get('tool_marker_size_mm', 50.0)
        
        # Detectar ArUcos en frame original (no redimensionado)
        all_arucos_result = detect_all_arucos(frame, marker_size_mm=frame_marker_size)
        frame_result = detect_aruco_by_id(frame, frame_aruco_id, marker_size_mm=frame_marker_size)
        tool_result = detect_aruco_by_id(frame, tool_aruco_id, marker_size_mm=tool_marker_size)
        
        frame_detected = frame_result is not None
        tool_detected = tool_result is not None
        
        # Cargar configuración de checkboxes de ArUcos
        aruco_config = load_config()
        show_frame = aruco_config.get('aruco', {}).get('show_frame', True)
        show_tool = aruco_config.get('aruco', {}).get('show_tool', True)
        
        print(f"[análisis] 📋 Configuración ArUcos:")
        print(f"  - Mostrar Frame ArUco: {show_frame}")
        print(f"  - Mostrar Tool ArUco: {show_tool}")
        
        print(f"[análisis] Detección de ArUcos:")
        print(f"  - Frame ArUco (ID: {frame_aruco_id}) detectado: {frame_detected}")
        print(f"  - Tool ArUco (ID: {tool_aruco_id}) detectado: {tool_detected}")
        print(f"[TIMING] ⏱️  Detectar ArUcos: {time.time() - step_start:.3f}s")
        
        # Actualizar marcos con datos reales si están detectados
        if frame_detected and frame_result:
            frame_center = frame_result['center']
            frame_angle = np.arctan2(frame_result['rotation_matrix'][1][0], frame_result['rotation_matrix'][0][0])
            frame_px_per_mm = frame_result['px_per_mm']
            
            overlay_manager.define_frame(
                "base_frame",
                offset=(frame_center[0], frame_center[1]),
                rotation=frame_angle,
                px_per_mm=frame_px_per_mm,
                parent_frame="world",
                is_temporary=False
            )
            print(f"[análisis] ✓ Marco base_frame actualizado con ArUco real")
        
        if tool_detected and tool_result:
            tool_center = tool_result['center']
            tool_angle = np.arctan2(tool_result['rotation_matrix'][1][0], tool_result['rotation_matrix'][0][0])
            tool_px_per_mm = tool_result['px_per_mm']
            
            overlay_manager.define_frame(
                "tool_frame",
                offset=(tool_center[0], tool_center[1]),
                rotation=tool_angle,
                px_per_mm=tool_px_per_mm,
                parent_frame="world",
                is_temporary=False
            )
            print(f"[análisis] ✓ Marco tool_frame actualizado con ArUco real")
        
        # Crear imagen de fondo en escala de grises
        gray_background = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_background = cv2.cvtColor(gray_background, cv2.COLOR_GRAY2BGR)
        
        # Establecer fondo en OverlayManager
        overlay_manager.set_background("main_background", gray_background)
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 7: Agregar círculo del centro del troquel con referencia correcta
        # ═══════════════════════════════════════════════════════════════════
        
        # Obtener coordenadas del centro del troquel
        center_x_mm = aruco_config.get('center_x_mm', 0.0)
        center_y_mm = aruco_config.get('center_y_mm', 0.0)
        
        # Determinar qué marco usar para el centro del troquel
        if frame_detected:
            # Usar marco del Frame ArUco (tiene px_per_mm correcto)
            # Las coordenadas center_x_mm, center_y_mm son RELATIVAS al ArUco Frame
            frame_name = "base_frame"
            center_x_final = center_x_mm  # Leer del JSON
            center_y_final = center_y_mm  # Leer del JSON
            print(f"[análisis] Centro del troquel: usando marco Frame ({center_x_mm}, {center_y_mm}) mm")
        else:
            # Usar marco world con px_per_mm estimado
            image_height, image_width = frame.shape[:2]
            assumed_width_mm = 200.0
            assumed_height_mm = 150.0
            px_per_mm = min(image_width / assumed_width_mm, image_height / assumed_height_mm)
            overlay_manager.frames["world"].px_per_mm = px_per_mm
            frame_name = "world"
            center_x_final = center_x_mm  # Usar coordenadas absolutas
            center_y_final = center_y_mm  # Usar coordenadas absolutas
            print(f"[análisis] Centro del troquel: usando marco world ({center_x_mm}, {center_y_mm}) mm, px_per_mm={px_per_mm:.3f}")
        
        # Agregar círculo del centro del troquel (10mm de diámetro)
        overlay_manager.add_circle(
            frame_name,
            center=(center_x_final, center_y_final),
            radius=5.0,  # 5mm de radio (10mm de diámetro)
            name="center_circle",
            color=(255, 255, 0),  # Cyan
            filled=True
        )
        print(f"[análisis] ✓ Círculo del centro del troquel agregado en marco '{frame_name}'")
        print(f"[análisis] 📍 Coordenadas del centro: ({center_x_final}, {center_y_final}) mm")
        print(f"[análisis] 📏 Radio: 5.0 mm (10mm diámetro)")
        print(f"[análisis] 🎨 Color: Cyan (255, 255, 0)")
        
        # Verificar que el objeto se creó correctamente
        if "center_circle" in overlay_manager.objects:
            obj = overlay_manager.objects["center_circle"]
            print(f"[análisis] ✓ Objeto 'center_circle' creado correctamente:")
            print(f"  - Marco: {obj.original_frame}")
            print(f"  - Centro: {obj.coordinates.get('center', 'N/A')}")
            print(f"  - Radio: {obj.coordinates.get('radius', 'N/A')}")
            print(f"  - Color: {obj.properties.get('color', 'N/A')}")
        else:
            print(f"[análisis] ❌ ERROR: Objeto 'center_circle' NO se creó")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 6: YOLO para detectar junta (gasket) - OPTIMIZADO con ROI
        # ═══════════════════════════════════════════════════════════════════
        
        step_start = time.time()
        print(f"[análisis] 🔍 Iniciando detección de junta con YOLO (optimizado con ROI)...")
        
        # Cargar configuración ROI
        config = load_config()
        roi_config = config.get('vision', {})
        roi_enabled = roi_config.get('roi_enabled', False)
        roi_offset_y_mm = roi_config.get('roi_offset_y_mm', 0.0)
        roi_zoom_x_percent = roi_config.get('roi_zoom_x_percent', 150)
        roi_zoom_y_percent = roi_config.get('roi_zoom_y_percent', 150)
        
        print(f"[ROI] 📋 Configuración ROI cargada:")
        print(f"  - ROI habilitado: {roi_enabled}")
        print(f"  - Offset Y: {roi_offset_y_mm} mm")
        print(f"  - Zoom X: {roi_zoom_x_percent}%")
        print(f"  - Zoom Y: {roi_zoom_y_percent}%")
        
        # Crear imagen de baja resolución para detección de junta (más rápida)
        low_res_scale = 0.2  # 20% de la resolución original (ultra agresivo para CUDA)
        low_res_height = int(frame.shape[0] * low_res_scale)
        low_res_width = int(frame.shape[1] * low_res_scale)
        low_res_frame = cv2.resize(frame, (low_res_width, low_res_height))
        
        print(f"[análisis] ✓ Imagen de baja resolución: {frame.shape} → {low_res_frame.shape} (factor: {low_res_scale})")
        
        # Aplicar ROI si está habilitado
        if roi_enabled:
            print(f"[ROI] 🎯 Aplicando ROI a la detección de junta...")
            
            # Obtener junta seleccionada para dimensiones
            try:
                junta_response = requests.get('http://127.0.0.1:5000/api/juntas/selected', timeout=5)
                junta_data = junta_response.json()
                junta_id = junta_data.get('junta', {}).get('id') if junta_data.get('junta') else None
                print(f"[ROI] 📊 Junta seleccionada ID: {junta_id}")
                print(f"[ROI] 📊 Respuesta completa: {junta_data}")
                
                if junta_id:
                    # Obtener dimensiones directamente de la junta seleccionada
                    junta_data = junta_response.json()
                    junta_info = junta_data.get('junta', {})
                    
                    # Obtener dimensiones en mm directamente de la base de datos
                    junta_width_mm = junta_info.get('ancho_mm', 461.20)  # Default 461.20mm
                    junta_height_mm = junta_info.get('alto_mm', 170.00)  # Default 170.00mm
                    
                    print(f"[ROI] 📏 Dimensiones de la junta:")
                    print(f"  - Ancho: {junta_width_mm} mm")
                    print(f"  - Alto: {junta_height_mm} mm")
                    
                    # Calcular dimensiones con zoom
                    roi_width_mm = junta_width_mm * (roi_zoom_x_percent / 100.0)
                    roi_height_mm = junta_height_mm * (roi_zoom_y_percent / 100.0)
                    
                    print(f"[ROI] 🔍 Dimensiones ROI con zoom:")
                    print(f"  - Ancho: {roi_width_mm} mm (zoom {roi_zoom_x_percent}%)")
                    print(f"  - Alto: {roi_height_mm} mm (zoom {roi_zoom_y_percent}%)")
                    
                    # Obtener px_per_mm del tool_frame
                    tool_px_per_mm = overlay_manager.frames.get('tool_frame', {}).px_per_mm if 'tool_frame' in overlay_manager.frames else 1.0
                    print(f"[ROI] 📐 px_per_mm del tool_frame: {tool_px_per_mm}")
                    
                    # Convertir dimensiones a píxeles
                    roi_width_px = roi_width_mm * tool_px_per_mm
                    roi_height_px = roi_height_mm * tool_px_per_mm
                    
                    print(f"[ROI] 📐 Dimensiones ROI en píxeles:")
                    print(f"  - Ancho: {roi_width_px} px")
                    print(f"  - Alto: {roi_height_px} px")
                    
                    # Calcular posición del ROI
                    tool_center_x = overlay_manager.frames['tool_frame'].offset[0] if 'tool_frame' in overlay_manager.frames else 0
                    tool_center_y = overlay_manager.frames['tool_frame'].offset[1] if 'tool_frame' in overlay_manager.frames else 0
                    
                    # Offset Y en píxeles
                    offset_y_px = roi_offset_y_mm * tool_px_per_mm
                    
                    # Posición final del ROI
                    roi_center_x = tool_center_x
                    roi_center_y = tool_center_y + offset_y_px + (roi_height_px / 2)
                    
                    print(f"[ROI] 📍 Posición del ROI:")
                    print(f"  - Centro tool_frame: ({tool_center_x}, {tool_center_y})")
                    print(f"  - Offset Y: {offset_y_px} px")
                    print(f"  - Centro ROI: ({roi_center_x}, {roi_center_y})")
                    
                    # Calcular coordenadas del rectángulo ROI
                    roi_x1 = int(roi_center_x - roi_width_px / 2)
                    roi_y1 = int(roi_center_y - roi_height_px / 2)
                    roi_x2 = int(roi_center_x + roi_width_px / 2)
                    roi_y2 = int(roi_center_y + roi_height_px / 2)
                    
                    print(f"[ROI] 📦 Coordenadas ROI:")
                    print(f"  - x1: {roi_x1}, y1: {roi_y1}")
                    print(f"  - x2: {roi_x2}, y2: {roi_y2}")
                    
                    # Asegurar que el ROI esté dentro de la imagen
                    roi_x1 = max(0, roi_x1)
                    roi_y1 = max(0, roi_y1)
                    roi_x2 = min(low_res_width, roi_x2)
                    roi_y2 = min(low_res_height, roi_y2)
                    
                    print(f"[ROI] 📦 Coordenadas ROI ajustadas:")
                    print(f"  - x1: {roi_x1}, y1: {roi_y1}")
                    print(f"  - x2: {roi_x2}, y2: {roi_y2}")
                    
                    # Crear rectángulo ROI visual
                    overlay_manager.add_polygon(
                        "world",
                        points=[
                            [roi_x1 / low_res_scale, roi_y1 / low_res_scale],  # Top-left (escalado a resolución original)
                            [roi_x2 / low_res_scale, roi_y1 / low_res_scale],  # Top-right
                            [roi_x2 / low_res_scale, roi_y2 / low_res_scale],  # Bottom-right
                            [roi_x1 / low_res_scale, roi_y2 / low_res_scale]   # Bottom-left
                        ],
                        name="roi_rectangle",
                        color=(0, 255, 255),  # Cyan (más visible)
                        thickness=4  # Más grueso
                    )
                    
                    print(f"[ROI] ✅ Rectángulo ROI agregado como overlay visual")
                    
                    # Recortar imagen usando ROI
                    roi_crop = low_res_frame[roi_y1:roi_y2, roi_x1:roi_x2]
                    print(f"[ROI] ✂️ Imagen recortada con ROI: {roi_crop.shape}")
                    
                    # Usar imagen recortada para YOLO
                    color_frame = roi_crop
                    print(f"[ROI] 🎯 Usando imagen recortada para YOLO de junta")
                    
                else:
                    print(f"[ROI] ⚠️ No se pudo obtener dimensiones de la junta, usando detección normal")
                    color_frame = low_res_frame
            else:
                print(f"[ROI] ⚠️ No hay junta seleccionada, usando detección normal")
                color_frame = low_res_frame
                
            except Exception as roi_error:
                print(f"[ROI] ❌ Error aplicando ROI: {roi_error}")
                print(f"[ROI] 🔄 Usando detección normal como fallback")
                color_frame = low_res_frame
        else:
            print(f"[ROI] ⚠️ ROI deshabilitado, usando detección normal")
            color_frame = low_res_frame
        
        # Detectar junta con YOLO
        try:
            gasket_result = yolo_detector.detect_gasket(color_frame)
            print(f"[TIMING] ⏱️  Detectar junta YOLO: {time.time() - step_start:.3f}s")
            print(f"[análisis] 🔍 Resultado YOLO: {gasket_result}")
            print(f"[análisis] 🔍 Tipo de resultado: {type(gasket_result)}")
            
            if gasket_result and isinstance(gasket_result, dict) and 'bbox' in gasket_result:
                gasket_bbox = gasket_result['bbox']
                print(f"[análisis] ✓ Junta detectada: bbox={gasket_bbox}")
                
                # ESCALAR bbox de baja resolución a alta resolución
                scale_factor = 1.0 / low_res_scale  # Factor de escalado inverso
                scaled_bbox = [
                    int(gasket_bbox[0] * scale_factor),  # x1
                    int(gasket_bbox[1] * scale_factor),  # y1
                    int(gasket_bbox[2] * scale_factor),  # x2
                    int(gasket_bbox[3] * scale_factor)   # y2
                ]
                
                print(f"[análisis] ✓ Bbox escalado a alta resolución: {gasket_bbox} → {scaled_bbox}")
                
                # Agrandar bbox escalado en 10%
                x1, y1, x2, y2 = scaled_bbox
                width = x2 - x1
                height = y2 - y1
                margin_x = width * 0.1
                margin_y = height * 0.1
                
                enlarged_bbox = [
                    max(0, x1 - margin_x),
                    max(0, y1 - margin_y),
                    min(frame.shape[1], x2 + margin_x),
                    min(frame.shape[0], y2 + margin_y)
                ]
                
                print(f"[análisis] ✓ Bbox agrandado 10% (alta res): {enlarged_bbox}")
                
                # Crear rectángulo verde para mostrar el bbox de la junta
                overlay_manager.add_polygon(
                    "world",
                    points=[
                        [enlarged_bbox[0], enlarged_bbox[1]],  # Top-left
                        [enlarged_bbox[2], enlarged_bbox[1]],  # Top-right
                        [enlarged_bbox[2], enlarged_bbox[3]],  # Bottom-right
                        [enlarged_bbox[0], enlarged_bbox[3]]   # Bottom-left
                    ],
                    name="gasket_bbox",
                    color=(0, 255, 0),  # Verde
                    thickness=3
                )
                
                print(f"[análisis] ✓ Rectángulo verde del bbox de junta agregado")
                
                # Actualizar junta_frame con el bbox escalado
                center_x = (enlarged_bbox[0] + enlarged_bbox[2]) / 2
                center_y = (enlarged_bbox[1] + enlarged_bbox[3]) / 2
                bbox_width = enlarged_bbox[2] - enlarged_bbox[0]
                bbox_height = enlarged_bbox[3] - enlarged_bbox[1]
                
                # Estimar px_per_mm basado en el tamaño del bbox
                estimated_diameter_mm = 100.0
                px_per_mm = min(bbox_width, bbox_height) / estimated_diameter_mm
                
                # Actualizar junta_frame
                overlay_manager.define_frame(
                    "junta_frame",
                    offset=(center_x, center_y),
                    rotation=0.0,
                    px_per_mm=px_per_mm,
                    parent_frame="world"
                )
                
                print(f"[análisis] ✓ Marco junta_frame actualizado:")
                print(f"  - Centro: ({center_x:.1f}, {center_y:.1f}) px")
                print(f"  - px_per_mm: {px_per_mm:.3f}")
                print(f"  - Dimensiones: {bbox_width:.1f}x{bbox_height:.1f} px")
                
            elif gasket_result and isinstance(gasket_result, (list, tuple)) and len(gasket_result) >= 4:
                # Si el resultado es una lista/tupla con al menos 4 elementos (x1, y1, x2, y2)
                gasket_bbox = list(gasket_result[:4])  # Tomar los primeros 4 elementos
                print(f"[análisis] ✓ Junta detectada (formato lista): bbox={gasket_bbox}")
                
                # ESCALAR bbox de baja resolución a alta resolución
                scale_factor = 1.0 / low_res_scale  # Factor de escalado inverso
                scaled_bbox = [
                    int(gasket_bbox[0] * scale_factor),  # x1
                    int(gasket_bbox[1] * scale_factor),  # y1
                    int(gasket_bbox[2] * scale_factor),  # x2
                    int(gasket_bbox[3] * scale_factor)   # y2
                ]
                
                print(f"[análisis] ✓ Bbox escalado a alta resolución: {gasket_bbox} → {scaled_bbox}")
                
                # Agrandar bbox escalado en 10%
                x1, y1, x2, y2 = scaled_bbox
                width = x2 - x1
                height = y2 - y1
                margin_x = width * 0.1
                margin_y = height * 0.1
                
                enlarged_bbox = [
                    max(0, x1 - margin_x),
                    max(0, y1 - margin_y),
                    min(frame.shape[1], x2 + margin_x),
                    min(frame.shape[0], y2 + margin_y)
                ]
                
                print(f"[análisis] ✓ Bbox agrandado 10% (alta res): {enlarged_bbox}")
                
                # Crear rectángulo verde para mostrar el bbox de la junta
                overlay_manager.add_polygon(
                    "world",
                    points=[
                        [enlarged_bbox[0], enlarged_bbox[1]],  # Top-left
                        [enlarged_bbox[2], enlarged_bbox[1]],  # Top-right
                        [enlarged_bbox[2], enlarged_bbox[3]],  # Bottom-right
                        [enlarged_bbox[0], enlarged_bbox[3]]   # Bottom-left
                    ],
                    name="gasket_bbox",
                    color=(0, 255, 0),  # Verde
                    thickness=3
                )
                
                print(f"[análisis] ✓ Rectángulo verde del bbox de junta agregado")
                
                # Actualizar junta_frame con el bbox escalado
                center_x = (enlarged_bbox[0] + enlarged_bbox[2]) / 2
                center_y = (enlarged_bbox[1] + enlarged_bbox[3]) / 2
                bbox_width = enlarged_bbox[2] - enlarged_bbox[0]
                bbox_height = enlarged_bbox[3] - enlarged_bbox[1]
                
                # Estimar px_per_mm basado en el tamaño del bbox
                estimated_diameter_mm = 100.0
                px_per_mm = min(bbox_width, bbox_height) / estimated_diameter_mm
                
                # Actualizar junta_frame
                overlay_manager.define_frame(
                    "junta_frame",
                    offset=(center_x, center_y),
                    rotation=0.0,
                    px_per_mm=px_per_mm,
                    parent_frame="world"
                )
                
                print(f"[análisis] ✓ Marco junta_frame actualizado:")
                print(f"  - Centro: ({center_x:.1f}, {center_y:.1f}) px")
                print(f"  - px_per_mm: {px_per_mm:.3f}")
                print(f"  - Dimensiones: {bbox_width:.1f}x{bbox_height:.1f} px")
                
            else:
                print(f"[análisis] ⚠️ No se detectó junta con YOLO")
                print(f"[análisis] 🔍 Formato no reconocido: {gasket_result}")
                gasket_result = None
                
        except Exception as e:
            print(f"[análisis] ❌ Error en detección de junta: {e}")
            gasket_result = None
        
        print(f"[TIMING] ⏱️  Detección de junta: {time.time() - step_start:.3f}s")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 8: YOLO holes detector (crop + detect_holes_bboxes)
        # ═══════════════════════════════════════════════════════════════════
        
        step_start = time.time()
        holes_result = None
        
        if gasket_result and (('bbox' in gasket_result) or (isinstance(gasket_result, (list, tuple)) and len(gasket_result) >= 4)):
            print(f"[análisis] 🔍 Iniciando detección de agujeros en junta recortada...")
            
            try:
                # Obtener bbox de la junta (en baja resolución)
                if isinstance(gasket_result, dict) and 'bbox' in gasket_result:
                    gasket_bbox = gasket_result['bbox']
                else:
                    gasket_bbox = list(gasket_result[:4])
                
                # ESCALAR bbox de baja resolución a alta resolución para el crop
                scale_factor = 1.0 / low_res_scale  # Factor de escalado inverso
                scaled_bbox = [
                    int(gasket_bbox[0] * scale_factor),  # x1
                    int(gasket_bbox[1] * scale_factor),  # y1
                    int(gasket_bbox[2] * scale_factor),  # x2
                    int(gasket_bbox[3] * scale_factor)   # y2
                ]
                
                print(f"[análisis] ✓ Bbox para crop escalado: {gasket_bbox} → {scaled_bbox}")
                
                # Recortar imagen de la junta usando la imagen ORIGINAL (alta resolución)
                x1, y1, x2, y2 = [int(coord) for coord in scaled_bbox]
                cropped_image = frame[y1:y2, x1:x2]  # Usar frame original con bbox escalado
                
                print(f"[análisis] ✓ Imagen recortada: {cropped_image.shape} (bbox escalado: {scaled_bbox})")
                
                # Detectar agujeros con YOLO en la imagen recortada
                holes_result = yolo_detector.detect_holes_bboxes(cropped_image)
                print(f"[TIMING] ⏱️  Detectar agujeros YOLO: {time.time() - step_start:.3f}s")
                print(f"[análisis] 🔍 Resultado detección agujeros: {holes_result}")
                print(f"[análisis] 🔍 Tipo de resultado: {type(holes_result)}")
                print(f"[análisis] 🔍 Longitud del resultado: {len(holes_result) if holes_result else 'None'}")
                
                if holes_result and len(holes_result) > 0:
                    print(f"[análisis] ✓ Agujeros detectados: {len(holes_result)} agujeros")
                    
                    # Crear objetos de overlay para cada agujero detectado
                    hole_objects = []
                    for i, hole_data in enumerate(holes_result):
                        # Extraer bbox del diccionario
                        if isinstance(hole_data, dict) and 'bbox' in hole_data:
                            hole_bbox = hole_data['bbox']
                        else:
                            hole_bbox = hole_data
                        
                        # El bbox del agujero está en coordenadas relativas a la imagen recortada
                        # Agrandar bbox en 10%
                        hole_x1, hole_y1, hole_x2, hole_y2 = hole_bbox
                        width = hole_x2 - hole_x1
                        height = hole_y2 - hole_y1
                        margin_x = width * 0.1
                        margin_y = height * 0.1
                        
                        enlarged_hole_bbox = [
                            max(0, hole_x1 - margin_x),
                            max(0, hole_y1 - margin_y),
                            min(cropped_image.shape[1], hole_x2 + margin_x),
                            min(cropped_image.shape[0], hole_y2 + margin_y)
                        ]
                        
                        # Convertir a coordenadas absolutas de la imagen original
                        abs_x1 = x1 + enlarged_hole_bbox[0]
                        abs_y1 = y1 + enlarged_hole_bbox[1]
                        abs_x2 = x1 + enlarged_hole_bbox[2]
                        abs_y2 = y1 + enlarged_hole_bbox[3]
                        
                        # Crear rectángulo rojo para cada agujero
                        hole_name = f"hole_{i+1}"
                        overlay_manager.add_polygon(
                            "world",
                            points=[
                                [abs_x1, abs_y1],  # Top-left
                                [abs_x2, abs_y1],  # Top-right
                                [abs_x2, abs_y2],  # Bottom-right
                                [abs_x1, abs_y2]   # Bottom-left
                            ],
                            name=hole_name,
                            color=(0, 0, 255),  # Rojo
                            thickness=2
                        )
                        
                        hole_objects.append(hole_name)
                        print(f"[análisis] ✓ Agujero {i+1}: bbox original=({hole_x1}, {hole_y1}, {hole_x2}, {hole_y2}), agrandado=({enlarged_hole_bbox[0]:.1f}, {enlarged_hole_bbox[1]:.1f}, {enlarged_hole_bbox[2]:.1f}, {enlarged_hole_bbox[3]:.1f}), absoluto=({abs_x1:.1f}, {abs_y1:.1f}, {abs_x2:.1f}, {abs_y2:.1f})")
                        
                        # Verificar que el objeto se creó correctamente
                        if hole_name in overlay_manager.objects:
                            obj = overlay_manager.objects[hole_name]
                            print(f"[análisis] ✓ Objeto '{hole_name}' creado correctamente:")
                            print(f"  - Marco: {obj.original_frame}")
                            print(f"  - Puntos: {obj.coordinates.get('points', 'N/A')}")
                            print(f"  - Color: {obj.properties.get('color', 'N/A')}")
                        else:
                            print(f"[análisis] ❌ ERROR: Objeto '{hole_name}' NO se creó")
                    
                    print(f"[análisis] ✓ {len(hole_objects)} objetos de agujeros creados")
                    print(f"[análisis] 📋 Objetos de agujeros en OverlayManager: {[name for name in overlay_manager.objects.keys() if name.startswith('hole_')]}")
                    
                else:
                    print(f"[análisis] ⚠️ No se detectaron agujeros en la junta")
                    holes_result = None
                    
            except Exception as e:
                print(f"[análisis] ❌ Error en detección de agujeros: {e}")
                holes_result = None
        else:
            print(f"[análisis] ⚠️ No se puede detectar agujeros: junta no detectada")
            holes_result = None
        
        print(f"[TIMING] ⏱️  Detección de agujeros: {time.time() - step_start:.3f}s")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 9: OpenCV refinamiento (cada bbox + detección azul + elipses)
        # ═══════════════════════════════════════════════════════════════════
        
        step_start = time.time()
        ellipse_objects = []
        
        if holes_result and len(holes_result) > 0:
            print(f"[análisis] 🔍 Iniciando refinamiento OpenCV para {len(holes_result)} agujeros...")
            
            try:
                for i, hole_data in enumerate(holes_result):
                    # Extraer bbox del diccionario
                    if isinstance(hole_data, dict) and 'bbox' in hole_data:
                        hole_bbox = hole_data['bbox']
                    else:
                        hole_bbox = hole_data
                    
                    # Obtener bbox agrandado (igual que antes)
                    hole_x1, hole_y1, hole_x2, hole_y2 = hole_bbox
                    width = hole_x2 - hole_x1
                    height = hole_y2 - hole_y1
                    margin_x = width * 0.1
                    margin_y = height * 0.1
                    
                    enlarged_hole_bbox = [
                        max(0, hole_x1 - margin_x),
                        max(0, hole_y1 - margin_y),
                        min(cropped_image.shape[1], hole_x2 + margin_x),
                        min(cropped_image.shape[0], hole_y2 + margin_y)
                    ]
                    
                    # Recortar imagen del agujero para OpenCV
                    hole_crop = cropped_image[
                        int(enlarged_hole_bbox[1]):int(enlarged_hole_bbox[3]),
                        int(enlarged_hole_bbox[0]):int(enlarged_hole_bbox[2])
                    ]
                    
                    print(f"[análisis] ✓ Agujero {i+1}: crop shape={hole_crop.shape}")
                    
                    # Aplicar OpenCV para detectar elipses (método del pipeline original)
                    # Extraer canales BGR
                    b_channel = hole_crop[:, :, 0].astype(np.float32)
                    g_channel = hole_crop[:, :, 1].astype(np.float32)
                    r_channel = hole_crop[:, :, 2].astype(np.float32)
                    
                    # Crear máscara donde azul es predominante
                    # Un píxel es "azul" si B > (G + R) * factor
                    factor_predominancia = 0.7
                    es_azul = b_channel > (g_channel + r_channel) * factor_predominancia
                    
                    # Máscara binaria: azul → 255, no azul → 0
                    mask = np.zeros_like(b_channel, dtype=np.uint8)
                    mask[es_azul] = 255
                    
                    # Encontrar contornos
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    if len(contours) > 0:
                        # Encontrar el contorno más grande
                        largest_contour = max(contours, key=cv2.contourArea)
                        area = cv2.contourArea(largest_contour)
                        
                        # Filtrar contornos muy pequeños (ruido)
                        if area < 10:
                            print(f"[análisis] ⚠️ Agujero {i+1}: contorno muy pequeño (área={area:.1f})")
                            continue
                        
                        # Ajustar elipse al contorno
                        if len(largest_contour) >= 5:  # Mínimo 5 puntos para ajustar elipse
                            ellipse = cv2.fitEllipse(largest_contour)
                            center, axes, angle = ellipse
                            
                            print(f"[análisis] ✓ Elipse detectada en agujero {i+1}: center={center}, axes={axes}, angle={angle:.1f}°")
                            
                            # Convertir coordenadas de la elipse a coordenadas absolutas
                            abs_center_x = x1 + enlarged_hole_bbox[0] + center[0]
                            abs_center_y = y1 + enlarged_hole_bbox[1] + center[1]
                            
                            # Crear elipse verde
                            ellipse_name = f"ellipse_{i+1}"
                            overlay_manager.add_ellipse(
                                "world",
                                center=(abs_center_x, abs_center_y),
                                axes=(axes[0]/2, axes[1]/2),  # OpenCV usa diámetros, nosotros radios
                                angle=angle,
                                name=ellipse_name,
                                color=(0, 255, 0),  # Verde
                                thickness=2
                            )
                            
                            # Crear centro rojo
                            center_name = f"hole_center_{i+1}"
                            overlay_manager.add_circle(
                                "world",
                                center=(abs_center_x, abs_center_y),
                                radius=3,  # 3px de radio
                                name=center_name,
                                color=(0, 0, 255),  # Rojo
                                filled=True
                            )
                            
                            ellipse_objects.extend([ellipse_name, center_name])
                            print(f"[análisis] ✓ Elipse verde y centro rojo creados para agujero {i+1}")
                            
                        else:
                            # Si no hay suficientes puntos para elipse, usar momentos
                            moments = cv2.moments(largest_contour)
                            if moments["m00"] != 0:
                                center_x = int(moments["m10"] / moments["m00"])
                                center_y = int(moments["m01"] / moments["m00"])
                                
                                print(f"[análisis] ✓ Centro detectado con momentos en agujero {i+1}: center=({center_x}, {center_y})")
                                
                                # Convertir coordenadas de la elipse a coordenadas absolutas
                                abs_center_x = x1 + enlarged_hole_bbox[0] + center_x
                                abs_center_y = y1 + enlarged_hole_bbox[1] + center_y
                                
                                # Crear solo centro rojo (sin elipse)
                                center_name = f"hole_center_{i+1}"
                                overlay_manager.add_circle(
                                    "world",
                                    center=(abs_center_x, abs_center_y),
                                    radius=3,  # 3px de radio
                                    name=center_name,
                                    color=(0, 0, 255),  # Rojo
                                    filled=True
                                )
                                
                                ellipse_objects.append(center_name)
                                print(f"[análisis] ✓ Centro rojo creado para agujero {i+1} (sin elipse)")
                            else:
                                print(f"[análisis] ⚠️ Agujero {i+1}: no se pudo calcular centro con momentos")
                    else:
                        print(f"[análisis] ⚠️ Agujero {i+1}: no se encontraron contornos azules")
                        
            except Exception as e:
                print(f"[análisis] ❌ Error en refinamiento OpenCV: {e}")
                ellipse_objects = []
        else:
            print(f"[análisis] ⚠️ No se puede aplicar refinamiento OpenCV: no hay agujeros detectados")
            ellipse_objects = []
        
        print(f"[TIMING] ⏱️  Refinamiento OpenCV: {time.time() - step_start:.3f}s")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 10: Crear segmento y punto medio (misma estrategia del pipeline original)
        # ═══════════════════════════════════════════════════════════════════
        
        step_start = time.time()
        segment_objects = []
        
        if ellipse_objects and len(ellipse_objects) > 0:
            print(f"[análisis] 🔍 Calculando segmento y punto medio para {len(ellipse_objects)} centros...")
            
            try:
                # Extraer centros de los objetos de elipses/centros
                centros = []
                for obj_name in ellipse_objects:
                    if obj_name.startswith('hole_center_'):
                        if obj_name in overlay_manager.objects:
                            obj = overlay_manager.objects[obj_name]
                            center = obj.coordinates.get('center')
                            if center:
                                centros.append(center)
                                print(f"[análisis] ✓ Centro extraído de {obj_name}: {center}")
                
                if len(centros) >= 2:
                    # Ordenar de izquierda a derecha (misma estrategia del pipeline original)
                    centros_ordenados = sorted(centros, key=lambda p: (p[0], p[1]))
                    
                    # Extremos (para la línea de referencia)
                    p1 = centros_ordenados[0]
                    p2 = centros_ordenados[-1]
                    
                    print(f"[análisis] ✓ Centros ordenados: {centros_ordenados}")
                    print(f"[análisis] ✓ P1 (más a la izquierda): {p1}")
                    print(f"[análisis] ✓ P2 (más a la derecha): {p2}")
                    
                    # Calcular punto medio entre extremos
                    punto_medio_extremos = (
                        int((p1[0] + p2[0]) / 2),
                        int((p1[1] + p2[1]) / 2)
                    )
                    
                    # Calcular centroide de todos los centros (más preciso)
                    centro_x = sum(p[0] for p in centros) / len(centros)
                    centro_y = sum(p[1] for p in centros) / len(centros)
                    punto_medio_centroide = (int(centro_x), int(centro_y))
                    
                    print(f"[análisis] ✓ Punto medio entre extremos: {punto_medio_extremos}")
                    print(f"[análisis] ✓ Punto medio centroide: {punto_medio_centroide}")
                    
                    # Usar el centroide (más preciso para agujeros no perfectamente equiespaciados)
                    punto_medio = punto_medio_centroide
                    
                    # Calcular ángulo del segmento
                    angle_rad = np.arctan2(p2[1] - p1[1], p2[0] - p1[0])
                    angle_deg = np.degrees(angle_rad)
                    
                    print(f"[análisis] ✓ Ángulo del segmento: {angle_deg:.2f}° ({angle_rad:.4f} rad)")
                    
                    # Distancia en píxeles
                    distancia_px = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                    print(f"[análisis] ✓ Distancia del segmento: {distancia_px:.1f} px")
                    
                    # Crear línea de referencia (segmento)
                    segment_name = "reference_segment"
                    overlay_manager.add_line(
                        "world",
                        start=p1,
                        end=p2,
                        name=segment_name,
                        color=(255, 0, 0),  # Rojo
                        thickness=3
                    )
                    
                    # Crear punto medio
                    midpoint_name = "segment_midpoint"
                    overlay_manager.add_circle(
                        "world",
                        center=punto_medio,
                        radius=5,  # 5px de radio
                        name=midpoint_name,
                        color=(0, 255, 255),  # Cyan
                        filled=True
                    )
                    
                    segment_objects.extend([segment_name, midpoint_name])
                    print(f"[análisis] ✓ Segmento rojo y punto medio cyan creados")
                    print(f"[análisis] ✓ Segmento: P1={p1} → P2={p2}")
                    print(f"[análisis] ✓ Punto medio: {punto_medio}")
                    
                else:
                    print(f"[análisis] ⚠️ No hay suficientes centros para crear segmento (necesario: 2, encontrado: {len(centros)})")
                    
            except Exception as e:
                print(f"[análisis] ❌ Error calculando segmento y punto medio: {e}")
                segment_objects = []
        else:
            print(f"[análisis] ⚠️ No se puede calcular segmento: no hay centros de agujeros")
            segment_objects = []
        
        print(f"[TIMING] ⏱️  Cálculo de segmento y punto medio: {time.time() - step_start:.3f}s")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 11: Agregar objetos de ArUcos detectados
        # ═══════════════════════════════════════════════════════════════════
        
        aruco_objects = []
        
        # Agregar objetos del Frame ArUco si está detectado
        if frame_detected and frame_result:
            frame_center = frame_result['center']
            frame_corners = frame_result['corners']
            frame_angle = np.arctan2(frame_result['rotation_matrix'][1][0], frame_result['rotation_matrix'][0][0])
            
            # Contorno del Frame ArUco
            overlay_manager.add_polygon(
                "world",
                points=frame_corners,
                name=f"aruco_contour_{frame_aruco_id}",
                color=(0, 255, 255),  # Amarillo
                thickness=2
            )
            
            # Ejes del Frame ArUco
            image_height, image_width = frame.shape[:2]
            axis_length = max(image_width, image_height)
            
            x_end1 = (frame_center[0] + axis_length * np.cos(frame_angle), frame_center[1] + axis_length * np.sin(frame_angle))
            x_end2 = (frame_center[0] - axis_length * np.cos(frame_angle), frame_center[1] - axis_length * np.sin(frame_angle))
            
            y_angle = frame_angle + np.pi / 2
            y_end1 = (frame_center[0] + axis_length * np.cos(y_angle), frame_center[1] + axis_length * np.sin(y_angle))
            y_end2 = (frame_center[0] - axis_length * np.cos(y_angle), frame_center[1] - axis_length * np.sin(y_angle))
            
            overlay_manager.add_line("world", start=x_end2, end=x_end1, name=f"aruco_x_axis_{frame_aruco_id}", color=(0, 255, 255), thickness=2)
            overlay_manager.add_line("world", start=y_end2, end=y_end1, name=f"aruco_y_axis_{frame_aruco_id}", color=(0, 255, 255), thickness=2)
            
            # Centro del Frame ArUco
            overlay_manager.add_circle("world", center=frame_center, radius=5, name=f"aruco_center_{frame_aruco_id}", color=(0, 255, 255), filled=True)
            
            # Verificar si el checkbox del Frame ArUco está habilitado
            show_frame = aruco_config.get('aruco', {}).get('show_frame', True)
            
            if show_frame:
                aruco_objects.extend([f"aruco_contour_{frame_aruco_id}", f"aruco_x_axis_{frame_aruco_id}", f"aruco_y_axis_{frame_aruco_id}", f"aruco_center_{frame_aruco_id}"])
                print(f"[análisis] ✅ Objetos del Frame ArUco (ID: {frame_aruco_id}) agregados (checkbox habilitado)")
            else:
                print(f"[análisis] ⚠️ Frame ArUco detectado pero checkbox deshabilitado - NO agregado")
        
        # Agregar objetos del Tool ArUco si está detectado
        if tool_detected and tool_result:
            tool_center = tool_result['center']
            tool_corners = tool_result['corners']
            tool_angle = np.arctan2(tool_result['rotation_matrix'][1][0], tool_result['rotation_matrix'][0][0])
            
            # Contorno del Tool ArUco
            overlay_manager.add_polygon("world", points=tool_corners, name=f"aruco_contour_{tool_aruco_id}", color=(255, 0, 0), thickness=2)
            
            # Ejes del Tool ArUco
            image_height, image_width = frame.shape[:2]
            axis_length = max(image_width, image_height)
            
            x_end1 = (tool_center[0] + axis_length * np.cos(tool_angle), tool_center[1] + axis_length * np.sin(tool_angle))
            x_end2 = (tool_center[0] - axis_length * np.cos(tool_angle), tool_center[1] - axis_length * np.sin(tool_angle))
            
            y_angle = tool_angle + np.pi / 2
            y_end1 = (tool_center[0] + axis_length * np.cos(y_angle), tool_center[1] + axis_length * np.sin(y_angle))
            y_end2 = (tool_center[0] - axis_length * np.cos(y_angle), tool_center[1] - axis_length * np.sin(y_angle))
            
            overlay_manager.add_line("world", start=x_end2, end=x_end1, name=f"aruco_x_axis_{tool_aruco_id}", color=(255, 0, 0), thickness=2)
            overlay_manager.add_line("world", start=y_end2, end=y_end1, name=f"aruco_y_axis_{tool_aruco_id}", color=(255, 0, 0), thickness=2)
            
            # Centro del Tool ArUco
            overlay_manager.add_circle("world", center=tool_center, radius=5, name=f"aruco_center_{tool_aruco_id}", color=(255, 0, 0), filled=True)
            
            # Verificar si el checkbox del Tool ArUco está habilitado
            show_tool = aruco_config.get('aruco', {}).get('show_tool', True)
            
            if show_tool:
                aruco_objects.extend([f"aruco_contour_{tool_aruco_id}", f"aruco_x_axis_{tool_aruco_id}", f"aruco_y_axis_{tool_aruco_id}", f"aruco_center_{tool_aruco_id}"])
                print(f"[análisis] ✅ Objetos del Tool ArUco (ID: {tool_aruco_id}) agregados (checkbox habilitado)")
            else:
                print(f"[análisis] ⚠️ Tool ArUco detectado pero checkbox deshabilitado - NO agregado")
        
        # ═══════════════════════════════════════════════════════════════════
        # PASO 9: Crear lista de renderizado con objetos necesarios
        # ═══════════════════════════════════════════════════════════════════
        
        # Crear lista de objetos para renderizar
        all_objects = ["center_circle"] + aruco_objects  # ← Solo centro del troquel + ArUcos detectados
        
        # Agregar bbox de junta si fue detectado
        if gasket_result and (('bbox' in gasket_result) or (isinstance(gasket_result, (list, tuple)) and len(gasket_result) >= 4)):
            all_objects.append("gasket_bbox")
            print(f"[análisis] ✓ Bbox de junta agregado a la lista de renderizado")
        
        # Agregar objetos de agujeros si fueron detectados
        if holes_result and len(holes_result) > 0:
            hole_objects = [f"hole_{i+1}" for i in range(len(holes_result))]
            all_objects.extend(hole_objects)
            print(f"[análisis] ✓ {len(hole_objects)} objetos de agujeros agregados a la lista de renderizado")
        
        # Agregar objetos de elipses si fueron detectados
        if ellipse_objects and len(ellipse_objects) > 0:
            all_objects.extend(ellipse_objects)
            print(f"[análisis] ✓ {len(ellipse_objects)} objetos de elipses agregados a la lista de renderizado")
        
        # Agregar objetos de segmento si fueron detectados
        if segment_objects and len(segment_objects) > 0:
            all_objects.extend(segment_objects)
            print(f"[análisis] ✓ {len(segment_objects)} objetos de segmento agregados a la lista de renderizado")
        
        # Verificar que todos los objetos existen antes de crear la renderlist
        existing_objects = []
        for obj_name in all_objects:
            if obj_name in overlay_manager.objects:
                existing_objects.append(obj_name)
                print(f"[análisis] ✓ Objeto '{obj_name}' encontrado")
            else:
                print(f"[análisis] ⚠️ Objeto '{obj_name}' no existe, omitiendo...")
        
        print(f"[análisis] 📋 Objetos disponibles en OverlayManager: {list(overlay_manager.objects.keys())}")
        print(f"[análisis] 🎯 Objetos que se van a renderizar: {existing_objects}")
        
        # Verificar específicamente el centro del troquel
        if "center_circle" in overlay_manager.objects:
            obj = overlay_manager.objects["center_circle"]
            print(f"[análisis] 🔍 Centro del troquel:")
            print(f"  - Existe: ✓")
            print(f"  - Marco: {obj.original_frame}")
            print(f"  - Centro: {obj.coordinates.get('center', 'N/A')}")
            print(f"  - Radio: {obj.coordinates.get('radius', 'N/A')}")
            print(f"  - Color: {obj.properties.get('color', 'N/A')}")
        else:
            print(f"[análisis] ❌ ERROR: 'center_circle' NO existe en OverlayManager")
        
        # Crear lista de renderizado usando el método correcto de la librería
        overlay_manager.create_renderlist(
            *existing_objects,  # ← Argumentos posicionales
            name="analysis_overlay"
        )
        print(f"[análisis] ✓ Renderlist 'analysis_overlay' creada con {len(existing_objects)} objetos: {existing_objects}")
        
        print(f"[TIMING] ⏱️  Preparar renderizado: {time.time() - step_start:.3f}s")
        
        # ⚡ RENDERIZAR UNA SOLA VEZ al final
        print(f"[análisis] 🎨 Iniciando renderizado con {len(existing_objects)} objetos...")
        for obj_name in existing_objects:
            if obj_name in overlay_manager.objects:
                obj = overlay_manager.objects[obj_name]
                print(f"[análisis] 🎯 Renderizando '{obj_name}': marco={obj.original_frame}, tipo={obj.type}")
            else:
                print(f"[análisis] ⚠️ Objeto '{obj_name}' no encontrado para renderizar")
        
        result_image, view_time = overlay_manager.render(
            gray_background,
            renderlist="analysis_overlay",  # ← Usar nombre de la lista
            view_time=500  # 0.5 segundos
        )
        
        print(f"[TIMING] ⏱️  Renderizado directo: {time.time() - step_start:.3f}s")
        print(f"[análisis] 🎨 Renderizado completado: {result_image.shape}, view_time={view_time}ms")
        
        # Verificar si la lista de renderizado se creó correctamente
        try:
            renderlist_content = overlay_manager.get_renderlist("analysis_overlay")
            print(f"[análisis] 📋 Contenido de la renderlist: {renderlist_content}")
        except Exception as e:
            print(f"[análisis] ❌ Error obteniendo renderlist: {e}")
        
        # Codificar imagen a base64
        _, buffer = cv2.imencode('.jpg', result_image, [cv2.IMWRITE_JPEG_QUALITY, 75])
        imagen_base64 = base64.b64encode(buffer).decode('utf-8')
        
        print(f"[TIMING] ⏱️  Codificar imagen: {time.time() - step_start:.3f}s")
        print(f"[TIMING] ⏱️  TIEMPO TOTAL: {time.time() - start_time:.3f}s")
        
        return jsonify({
            'ok': True,
            'analisis_exitoso': True,
            'imagen_base64': imagen_base64,
            'data': {
                'aruco': {'detected': True, 'test_mode': True},
                'holes': {'total_detected': 0, 'test_mode': True},
                'overlay_objects': all_objects,
                'render_time_ms': view_time,
                'total_time_ms': int((time.time() - start_time) * 1000)
            }
        })
        
    except Exception as e:
        print(f"[TIMING] ⏱️  ERROR TOTAL: {time.time() - start_time:.3f}s")
        print(f"[análisis] Error en POST /api/analyze_new: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'ok': False,
            'error': str(e)
        }), 500

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
