import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.io as pio
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

def run_sharpe_ratio(tickers):
    start_date = '1850-01-01'
    present_date = datetime.today().strftime('%Y-%m-%d')
    end_date = present_date
    RFR = 0.0535
    no_of_simulations = 5000

    returns = pd.DataFrame()
    earliest_start_date = pd.Timestamp(start_date).tz_localize('UTC')

    for ticker in tickers:
        stock = yf.Ticker(ticker)
        try:
            hist = stock.history(start=start_date, end=end_date)
            hist.index = hist.index.tz_convert('UTC').normalize()  # Convert index to UTC and normalize to remove time
            hist[ticker] = hist['Close'].pct_change()
            if returns.empty:
                returns = hist[[ticker]]
            else:
                returns = returns.join(hist[[ticker]], how='outer')
            logging.info(f"Fetched data for {ticker}")
            
            ticker_start_date = hist.index.min()
            if ticker_start_date > earliest_start_date:
                earliest_start_date = ticker_start_date
        except Exception as e:
            logging.error(f"Could not fetch data for {ticker}: {e}")

    if returns.empty:
        raise ValueError("No valid data fetched for the tickers provided.")

    # Drop NaN values and keep only rows with complete data
    returns.dropna(inplace=True)
    returns = returns[returns.index >= earliest_start_date]

    logging.info(f"Combined returns dataframe (last entries):\n{returns.tail()}")

    if returns.empty:
        raise ValueError("No valid data fetched for the tickers provided.")

    portfolio_returns = []
    portfolio_risks = []
    sharpe_ratios = []
    portfolio_weights = []

    for portfolio in range(no_of_simulations):
        weights = np.random.random_sample(len(tickers))
        weights = weights / np.sum(weights)
        weights = np.round(weights, 3)
        weight_dict = {tickers[i]: weights[i] for i in range(len(tickers))}
        portfolio_weights.append(weight_dict)
        
        annualized_return = np.sum(returns.mean() * weights) * 365
        portfolio_returns.append(annualized_return)
        
        matrix_covariance = returns.cov() * 365
        portfolio_variance = np.dot(weights.T, np.dot(matrix_covariance, weights))
        portfolio_stdv = np.sqrt(portfolio_variance)
        portfolio_risks.append(portfolio_stdv)
        
        sharpe_ratio = (annualized_return - RFR) / portfolio_stdv
        sharpe_ratios.append(sharpe_ratio)

    portfolio_returns = np.array(portfolio_returns)
    portfolio_risks = np.array(portfolio_risks)
    sharpe_ratios = np.array(sharpe_ratios)

    portfolio_metrics = [portfolio_returns, portfolio_risks, sharpe_ratios, portfolio_weights]
    portfolios_df = pd.DataFrame(portfolio_metrics).T
    portfolios_df.columns = ["Return", "Risk", "Sharpe", "Weights"]

    logging.info(f"Portfolios dataframe before dropping NaNs:\n{portfolios_df.head()}")

    portfolios_df.dropna(inplace=True)
    logging.info(f"Portfolios dataframe after dropping NaNs:\n{portfolios_df.head()}")

    if portfolios_df.empty:
        raise ValueError("No valid portfolios generated after removing NaN values.")

    try:
        min_risk = portfolios_df.iloc[portfolios_df['Risk'].astype(float).idxmin()]
        max_return = portfolios_df.iloc[portfolios_df['Return'].astype(float).idxmax()]
        max_sharpe = portfolios_df.iloc[portfolios_df['Sharpe'].astype(float).idxmax()]
    except Exception as e:
        logging.error(f"Error selecting min/max portfolios: {e}")
        raise

    min_risk_weights = min_risk['Weights']
    max_return_weights = max_return['Weights']

    tickers = min_risk['Weights'].keys()
    average_weights = {ticker: (min_risk_weights[ticker] + max_return_weights[ticker]) / 2 for ticker in tickers}
    average_weights_array = np.array(list(average_weights.values()))

    average_return = np.sum(returns.mean() * average_weights_array) * 365
    average_risk = np.sqrt(np.dot(average_weights_array.T, np.dot(returns.cov() * 365, average_weights_array)))
    average_sharpe = (average_return - RFR) / average_risk if average_risk != 0 else 0

    text_output = f"Minimum Risk Portfolio Weights:\n"
    for ticker, weight in min_risk['Weights'].items():
        text_output += f"{ticker}: {weight*100:.1f}%\n"
    text_output += f"Return: {min_risk['Return']*100:.2f}%\n"
    text_output += f"Risk: {min_risk['Risk']*100:.2f}%\n"
    text_output += f"Sharpe Ratio: {min_risk['Sharpe']:.2f}\n\n"

    text_output += "Maximum Return Portfolio Weights:\n"
    for ticker, weight in max_return['Weights'].items():
        text_output += f"{ticker}: {weight*100:.1f}%\n"
    text_output += f"Return: {max_return['Return']*100:.2f}%\n"
    text_output += f"Risk: {max_return['Risk']*100:.2f}%\n"
    text_output += f"Sharpe Ratio: {max_return['Sharpe']:.2f}\n\n"

    text_output += "Maximum Sharpe Ratio Portfolio Weights:\n"
    for ticker, weight in max_sharpe['Weights'].items():
        text_output += f"{ticker}: {weight*100:.1f}%\n"
    text_output += f"Return: {max_sharpe['Return']*100:.2f}%\n"
    text_output += f"Risk: {max_sharpe['Risk']*100:.2f}%\n"
    text_output += f"Sharpe Ratio: {max_sharpe['Sharpe']:.2f}\n\n"

    text_output += "Average Weights between Minimum Risk and Maximum Return Portfolios:\n"
    for ticker, weight in average_weights.items():
        text_output += f"{ticker}: {weight*100:.1f}%\n"
    text_output += f"Return: {average_return * 100:.2f}%\n"
    text_output += f"Risk: {average_risk * 100:.2f}%\n"
    text_output += f"Sharpe Ratio: {average_sharpe:.2f}\n"

    scatter = go.Scatter(
        x=portfolio_risks,
        y=portfolio_returns,
        mode='markers',
        marker=dict(
            size=7.5,
            color=sharpe_ratios[1:],
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title='Sharpe Ratio')
        ),
        text=[f"Weights: {weights}" for weights in portfolio_weights]
    )

    max_sharpe_marker = go.Scatter(
        x=[max_sharpe['Risk']],
        y=[max_sharpe['Return']],
        mode='markers',
        marker=dict(color='red', size=15, symbol='star'),
        name='Max Sharpe'
    )

    max_return_marker = go.Scatter(
        x=[max_return['Risk']],
        y=[max_return['Return']],
        mode='markers',
        marker=dict(color='blue', size=15, symbol='x'),
        name='Max Return'
    )

    min_risk_marker = go.Scatter(
        x=[min_risk['Risk']],
        y=[min_risk['Return']],
        mode='markers',
        marker=dict(color='green', size=15, symbol='triangle-up'),
        name='Min Risk'
    )

    average_marker = go.Scatter(
        x=[average_risk],
        y=[average_return],
        mode='markers',
        marker=dict(color='magenta', size=15, symbol='circle'),
        name='Average Portfolio'
    )

    layout = go.Layout(
        title=dict(
            text=f"Optimized Portfolios for {', '.join(tickers)}",
            x=0.5,  # Center the title
            xanchor='center'
        ),
        xaxis=dict(title="Volatility (Risk)"),
        yaxis=dict(title="Returns"),
        legend=dict(x=0, y=1),
        hovermode='closest',
        autosize=True,
    )

    fig = go.Figure(data=[scatter, max_sharpe_marker, max_return_marker, min_risk_marker, average_marker], layout=layout)
    graph_json = pio.to_json(fig)

    # Calculate the cumulative returns for the new portfolios and benchmarks
    data = pd.DataFrame()
    for ticker in list(tickers) + ['SPY', 'QQQ', 'DIA']:
        stock = yf.Ticker(ticker)
        try:
            hist = stock.history(start=earliest_start_date, end=end_date)
            hist.index = hist.index.tz_convert('UTC').normalize()
            hist[ticker] = hist['Close'].pct_change()
            if data.empty:
                data = hist[[ticker]]
            else:
                data = data.join(hist[[ticker]], how='outer')
            logging.info(f"Fetched data for {ticker}")
        except Exception as e:
            logging.error(f"Could not fetch data for {ticker}: {e}")

    data = data.dropna()

    fig2 = go.Figure()

    portfolio_names = ['Minimum Risk Portfolio', 'Maximum Return Portfolio', 'Maximum Sharpe Ratio Portfolio', 'Average Portfolio']
    portfolios = {
        'Minimum Risk Portfolio': min_risk_weights,
        'Maximum Return Portfolio': max_return_weights,
        'Maximum Sharpe Ratio Portfolio': max_sharpe['Weights'],
        'Average Portfolio': average_weights
    }

    for portfolio_name, weights in portfolios.items():
        portfolio_return = (data[tickers] * weights).sum(axis=1)
        cumulative_portfolio_return = (1 + portfolio_return).cumprod() * 10000
        fig2.add_trace(go.Scatter(x=cumulative_portfolio_return.index, y=cumulative_portfolio_return, mode='lines', name=portfolio_name))

    for benchmark in ['SPY', 'QQQ', 'DIA']:
        cumulative_benchmark_return = (1 + data[benchmark]).cumprod() * 10000
        fig2.add_trace(go.Scatter(x=cumulative_benchmark_return.index, y=cumulative_benchmark_return, mode='lines', name=benchmark))

    fig2.update_layout(
        title={
            'text': 'Portfolio Performance Comparison of $10,000',
            'x': 0.5,  # Center the title
            'xanchor': 'center'
        },
        xaxis_title='Date',
        yaxis_title='Value',
        yaxis_type="log",
    )

    performance_graph = pio.to_json(fig2)

    return {'graph': graph_json, 'text': text_output, 'performance_graph': performance_graph}
