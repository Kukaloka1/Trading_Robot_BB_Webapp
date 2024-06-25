import logging
import json
import asyncio
import websockets
from collections import deque

class ExcludeWebSocketFilter(logging.Filter):
    def filter(self, record):
        return not (
            'connection closed' in record.getMessage()
        )

def setup_logging():
    logging.basicConfig(
        filename='trading_bot.log',  # Nombre del archivo de log principal
        level=logging.INFO,  # Nivel de logging
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Formato del log
        datefmt='%Y-%m-%d %H:%M:%S'  # Formato de fecha
    )
    console = logging.StreamHandler()  # Crear un handler para la consola
    console.setLevel(logging.INFO)  # Establecer el nivel de logging para la consola
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')  # Formato del log para la consola
    console.setFormatter(formatter)  # Asignar el formato al handler de la consola
    logging.getLogger('').addHandler(console)  # Agregar el handler de la consola al logger global

    # Crear el filtro personalizado
    exclude_websocket_filter = ExcludeWebSocketFilter()

    # Agregar el filtro a todos los handlers
    for handler in logging.getLogger('').handlers:
        handler.addFilter(exclude_websocket_filter)

    # Verificar si ya existen handlers para evitar duplicación
    if not logging.getLogger('operations').hasHandlers():
        # Logger adicional para las operaciones y balance
        operations_handler = logging.FileHandler('operations.log')
        operations_handler.setLevel(logging.INFO)
        operations_handler.setFormatter(formatter)
        operations_logger = logging.getLogger('operations')
        operations_logger.addHandler(operations_handler)
        operations_logger.setLevel(logging.INFO)

def add_operation(self, operation):
    existing_order = next((op for op in self.operations if op['orderId'] == operation['orderId']), None)
    if existing_order:
        existing_order.update(operation)
    else:
        self.operations.append(operation)

    # Actualiza el balance en la operación
    if operation['side'] == 'buy':
        self.balance['available_balance'] -= operation['size'] * operation['price']
        self.balance['total_committed'] += operation['size'] * operation['price']
    elif operation['side'] == 'sell':
        self.balance['available_balance'] += operation['size'] * operation['price']
        self.balance['total_committed'] -= operation['size'] * operation['price']

    operation['balance'] = self.balance.copy()

    self.save_operations()
    logging.info(f"Operation added/updated: {operation}")
    self.operations_logger.info(f"Operation: {operation}")


def format_operations_log(file_path='operations.json'):
    try:
        with open(file_path, 'r') as f:
            operations = json.load(f)
        
        formatted_logs = []
        for i, operation in enumerate(operations, 1):
            log_entry = (
                f"{i}. ID: {operation.get('orderId')}, "
                f"Tipo: {operation.get('type')}, "
                f"Lado: {operation.get('side')}, "
                f"Tamaño: {operation.get('size')}, "
                f"Precio: {operation.get('price')}, "
                f"Estado: {operation.get('status')}, "
                f"Fecha: {operation.get('timestamp')}, "
                f"Balance: {operation.get('balance')}"
            )
            formatted_logs.append(log_entry)
        
        with open(file_path, 'w') as f:
            json.dump(formatted_logs, f, indent=4)
        
        logging.info(f"Operaciones formateadas y guardadas en {file_path}")
    except Exception as e:
        logging.error(f"Error al formatear los logs de operaciones: {e}")

# WebSocket Server Code
log_buffer = deque(maxlen=100)  # Limitar el tamaño del buffer a 100

def add_log_message(message):
    log_buffer.append(message)

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
        add_log_message("WebSocket connection closed")
    except Exception as e:
        logging.error(f"Error en el envío del mensaje de log: {e}")
    finally:
        logging.info("Conexión WebSocket finalizada")
        add_log_message("WebSocket connection finalized")

async def start_server():
    logging.info("Iniciando servidor WebSocket en ws://localhost:8765")
    server = await websockets.serve(send_logs, "localhost", 8765)
    logging.info("Servidor WebSocket iniciado y esperando conexiones")
    await server.wait_closed()

def run_server():
    asyncio.run(start_server())

if __name__ == "__main__":
    setup_logging()
    logging.info("Logging configurado correctamente.")
    print("Logging configurado correctamente.")
    run_server()

