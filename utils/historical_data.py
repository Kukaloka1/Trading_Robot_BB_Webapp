def prepare_historical_data(df):
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    # Resumir datos
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
        "daily": daily_data.tail(5).reset_index().to_dict('records')  # Últimos 5 días de datos
    }

    return historical_data
