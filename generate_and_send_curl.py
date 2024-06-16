import os
from dotenv import load_dotenv
import time
import hmac
import hashlib
import base64
import subprocess

# Cargar variables de entorno
load_dotenv()

# Obtener variables de entorno
api_key = os.getenv('KUCOIN_API_KEY')
api_secret = os.getenv('KUCOIN_API_SECRET')
api_passphrase = os.getenv('KUCOIN_API_PASSPHRASE')

# Verificar que las variables de entorno se cargaron correctamente
if not all([api_key, api_secret, api_passphrase]):
    raise ValueError("Las variables de entorno no se cargaron correctamente.")

# Imprimir las variables para verificar que son correctas
print(f"KUCOIN_API_KEY: {api_key}")
print(f"KUCOIN_API_SECRET: {api_secret}")
print(f"KUCOIN_API_PASSPHRASE: {api_passphrase}")

# Generar timestamp en milisegundos
timestamp = str(int(time.time() * 1000))
print("Generated Timestamp:", timestamp)

method = 'GET'
endpoint = '/api/v1/accounts'
body = ''

# Generar firma
message = timestamp + method + endpoint + body
signature = hmac.new(api_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
signature_b64 = base64.b64encode(signature).decode()

# Imprimir el signature para verificar
print("Generated Signature:", signature_b64)

# Crear el comando curl
curl_command = f"""
curl -X GET "https://api.kucoin.com{endpoint}" \\
-H "KC-API-KEY: {api_key}" \\
-H "KC-API-SIGN: {signature_b64}" \\
-H "KC-API-TIMESTAMP: {timestamp}" \\
-H "KC-API-PASSPHRASE: {api_passphrase}" \\
-H "Content-Type: application/json"
"""

# Ejecutar el comando curl
print("Executing curl command:")
print(curl_command)
result = subprocess.run(curl_command, shell=True, capture_output=True, text=True)
print("Response:")
print(result.stdout)
print("Error:")
print(result.stderr)


# El script está diseñado para interactuar con la API de KuCoin, 
# específicamente para obtener el balance de la cuenta. Utiliza claves API y una 
# frase de contraseña para autenticar las solicitudes. 