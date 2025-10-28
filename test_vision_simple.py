#!/usr/bin/env python3
"""
Script de prueba simple para el servidor de visión
"""
import time
import sys

print("🚀 Servidor de visión de prueba iniciado")
print(f"📁 Directorio de trabajo: {sys.path[0]}")
print(f"🐍 Python version: {sys.version}")

# Simular un servidor que responde en el puerto 8000
try:
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    @app.route('/')
    def health():
        return jsonify({
            'status': 'ok',
            'message': 'Servidor de visión funcionando',
            'timestamp': time.time()
        })
    
    @app.route('/test')
    def test():
        return jsonify({
            'test': 'success',
            'message': 'Endpoint de prueba funcionando'
        })
    
    print("✅ Flask importado correctamente")
    print("🌐 Iniciando servidor en puerto 8000...")
    
    app.run(host='127.0.0.1', port=8000, debug=False)
    
except ImportError as e:
    print(f"❌ Error importando Flask: {e}")
    print("💡 Instala Flask con: pip install flask")
    time.sleep(5)
except Exception as e:
    print(f"❌ Error inesperado: {e}")
    time.sleep(5)
