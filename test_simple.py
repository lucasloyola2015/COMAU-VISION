#!/usr/bin/env python3
"""
Servidor de prueba simple
"""

print("🚀 Servidor de prueba iniciado")
print("✅ Funcionando correctamente")

# Simular un servidor que se mantiene ejecutándose
import time
import sys

try:
    while True:
        print("⏰ Servidor ejecutándose...")
        time.sleep(5)
except KeyboardInterrupt:
    print("🛑 Servidor detenido")
    sys.exit(0)

