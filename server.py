# server.py

from flask import Flask, request, jsonify
import threading
import logging
from config import SYMBOL, ACCOUNT_TYPE, TIMEFRAME, LIMIT, RISK_PER_TRADE, LEVERAGE, MAX_CAPITAL_USAGE, MARGIN_TYPE, SYMBOL_FUTURES, SYMBOL_MARGIN, SYMBOL_SPOT
from data.data_fetcher import get_account_balance, update_artificial_balance, get_open_orders, get_current_price
from strategies.trading_strategy import calculate_indicators, confirm_entry_with_gpt, manage_position_with_trail_stop
from utils.logging_setup import setup_logging
from main import run_trading_bot, place_order_with_logging

app = Flask(__name__)

@app.route('/trigger_buy', methods=['POST'])
def trigger_buy():
    try:
        symbol = request.json.get('symbol', SYMBOL)
        order_type = 'market'
        side = 'buy'
        amount = request.json.get('amount', 0.01)  # Default amount for testing
        balance = get_account_balance()

        place_order_with_logging(symbol, order_type, side, amount, balance)
        
        return jsonify({"status": "success", "message": "Buy order triggered"}), 200
    except Exception as e:
        logging.error(f"Error triggering buy order: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    setup_logging()
    logging.info("Iniciando el servidor Flask")
    threading.Thread(target=run_trading_bot).start()
    app.run(host='0.0.0.0', port=5000)
