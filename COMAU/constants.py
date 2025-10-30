"""
COMAU Constants Module
=====================

Este módulo lee las constantes definidas en WORDS_IDX.h y las hace
disponibles para uso en Python.

Autor: Illinois Automation
Fecha: 2024
"""

import os
import re
from typing import Dict, Any


def _parse_c_header(file_path: str) -> Dict[str, int]:
    """
    Parsea un archivo header C (.h) y extrae las constantes #define.
    
    Args:
        file_path: Ruta al archivo .h
        
    Returns:
        Diccionario con las constantes encontradas
    """
    constants = {}
    
    if not os.path.exists(file_path):
        print(f"[constants] ⚠️ Archivo {file_path} no encontrado")
        return constants
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Patrón regex para encontrar #define CONSTANTE valor
        pattern = r'#define\s+(\w+)\s+(\d+)'
        matches = re.findall(pattern, content)
        
        for name, value in matches:
            constants[name] = int(value)
            print(f"[constants] 📋 Cargada constante: {name} = {value}")
        
        print(f"[constants] ✅ Cargadas {len(constants)} constantes desde {file_path}")
        
    except Exception as e:
        print(f"[constants] ❌ Error parseando {file_path}: {e}")
    
    return constants


# Ruta al archivo WORDS_IDX.h
_WORDS_IDX_PATH = os.path.join(os.path.dirname(__file__), '..', 'COMAU', 'WORDS_IDX.h')

# Cargar constantes desde el header
_COMAU_CONSTANTS = _parse_c_header(_WORDS_IDX_PATH)

# Las constantes se acceden dinámicamente usando las funciones:
# - get_constant(name, default)
# - get_all_constants()
# - has_constant(name)

# Función para obtener todas las constantes
def get_all_constants() -> Dict[str, int]:
    """Retorna todas las constantes cargadas"""
    return _COMAU_CONSTANTS.copy()

# Función para obtener una constante específica
def get_constant(name: str, default: int = 0) -> int:
    """Obtiene una constante específica por nombre"""
    return _COMAU_CONSTANTS.get(name, default)

# Función para verificar si una constante existe
def has_constant(name: str) -> bool:
    """Verifica si una constante existe"""
    return name in _COMAU_CONSTANTS
