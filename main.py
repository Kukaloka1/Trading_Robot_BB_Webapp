import time
import requests
import asyncio
import websockets
import datetime
import json
import uuid
import sys
import logging
import threading
from utils.logging_setup import setup_logging
from data.data_fetcher import get_market_data, get_account_balance, calculate_trade_amount, place_order, get_open_orders, get_open_orders_futures, get_current_price, update_artificial_balance
from indicators.technical_indicators import calculate_indicators
from config import SYMBOL, ACCOUNT_TYPE, TIMEFRAME, LIMIT, RISK_PER_TRADE, SYMBOL_SPOT, EXCHANGE, MAX_CAPITAL_USAGE, SYMBOL_FUTURES, LEVERAGE, SYMBOL_MARGIN, MARGIN_TYPE, ARTIFICIAL_BALANCE
from utils.gpt4_integration import get_gpt4_recommendation, prepare_historical_data
from strategies.trading_strategy import manage_position_with_trail_stop, confirm_entry_with_gpt
from kucoin_signature import get_kucoin_headers
from config import KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE
from kucoin_requests import BASE_URL_FUTURES, get_open_orders_margin, BASE_URL_MARGIN
from stream_trading.stream_logs import run_server, add_log_message
from balance_manager import BalanceManager
from config import INITIAL_BALANCE

print("💰โค้ดนี้จะทำให้ฉันเป็นเศรษฐี, สำเร็จแล้ว ด้วยความช่วยเหลือจาก AI💰")

class BufferHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        add_log_message(log_entry)

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    buffer_handler = BufferHandler()
    logging.getLogger().addHandler(buffer_handler)

def set_leverage(symbol, leverage, margin_type=None):
    try:
        if ACCOUNT_TYPE == 'futures':
            endpoint = f'/api/v1/position?symbol={symbol}&leverage={leverage}'
            base_url = BASE_URL_FUTURES
        elif ACCOUNT_TYPE == 'margin':
            if margin_type == 'cross':
                endpoint = f'/api/v1/margin/leverage?symbol={symbol}&leverage={leverage}'
            elif margin_type == 'isolated':
                endpoint = f'/api/v1/isolated/leverage?symbol={symbol}&leverage={leverage}'
            base_url = BASE_URL_MARGIN
        else:
            logging.error("La configuración de apalancamiento solo es aplicable a cuentas de futuros o margen.")
            return

        headers = get_kucoin_headers(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, 'POST', endpoint)
        response = requests.post(base_url + endpoint, headers=headers)

        if response.status_code == 200:
            logging.info(f"Apalancamiento configurado a {leverage}x para {symbol}")
        else:
            logging.error(f"Error al configurar el apalancamiento: {response.text}")
            response.raise_for_status()
    except Exception as e:
        logging.error(f"Error crítico al configurar el apalancamiento: {e}")

def log_indicators(df):
    while True:
        try:
            latest_data = df.iloc[-1]
            logging.info(f"Indicadores en {latest_data['timestamp']}: RSI: {latest_data['RSI']}, MACD: {latest_data['MACD']}, MACD Signal: {latest_data['MACDSignal']}, SMA50: {latest_data['SMA50']}, GPT-4 Sentiment: {latest_data.get('GPT4_Sentiment', 'N/A')}, GPT-4 Risk Assessment: {latest_data.get('GPT4_RiskAssessment', 'N/A')}")
        except Exception as e:
            logging.error(f"Error al registrar indicadores: {e}")
        time.sleep(600)  # Esperar 10 minutos

def log_order_details(order_response, balance):
    try:
        order = order_response['data']
        logging.info(f"Detalles de la orden: ID {order['orderId']}, Tamaño {order['size']}, Precio {order['price']}, Balance {balance}")
    except Exception as e:
        logging.error(f"Error registrando los detalles de la orden: {e}")

