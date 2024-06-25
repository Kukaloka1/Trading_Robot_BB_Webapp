import openai
import logging
import os
import pandas as pd
import tiktoken  # Importa tiktoken para contar los tokens


# Configura tu clave de API
openai.api_key = os.getenv('OPENAI_API_KEY')

def summarize_data(df, period):
    summarized_data = df.resample(period).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'RSI': 'mean',
        'MACD': 'mean',
        'MACDSignal': 'mean',
        'SMA50': 'mean'
    }).tail(10)  # Limitamos a los últimos 10 periodos para no enviar demasiados datos
    return summarized_data

def prepare_historical_data(df):
    df.index = pd.to_datetime(df.index)

    weekly_data = summarize_data(df, 'W').to_dict('records')
    monthly_data = summarize_data(df, 'MS').to_dict('records')  # Cambiamos 'M' a 'MS'
    daily_data = df[-1:].to_dict('records')

    historical_data = {
        "weekly": weekly_data,
        "monthly": monthly_data,
        "daily": daily_data
    }
    return historical_data

def get_gpt4_recommendation(historical_data, current_price, percentage_change_24h, percentage_change_hourly, trading_volume):
    try:
        logging.info('Solicitando recomendación a GPT-4.')

        # Crear el prompt con un resumen de los datos
        prompt = (
            f"You are an expert trader of Bitcoin. Analyze the current market sentiment and provide a risk assessment based on the following summarized data and make a prediction of the trend:\n\n"
            f"Current Price: {current_price}\n"
            f"Percentage Change in Last 24 Hours: {percentage_change_24h:.2f}%\n"
            f"Hourly Percentage Change: {percentage_change_hourly:.2f}%\n"
            f"Trading Volume: {trading_volume}\n"
            f"Weekly Data Summary: {historical_data['weekly']}\n"
            f"Monthly Data Summary: {historical_data['monthly']}\n"
            f"Daily Data Summary: {historical_data['daily']}\n"
        )
        
        # Contar los tokens del prompt
        enc = tiktoken.encoding_for_model("gpt-4")
        num_tokens = len(enc.encode(prompt))
        logging.info(f"Tokens en el prompt enviado: {num_tokens}")
        

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.9,
            top_p=1.0,
            frequency_penalty=1.0,
            presence_penalty=1.0
        )
        recommendation = response.choices[0].message['content'].strip()
        logging.info('Recomendación recibida de GPT-4.')

        # Transformar el análisis en un formato útil
        analysis_data = {
            "sentiment": "positive" if "positive" in recommendation else "negative" if "negative" in recommendation else "neutral",
            "risk_assessment": "low" if "low" in recommendation else "high" if "high" in recommendation else "normal"
        }

        logging.info("GPT-4 analysis requested successfully")
        return analysis_data
    except Exception as e:
        logging.error(f"Error requesting GPT-4 analysis: {e}")
        return {"sentiment": "neutral", "risk_assessment": "normal"}  # Valores predeterminados
