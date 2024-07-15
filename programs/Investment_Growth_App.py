import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import pandas as pd
import plotly.graph_objs as go
import yfinance as yf

def create_dash_app(server):
    dash_app = dash.Dash(__name__, server=server, url_base_pathname='/dash/')

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
        
        investment_summary = []
        for month in first_trading_days:
            if month >= start_date:
                monthly_start_price = stock_data.loc[month, 'Price']
                current_investment += monthly_investment
                stock_data['Investment Value'] += (monthly_investment / monthly_start_price) * stock_data['Price']
                if month.month == 12:
                    end_of_year_value = stock_data['Investment Value'].loc[month]
                    investment_summary.append((month.year, current_investment, end_of_year_value))

        final_amount = stock_data['Investment Value'].iloc[-1]
        investment_summary.append((stock_data.index[-1].year, current_investment, final_amount))
        initial_investment = (len(first_trading_days) - 1) * monthly_investment
        percent_change = ((final_amount - initial_investment) / initial_investment) * 100

        return stock_data['Investment Value'], investment_summary, percent_change, initial_investment, first_valid_date

    def update_data(tickers, start_date, monthly_investment):
        growth_data = pd.DataFrame()
        valid_tickers = []
        first_trading_days_dict = {}
        investment_summaries = {}
        final_amounts = []
        percent_changes = []
        total_investments = []
        for ticker in tickers:
            investment_growth, investment_summary, percent_change, total_investment, first_valid_date = calculate_investment_growth(ticker, start_date, monthly_investment)
            if investment_growth is not None and not investment_growth[start_date:].isna().all():
                growth_data = pd.concat([growth_data, investment_growth], axis=1)
                valid_tickers.append(ticker)
                first_trading_days_dict[ticker] = first_valid_date
                investment_summaries[ticker] = investment_summary
                final_amounts.append(investment_growth.iloc[-1])
                percent_changes.append(percent_change)
                total_investments.append(total_investment)
        if not growth_data.empty:
            growth_data.columns = valid_tickers
            growth_data = growth_data.ffill().bfill()
        return growth_data, valid_tickers, first_trading_days_dict, investment_summaries, final_amounts, percent_changes, total_investments

    dash_app.layout = html.Div(className='container', style={'min-height': '100vh', 'display': 'flex', 'flex-direction': 'column', 'padding': '0', 'overflow': 'hidden'}, children=[
    html.H1('Investment Growth Over Time', style={'text-align': 'center', 'margin': '0', 'padding': '10px'}),
    html.Div(className='row', style={'display': 'flex', 'flex': '1', 'padding': '0 10px'}, children=[
        html.Div(className='six columns', style={'width': '60%', 'height': '100%', 'padding-right': '10px'}, children=[
            dcc.Graph(id='investment-graph', style={'height': 'calc(80vh - 180px)'}),
            html.Div(className='input-group', style={'display': 'flex', 'flex-direction': 'column', 'gap': '5px'}, children=[
                html.Label('Enter Stock Tickers (comma-separated):', className='label'),
                dcc.Input(
                    id='ticker-input',
                    type='text',
                    value='AAPL',
                    className='form-control'
                ),
                html.Label('Select Start Date:', className='label'),
                dcc.DatePickerSingle(
                    id='start-date-picker',
                    date='2000-01-03',
                    display_format='YYYY-MM-DD',
                    className='form-control'
                ),
                html.Label('Monthly Investment Amount ($):', className='label'),
                dcc.Input(
                    id='investment-amount',
                    type='number',
                    value=100,
                    className='form-control',
                    min=1,
                    step=1
                ),
                html.Button('Update Graph', id='update-button', className='btn btn-primary', style={'margin-top': '5px'})
            ]),
        ]),
        html.Div(className='six columns', style={'width': '40%', 'height': '100%', 'display': 'flex', 'justify-content': 'center', 'align-items': 'center', 'padding': '0'}, children=[
            html.Div(id='investment-table-container', style={'width': '100%'})
        ]),
    ]),
    html.Footer('Investment Tracker © 2024', className='footer', style={'text-align': 'center', 'padding': '5px', 'flex-shrink': '0'})
])

    # Define the callback to update the graph and the table
    @dash_app.callback(
        [Output('investment-graph', 'figure'),
        Output('investment-table-container', 'children')],
        [Input('update-button', 'n_clicks'),
        Input('ticker-input', 'n_submit')],
        [State('ticker-input', 'value'),
        State('start-date-picker', 'date'),
        State('investment-amount', 'value')]
    )
    def update_graph_and_table(n_clicks, n_submit, ticker_input, selected_start_date, monthly_investment):
        if selected_start_date is None:
            selected_start_date = '2000-01-03'
        selected_start_date = pd.Timestamp(selected_start_date)
        if monthly_investment is None or monthly_investment <= 0:
            monthly_investment = 100
        tickers = [ticker.strip().upper() for ticker in ticker_input.split(',')]
        growth_data, valid_tickers, first_trading_days_dict, investment_summaries, final_amounts, percent_changes, total_investments = update_data(tickers, selected_start_date, monthly_investment)
        filtered_data = pd.DataFrame()
        for company in valid_tickers:
            if company in growth_data.columns:
                first_valid_date = first_trading_days_dict[company]
                filtered_data[company] = growth_data[company][growth_data.index >= first_valid_date]
        filtered_data = filtered_data.dropna(axis=1, how='all')

        traces = []
        for company in filtered_data.columns:
            traces.append(go.Scatter(
                x=filtered_data.index,
                y=filtered_data[company],
                mode='lines',
                name=company
            ))

        title_date = selected_start_date.strftime("%Y-%m-%d") if not pd.isna(selected_start_date) else '2000-01-03'
        graph_figure = {
            'data': traces,
            'layout': go.Layout(
                title=f'Growth of ${monthly_investment} Invested Monthly Since {title_date}',
                xaxis={'title': 'Date'},
                yaxis={'title': 'Investment Value ($)', 'type': 'log'},
                legend={'title': 'Company'},
                hovermode='closest'
            )
        }

        table_header = [
            html.Thead(html.Tr([
                html.Th("Company", style={'text-align': 'center'}),
                html.Th("Total Invested ($)", style={'text-align': 'center'}),
                html.Th("Current Value ($)", style={'text-align': 'center'}),
                html.Th("Percent Change (%)", style={'text-align': 'center'})
            ]))
        ]
        table_body = [
            html.Tbody([
                html.Tr([
                    html.Td(valid_tickers[i], style={'text-align': 'center'}),
                    html.Td(f"${total_investments[i]:,.2f}", style={'text-align': 'center'}),
                    html.Td(f"${final_amounts[i]:,.2f}", style={'text-align': 'center'}),
                    html.Td(f"{percent_changes[i]:.2f}%", style={'text-align': 'center'})
                ]) for i in range(len(valid_tickers))
            ])
        ]
        table = html.Table(table_header + table_body, className='table table-striped')

        return graph_figure, table