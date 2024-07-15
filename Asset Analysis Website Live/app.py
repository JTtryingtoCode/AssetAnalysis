from flask import Flask, render_template, request, send_file, jsonify
import importlib.util
import io
import yfinance as yf
import logging
import os

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/regression')
def regression():
    return render_template('regression.html')

@app.route('/sharpe_ratio')
def sharpe_ratio():
    return render_template('sharpe_ratio.html')

@app.route('/investment_growth')
def investment_growth():
    return render_template('investment_growth.html')

@app.route('/run_regression', methods=['POST'])
def run_regression():
    stock = request.json.get('stock')
    start_date_choice = request.json.get('start_date')

    if start_date_choice == 'ipo':
        stock_info = yf.Ticker(stock).info
        start_date = stock_info.get('ipoDate', '1950-01-01')
    else:
        start_date = start_date_choice

    script_path = os.path.join(BASE_DIR, 'programs', 'Regression.py')
    img_bytes = run_script(script_path, 'run_stock_linear_regression', stock, start_date)

    return send_file(img_bytes, mimetype='image/png')

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

def import_create_dash_app():
    script_path = os.path.join(BASE_DIR, 'programs', 'Investment_Growth_App.py')
    spec = importlib.util.spec_from_file_location("create_dash_app", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, 'create_dash_app')

def run_script(script_path, function_name, stock, start_date):
    spec = importlib.util.spec_from_file_location("regression", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, function_name)
    return func(stock, start_date)

create_dash_app = import_create_dash_app()
dash_app = create_dash_app(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
