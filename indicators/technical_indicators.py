import talib
import logging
import json
from patterns.price_action_patterns import is_pin_bar, is_bullish_engulfing, is_bearish_engulfing

def calculate_indicators(df):
    try:
        # Calcular indicadores técnicos
        df['SMA50'] = talib.SMA(df['close'], timeperiod=50).fillna(0)
        df['SMA200'] = talib.SMA(df['close'], timeperiod=200).fillna(0)
        df['RSI'] = talib.RSI(df['close'], timeperiod=14).fillna(0)
        df['MACD'], df['MACDSignal'], _ = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        df['BollingerUpper'], df['BollingerMiddle'], df['BollingerLower'] = talib.BBANDS(df['close'], timeperiod=20)
        df['ATR'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14).fillna(0)
        df['ADX'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14).fillna(0)
        df['PlusDI'] = talib.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14).fillna(0)
        df['MinusDI'] = talib.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14).fillna(0)

        # Detectar patrones de acción del precio
        df['PinBar'] = [is_pin_bar(df, i) for i in range(len(df))]
        df['BullishEngulfing'] = [is_bullish_engulfing(df, i) for i in range(len(df))]
        df['BearishEngulfing'] = [is_bearish_engulfing(df, i) for i in range(len(df))]

        logging.info(f"Indicadores técnicos y patrones calculados. Columnas del DataFrame: {df.columns}")
    except Exception as e:
        logging.error(f"Error calculando indicadores técnicos: {e}")
        raise
    return df













