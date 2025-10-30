"""
COMAU Variable Registry
======================

Este módulo define el registro de variables del sistema COMAU con metadatos
completos, incluyendo tipos, descripciones y validaciones.

Autor: Illinois Automation
Fecha: 2024
"""

from typing import Dict, Optional, List
from enum import Enum
import sys
import os

# Importar constants del mismo directorio
try:
    from constants import get_constant
except ImportError:
    # Si no se puede importar directamente, agregar el directorio al path
    import os
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from constants import get_constant


class COMAUVariableType(Enum):
    """Tipos de variables del sistema COMAU"""
    SYSTEM = "system"           # Variables del sistema base
    CONTROL = "control"         # Variables de control de comunicación
    COMMAND = "command"         # Variables de comandos
    STATE = "state"            # Variables de estado
    PARAMETER = "parameter"     # Variables de parámetros/coordenadas
    IO = "io"                  # Variables de entrada/salida


class COMAUVariableIndex:
    """Representa un índice de variable del sistema COMAU con metadatos completos"""
    
    def __init__(self, index: int, name: str, description: str, 
                 var_type: COMAUVariableType, valid_values: Optional[List] = None):
        self.index = index
        self.name = name
        self.description = description
        self.type = var_type
        self.valid_values = valid_values or []
    
    def __str__(self):
        return f"$WORD[{self.index}]"
    
    def get_command_string(self, value) -> str:
        """Retorna el comando string para establecer el valor"""
        return f"$WORD[{self.index}]:={value}"
    
    def validate_value(self, value) -> bool:
        """Valida si un valor es válido para esta variable"""
        if not self.valid_values:
            return True
        return value in self.valid_values


class COMAUVariableRegistry:
    """Registro de todas las variables del sistema COMAU con metadatos"""
    
    def __init__(self):
        self.variables: Dict[int, COMAUVariableIndex] = {}
        self.variable_names: Dict[str, int] = {}
        self._register_system_variables()
    
    def _register_system_variables(self):
        """Registra todas las variables del sistema usando constantes dinámicas"""
        
        # Variables del sistema (0X) - Control y Comandos
        self.register_variable(COMAUVariableIndex(
            index=get_constant('ID_COM', 1),
            name="ID_COM",
            description="Variable que se usa a la hora de responder con el Index",
            var_type=COMAUVariableType.CONTROL
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=get_constant('SAY_HELLO', 2),
            name="SAY_HELLO",
            description="Comando para decir Hola",
            var_type=COMAUVariableType.COMMAND,
            valid_values=[1]  # Solo acepta valor 1 para activar
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=get_constant('MAQUINA_ESTADOS', 3),
            name="MAQUINA_ESTADOS",
            description="Índice de la máquina de estados",
            var_type=COMAUVariableType.STATE,
            valid_values=list(range(0, 100))  # Estados válidos 0-99
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=get_constant('MOVE_TO_HOME', 4),
            name="MOVE_TO_HOME",
            description="Comando para enviar el brazo al HOME",
            var_type=COMAUVariableType.COMMAND,
            valid_values=[1]  # Solo acepta valor 1 para activar
        ))
        
        # Argumentos offsets (2X) - Coordenadas y Parámetros
        self.register_variable(COMAUVariableIndex(
            index=get_constant('dX', 22),
            name="dX",
            description="Argumento X - Coordenada X",
            var_type=COMAUVariableType.PARAMETER
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=get_constant('dY', 23),
            name="dY",
            description="Argumento Y - Coordenada Y",
            var_type=COMAUVariableType.PARAMETER
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=get_constant('dZ', 24),
            name="dZ",
            description="Argumento Z - Coordenada Z",
            var_type=COMAUVariableType.PARAMETER
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=get_constant('dA', 25),
            name="dA",
            description="Argumento A - Ángulo A",
            var_type=COMAUVariableType.PARAMETER
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=get_constant('dE', 26),
            name="dE",
            description="Argumento E - Ángulo E",
            var_type=COMAUVariableType.PARAMETER
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=get_constant('dR', 27),
            name="dR",
            description="Argumento R - Ángulo R",
            var_type=COMAUVariableType.PARAMETER
        ))
        
        # Variables I/O
        self.register_variable(COMAUVariableIndex(
            index=get_constant('EV_PINZA', 7),
            name="EV_PINZA",
            description="Puerto de salida para pinza",
            var_type=COMAUVariableType.IO,
            valid_values=[0, 1]  # Solo acepta 0 o 1
        ))
    
    def register_variable(self, variable: COMAUVariableIndex):
        """Registra un nuevo índice de variable"""
        self.variables[variable.index] = variable
        self.variable_names[variable.name] = variable.index
    
    def get_variable(self, index: int) -> Optional[COMAUVariableIndex]:
        """Obtiene una variable por su índice"""
        return self.variables.get(index)
    
    def get_variable_by_name(self, name: str) -> Optional[COMAUVariableIndex]:
        """Obtiene una variable por su nombre"""
        index = self.variable_names.get(name)
        if index:
            return self.variables.get(index)
        return None
    
    def get_all_variables(self) -> Dict[int, COMAUVariableIndex]:
        """Retorna todas las variables registradas"""
        return self.variables.copy()
    
    def get_variables_by_type(self, var_type: COMAUVariableType) -> Dict[int, COMAUVariableIndex]:
        """Retorna variables filtradas por tipo"""
        return {idx: var for idx, var in self.variables.items() if var.type == var_type}
    
    def validate_variable_value(self, index: int, value) -> bool:
        """Valida si un valor es válido para una variable específica"""
        variable = self.get_variable(index)
        if not variable:
            return False
        return variable.validate_value(value)
    
    def get_command_string(self, index: int, value) -> str:
        """Genera el comando string para una variable y valor"""
        variable = self.get_variable(index)
        if not variable:
            raise ValueError(f"Variable con índice {index} no encontrada")
        
        if not variable.validate_value(value):
            raise ValueError(f"Valor {value} no válido para variable {variable.name}")
        
        return variable.get_command_string(value)


# Instancia global del registro
_variable_registry = None

def get_variable_registry() -> COMAUVariableRegistry:
    """Obtiene la instancia global del registro de variables"""
    global _variable_registry
    if _variable_registry is None:
        _variable_registry = COMAUVariableRegistry()
    return _variable_registry
