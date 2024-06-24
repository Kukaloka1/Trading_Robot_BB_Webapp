import logging
from data.data_fetcher import place_order, get_market_data, get_account_balance
from indicators.technical_indicators import calculate_indicators
from patterns.price_action_patterns import is_pin_bar, is_bullish_engulfing, is_bearish_engulfing
from utils.gpt4_integration import get_gpt4_recommendation
from config import TRAILING_STOP_PCT, TAKE_PROFIT_MULTIPLIER, TIMEFRAME_SCALING_FACTORS, TIMEFRAME, RISK_PER_TRADE, SYMBOL, LIMIT


# Definir los pesos para cada factor
weights = {
    "pin_bar": 2,
    "bullish_engulfing": 2,
    "bearish_engulfing": -2,
    "rsi_buy": 2,
    "rsi_sell": -1,
    "macd_buy": 1,
    "macd_sell": -1,
    "sma50_buy": 1,
    "sma50_sell": -1,
    "volume": 1,
    "adx": 1,
    "plus_di": 1,
    "minus_di": -1,
    "gpt_positive": 3,
    "gpt_negative": -3,
    "gpt_low_risk": 2,
    "gpt_high_risk": -2,
}

def calculate_score(df, index):
    score = 0
    logging.info(f"Calculando puntuación para el índice {index}")

    if is_pin_bar(df, index):
        score += weights["pin_bar"]
        logging.info(f"Patrón Pin Bar detectado, puntaje += {weights['pin_bar']}")

    if is_bullish_engulfing(df, index):
        score += weights["bullish_engulfing"]
        logging.info(f"Patrón Bullish Engulfing detectado, puntaje += {weights['bullish_engulfing']}")

    if is_bearish_engulfing(df, index):
        score += weights["bearish_engulfing"]
        logging.info(f"Patrón Bearish Engulfing detectado, puntaje += {weights['bearish_engulfing']}")

    rsi = df.iloc[index]['RSI']
    if rsi < 30:
        score += weights["rsi_buy"]
        logging.info(f"RSI bajo detectado (RSI={rsi}), puntaje += {weights['rsi_buy']}")
    elif rsi > 70:
        score += weights["rsi_sell"]
        logging.info(f"RSI alto detectado (RSI={rsi}), puntaje += {weights['rsi_sell']}")

    macd = df.iloc[index]['MACD']
    macd_signal = df.iloc[index]['MACDSignal']
    if macd > macd_signal:
        score += weights["macd_buy"]
        logging.info(f"MACD cruzando hacia arriba (MACD={macd}, MACD Signal={macd_signal}), puntaje += {weights['macd_buy']}")
    else:
        score += weights["macd_sell"]
        logging.info(f"MACD cruzando hacia abajo (MACD={macd}, MACD Signal={macd_signal}), puntaje += {weights['macd_sell']}")

    sma50 = df.iloc[index]['SMA50']
    close_price = df.iloc[index]['close']
    if close_price > sma50:
        score += weights["sma50_buy"]
        logging.info(f"Cierre por encima de SMA50 (Close={close_price}, SMA50={sma50}), puntaje += {weights['sma50_buy']}")
    else:
        score += weights["sma50_sell"]
        logging.info(f"Cierre por debajo de SMA50 (Close={close_price}, SMA50={sma50}), puntaje += {weights['sma50_sell']}")

    volume = df.iloc[index]['volume']
    avg_volume = df['volume'].rolling(window=20).mean().iloc[index]
    if volume > avg_volume:
        score += weights["volume"]
        logging.info(f"Volumen por encima del promedio (Volume={volume}, Avg Volume={avg_volume}), puntaje += {weights['volume']}")

    adx = df.iloc[index]['ADX']
    if adx > 25:
        score += weights["adx"]
        logging.info(f"ADX por encima de 25 (ADX={adx}), puntaje += {weights['adx']}")

    plus_di = df.iloc[index]['PlusDI']
    minus_di = df.iloc[index]['MinusDI']
    if plus_di > minus_di:
        score += weights["plus_di"]
        logging.info(f"Plus DI por encima de Minus DI (Plus DI={plus_di}, Minus DI={minus_di}), puntaje += {weights['plus_di']}")
    else:
        score += weights["minus_di"]
        logging.info(f"Minus DI por encima de Plus DI (Plus DI={plus_di}, Minus DI={minus_di}), puntaje += {weights['minus_di']}")

    logging.info(f"Puntuación total calculada: {score}")
    return score

