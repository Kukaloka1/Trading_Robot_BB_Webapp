import logging
import json
import os

class BalanceManager:
    def __init__(self, initial_balance, balance_file='balance.json', operations_file='operations.json'):
        self.initial_balance = initial_balance
        self.balance_file = balance_file
        self.operations_file = operations_file
        self.committed_balance = 0
        self.load_balance()
        self.load_operations()
        self.operations_logger = logging.getLogger('operations')

    def load_balance(self):
        if os.path.exists(self.balance_file):
            with open(self.balance_file, 'r') as f:
                self.balance = json.load(f)
        else:
            self.balance = {'USDT': self.initial_balance}
            self.save_balance()

    def save_balance(self):
        with open(self.balance_file, 'w') as f:
            json.dump(self.balance, f)

    def load_operations(self):
        if os.path.exists(self.operations_file):
            with open(self.operations_file, 'r') as f:
                self.operations = json.load(f)
        else:
            self.operations = []
            self.save_operations()

    def save_operations(self):
        with open(self.operations_file, 'w') as f:
            json.dump(self.operations, f)

    def get_balance(self):
        return self.balance

    def update_balance(self, amount, price, side):
        cost = amount * price
        if side == 'buy':
            self.balance['USDT'] -= cost
        elif side == 'sell':
            self.balance['USDT'] += cost
        self.save_balance()
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
        self.operations.append(operation)
        self.save_operations()
        logging.info(f"Operation added: {operation}")
        self.operations_logger.info(f"Operation: {operation}")

    def get_operations(self):
        return self.operations



