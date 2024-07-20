import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import pandas as pd
import plotly.graph_objs as go
import yfinance as yf

def create_dash_app(server):
    dash_app = dash.Dash(__name__, server=server, url_base_pathname='/dash/')

    def fetch_stock_data(ticker, start_date):
        stock_data = yf.download(ticker, start=start_date)
        if stock_data.empty:
            return None, None
        stock_data['Price'] = stock_data['Adj Close']
        stock_data = stock_data.ffill().interpolate()
        first_valid_date = stock_data.index.min()
        return stock_data['Price'], first_valid_date

    def update_data(tickers, start_date):
        price_data = pd.DataFrame()
        valid_tickers = []
        first_trading_days_dict = {}

        for ticker in tickers:
            stock_prices, first_valid_date = fetch_stock_data(ticker, start_date)
            if stock_prices is not None and not stock_prices[start_date:].isna().all():
                price_data = pd.concat([price_data, stock_prices], axis=1)
                valid_tickers.append(ticker)
                first_trading_days_dict[ticker] = first_valid_date
        
        if not price_data.empty:
            price_data.columns = valid_tickers
            price_data = price_data.ffill().bfill()
        
        return price_data, valid_tickers, first_trading_days_dict

    dash_app.layout = html.Div(className='container', style={'min-height': '100vh', 'display': 'flex', 'flex-direction': 'column', 'padding': '0', 'overflow': 'hidden'}, children=[
        html.H1('Stock Price Performance', style={'text-align': 'center', 'margin': '0', 'padding': '10px'}),
        html.Div(className='row', style={'display': 'flex', 'flex': '1', 'padding': '0 10px'}, children=[
            html.Div(className='six columns', style={'width': '60%', 'height': '100%', 'padding-right': '10px'}, children=[
                dcc.Graph(id='price-graph', style={'height': 'calc(80vh - 180px)'}),
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
                    html.Button('Update Graph', id='update-button', className='btn btn-primary', style={'margin-top': '5px'})
                ]),
            ]),
            html.Div(className='six columns', style={'width': '40%', 'height': '100%', 'display': 'flex', 'justify-content': 'center', 'align-items': 'center', 'padding': '0'}, children=[
                html.Div(id='price-table-container', style={'width': '100%'})
            ]),
        ]),
        html.Footer('Stock Tracker © 2024', className='footer', style={'text-align': 'center', 'padding': '5px', 'flex-shrink': '0'})
    ])

    @dash_app.callback(
        [Output('price-graph', 'figure'),
         Output('price-table-container', 'children')],
        [Input('update-button', 'n_clicks'),
         Input('ticker-input', 'n_submit')],
        [State('ticker-input', 'value'),
         State('start-date-picker', 'date')]
    )
    def update_graph_and_table(n_clicks, n_submit, ticker_input, selected_start_date):
        if selected_start_date is None:
            selected_start_date = '2000-01-03'
        selected_start_date = pd.Timestamp(selected_start_date)
        
        tickers = [ticker.strip().upper() for ticker in ticker_input.split(',')]
        price_data, valid_tickers, first_trading_days_dict = update_data(tickers, selected_start_date)
        
        filtered_data = pd.DataFrame()
        for company in valid_tickers:
            if company in price_data.columns:
                first_valid_date = first_trading_days_dict[company]
                filtered_data[company] = price_data[company][price_data.index >= first_valid_date]
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
                title=dict(
                    text=f'Stock Price Performance Since {title_date}',
                    x=0.5,
                    xanchor = 'center',
                ),
                xaxis={'title': 'Date'},
                yaxis={'title': 'Price ($)', 'type': 'log'},
                legend={'title': 'Company'},
                hovermode='closest'
            )
        }

        table_header = [
            html.Thead(html.Tr([
                html.Th("Company", style={'text-align': 'center'}),
                html.Th("Starting Price ($)", style={'text-align': 'center'}),
                html.Th("Current Price ($)", style={'text-align': 'center'})
            ]))
        ]
        table_body = [
            html.Tbody([
                html.Tr([
                    html.Td(valid_tickers[i], style={'text-align': 'center'}),
                    html.Td(f"${filtered_data[valid_tickers[i]].iloc[0]:,.2f}", style={'text-align': 'center'}),
                    html.Td(f"${filtered_data[valid_tickers[i]].iloc[-1]:,.2f}", style={'text-align': 'center'})
                ]) for i in range(len(valid_tickers))
            ])
        ]
        table = html.Table(table_header + table_body, className='table table-striped')

        return graph_figure, table

    return dash_app
