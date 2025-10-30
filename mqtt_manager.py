"""
Gestor de comunicación MQTT para el sistema de visión.
Maneja la conexión con brokers MQTT y el envío/recepción de mensajes.

Arquitectura basada en thread dedicado con máquina de estados.
"""

import json
import logging
import threading
import time
from typing import Optional, Dict, Any, Callable
from enum import Enum

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logging.warning("Librería paho-mqtt no instalada. Funcionalidad MQTT deshabilitada.")


# ============================================================================
# ESTADOS DE LA MÁQUINA DE ESTADOS
# ============================================================================
class MQTTState(Enum):
    """Estados posibles de la conexión MQTT"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    STOPPING = "stopping"


class MQTTManager:
    """
    Gestor de conexión y comunicación con brokers MQTT.
    Usa un thread dedicado y máquina de estados para gestión robusta.
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        Inicializa el gestor MQTT.
        
        Args:
            config_path: Ruta al archivo de configuración JSON
        """
        self.config_path = config_path
        self.client: Optional[mqtt.Client] = None
        
        # Configuración MQTT (se carga desde config.json)
        self.broker_ip: Optional[str] = None
        self.broker_port: int = 1883
        self.topic_commands: str = "COMAU/commands"
        self.topic_keyboard: str = "COMAU/toRobot"
        self.topic_responses: str = "COMAU/memoryData"
        self.connect_on_start: bool = True
        
        # Máquina de estados
        self._state = MQTTState.DISCONNECTED
        self._state_lock = threading.Lock()
        
        # Thread dedicado para MQTT
        self._mqtt_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        
        # Sistema de espera de respuestas
        self._pending_responses = {}  # Dict para almacenar respuestas pendientes
        self._response_lock = threading.Lock()
        
        # Callbacks personalizados
        self.on_connect_callback: Optional[Callable] = None
        self.on_disconnect_callback: Optional[Callable] = None
        self.on_message_callback: Optional[Callable] = None
        
        # Logger
        self.logger = logging.getLogger(__name__)
        self.logger.info("MQTTManager inicializado")
        
        # Cargar configuración si existe
        self._load_config()
    
    # ========================================================================
    # GETTERS/SETTERS DE ESTADO (thread-safe)
    # ========================================================================
    
    @property
    def state(self) -> MQTTState:
        """Obtiene el estado actual de la máquina de estados"""
        with self._state_lock:
            return self._state
    
    def _set_state(self, new_state: MQTTState):
        """
        Cambia el estado de la máquina de estados
        
        Args:
            new_state: Nuevo estado
        """
        with self._state_lock:
            old_state = self._state
            self._state = new_state
            if old_state != new_state:
                self.logger.info(f"Estado MQTT: {old_state.value} → {new_state.value}")
                print(f"[MQTT] Estado: {old_state.value} → {new_state.value}")
    
    @property
    def connected(self) -> bool:
        """Retorna True si el estado es CONNECTED"""
        return self.state == MQTTState.CONNECTED
    
    @property
    def is_running(self) -> bool:
        """Retorna True si el thread MQTT está activo"""
        return self._mqtt_thread is not None and self._mqtt_thread.is_alive()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Carga la configuración MQTT desde el archivo JSON.
        
        Returns:
            Diccionario con la configuración MQTT
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                mqtt_config = config.get('mqtt', {})
                
                # Cargar configuración básica
                self.broker_ip = mqtt_config.get('broker_ip')
                self.broker_port = mqtt_config.get('broker_port', 1883)
                
                # Cargar topics desde la sección 'topics'
                topics = mqtt_config.get('topics', {})
                self.topic_commands = topics.get('commands', 'COMAU/commands')
                self.topic_keyboard = topics.get('keyboard', 'COMAU/toRobot')
                self.topic_responses = topics.get('responses', 'COMAU/memoryData')
                self.connect_on_start = mqtt_config.get('connect_on_start', True)
                
                self.logger.info(f"Configuración MQTT cargada: {self.broker_ip}:{self.broker_port}")
                self.logger.debug(f"Topics: commands={self.topic_commands}, keyboard={self.topic_keyboard}, responses={self.topic_responses}")
                
                return mqtt_config
        except FileNotFoundError:
            self.logger.warning(f"Archivo de configuración {self.config_path} no encontrado")
            return {}
        except json.JSONDecodeError as e:
            self.logger.error(f"Error al decodificar JSON: {e}")
            return {}
    
    def save_config(self, broker_ip: str, broker_port: int = 1883,
                   topic_commands: str = "COMAU/commands", 
                   topic_keyboard: str = "COMAU/toRobot",
                   topic_responses: str = "COMAU/memoryData",
                   connect_on_start: bool = True) -> bool:
        """
        Guarda la configuración MQTT en el archivo JSON.
        
        Args:
            broker_ip: Dirección IP del broker MQTT
            broker_port: Puerto del broker (default: 1883)
            topic_commands: Topic para recibir comandos
            topic_keyboard: Topic para emular teclado
            topic_responses: Topic para enviar respuestas
        
        Returns:
            True si se guardó correctamente, False en caso contrario
        """
        try:
            # Cargar configuración existente
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except FileNotFoundError:
                config = {}
            
            # Actualizar sección MQTT
            config['mqtt'] = {
                'broker_ip': broker_ip,
                'broker_port': broker_port,
                'topics': {
                    'commands': topic_commands,
                    'keyboard': topic_keyboard,
                    'responses': topic_responses
                },
                'connect_on_start': connect_on_start
            }
            
            # Guardar
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # Actualizar variables internas
            self.broker_ip = broker_ip
            self.broker_port = broker_port
            self.topic_commands = topic_commands
            self.topic_keyboard = topic_keyboard
            self.topic_responses = topic_responses
            self.connect_on_start = connect_on_start
            
            self.logger.info(f"Configuración MQTT guardada: {broker_ip}:{broker_port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error guardando configuración MQTT: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """
        Obtiene la configuración MQTT actual.
        
        Returns:
            Diccionario con la configuración
        """
        return {
            'broker_ip': self.broker_ip,
            'broker_port': self.broker_port,
            'topics': {
                'commands': self.topic_commands,
                'keyboard': self.topic_keyboard,
                'responses': self.topic_responses
            },
            'connect_on_start': self.connect_on_start,
            'connected': self.connected,
            'state': self.state.value
        }
    
    # ========================================================================
    # CALLBACKS MQTT (ejecutados por el thread de paho-mqtt)
    # ========================================================================
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback interno cuando se establece conexión."""
        if rc == 0:
            self._set_state(MQTTState.CONNECTED)
            self.logger.info(f"Conectado al broker MQTT: {self.broker_ip}:{self.broker_port}")
            
            # Auto-suscripción a los topics necesarios
            try:
                # Suscribirse al topic de comandos (QoS 2 para garantizar entrega)
                client.subscribe(self.topic_commands, qos=2)
                self.logger.info(f"Suscrito a topic de comandos: {self.topic_commands}")
                
                # Suscribirse al topic de teclado (QoS 2 para garantizar entrega)
                client.subscribe(self.topic_keyboard, qos=2)
                self.logger.info(f"Suscrito a topic de teclado: {self.topic_keyboard}")
                
                # Suscribirse al topic de respuestas (QoS 2 para garantizar entrega)
                client.subscribe(self.topic_responses, qos=2)
                self.logger.info(f"Suscrito a topic de respuestas: {self.topic_responses}")
            except Exception as e:
                self.logger.error(f"Error suscribiéndose a topics: {e}")
            
            # Callback personalizado
            if self.on_connect_callback:
                try:
                    self.on_connect_callback(client, userdata, flags, rc)
                except Exception as e:
                    self.logger.error(f"Error en callback on_connect: {e}")
        else:
            self._set_state(MQTTState.ERROR)
            error_messages = {
                1: "Protocolo incorrecto",
                2: "ID de cliente inválido",
                3: "Servidor no disponible",
                4: "Usuario o contraseña incorrectos",
                5: "No autorizado"
            }
            error = error_messages.get(rc, f"Error desconocido (código {rc})")
            self.logger.error(f"Error de conexión MQTT: {error}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback interno cuando se pierde la conexión."""
        if self.state != MQTTState.STOPPING:
            if rc != 0:
                self._set_state(MQTTState.ERROR)
                self.logger.warning(f"Desconexión inesperada del broker MQTT (código: {rc})")
            else:
                self._set_state(MQTTState.DISCONNECTED)
                self.logger.info("Desconectado del broker MQTT")
        
        # Callback personalizado
        if self.on_disconnect_callback:
            try:
                self.on_disconnect_callback(client, userdata, rc)
            except Exception as e:
                self.logger.error(f"Error en callback on_disconnect: {e}")
    
    def _on_message(self, client, userdata, msg):
        """Callback interno cuando se recibe un mensaje."""
        try:
            payload = msg.payload.decode('utf-8')
            self.logger.debug(f"Mensaje recibido - Topic: {msg.topic}, Payload: {payload[:100]}")
            
            # Procesar mensajes según el topic
            if msg.topic == self.topic_commands:
                self._process_command_message(payload)
            elif msg.topic == self.topic_keyboard:
                self._process_keyboard_message(payload)
            elif msg.topic == self.topic_responses:
                self._process_response_message(payload)
            
            # Callback personalizado
            if self.on_message_callback:
                self.on_message_callback(client, userdata, msg)
        except Exception as e:
            self.logger.error(f"Error procesando mensaje: {e}")
    
    def _process_command_message(self, payload):
        """Procesa mensajes del topic de comandos."""
        try:
            # Los comandos vienen en formato JSON
            command_data = json.loads(payload)
            command = command_data.get('command')
            self.logger.info(f"Comando recibido: {command}")
            
            # Aquí se pueden agregar más comandos en el futuro
            if command == 'InitWinC5G':
                self.logger.info("Comando InitWinC5G recibido - procesando...")
                
        except json.JSONDecodeError:
            self.logger.warning(f"Comando no es JSON válido: {payload}")
        except Exception as e:
            self.logger.error(f"Error procesando comando: {e}")
    
    def _process_keyboard_message(self, payload):
        """Procesa mensajes del topic de teclado."""
        try:
            # Los mensajes de teclado vienen como texto plano
            self.logger.info(f"Texto de teclado recibido: {payload}")
            
            # Aquí se puede implementar la emulación de teclado
            # Por ahora solo logueamos el mensaje
            
        except Exception as e:
            self.logger.error(f"Error procesando mensaje de teclado: {e}")
    
    def _process_response_message(self, payload):
        """Procesa mensajes del topic de respuestas."""
        try:
            # Las respuestas vienen en formato JSON
            response_data = json.loads(payload)
            status = response_data.get('status')
            command = response_data.get('command')
            request_id = response_data.get('request_id')
            
            self.logger.info(f"Respuesta recibida - Comando: {command}, Status: {status}, ID: {request_id}")
            
            # Almacenar respuesta para comandos pendientes
            if request_id:
                with self._response_lock:
                    self._pending_responses[request_id] = response_data
                self.logger.info(f"Respuesta almacenada para request_id: {request_id}")
            
            # Actualizar estado del icono MQTT basado en la respuesta
            if status == 'success':
                self._update_mqtt_icon_status(True)
                self.logger.info("✓ Comando ejecutado exitosamente")
            elif status == 'error':
                self._update_mqtt_icon_status(False)
                error_msg = response_data.get('error_message', 'Error desconocido')
                self.logger.error(f"✗ Comando falló: {error_msg}")
                
        except json.JSONDecodeError:
            self.logger.warning(f"Respuesta no es JSON válido: {payload}")
        except Exception as e:
            self.logger.error(f"Error procesando respuesta: {e}")
    
    def _update_mqtt_icon_status(self, status):
        """Actualiza el estado del icono MQTT en la interfaz."""
        try:
            # Actualizar variable global del servidor Flask
            try:
                import requests
                requests.post('http://localhost:5000/api/mqtt_icon_status', 
                            json={'status': status}, timeout=1)
            except:
                pass  # Ignorar errores de conexión
            
            # Logging del estado
            if status == 'success':
                self.logger.info("Icono MQTT actualizado a VERDE")
                print("[MQTT] Icono MQTT: VERDE (comando exitoso)")
            elif status == 'error':
                self.logger.info("Icono MQTT actualizado a ROJO")
                print("[MQTT] Icono MQTT: ROJO (error en comando)")
            elif status == 'waiting':
                self.logger.info("Icono MQTT actualizado a NARANJA (parpadeante)")
                print("[MQTT] Icono MQTT: NARANJA (esperando respuesta)")
            # else:
            #     self.logger.info("Icono MQTT actualizado a GRIS")
            #     print("[MQTT] Icono MQTT: GRIS (estado por defecto)")
                
        except Exception as e:
            self.logger.error(f"Error actualizando icono MQTT: {e}")
    
    # ========================================================================
    # THREAD MQTT - Worker principal
    # ========================================================================
    
    def _mqtt_worker(self):
        """
        Worker del thread MQTT.
        Gestiona la conexión usando la máquina de estados.
        """
        self.logger.info("[MQTT Thread] Iniciado")
        print("[MQTT Thread] Iniciado")
        
        try:
            # Verificar que tengamos configuración
            if not self.broker_ip:
                self.logger.error("No hay broker IP configurado")
                self._set_state(MQTTState.ERROR)
                return
            
            # Crear cliente MQTT
            client_id = f"comau_vision_{int(time.time())}"
            self.client = mqtt.Client(client_id=client_id)
            
            # Configurar callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            # Intentar conexión
            self._set_state(MQTTState.CONNECTING)
            self.logger.info(f"Conectando a broker MQTT: {self.broker_ip}:{self.broker_port}")
            
            try:
                self.client.connect(self.broker_ip, self.broker_port, keepalive=60)
            except Exception as e:
                self.logger.error(f"Error al conectar: {e}")
                self._set_state(MQTTState.ERROR)
                return
            
            # Iniciar loop de red (bloqueante)
            # Este loop procesa los mensajes MQTT en este thread
            self.client.loop_start()
            
            # Mantener thread vivo mientras no se detenga
            while not self._stop_flag.is_set():
                time.sleep(0.5)
                
                # Si estamos en ERROR, intentar reconectar
                if self.state == MQTTState.ERROR:
                    self.logger.info("Intentando reconectar...")
                    self._set_state(MQTTState.CONNECTING)
                    try:
                        self.client.reconnect()
                    except Exception as e:
                        self.logger.error(f"Error en reconexión: {e}")
                        time.sleep(5)  # Esperar antes de reintentar
            
            # Detener loop y desconectar
            self._set_state(MQTTState.STOPPING)
            self.client.loop_stop()
            self.client.disconnect()
            self._set_state(MQTTState.DISCONNECTED)
            
        except Exception as e:
            self.logger.error(f"Error en MQTT worker: {e}")
            self._set_state(MQTTState.ERROR)
        
        finally:
            self.logger.info("[MQTT Thread] Detenido")
            print("[MQTT Thread] Detenido")
    
    # ========================================================================
    # API PÚBLICA - Control del thread
    # ========================================================================
    
    def start(self) -> bool:
        """
        Inicia el thread MQTT.
        
        Returns:
            True si se inició correctamente, False si ya estaba corriendo o falló
        """
        if not MQTT_AVAILABLE:
            self.logger.error("Librería paho-mqtt no disponible")
            return False
        
        if self.is_running:
            self.logger.warning("Thread MQTT ya está corriendo")
            return False
        
        if not self.broker_ip:
            self.logger.error("No hay broker IP configurado")
            return False
        
        # Resetear flag de stop
        self._stop_flag.clear()
        
        # Crear e iniciar thread
        self._mqtt_thread = threading.Thread(
            target=self._mqtt_worker,
            name="MQTTWorker",
            daemon=True
        )
        self._mqtt_thread.start()
        
        self.logger.info("Thread MQTT iniciado")
        return True
    
    def stop(self, timeout: float = 5.0):
        """
        Detiene el thread MQTT de forma ordenada.
        
        Args:
            timeout: Tiempo máximo de espera en segundos
        """
        if not self.is_running:
            self.logger.warning("Thread MQTT no está corriendo")
            return
        
        self.logger.info("Deteniendo thread MQTT...")
        self._stop_flag.set()
        
        # Esperar a que termine
        if self._mqtt_thread:
            self._mqtt_thread.join(timeout=timeout)
            
            if self._mqtt_thread.is_alive():
                self.logger.warning("Thread MQTT no terminó en el timeout especificado")
            else:
                self.logger.info("Thread MQTT detenido correctamente")
    
    def connect(self, broker_ip: Optional[str] = None, broker_port: Optional[int] = None) -> bool:
        """
        DEPRECADO: Usa start() en su lugar.
        Conecta al broker MQTT usando el thread dedicado.
        
        Args:
            broker_ip: Dirección IP del broker (usa la configuración si es None)
            broker_port: Puerto del broker (usa la configuración si es None)
        
        Returns:
            True si se inició correctamente
        """
        # Actualizar configuración si se proporcionó
        if broker_ip:
            self.broker_ip = broker_ip
        if broker_port:
            self.broker_port = broker_port
        
        return self.start()
    
    def disconnect(self):
        """
        DEPRECADO: Usa stop() en su lugar.
        Desconecta del broker MQTT.
        """
        self.stop()
    
    def publish(self, topic: str, payload: Any, qos: int = 2, retain: bool = False) -> bool:
        """
        Publica un mensaje en un topic.
        
        Args:
            topic: Topic MQTT donde publicar
            payload: Datos a publicar (puede ser string, dict, etc.)
            qos: Calidad de servicio (0, 1 o 2) - default 2 para garantizar entrega
            retain: Si el broker debe retener el mensaje
        
        Returns:
            True si se publicó correctamente, False en caso contrario
        """
        if not self.connected or not self.client:
            self.logger.error("No hay conexión MQTT activa")
            return False
        
        try:
            # Convertir payload a string si es necesario
            if isinstance(payload, dict):
                payload = json.dumps(payload, ensure_ascii=False)
            elif not isinstance(payload, (str, bytes)):
                payload = str(payload)
            
            result = self.client.publish(topic, payload, qos=qos, retain=retain)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.debug(f"Mensaje publicado en '{topic}' con QoS {qos}")
                return True
            else:
                self.logger.error(f"Error publicando mensaje (código: {result.rc})")
                return False
                
        except Exception as e:
            self.logger.error(f"Error al publicar mensaje: {e}")
            return False
    
    def subscribe(self, topic: str, qos: int = 2) -> bool:
        """
        Se suscribe a un topic.
        
        Args:
            topic: Topic MQTT al que suscribirse
            qos: Calidad de servicio (0, 1 o 2) - default 2 para garantizar entrega
        
        Returns:
            True si se suscribió correctamente, False en caso contrario
        """
        if not self.connected or not self.client:
            self.logger.error("No hay conexión MQTT activa")
            return False
        
        try:
            result = self.client.subscribe(topic, qos=qos)
            
            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                self.logger.info(f"Suscrito al topic '{topic}' con QoS {qos}")
                return True
            else:
                self.logger.error(f"Error suscribiéndose al topic (código: {result[0]})")
                return False
                
        except Exception as e:
            self.logger.error(f"Error al suscribirse: {e}")
            return False
    
    def unsubscribe(self, topic: str) -> bool:
        """
        Se desuscribe de un topic.
        
        Args:
            topic: Topic del que desuscribirse
        
        Returns:
            True si se desuscribió correctamente, False en caso contrario
        """
        if not self.connected or not self.client:
            self.logger.error("No hay conexión MQTT activa")
            return False
        
        try:
            result = self.client.unsubscribe(topic)
            
            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                self.logger.info(f"Desuscrito del topic '{topic}'")
                return True
            else:
                self.logger.error(f"Error desuscribiéndose (código: {result[0]})")
                return False
                
        except Exception as e:
            self.logger.error(f"Error al desuscribirse: {e}")
            return False
    
    def test_connection(self, broker_ip: str, broker_port: int = 1883,
                       timeout: int = 5) -> tuple[bool, str]:
        """
        Prueba la conexión con un broker MQTT sin mantener la conexión.
        
        Args:
            broker_ip: Dirección IP del broker
            broker_port: Puerto del broker
            timeout: Tiempo máximo de espera en segundos
        
        Returns:
            Tupla (éxito, mensaje)
        """
        if not MQTT_AVAILABLE:
            return False, "Librería paho-mqtt no disponible"
        
        test_client = None
        connection_result = [False, "Timeout"]
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                connection_result[0] = True
                connection_result[1] = "Conexión exitosa"
            else:
                error_messages = {
                    1: "Protocolo incorrecto",
                    2: "ID de cliente inválido",
                    3: "Servidor no disponible",
                    4: "Usuario o contraseña incorrectos",
                    5: "No autorizado"
                }
                connection_result[1] = error_messages.get(rc, f"Error desconocido (código {rc})")
        
        try:
            client_id = f"comau_test_{int(time.time())}"
            test_client = mqtt.Client(client_id=client_id)
            test_client.on_connect = on_connect
            
            test_client.connect(broker_ip, broker_port, keepalive=60)
            test_client.loop_start()
            
            # Esperar resultado
            start_time = time.time()
            while time.time() - start_time < timeout:
                if connection_result[0] or connection_result[1] != "Timeout":
                    break
                time.sleep(0.1)
            
            test_client.loop_stop()
            test_client.disconnect()
            
            return connection_result[0], connection_result[1]
            
        except Exception as e:
            if test_client:
                try:
                    test_client.loop_stop()
                    test_client.disconnect()
                except:
                    pass
            return False, f"Error: {str(e)}"
    
    def wait_for_response(self, request_id: str, timeout: int = 30) -> dict:
        """
        Espera la respuesta de un comando específico.
        
        Args:
            request_id: ID del comando enviado
            timeout: Tiempo máximo de espera en segundos
        
        Returns:
            Diccionario con la respuesta o None si timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self._response_lock:
                if request_id in self._pending_responses:
                    response = self._pending_responses.pop(request_id)
                    self.logger.info(f"Respuesta encontrada para {request_id}")
                    return response
            
            time.sleep(0.1)  # Esperar 100ms antes de verificar nuevamente
        
        self.logger.warning(f"Timeout esperando respuesta para {request_id}")
        return None
    
    def send_command_and_wait(self, command_data: dict, timeout: int = 30) -> dict:
        """
        Envía un comando y espera la respuesta.
        
        Args:
            command_data: Diccionario con el comando a enviar
            timeout: Tiempo máximo de espera en segundos
        
        Returns:
            Diccionario con la respuesta o None si error/timeout
        """
        if not self.connected or not self.client:
            self.logger.error("No hay conexión MQTT activa")
            return None
        
        request_id = command_data.get('request_id')
        if not request_id:
            self.logger.error("Comando sin request_id")
            return None
        
        # Actualizar icono a naranja parpadeante (esperando respuesta)
        if command_data.get('command') == 'InitWinC5G':
            self._update_mqtt_icon_status('waiting')
        
        # Enviar comando
        success = self.publish(self.topic_commands, command_data, qos=2)
        if not success:
            self.logger.error("Error enviando comando")
            return None
        
        self.logger.info(f"Comando enviado, esperando respuesta para {request_id}...")
        
        # Esperar respuesta
        response = self.wait_for_response(request_id, timeout)
        
        # Actualizar icono según la respuesta
        if command_data.get('command') == 'InitWinC5G':
            if response:
                if response.get('status') == 'success':
                    self._update_mqtt_icon_status('success')
                    # El icono se mantiene verde cuando el sistema está funcionando
                    # Solo volver a gris si hay un error posterior
                else:
                    self._update_mqtt_icon_status('error')
                    # Volver a gris después de 5 segundos si hay error
                    threading.Timer(5.0, lambda: self._update_mqtt_icon_status('default')).start()
            else:
                self._update_mqtt_icon_status('error')
                # Volver a gris después de 5 segundos si hay timeout
                threading.Timer(5.0, lambda: self._update_mqtt_icon_status('default')).start()
        
        return response


# Instancia global (singleton)
_mqtt_manager_instance: Optional[MQTTManager] = None


def get_mqtt_manager() -> MQTTManager:
    """
    Obtiene la instancia global del MQTTManager (patrón singleton).
    
    Returns:
        Instancia de MQTTManager
    """
    global _mqtt_manager_instance
    if _mqtt_manager_instance is None:
        _mqtt_manager_instance = MQTTManager()
    else:
        # Verificar que la instancia tenga el logger inicializado
        if not hasattr(_mqtt_manager_instance, 'logger'):
            _mqtt_manager_instance = MQTTManager()
    return _mqtt_manager_instance

