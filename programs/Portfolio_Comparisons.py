import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
import plotly.io as pio
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)

def run_portfolio_comparison(tickers, allocations, benchmark, start_date):
    allocations = [float(a) for a in allocations]
    
    #logging.info(f"Received tickers: {tickers}")
    #logging.info(f"Received allocations: {allocations}")
    #logging.info(f"Selected benchmark: {benchmark}")
    #logging.info(f"Selected start date: {start_date}")

    if sum(allocations) != 100:
        raise ValueError("Allocations must sum to 100.")

    # Normalize allocations to sum to 1
    allocations = [a / 100 for a in allocations]
    #logging.info(f"Processed allocations: {allocations}")
    #logging.info(f"Sum of allocations: {sum(allocations)}")

    end_date = datetime.today().strftime('%Y-%m-%d')

    data = pd.DataFrame()
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)
            hist.index = hist.index.tz_convert('UTC').normalize()
            hist[ticker] = hist['Close'].pct_change()
            if data.empty:
                data = hist[[ticker]]
            else:
                data = data.join(hist[[ticker]], how='outer')
            logging.info(f"Fetched data for {ticker}")
        except Exception as e:
            logging.error(f"Could not fetch data for {ticker}: {e}")

    try:
        benchmark_stock = yf.Ticker(benchmark)
        benchmark_hist = benchmark_stock.history(start=start_date, end=end_date)
        benchmark_hist.index = benchmark_hist.index.tz_convert('UTC').normalize()
        benchmark_hist[benchmark] = benchmark_hist['Close'].pct_change()
        data = data.join(benchmark_hist[[benchmark]], how='outer')
        logging.info(f"Fetched data for {benchmark}")
    except Exception as e:
        logging.error(f"Could not fetch data for {benchmark}: {e}")

    #logging.info(f"Combined data head:\n{data.head()}")
    #logging.info(f"Combined data tail:\n{data.tail()}")

    data = data.dropna()

    portfolio_return = (data[tickers] * allocations).sum(axis=1)
    cumulative_portfolio_return = (1 + portfolio_return).cumprod() * 10000
    cumulative_benchmark_return = (1 + data[benchmark]).cumprod() * 10000

    #logging.info(f"Cumulative portfolio return head:\n{cumulative_portfolio_return.head()}")
    #logging.info(f"Cumulative benchmark return head:\n{cumulative_benchmark_return.head()}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cumulative_portfolio_return.index, y=cumulative_portfolio_return.values, mode='lines', name='Portfolio'))
    fig.add_trace(go.Scatter(x=cumulative_benchmark_return.index, y=cumulative_benchmark_return.values, mode='lines', name=benchmark))

    fig.update_layout(
        title={
            'text': f'Portfolio Comparison: Portfolio vs. {benchmark}',
            'x': 0.5,  # Center the title
            'xanchor': 'center'
        },
        xaxis_title='Date',
        yaxis_title='Value of $10,000',
        yaxis_type="log"
    )

    graph_json = pio.to_json(fig)
    return {'graph': graph_json}
