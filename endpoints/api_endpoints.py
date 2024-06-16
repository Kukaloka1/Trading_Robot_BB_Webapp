from flask import Flask, jsonify, request
import uuid  
from data.data_fetcher import get_market_data, get_account_balance, place_order, cancel_order, get_order_status

app = Flask(__name__)

@app.route('/api/market-data', methods=['GET'])
def market_data():
    symbol = request.args.get('symbol')
    timeframe = request.args.get('timeframe', '1h')
    limit = int(request.args.get('limit', 200))
    data = get_market_data(symbol, timeframe, limit)
    if data is not None:
        return jsonify(data)
    return jsonify({'error': 'Failed to fetch market data'}), 500

@app.route('/api/account-balance', methods=['GET'])
def account_balance():
    balance = get_account_balance()
    if balance is not None:
        return jsonify(balance)
    return jsonify({'error': 'Failed to fetch account balance'}), 500

@app.route('/api/place-order', methods=['POST'])
def place_order_endpoint():
    data = request.json
    symbol = data.get('symbol')
    order_type = data.get('type')
    side = data.get('side')
    amount = data.get('amount')
    price = data.get('price')
    
    if not symbol or not order_type or not side or not amount:
        return jsonify({'error': 'Missing required parameters'}), 400

    order = place_order(str(uuid.uuid4()), symbol, side, order_type, amount, price)
    if order and 'data' in order:
        return jsonify(order)
    return jsonify({'error': 'Failed to place order', 'details': order}), 500

@app.route('/api/cancel-order', methods=['POST'])
def cancel_order_endpoint():
    data = request.json
    order_id = data.get('order_id')
    symbol = data.get('symbol')
    if not order_id or not symbol:
        return jsonify({'error': 'Missing required parameters'}), 400

    result = cancel_order(order_id, symbol)
    if result is not None:
        return jsonify(result)
    return jsonify({'error': 'Failed to cancel order'}), 500

@app.route('/api/order-status', methods=['GET'])
def order_status():
    order_id = request.args.get('order_id')
    symbol = request.args.get('symbol')
    if not order_id or not symbol:
        return jsonify({'error': 'Missing required parameters'}), 400

    order = get_order_status(order_id, symbol)
    if order is not None:
        return jsonify(order)
    return jsonify({'error': 'Failed to fetch order status'}), 500

if __name__ == '__main__':
    app.run(debug=True)

