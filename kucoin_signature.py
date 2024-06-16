import hmac
import hashlib
import base64
import time

def generate_signature(api_secret, timestamp, method, endpoint, body=''):
    str_to_sign = f'{timestamp}{method}{endpoint}{body}'
    signature = hmac.new(api_secret.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256)
    signature_b64 = base64.b64encode(signature.digest())
    return signature_b64.decode('utf-8')

def get_kucoin_headers(api_key, api_secret, api_passphrase, method, endpoint, body=''):
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(api_secret, timestamp, method, endpoint, body)
    
    headers = {
        'KC-API-KEY': api_key,
        'KC-API-SIGN': signature,
        'KC-API-TIMESTAMP': timestamp,
        'KC-API-PASSPHRASE': api_passphrase,
        'Content-Type': 'application/json'
    }
    return headers




