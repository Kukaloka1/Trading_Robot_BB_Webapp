import asyncio
import websockets
import json
import logging
from collections import deque

# Configuración del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Buffer para almacenar mensajes de log
log_buffer = deque(maxlen=100)  # Limitar el tamaño del buffer a 100

def add_log_message(message):
    log_buffer.append(message)

class ExcludeWebSocketFilter(logging.Filter):
    def filter(self, record):
        # Filtrar solo los mensajes de conexión WebSocket
        return not (
            'connection closed' in record.getMessage() or
            'Nueva conexión WebSocket establecida' in record.getMessage() or
            'Conexión WebSocket cerrada' in record.getMessage() or
            'connection open' in record.getMessage() or
            'Conexión WebSocket finalizada' in record.getMessage()
        )

async def send_logs(websocket, path):
    logging.info("Nueva conexión WebSocket establecida")
    try:
        while True:
            if log_buffer:
                log_message = log_buffer.popleft()
                await websocket.send(json.dumps({"message": log_message}))
                logging.debug(f"Mensaje enviado: {log_message}")
            await asyncio.sleep(1)  # Verifica el buffer cada segundo
    except websockets.exceptions.ConnectionClosed as e:
        logging.info(f"Conexión WebSocket cerrada: {e}")
    except Exception as e:
        logging.error(f"Error en el envío del mensaje de log: {e}")
    finally:
        logging.info("Conexión WebSocket finalizada")

async def start_server():
    logging.info("Iniciando servidor WebSocket en ws://localhost:8765")
    server = await websockets.serve(send_logs, "localhost", 8765)
    logging.info("Servidor WebSocket iniciado y esperando conexiones")
    await server.wait_closed()

def run_server():
    # Aplicar el filtro personalizado
    exclude_websocket_filter = ExcludeWebSocketFilter()
    for handler in logging.getLogger('').handlers:
        handler.addFilter(exclude_websocket_filter)

    asyncio.run(start_server())

if __name__ == "__main__":
    run_server()









