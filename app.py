from flask import Flask, json, render_template, redirect, url_for, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
import plotly.figure_factory as ff
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

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = secrets.token_urlsafe(16)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

stripe.api_key = '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'
YOUR_DOMAIN = 'https://assetanalysis.info'

#te.login('1c15ef785f7244b:kvc8y6mv8z6c41a')
logging.basicConfig(level=logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


#User Settings (Load Users, Profile, Register, Login, Logout)
#------------------------------------------------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(150), nullable=False)
    last_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    subscription_status = db.Column(db.String(50), nullable=False, default='Free')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(first_name=first_name, last_name=last_name, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('profile'))
    return render_template('login.html')

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

#Stripe Setup (Subscriptions & Payments)
#------------------------------------------------------------

def subscription_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.subscription_status not in ['monthly', 'yearly']:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/check_subscription')
def check_subscription():
    if current_user.is_authenticated:
        return jsonify(subscription_status=current_user.subscription_status)
    else:
        return jsonify(subscription_status='none')

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

#Index.html and other pages
#-----------------------------------------------

@app.route('/')
def index():
    return render_template('index.html', current_user=current_user)

@app.route('/regression')
#@login_required
#@subscription_required
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
#@login_required
#@subscription_required
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

def run_script(script_path, function_name, stock, start_date):
    spec = importlib.util.spec_from_file_location("regression", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, function_name)
    return func(stock, start_date)

@app.route('/company_comparisons')
def company_comparisons():
    return render_template('company_comparisons.html')

@app.route('/compare_companies', methods=['POST'])
def compare_companies():
    data = request.get_json()
    tickers = data['tickers']
    if not tickers:
        return jsonify({"comparison": []})
    
    ticker = tickers[0]  # Use the first ticker to extract metrics
    stock = yf.Ticker(ticker)
    
    # Extract metrics from different data sources
    financials_metrics = stock.financials.index.tolist()
    balance_sheet_metrics = stock.balance_sheet.index.tolist()
    cashflow_metrics = stock.cashflow.index.tolist()
    info_metrics = list(stock.info.keys())
    
    return jsonify({
        "financials": [{"name": metric.replace('_', ' ').title(), "key": metric} for metric in financials_metrics],
        "balance_sheet": [{"name": metric.replace('_', ' ').title(), "key": metric} for metric in balance_sheet_metrics],
        "cash_flow": [{"name": metric.replace('_', ' ').title(), "key": metric} for metric in cashflow_metrics],
        "info": [{"name": metric.replace('_', ' ').title(), "key": metric} for metric in info_metrics]
    })

@app.route('/get_financials', methods=['POST'])
def get_financials():
    data = request.json
    tickers = data.get('tickers', [])
    metric = data.get('metric', None)
    period = data.get('period', 'yearly')  # Default to yearly if not specified
    
    financial_data = {}

    for ticker in tickers:
        ticker = ticker.strip().upper()
        print(f"Fetching data for ticker: {ticker}")
        try:
            stock = yf.Ticker(ticker)
            historical_data = None

            if metric in stock.info:
                # Special handling for info dictionary metrics
                financial_data[ticker] = [{"date": pd.Timestamp.today().strftime('%Y-%m-%d'), "value": stock.info[metric]}]
            else:
                if period == 'quarterly':
                    if metric in stock.quarterly_financials.index:
                        historical_data = stock.quarterly_financials.loc[metric]
                    elif metric in stock.quarterly_balance_sheet.index:
                        historical_data = stock.quarterly_balance_sheet.loc[metric]
                    elif metric in stock.quarterly_cashflow.index:
                        historical_data = stock.quarterly_cashflow.loc[metric]
                else:
                    if metric in stock.financials.index:
                        historical_data = stock.financials.loc[metric]
                    elif metric in stock.balance_sheet.index:
                        historical_data = stock.balance_sheet.loc[metric]
                    elif metric in stock.cashflow.index:
                        historical_data = stock.cashflow.loc[metric]

                if historical_data is not None:
                    # Filter out NaN values
                    historical_data = historical_data.dropna()
                    financial_data[ticker] = [{"date": date.strftime('%Y-%m-%d'), "value": value} for date, value in historical_data.items()]
                else:
                    financial_data[ticker] = 'N/A'
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            financial_data[ticker] = 'N/A'

    print(f"Final financial data: {financial_data}")
    return jsonify(financial_data)

@app.route('/portfolio_comparisons')
def portfolio_comparisons():
    return render_template('portfolio_comparisons.html')

@app.route('/run_portfolio_comparison', methods=['POST'])
def run_portfolio_comparison():
    data = request.get_json()
    tickers = data.get('tickers')
    allocations = data.get('allocations')
    benchmark = data.get('benchmark')
    start_date = data.get('start_date')
    
    logging.info(f"Form data received: {data}")
    logging.info(f"Tickers: {tickers}")
    logging.info(f"Allocations: {allocations}")
    logging.info(f"Benchmark: {benchmark}")
    logging.info(f"Start Date: {start_date}")
    
    # Filter out empty tickers and allocations
    filtered_tickers = [t for t in tickers if t]
    filtered_allocations = [a for a in allocations if a]
    
    logging.info(f"Filtered Tickers: {filtered_tickers}")
    logging.info(f"Filtered Allocations: {filtered_allocations}")

    # Dynamically load the function
    script_path = os.path.join(BASE_DIR, 'programs', 'Portfolio_Comparisons.py')
    spec = importlib.util.spec_from_file_location("portfolio_comparisons", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, 'run_portfolio_comparison')
    
    result = func(filtered_tickers, filtered_allocations, benchmark, start_date)
    return jsonify(result)

@app.route('/dcf_calculator', methods=['GET'])
def dcf():
    return render_template('dcf_calculator.html')

# Fetch DCF data and financials
@app.route('/fetch_dcf_data', methods=['POST'])
def fetch_dcf_data():
    data = request.json
    ticker = data.get('ticker')

    # Load dcf.py dynamically
    script_path = os.path.join(BASE_DIR, 'programs', 'DCF.py')
    spec = importlib.util.spec_from_file_location("dcf", script_path)
    dcf_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dcf_module)

    # Call the function from dcf.py
    return dcf_module.fetch_dcf_data_route(data)

