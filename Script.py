pip install webull
pip install pandas
pip install ta

import pandas as pd
import numpy as np
import logging
from webull import webull
from ta.trend import EMAIndicator
from time import sleep

# Initialize logging
logging.basicConfig(filename='trading_bot.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize the Webull API
wb = webull()
wb.login('your_email', 'your_password')  # Replace with your Webull credentials

# Function to fetch historical data
def fetch_historical_data(ticker, interval='m1', count=1000):
    try:
        data = wb.get_bars(stock=ticker, interval=interval, count=count)
        df = pd.DataFrame(data)
        df['close'] = df['close'].astype(float)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        logging.error(f"Error fetching historical data: {e}")
        return pd.DataFrame()

# Function to calculate EMAs
def calculate_ema(data, windows):
    try:
        for window in windows:
            data[f'EMA_{window}'] = EMAIndicator(data['close'], window=window).ema_indicator()
        return data
    except Exception as e:
        logging.error(f"Error calculating EMAs: {e}")
        return data

# Function to generate trading signals
def generate_signals(data):
    try:
        data['signal'] = 0
        data['position'] = 0

        for i in range(1, len(data)):
            if data['EMA_9'].iloc[i] > data['EMA_200'].iloc[i] and data['EMA_9'].iloc[i-1] <= data['EMA_200'].iloc[i-1]:
                data['signal'].iloc[i] = 1  # Golden cross signal
            elif data['EMA_9'].iloc[i] < data['EMA_200'].iloc[i] and data['EMA_9'].iloc[i-1] >= data['EMA_200'].iloc[i-1]:
                data['signal'].iloc[i] = -1  # Death cross signal
            
            # Determine positions based on signals
            if data['signal'].iloc[i] == 1:  # Long position
                data['position'].iloc[i] = 1
            elif data['signal'].iloc[i] == -1:  # Short position
                data['position'].iloc[i] = -1
            elif data['position'].iloc[i-1] == 1 and data['close'].iloc[i] < data['EMA_50'].iloc[i]:  # Close long position
                data['position'].iloc[i] = 0
            elif data['position'].iloc[i-1] == -1 and data['close'].iloc[i] > data['EMA_50'].iloc[i]:  # Close short position
                data['position'].iloc[i] = 0
            else:
                data['position'].iloc[i] = data['position'].iloc[i-1]

        return data
    except Exception as e:
        logging.error(f"Error generating signals: {e}")
        return data

# Function to execute trades with stop loss and trailing stop loss
def execute_trade(ticker, position, entry_price, stop_loss_max, trailing_stop_loss_trigger, trailing_stop_loss_distance):
    try:
        current_price = wb.get_last_quote(stock=ticker)['close']

        if position == 1:  # Go long
            wb.place_order(stock=ticker, action='BUY', orderType='MKT', enforce='DAY', qty=30)  # 30 contracts
            logging.info(f"Placed BUY order for {ticker} - 30 contracts at {current_price}")
            entry_price = current_price
            stop_loss = entry_price - stop_loss_max
        elif position == -1:  # Go short
            wb.place_order(stock=ticker, action='SELL', orderType='MKT', enforce='DAY', qty=30)  # 30 contracts
            logging.info(f"Placed SELL order for {ticker} - 30 contracts at {current_price}")
            entry_price = current_price
            stop_loss = entry_price + stop_loss_max
        elif position == 0:  # Close positions
            current_position = wb.get_positions(stock=ticker)
            if current_position:
                action = 'SELL' if current_position['side'] == 'LONG' else 'BUY'
                wb.place_order(stock=ticker, action=action, orderType='MKT', enforce='DAY', qty=current_position['qty'])
                logging.info(f"Closed position for {ticker} at {current_price}")

        # Update stop loss based on trailing stop loss conditions
        if position == 1 and current_price >= entry_price + trailing_stop_loss_trigger:
            stop_loss = max(stop_loss, current_price - trailing_stop_loss_distance)
        elif position == -1 and current_price <= entry_price - trailing_stop_loss_trigger:
            stop_loss = min(stop_loss, current_price + trailing_stop_loss_distance)

        # Check if stop loss is hit
        if position == 1 and current_price <= stop_loss:
            wb.place_order(stock=ticker, action='SELL', orderType='MKT', enforce='DAY', qty=30)  # 30 contracts
            logging.info(f"Stop loss hit, placed SELL order for {ticker} - 30 contracts at {current_price}")
        elif position == -1 and current_price >= stop_loss:
            wb.place_order(stock=ticker, action='BUY', orderType='MKT', enforce='DAY', qty=30)  # 30 contracts
            logging.info(f"Stop loss hit, placed BUY order for {ticker} - 30 contracts at {current_price}")

        return entry_price, stop_loss
    except Exception as e:
        logging.error(f"Error executing trade: {e}")
        return entry_price, stop_loss

# Main function to run the bot
def run_bot(ticker, interval='m1', count=1000, windows=[9, 50, 113, 200]):
    entry_price = None
    stop_loss = None
    stop_loss_max = 3.50
    trailing_stop_loss_trigger = 3.00
    trailing_stop_loss_distance = 5.00
    
    while True:
        try:
            data = fetch_historical_data(ticker, interval, count)
            if data.empty:
                logging.warning(f"No data fetched for {ticker}. Skipping execution.")
                sleep(60)
                continue

            data = calculate_ema(data, windows)
            data = generate_signals(data)
            
            latest_position = data['position'].iloc[-1]
            entry_price, stop_loss = execute_trade(
                ticker, latest_position, entry_price, stop_loss_max, 
                trailing_stop_loss_trigger, trailing_stop_loss_distance
            )
            logging.info(f"Executed trade for {ticker} with position {latest_position}")
            sleep(60)
        except Exception as e:
            logging.error(f"Error in run_bot: {e}")
            sleep(60)

# Example usage
ticker = 'ES_F'
run_bot(ticker)
