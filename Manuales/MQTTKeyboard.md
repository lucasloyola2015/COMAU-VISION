# SimpleMQTTKeyboard \- Documentación de API

## Descripción General

SimpleMQTTKeyboard es un controlador MQTT simplificado que permite ejecutar secuencias de teclas, gestionar procesos WinC5G y realizar búsquedas en memoria. Se conecta al broker MQTT y responde a comandos específicos.

## Configuración MQTT

- **Broker:** `localhost:1883`  
- **Topic de comandos:** `COMAU/commands`  
- **Topic de respuestas:** `COMAU/responses`

## Comandos Disponibles

### 1\. ExecuteKeySequence

Ejecuta una secuencia de teclas en la aplicación WinC5G.exe.

#### JSON de Entrada:

{

  "command": "ExecuteKeySequence",

  "timestamp": "2025-10-22T16:30:00",

  "args": {

    "sequence": \[

      {

        "action": "delay",

        "ms": 300,

        "description": "Delay inicial"

      },

      {

        "action": "press\_key",

        "key": "ESC",

        "description": "Presionar ESC",

        "delay\_after": 200

      },

      {

        "action": "type\_text",

        "text": "COMAU",

        "description": "Escribir texto",

        "delay\_after": 200

      },

      {

        "action": "hotkey",

        "keys": \["CTRL", "T"\],

        "description": "Combinación de teclas",

        "delay\_after": 500

      }

    \],

    "options": {

      "verify\_focus": true,

      "restore\_focus": false,

      "abort\_on\_error": true,

      "dry\_run": false

    }

  },

  "request\_id": "seq\_1234567890"

}

#### Tipos de Acciones Disponibles:

**delay:**

{

  "action": "delay",

  "ms": 300,

  "description": "Esperar 300ms"

}

**press\_key:**

{

  "action": "press\_key",

  "key": "ENTER",

  "description": "Presionar ENTER",

  "delay\_after": 200

}

**type\_text:**

{

  "action": "type\_text",

  "text": "Texto a escribir",

  "description": "Escribir texto",

  "delay\_after": 200

}

**hotkey:**

{

  "action": "hotkey",

  "keys": \["CTRL", "T"\],

  "description": "Combinación CTRL+T",

  "delay\_after": 500

}

#### Teclas Soportadas:

- **Teclas especiales:** ESC, ENTER, TAB, SPACE, BACKSPACE, DELETE  
- **Teclas de función:** F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12  
- **Teclas de flecha:** UP, DOWN, LEFT, RIGHT  
- **Modificadores:** CTRL, ALT, SHIFT, WIN  
- **Teclas alfanuméricas:** A-Z, 0-9, símbolos

#### Respuesta de Éxito:

{

  "status": "success",

  "command": "ExecuteKeySequence",

  "request\_id": "seq\_1234567890",

  "timestamp": "2025-10-22T16:30:05",

  "message": "Secuencia ejecutada exitosamente",

  "execution\_time\_ms": 2500,

  "actions\_executed": 4,

  "actions\_failed": 0

}

#### Respuesta de Error:

{

  "status": "error",

  "command": "ExecuteKeySequence",

  "request\_id": "seq\_1234567890",

  "timestamp": "2025-10-22T16:30:05",

  "error\_code": "PROCESS\_NOT\_FOUND",

  "error\_message": "WinC5G.exe no encontrado"

}

---

### 2\. FindDriveBlock

Busca el bloque "Drive" en la memoria del proceso WinC5G.exe.

#### JSON de Entrada:

{

  "command": "FindDriveBlock",

  "timestamp": "2025-10-22T16:30:00",

  "args": {},

  "request\_id": "find\_1234567890"

}

#### Respuesta de Éxito:

{

  "status": "success",

  "command": "FindDriveBlock",

  "request\_id": "find\_1234567890",

  "timestamp": "2025-10-22T16:30:05",

  "message": "Bloque Drive encontrado",

  "start\_address": "0x396463e",

  "end\_address": "0x3964e06",

  "size": 1992,

  "start\_string": "Drive:",

  "end\_string": "F6        F7        F8",

  "found": true,

  "data": "Drive:OFF  State:LOCAL  HOLD     %85..."

}

#### Respuesta de Error:

{

  "status": "error",

  "command": "FindDriveBlock",

  "request\_id": "find\_1234567890",

  "timestamp": "2025-10-22T16:30:05",

  "error\_code": "BLOCK\_NOT\_FOUND",

  "error\_message": "Bloque Drive no encontrado en memoria"

}

---

### 3\. ResetWinc5g

Reinicia la aplicación WinC5G.exe matando todos los procesos existentes y ejecutando uno nuevo.

#### JSON de Entrada:

{

  "command": "ResetWinc5g",

  "timestamp": "2025-10-22T16:30:00",

  "args": {},

  "request\_id": "reset\_1234567890"

}

#### Respuesta de Éxito:

{

  "status": "success",

  "command": "ResetWinc5g",

  "request\_id": "reset\_1234567890",

  "timestamp": "2025-10-22T16:30:10",

  "message": "WinC5G reiniciado exitosamente",

  "killed\_processes": \[1234, 5678\],

  "new\_process\_pid": 9999,

  "execution\_time\_ms": 5000

}

