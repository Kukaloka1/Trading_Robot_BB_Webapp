from dotenv import load_dotenv
import os
import ccxt
import logging

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Configuración del Bot de Trading
SYMBOL_SPOT = os.getenv('SYMBOL_SPOT')
SYMBOL_FUTURES = os.getenv('SYMBOL_FUTURES')
SYMBOL_MARGIN = os.getenv('SYMBOL_MARGIN')  # Añadir símbolo de margen
TIMEFRAME = os.getenv('TIMEFRAME')
LIMIT = int(os.getenv('LIMIT'))
RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE'))
ACCOUNT_TYPE = os.getenv('ACCOUNT_TYPE')
MAX_CAPITAL_USAGE = float(os.getenv('MAX_CAPITAL_USAGE'))
LEVERAGE = int(os.getenv('LEVERAGE'))
MARGIN_TYPE = os.getenv('MARGIN_TYPE')  # Añadir tipo de margen

# Factores de escala para diferentes timeframes
TIMEFRAME_SCALING_FACTORS = {
    '1m': 0.5,
    '5m': 1.0,
    '15m': 1.5,
    '1h': 2.0,
    '4h': 2.5,
    '1d': 3.0,
    '1w': 3.5,
}

# Parámetros para la gestión de trailing stop
TRAILING_STOP_PCT = 0.005  # 0.5%
TAKE_PROFIT_MULTIPLIER = 1.005  # 0.5% Take Profit

print(f"TRAILING_STOP_PCT: {TRAILING_STOP_PCT}")
print(f"TAKE_PROFI_MULTIPLIER: {TAKE_PROFIT_MULTIPLIER}")

# Credenciales de KuCoin desde variables de entorno
KUCOIN_API_KEY = os.getenv('KUCOIN_API_KEY')
KUCOIN_API_SECRET = os.getenv('KUCOIN_API_SECRET')
KUCOIN_API_PASSPHRASE = os.getenv('KUCOIN_API_PASSPHRASE')

# Verificación de la carga de variables
print(f"ACCOUNT_TYPE: {ACCOUNT_TYPE}")
print(f"KUCOIN_API_KEY: {KUCOIN_API_KEY}")
print(f"KUCOIN_API_SECRET: {KUCOIN_API_SECRET}")
print(f"KUCOIN_API_PASSPHRASE: {KUCOIN_API_PASSPHRASE}")

BASE_URL_SPOT = 'https://api.kucoin.com'
BASE_URL_FUTURES = 'https://api-futures.kucoin.com'
BASE_URL_MARGIN = 'https://api.kucoin.com'

# Inicialización del exchange según el tipo de cuenta
try:
    if ACCOUNT_TYPE == 'futures':
        exchange = ccxt.kucoinfutures({
            'apiKey': KUCOIN_API_KEY,
            'secret': KUCOIN_API_SECRET,
            'password': KUCOIN_API_PASSPHRASE,
        })
        symbol = SYMBOL_FUTURES
        print("Futures account initialized.")
    elif ACCOUNT_TYPE == 'margin':
        exchange = ccxt.kucoin({
            'apiKey': KUCOIN_API_KEY,
            'secret': KUCOIN_API_SECRET,
            'password': KUCOIN_API_PASSPHRASE,
            'options': {
                'defaultType': 'margin',
            }
        })
        symbol = SYMBOL_MARGIN
        print("Margin account initialized.")
    else:
        exchange = ccxt.kucoin({
            'apiKey': KUCOIN_API_KEY,
            'secret': KUCOIN_API_SECRET,
            'password': KUCOIN_API_PASSPHRASE,
        })
        symbol = SYMBOL_SPOT
        print("Spot account initialized.")

    exchange.load_markets()
    print("Markets loaded.")

except Exception as e:
    logging.error(f"Error initializing exchange: {e}")
    print(f"Error initializing exchange: {e}")
    raise

# Exportar exchange y symbol para uso en otros módulos
EXCHANGE = exchange
SYMBOL = symbol

# Balance artificial en USDT
ARTIFICIAL_BALANCE = {
    "USDT": 10000
}
# Exportar otras configuraciones
__all__ = ['SYMBOL', 'TIMEFRAME', 'LIMIT', 'RISK_PER_TRADE', 'EXCHANGE', 'ACCOUNT_TYPE', 'MAX_CAPITAL_USAGE', 'LEVERAGE']
