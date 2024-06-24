import logging

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

    # Verificar si ya existen handlers para evitar duplicación
    if not logging.getLogger('operations').hasHandlers():
        # Logger adicional para las operaciones y balance
        operations_handler = logging.FileHandler('operations.log')
        operations_handler.setLevel(logging.INFO)
        operations_handler.setFormatter(formatter)
        operations_logger = logging.getLogger('operations')
        operations_logger.addHandler(operations_handler)
        operations_logger.setLevel(logging.INFO)
    
    if __name__ == "__main__":
        setup_logging()
        logging.info("Logging configurado correctamente.")
        print("Logging configurado correctamente.")

