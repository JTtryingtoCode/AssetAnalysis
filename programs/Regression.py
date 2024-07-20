import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
import plotly.graph_objs as go
import yfinance as yf
from datetime import datetime
import json
import plotly.utils

def run_stock_linear_regression(stock_ticker, start_date):
    # Get the current date
    end_date = datetime.today().strftime('%Y-%m-%d')

    # Fetch stock data using yfinance
    stock_data = yf.download(stock_ticker, start=start_date, end=end_date)

    # Data cleaning and processing
    stock_data.reset_index(inplace=True)
    stock_data = stock_data[['Date', 'Close']].rename(columns={'Close': 'Price'})
    
    # Ensure there are no missing values
    stock_data.dropna(subset=['Price'], inplace=True)
    
    # Find the first day with a non-zero price
    first_day = stock_data['Date'].min()
    stock_data['Days'] = (stock_data['Date'] - first_day).dt.days + 1  # Ensure x starts from 1

    # Define the linear model function
    def linear_model(x, a, b):
        return a * x + b
    
    # Prepare data for curve fitting
    X = stock_data['Days']
    Y = stock_data['Price']

    # Fit the linear model
    popt, _ = curve_fit(linear_model, X, np.log(Y))
    a, b = popt

    # Apply the model to the dataset
    stock_data['Linear_Fit'] = np.exp(linear_model(stock_data['Days'], *popt))

    # Calculate the residuals and the standard deviation
    stock_data['Residuals'] = np.log(stock_data['Price']) - linear_model(stock_data['Days'], *popt)
    std_dev = stock_data['Residuals'].std()

    # Extend the date range by 5 years
    last_day = stock_data['Date'].max()
    future_dates = pd.date_range(start=last_day, periods=4*365, freq='D', inclusive='right')
    future_days = (future_dates - first_day).days + 1

    # Predict prices using the existing model
    future_prices = np.exp(linear_model(future_days, *popt))

    # Calculate the future 1SD and 2SD bounds
    future_1_SD_Upper = np.exp(linear_model(future_days, *popt) + std_dev)
    future_1_SD_Lower = np.exp(linear_model(future_days, *popt) - std_dev)
    future_2_SD_Upper = np.exp(linear_model(future_days, *popt) + 2 * std_dev)
    future_2_SD_Lower = np.exp(linear_model(future_days, *popt) - 2 * std_dev)
    future_3_SD_Upper = np.exp(linear_model(future_days, *popt) + 3 * std_dev)
    future_3_SD_Lower = np.exp(linear_model(future_days, *popt) - 3 * std_dev)

    # Calculate the 1SD bounds
    stock_data['1_SD_Upper'] = np.exp(linear_model(stock_data['Days'], *popt) + std_dev)
    stock_data['1_SD_Lower'] = np.exp(linear_model(stock_data['Days'], *popt) - std_dev)

    # Calculate the 2SD bounds
    stock_data['2_SD_Upper'] = np.exp(linear_model(stock_data['Days'], *popt) + 2 * std_dev)
    stock_data['2_SD_Lower'] = np.exp(linear_model(stock_data['Days'], *popt) - 2 * std_dev)

    # Calculate the 3SD bounds
    stock_data['3_SD_Upper'] = np.exp(linear_model(stock_data['Days'], *popt) + 3 * std_dev)
    stock_data['3_SD_Lower'] = np.exp(linear_model(stock_data['Days'], *popt) - 3 * std_dev)

    # Combine future predictions with existing data
    extended_dates = pd.concat([stock_data['Date'], pd.Series(future_dates)])
    extended_prices = np.concatenate([stock_data['Linear_Fit'], future_prices])
    extended_1_SD_Upper = np.concatenate([stock_data['1_SD_Upper'], future_1_SD_Upper])
    extended_1_SD_Lower = np.concatenate([stock_data['1_SD_Lower'], future_1_SD_Lower])
    extended_2_SD_Upper = np.concatenate([stock_data['2_SD_Upper'], future_2_SD_Upper])
    extended_2_SD_Lower = np.concatenate([stock_data['2_SD_Lower'], future_2_SD_Lower])
    extended_3_SD_Upper = np.concatenate([stock_data['3_SD_Upper'], future_3_SD_Upper])
    extended_3_SD_Lower = np.concatenate([stock_data['3_SD_Lower'], future_3_SD_Lower])

    # Create Plotly traces
    actual_prices_trace = go.Scatter(x=stock_data['Date'], y=stock_data['Price'], mode='lines', name='Actual Prices', line=dict(color='black'))
    linear_fit_trace = go.Scatter(x=stock_data['Date'], y=stock_data['Linear_Fit'], mode='lines', name='Linear Fit', line=dict(color='orange'))

    upper_1sd_trace = go.Scatter(x=extended_dates, y=extended_1_SD_Upper, mode='lines', name='1 SD Upper Bound', line=dict(color='red', dash='dash'))
    lower_1sd_trace = go.Scatter(x=extended_dates, y=extended_1_SD_Lower, mode='lines', name='1 SD Lower Bound', line=dict(color='green', dash='dash'))
    
    upper_2sd_trace = go.Scatter(x=extended_dates, y=extended_2_SD_Upper, mode='lines', name='2 SD Upper Bound', line=dict(color='red', dash='dot'))
    lower_2sd_trace = go.Scatter(x=extended_dates, y=extended_2_SD_Lower, mode='lines', name='2 SD Lower Bound', line=dict(color='green', dash='dot'))
    
    upper_3sd_trace = go.Scatter(x=extended_dates, y=extended_3_SD_Upper, mode='lines', name='3 SD Upper Bound', line=dict(color='red', dash='dashdot'))
    lower_3sd_trace = go.Scatter(x=extended_dates, y=extended_3_SD_Lower, mode='lines', name='3 SD Lower Bound', line=dict(color='green', dash='dashdot'))

    # Create the layout
    layout = go.Layout(
    title=dict(
        text=f'{stock_ticker} Stock Price with Linear Regression and Standard Deviation Bounds',
        x=0.5,
        xanchor='center'
    ),
    xaxis=dict(title='Date', type='date'),
    yaxis=dict(title='Stock Price ($)', type='log'),
    legend=dict(x=0, y=1),
    hovermode='closest',
    autosize=True,
    margin=dict(l=40, r=40, b=40, t=40)
    )

    # Extending the linear fit line into the future
    combined_dates = pd.concat([stock_data['Date'], pd.Series(future_dates)])
    combined_linear_fit = np.concatenate([stock_data['Linear_Fit'], future_prices])

    linear_fit_trace = go.Scatter(x=combined_dates, y=combined_linear_fit, mode='lines', name='Linear Fit', line=dict(color='orange'))

    # Create the figure
    fig = go.Figure(data=[actual_prices_trace, linear_fit_trace, upper_1sd_trace, lower_1sd_trace, upper_2sd_trace, lower_2sd_trace, upper_3sd_trace, lower_3sd_trace], layout=layout)

    # Convert the figure to JSON
    graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return graph_json