#### Respuesta de Error:

{

  "status": "error",

  "command": "ResetWinc5g",

  "request\_id": "reset\_1234567890",

  "timestamp": "2025-10-22T16:30:10",

  "error\_code": "PROCESS\_START\_FAILED",

  "error\_message": "No se pudo iniciar el nuevo proceso WinC5G"

}

---

### 4\. InitWinC5G

Comando unificado que ejecuta una secuencia completa de inicialización:

1. ResetWinC5g  
2. Espera 5 segundos  
3. Ejecuta secuencia de teclas hardcodeada  
4. Busca el bloque Drive  
5. Verifica que "Instr:" existe en el bloque

#### JSON de Entrada:

{

  "command": "InitWinC5G",

  "timestamp": "2025-10-22T16:30:00",

  "args": {},

  "request\_id": "init\_1234567890"

}

#### Respuesta de Éxito:

{

  "status": "success",

  "command": "InitWinC5G",

  "request\_id": "init\_1234567890",

  "timestamp": "2025-10-22T16:30:25",

  "message": "Inicialización completa de WinC5G exitosa \- Instr: encontrado",

  "initialization\_completed": true,

  "steps\_completed": \[

    "ResetWinc5g",

    "ExecuteKeySequence", 

    "FindDriveBlock",

    "WaitForInstr",

    "VerifyInstr"

  \],

  "reset\_result": {...},

  "sequence\_result": {...},

  "find\_result": {...},

  "instr\_search\_result": {...},

  "instr\_found": true

}

#### Respuesta de Error:

{

  "status": "error",

  "command": "InitWinC5G",

  "request\_id": "init\_1234567890",

  "timestamp": "2025-10-22T16:30:25",

  "error\_code": "INITIALIZATION\_INCOMPLETE",

  "error\_message": "Inicialización incompleta \- Instr: no encontrado en el bloque Drive",

  "initialization\_completed": false,

  "steps\_completed": \["ResetWinc5g", "ExecuteKeySequence", "FindDriveBlock", "WaitForInstr"\]

}

---

### 5\. FindStringLenInBlock

Busca un string específico dentro de un bloque de memoria y retorna N caracteres después del string encontrado.

#### JSON de Entrada:

{

  "command": "FindStringLenInBlock",

  "timestamp": "2025-10-22T16:30:00",

  "args": {

    "block\_id": 1,

    "search\_string": "Instr:",

    "length": 50,

    "timeout\_ms": 5000

  },

  "request\_id": "search\_1234567890"

}

#### Respuesta de Éxito:

{

  "status": "success",

  "command": "FindStringLenInBlock",

  "request\_id": "search\_1234567890",

  "timestamp": "2025-10-22T16:30:05",

  "message": "'Instr:' encontrado en bloque Drive",

  "block\_id": 1,

  "search\_string": "Instr:",

  "length": 50,

  "occurrences": \[

    {

      "position": 1850,

      "context": "                                                                          E                   ",

      "full\_context": "                                                  Instr:                                                                          E                   ",

      "block\_address": "0x396463e",

      "block\_size": 1992

    }

  \]

}

#### Respuesta de Error:

{

  "status": "error",

  "command": "FindStringLenInBlock",

  "request\_id": "search\_1234567890",

  "timestamp": "2025-10-22T16:30:05",

  "error\_code": "STRING\_NOT\_FOUND",

  "error\_message": "'Instr:' no encontrado en el bloque Drive",

  "block\_id": 1,

  "search\_string": "Instr:",

  "block\_address": "0x396463e",

  "block\_size": 1992

}

---

### 6\. ExecuteKeySequenceWithInstrCheck

Ejecuta una secuencia de teclas solo si el string "Instr:" existe en el bloque Drive.

#### JSON de Entrada:

{

  "command": "ExecuteKeySequenceWithInstrCheck",

  "timestamp": "2025-10-22T16:30:00",

  "args": {

    "sequence": \[

      {

        "action": "type\_text",

        "text": "$FMI\[1\]:=0",

        "description": "Escribir '$FMI\[1\]:=0'",

        "delay\_after": 200

      },

      {

        "action": "press\_key",

        "key": "ENTER",

        "description": "Primer ENTER",

        "delay\_after": 200

      },

      {

        "action": "press\_key",

        "key": "ENTER",

        "description": "Segundo ENTER",

        "delay\_after": 200

      },

      {

        "action": "press\_key",

        "key": "ENTER",

        "description": "Tercer ENTER",

        "delay\_after": 500

      }

    \],

    "instr\_check": {

      "enabled": true,

      "block\_id": 1,

      "search\_string": "Instr:",

      "timeout\_ms": 5000

    },

    "options": {

      "verify\_focus": true,

      "restore\_focus": false,

      "abort\_on\_error": true,

      "dry\_run": false

    }

  },

  "request\_id": "seq\_instr\_1234567890"

}

#### Respuesta de Éxito:

