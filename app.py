from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import importlib.util
import yfinance as yf
import logging
import stripe
import secrets
import os
import pandas as pd
import plotly.graph_objs as go
import plotly.io as pio
from datetime import datetime, timedelta
import tradingeconomics as te
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = secrets.token_urlsafe(16)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

stripe.api_key = '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'
YOUR_DOMAIN = 'https://assetanalysis.info'

te.login('1c15ef785f7244b:kvc8y6mv8z6c41a')

logging.basicConfig(level=logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    subscription_status = db.Column(db.String(50), nullable=False, default='Free')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

def subscription_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.subscription_status not in ['monthly', 'yearly']:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html', current_user=current_user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        subscription = request.form.get('subscription')
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(email=email, password=hashed_password, subscription_status=subscription)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/check_subscription')
def check_subscription():
    if current_user.is_authenticated:
        return jsonify(subscription_status=current_user.subscription_status)
    else:
        return jsonify(subscription_status='none')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/change_subscription', methods=['POST'])
@login_required
def change_subscription():
    data = request.get_json()
    new_subscription = data.get('subscription')
    if new_subscription == 'Free':
        current_user.subscription_status = 'Free'
        db.session.commit()
        return jsonify(success=True)
    else:
        return jsonify(success=False)

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    event = None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, 'whsec_Y0UgzS4eUzwHQKYMPr6fbwXD9gDCarI0')
    except ValueError as e:
        logging.error(f"ValueError: {e}")
        return jsonify(success=False), 400
    except stripe.error.SignatureVerificationError as e:
        logging.error(f"SignatureVerificationError: {e}")
        return jsonify(success=False), 400

    logging.info(f"Received event: {event}")

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session['customer_details']['email']
        subscription_id = session['subscription']
        logging.info(f"Processing session for email: {customer_email}, subscription_id: {subscription_id}")

        user = User.query.filter_by(email=customer_email).first()
        if user:
            # Get the subscription plan from Stripe
            subscription = stripe.Subscription.retrieve(subscription_id)
            plan_id = subscription['items']['data'][0]['plan']['id']
            if plan_id == 'price_1PfVMTIH81wHt27NyPkTnlNY':  # Replace with your actual Stripe plan ID for monthly
                user.subscription_status = 'monthly'
            elif plan_id == 'price_1PfVKoIH81wHt27NSTi1jJ4M':  # Replace with your actual Stripe plan ID for yearly
                user.subscription_status = 'yearly'
            db.session.commit()
            logging.info(f"Updated user {user.email} subscription to {user.subscription_status}")
        else:
            logging.error(f"User with email {customer_email} not found")

    return jsonify(success=True), 200


@app.route('/regression')
@login_required
@subscription_required
def regression():
    return render_template('regression.html')

@app.route('/run_regression', methods=['POST'])
def run_regression():
    stock = request.json.get('stock')
    start_date_choice = request.json.get('start_date')

    if start_date_choice == 'ipo':
        stock_info = yf.Ticker(stock).info
        start_date = stock_info.get('ipoDate', '1850-01-01')
    else:
        start_date = start_date_choice

    script_path = os.path.join(BASE_DIR, 'programs', 'Regression.py')
    graph_json = run_script(script_path, 'run_stock_linear_regression', stock, start_date)

    return jsonify({"graph": graph_json})

@app.route('/portfolio_optimizer')
@login_required
@subscription_required
def sharpe_ratio():
    return render_template('portfolio_optimizer.html')

@app.route('/run_sharpe_ratio', methods=['POST'])
def run_sharpe_ratio():
    tickers = request.json.get('tickers')
    logging.info(f"Received tickers: {tickers}")

    tickers_list = [ticker.strip().upper() for ticker in tickers]
    logging.info(f"Processed tickers list: {tickers_list}")

    script_path = os.path.join(BASE_DIR, 'programs', 'Sharpe_Ratio.py')
    spec = importlib.util.spec_from_file_location("sharpe_ratio", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, 'run_sharpe_ratio')

    result = func(tickers_list)
    return jsonify(result)

@app.route('/investment_growth')
def investment_growth():
    return render_template('investment_growth.html')

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

@app.route('/stock_price_performance')
def stock_price_performance():
    return render_template('stock_price_performance.html')