def confirm_entry_with_gpt(df, index, gpt4_analysis):
    score = calculate_score(df, index)
    logging.info(f"Puntuación inicial en el índice {index}: {score} 👀")

    sentiment = gpt4_analysis["sentiment"]
    risk_assessment = gpt4_analysis["risk_assessment"]

    if sentiment == "positive":
        score += weights["gpt_positive"]
        logging.info(f"Sentimiento positivo detectado por GPT-4, puntaje += {weights['gpt_positive']}")
    elif sentiment == "negative":
        score += weights["gpt_negative"]
        logging.info(f"Sentimiento negativo detectado por GPT-4, puntaje += {weights['gpt_negative']}")

    if risk_assessment == "low":
        score += weights["gpt_low_risk"]
        logging.info(f"Riesgo bajo detectado por GPT-4, puntaje += {weights['gpt_low_risk']}")
    elif risk_assessment == "high":
        score += weights["gpt_high_risk"]
        logging.info(f"Riesgo alto detectado por GPT-4, puntaje += {weights['gpt_high_risk']}")

    threshold = 3  # Ajuste del umbral a 3

    if score >= threshold:
        logging.info(f"🚀 Señal de compra confirmada en el índice {index} con puntuación {score} y umbral {threshold}")
        return 'buy', score
    elif score <= -threshold:
        logging.info(f"💥 Señal de venta confirmada en el índice {index} con puntuación {score} y umbral {threshold}")
        return 'sell', score

    logging.info(f"🙅‍♂️ Ninguna señal confirmada en el índice {index} con puntuación {score} y umbral {threshold} (Estado: Neutro)")
    return None, score


def trading_decision_with_gpt(df, account_balance, risk_per_trade, in_position, entry_price, stop_loss, take_profit, position_size):
    for index in range(1, len(df)):
        try:
            gpt4_analysis = get_gpt4_recommendation(
                historical_data={
                    "weekly": df.iloc[max(0, index-7):index].to_dict('records'),
                    "monthly": df.iloc[max(0, index-30):index].to_dict('records'),
                    "daily": df.iloc[max(0, index-1):index].to_dict('records')
                },
                current_price=df.iloc[index]['close'],
                percentage_change_24h=df['close'].pct_change(24).iloc[index] * 100,
                percentage_change_hourly=df['close'].pct_change().iloc[index] * 100,
                trading_volume=df.iloc[index]['volume']
            )
            logging.info(f"Recomendación GPT-4: {gpt4_analysis}")
        except Exception as e:
            logging.error(f"Error al obtener la recomendación de GPT-4: {e}")
            continue

        try:
            signal, score = confirm_entry_with_gpt(df, index, gpt4_analysis)
            logging.info(f"Señal: {signal}, Puntuación: {score}")
            
            if signal == 'buy':
                entry_price = df.iloc[index]['close']
                stop_loss = entry_price - entry_price * risk_per_trade
                take_profit = entry_price + entry_price * (risk_per_trade * 3)
                position_size = account_balance * risk_per_trade / (entry_price - stop_loss)
                in_position = 'buy'
                logging.info(f"Entrando en posición larga en {entry_price} con puntuación {score}")
                log_trade('Enter Buy', SYMBOL, entry_price, position_size, df.iloc[index]['timestamp'])
                place_order(SYMBOL, 'market', 'buy', position_size)  # Abrir posición larga

            elif signal == 'sell':
                entry_price = df.iloc[index]['close']
                stop_loss = entry_price + entry_price * risk_per_trade
                take_profit = entry_price - entry_price * (risk_per_trade * 3)
                position_size = account_balance * risk_per_trade / (stop_loss - entry_price)
                in_position = 'sell'
                logging.info(f"Entrando en posición corta en {entry_price} con puntuación {score}")
                log_trade('Enter Sell', SYMBOL, entry_price, position_size, df.iloc[index]['timestamp'])
                place_order(SYMBOL, 'market', 'sell', position_size)  # Abrir posición corta

            in_position, stop_loss = manage_position_with_trail_stop(df, index, in_position, entry_price, stop_loss, take_profit, SYMBOL, position_size)

        except Exception as e:
            logging.error(f"Error en la lógica de trading: {e}")
            continue

    return in_position, stop_loss


