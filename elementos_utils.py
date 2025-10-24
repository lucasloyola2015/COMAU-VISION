"""
Utilidades Compartidas para Elementos de Marcado
=================================================

Funciones helper para cálculo y extracción de datos de elementos
(muescas, illinois, codigo, lote)
"""

from typing import List, Dict, Tuple

# Constantes
SEPARACION_MUESCAS_MM = 7.0
DIAMETRO_MUESCA_MM = 4.0
ALTURA_TEXTO_MM = 4.0

def calcular_centros_muescas(cantidad: int, 
                             primera_x_mm: float, 
                             primera_y_mm: float, 
                             vertical: bool) -> List[Dict]:
    """
    Calcula los centros de todas las muescas en mm (relativas al punto medio)
    
    Args:
        cantidad: Número de muescas
        primera_x_mm: Coordenada X de la primera muesca
        primera_y_mm: Coordenada Y de la primera muesca
        vertical: True para orientación vertical
    
    Returns:
        Lista de diccionarios: [{'id': 1, 'centro_mm': [x, y]}, ...]
    """
    if cantidad <= 0:
        return []
    
    centros = []
    for i in range(cantidad):
        if vertical:
            centro_mm = [primera_x_mm, primera_y_mm + (i * SEPARACION_MUESCAS_MM)]
        else:
            centro_mm = [primera_x_mm + (i * SEPARACION_MUESCAS_MM), primera_y_mm]
        
        centros.append({
            'id': i + 1,
            'centro_mm': [round(centro_mm[0], 1), round(centro_mm[1], 1)]
        })
    
    return centros


def extraer_datos_elementos_form(request_form) -> Dict:
    """
    Extrae todos los datos de elementos (muescas, illinois, codigo, lote) del FormData
    
    Args:
        request_form: request.form de Flask
    
    Returns:
        Diccionario con todos los datos extraídos y parseados
    """
    # Helper para convertir checkbox
    def parse_bool(value):
        return value == 'on' or value == 'true'
    
    # Helper para convertir número
    def parse_float(value, default=None):
        if value and str(value).strip():
            return float(value)
        return default
    
    def parse_int(value, default=0):
        if value and str(value).strip():
            return int(value)
        return default
    
    return {
        # Muescas
        'cantidad_muescas': parse_int(request_form.get('cantidadMuescas'), 0),
        'muesca_x': parse_float(request_form.get('muescaX'), 0.0),
        'muesca_y': parse_float(request_form.get('muescaY'), 0.0),
        'muescas_vertical': parse_bool(request_form.get('muescasVertical')),
        
        # Illinois
        'illinois_x': parse_float(request_form.get('illinoisX')),
        'illinois_y': parse_float(request_form.get('illinoisY')),
        'illinois_vertical': parse_bool(request_form.get('illinoisVertical')),
        
        # Código
        'codigo_x': parse_float(request_form.get('codigoX')),
        'codigo_y': parse_float(request_form.get('codigoY')),
        'codigo_vertical': parse_bool(request_form.get('codigoVertical')),
        
        # Lote
        'lote_x': parse_float(request_form.get('loteX')),
        'lote_y': parse_float(request_form.get('loteY')),
        'lote_vertical': parse_bool(request_form.get('loteVertical'))
    }


def extraer_datos_elementos_json(request_json, junta_fallback) -> Dict:
    """
    Extrae datos de elementos desde JSON (POST) con fallback a junta guardada
    
    Args:
        request_json: request.get_json() de Flask
        junta_fallback: Diccionario de la junta guardada (para valores default)
    
    Returns:
        Diccionario con todos los datos
    """
    return {
        # Muescas
        'cantidad_muescas': request_json.get('cantidad_muescas', junta_fallback.get('cantidad_muescas', 0)),
        'muesca_x': request_json.get('muesca_x', 
                                     junta_fallback.get('centros_muescas', [{}])[0].get('centro_mm', [0.0])[0] if junta_fallback.get('centros_muescas') else 0.0),
        'muesca_y': request_json.get('muesca_y',
                                     junta_fallback.get('centros_muescas', [{}])[0].get('centro_mm', [0.0, 0.0])[1] if junta_fallback.get('centros_muescas') else 0.0),
        'vertical': request_json.get('vertical', junta_fallback.get('muescas_vertical', False)),
        
        # Illinois
        'illinois_x': request_json.get('illinois_x', junta_fallback.get('illinois_x', 0.0)),
        'illinois_y': request_json.get('illinois_y', junta_fallback.get('illinois_y', 0.0)),
        'illinois_vertical': request_json.get('illinois_vertical', junta_fallback.get('illinois_vertical', False)),
        
        # Código
        'codigo_x': request_json.get('codigo_x', junta_fallback.get('codigo_x', 0.0)),
        'codigo_y': request_json.get('codigo_y', junta_fallback.get('codigo_y', 0.0)),
        'codigo_vertical': request_json.get('codigo_vertical', junta_fallback.get('codigo_vertical', False)),
        
        # Lote
        'lote_x': request_json.get('lote_x', junta_fallback.get('lote_x', 0.0)),
        'lote_y': request_json.get('lote_y', junta_fallback.get('lote_y', 0.0)),
        'lote_vertical': request_json.get('lote_vertical', junta_fallback.get('lote_vertical', False))
    }


