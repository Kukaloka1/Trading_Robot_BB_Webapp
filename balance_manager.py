import json
import os
import logging

class BalanceManager:

    def __init__(self, artificial_balance, operations_file='operations.json'):
        self.artificial_balance = artificial_balance['USDT']
        self.operations_file = operations_file
        self.committed_balance = 0
        self.load_operations()
        self.balance = {'USDT': self.artificial_balance}
        self.operations_logger = logging.getLogger('operations')

    def load_operations(self):
        if os.path.exists(self.operations_file):
            with open(self.operations_file, 'r') as f:
                self.operations = json.load(f)
        else:
            self.operations = []
            self.save_operations()

    def save_operations(self):
        with open(self.operations_file, 'w') as f:
            json.dump(self.operations, f, indent=4)

    def get_balance(self, current_price=None):
        available_balance = self.balance.get('USDT', 0)
        total_committed = 0
        unrealized_pnl = 0

        if current_price:
            for op in self.operations:
                if op['status'] == 'open':
                    if op['side'] == 'buy':
                        total_committed += op['size'] * op['price']
                        unrealized_pnl += (current_price - op['price']) * op['size']
                    elif op['side'] == 'sell':
                        total_committed += op['size'] * op['price']
                        unrealized_pnl += (op['price'] - current_price) * op['size']

        total_balance = available_balance - total_committed + unrealized_pnl
        logging.info(f"Balances calculados - Available: {available_balance}, Committed: {total_committed}, PnL: {unrealized_pnl}, Total: {total_balance}")
        return {
            'available_balance': available_balance - total_committed,
            'total_committed': total_committed,
            'unrealized_pnl': unrealized_pnl,
            'total_balance': total_balance
        }

    def update_balance(self, amount, price, side):
        cost = amount * price
        if side == 'buy':
            self.balance['USDT'] -= cost
        elif side == 'sell':
            self.balance['USDT'] += cost

        logging.info(f"Updated artificial balance: {self.balance}")

    def can_trade(self, amount, price, side):
        cost = amount * price
        if side == 'buy':
            return cost <= (self.balance['USDT'] - self.committed_balance)
        elif side == 'sell':
            return True
        return False

    def commit_balance(self, amount, price):
        self.committed_balance += amount * price
        logging.info(f"Committed balance updated: {self.committed_balance}")

    def release_committed_balance(self, amount, price):
        self.committed_balance -= amount * price
        logging.info(f"Committed balance released: {self.committed_balance}")

    def add_operation(self, operation):
        existing_order = next((op for op in self.operations if op['orderId'] == operation['orderId']), None)
        if existing_order:
            existing_order.update(operation)
        else:
            self.operations.append(operation)

        # Actualiza el balance en la operación
        if operation['side'] == 'buy':
            self.balance['USDT'] -= operation['size'] * operation['price']
            self.balance['total_committed'] += operation['size'] * operation['price']
        elif operation['side'] == 'sell':
            self.balance['USDT'] += operation['size'] * operation['price']
            self.balance['total_committed'] -= operation['size'] * operation['price']

        operation['balance'] = self.get_balance().copy()

        self.save_operations()
        logging.info(f"Operation added/updated: {operation}")
        self.operations_logger.info(f"Operation: {operation}")

    def close_operation(self, order_id):
        for operation in self.operations:
            if operation['orderId'] == order_id and operation['status'] == 'open':
                operation['status'] = 'closed'
                if operation['side'] == 'buy':
                    self.balance['USDT'] += operation['size'] * operation['price']
                    self.balance['total_committed'] -= operation['size'] * operation['price']
                elif operation['side'] == 'sell':
                    self.balance['USDT'] -= operation['size'] * operation['price']
                    self.balance['total_committed'] += operation['size'] * operation['price']
                break

        self.save_operations()
        logging.info(f"Operation closed: {order_id}")
        self.operations_logger.info(f"Operation closed: {order_id}")

    def get_operations(self):
        return self.operations

    def clean_operations(self):
        self.operations = [op for op in self.operations if op.get('status') != 'fictitious']
        self.save_operations()

    def format_operations(self):
        """Leer, formatear y guardar el archivo operation.json"""
        with open(self.operations_file, 'r') as file:
            operations = json.load(file)
        with open(self.operations_file, 'w') as file:
            json.dump(operations, file, indent=4)