{

  "status": "success",

  "command": "ExecuteKeySequenceWithInstrCheck",

  "request\_id": "seq\_instr\_1234567890",

  "timestamp": "2025-10-22T16:30:05",

  "message": "Secuencia ejecutada exitosamente después de verificar Instr:",

  "instr\_check\_passed": true,

  "instr\_found\_at\_position": 1850,

  "instr\_context": "                                                  Instr:                                                                          E                   ",

  "block\_address": "0x396463e",

  "block\_size": 1992,

  "sequence\_result": {...}

}

#### Respuesta de Error (Instr no encontrado):

{

  "status": "error",

  "command": "ExecuteKeySequenceWithInstrCheck",

  "request\_id": "seq\_instr\_1234567890",

  "timestamp": "2025-10-22T16:30:05",

  "error\_code": "INSTR\_NOT\_FOUND",

  "error\_message": "'Instr:' no encontrado en el bloque Drive \- secuencia no ejecutada",

  "block\_found": true,

  "block\_address": "0x396463e",

  "block\_size": 1992

}

---

### 7\. VerifyInstr

Verifica si el string "Instr:" existe actualmente en el bloque Drive de memoria del proceso WinC5G.exe y devuelve true/false.

#### JSON de Entrada:

{

  "command": "VerifyInstr",

  "timestamp": "2025-10-22T16:30:00",

  "args": {},

  "request\_id": "verify\_1234567890"

}

#### Respuesta de Éxito (encontrado):

{

  "status": "success",

  "command": "VerifyInstr",

  "request\_id": "verify\_1234567890",

  "timestamp": "2025-10-22T16:30:05",

  "found": true,

  "block\_address": "0x396463e",

  "block\_size": 1992

}

#### Respuesta de Éxito (no encontrado o bloque ausente):

{

  "status": "success",

  "command": "VerifyInstr",

  "request\_id": "verify\_1234567890",

  "timestamp": "2025-10-22T16:30:05",

  "found": false,

  "message": "Bloque Drive no encontrado"

}

#### Respuesta de Error:

{

  "status": "error",

  "command": "VerifyInstr",

  "request\_id": "verify\_1234567890",

  "timestamp": "2025-10-22T16:30:05",

  "error\_code": "PROCESS\_NOT\_FOUND",

  "error\_message": "WinC5G.exe no encontrado"

}

---

## Códigos de Error Comunes

| Código | Descripción |
| :---- | :---- |
| `PROCESS_NOT_FOUND` | WinC5G.exe no está ejecutándose |
| `BLOCK_NOT_FOUND` | Bloque Drive no encontrado en memoria |
| `STRING_NOT_FOUND` | String específico no encontrado en el bloque |
| `INSTR_NOT_FOUND` | "Instr:" no encontrado en el bloque Drive |
| `SEQUENCE_FAILED` | La secuencia de teclas falló en la ejecución |
| `INITIALIZATION_INCOMPLETE` | Inicialización no completada exitosamente |
| `PROCESS_START_FAILED` | No se pudo iniciar el proceso WinC5G |
| `MISSING_ARGUMENT` | Falta un argumento requerido en el JSON |
| `INVALID_COMMAND` | Comando no reconocido |
| `EXECUTION_ERROR` | Error general en la ejecución |

## Ejemplos de Uso

### Ejemplo 1: Secuencia Simple

{

  "command": "ExecuteKeySequence",

  "timestamp": "2025-10-22T16:30:00",

  "args": {

    "sequence": \[

      {

        "action": "type\_text",

        "text": "Hola Mundo",

        "delay\_after": 500

      },

      {

        "action": "press\_key",

        "key": "ENTER",

        "delay\_after": 200

      }

    \]

  },

  "request\_id": "test\_001"

}

### Ejemplo 2: Verificación de Instr antes de Ejecutar

{

  "command": "ExecuteKeySequenceWithInstrCheck",

  "timestamp": "2025-10-22T16:30:00",

  "args": {

    "sequence": \[

      {

        "action": "type\_text",

        "\[$FMI\[1\]:=0",

        "delay\_after": 200

      }

    \],

    "instr\_check": {

      "enabled": true,

      "search\_string": "Instr:"

    }

  },

  "request\_id": "test\_002"

}

## Notas Importantes

1. **Enfoque de ventana:** El sistema fuerza automáticamente el foco a WinC5G.exe antes de ejecutar secuencias  
2. **Delays:** Todos los delays están en milisegundos (ms)  
3. **Verificación de proceso:** La mayoría de comandos verifican que WinC5G.exe esté ejecutándose  
4. **Bloque Drive:** El bloque Drive se busca entre los delimitadores "Drive:" y "F6        F7        F8"  
5. **Reutilización de código:** Los comandos reutilizan funciones existentes para evitar duplicación

## Logs y Debugging

El sistema genera logs detallados que incluyen:

- Timestamps de todas las operaciones  
- Estados de los procesos  
- Contenido de bloques de memoria encontrados  
- Resultados de búsquedas de strings  
- Errores detallados con contexto

Los logs se pueden encontrar en el archivo `simple_keyboard.log`.  
