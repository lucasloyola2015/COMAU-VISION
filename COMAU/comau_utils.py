"""
COMAU Utilities Module
=====================

Este módulo contiene funciones utilitarias para comandos del robot COMAU,
incluyendo funciones comunes que se reutilizan en múltiples comandos.

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

# Agregar el directorio padre al path para importar constants
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from constants import get_constant
from variable_registry import get_variable_registry, COMAUVariableType

DELAY_TECLAS = 10
DELAY_ULTIMO_ENTER = 500

# Control de verbosidad (silenciado por defecto)
VERBOSE = False

def set_comau_utils_verbose(enabled: bool) -> None:
    global VERBOSE
    VERBOSE = enabled

def _vprint(message: str) -> None:
    if VERBOSE:
        print(message)

def addWordToSequence(indice: int, texto: str) -> list:
    """
    Crea un elemento de secuencia para establecer $WORD[indice] := texto + ENTER + ENTER + ENTER.
    
    Args:
        indice: Índice de la variable WORD (ej: ID_COM, MOVE_TO_HOME)
        texto: Valor a asignar a la variable
        
    Returns:
        Lista con los elementos de secuencia para agregar a una secuencia completa
    """
    return [
        {
            "action": "type_text",
            "text": "$WORD[",
            "description": "Escribir '$WORD['",
            "delay_after": DELAY_TECLAS
        },
        {
            "action": "type_text",
            "text": str(indice),
            "description": f"Escribir '{indice}' (índice)",
            "delay_after": DELAY_TECLAS
        },
        {
            "action": "type_text",
            "text": "]:=",
            "description": "Escribir ']:='",
            "delay_after": DELAY_TECLAS
        },
        {
            "action": "type_text",
            "text": str(texto),
            "description": f"Escribir '{texto}' (valor)",
            "delay_after": DELAY_TECLAS
        },
        {
            "action": "press_key",
            "key": "ENTER",
            "description": "Primer ENTER",
            "delay_after": DELAY_TECLAS
        },
        {
            "action": "press_key",
            "key": "ENTER",
            "description": "Segundo ENTER",
            "delay_after": DELAY_TECLAS
        },
        {
            "action": "press_key",
            "key": "ENTER",
            "description": "Tercer ENTER",
            "delay_after": DELAY_ULTIMO_ENTER
        }
    ]


def sendSequenceToBroker(sequence: list, command_name: str = "COMMAND") -> Dict[str, Any]:
    """
    Envía una secuencia de comandos al broker MQTT usando ExecuteKeySequenceWithInstrCheck.
    
    Args:
        sequence: Lista de acciones de la secuencia
        command_name: Nombre del comando para logging (opcional)
        
    Returns:
        Dict con el resultado de la ejecución
    """
    try:
        # Obtener el manager MQTT
        mqtt_manager = get_mqtt_manager()
        
        _vprint(f"[comau_utils] 🔍 Estado MQTT: connected={mqtt_manager.connected}, state={mqtt_manager.state}")
        
        # Verificar si MQTT está conectado
        if not mqtt_manager.connected:
            _vprint(f"[comau_utils] ❌ MQTT no conectado - estado: {mqtt_manager.state}")
            return {
                'ok': False,
                'error': 'MQTT no conectado',
                'status': 'error',
                'message': 'No se puede comunicar con el robot - MQTT desconectado',
                'robot_status': 'disconnected'
            }
        
        # Generar ID único de request para MQTT
        request_id = f"{command_name.lower()}_{int(time.time())}_{str(uuid.uuid4())[:8]}"
        
        # Crear comando ExecuteKeySequenceWithInstrCheck
        command = {
            "command": "ExecuteKeySequenceWithInstrCheck",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "args": {
                "sequence": sequence,
                "instr_check": {
                    "enabled": True,
                    "block_id": 1,
                    "search_string": "Instr:",
                    "timeout_ms": 5000
                },
                "options": {
                    "verify_focus": True,
                    "restore_focus": False,
                    "abort_on_error": True,
                    "dry_run": False
                }
            },
            "request_id": request_id
        }
        
        _vprint(f"[comau_utils] 🤖 Enviando comando {command_name} (ID: {request_id})")
        _vprint(f"[comau_utils] 📤 Comando: {command}")
        
        # Enviar comando y esperar respuesta
        response = mqtt_manager.send_command_and_wait(command, timeout=30)
        
        if response and response.get('status') == 'success':
            _vprint(f"[comau_utils] 📥 Respuesta success recibida")
        else:
            _vprint(f"[comau_utils] 📥 Respuesta recibida: {response}")
        
        if response:
            # Procesar respuesta del robot
            if response.get('status') == 'success':
                if response.get('instr_check_passed', False):
                    # Robot ejecutó el comando correctamente
                    return {
                        'ok': True,
                        'status': 'success',
                        'message': f'Comando {command_name} ejecutado correctamente',
                        'robot_status': 'active',
                        'instr_check_passed': True,
                        'execution_time': response.get('execution_time'),
                        'block_address': response.get('block_address'),
                        'block_size': response.get('block_size')
                    }
                else:
                    # Robot no está activo (no encontró "Instr:")
                    return {
                        'ok': True,
                        'status': 'warning',
                        'message': 'Robot no está activo - Instr: no detectado',
                        'robot_status': 'inactive',
                        'instr_check_passed': False,
                        'context': response.get('message', 'Bloque Drive no encontrado')
                    }
            else:
                # Error en la ejecución del comando
                return {
                    'ok': True,
                    'status': 'error',
                    'message': f"Error ejecutando {command_name}: {response.get('error_message', 'Error desconocido')}",
                    'robot_status': 'error',
                    'error_code': response.get('error_code', 'UNKNOWN_ERROR'),
                    'error_message': response.get('error_message', 'Error desconocido')
                }
        else:
            # No hay respuesta del robot
            return {
                'ok': True,
                'status': 'error',
                'message': 'Robot COMAU no responde - timeout o error de comunicación',
                'robot_status': 'no_response'
            }
            
    except Exception as e:
        _vprint(f"[comau_utils] ❌ Error interno en {command_name}: {str(e)}")
        return {
            'ok': False,
            'error': str(e),
            'status': 'error',
            'message': f'Error interno: {str(e)}',
            'robot_status': 'error'
        }


def set_ID_com(sequence_id: int) -> Dict[str, Any]:
    """
    Establece el ID de secuencia en $WORD[ID_COM] para correlacionar comandos con respuestas.
    
    Envía la secuencia: $WORD[ID_COM] := sequence_id + ENTER + ENTER
    
    Args:
        sequence_id: ID único de secuencia (ej: 2255)
        
    Returns:
        Dict con el resultado de la ejecución
    """
    try:
        # Obtener constante ID_COM dinámicamente
        id_com_value = get_constant('ID_COM', 1)
        
        # Crear secuencia usando la función encapsulada
        sequence = addWordToSequence(id_com_value, str(sequence_id))
        
        # Enviar secuencia al broker usando la función encapsulada
        result = sendSequenceToBroker(sequence, "SET_ID_COM")
        
        # Agregar información específica del sequence_id
        if result.get('ok', False):
            result['sequence_id'] = str(sequence_id)
            if result.get('status') == 'success':
                result['message'] = f'ID de secuencia {sequence_id} establecido correctamente'
        
        return result
        
    except Exception as e:
        print(f"[comau_utils] ❌ Error interno en SET ID_COM: {str(e)}")
        return {
            'ok': False,
            'error': str(e),
            'status': 'error',
            'message': f'Error interno: {str(e)}',
            'robot_status': 'error'
        }


def waitComauResponse(id_sequence: int, texto: str = None, timeout_ms: int = 5000) -> Dict[str, Any]:
    """
    Espera la respuesta del robot buscando el ID de secuencia en el bloque de memoria.
    
    Busca el patrón "[ id_sequence]:" y extrae el contenido hasta el primer "#".
    
    Args:
        id_sequence: ID de secuencia a buscar (ej: 2489)
        texto: Texto esperado exacto (ej: "$HOME done!") o None para leer cualquier respuesta
        timeout_ms: Timeout en milisegundos para la búsqueda
        
    Returns:
        Dict con el resultado:
        - success: bool - Si la operación fue exitosa
        - id_found: bool - Si se encontró el ID de secuencia
        - text_match: bool - Si el texto coincide (solo si texto no es None)
        - response_text: str - Texto extraído entre ":" y "#"
        - full_response: str - Respuesta completa encontrada
        - error_type: str - Tipo de error si aplica
        - error_message: str - Mensaje de error detallado
    """
    try:
        # Obtener el manager MQTT
        mqtt_manager = get_mqtt_manager()
        
        # Verificar si MQTT está conectado
        if not mqtt_manager or not mqtt_manager.connected:
            _vprint(f"[comau_utils] ❌ MQTT no conectado para waitComauResponse")
            return {
                'success': False,
                'id_found': False,
                'text_match': False,
                'response_text': '',
                'full_response': '',
                'error_type': 'mqtt_disconnected',
                'error_message': 'MQTT no conectado'
            }
        
        # Construir el string de búsqueda: "[ id_sequence]:"
        search_string = f"[ {id_sequence}]:"
        
        # Longitud de caracteres a leer después del string encontrado
        # Leemos suficiente para capturar el mensaje completo hasta el #
        length = 70  # Suficiente para la mayoría de respuestas
        
        # Generar ID único de request para MQTT
        request_id = f"wait_response_{int(time.time())}_{str(uuid.uuid4())[:8]}"
        
        # Crear comando FindStringLenInBlock
        command = {
            "command": "FindStringLenInBlock",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "args": {
                "block_id": 1,
                "search_string": search_string,
                "length": length,
                "timeout_ms": timeout_ms
            },
            "request_id": request_id
        }
        
        _vprint(f"[comau_utils] 🔍 Buscando respuesta para ID {id_sequence}: '{search_string}'...")
        _vprint(f"[comau_utils] 📤 Comando: {command}")
        
        # Enviar comando y esperar respuesta
        response = mqtt_manager.send_command_and_wait(command, timeout=(timeout_ms / 1000) + 5)
        
        if response and response.get('status') == 'success':
            _vprint(f"[comau_utils] 📥 Respuesta success recibida")
        else:
            _vprint(f"[comau_utils] 📥 Respuesta recibida: {response}")
        
        if response and response.get('status') == 'success':
            # Verificar si se encontraron ocurrencias
            occurrences = response.get('occurrences', [])
            
            if occurrences:
                # Procesar la primera ocurrencia encontrada
                occurrence = occurrences[0]
                full_context = occurrence.get('full_context', '')
                
                _vprint(f"[comau_utils] ✅ ID {id_sequence} encontrado")
                _vprint(f"[comau_utils] 📋 Contexto completo: '{full_context}'")
                
                # Extraer el texto entre ":" y "#"
                # Buscar el primer ":" después del ID
                colon_pos = full_context.find(':')
                if colon_pos != -1:
                    # Buscar el primer "#" después de ":"
                    hash_pos = full_context.find('#', colon_pos + 1)
                    if hash_pos != -1:
                        # Extraer texto entre ":" y "#"
                        response_text = full_context[colon_pos + 1:hash_pos].strip()
                        _vprint(f"[comau_utils] 📝 Texto extraído: '{response_text}'")
                        
                        # Si se especificó texto esperado, verificar coincidencia exacta
                        if texto is not None:
                            text_match = (response_text == texto)
                            _vprint(f"[comau_utils] 🔍 Comparando: '{response_text}' == '{texto}' -> {text_match}")
                            
                            return {
                                'success': text_match,
                                'id_found': True,
                                'text_match': text_match,
                                'response_text': response_text,
                                'full_response': full_context,
                                'error_type': 'text_mismatch' if not text_match else None,
                                'error_message': f"Texto esperado '{texto}' no coincide con '{response_text}'" if not text_match else None
                            }
                        else:
                            # Solo leer respuesta sin verificar texto
                            return {
                                'success': True,
                                'id_found': True,
                                'text_match': True,  # N/A cuando texto es None
                                'response_text': response_text,
                                'full_response': full_context,
                                'error_type': None,
                                'error_message': None
                            }
                    else:
                        # No se encontró "#" - respuesta incompleta
                        _vprint(f"[comau_utils] ⚠️ No se encontró '#' en la respuesta")
                        return {
                            'success': False,
                            'id_found': True,
                            'text_match': False,
                            'response_text': full_context[colon_pos + 1:].strip(),
                            'full_response': full_context,
                            'error_type': 'incomplete_response',
                            'error_message': "Respuesta incompleta - no se encontró '#'"
                        }
                else:
                    # No se encontró ":" - formato incorrecto
                    _vprint(f"[comau_utils] ⚠️ No se encontró ':' en la respuesta")
                    return {
                        'success': False,
                        'id_found': True,
                        'text_match': False,
                        'response_text': '',
                        'full_response': full_context,
                        'error_type': 'invalid_format',
                        'error_message': "Formato de respuesta inválido - no se encontró ':'"
                    }
            else:
                # No se encontró el ID de secuencia
                _vprint(f"[comau_utils] ❌ ID de secuencia {id_sequence} no encontrado")
                return {
                    'success': False,
                    'id_found': False,
                    'text_match': False,
                    'response_text': '',
                    'full_response': '',
                    'error_type': 'id_not_found',
                    'error_message': f"ID de secuencia {id_sequence} no encontrado"
                }
        else:
            # Error en la búsqueda
            error_msg = response.get('error_message', 'Error desconocido') if response else 'Sin respuesta'
            _vprint(f"[comau_utils] ❌ Error buscando respuesta: {error_msg}")
            return {
                'success': False,
                'id_found': False,
                'text_match': False,
                'response_text': '',
                'full_response': '',
                'error_type': 'server_error',
                'error_message': f"Error del servidor: {error_msg}"
            }
            
    except Exception as e:
        _vprint(f"[comau_utils] ❌ Error interno en waitComauResponse: {str(e)}")
        return {
            'success': False,
            'id_found': False,
            'text_match': False,
            'response_text': '',
            'full_response': '',
            'error_type': 'internal_error',
            'error_message': f"Error interno: {str(e)}"
        }


# ============================================================
# FUNCIONES DE GESTIÓN DE VARIABLES CON METADATOS
# ============================================================

def get_variable_info(index: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene información completa de una variable por su índice.
    
    Args:
        index: Índice de la variable
        
    Returns:
        Dict con información de la variable o None si no existe
    """
    try:
        registry = get_variable_registry()
        variable = registry.get_variable(index)
        
        if variable:
            return {
                'index': variable.index,
                'name': variable.name,
                'description': variable.description,
                'type': variable.type.value,
                'valid_values': variable.valid_values,
                'command_string': f"$WORD[{variable.index}]"
            }
        return None
        
    except Exception as e:
        _vprint(f"[comau_utils] ❌ Error obteniendo info de variable {index}: {str(e)}")
        return None


