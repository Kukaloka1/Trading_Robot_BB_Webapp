import requests
import logging
from kucoin_signature import get_kucoin_headers
from config import KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, ACCOUNT_TYPE, SYMBOL

def get_base_url():
    return "https://api.kucoin.com"

def get_open_orders_or_positions(symbol, account_type='spot'):
    base_url = get_base_url()
    endpoint = ''
    if account_type == 'spot':
        endpoint = f'/api/v1/accounts'
    elif account_type == 'margin':
        endpoint = f'/api/v1/margin/orders?status=active'
    elif account_type == 'futures':
        endpoint = f'/api/v1/futures/orders?status=active'
    
    headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'GET', endpoint)
    
    logging.info(f"Requesting open orders/positions with endpoint: {base_url + endpoint}")
    logging.info(f"Headers: {headers}")
    
    response = requests.get(base_url + endpoint, headers=headers)
    logging.info(f"Response status code: {response.status_code}")
    logging.info(f"Response content: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        if account_type == 'spot':
            positions = data['data']
            logging.info(f"Posiciones obtenidas: {positions}")
            filtered_positions = [position for position in positions if position['currency'] == symbol.split('-')[0]]
            logging.info(f"Posiciones filtradas por símbolo {symbol}: {filtered_positions}")
            return {'data': {'items': filtered_positions}}
        else:
            orders = data
            logging.info(f"Órdenes abiertas obtenidas: {orders}")
            filtered_orders = [order for order in orders['data']['items'] if order['symbol'] == symbol]
            logging.info(f"Órdenes filtradas por símbolo {symbol}: {filtered_orders}")
            return {'data': {'items': filtered_orders}}
    else:
        logging.error(f"Error al obtener órdenes/posiciones abiertas: {response.text}")
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    symbol = SYMBOL  # Reemplaza con tu símbolo, p.ej. "BTC-USDT"
    account_type = ACCOUNT_TYPE  # Puede ser 'spot', 'margin' o 'futures'
    orders_or_positions = get_open_orders_or_positions(symbol, account_type)
    print(orders_or_positions)






