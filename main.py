import time
import requests
import uuid  
import logging
import threading
from utils.logging_setup import setup_logging
from data.data_fetcher import get_market_data, get_account_balance, calculate_trade_amount, place_order, get_open_orders, get_open_orders_futures, get_current_price
from indicators.technical_indicators import calculate_indicators
from config import SYMBOL, ACCOUNT_TYPE, TIMEFRAME, LIMIT, RISK_PER_TRADE, SYMBOL_SPOT, EXCHANGE, MAX_CAPITAL_USAGE, SYMBOL_FUTURES, LEVERAGE, SYMBOL_MARGIN, MARGIN_TYPE
from utils.gpt4_integration import get_gpt4_recommendation, prepare_historical_data
from strategies.trading_strategy import manage_position_with_trail_stop, confirm_entry_with_gpt
from kucoin_signature import get_kucoin_headers
from config import KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE
from kucoin_requests import BASE_URL_FUTURES, get_open_orders_margin, BASE_URL_MARGIN
from stream_trading.stream_logs import run_server, add_log_message


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
        order_id = order_response['data']['orderId']
        logging.info(f"Orden ID: {order_id}")
        
        # Obtener detalles de la orden
        order_details = EXCHANGE.fetch_order(order_id, SYMBOL)
        price = order_details['price']
        filled = order_details['filled']
        remaining = order_details['remaining']
        logging.info(f"Detalles de la orden: Precio {price}, Cantidad {filled}, Restante {remaining}")
        
        # Loguear el balance después de la operación
        logging.info(f"Balance disponible en USDT: {balance['free']['USDT']}")
        logging.info(f"Balance en el mercado: {balance['used']['USDT']}")
    except Exception as e:
        logging.error(f"Error al obtener detalles de la orden: {e}")

def place_order_with_logging(symbol, order_type, side, amount, balance):
    try:
        order_response = place_order(symbol, order_type, side, amount)
        if order_response and order_response.get('code') == '200000':
            logging.info(f"Orden de {side} colocada por {amount} unidades.")
            log_order_details(order_response, balance)
        else:
            logging.error(f"Error al colocar la orden: {order_response}")
    except Exception as e:
        logging.error(f"Error al colocar la orden: {e}")

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

        if buy_condition:
            logging.info("Condiciones de compra detectadas.")
            return 'buy'
        elif sell_condition:
            logging.info("Condiciones de venta detectadas.")
            return 'sell'
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

