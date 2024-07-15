from matplotlib.ticker import ScalarFormatter
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import yfinance as yf
from datetime import datetime

def run_stock_linear_regression(stock_ticker, start_date):
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend

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

    # Plotting
    plt.figure(figsize=(10, 6))
    plt.plot(stock_data['Date'], stock_data['Price'], label='Actual Prices', color='black', linewidth=1)
    plt.plot(stock_data['Date'], stock_data['Linear_Fit'], label='Linear Fit', color='orange', linewidth=2)

    # Plot the bounds
    plt.plot(stock_data['Date'], stock_data['1_SD_Upper'], 'r--', label='1 SD Upper Bound', linewidth=1)
    plt.plot(stock_data['Date'], stock_data['1_SD_Lower'], 'g--', label='1 SD Lower Bound', linewidth=1)
    plt.plot(stock_data['Date'], stock_data['2_SD_Upper'], 'r-.', label='2 SD Upper Bound', linewidth=1, alpha=0.7)
    plt.plot(stock_data['Date'], stock_data['2_SD_Lower'], 'g-.', label='2 SD Lower Bound', linewidth=1, alpha=0.7)
    plt.plot(stock_data['Date'], stock_data['3_SD_Upper'], 'r-.', label='3 SD Upper Bound', linewidth=1, alpha=0.7)
    plt.plot(stock_data['Date'], stock_data['3_SD_Lower'], 'g-.', label='3 SD Lower Bound', linewidth=1, alpha=0.7)

    plt.plot(extended_dates, extended_prices, color='orange', linewidth=2)
    plt.plot(extended_dates, extended_1_SD_Upper, 'r--', linewidth=1)
    plt.plot(extended_dates, extended_1_SD_Lower, 'g--', linewidth=1)
    plt.plot(extended_dates, extended_2_SD_Upper, 'r-.', linewidth=1, alpha=0.7)
    plt.plot(extended_dates, extended_2_SD_Lower, 'g-.', linewidth=1, alpha=0.7)
    plt.plot(extended_dates, extended_3_SD_Upper, 'r-.', linewidth=1, alpha=0.7)
    plt.plot(extended_dates, extended_3_SD_Lower, 'g-.', linewidth=1, alpha=0.7)

    # Continue as in your original script
    plt.yscale('log')
    plt.gca().yaxis.set_major_formatter(ScalarFormatter())
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    plt.gca().xaxis.set_major_locator(mdates.YearLocator(5))
    plt.gcf().autofmt_xdate()
    plt.xlabel('Date')
    plt.ylabel('Stock Price ($)')
    plt.title(f'{stock_ticker} Stock Price with Linear Regression and Standard Deviation Bounds')
    plt.grid(True, which="both", ls="--", lw=0.5)
    plt.legend()
    plt.tight_layout()
    #plt.show()

    # Save plot to a byte stream
    img_bytes = io.BytesIO()
    plt.savefig(img_bytes, format='png')
    img_bytes.seek(0)
    plt.close()

    return img_bytes