def get_variable_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene información completa de una variable por su nombre.
    
    Args:
        name: Nombre de la variable (ej: "ID_COM", "MOVE_TO_HOME")
        
    Returns:
        Dict con información de la variable o None si no existe
    """
    try:
        registry = get_variable_registry()
        variable = registry.get_variable_by_name(name)
        
        if variable:
            return {
                'index': variable.index,
                'name': variable.name,
                'description': variable.description,
                'type': variable.type.value,
                'valid_values': variable.valid_values,
                'command_string': f"$WORD[{variable.index}]"
            }
        return None
        
    except Exception as e:
        _vprint(f"[comau_utils] ❌ Error obteniendo variable '{name}': {str(e)}")
        return None


def validate_variable_value(index: int, value: Any) -> bool:
    """
    Valida si un valor es válido para una variable específica.
    
    Args:
        index: Índice de la variable
        value: Valor a validar
        
    Returns:
        True si el valor es válido, False en caso contrario
    """
    try:
        registry = get_variable_registry()
        return registry.validate_variable_value(index, value)
        
    except Exception as e:
        _vprint(f"[comau_utils] ❌ Error validando valor {value} para variable {index}: {str(e)}")
        return False


def get_all_variables() -> Dict[int, Dict[str, Any]]:
    """
    Obtiene información de todas las variables del sistema.
    
    Returns:
        Dict con {índice: info_variable} para todas las variables
    """
    try:
        registry = get_variable_registry()
        variables = registry.get_all_variables()
        
        result = {}
        for index, variable in variables.items():
            result[index] = {
                'index': variable.index,
                'name': variable.name,
                'description': variable.description,
                'type': variable.type.value,
                'valid_values': variable.valid_values,
                'command_string': f"$WORD[{variable.index}]"
            }
        
        return result
        
    except Exception as e:
        _vprint(f"[comau_utils] ❌ Error obteniendo todas las variables: {str(e)}")
        return {}


def get_variables_by_type(var_type: str) -> Dict[int, Dict[str, Any]]:
    """
    Obtiene variables filtradas por tipo.
    
    Args:
        var_type: Tipo de variable ("system", "control", "command", "state", "parameter", "io")
        
    Returns:
        Dict con variables del tipo especificado
    """
    try:
        registry = get_variable_registry()
        
        # Convertir string a enum
        type_enum = COMAUVariableType(var_type)
        variables = registry.get_variables_by_type(type_enum)
        
        result = {}
        for index, variable in variables.items():
            result[index] = {
                'index': variable.index,
                'name': variable.name,
                'description': variable.description,
                'type': variable.type.value,
                'valid_values': variable.valid_values,
                'command_string': f"$WORD[{variable.index}]"
            }
        
        return result
        
    except Exception as e:
        _vprint(f"[comau_utils] ❌ Error obteniendo variables por tipo '{var_type}': {str(e)}")
        return {}


def create_word_command_with_validation(index: int, value: Any) -> str:
    """
    Crea un comando $WORD[i] con validación de valor.
    
    Args:
        index: Índice de la variable
        value: Valor a establecer
        
    Returns:
        String del comando $WORD[i]:=value
        
    Raises:
        ValueError: Si el valor no es válido para la variable
    """
    try:
        registry = get_variable_registry()
        return registry.get_command_string(index, value)
        
    except Exception as e:
        _vprint(f"[comau_utils] ❌ Error creando comando $WORD[{index}]:={value}: {str(e)}")
        raise