# Run DCF Calculation
@app.route('/calculate_dcf', methods=['POST'])
def calculate_dcf():
    data = request.json

    # Load dcf.py dynamically
    script_path = os.path.join(BASE_DIR, 'programs', 'DCF.py')
    spec = importlib.util.spec_from_file_location("dcf", script_path)
    dcf_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dcf_module)

    # Call the function from dcf.py
    return dcf_module.calculate_dcf_route(data)


@app.route('/investment_tracker')
def unified_stock_tracker():
    return render_template('Investment_Tracker.html')

@app.route('/run_investment_tracker', methods=['POST'])
def run_stock_tracker():
    tickers = request.json.get('tickers')
    start_date = request.json.get('start_date')
    monthly_investment = request.json.get('monthly_investment', None)  # Optional

    if not tickers or not start_date:
        return jsonify({"error": "Please provide valid tickers and start date."}), 400

    # Dynamically load the Unified_Stock_Tracker.py script
    script_path = os.path.join(BASE_DIR, 'programs', 'Investment_Tracker.py')
    spec = importlib.util.spec_from_file_location("Unified_Stock_Tracker", script_path)
    unified_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(unified_module)

    # Call the run_stock_tracker function
    response = unified_module.run_stock_tracker(tickers, start_date, monthly_investment)

    if "error" in response:
        return jsonify({"error": response["error"]}), 400

    # Return the entire response, which includes graph, summary, and totals
    return jsonify({
        "graph": response["graph"],
        "summary": response["summary"],
        "cumulative_investment": response["cumulative_investment"],
        "cumulative_total_value": response["cumulative_total_value"]
    })

@app.route('/correlation_matrix')
def correlation_matrix():
    # Define default tickers and date range
    DEFAULT_TICKERS = ['AAPL', 'AMZN', 'GOOGL', 'TSLA', 'BTC-USD', 'ETH-USD', 'GC=F', 'SI=F', 'PL=F', 'PA=F', 'DX-Y.NYB', 'NVDA', 'MSFT', 'META', '^SPX', '^NDX', '^DJI']
    start_date = '1950-01-01'
    end_date = pd.Timestamp.today().strftime('%Y-%m-%d')

    # Dynamically load the Correlation_Matrix.py script
    script_path = os.path.join(BASE_DIR, 'programs', 'Correlation_Matrix.py')
    spec = importlib.util.spec_from_file_location("Correlation_Matrix", script_path)
    correlation_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(correlation_module)

    # Call the compute_correlation_matrix function from the loaded module
    graph_json = correlation_module.compute_correlation_matrix(','.join(DEFAULT_TICKERS), start_date, end_date)

    # Pass the JSON safely to the template
    return render_template('correlation_matrix.html', default_graph=json.loads(graph_json))

# Correlation matrix API for user-defined tickers
@app.route('/compute_correlation', methods=['POST'])
def compute_correlation():
    data = request.get_json()
    tickers = data.get('tickers', '')
    start_date = '1950-01-01'  # Fixed start date
    end_date = pd.Timestamp.today().strftime('%Y-%m-%d')  # Current date

    # Dynamically load the Correlation_Matrix.py script
    script_path = os.path.join(BASE_DIR, 'programs', 'Correlation_Matrix.py')
    spec = importlib.util.spec_from_file_location("Correlation_Matrix", script_path)
    correlation_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(correlation_module)

    # Call the compute_correlation_matrix function from the loaded module
    graph_json = correlation_module.compute_correlation_matrix(tickers, start_date, end_date)

    if graph_json:
        return jsonify({'graph': graph_json})
    else:
        return jsonify({'error': 'Unable to compute correlation matrix. Please check the input data.'})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', debug=True, port=5020)
