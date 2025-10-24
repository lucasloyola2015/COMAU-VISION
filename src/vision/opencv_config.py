# opencv_config.py - Configuración de OpenCV para suprimir warnings
import os
import sys

def configure_opencv():
    """Configura OpenCV para suprimir warnings innecesarios"""
    # Suprimir warnings de OpenCV
    os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'
    os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'

# Ejecutar al importar
configure_opencv()

