import pandas as pd
import logging
import json
import os
import requests
import datetime
import ccxt
import uuid  # Import the uuid module
import time
from config import EXCHANGE, SYMBOL, RISK_PER_TRADE, SYMBOL_SPOT, ACCOUNT_TYPE, MARGIN_TYPE, BASE_URL_FUTURES, ARTIFICIAL_BALANCE
from kucoin_requests import KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE
from kucoin_requests import get_kucoin_headers, get_base_url

def log_account_type(account_type):
    if account_type == 'futures':
        logging.info("Operando en cuenta de futuros.")
    else:
        logging.info("Operando en cuenta spot.")

def get_market_data(symbol=SYMBOL, timeframe='1h', limit=200):
    try:
        logging.info(f"Fetching market data for {symbol} with timeframe {timeframe} and limit {limit}")
        ohlcv = EXCHANGE.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        logging.info(f"Market data fetched for {symbol}: {df.head()}")

        # Convertir los timestamps a cadenas de texto
        df['timestamp'] = df['timestamp'].astype(str)

        # Convertir DataFrame a lista de diccionarios
        data = df.to_dict(orient='records')

        return df
    except Exception as e:
        logging.error(f"Error fetching market data for {symbol}: {e}")
        return None

def log_operation(operation):
    log_file_path = '/Volumes/morespace/trading_bot_ui/operation_logs.json'
    logs = []
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r') as f:
            logs = json.load(f)
    logs.append(operation)
    with open(log_file_path, 'w') as f:
        json.dump(logs, f)

# Ejemplo de cómo usar log_operation en tu bot
def execute_trade(symbol, amount, side):
    try:
        order = EXCHANGE.create_order(symbol, 'market', side, amount)
        logging.info(f"Order executed: {order}")
        log_operation({
            'timestamp': datetime.datetime.now().isoformat(),
            'symbol': symbol,
            'amount': amount,
            'side': side,
            'order': order
        })
    except Exception as e:
        logging.error(f"Error executing trade: {e}")
        log_operation({
            'timestamp': datetime.datetime.now().isoformat(),
            'symbol': symbol,
            'amount': amount,
            'side': side,
            'error': str(e)
        })
        
        
def get_account_balance(use_artificial=True):
    try:
        logging.info("Fetching account balance")
        if use_artificial:
            logging.info("Using artificial balance.")
            return ARTIFICIAL_BALANCE
        balance = EXCHANGE.fetch_balance()
        if balance:
            logging.info("Account balance fetched successfully.")
            filtered_balance = {"USDT": balance['total'].get("USDT", 0)}
            logging.info(f"Filtered account balance: {filtered_balance}")
            return filtered_balance
        else:
            logging.error("No se pudo obtener el balance de la cuenta.")
            return {}
    except Exception as e:
        logging.error(f"Error fetching account balance: {e}")
        return {}

    
def update_artificial_balance(order_response, side):
    try:
        global ARTIFICIAL_BALANCE
        order = order_response['data']
        if side == 'buy':
            ARTIFICIAL_BALANCE['USDT'] -= float(order['size']) * float(order['price'])
        elif side == 'sell':
            ARTIFICIAL_BALANCE['USDT'] += float(order['size']) * float(order['price'])
        logging.info(f"Updated artificial balance: {ARTIFICIAL_BALANCE}")
    except Exception as e:
        logging.error(f"Error updating artificial balance: {e}")    

def get_increment(symbol):
    try:
        url = "https://api.kucoin.com/api/v1/symbols"
        response = requests.get(url)
        if response.status_code == 200:
            symbols_info = response.json()
            for s in symbols_info['data']:
                if s['symbol'] == symbol:
                    return float(s['quoteIncrement'])
        logging.error(f"Symbol {symbol} not found in market information.")
        return None
    except Exception as e:
        logging.error(f"Error fetching increment for {symbol}: {e}")
        return None


