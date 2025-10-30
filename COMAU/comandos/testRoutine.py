"""
COMAU Test Routine Command Module
=================================

Este módulo contiene la función específica para el comando RUTINA DE PRUEBA del robot COMAU.

Autor: Illinois Automation
Fecha: 2024
"""

import json
import time
import uuid
import sys
import os
from typing import Dict, Any, Optional
from mqtt_manager import get_mqtt_manager
# Quitar: from flask_socketio import SocketIO
# Quitar: from illinois-server import socketio, app

# Agregar el directorio padre al path para importar constants y utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from constants import get_constant
from comau_utils import addWordToSequence, sendSequenceToBroker, waitComauResponse

# Agregar el directorio raíz del proyecto al path para importar server_test
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from src.vision.vision_manager import server_test


def testRoutine(verbose: bool = False) -> Dict[str, Any]:
    """
    Ejecuta la rutina de prueba del robot COMAU.
    
    Este comando ejecuta la rutina de prueba usando el nuevo sistema modular:
    1. Crea secuencia completa con ambos comandos
    2. Envía secuencia completa al robot (ID_COM + MAQUINA_ESTADOS = 10)
    3. Espera primera respuesta: "Move to Feeder done!"
    4. Espera segunda respuesta: "Take a Photo!" (con sequence_id + 1)
    5. Ejecuta análisis de imagen (server_test) - mismo que el botón PROBAR del dashboard
    
    Returns:
        Dict con el resultado de la ejecución:
        - ok: bool - Si la operación fue exitosa
        - status: str - Estado del comando ('success', 'error', 'warning')
        - sequence_id: str - ID único de la secuencia
        - message: str - Mensaje descriptivo
        - robot_status: str - Estado del robot
        - error: str - Mensaje de error si aplica
    """
    try:
        # Generar ID único de secuencia
        sequence_id = int(time.time()) % 10000  # ID de 4 dígitos
        
        if verbose:
            print(f"[testRoutine] 🤖 Iniciando RUTINA DE PRUEBA con ID: {sequence_id}")
        
        # Crear secuencia completa con ambos comandos
        if verbose:
            print(f"[testRoutine] 📋 Creando secuencia completa...")
        sequence = []
        
        # 1. Agregar comando ID de secuencia
        sequence.extend(addWordToSequence(get_constant('ID_COM', 1), str(sequence_id)))
        if verbose:
            print(f"[testRoutine] ✅ ID de secuencia {sequence_id} agregado a la secuencia")
        
        # 2. Agregar comando RUTINA DE PRUEBA
        sequence.extend(addWordToSequence(get_constant('MAQUINA_ESTADOS', 3), "10"))
        if verbose:
            print(f"[testRoutine] ✅ Comando MAQUINA_ESTADOS=10 agregado a la secuencia")

        # 2.5 Agregar CANTIDAD_MUESCAS desde juntas.json (junta seleccionada)
        try:
            juntas_path = 'juntas.json'
            if not os.path.exists(juntas_path):
                # Intentar junto a config.json
                cfg_path = 'config.json'
                if os.path.exists(cfg_path):
                    juntas_path = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), 'juntas.json')
            cantidad_muescas = 0
            altura_junta_mm = 0.0
            if os.path.exists(juntas_path):
                with open(juntas_path, 'r', encoding='utf-8') as f:
                    db = json.load(f)
                selected_id = db.get('selected_id')
                juntas = db.get('juntas', [])
                junta = next((j for j in juntas if j.get('id') == selected_id), None)
                if junta:
                    cantidad_muescas = int(junta.get('cantidad_muescas') or 0)
                    # Fallback si no está seteado: usar longitud de lista 'muescas' si existe
                    if not cantidad_muescas and isinstance(junta.get('muescas'), list):
                        cantidad_muescas = len(junta['muescas'])

                    # Calcular alto de la junta en mm si está parametrizada
                    try:
                        if junta.get('parametrizado') and junta.get('parametros_proporcionales'):
                            px_mm = float(junta.get('px_mm', 1.0) or 1.0)
                            params = junta.get('parametros_proporcionales', {})
                            alto_px = params.get('alto_junta_px')
                            if isinstance(alto_px, (int, float)) and px_mm:
                                altura_junta_mm = float(alto_px) / px_mm
                    except Exception:
                        altura_junta_mm = 0.0
            else:
                print(f"[testRoutine] ⚠️ No se encontró juntas.json para obtener CANTIDAD_MUESCAS")

            sequence.extend(addWordToSequence(get_constant('CANTIDAD_MUESCAS', 30), str(cantidad_muescas)))
            if verbose:
                print(f"[testRoutine] ✅ CANTIDAD_MUESCAS={cantidad_muescas} agregado a la secuencia")

            # 2.6 Agregar dZ con alto de la junta (mm * 10, redondeado)
            try:
                dz_val = (2200 - int(round(altura_junta_mm * 10))) if altura_junta_mm else 0
                sequence.extend(addWordToSequence(get_constant('dZ', 24), str(dz_val)))
                if verbose:
                    print(f"[testRoutine] ✅ dZ (2200 - alto_junta*10)={dz_val} agregado a la secuencia")
            except Exception as dz_exc:
                print(f"[testRoutine] ⚠️ No se pudo agregar dZ (alto de junta): {dz_exc}")
        except Exception as e:
            print(f"[testRoutine] ⚠️ No se pudo agregar CANTIDAD_MUESCAS: {e}")
        
        # 3. Enviar secuencia completa
        if verbose:
            print(f"[testRoutine] 📋 Enviando secuencia completa al robot...")
        result = sendSequenceToBroker(sequence, "TEST_ROUTINE")
        
        if not result.get('ok', False):
            if verbose:
                print(f"[testRoutine] ❌ Error enviando secuencia: {result.get('message', 'Error desconocido')}")
            return {
                'ok': False,
                'status': 'error',
                'sequence_id': str(sequence_id),
                'message': f"Error enviando secuencia RUTINA DE PRUEBA: {result.get('message', 'Error desconocido')}",
                'robot_status': 'error',
                'error': result.get('error', 'Error enviando secuencia')
            }
        
        if verbose:
            print(f"[testRoutine] ✅ Secuencia completa enviada correctamente")
            print(f"[testRoutine] 🔎 IDs esperados tras envío: 'Move to Feeder done!' -> {sequence_id}, 'Take a Photo!' -> {sequence_id + 1}")
        
        # 4. Esperar respuesta específica del robot
        if verbose:
            print(f"[testRoutine] 📋 Paso 4: Esperando respuesta 'Move to Feeder done!' (ID {sequence_id}) del robot...")
        response_result = waitComauResponse(sequence_id, "Move to Feeder done!", 30000)  # 30 segundos timeout
        
        if response_result['success']:
            if verbose:
                print(f"[testRoutine] ✅ Primera respuesta recibida: 'Move to Feeder done!'")
            
            # 5. Esperar segunda respuesta específica del robot
            if verbose:
                print(f"[testRoutine] 📋 Paso 5: Esperando segunda respuesta 'Take a Photo!' (ID {sequence_id + 1}) del robot...")
            response_result_2 = waitComauResponse(sequence_id + 1, "Take a Photo!", 30000)  # 30 segundos timeout
            
            if response_result_2['success']:
                print(f"[testRoutine] ✅ Segunda respuesta recibida: 'Take a Photo!'")
                # Emitir eventos por websocket usando sockets.socketio si está inicializado
                try:
                    import sockets
                    if getattr(sockets, 'socketio', None) is not None:
                        sockets.socketio.emit('AUTO_ANALYZE')
                    else:
                        print("[testRoutine] ⚠️ SocketIO no inicializado (sockets.socketio es None)")
                except Exception as socket_exc:
                    print(f"[testRoutine] ⚠️ No se pudo emitir AUTO_ANALYZE vía websocket: {socket_exc}")

                # Ejecutar procesamiento visual
                try:
                    from src.vision.vision_manager import server_test
                    server_result = server_test()
                    if isinstance(server_result, dict) and 'overlay_image' in server_result:
                        result_no_img = {k: v for k, v in server_result.items() if k != 'overlay_image'}
                    else:
                        result_no_img = server_result

                    # Formatear tabla con valores redondeados de trajectory_vectors
                    trajectory_vectors = result_no_img.get('trajectory_vectors', []) or []
                    rounded_vectors = []
                    for item in trajectory_vectors:
                        segmento = item.get('segmento', 'N/A')
                        vec = item.get('vector_mm') or item.get('centro_mm') or [0.0, 0.0]
                        x = round(float(vec[0]), 2) if isinstance(vec, (list, tuple)) and len(vec) > 0 else 0.0
                        y = round(float(vec[1]), 2) if isinstance(vec, (list, tuple)) and len(vec) > 1 else 0.0
                        rounded_vectors.append({'segmento': segmento, 'vector_mm': [x, y]})

                    # Imprimir tabla elegante
                    print("[testRoutine] 📊 Resultados de trayectoria (mm):")
                    print("[testRoutine] ┌───────────────────────────────────────────────┬────────────┬────────────┐")
                    print("[testRoutine] │ Segmento                                      │   X (mm)   │   Y (mm)   │")
                    print("[testRoutine] ├───────────────────────────────────────────────┼────────────┼────────────┤")
                    for rv in rounded_vectors:
                        seg = str(rv['segmento'])[:47].ljust(47)
                        x_str = f"{rv['vector_mm'][0]:.2f}".rjust(10)
                        y_str = f"{rv['vector_mm'][1]:.2f}".rjust(10)
                        print(f"[testRoutine] │ {seg} │ {x_str} │ {y_str} │")
                    print("[testRoutine] └───────────────────────────────────────────────┴────────────┴────────────┘")

                    # Guardar vectores redondeados para su uso posterior
                    try:
                        save_payload = {
                            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
                            'rounded_trajectory_vectors': rounded_vectors
                        }
                        with open('last_trajectory_vectors.json', 'w', encoding='utf-8') as f:
                            json.dump(save_payload, f, ensure_ascii=False, indent=2)
                        print("[testRoutine] 💾 Vectores redondeados guardados en last_trajectory_vectors.json")
                    except Exception as save_exc:
                        print(f"[testRoutine] ⚠️ No se pudo guardar last_trajectory_vectors.json: {save_exc}")

                    # Construir nueva secuencia para enviar MUESCAS_MATRIX_XY y luego MAQUINA_ESTADOS=40
                    try:
                        sequence_muescas = []
                        base_idx = get_constant('MUESCAS_MATRIX_XY', 31)
                        # Usar los valores crudos del servidor para no perder precisión
                        server_vectors = server_result.get('trajectory_vectors', []) or []
                        cantidad = len(server_vectors)
                        if cantidad == 0:
                            print("[testRoutine] ⚠️ No hay vectores de trayectoria para enviar")
                        # Primero, agregar MAQUINA_ESTADOS=40
                        sequence_muescas.extend(addWordToSequence(get_constant('MAQUINA_ESTADOS', 3), "40"))
                        # Luego, pares X,Y en posiciones contiguas a partir de MUESCAS_MATRIX_XY
                        for i, rv in enumerate(server_vectors, start=1):
                            idx_x = base_idx + (i - 1) * 2
                            idx_y = idx_x + 1
                            vec = rv.get('vector_mm') or rv.get('centro_mm') or [0.0, 0.0]
                            x_raw = float(vec[0]) if isinstance(vec, (list, tuple)) and len(vec) > 0 else 0.0
                            y_raw = float(vec[1]) if isinstance(vec, (list, tuple)) and len(vec) > 1 else 0.0
                            x_val = str(int(round(x_raw * 10)))
                            y_val = str(int(round(y_raw * 10)))
                            sequence_muescas.extend(addWordToSequence(idx_x, x_val))
                            sequence_muescas.extend(addWordToSequence(idx_y, y_val))
                        
                        # Enviar secuencia
                        print(f"[testRoutine] 🚀 Enviando secuencia de muescas (cantidad={cantidad}) + MAQUINA_ESTADOS=40...")
                        send_result = sendSequenceToBroker(sequence_muescas, "SET_MUESCAS")
                        if not send_result.get('ok', False):
                            print(f"[testRoutine] ❌ Error enviando secuencia de muescas: {send_result.get('message')}")
                        else:
                            print("[testRoutine] ✅ Secuencia de muescas enviada correctamente")
                            print(f"[testRoutine] 🔎 ID esperado para confirmación final 'Troqueles hechos!': {sequence_id + 2}")
                            # Esperar confirmación: ID_COM + 1 respecto del último (original + 2) y texto exacto "Troqueles hechos!"
                            try:
                                print(f"[testRoutine] ⏳ Esperando 'Troqueles hechos!' (ID {sequence_id + 2})...")
                                confirm_result = waitComauResponse(sequence_id + 2, "Troqueles hechos!", 30000)
                                if confirm_result.get('success'):
                                    print("[testRoutine] ✅ Confirmación recibida: 'Troqueles hechos!'")
                                else:
                                    if confirm_result.get('id_found'):
                                        print(f"[testRoutine] ⚠️ Respuesta recibida pero diferente: '{confirm_result.get('response_text','')}'")
                                    else:
                                        print(f"[testRoutine] ❌ No se recibió confirmación de troquelado: {confirm_result.get('error_message','sin detalle')}")
                            except Exception as wait_exc:
                                print(f"[testRoutine] ⚠️ Error esperando confirmación de troquelado: {wait_exc}")
                    except Exception as seq_exc:
                        print(f"[testRoutine] ❌ Error construyendo/enviando secuencia de muescas: {seq_exc}")
                    # Emitir resultado completo al frontend (incluye overlay para que dashboard muestre imagen)
                    try:
                        import sockets
                        if getattr(sockets, 'socketio', None) is not None:
                            sockets.socketio.emit('SERVER_TEST_RESULT', server_result)
                            print("[testRoutine] 📤 Evento SERVER_TEST_RESULT emitido (websocket)")
                        else:
                            print("[testRoutine] ⚠️ SocketIO no inicializado, no se emite SERVER_TEST_RESULT")
                    except Exception as emit_exc:
                        print(f"[testRoutine] ⚠️ Error emitiendo SERVER_TEST_RESULT: {emit_exc}")
                except Exception as vision_exc:
                    print(f"[testRoutine] ❌ Error ejecutando análisis visual: {vision_exc}")

                return {
                    'ok': True,
                    'status': 'success',
                    'sequence_id': str(sequence_id),
                    'message': "Rutina de prueba: 'Take a Photo!' recibido",
                    'robot_status': 'active',
                    'response_text': response_result_2['response_text'],
                    'full_response': response_result_2['full_response'],
                    'first_response': response_result['response_text']
                }
            else:
                # Analizar el tipo de error de la segunda respuesta
                if response_result_2['id_found']:
                    if verbose:
                        print(f"[testRoutine] ⚠️ Segunda respuesta recibida pero no con el mensaje esperado")
                    return {
                        'ok': True,
                        'status': 'warning',
                        'sequence_id': str(sequence_id),
                        'message': f"Primera respuesta OK, pero segunda no es 'Take a Photo!'. Recibido: '{response_result_2['response_text']}'",
                        'robot_status': 'active',
                        'response_text': response_result_2['response_text'],
                        'full_response': response_result_2['full_response'],
                        'first_response': response_result['response_text'],
                        'error': response_result_2['error_message']
                    }
                else:
                    if verbose:
                        print(f"[testRoutine] ❌ No se recibió segunda respuesta del robot: {response_result_2['error_message']}")
                    return {
                        'ok': True,
                        'status': 'error',
                        'sequence_id': str(sequence_id),
                        'message': f"Primera respuesta OK, pero no se recibió segunda respuesta: {response_result_2['error_message']}",
                        'robot_status': 'partial_response',
                        'first_response': response_result['response_text'],
                        'error': response_result_2['error_message']
                    }
        else:
            # Analizar el tipo de error
            if response_result['id_found']:
                if verbose:
                    print(f"[testRoutine] ⚠️ Robot respondió pero no con el mensaje esperado")
                return {
                    'ok': True,
                    'status': 'warning',
                    'sequence_id': str(sequence_id),
                    'message': f"Robot respondió pero no con 'Move to Feeder done!'. Recibido: '{response_result['response_text']}'",
                    'robot_status': 'active',
                    'response_text': response_result['response_text'],
                    'full_response': response_result['full_response'],
                    'error': response_result['error_message']
                }
            else:
                if verbose:
                    print(f"[testRoutine] ❌ No se recibió respuesta del robot: {response_result['error_message']}")
                return {
                    'ok': True,
                    'status': 'error',
                    'sequence_id': str(sequence_id),
                    'message': f"No se recibió respuesta del robot: {response_result['error_message']}",
                    'robot_status': 'no_response',
                    'error': response_result['error_message']
                }
            
    except Exception as e:
        if verbose:
            print(f"[testRoutine] ❌ Error interno en RUTINA DE PRUEBA: {str(e)}")
        return {
            'ok': False,
            'error': str(e),
            'status': 'error',
            'message': f'Error interno: {str(e)}',
            'robot_status': 'error'
        }
