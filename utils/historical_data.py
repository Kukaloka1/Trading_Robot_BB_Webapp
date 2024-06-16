import pandas as pd

def prepare_historical_data(df):
    """
    Prepara los datos históricos resumiéndolos para su uso en la integración con GPT-4.

    Args:
    df (pandas.DataFrame): DataFrame con los datos de mercado.

    Returns:
    dict: Diccionario con los datos históricos resumidos.
    """
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)

        # Resumir los datos a diario y semanalmente
        daily_data = df.resample('D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()

        weekly_data = df.resample('W').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()

        historical_data = {
            "weekly": weekly_data.reset_index().to_dict('records'),
            "daily": daily_data.tail(7).reset_index().to_dict('records'),  # Enviar solo los últimos 7 días de datos diarios
        }

        return historical_data
    except Exception as e:
        print(f"Error al preparar los datos históricos: {e}")
        return None