def run_trading_bot():
    operations_logger = logging.getLogger('operations')
    logging.info("🚀 Bot de trading iniciado. Buscando oportunidades de trading.")
    
    if ACCOUNT_TYPE in ['futures', 'margin']:
        try:
            if ACCOUNT_TYPE == 'futures':
                set_leverage(SYMBOL, LEVERAGE)
                logging.info(f"📈 Apalancamiento configurado a {LEVERAGE}x para cuenta de futuros.")
            elif ACCOUNT_TYPE == 'margin':
                if MARGIN_TYPE == 'cross':
                    logging.info("🔄 Operando en cuenta de margen tipo cross.")
                elif MARGIN_TYPE == 'isolated':
                    logging.info("🔒 Operando en cuenta de margen tipo isolated.")
                logging.info(f"🔧 El apalancamiento {LEVERAGE}x se configurará durante la creación de la orden para cuentas de margen.")
        except Exception as e:
            logging.error(f"❌ Error crítico al configurar el apalancamiento: {e}")

    logging_thread = None
    in_position = False
    entry_price = 0
    stop_loss = 0
    take_profit = 0
    position_size = 0
    order_id = None

    if ACCOUNT_TYPE == 'futures':
        symbol = SYMBOL_FUTURES
        logging.info("💹 Operando en cuenta de futuros.")
    elif ACCOUNT_TYPE == 'margin':
        symbol = SYMBOL_MARGIN
        logging.info("💹 Operando en cuenta de margen.")
    else:
        symbol = SYMBOL_SPOT
        logging.info("💹 Operando en cuenta spot.")

    open_orders = get_open_orders(symbol)
    
    if open_orders and 'data' in open_orders and 'items' in open_orders['data']:
        for order in open_orders['data']['items']:
            if order['status'] == 'active':
                operations_logger.info(f"Orden abierta recuperada: ID {order['id']}, Precio {order.get('price')}, Cantidad {order['size']}, Estado {order['status']}")
                in_position = 'buy' if order['side'] == 'buy' else 'sell'
                entry_price = float(order['price'])
                stop_loss = entry_price * (1 - 0.02) if in_position == 'buy' else entry_price * (1 + 0.02)
                take_profit = entry_price * 1.05 if in_position == 'buy' else entry_price * 0.95
                position_size = float(order['size'])
                order_id = order['id']
                current_price = get_current_price(symbol)
                logging.info(f"Recuperada orden {in_position} ID {order_id} comprada a {entry_price}, precio actual {current_price}")
                break
    else:
        logging.info("📭 No hay órdenes abiertas.")

    # Parámetro para usar el balance artificial
    use_artificial_balance = True  # Cambiar a False si deseas usar el balance real

    while True:
        try:
            logging.info("💼 Obteniendo datos del mercado...")
            df = get_market_data(symbol, TIMEFRAME, LIMIT)
            if df is not None:
                logging.info("📊 Datos del mercado obtenidos.")
                logging.info("📈 Calculando indicadores técnicos...")
                df = calculate_indicators(df)
                logging.info("📊 Indicadores técnicos calculados.")

                if logging_thread is None or not logging_thread.is_alive():
                    logging_thread = threading.Thread(target=log_indicators, args=(df,), daemon=True)
                    logging_thread.start()

                historical_data = prepare_historical_data(df)
                current_price = df['close'].iloc[-1]
                percentage_change_24h = df['close'].pct_change(24).iloc[-1] * 100
                percentage_change_hourly = df['close'].pct_change().iloc[-1] * 100
                trading_volume = df['volume'].iloc[-1]

                logging.info("🧠 Solicitando recomendación a GPT-4...")
                gpt4_recommendation = get_gpt4_recommendation(historical_data, current_price, percentage_change_24h, percentage_change_hourly, trading_volume)
                df['GPT4_Sentiment'] = gpt4_recommendation['sentiment']
                df['GPT4_RiskAssessment'] = gpt4_recommendation['risk_assessment']
                logging.info(f"🤖 Recomendación GPT-4: Sentimiento {gpt4_recommendation['sentiment']}, Evaluación de Riesgo {gpt4_recommendation['risk_assessment']}")

                logging.info("💼 Obteniendo balance de la cuenta...")
                account_balance = get_account_balance(use_artificial=use_artificial_balance)  # Usa el parámetro aquí
                if account_balance:
                    logging.info(f"💰 Balance de la cuenta (USDT): {account_balance}")

                    total_balance = account_balance.get('USDT', 0)
                    if total_balance <= 0:
                        logging.warning("El balance disponible es cero. No se procederá con las operaciones. Por favor, deposite fondos en la cuenta.")
                        time.sleep(300)
                        continue

                    capital_usado = sum([float(order['size']) * float(order['price']) for order in open_orders['data']['items']]) if open_orders and 'data' in open_orders and 'items' in open_orders['data'] else 0
                    if capital_usado >= total_balance * MAX_CAPITAL_USAGE:
                        logging.warning(f"Uso de capital máximo alcanzado: {capital_usado} USDT. No se colocarán nuevas órdenes.")
                    else:
                        if not in_position:
                            action, score = confirm_entry_with_gpt(df, -1, gpt4_recommendation)
                            logging.info(f"Puntuación inicial en el índice -1: {score}")
                            if action:
                                in_position = action
                                entry_price = current_price
                                stop_loss = entry_price * (1 - 0.02) if action == 'buy' else entry_price * (1 + 0.02)
                                take_profit = entry_price * 1.05 if action == 'buy' else entry_price * 0.95
                                position_size = calculate_trade_amount(account_balance, RISK_PER_TRADE)
                                logging.info(f"Posición {action} abierta en {entry_price} con tamaño {position_size}")
                                if ACCOUNT_TYPE == 'spot' and action == 'sell':
                                    logging.info("Venta detectada en mercado spot, ignorando señal de venta.")
                                else:
                                    if position_size >= 0.1:
                                        order = place_order(str(uuid.uuid4()), symbol, action, 'market', position_size, leverage=LEVERAGE if ACCOUNT_TYPE == 'margin' else None)
                                        if order:
                                            order_id = order.get('data', {}).get('orderId')  # Manejo seguro de la clave 'data'
                                            if not order_id:
                                                logging.error(f"Orden no contiene 'orderId': {order}")
                                        else:
                                            logging.error("Error al colocar la orden.")
                                    else:
                                        logging.error(f"Trade amount {position_size} USDT es menor que el mínimo requerido de 0.1 USDT.")
                        else:
                            in_position, stop_loss = manage_position_with_trail_stop(df, -1, in_position, entry_price, stop_loss, take_profit, symbol, position_size, order_id, trailing_stop_pct=0.02)
                            logging.info(f"Gestionando posición {in_position} en el índice -1. Precio actual: {current_price}. ID de la orden: {order_id}")
                            logging.info(f"Stop loss actual: {stop_loss}, Take profit: {take_profit}")
            else:
                logging.error("Error al obtener los datos del mercado.")
        except Exception as e:
            logging.error(f"Error en la ejecución del bot de trading: {e}")

        logging.info("🕒 Esperando 5 minutos antes de la siguiente ejecución...")
        time.sleep(300)

if __name__ == "__main__":
    setup_logging()
    logging.info("Iniciando el bot de trading y el servidor WebSocket")
    threading.Thread(target=run_server).start()
    run_trading_bot()




















