def place_order_with_logging(symbol, order_type, side, amount):
    try:
        client_oid = str(uuid.uuid4())
        current_price = get_current_price(symbol)

        if current_price is None:
            logging.error("No se pudo obtener el precio actual para el símbolo.")
            return

        cost = amount * current_price

        logging.info(f"Intentando colocar orden: {side} {amount} unidades en {symbol} a {current_price} cada una (Costo: {cost} USDT).")
        logging.info(f"Balance actual: {balance_manager.get_balance()['USDT']}, Balance comprometido: {balance_manager.committed_balance}")

        if not balance_manager.can_trade(amount, current_price, side):
            logging.error("Balance insuficiente para realizar la orden.")
            return

        balance_manager.commit_balance(amount, current_price)

        order_response = place_order(client_oid, symbol, side, order_type, amount)
        if order_response and order_response.get('code') == '200000':
            logging.info(f"Orden de {side} colocada por {amount} unidades en {symbol}.")
            balance_manager.update_balance(amount, current_price, side)
            order_id = order_response['data']['orderId']  # Establecer order_id
            operation = {
                'orderId': order_id,
                'size': amount,
                'price': current_price,
                'side': side,
                'type': order_type,
                'status': 'open',
                'timestamp': str(datetime.datetime.now()),
                'balance': balance_manager.get_balance()
            }
            balance_manager.add_operation(operation)
            logging.info(f"Detalles de la orden: ID {order_id}, Tamaño {amount}, Precio {current_price}")
        else:
            logging.error(f"Error al colocar la orden: {order_response}")
            balance_manager.release_committed_balance(amount, current_price)

            # Crear una orden ficticia si hay un error (como balance insuficiente)
            order_id = client_oid
            operation = {
                'orderId': order_id,
                'size': amount,
                'price': current_price,
                'side': side,
                'type': order_type,
                'status': 'fictitious',
                'timestamp': str(datetime.datetime.now()),
                'balance': balance_manager.get_balance()
            }
            balance_manager.add_operation(operation)
            logging.info(f"Orden ficticia de {side} creada: ID {order_id}, Tamaño {amount}, Precio {current_price}")
    except Exception as e:
        logging.error(f"Error al colocar la orden: {e}")
        balance_manager.release_committed_balance(amount, current_price)

def trigger_manual_order(side, amount):
    symbol = SYMBOL
    order_type = 'market'
    logging.info(f"Balance antes de la orden: {balance_manager.get_balance()}")
    place_order_with_logging(symbol, order_type, side, amount)
    logging.info(f"Balance después de la orden: {balance_manager.get_balance()}")

def check_trade_conditions(df, account_balance):
    try:
        latest_data = df.iloc[-1]
        indicators = {
            'gpt4_sentiment': latest_data['GPT4_Sentiment'],
            'gpt4_risk': latest_data['GPT4_RiskAssessment'],
            'rsi': latest_data['RSI'],
            'macd': latest_data['MACD'],
            'macd_signal': latest_data['MACDSignal'],
            'sma50': latest_data['SMA50'],
            'close_price': latest_data['close'],
            'pin_bar': latest_data['PinBar'],
            'bullish_engulfing': latest_data['BullishEngulfing'],
            'bearish_engulfing': latest_data['BearishEngulfing']
        }

        logging.info("Evaluando condiciones de trading: %s", indicators)
        buy_condition = (
            (indicators['gpt4_sentiment'] == 'positive' and 
             indicators['gpt4_risk'] == 'low' and 
             indicators['rsi'] < 30 and 
             indicators['macd'] > indicators['macd_signal'] and 
             indicators['close_price'] > indicators['sma50']) or
            indicators['bullish_engulfing'] or
            indicators['pin_bar']
        )
        sell_condition = (
            (ACCOUNT_TYPE == 'futures' and 
             indicators['gpt4_sentiment'] == 'negative' and 
             indicators['gpt4_risk'] == 'high' and 
             indicators['rsi'] > 70 and 
             indicators['macd'] < indicators['macd_signal'] and 
             indicators['close_price'] < indicators['sma50']) or
            indicators['bearish_engulfing']
        )

        if buy_condition or sell_condition:
            used_capital_percentage = (ARTIFICIAL_BALANCE['USDT'] - account_balance['USDT']) / ARTIFICIAL_BALANCE['USDT']
            if used_capital_percentage <= MAX_CAPITAL_USAGE:
                if buy_condition:
                    logging.info("Condiciones de compra detectadas.")
                    return 'buy'
                elif sell_condition:
                    logging.info("Condiciones de venta detectadas.")
                    return 'sell'
            else:
                logging.warning(f"Uso de capital máximo alcanzado: {used_capital_percentage:.2%} de {MAX_CAPITAL_USAGE:.2%}")
        else:
            logging.info("No se cumplen las condiciones para comprar o vender.")
            return None
    except Exception as e:
        logging.error(f"Error al evaluar las condiciones de trading: {e}")
        return None

