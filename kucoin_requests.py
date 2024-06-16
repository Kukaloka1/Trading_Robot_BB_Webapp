import requests
import json
import logging
from kucoin_signature import get_kucoin_headers
from config import KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, ACCOUNT_TYPE, MARGIN_TYPE

BASE_URL_SPOT = 'https://api.kucoin.com'
BASE_URL_FUTURES = 'https://api-futures.kucoin.com'
BASE_URL_MARGIN = 'https://api.kucoin.com'

def get_base_url():
    if ACCOUNT_TYPE == 'futures':
        return BASE_URL_FUTURES
    elif ACCOUNT_TYPE == 'margin':
        return BASE_URL_MARGIN
    return BASE_URL_SPOT

def get_market_data(symbol, timeframe='1hour'):
    base_url = get_base_url()
    endpoint = f'/api/v1/market/candles?type={timeframe}&symbol={symbol}'
    headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'GET', endpoint)
    
    response = requests.get(base_url + endpoint, headers=headers)
    return response.json()

def get_account_balance():
    base_url = get_base_url()
    endpoint = '/api/v1/margin/account' if ACCOUNT_TYPE == 'margin' else '/api/v1/accounts'
    headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'GET', endpoint)
    
    response = requests.get(base_url + endpoint, headers=headers)
    return response.json()

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
    
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Error al colocar la orden: {response.json()}")
        return None


def cancel_order(order_id, symbol):
    base_url = get_base_url()
    endpoint = f'/api/v1/orders/{order_id}'
    headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'DELETE', endpoint)
    
    response = requests.delete(base_url + endpoint, headers=headers)
    return response.json()

def get_order_status(order_id, symbol):
    base_url = get_base_url()
    endpoint = f'/api/v1/orders/{order_id}'
    headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'GET', endpoint)
    
    response = requests.get(base_url + endpoint, headers=headers)
    return response.json()

def get_open_orders(symbol):
    base_url = get_base_url()
    endpoint = f'/api/v1/orders?status=active&symbol={symbol}'
    headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'GET', endpoint)
    
    response = requests.get(base_url + endpoint, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Error al obtener órdenes abiertas: {response.text}")
        return None


def get_open_orders_futures(symbol):
    base_url = get_base_url()
    endpoint = f'/api/v1/orders?status=active&symbol={symbol}'
    headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'GET', endpoint)
    
    response = requests.get(base_url + endpoint, headers=headers)
    return response.json()

def get_open_orders_margin(symbol):
    base_url = get_base_url()
    endpoint = f'/api/v1/margin/order?status=active&symbol={symbol}' if MARGIN_TYPE == 'cross' else f'/api/v1/isolated/order?status=active&symbol={symbol}'
    headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'GET', endpoint)
    
    response = requests.get(base_url + endpoint, headers=headers)
    return response.json()