def run_trading_strategy():
    logging.info(f"Ejecutando estrategia de trading para {SYMBOL} con timeframe {TIMEFRAME} y límite {LIMIT}")
    
    # Obtener balance de la cuenta
    account_balance = get_account_balance()
    if account_balance is None:
        logging.error("Failed to fetch account balance. Trading strategy execution aborted.")
        return
    
    balance_usdt = account_balance['total']['USDT']  # Asegúrate de que obtienes el balance de la manera correcta
    df = get_market_data(SYMBOL, TIMEFRAME, LIMIT)
    if df is not None:
        df = calculate_indicators(df)
        in_position, stop_loss = False, 0
        entry_price, take_profit, position_size = 0, 0, 0
        in_position, stop_loss = trading_decision_with_gpt(df, balance_usdt, RISK_PER_TRADE, in_position, entry_price, stop_loss, take_profit, position_size)
    else:
        logging.error("Failed to fetch market data. Trading strategy execution aborted.")


def manage_position_with_trail_stop(df, index, in_position, entry_price, stop_loss, take_profit, symbol, position_size, order_id, trailing_stop_pct):
    current_price = df.iloc[index]['close']
    scaling_factor = TIMEFRAME_SCALING_FACTORS.get(TIMEFRAME, 1.0)
    trailing_stop_pct = trailing_stop_pct * scaling_factor
    take_profit_multiplier = TAKE_PROFIT_MULTIPLIER * scaling_factor

    logging.info(f"Gestionando posición {'buy' if in_position == 'buy' else 'sell'} en el índice {index}. Precio actual: {current_price}. ID de la orden: {order_id}")

    if in_position == 'buy':
        new_stop_loss = current_price * (1 - trailing_stop_pct)
        stop_loss = max(stop_loss, new_stop_loss)
        if take_profit is None:
            take_profit = entry_price * take_profit_multiplier
        logging.info(f"Nuevo stop loss calculado para posición larga: {new_stop_loss}. Stop loss ajustado: {stop_loss}. Take profit: {take_profit}")

        if current_price >= take_profit:
            log_trade('Exit Buy', symbol, current_price, position_size, df.iloc[index]['timestamp'])
            place_order(symbol, 'market', 'sell', position_size)
            in_position = False
        elif current_price <= stop_loss:
            log_trade('Exit Buy - Stop Loss', symbol, current_price, position_size, df.iloc[index]['timestamp'])
            place_order(symbol, 'market', 'sell', position_size)
            in_position = False
        else:
            logging.info(f"Trailing stop activo. Precio actual: {current_price}, Stop loss actual: {stop_loss}, Take profit: {take_profit}. ID de la orden: {order_id}")

    elif in_position == 'sell':
        new_stop_loss = current_price * (1 + trailing_stop_pct)
        stop_loss = min(stop_loss, new_stop_loss)
        if take_profit is None:
            take_profit = entry_price * (2 - take_profit_multiplier)
        logging.info(f"Nuevo stop loss calculado para posición corta: {new_stop_loss}. Stop loss ajustado: {stop_loss}. Take profit: {take_profit}")

        if current_price <= take_profit:
            log_trade('Exit Sell', symbol, current_price, position_size, df.iloc[index]['timestamp'])
            place_order(symbol, 'market', 'buy', position_size)
            in_position = False
        elif current_price >= stop_loss:
            log_trade('Exit Sell - Stop Loss', symbol, current_price, position_size, df.iloc[index]['timestamp'])
            place_order(symbol, 'market', 'buy', position_size)
            in_position = False
        else:
            logging.info(f"Trailing stop activo. Precio actual: {current_price}, Stop loss actual: {stop_loss}, Take profit: {take_profit}. ID de la orden: {order_id}")

    return in_position, stop_loss, order_id  # Asegurarse de devolver el order_id




def log_trade(action, symbol, price, size, timestamp):
    logging.info(f"{action} - Symbol: {symbol}, Price: {price}, Size: {size}, Time: {timestamp}")










