"""
COMAU Robot Management Module
=============================

Este módulo gestiona todas las rutinas relacionadas con el robot COMAU,
incluyendo comandos MQTT, secuencias de teclas y operaciones específicas.

Autor: Illinois Automation
Fecha: 2024
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


class COMAUCommandType(Enum):
    """Tipos de comandos COMAU disponibles"""
    VERIFY_INSTR = "VerifyInstr"
    INIT_WINC5G = "InitWinC5G"
    EXECUTE_KEY_SEQUENCE = "ExecuteKeySequence"
    EXECUTE_KEY_SEQUENCE_WITH_INSTR_CHECK = "ExecuteKeySequenceWithInstrCheck"
    RESET_ROBOT = "ResetRobot"
    MOVE_TO_HOME = "MoveToHome"


class COMAUActionType(Enum):
    """Tipos de acciones disponibles en secuencias de teclas"""
    TYPE_TEXT = "type_text"
    PRESS_KEY = "press_key"
    WAIT = "wait"
    MOUSE_CLICK = "mouse_click"


class COMAUKey(Enum):
    """Teclas especiales disponibles"""
    ENTER = "ENTER"
    ESC = "ESC"
    TAB = "TAB"
    SPACE = "SPACE"
    BACKSPACE = "BACKSPACE"
    DELETE = "DELETE"
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"
    F5 = "F5"
    F6 = "F6"
    F7 = "F7"
    F8 = "F8"
    F9 = "F9"
    F10 = "F10"
    F11 = "F11"
    F12 = "F12"


class COMAUManager:
    """
    Gestor principal para todas las operaciones del robot COMAU.
    
    Esta clase maneja:
    - Comandos MQTT al robot
    - Secuencias de teclas predefinidas
    - Rutinas de operación específicas
    - Validación de respuestas
    """
    
    def __init__(self, mqtt_manager=None):
        """
        Inicializa el gestor COMAU.
        
        Args:
            mqtt_manager: Instancia del gestor MQTT para enviar comandos
        """
        self.mqtt_manager = mqtt_manager
        self.logger = logging.getLogger(__name__)
        
        # Configuración por defecto
        self.default_timeout = 30
        self.default_delay = 200
        self.default_instr_timeout = 5000
        
        # Rutinas predefinidas
        self.routines = {}
        self._load_predefined_routines()
        
        self.logger.info("COMAUManager inicializado")
    
    def _load_predefined_routines(self):
        """Carga rutinas predefinidas del robot"""
        self.routines = {
            "reset_robot": self._get_reset_robot_sequence(),
            "move_to_home": self._get_move_to_home_sequence(),
            "clear_errors": self._get_clear_errors_sequence(),
            "start_program": self._get_start_program_sequence(),
            "stop_program": self._get_stop_program_sequence(),
            "set_fmi_zero": self._get_set_fmi_zero_sequence(),
        }
    
    def _get_reset_robot_sequence(self) -> List[Dict]:
        """Secuencia para resetear el robot"""
        return [
            {
                "action": "type_text",
                "text": "$FMI[1]:=0",
                "description": "Escribir '$FMI[1]:=0'",
                "delay_after": 200
            },
            {
                "action": "press_key",
                "key": "ENTER",
                "description": "Primer ENTER",
                "delay_after": 200
            },
            {
                "action": "press_key",
                "key": "ENTER",
                "description": "Segundo ENTER",
                "delay_after": 200
            },
            {
                "action": "press_key",
                "key": "ENTER",
                "description": "Tercer ENTER",
                "delay_after": 500
            }
        ]
    
    def _get_move_to_home_sequence(self) -> List[Dict]:
        """Secuencia para mover el robot a posición home"""
        return [
            {
                "action": "type_text",
                "text": "HOME",
                "description": "Escribir 'HOME'",
                "delay_after": 200
            },
            {
                "action": "press_key",
                "key": "ENTER",
                "description": "ENTER para ejecutar HOME",
                "delay_after": 1000
            }
        ]
    
    def _get_clear_errors_sequence(self) -> List[Dict]:
        """Secuencia para limpiar errores del robot"""
        return [
            {
                "action": "press_key",
                "key": "ESC",
                "description": "ESC para limpiar errores",
                "delay_after": 200
            },
            {
                "action": "press_key",
                "key": "ENTER",
                "description": "ENTER para confirmar",
                "delay_after": 500
            }
        ]
    
    def _get_start_program_sequence(self) -> List[Dict]:
        """Secuencia para iniciar programa"""
        return [
            {
                "action": "press_key",
                "key": "F1",
                "description": "F1 para iniciar programa",
                "delay_after": 1000
            }
        ]
    
    def _get_stop_program_sequence(self) -> List[Dict]:
        """Secuencia para detener programa"""
        return [
            {
                "action": "press_key",
                "key": "ESC",
                "description": "ESC para detener programa",
                "delay_after": 500
            }
        ]
    
    def _get_set_fmi_zero_sequence(self) -> List[Dict]:
        """Secuencia para establecer FMI en cero"""
        return [
            {
                "action": "type_text",
                "text": "$FMI[1]:=0",
                "description": "Escribir '$FMI[1]:=0'",
                "delay_after": 200
            },
            {
                "action": "press_key",
                "key": "ENTER",
                "description": "ENTER para confirmar",
                "delay_after": 200
            }
        ]
    
    def verify_instr(self, timeout: int = 5) -> Dict[str, Any]:
        """
        Verifica si el string "Instr:" existe en el bloque Drive.
        
        Args:
            timeout: Tiempo máximo de espera en segundos
            
        Returns:
            Diccionario con el resultado de la verificación
        """
        if not self.mqtt_manager or not self.mqtt_manager.connected:
            return {
                'success': False,
                'error': 'No hay conexión MQTT activa',
                'found': False
            }
        
        command = {
            'command': 'VerifyInstr',
            'timestamp': datetime.now().isoformat(),
            'args': {},
            'request_id': f'verify_{int(time.time())}'
        }
        
        self.logger.info("Enviando comando VerifyInstr")
        response = self.mqtt_manager.send_command_and_wait(command, timeout)
        
        if response:
            success = response.get('status') == 'success'
            found = response.get('found', False)
            
            return {
                'success': success,
                'found': found,
                'response': response,
                'message': response.get('message', '')
            }
        else:
            return {
                'success': False,
                'error': 'Timeout esperando respuesta',
                'found': False
            }
    
    def execute_key_sequence_with_instr_check(
        self, 
        sequence: List[Dict], 
        timeout: int = 30,
        instr_timeout: int = 5000
    ) -> Dict[str, Any]:
        """
        Ejecuta una secuencia de teclas solo si "Instr:" existe en memoria.
        
        Args:
            sequence: Lista de acciones a ejecutar
            timeout: Tiempo máximo de espera para la secuencia
            instr_timeout: Tiempo máximo para verificar Instr
            
        Returns:
            Diccionario con el resultado de la ejecución
        """
        if not self.mqtt_manager or not self.mqtt_manager.connected:
            return {
                'success': False,
                'error': 'No hay conexión MQTT activa'
            }
        
        command = {
            'command': 'ExecuteKeySequenceWithInstrCheck',
            'timestamp': datetime.now().isoformat(),
            'args': {
                'sequence': sequence,
                'instr_check': {
                    'enabled': True,
                    'block_id': 1,
                    'search_string': 'Instr:',
                    'timeout_ms': instr_timeout
                },
                'options': {
                    'verify_focus': True,
                    'restore_focus': False,
                    'abort_on_error': True,
                    'dry_run': False
                }
            },
            'request_id': f'seq_instr_{int(time.time())}'
        }
        
        self.logger.info("Enviando comando ExecuteKeySequenceWithInstrCheck")
        response = self.mqtt_manager.send_command_and_wait(command, timeout)
        
        if response:
            success = response.get('status') == 'success'
            instr_check_passed = response.get('instr_check_passed', False)
            
            return {
                'success': success,
                'instr_check_passed': instr_check_passed,
                'response': response,
                'message': response.get('message', ''),
                'error_code': response.get('error_code'),
                'error_message': response.get('error_message')
            }
        else:
            return {
                'success': False,
                'error': 'Timeout esperando respuesta',
                'instr_check_passed': False
            }
    
    def execute_routine(self, routine_name: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Ejecuta una rutina predefinida.
        
        Args:
            routine_name: Nombre de la rutina a ejecutar
            timeout: Tiempo máximo de espera
            
        Returns:
            Diccionario con el resultado de la ejecución
        """
        if routine_name not in self.routines:
            return {
                'success': False,
                'error': f'Rutina "{routine_name}" no encontrada',
                'available_routines': list(self.routines.keys())
            }
        
        sequence = self.routines[routine_name]
        self.logger.info(f"Ejecutando rutina: {routine_name}")
        
        return self.execute_key_sequence_with_instr_check(sequence, timeout)
    
    def reset_robot(self, timeout: int = 30) -> Dict[str, Any]:
        """Resetea el robot usando la rutina predefinida"""
        return self.execute_routine("reset_robot", timeout)
    
    def move_to_home(self, timeout: int = 30) -> Dict[str, Any]:
        """Mueve el robot a posición home"""
        return self.execute_routine("move_to_home", timeout)
    
    def clear_errors(self, timeout: int = 30) -> Dict[str, Any]:
        """Limpia errores del robot"""
        return self.execute_routine("clear_errors", timeout)
    
    def start_program(self, timeout: int = 30) -> Dict[str, Any]:
        """Inicia un programa en el robot"""
        return self.execute_routine("start_program", timeout)
    
    def stop_program(self, timeout: int = 30) -> Dict[str, Any]:
        """Detiene el programa actual del robot"""
        return self.execute_routine("stop_program", timeout)
    
    def set_fmi_zero(self, timeout: int = 30) -> Dict[str, Any]:
        """Establece FMI en cero"""
        return self.execute_routine("set_fmi_zero", timeout)
    
    def get_available_routines(self) -> List[str]:
        """Retorna lista de rutinas disponibles"""
        return list(self.routines.keys())
    
    def add_custom_routine(self, name: str, sequence: List[Dict]):
        """
        Agrega una rutina personalizada.
        
        Args:
            name: Nombre de la rutina
            sequence: Lista de acciones de la rutina
        """
        self.routines[name] = sequence
        self.logger.info(f"Rutina personalizada agregada: {name}")
    
    def validate_sequence(self, sequence: List[Dict]) -> Tuple[bool, str]:
        """
        Valida que una secuencia de teclas sea correcta.
        
        Args:
            sequence: Lista de acciones a validar
            
        Returns:
            Tupla con (es_valida, mensaje_error)
        """
        if not isinstance(sequence, list):
            return False, "La secuencia debe ser una lista"
        
        for i, action in enumerate(sequence):
            if not isinstance(action, dict):
                return False, f"Acción {i} debe ser un diccionario"
            
            if 'action' not in action:
                return False, f"Acción {i} debe tener campo 'action'"
            
            action_type = action['action']
            
            if action_type == 'type_text':
                if 'text' not in action:
                    return False, f"Acción {i} type_text debe tener campo 'text'"
            elif action_type == 'press_key':
                if 'key' not in action:
                    return False, f"Acción {i} press_key debe tener campo 'key'"
            elif action_type == 'wait':
                if 'duration' not in action:
                    return False, f"Acción {i} wait debe tener campo 'duration'"
            else:
                return False, f"Tipo de acción '{action_type}' no válido"
        
        return True, "Secuencia válida"