def obtener_primera_muesca_desde_centros(centros_muescas: List[Dict]) -> Tuple[float, float]:
    """
    Extrae las coordenadas de la primera muesca desde el array de centros
    
    Args:
        centros_muescas: Array de centros guardado en BD
    
    Returns:
        Tupla (x, y) de la primera muesca
    """
    if centros_muescas and len(centros_muescas) > 0:
        centro = centros_muescas[0].get('centro_mm', [0.0, 0.0])
        return (centro[0], centro[1])
    return (0.0, 0.0)


def obtener_datos_elementos_para_renderizar(request_method, request_json_data, junta) -> Dict:
    """
    Obtiene datos de elementos para renderizar (desde POST request o desde BD)
    
    Args:
        request_method: 'GET' o 'POST'
        request_json_data: request.get_json() si es POST, None si es GET
        junta: Diccionario de la junta desde BD
    
    Returns:
        Diccionario con datos listos para renderizar
    """
    # Helper: Si viene null del frontend, usar valor de BD; si no viene, usar 0.0
    def get_coord(key, junta_key):
        if request_method == 'POST' and request_json_data:
            value = request_json_data.get(key)
            if value is None:
                # null desde frontend → usar BD
                return junta.get(junta_key, 0.0)
            return value
        return junta.get(junta_key, 0.0)
    
    if request_method == 'POST' and request_json_data:
        # Desde POST, con fallback inteligente a BD
        # Extraer coordenadas de primera muesca desde BD
        primera_x_bd, primera_y_bd = obtener_primera_muesca_desde_centros(junta.get('centros_muescas', []))
        
        # Para muescas: si viene null, usar BD; si viene un número (incluso 0), usarlo
        muesca_x_val = request_json_data.get('muesca_x')
        if muesca_x_val is None:
            muesca_x_val = primera_x_bd
        
        muesca_y_val = request_json_data.get('muesca_y')
        if muesca_y_val is None:
            muesca_y_val = primera_y_bd
        
        return {
            'cantidad_muescas': request_json_data.get('cantidad_muescas', junta.get('cantidad_muescas', 0)),
            'muesca_x': muesca_x_val,
            'muesca_y': muesca_y_val,
            'vertical': request_json_data.get('vertical', junta.get('muescas_vertical', False)),
            'illinois_x': get_coord('illinois_x', 'illinois_x'),
            'illinois_y': get_coord('illinois_y', 'illinois_y'),
            'illinois_vertical': request_json_data.get('illinois_vertical', junta.get('illinois_vertical', False)),
            'codigo_x': get_coord('codigo_x', 'codigo_x'),
            'codigo_y': get_coord('codigo_y', 'codigo_y'),
            'codigo_vertical': request_json_data.get('codigo_vertical', junta.get('codigo_vertical', False)),
            'lote_x': get_coord('lote_x', 'lote_x'),
            'lote_y': get_coord('lote_y', 'lote_y'),
            'lote_vertical': request_json_data.get('lote_vertical', junta.get('lote_vertical', False))
        }
    else:
        # Desde BD (GET)
        primera_x, primera_y = obtener_primera_muesca_desde_centros(junta.get('centros_muescas', []))
        return {
            'cantidad_muescas': junta.get('cantidad_muescas', 0),
            'muesca_x': primera_x,
            'muesca_y': primera_y,
            'vertical': junta.get('muescas_vertical', False),
            'illinois_x': junta.get('illinois_x', 0.0),
            'illinois_y': junta.get('illinois_y', 0.0),
            'illinois_vertical': junta.get('illinois_vertical', False),
            'codigo_x': junta.get('codigo_x', 0.0),
            'codigo_y': junta.get('codigo_y', 0.0),
            'codigo_vertical': junta.get('codigo_vertical', False),
            'lote_x': junta.get('lote_x', 0.0),
            'lote_y': junta.get('lote_y', 0.0),
            'lote_vertical': junta.get('lote_vertical', False)
        }


