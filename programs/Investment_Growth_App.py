import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
import plotly.io as pio
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

def calculate_investment_growth(ticker, start_date, monthly_investment):
    stock_data = yf.download(ticker, start=start_date)
    
    if stock_data.empty:
        return None, None, None, None, None

    stock_data['Price'] = stock_data['Adj Close']
    
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
            current_investment += monthly_investment
            stock_data.loc[month:, 'Investment Value'] += (monthly_investment / monthly_start_price) * stock_data.loc[month:, 'Price']
            if month == first_trading_days[0]:
                stock_data.loc[month, 'Investment Value'] = monthly_investment

    final_amount = stock_data['Investment Value'].iloc[-1]
    total_investment = len(first_trading_days) * monthly_investment
    percent_change = ((final_amount - total_investment) / total_investment) * 100

    return stock_data['Investment Value'], total_investment, percent_change, first_valid_date


@app.route('/')
def index():
    return render_template('investment_growth.html')

@app.route('/generate_investment_growth_graph', methods=['POST'])
def generate_investment_growth_graph():
    tickers = request.json.get('tickers')
    start_date = request.json.get('start_date')
    monthly_investment = request.json.get('monthly_investment')

    if not tickers or not start_date or not monthly_investment:
        return jsonify({"error": "Please provide valid tickers, start date, and monthly investment."}), 400

    tickers_list = [ticker.strip().upper() for ticker in tickers.split(',')]
    start_date = pd.Timestamp(start_date)
    monthly_investment = float(monthly_investment)

    # Determine the earliest common start date
    earliest_common_date = pd.Timestamp('2100-01-01')
    data = []
    for ticker in tickers_list:
        investment_growth, total_investment, percent_change, first_valid_date = calculate_investment_growth(ticker, start_date, monthly_investment)
        if investment_growth is not None:
            earliest_common_date = min(earliest_common_date, first_valid_date)
            trace = go.Scatter(
                x=investment_growth.index,
                y=investment_growth,
                mode='lines',
                name=ticker
            )
            data.append((trace, investment_growth))

    # Align all investment growth data to the earliest common date
    aligned_data = []
    for trace, investment_growth in data:
        aligned_growth = investment_growth[investment_growth.index >= earliest_common_date]
        aligned_growth.iloc[0] = monthly_investment  # Ensure initial value is the monthly investment
        trace['x'] = aligned_growth.index
        trace['y'] = aligned_growth
        aligned_data.append(trace)

    layout = go.Layout(
        title=f'Growth of ${monthly_investment} Invested Monthly Since {earliest_common_date.strftime("%Y-%m-%d")}',
        xaxis=dict(title='Date'),
        yaxis=dict(title='Investment Value ($)', type='log', side='right'),
        legend=dict(x=0, y=1),
        hovermode='closest'
    )

    fig = go.Figure(data=aligned_data, layout=layout)
    graph_json = pio.to_json(fig)

    return jsonify({"graph": graph_json})
