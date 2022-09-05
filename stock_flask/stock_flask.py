from __future__ import print_function
import yfinance as yf
from tabulate import tabulate as tb
from datetime import date, datetime, timedelta
from flask import Flask, render_template, request, url_for, redirect
import webbrowser
import json
import logging
import configparser
import sys
import requests
from rauth import OAuth1Service
from logging.handlers import RotatingFileHandler
#from market.market import Market

# loading configuration file
config = configparser.ConfigParser()
config.read('config.ini')

# logger settings
logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler("python_client.log", maxBytes=5*1024*1024, backupCount=3)
FORMAT = "%(asctime)-15s %(message)s"
fmt = logging.Formatter(FORMAT, datefmt='%m/%d/%Y %I:%M:%S %p')
handler.setFormatter(fmt)
logger.addHandler(handler)

app = Flask(__name__)

#==========================FUNCTIONS====================================================

# Access stock information
def ticker_data(symbol):
    stock_data = yf.Ticker(symbol)
    return stock_data

# Compute % increases
def compute_increase(current_price, increase):
    # Compute the increase
    increase = current_price + (current_price * (increase / 100) )
    # Format the return value
    formatted_increase = format(increase, '.2f')
    return formatted_increase

# Compute % increases
def compute_decrease(current_price, decrease):
    # Compute the decrease
    decrease = current_price - (current_price * (decrease / 100) )
    # Format the return value
    formatted_decrease = format(decrease, '.2f')
    return formatted_decrease

# Get options premiums
def get_options_data(stock_data, date):
    options_data = stock_data.option_chain(date).calls
    return options_data

# Get put premiums
def get_puts_data(stock_data, date):
    puts_data = stock_data.option_chain(date).puts
    return puts_data

def compute_risk(premium_price, current_price, annual, outlook):
    risk = str(round(( premium_price / current_price * (annual * 52) / outlook) * 100)) + '%'
    return risk

def add_row(increase_data):
    increase_data_row = []
    for item in increase_data:
        increase_data_row.append(item)
    return increase_data_row

def build_increases_table(current_price):
    increases = {}
    for i in range(1, 21):
        increases[i] = (compute_increase(current_price, i))
    return increases

def build_decreases_table(current_price):
    decreases = {}
    for i in range(1, 21):
        decreases[i] = (compute_decrease(current_price, i))
    return decreases

def build_stike_price_table(increases, call_data):
    increase_strike_table = {}
    for keys, values in increases.items():
        value = round(float(values))
        stike_price = call_data.iloc[(call_data['strike']-value).abs().argsort()[:1]]
        increase_strike_table[keys] = stike_price['strike'].values[0]
    return increase_strike_table

def query_stike_price(increase, strike_table):
    strike_price = strike_table[increase]
    return strike_price


#===============================SINGLE INCREASE COMPUTE===============================================

def compute_call_single_increase(stock_data, annual, outlook, increase_percent):
    int_outlook = int(outlook)
    int_annual = int(annual)
    current_price = stock_data.info['currentPrice']
    increases = build_increases_table(current_price)
    increase_price = increases[increase_percent]
    call_data = get_options_data(stock_data, stock_data.options[int_outlook - 1])
    strike_table = build_stike_price_table(increases, call_data)
    strike_price = query_stike_price(increase_percent, strike_table)
    premium = call_data[call_data["strike"] == strike_price]
    premium_price = premium['lastPrice'].values[0]
    risk = compute_risk(premium_price, strike_price, int_annual, int_outlook)
    amount_increased = format((float(strike_price) - current_price), '.2f')
    return [increase_percent, amount_increased, strike_price, premium_price, risk]


def compute_put_single_increase(stock_data, annual, outlook, decrease_percent):
    test = int(outlook)
    test_2 = int(annual)
    current_price = stock_data.info['currentPrice']
    increases = build_decreases_table(current_price)
    decrease_price = increases[decrease_percent]
    call_data = get_puts_data(stock_data, stock_data.options[test - 1])
    strike_table = build_stike_price_table(increases, call_data)
    strike_price = query_stike_price(decrease_percent, strike_table)
    premium = call_data[call_data["strike"] == strike_price]
    premium_price = premium['lastPrice'].values[0]
    risk = compute_risk(premium_price, strike_price, test_2, test)
    amount_decreased = format((float(decrease_price) - current_price), '.2f')
    return [decrease_percent, amount_decreased, strike_price, premium_price, risk]

#================================CREATE AND DISPLAY TABLE==============================================

def build_call_data_table(data, years, expiry_date):
    pop_table = []
    for i in range(1, 21):
        pop_table.append(add_row(compute_call_single_increase(data, years, expiry_date, i)))
    return pop_table

def build_put_data_table(data, years, expiry_date):
    pop_table = []
    for i in range(1, 21):
        pop_table.append(add_row(compute_put_single_increase(data, years, expiry_date, i)))
    return pop_table

call_table_header = ('% Increase', 'Amount Increased', 'Strike', 'Premium', 'RISK/APR')
put_table_header = ('% Decrease', 'Amount Decrased', 'Strike', 'Premium', 'RISK/APR')
#====================================================================================================



#=================================Flask Section ======================================================

@app.route('/calldata/<ticker_3>/<date_3>/<years_3>')
def call_page(ticker_3=None, years_3=None, date_3=None):
    data = ticker_data(ticker_3)
    table_data = build_call_data_table(data, years_3, date_3)
    expiry_date = data.options[int(date_3) - 1]
    price = data.info['currentPrice']
    return render_template("call_data.html", year = years_3, ticker = ticker_3, option_date = expiry_date, table_header = call_table_header, data = table_data, price = price)


@app.route('/putdata/<ticker_3>/<date_3>/<years_3>')
def put_page(ticker_3=None, years_3=None, date_3=None):
    data = ticker_data(ticker_3)
    table_data = build_put_data_table(data, years_3, date_3)
    expiry_date = data.options[int(date_3) - 1]
    price = data.info['currentPrice']
    return render_template("put_data.html", year = years_3, ticker = ticker_3, option_date = expiry_date, table_header = put_table_header, data = table_data, price = price)

@app.route('/calls',methods = ['POST', 'GET'])
def calls():
   if request.method == 'POST':
      ticker_2 = request.form['ticker_1']
      years_2 = request.form['years_1']
      date_2 = request.form['date_1']
      return redirect(url_for('call_page',ticker_3 = ticker_2, date_3 = date_2, years_3 = years_2))
   else:
      return render_template('call_base.html')


@app.route('/puts',methods = ['POST', 'GET'])
def puts():
   if request.method == 'POST':
      ticker_2 = request.form['ticker_1']
      years_2 = request.form['years_1']
      date_2 = request.form['date_1']
      return redirect(url_for('put_page',ticker_3 = ticker_2, date_3 = date_2, years_3 = years_2))
   else:
      return render_template('put_base.html')

@app.route('/')
def main():
   return render_template('index.html')

if __name__ == '__main__':
   app.run(debug = True)