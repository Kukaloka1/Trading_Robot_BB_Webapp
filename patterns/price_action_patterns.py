import pandas as pd
import logging

def is_pin_bar(df, index):
    if index < 1 or index >= len(df):
        return False
    try:
        bar = df.iloc[index]
        body = abs(bar['close'] - bar['open'])
        tail = abs(bar['high'] - bar['low'])
        pin_bar = (tail > 2 * body) and (min(bar['close'], bar['open']) > bar['low']) and (max(bar['close'], bar['open']) < bar['high'])
        return pin_bar
    except Exception as e:
        logging.error(f"Error al verificar Pin Bar en índice {index}: {e}")
        return False

def is_bullish_engulfing(df, index):
    if index < 1 or index >= len(df):
        return False
    try:
        prev_bar = df.iloc[index - 1]
        curr_bar = df.iloc[index]
        bullish_engulfing = (prev_bar['close'] < prev_bar['open']) and (curr_bar['close'] > curr_bar['open']) and (curr_bar['close'] > prev_bar['open']) and (curr_bar['open'] < prev_bar['close'])
        return bullish_engulfing
    except Exception as e:
        logging.error(f"Error al verificar Bullish Engulfing en índice {index}: {e}")
        return False

def is_bearish_engulfing(df, index):
    if index < 1 or index >= len(df):
        return False
    try:
        prev_bar = df.iloc[index - 1]
        curr_bar = df.iloc[index]
        bearish_engulfing = (prev_bar['close'] > prev_bar['open']) and (curr_bar['close'] < curr_bar['open']) and (curr_bar['open'] > prev_bar['close']) and (curr_bar['close'] < prev_bar['open'])
        return bearish_engulfing
    except Exception as e:
        logging.error(f"Error al verificar Bearish Engulfing en índice {index}: {e}")
        return False
