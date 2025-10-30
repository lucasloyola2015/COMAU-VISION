"""
COMAU Move to Home Command Module
=================================

Este módulo contiene la función específica para el comando MOVE TO HOME del robot COMAU.

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

# Agregar el directorio padre al path para importar constants y utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from constants import get_constant
from comau_utils import addWordToSequence, sendSequenceToBroker, waitComauResponse


def move_to_home() -> Dict[str, Any]:
    """
    Ejecuta el comando MOVE TO HOME del robot COMAU.
    
    Este comando mueve el robot a su posición HOME usando el nuevo sistema modular:
    1. Establece ID de secuencia
    2. Envía comando MOVE_TO_HOME
    3. Espera respuesta específica del robot
    
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
        
        print(f"[cmd_move_to_home] 🤖 Iniciando MOVE TO HOME con ID: {sequence_id}")
        
        # 1. Establecer ID de secuencia
        print(f"[cmd_move_to_home] 📋 Paso 1: Estableciendo ID de secuencia {sequence_id}")
        id_result = sendSequenceToBroker(
            addWordToSequence(get_constant('ID_COM', 1), str(sequence_id)),
            "SET_ID_COM"
        )
        
        if not id_result.get('ok', False):
            print(f"[cmd_move_to_home] ❌ Error estableciendo ID: {id_result.get('message', 'Error desconocido')}")
            return {
                'ok': False,
                'status': 'error',
                'sequence_id': str(sequence_id),
                'message': f"Error estableciendo ID de secuencia: {id_result.get('message', 'Error desconocido')}",
                'robot_status': 'error',
                'error': id_result.get('error', 'Error estableciendo ID')
            }
        
        print(f"[cmd_move_to_home] ✅ ID de secuencia {sequence_id} establecido correctamente")
        
        # 2. Enviar comando MOVE TO HOME
        print(f"[cmd_move_to_home] 📋 Paso 2: Enviando comando MOVE TO HOME")
        move_result = sendSequenceToBroker(
            addWordToSequence(get_constant('MOVE_TO_HOME', 4), "1"),
            "MOVE_TO_HOME"
        )
        
        if not move_result.get('ok', False):
            print(f"[cmd_move_to_home] ❌ Error enviando comando: {move_result.get('message', 'Error desconocido')}")
            return {
                'ok': False,
                'status': 'error',
                'sequence_id': str(sequence_id),
                'message': f"Error enviando comando MOVE TO HOME: {move_result.get('message', 'Error desconocido')}",
                'robot_status': 'error',
                'error': move_result.get('error', 'Error enviando comando')
            }
        
        print(f"[cmd_move_to_home] ✅ Comando MOVE TO HOME enviado correctamente")
        
        # 3. Esperar respuesta específica del robot
        print(f"[cmd_move_to_home] 📋 Paso 3: Esperando respuesta del robot...")
        response_result = waitComauResponse(sequence_id, "$HOME done!", 10000)  # 10 segundos timeout
        
        if response_result['success']:
            print(f"[cmd_move_to_home] 🎉 ¡Robot movido a HOME exitosamente!")
            return {
                'ok': True,
                'status': 'success',
                'sequence_id': str(sequence_id),
                'message': 'Robot movido a HOME exitosamente',
                'robot_status': 'active',
                'response_text': response_result['response_text'],
                'full_response': response_result['full_response']
            }
        else:
            # Analizar el tipo de error
            if response_result['id_found']:
                if response_result['error_type'] == 'text_mismatch':
                    print(f"[cmd_move_to_home] ⚠️ Robot respondió pero con texto incorrecto")
                    return {
                        'ok': True,
                        'status': 'warning',
                        'sequence_id': str(sequence_id),
                        'message': f"Robot respondió pero con texto incorrecto: '{response_result['response_text']}'",
                        'robot_status': 'active',
                        'response_text': response_result['response_text'],
                        'full_response': response_result['full_response'],
                        'error': response_result['error_message']
                    }
                else:
                    print(f"[cmd_move_to_home] ❌ Error en respuesta del robot: {response_result['error_message']}")
                    return {
                        'ok': True,
                        'status': 'error',
                        'sequence_id': str(sequence_id),
                        'message': f"Error en respuesta del robot: {response_result['error_message']}",
                        'robot_status': 'error',
                        'error': response_result['error_message']
                    }
            else:
                print(f"[cmd_move_to_home] ❌ No se recibió respuesta del robot: {response_result['error_message']}")
                return {
                    'ok': True,
                    'status': 'error',
                    'sequence_id': str(sequence_id),
                    'message': f"No se recibió respuesta del robot: {response_result['error_message']}",
                    'robot_status': 'no_response',
                    'error': response_result['error_message']
                }
            
    except Exception as e:
        print(f"[cmd_move_to_home] ❌ Error interno en MOVE TO HOME: {str(e)}")
        return {
            'ok': False,
            'error': str(e),
            'status': 'error',
            'message': f'Error interno: {str(e)}',
            'robot_status': 'error'
        }
