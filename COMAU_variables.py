"""
COMAU Variables Index Mapping
============================

Este módulo define el mapeo de índices del sistema COMAU.
Las variables $WORD[i] son solo para escribir comandos al robot.

Autor: Illinois Automation
Fecha: 2024
"""

from typing import Dict, Any, Optional
from enum import Enum


class COMAUVariableType(Enum):
    """Tipos de variables del sistema COMAU"""
    SYSTEM = "system"
    CONTROL = "control"
    PARAMETER = "parameter"
    STATE = "state"
    COMMAND = "command"
    EXECUTION = "execution"


class COMAUVariableIndex:
    """Representa un índice de variable del sistema COMAU"""
    
    def __init__(self, index: int, name: str, description: str, 
                 var_type: COMAUVariableType, valid_values: Optional[list] = None):
        self.index = index
        self.name = name
        self.description = description
        self.type = var_type
        self.valid_values = valid_values or []
    
    def __str__(self):
        return f"$WORD[{self.index}]"
    
    def get_command_string(self, value: Any) -> str:
        """Retorna el comando string para establecer el valor"""
        return f"$WORD[{self.index}]:={value}"
    
    def validate_value(self, value: Any) -> bool:
        """Valida si un valor es válido para esta variable"""
        if not self.valid_values:
            return True
        return value in self.valid_values