def calculate_trade_amount(balance, risk_per_trade):
    try:
        balance_usdt = balance.get('USDT', 0)
        logging.info(f"💰Balance disponible en USDT: {balance_usdt}")
        if balance_usdt > 0:
            trade_amount_usdt = balance_usdt * risk_per_trade
            logging.info(f"Calculando trade amount: {trade_amount_usdt} USDT (balance_usdt * risk_per_trade)")

            current_price = get_current_price(SYMBOL_SPOT)
            if current_price is None:
                logging.error("No se pudo obtener el precio actual para calcular la cantidad de la operación.")
                return None

            trade_amount = trade_amount_usdt / current_price
            logging.info(f"Trade amount calculado en unidades del activo: {trade_amount} BTC (trade_amount_usdt / current_price)")

            increment = get_increment(SYMBOL_SPOT)
            if increment:
                trade_amount = round(trade_amount // increment * increment, 8)
                logging.info(f"Trade amount ajustado al incremento: {trade_amount} BTC")
                if trade_amount < 0.001:
                    logging.error(f"Trade amount {trade_amount} BTC es menor que el mínimo requerido de 0.001 BTC.")
                    return None
                logging.info(f"Calculated trade amount: {trade_amount} BTC based on balance {balance_usdt} USDT and risk per trade {risk_per_trade}")
                return trade_amount
            else:
                logging.error("No se pudo obtener el incremento para el par de trading.")
                return None
        else:
            logging.error(f"Balance insuficiente para calcular la cantidad de la operación. Balance disponible: {balance_usdt} USDT")
            return None
    except Exception as e:
        logging.error(f"Error calculating trade amount: {e}")
        return None




def place_order(client_oid, symbol, side, order_type, size, price=None, leverage=None):
    base_url = get_base_url()
    endpoint = '/api/v1/margin/order' if ACCOUNT_TYPE == 'margin' else '/api/v1/orders'
    body = {
        'clientOid': client_oid,
        'side': side,
        'symbol': symbol,
        'type': order_type,
        'size': size
    }

    if price:
        body['price'] = price

    if ACCOUNT_TYPE == 'margin' and leverage:
        body['leverage'] = leverage

    headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'POST', endpoint, json.dumps(body))
    
    response = requests.post(base_url + endpoint, headers=headers, json=body)
    return response.json()




def place_order_futures(symbol, order_type, side, amount, price=None, stop_price=None, stop_price_type=None):
    try:
        url = "https://api-futures.kucoin.com/api/v1/orders"
        data = {
            'clientOid': str(uuid.uuid4()),
            'symbol': symbol,
            'type': order_type,
            'side': side,
            'size': str(amount)
        }
        
        if order_type == 'limit' and price is not None:
            data['price'] = str(price)
        
        if stop_price is not None and stop_price_type is not None:
            data['stopPrice'] = str(stop_price)
            data['stopPriceType'] = stop_price_type
            data['stop'] = 'up' if side == 'buy' else 'down'
        body = json.dumps(data)
        headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'POST', '/api/v1/orders', body)
        
        logging.info(f"Headers: {headers}")
        logging.info(f"Sending order data: {data}")
        response = requests.post(url, headers=headers, data=body)
        if response.status_code == 200:
            order = response.json()
            logging.info(f"Orden colocada: {order}")
            return order
        else:
            logging.error(f"Error al colocar la orden: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error al colocar la orden: {e}")
        return None


def cancel_order(order_id):
    try:
        url = f"https://api.kucoin.com/api/v1/orders/{order_id}"
        headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'DELETE', f'/api/v1/orders/{order_id}')
        
        response = requests.delete(url, headers=headers)
        if response.status_code == 200:
            result = response.json()
            logging.info(f"Order cancelled: {result}")
            return result
        else:
            logging.error(f"Failed to cancel order: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error cancelling order: {e}")
        return None

def get_order_status(order_id):
    try:
        url = f"https://api.kucoin.com/api/v1/orders/{order_id}"
        headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'GET', f'/api/v1/orders/{order_id}')
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            order = response.json()
            logging.info(f"Order status fetched: {order}")
            return order
        else:
            logging.error(f"Failed to fetch order status: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error fetching order status: {e}")
        return None


def get_open_orders(symbol):
    try:
        logging.info(f"Revisando si hay órdenes abiertas para {symbol}...")
        url = f"https://api.kucoin.com/api/v1/orders?status=active&symbol={symbol}"
        headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'GET', f'/api/v1/orders?status=active&symbol={symbol}')
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            open_orders = response.json()
            logging.info(f"Órdenes abiertas obtenidas: {open_orders}")
            if 'data' in open_orders and 'items' in open_orders['data']:
                return open_orders['data']['items']
            else:
                logging.error("La respuesta de la API no contiene los campos esperados.")
                return []
        else:
            logging.error(f"Error al obtener las órdenes abiertas: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        logging.error(f"Error al obtener las órdenes abiertas: {e}")
        return []

def get_open_orders_futures(symbol):
    try:
        logging.info(f"Revisando si hay órdenes abiertas para {symbol} en la cuenta de futuros...")
        url = f"https://api-futures.kucoin.com/api/v1/orders?status=active&symbol={symbol}"
        headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'GET', f'/api/v1/orders?status=active&symbol={symbol}')
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            open_orders = response.json()
            logging.info(f"Órdenes abiertas obtenidas: {open_orders}")
            return open_orders['data']
        else:
            logging.error(f"Error al obtener las órdenes abiertas: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error al obtener las órdenes abiertas: {e}")
        return None


def get_current_price(symbol):
    try:
        response = requests.get(f'https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}')
        data = response.json()
        if 'data' in data and 'price' in data['data']:
            current_price = float(data['data']['price'])
            logging.info(f"Precio actual obtenido para {symbol}: {current_price}")
            return current_price
        else:
            logging.error("No se pudo obtener el precio actual del símbolo.")
            return None
    except Exception as e:
        logging.error(f"Error al obtener el precio actual: {e}")
        return None