# Instancia global del gestor COMAU
_comau_manager_instance: Optional[COMAUManager] = None


def get_comau_manager(mqtt_manager=None) -> COMAUManager:
    """
    Obtiene la instancia global del gestor COMAU (patrón singleton).
    
    Args:
        mqtt_manager: Instancia del gestor MQTT (opcional)
        
    Returns:
        Instancia del gestor COMAU
    """
    global _comau_manager_instance
    
    if _comau_manager_instance is None:
        _comau_manager_instance = COMAUManager(mqtt_manager)
    elif mqtt_manager is not None and _comau_manager_instance.mqtt_manager != mqtt_manager:
        _comau_manager_instance.mqtt_manager = mqtt_manager
    
    return _comau_manager_instance


if __name__ == "__main__":
    # Ejemplo de uso
    logging.basicConfig(level=logging.INFO)
    
    manager = get_comau_manager()
    
    print("Rutinas disponibles:")
    for routine in manager.get_available_routines():
        print(f"  - {routine}")
    
    print("\nEjemplo de secuencia personalizada:")
    custom_sequence = [
        {
            "action": "type_text",
            "text": "TEST",
            "description": "Escribir TEST",
            "delay_after": 200
        },
        {
            "action": "press_key",
            "key": "ENTER",
            "description": "ENTER",
            "delay_after": 500
        }
    ]
    
    is_valid, message = manager.validate_sequence(custom_sequence)
    print(f"Secuencia válida: {is_valid} - {message}")
