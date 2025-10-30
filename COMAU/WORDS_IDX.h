/*
 * COMAU WORDS INDEX Definitions
 * =============================
 * 
 * Este archivo contiene las definiciones de índices de variables
 * y constantes del sistema COMAU para comunicación MQTT.
 * 
 * Autor: Illinois Automation
 * Fecha: 2024
 */

#ifndef WORDS_IDX_H
#define WORDS_IDX_H

// ============================================================
// SISTEMA 0X - VARIABLES DE CONTROL
// ============================================================

#define ID_COM 1                    // Variable que se usa a la hora de responder con el Index
#define SAY_HELLO 2                 // Comando para decir Hola
#define MAQUINA_ESTADOS 3           // Indice de la maquina de estados
#define MOVE_TO_HOME 4              // Comando para enviar el brazo al HOME

// ============================================================
// ARGUMENTOS OFFSETS 2X - COORDENADAS
// ============================================================

#define dX 22                       // Argumento X - Coordenada X
#define dY 23                       // Argumento Y - Coordenada Y
#define dZ 24                       // Argumento Z - Coordenada Z
#define dA 25                       // Argumento A - Angulo A
#define dE 26                       // Argumento E - Angulo E
#define dR 27                       // Argumento R - Angulo R

// ============================================================
// PARÁMETROS DE MUESCAS 3X - MATRIZ Y CANTIDAD
// ============================================================

#define CANTIDAD_MUESCAS 30          // Cantidad total de muescas detectadas/calculadas
#define MUESCAS_MATRIX_XY 31         // Matriz/Buffer de muescas (pares X,Y consecutivos)

// ============================================================
// PARÁMETROS DE TIEMPO 4X - DELAYS
// ============================================================

#define DELAY_TROQUELADORA 40        // Delay de troqueladora (ms)

// ============================================================
// FIN DEFINICIONES WORD INDEX
// ============================================================

// ============================================================
// DEFINICIONES I/O PORTS
// ============================================================

#define EV_PINZA 7                  // OUT[7] - Puerto de salida para pinza

#endif // WORDS_IDX_H