def check_capital_usage(balance, position_size, max_usage):
    total_balance = balance['total'].get('USDT', 0)
    used_balance = balance['used'].get('USDT', 0)
    available_balance = balance['free'].get('USDT', 0)
    
    used_percentage = (used_balance + position_size) / total_balance
    
    logging.info(f"Capital utilizado: {used_percentage * 100:.2f}% del balance total")
    
    if used_percentage > max_usage:
        logging.warning(f"Capital utilizado excede el {max_usage * 100:.2f}% del balance total. Deteniendo operaciones.")
        return False
    return True

async def send_signal(signal):
    try:
        async with websockets.connect("ws://localhost:8765") as websocket:
            message = json.dumps({"type": "signal", "action": signal})
            await websocket.send(message)
            logging.info(f"Señal enviada: {message}")
            add_log_message(f"Señal enviada: {message}")
    except Exception as e:
        logging.error(f"Error enviando señal: {e}")
        add_log_message(f"Error enviando señal: {e}")

def notify_signal(signal):
    asyncio.run(send_signal(signal))

def run_trading_bot():
    balance_manager.clean_operations()  # Limpiar operaciones fantasma al inicio

    operations_logger = logging.getLogger('operations')
    logging.info("🚀 Bot de trading iniciado. Buscando oportunidades de trading.")

    logging_thread = None
    in_position = False
    entry_price = 0
    stop_loss = 0
    take_profit = 0
    position_size = 0
    order_id = None
    trailing_stop_pct = 0.02

    if ACCOUNT_TYPE == 'futures':
        symbol = SYMBOL_FUTURES
        logging.info("💹 Operando en cuenta de futuros.")
        add_log_message("💹 Operando en cuenta de futuros.")
    elif ACCOUNT_TYPE == 'margin':
        symbol = SYMBOL_MARGIN
        logging.info("💹 Operando en cuenta de margen.")
        add_log_message("💹 Operando en cuenta de margen.")
    else:
        symbol = SYMBOL_SPOT
        logging.info("💹 Operando en cuenta spot.")
        add_log_message("💹 Operando en cuenta spot.")

    # Recuperación de órdenes activas
    active_orders = [order for order in balance_manager.get_operations() if order.get('status') in ['open', 'active']]
    if active_orders:
        for order in active_orders:
            if order['side'] in ['buy', 'sell']:
                operations_logger.info(f"Orden abierta recuperada: ID {order['orderId']}")
                in_position = 'buy' if order['side'] == 'buy' else 'sell'
                entry_price = float(order['price'])
                stop_loss = entry_price * (1 - 0.02) if in_position == 'buy' else entry_price * (1 + 0.02)
                take_profit = entry_price * 1.05 if in_position == 'buy' else entry_price * 0.95
                position_size = float(order['size'])
                order_id = order['orderId']
                current_price = get_current_price(symbol)
                logging.info(f"Recuperada orden {in_position} ID {order_id} con precio de entrada {entry_price}")
                add_log_message(f"Recuperada orden {in_position} ID {order_id} con precio de entrada {entry_price}")
                break
    else:
        logging.info("📭 No hay órdenes abiertas.")
        add_log_message("📭 No hay órdenes abiertas.")

    while True:
        try:
            logging.info("💼 Obteniendo datos del mercado...")
            add_log_message("💼 Obteniendo datos del mercado...")
            df = get_market_data(symbol, TIMEFRAME, LIMIT)
            if df is not None:
                logging.info("📊 Datos del mercado obtenidos.")
                add_log_message("📊 Datos del mercado obtenidos.")
                logging.info("📈 Calculando indicadores técnicos...")
                add_log_message("📈 Calculando indicadores técnicos...")
                df = calculate_indicators(df)
                logging.info("📊 Indicadores técnicos calculados.")
                add_log_message("📊 Indicadores técnicos calculados.")
                if logging_thread is None or not logging_thread.is_alive():
                    logging_thread = threading.Thread(target=log_indicators, args=(df,))
                    logging_thread.start()
                historical_data = prepare_historical_data(df)
                current_price = df['close'].iloc[-1]
                percentage_change_24h = df['close'].pct_change(24).iloc[-1] * 100
                percentage_change_hourly = df['close'].pct_change().iloc[-1] * 100
                trading_volume = df['volume'].iloc[-1]
                logging.info("🧠 Solicitando recomendación a GPT-4...")
                add_log_message("🧠 Solicitando recomendación a GPT-4...")
                gpt4_recommendation = get_gpt4_recommendation(historical_data, current_price, percentage_change_24h, percentage_change_hourly, trading_volume)
                df['GPT4_Sentiment'] = gpt4_recommendation['sentiment']
                df['GPT4_RiskAssessment'] = gpt4_recommendation['risk_assessment']
                logging.info(f"🤖 Recomendación GPT-4: Sentimiento {gpt4_recommendation['sentiment']}, Evaluación de Riesgo {gpt4_recommendation['risk_assessment']}")
                add_log_message(f"🤖 Recomendación GPT-4: Sentimiento {gpt4_recommendation['sentiment']}, Evaluación de Riesgo {gpt4_recommendation['risk_assessment']}")
                logging.info("💼 Obteniendo balance de la cuenta...")
                add_log_message("💼 Obteniendo balance de la cuenta...")
                account_balance = balance_manager.get_balance(current_price=current_price)
                if account_balance:
                    logging.info(f"💰 Balance de la cuenta (USDT): {account_balance['available_balance']}")
                    add_log_message(f"💰 Balance de la cuenta (USDT): {account_balance['available_balance']}")

                    # Añadir logging de posiciones abiertas y porcentaje del capital inicial
                    open_orders = balance_manager.get_operations()
                    open_positions = [order for order in open_orders if order.get('status') == 'open']
                    num_open_positions = len(open_positions)
                    total_invested = sum([order['size'] * order['price'] for order in open_positions])
                    invested_percentage = (total_invested / INITIAL_BALANCE) * 100

                    logging.info(f"📈 Posiciones abiertas: {num_open_positions}, Capital invertido: {invested_percentage:.2f}% del balance inicial")
                    add_log_message(f"📈 Posiciones abiertas: {num_open_positions}, Capital invertido: {invested_percentage:.2f}% del balance inicial")

                    total_balance = account_balance.get('total_balance', 0)
                    if total_balance <= 0:
                        logging.warning("El balance disponible es cero. No se puede realizar ninguna operación.")
                        add_log_message("El balance disponible es cero. No se puede realizar ninguna operación.")
                        time.sleep(300)
                        continue
                    capital_usado = sum([float(order['size']) * float(order['price']) for order in open_orders if order['side'] in ['buy', 'sell']])
                    if capital_usado >= total_balance * MAX_CAPITAL_USAGE:
                        logging.warning(f"Uso de capital máximo alcanzado: {capital_usado} USDT de {total_balance} USDT.")
                        add_log_message(f"Uso de capital máximo alcanzado: {capital_usado} USDT de {total_balance} USDT.")
                    else:
                        if not in_position:
                            action = check_trade_conditions(df, account_balance)
                            if action:
                                in_position = action
                                entry_price = current_price
                                stop_loss = entry_price * (1 - 0.02) if action == 'buy' else entry_price * (1 + 0.02)
                                take_profit = entry_price * 1.05 if action == 'buy' else entry_price * 0.95
                                position_size = calculate_trade_amount(account_balance, RISK_PER_TRADE)
                                if position_size and position_size >= 0.001:
                                    logging.info(f"Posición {action} abierta en {entry_price} con tamaño {position_size}.")
                                    add_log_message(f"Posición {action} abierta en {entry_price} con tamaño {position_size}.")
                                    if ACCOUNT_TYPE == 'spot' and action == 'sell':
                                        logging.info("Venta detectada en mercado spot. No se permite venta en corto.")
                                        add_log_message("Venta detectada en mercado spot. No se permite venta en corto.")
                                    else:
                                        place_order_with_logging(symbol, 'market', action, position_size)
                                        order_id = str(uuid.uuid4())  # Asignar un nuevo ID de orden
                                        operation = {
                                            'orderId': order_id,
                                            'size': position_size,
                                            'price': entry_price,
                                            'side': action,
                                            'type': 'market',
                                            'status': 'open',
                                            'timestamp': str(datetime.datetime.now()),
                                            'balance': account_balance
                                        }
                                        balance_manager.add_operation(operation)
                                        balance_manager.update_balance(position_size, entry_price, action)  # Actualizar balance aquí
                                else:
                                    logging.error(f"Trade amount {position_size} es menor que el mínimo requerido.")
                                    add_log_message(f"Trade amount {position_size} es menor que el mínimo requerido.")
                        else:
                            in_position, stop_loss = manage_position_with_trail_stop(df, -1, in_position, entry_price, stop_loss, take_profit, symbol, position_size, order_id, trailing_stop_pct)
                            if in_position == 'closed':
                                balance_manager.close_operation(order_id)
                                balance_manager.update_balance(position_size, entry_price, 'sell')  # Actualizar balance aquí
                            logging.info(f"Gestionando posición {in_position}. Stop loss: {stop_loss}, Take profit: {take_profit}.")
                            add_log_message(f"Gestionando posición {in_position}. Stop loss: {stop_loss}, Take profit: {take_profit}.")
            else:
                logging.error("Error al obtener los datos del mercado.")
                add_log_message("Error al obtener los datos del mercado.")
        except Exception as e:
            logging.error(f"Error en la ejecución del bot de trading: {e}")
            add_log_message(f"Error en la ejecución del bot de trading: {e}")
        logging.info("🕒 Esperando 5 minutos antes de la siguiente ejecución.")
        add_log_message("🕒 Esperando 5 minutos antes de la siguiente ejecución.")
        time.sleep(300)

if __name__ == "__main__":
    setup_logging()
    logging.info("Iniciando el bot de trading y el servidor WebSocket")
    add_log_message("Iniciando el bot de trading y el servidor WebSocket")

    # Crear una instancia de BalanceManager y formatear operations.json
    balance_manager = BalanceManager(initial_balance=INITIAL_BALANCE)
    balance_manager.format_operations()

    # Iniciar el servidor WebSocket en el hilo principal
    server_thread = threading.Thread(target=run_server)
    server_thread.start()

    # Ejecutar el bot de trading en un executor
    trading_thread = threading.Thread(target=run_trading_bot)
    trading_thread.start()

    trading_thread.join()
    server_thread.join()

























