def run_stock_logarithmic_regression(stock_ticker, start_date):
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend

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
    first_price = stock_data[stock_data['Price'] > 0].iloc[0]['Price']

    # Define the logarithmic model function
    def logarithmic_model(x, a, b):
        return np.maximum(first_price, 10**(a * np.log(np.maximum(x, 1)) + b))
    
    # Prepare data for curve fitting
    X = stock_data['Days']
    Y = stock_data['Price']

    # Fit the logarithmic model
    popt, _ = curve_fit(logarithmic_model, X, np.log(Y))
    a, b = popt

    # Apply the model to the dataset
    stock_data['Logarithmic_Fit'] = np.exp(logarithmic_model(stock_data['Days'], *popt))

    # Calculate the residuals and the standard deviation
    stock_data['Residuals'] = np.log(stock_data['Price']) - logarithmic_model(stock_data['Days'], *popt)
    std_dev = stock_data['Residuals'].std()

    # Extend the date range by 5 years
    last_day = stock_data['Date'].max()
    future_dates = pd.date_range(start=last_day, periods=3*365, freq='D', inclusive='right')
    future_days = (future_dates - first_day).days + 1

    # Predict prices using the existing model
    future_prices = np.exp(logarithmic_model(future_days, *popt))

    # Calculate the future 1SD and 2SD bounds
    future_1_SD_Upper = np.exp(logarithmic_model(future_days, *popt) + std_dev)
    future_1_SD_Lower = np.exp(logarithmic_model(future_days, *popt) - std_dev)
    future_2_SD_Upper = np.exp(logarithmic_model(future_days, *popt) + 2 * std_dev)
    future_2_SD_Lower = np.exp(logarithmic_model(future_days, *popt) - 2 * std_dev)

    # Calculate the 1SD bounds
    stock_data['1_SD_Upper'] = np.exp(logarithmic_model(stock_data['Days'], *popt) + std_dev)
    stock_data['1_SD_Lower'] = np.exp(logarithmic_model(stock_data['Days'], *popt) - std_dev)

    # Calculate the 2SD bounds
    stock_data['2_SD_Upper'] = np.exp(logarithmic_model(stock_data['Days'], *popt) + 2 * std_dev)
    stock_data['2_SD_Lower'] = np.exp(logarithmic_model(stock_data['Days'], *popt) - 2 * std_dev)

    # Combine future predictions with existing data
    extended_dates = pd.concat([stock_data['Date'], pd.Series(future_dates)])
    extended_prices = np.concatenate([stock_data['Logarithmic_Fit'], future_prices])
    extended_1_SD_Upper = np.concatenate([stock_data['1_SD_Upper'], future_1_SD_Upper])
    extended_1_SD_Lower = np.concatenate([stock_data['1_SD_Lower'], future_1_SD_Lower])
    extended_2_SD_Upper = np.concatenate([stock_data['2_SD_Upper'], future_2_SD_Upper])
    extended_2_SD_Lower = np.concatenate([stock_data['2_SD_Lower'], future_2_SD_Lower])

    # Plotting
    plt.figure(figsize=(10, 6))
    plt.plot(stock_data['Date'], stock_data['Price'], label='Actual Prices', color='black', linewidth=1)
    plt.plot(stock_data['Date'], stock_data['Logarithmic_Fit'], label='Logarithmic Fit', color='orange', linewidth=2)

    # Plot the bounds
    plt.plot(stock_data['Date'], stock_data['1_SD_Upper'], 'r--', label='1 SD Upper Bound', linewidth=1)
    plt.plot(stock_data['Date'], stock_data['1_SD_Lower'], 'g--', label='1 SD Lower Bound', linewidth=1)
    plt.plot(stock_data['Date'], stock_data['2_SD_Upper'], 'r-.', label='2 SD Upper Bound', linewidth=1, alpha=0.7)
    plt.plot(stock_data['Date'], stock_data['2_SD_Lower'], 'g-.', label='2 SD Lower Bound', linewidth=1, alpha=0.7)

    plt.plot(extended_dates, extended_prices, color='orange', linewidth=2)
    plt.plot(extended_dates, extended_1_SD_Upper, 'r--', linewidth=1)
    plt.plot(extended_dates, extended_1_SD_Lower, 'g--', linewidth=1)
    plt.plot(extended_dates, extended_2_SD_Upper, 'r-.', linewidth=1, alpha=0.7)
    plt.plot(extended_dates, extended_2_SD_Lower, 'g-.', linewidth=1, alpha=0.7)

    # Continue as in your original script
    plt.yscale('log')
    plt.gca().yaxis.set_major_formatter(ScalarFormatter())
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    plt.gca().xaxis.set_major_locator(mdates.YearLocator())
    plt.gcf().autofmt_xdate()
    plt.xlabel('Date')
    plt.ylabel('Stock Price ($)')
    plt.title(f'{stock_ticker} Stock Price with Logarithmic Regression and Standard Deviation Bounds')
    plt.grid(True, which="both", ls="--", lw=0.5)
    plt.legend()
    plt.tight_layout()
    #plt.show()

    # Save plot to a byte stream
    img_bytes = io.BytesIO()
    plt.savefig(img_bytes, format='png')
    img_bytes.seek(0)
    plt.close()

    return img_bytes