class COMAUVariableRegistry:
    """Registro de todos los índices de variables del sistema COMAU"""
    
    def __init__(self):
        self.variables: Dict[int, COMAUVariableIndex] = {}
        self.variable_names: Dict[str, int] = {}
        self._register_system_variables()
    
    def _register_system_variables(self):
        """Registra los índices de variables del sistema"""
        
        # Variables del sistema (0X)
        self.register_variable(COMAUVariableIndex(
            index=1,
            name="ID_COM",
            description="Variable que se usa a la hora de responder con el Index",
            var_type=COMAUVariableType.CONTROL
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=2,
            name="SAY_HELLO",
            description="Comando para decir Hola",
            var_type=COMAUVariableType.COMMAND
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=3,
            name="MAQUINA_ESTADOS",
            description="Índice de la máquina de estados",
            var_type=COMAUVariableType.STATE
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=4,
            name="MOVE_TO_HOME",
            description="Comando para enviar el brazo al HOME",
            var_type=COMAUVariableType.COMMAND
        ))
        
        # Argumentos offsets (2X)
        self.register_variable(COMAUVariableIndex(
            index=22,
            name="dX",
            description="Argumento X - Coordenada X",
            var_type=COMAUVariableType.PARAMETER
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=23,
            name="dY",
            description="Argumento Y - Coordenada Y",
            var_type=COMAUVariableType.PARAMETER
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=24,
            name="dZ",
            description="Argumento Z - Coordenada Z",
            var_type=COMAUVariableType.PARAMETER
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=25,
            name="dA",
            description="Argumento A - Ángulo A",
            var_type=COMAUVariableType.PARAMETER
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=26,
            name="dE",
            description="Argumento E - Ángulo E",
            var_type=COMAUVariableType.PARAMETER
        ))
        
        self.register_variable(COMAUVariableIndex(
            index=27,
            name="dR",
            description="Argumento R - Ángulo R",
            var_type=COMAUVariableType.PARAMETER
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
    
    def get_command_string(self, index: int, value: Any) -> str:
        """Retorna el comando string para establecer el valor de una variable"""
        return f"$WORD[{index}]:={value}"
    
    def get_all_variables(self) -> Dict[int, COMAUVariableIndex]:
        """Retorna todas las variables registradas"""
        return self.variables.copy()
    
    def get_variables_by_type(self, var_type: COMAUVariableType) -> Dict[int, COMAUVariableIndex]:
        """Retorna variables filtradas por tipo"""
        return {idx: var for idx, var in self.variables.items() if var.type == var_type}
    
    def validate_variable_value(self, index: int, value: Any) -> bool:
        """Valida si un valor es válido para una variable específica"""
        variable = self.get_variable(index)
        if not variable:
            return False
        return variable.validate_value(value)


class COMAUVariableCommands:
    """Generador de comandos $WORD[i] para el robot"""
    
    def __init__(self, registry: COMAUVariableRegistry):
        self.registry = registry
    
    def create_word_command(self, index: int, value: Any) -> str:
        """
        Crea un comando $WORD[i] para establecer el valor de una variable.
        
        Args:
            index: Índice de la variable
            value: Valor a establecer
            
        Returns:
            String del comando $WORD[i]:=value
        """
        if not self.registry.validate_variable_value(index, value):
            raise ValueError(f"Valor {value} no válido para variable $WORD[{index}]")
        
        return f"$WORD[{index}]:={value}"
    
    def create_set_variable_sequence(self, index: int, value: Any) -> list:
        """
        Crea una secuencia de comandos para establecer el valor de una variable.
        Secuencia: escribir "$WORD[i]:=valor" + 3 ENTER
        
        Args:
            index: Índice de la variable
            value: Valor a establecer
            
        Returns:
            Lista con la secuencia de comandos
        """
        variable = self.registry.get_variable(index)
        variable_name = variable.name if variable else f"VAR_{index}"
        
        return [
            {
                "action": "type_text",
                "text": self.create_word_command(index, value),
                "description": f"Escribir {variable_name} = {value}",
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
    
    def create_execute_command_sequence(self, command_id: int, parameters: dict = None) -> list:
        """
        Crea una secuencia de comandos para ejecutar una acción.
        
        Args:
            command_id: ID del comando a ejecutar
            parameters: Diccionario con parámetros {dX: valor, dY: valor, ...}
            
        Returns:
            Lista de comandos para ejecutar
        """
        sequence = []
        
        # Establecer parámetros si se proporcionan
        if parameters:
            # Mapeo de parámetros a índices
            param_mapping = {
                'dX': 2, 'dY': 3, 'dZ': 4, 
                'dA': 5, 'dE': 6, 'dR': 7
            }
            
            for param_name, value in parameters.items():
                if param_name in param_mapping:
                    index = param_mapping[param_name]
                    sequence.extend(self.create_set_variable_sequence(index, value))
        
        # Establecer ID del comando
        sequence.extend(self.create_set_variable_sequence(8, command_id))
        
        # Activar ejecución
        sequence.extend(self.create_set_variable_sequence(1, 1))
        
        return sequence
    
    def create_control_execution_sequence(self, control_value: int) -> list:
        """
        Crea una secuencia para controlar la ejecución.
        
        Args:
            control_value: Valor de control (0=deshabilitado, 1=iniciar, 2=reanudar, 3=ejecutándose)
            
        Returns:
            Lista de comandos para ejecutar
        """
        return self.create_set_variable_sequence(3, control_value)  # MAQUINA_ESTADOS = 3
    
    def create_move_to_home_sequence(self, sequence_id: int = None) -> tuple:
        """
        Crea una secuencia para mover el robot a HOME.
        
        Args:
            sequence_id: ID único de secuencia (opcional, se genera automáticamente si no se proporciona)
            
        Returns:
            Tupla con (lista de comandos, ID de secuencia)
        """
        # Generar ID de secuencia si no se proporciona
        if sequence_id is None:
            sequence_id = self.generate_sequence_id()
        
        sequence = []
        
        # 1. Establecer ID de secuencia
        sequence.extend(self.create_set_variable_sequence(1, sequence_id))  # ID_COM = 1
        
        # 2. Establecer comando Move to Home
        sequence.extend(self.create_set_variable_sequence(4, 1))  # MOVE_TO_HOME = 4, valor = 1
        
        return sequence, sequence_id
    
    def create_test_routine_sequence(self, sequence_id: int = None) -> tuple:
        """
        Crea una secuencia para ejecutar la rutina de prueba.
        
        Args:
            sequence_id: ID único de secuencia (opcional, se genera automáticamente si no se proporciona)
            
        Returns:
            Tupla con (lista de comandos, ID de secuencia)
        """
        # Generar ID de secuencia si no se proporciona
        if sequence_id is None:
            sequence_id = self.generate_sequence_id()
        
        sequence = []
        
        # 1. Establecer ID de secuencia
        sequence.extend(self.create_set_variable_sequence(1, sequence_id))  # ID_COM = 1
        
        # 2. Establecer rutina de prueba
        sequence.extend(self.create_set_variable_sequence(3, 10))  # MAQUINA_ESTADOS = 3, valor = 10
        
        return sequence, sequence_id
    
    def create_set_multiple_variables_sequence(self, variables: dict) -> list:
        """
        Crea una secuencia para establecer múltiples variables en una sola ejecución.
        
        Args:
            variables: Diccionario con {índice: valor} o {nombre_variable: valor}
            
        Returns:
            Lista con la secuencia completa de comandos
        """
        sequence = []
        
        for key, value in variables.items():
            # Determinar el índice de la variable
            if isinstance(key, int):
                index = key
            elif isinstance(key, str):
                # Buscar por nombre de variable
                variable = self.registry.get_variable_by_name(key)
                if variable:
                    index = variable.index
                else:
                    raise ValueError(f"Variable '{key}' no encontrada")
            else:
                raise ValueError(f"Clave inválida: {key}")
            
            # Agregar secuencia para esta variable
            sequence.extend(self.create_set_variable_sequence(index, value))
        
        return sequence
    
    def create_set_coordinates_sequence(self, x: float = None, y: float = None, z: float = None, 
                                      a: float = None, e: float = None, r: float = None) -> list:
        """
        Crea una secuencia para establecer coordenadas del robot.
        
        Args:
            x, y, z, a, e, r: Valores de coordenadas (opcionales)
            
        Returns:
            Lista con la secuencia de comandos
        """
        variables = {}
        
        if x is not None:
            variables[22] = x  # dX = 22
        if y is not None:
            variables[23] = y  # dY = 23
        if z is not None:
            variables[24] = z  # dZ = 24
        if a is not None:
            variables[25] = a  # dA = 25
        if e is not None:
            variables[26] = e  # dE = 26
        if r is not None:
            variables[27] = r  # dR = 27
        
        return self.create_set_multiple_variables_sequence(variables)
    
    def create_execute_robot_command_sequence(self, command_id: int, 
                                            x: float = None, y: float = None, z: float = None,
                                            a: float = None, e: float = None, r: float = None) -> list:
        """
        Crea una secuencia completa para ejecutar un comando del robot con coordenadas.
        
        Args:
            command_id: ID del comando a ejecutar
            x, y, z, a, e, r: Valores de coordenadas (opcionales)
            
        Returns:
            Lista con la secuencia completa de comandos
        """
        sequence = []
        
        # Establecer coordenadas si se proporcionan
        if any(val is not None for val in [x, y, z, a, e, r]):
            sequence.extend(self.create_set_coordinates_sequence(x, y, z, a, e, r))
        
        # Establecer ID del comando
        sequence.extend(self.create_set_variable_sequence(4, command_id))  # MOVE_TO_HOME = 4
        
        # Activar ejecución
        sequence.extend(self.create_set_variable_sequence(3, 1))  # MAQUINA_ESTADOS = 3
        
        return sequence
    
    def create_command_with_sequence(self, command_variable_index: int, command_value: Any, 
                                   sequence_id: int = None) -> list:
        """
        Crea una secuencia para ejecutar un comando con ID de secuencia para identificar la respuesta.
        
        Args:
            command_variable_index: Índice de la variable que activa el comando (ej: 87)
            command_value: Valor que activa el comando (ej: 1)
            sequence_id: ID único de secuencia (opcional, se genera automáticamente si no se proporciona)
            
        Returns:
            Lista con la secuencia de comandos
        """
        import time
        
        # Generar ID de secuencia si no se proporciona
        if sequence_id is None:
            sequence_id = int(time.time() * 1000) % 10000  # Últimos 4 dígitos del timestamp
        
        sequence = []
        
        # 1. Establecer ID de secuencia
        sequence.extend(self.create_set_variable_sequence(2, sequence_id))
        
        # 2. Activar el comando
        sequence.extend(self.create_set_variable_sequence(command_variable_index, command_value))
        
        return sequence
    
    def create_command_with_sequence_and_params(self, command_variable_index: int, command_value: Any,
                                              sequence_id: int = None, 
                                              x: float = None, y: float = None, z: float = None,
                                              a: float = None, e: float = None, r: float = None) -> list:
        """
        Crea una secuencia completa para ejecutar un comando con parámetros y ID de secuencia.
        
        Args:
            command_variable_index: Índice de la variable que activa el comando
            command_value: Valor que activa el comando
            sequence_id: ID único de secuencia (opcional)
            x, y, z, a, e, r: Parámetros de coordenadas (opcionales)
            
        Returns:
            Lista con la secuencia completa de comandos
        """
        import time
        
        # Generar ID de secuencia si no se proporciona
        if sequence_id is None:
            sequence_id = int(time.time() * 1000) % 10000
        
        sequence = []
        
        # 1. Establecer coordenadas si se proporcionan
        if any(val is not None for val in [x, y, z, a, e, r]):
            sequence.extend(self.create_set_coordinates_sequence(x, y, z, a, e, r))
        
        # 2. Establecer ID de secuencia
        sequence.extend(self.create_set_variable_sequence(2, sequence_id))
        
        # 3. Activar el comando
        sequence.extend(self.create_set_variable_sequence(command_variable_index, command_value))
        
        return sequence
    
    def generate_sequence_id(self) -> int:
        """
        Genera un ID único de secuencia entre 0-9999.
        Evita repeticiones en las últimas 20 ejecuciones.
        
        Returns:
            ID único de secuencia
        """
        import time
        import random
        
        # Lista para mantener las últimas 20 secuencias usadas
        if not hasattr(self, '_used_sequences'):
            self._used_sequences = []
        
        # Generar ID único
        max_attempts = 100
        for attempt in range(max_attempts):
            # Usar timestamp + random para mayor unicidad
            sequence_id = int(time.time() * 1000) % 10000
            
            # Si no está en las últimas 20, usarlo
            if sequence_id not in self._used_sequences:
                # Agregar a la lista de usados
                self._used_sequences.append(sequence_id)
                
                # Mantener solo las últimas 20
                if len(self._used_sequences) > 20:
                    self._used_sequences.pop(0)
                
                return sequence_id
        
        # Si no se encuentra uno único, usar random
        sequence_id = random.randint(0, 9999)
        self._used_sequences.append(sequence_id)
        if len(self._used_sequences) > 20:
            self._used_sequences.pop(0)
        
        return sequence_id
    
    def create_hello_command_sequence(self, sequence_id: int = None) -> tuple:
        """
        Crea una secuencia para enviar el comando de prueba HOLA.
        
        Args:
            sequence_id: ID único de secuencia (opcional, se genera automáticamente si no se proporciona)
            
        Returns:
            Tupla con (lista de comandos, ID de secuencia)
        """
        # Generar ID de secuencia si no se proporciona
        if sequence_id is None:
            sequence_id = self.generate_sequence_id()
        
        sequence = []
        
        # 1. Establecer ID de secuencia
        sequence.extend(self.create_set_variable_sequence(1, sequence_id))  # ID_COM = 1
        
        # 2. Establecer comando de prueba HOLA
        sequence.extend(self.create_set_variable_sequence(2, 1))  # SAY_HELLO = 2, valor = 1
        
        return sequence, sequence_id


# Instancia global del registro de variables
_variable_registry = COMAUVariableRegistry()
_variable_commands = COMAUVariableCommands(_variable_registry)


def get_variable_registry() -> COMAUVariableRegistry:
    """Obtiene la instancia global del registro de variables"""
    return _variable_registry


def get_variable_commands() -> COMAUVariableCommands:
    """Obtiene la instancia global de comandos de variables"""
    return _variable_commands


# Constantes de conveniencia
class COMAUVariables:
    """Constantes de variables del sistema para fácil acceso"""
    
    # Variables del sistema (0X)
    ID_COM = 1  # Variable que se usa a la hora de responder con el Index
    SAY_HELLO = 2  # Comando para decir Hola
    MAQUINA_ESTADOS = 3  # Índice de la máquina de estados
    MOVE_TO_HOME = 4  # Comando para enviar el brazo al HOME
    
    # Argumentos offsets (2X)
    dX = 22
    dY = 23
    dZ = 24
    dA = 25
    dE = 26
    dR = 27


# Valores de control de ejecución
class COMAUControlValues:
    """Valores de control para la máquina de estados"""
    DISABLED = 0      # Deshabilitado
    START_FRESH = 1   # Iniciar de cero
    RESUME = 2        # Reanudar
    EXECUTING = 3     # Ejecutándose


if __name__ == "__main__":
    # Ejemplo de uso
    registry = get_variable_registry()
    commands = get_variable_commands()
    
    print("Variables del sistema COMAU:")
    print("=" * 50)
    
    for index, variable in registry.get_all_variables().items():
        print(f"$WORD[{index}] - {variable.name}")
        print(f"  Descripción: {variable.description}")
        print(f"  Tipo: {variable.type.value}")
        if variable.valid_values:
            print(f"  Valores válidos: {variable.valid_values}")
        print()
    
    print("Ejemplo de comando para establecer variable:")
    cmd = commands.create_word_command(COMAUVariables.SAY_HELLO, 1)
    print(f"Comando: {cmd}")
    
    print("\nEjemplo de secuencia para una variable:")
    sequence = commands.create_set_variable_sequence(COMAUVariables.dX, 100)
    for i, cmd in enumerate(sequence):
        print(f"{i+1}. {cmd['description']}")
    
    print("\nEjemplo de secuencia para múltiples variables:")
    variables = {COMAUVariables.dX: 100, COMAUVariables.dY: 200, COMAUVariables.dZ: 300}
    sequence = commands.create_set_multiple_variables_sequence(variables)
    for i, cmd in enumerate(sequence):
        print(f"{i+1}. {cmd['description']}")
    
    print("\nEjemplo de secuencia completa para ejecutar comando:")
    sequence = commands.create_execute_robot_command_sequence(100, x=100, y=200, z=300)
    for i, cmd in enumerate(sequence):
        print(f"{i+1}. {cmd['description']}")
    
    print("\nEjemplo de comando con secuencia de control:")
    sequence = commands.create_command_with_sequence(2, 1, 1234)  # Ejemplo: SAY_HELLO = 1 con secuencia 1234
    for i, cmd in enumerate(sequence):
        print(f"{i+1}. {cmd['description']}")
    
    print("\nEjemplo de comando completo con parámetros y secuencia:")
    sequence = commands.create_command_with_sequence_and_params(2, 1, 1234, x=100, y=200, z=300)
    for i, cmd in enumerate(sequence):
        print(f"{i+1}. {cmd['description']}")
    
    print("\nEjemplo de comando HOLA:")
    sequence, sequence_id = commands.create_hello_command_sequence()
    for i, cmd in enumerate(sequence):
        print(f"{i+1}. {cmd['description']}")
    print(f"ID de secuencia: {sequence_id}")
    
    print("\nEjemplo de comando Move to Home:")
    sequence, sequence_id = commands.create_move_to_home_sequence()
    for i, cmd in enumerate(sequence):
        print(f"{i+1}. {cmd['description']}")
    print(f"ID de secuencia: {sequence_id}")
    
    print("\nEjemplo de Rutina de Prueba:")
    sequence, sequence_id = commands.create_test_routine_sequence()
    for i, cmd in enumerate(sequence):
        print(f"{i+1}. {cmd['description']}")
    print(f"ID de secuencia: {sequence_id}")
    
    print(f"\nID de secuencia generado: {commands.generate_sequence_id()}")
    print(f"Secuencias usadas recientemente: {commands._used_sequences}")