@app.route('/generate_stock_graph', methods=['POST'])
def generate_stock_graph():
    tickers = request.json.get('tickers')
    start_date = request.json.get('start_date')

    if not tickers or not start_date:
        return jsonify({"error": "Please provide valid tickers and start date."}), 400

    tickers_list = [ticker.strip().upper() for ticker in tickers.split(',')]
    start_date = pd.Timestamp(start_date)

    data = []
    for ticker in tickers_list:
        stock_data = yf.download(ticker, start=start_date)
        if not stock_data.empty:
            stock_data['Cumulative Percent Change'] = ((stock_data['Adj Close'] / stock_data['Adj Close'].iloc[0]) - 1) * 100
            trace = go.Scatter(
                x=stock_data.index,
                y=stock_data['Cumulative Percent Change'],
                mode='lines',
                name=ticker
            )
            data.append(trace)

    layout = go.Layout(
        title=f'Stock Price Performance since {start_date.strftime("%Y-%m-%d")}',
        xaxis=dict(title='Date'),
        yaxis=dict(title='Cumulative Percent Change (%)', side='right'),
        legend=dict(x=0, y=1),
        hovermode='closest'
    )

    fig = go.Figure(data=data, layout=layout)
    graph_json = pio.to_json(fig)

    return jsonify({"graph": graph_json})

def run_script(script_path, function_name, stock, start_date):
    spec = importlib.util.spec_from_file_location("regression", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, function_name)
    return func(stock, start_date)

@app.route('/company_comparisons')
@login_required
@subscription_required
def company_comparisons():
    return render_template('company_comparisons.html')

@app.route('/compare_companies', methods=['POST'])
def compare_companies():
    data = request.get_json()
    tickers = data['tickers']
    comparison = []
    # Add logic to get company comparison metrics from Trading Economics API
    metrics = ["assets", "cost_of_sales", "current_liabilities", "dividend_yield", "ebitda",
               "eps_earnings_per_share", "gross_profit_on_sales", "interest_income",
               "market_capitalization", "operating_expenses", "ordinary_share_capital",
               "pre_tax_profit", "selling_and_administration_expenses", "trade_creditors",
               "cash_and_equivalent", "current_assets", "debt", "ebit", "employees",
               "equity_capital_and_reserves", "interest_expense_on_debt", "loan_capital",
               "net_income", "operating_profit", "pe_price_to_earnings", "sales_revenues",
               "stock", "trade_debtors"]
    for metric in metrics:
        comparison.append({"name": metric.replace('_', ' ').title(), "key": metric})
    return jsonify({"comparison": comparison})

@app.route('/get_financials', methods=['POST'])
def get_financials():
    data = request.json
    tickers = data.get('tickers', [])
    metric = data.get('metric', None)
    
    financial_data = {}
    
    for ticker in tickers:
        ticker = ticker.strip().upper()
        if ':US' not in ticker:
            ticker += ':US'
        print(f"Fetching data for ticker: {ticker}")
        
        retries = 3  # Number of retries
        for attempt in range(retries):
            try:
                response = requests.get(f"https://api.tradingeconomics.com/financials/historical/{ticker}:{metric}?d1=1900-01-01&c=1c15ef785f7244b:kvc8y6mv8z6c41a")
                response.raise_for_status()
                response_json = response.json()
                print(f"Raw response for {ticker}: {response_json}")

                financial_data[ticker.split(':')[0]] = response_json
                break  # Exit the retry loop if the request was successful
                
            except requests.exceptions.HTTPError as http_err:
                if response.status_code == 429:  # Rate limit exceeded
                    if attempt < retries - 1:
                        print(f"Rate limit exceeded for {ticker}. Retrying in 5 seconds...")
                        time.sleep(5)  # Wait before retrying
                        continue  # Retry the request
                    else:
                        print(f"HTTP error occurred for {ticker}: {http_err}")
                        financial_data[ticker.split(':')[0]] = 'N/A'
                else:
                    print(f"HTTP error occurred for {ticker}: {http_err}")
                    financial_data[ticker.split(':')[0]] = 'N/A'
                break  # Exit the retry loop for non-rate-limit errors
                
            except requests.exceptions.RequestException as req_err:
                print(f"Request error occurred for {ticker}: {req_err}")
                financial_data[ticker.split(':')[0]] = 'N/A'
                break  # Exit the retry loop
                
            except ValueError as json_err:
                print(f"JSON decode error occurred for {ticker}: {json_err}")
                print(f"Response content: {response.content}")
                financial_data[ticker.split(':')[0]] = 'N/A'
                break  # Exit the retry loop
                
            except Exception as e:
                print(f"Unexpected error occurred for {ticker}: {e}")
                financial_data[ticker.split(':')[0]] = 'N/A'
                break  # Exit the retry loop
    
    print(f"Final financial data: {financial_data}")
    return jsonify(financial_data)

@app.route('/cancel_subscription', methods=['POST'])
@login_required
def cancel_subscription():
    if current_user.subscription_status != 'Free':
        current_user.subscription_status = 'Free'
        db.session.commit()
    return redirect(url_for('subscription_cancelled'))

@app.route('/subscription_cancelled')
def subscription_cancelled():
    return render_template('cancel.html')

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', debug=True, port=5000)
