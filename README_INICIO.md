# 🚀 COMAU-VISION - Guía de Inicio Rápido

## ¿Qué tenemos?

El servidor Flask ya está reconstruido y completamente funcional con:
- ✅ Panel de Control (izquierda) + Dashboard (derecha)
- ✅ Lanzamiento automático de Chrome
- ✅ Modo Kiosk (pantalla completa) y Modo Ventana
- ✅ Monitoreo de Chrome con cierre ordenado

## 🎯 Cómo Ejecutar

### **Opción 1: Modo Normal (Ventana regular)**
```bash
python illinois-server.py
```
✅ Abre Chrome en una ventana normal
✅ Se ejecuta en http://127.0.0.1:5000

### **Opción 2: Modo Kiosk (Pantalla completa)**
```bash
python illinois-server.py -k
```
✅ Abre Chrome en modo pantalla completa
✅ Ideal para producción/instalación en el robot

### **Opción 3: Puerto Personalizado**
```bash
python illinois-server.py -p 8080
```
✅ Usa puerto 8080 en lugar de 5000

### **Combinado: Kiosk + Puerto Personalizado**
```bash
python illinois-server.py -k -p 8080
```

## 🖥️ Interfaz

Cuando inicia, ves:

```
┌─────────────────────────────────────────┐
│  COMAU-VISION    [MQTT] [Vision] [Robot]│
├──────────────────┬──────────────────────┤
│                  │                      │
│  Control Panel   │    Dashboard         │
│                  │                      │
│  (Lado izqdo)    │   (Lado derecho)    │
│                  │                      │
└──────────────────┴──────────────────────┘
```

## ⌨️ Controles

- **Panel Izquierdo**: Carga diferentes páginas de control
- **Panel Derecho**: Dashboard principal siempre visible
- **Iconos superiores**:
  - 🔌 MQTT: Click = VerifyInstr | Doble Click = InitWinC5G
  - 👁️ Vision: Monitoreo de cámara
  - 🤖 Robot: Click = Enviar HOLA

## ❌ Cerrando el Sistema

### Opción 1: Cerrar Chrome
- Solo cierra Chrome → El servidor se detiene automáticamente

### Opción 2: Ctrl+C en Terminal
- Presiona Ctrl+C en la terminal → Cierra todo ordenadamente

## 📋 Estado de Funcionalidades

### Implementadas ✅
- Interfaz principal (2 paneles)
- Lanzamiento de Chrome
- Monitoreo de Chrome
- API /api/status

### Pendientes de Reconstrucción ❌
- Endpoints MQTT
- Endpoints de Robot
- Endpoints de Cámara y Análisis
- Endpoints de Juntas
- Pipeline de Rutina de Prueba con WebSockets

## 🔄 Próximos Pasos

1. Reconstruir endpoints MQTT
2. Reconstruir endpoints de Robot
3. Implementar WebSockets para Rutina de Prueba
4. Integrar análisis automático

---

**¡Sistema en funcionamiento! 🎉**
