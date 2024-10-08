import yfinance as yf
import pandas as pd
import plotly.figure_factory as ff
import plotly.io as pio

def fetch_stock_data(ticker, start_date, end_date):
    stock_data = yf.download(ticker, start=start_date, end=end_date)
    if stock_data.empty:
        return None
    stock_data['Price'] = stock_data['Adj Close']
    stock_data = stock_data.ffill().interpolate()
    return stock_data['Price']

def compute_correlation_matrix(tickers, start_date, end_date):
    # Combine the default tickers with any user-specified ones
    DEFAULT_TICKERS = ['AAPL', 'AMZN', 'GOOGL', 'TSLA', 'BTC-USD', 'ETH-USD', 'GC=F', 'SI=F', 'PL=F', 'PA=F', 'DX-Y.NYB', 'NVDA', 'MSFT', 'META', '^SPX', '^NDX', '^DJI']
    tickers_list = list(set(DEFAULT_TICKERS + [ticker.strip().upper() for ticker in tickers.split(',') if ticker.strip()]))

    price_data = pd.DataFrame()

    # Fetch stock prices for each ticker
    for ticker in tickers_list:
        stock_prices = fetch_stock_data(ticker, start_date, end_date)
        if stock_prices is not None:
            price_data[ticker] = stock_prices

    if price_data.empty:
        return None

    # Compute the correlation matrix and round to 2 decimal places
    corr_matrix = price_data.corr(method='pearson').round(2)

    # Mapping of tickers to custom labels
    ticker_labels = {
        'AAPL': 'Apple',
        'TSLA': 'Tesla',
        'MSFT': 'Microsoft',
        'GOOGL': 'Alphabet',
        'AMZN': 'Amazon',
        'META': 'Meta',
        'NVDA': 'Nvidia',
        'DX-Y.NYB': 'DXY',
        '^SPX': 'S&P500',
        '^NDX': 'Nasdaq 100',
        '^DJI': 'Dow Jones',
        'GC=F': 'Gold',
        'SI=F': 'Silver',
        'PL=F': 'Platinum',
        'PA=F': 'Palladium',
        'ETH-USD': 'Ethereum',
        'BTC-USD': 'Bitcoin',
    }

    # Keep the original tickers for internal correlation matrix
    tickers_ordered = corr_matrix.columns.tolist()

    # Create a list of custom labels for display purposes, but keep the original tickers for calculations
    tickers_labeled = [ticker_labels.get(ticker, ticker) for ticker in tickers_ordered]

    # Reverse the order of the tickers and the correlation matrix rows
    tickers_reversed = tickers_ordered[::-1]
    corr_matrix_reversed = corr_matrix.loc[tickers_reversed, tickers_ordered]

    # Define the red-green color scale with more contrast
    colorscale = [
        [0, "red"],       # -1.0 -> Red
        [0.25, "#ff9999"],  # More shades of red
        [0.5, "white"],   # 0.0 -> White
        [0.75, "#99ff99"],  # More shades of green
        [1, "green"]      # 1.0 -> Green
    ]

    # Create a heatmap for the correlation matrix
    fig = ff.create_annotated_heatmap(
        z=corr_matrix_reversed.values,
        x=tickers_labeled,  # Use the custom labels for columns
        y=[ticker_labels.get(ticker, ticker) for ticker in tickers_reversed],  # Custom labels for rows
        annotation_text=corr_matrix_reversed.values,
        colorscale=colorscale,
        hoverinfo="z"
    )

    # Update layout to match the desired style
    fig.update_layout(
        title='Correlation Coefficient Matrix',
        xaxis=dict(title='Assets', tickmode='array', tickvals=tickers_labeled),
        yaxis=dict(title='Assets', tickmode='array', tickvals=[ticker_labels.get(ticker, ticker) for ticker in tickers_reversed]),
        autosize=True,
        margin=dict(l=40, r=40, b=80, t=40, pad=5),
    )

    # Convert the figure to JSON for rendering in the frontend
    graph_json = pio.to_json(fig)
    return graph_json
