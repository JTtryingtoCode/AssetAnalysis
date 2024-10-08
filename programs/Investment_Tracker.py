import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
import plotly.io as pio

def fetch_stock_data(ticker, start_date):
    stock_data = yf.download(ticker, start=start_date)
    if stock_data.empty:
        return None, None
    stock_data['Price'] = stock_data['Adj Close']
    stock_data = stock_data.ffill().interpolate()
    first_valid_date = stock_data.index.min()  # First available trading date for this stock
    return stock_data['Price'], first_valid_date

def calculate_investment_growth(ticker, start_date, monthly_investment):
    stock_data = yf.download(ticker, start=start_date)
    
    if stock_data.empty:
        return None, None, None, None, None

    # Ensure 'Adj Close' is a single column and assign it to 'Price'
    if 'Adj Close' in stock_data.columns:
        stock_data['Price'] = stock_data['Adj Close'].copy()
    else:
        return None, None, None, None, None

    stock_data = stock_data.ffill().interpolate()
    stock_data = stock_data.resample('D').first().ffill()
    first_valid_date = stock_data.index.min()
    stock_data = stock_data[stock_data.index >= first_valid_date]
    start_date = max(pd.to_datetime(start_date), first_valid_date)
    stock_data['Investment Value'] = 0
    current_investment = 0

    first_trading_days = []
    for i in range(len(stock_data)):
        date = stock_data.index[i]
        if i == 0 or (date.month != stock_data.index[i-1].month and date >= start_date):
            first_trading_days.append(date)
    
    for month in first_trading_days:
        if month >= start_date:
            monthly_start_price = stock_data.loc[month, 'Price']
            current_investment += monthly_investment  # Ensure monthly_investment is a float here
            stock_data.loc[month:, 'Investment Value'] += (monthly_investment / monthly_start_price) * stock_data.loc[month:, 'Price']
            if month == first_trading_days[0]:
                stock_data.loc[month, 'Investment Value'] = monthly_investment

    final_amount = stock_data['Investment Value'].iloc[-1]
    total_investment = len(first_trading_days) * monthly_investment
    percent_change = ((final_amount - total_investment) / total_investment) * 100

    return stock_data['Investment Value'], total_investment, percent_change, first_valid_date, final_amount

def run_stock_tracker(tickers, start_date, monthly_investment=None):
    tickers_list = [ticker.strip().upper() for ticker in tickers.split(',')]
    start_date = pd.Timestamp(start_date)

    # Initialize data holders
    investment_data = pd.DataFrame()
    price_data = pd.DataFrame()  # Track stock prices for each ticker
    valid_tickers = []
    investment_summary = []
    stock_summary = []  # To track percent change for stock performance
    cumulative_investment = 0
    cumulative_total_value = 0

    # Ensure that monthly_investment is properly converted to a float
    if monthly_investment:
        try:
            monthly_investment = float(monthly_investment)
        except ValueError:
            return {"error": "Invalid monthly investment amount."}
    
    # Loop through each ticker and fetch stock data from the specified start date
    for ticker in tickers_list:
        stock_prices, first_valid_date = fetch_stock_data(ticker, start_date)
        if stock_prices is not None:
            valid_tickers.append(ticker)

            # For investment growth, run the calculation
            if monthly_investment:
                investment_growth, total_investment, percent_change, _, final_amount = calculate_investment_growth(ticker, start_date, monthly_investment)
                investment_data[ticker] = investment_growth
                investment_summary.append({
                    'ticker': ticker,
                    'total_investment': f"${total_investment:,.2f}",
                    'present_value': f"${final_amount:,.2f}"
                })
                cumulative_investment += total_investment
                cumulative_total_value += final_amount
            else:
                # Calculate stock performance
                price_data[ticker] = stock_prices  # Store stock prices for this ticker
                # Calculate percent change for stock price performance
                start_price = stock_prices.iloc[0]
                end_price = stock_prices.iloc[-1]
                percent_change = ((end_price - start_price) / start_price) * 100
                stock_summary.append({
                    'ticker': ticker,
                    'start_price': f"${start_price:,.2f}",
                    'end_price': f"${end_price:,.2f}",
                    'percent_change': f"{percent_change:.2f}%"
                })

    # Plot graph for investment growth or stock performance
    traces = []
    if monthly_investment:
        for ticker in valid_tickers:
            # Plot each ticker from its first available date, no alignment to common date
            traces.append(go.Scatter(x=investment_data[ticker].index, y=investment_data[ticker], mode='lines', name=f'{ticker} Investment Growth'))
        title_text = f'Growth of ${monthly_investment:,.2f} Invested Monthly in {tickers}'
    else:
        for ticker in valid_tickers:
            # Plot each ticker from its individual start date
            traces.append(go.Scatter(x=price_data[ticker].index, y=price_data[ticker], mode='lines', name=ticker))
        title_text = f'Stock Price Performance for {", ".join(valid_tickers)}'

    graph_figure = {
        'data': traces,
        'layout': go.Layout(
            title=dict(
                text=title_text,
                x=0.5,
                xanchor='center'
            ),
            xaxis={'title': 'Date'},
            yaxis={'title': 'Price ($)' if not monthly_investment else 'Value ($)', 'type': 'log'},
            hovermode='closest'
        )
    }

    graph_json = pio.to_json(graph_figure)

    return {
        "graph": graph_json,
        "summary": investment_summary if monthly_investment else stock_summary,
        "cumulative_investment": f"${cumulative_investment:,.2f}" if monthly_investment else None,
        "cumulative_total_value": f"${cumulative_total_value:,.2f}" if monthly_investment else None
    }
