#!/usr/bin/env python3
import argparse
import base64
import datetime
import hashlib
import hmac
import logging
import os
import requests
import time


API_BASE_URL = 'https://api.pro.coinbase.com/'
# It is currently impossible to get real-time historical data. There is a ~5min
# delay of the latest historical data
DATA_DELAY = 300

class CoinbaseExchangeAuth(requests.auth.AuthBase):
  def __init__(self, api_key, secret_key, passphrase):
    self.api_key = api_key
    self.secret_key = secret_key
    self.passphrase = passphrase

  def __call__(self, request):
    timestamp = str(time.time())
    message = (timestamp + request.method + request.path_url +
               (request.body.decode() if request.body else ''))
    hmac_key = base64.b64decode(self.secret_key)
    signature = hmac.new(hmac_key, message.encode(), hashlib.sha256)
    signature_b64 = base64.b64encode(signature.digest())
    request.headers.update({
        'CB-ACCESS-SIGN': signature_b64,
        'CB-ACCESS-TIMESTAMP': timestamp,
        'CB-ACCESS-KEY': self.api_key,
        'CB-ACCESS-PASSPHRASE': self.passphrase,
        'Content-Type': 'application/json'
    })
    return request


class CoinbaseTrade(object):
  def __init__(self, auth, granularity):
    self.auth = auth
    self.granularity = granularity

  def GetAccountInfo(self):
    """Gets account USD and BTC balances."""
    accounts = requests.get(API_BASE_URL + 'accounts', auth=self.auth).json()
    for account in accounts:
      if account['currency'] == 'USD':
        usd_account = account
      elif account['currency'] == 'BTC':
        btc_account = account
    return ['USD: %.2f' % float(usd_account['balance']),
            'BTC: %.8f' % float(btc_account['balance'])]

  def GetEMAs(self):
    """Gets most current EMA values."""
    def EMA(N, prices):
      res = prices[0]
      k = 2 / (N + 1)
      for i in range(1, len(prices)):
        res = prices[i] * k + res * (1 - k)
      return res

    history = requests.get(
        API_BASE_URL + 'products/BTC-USD/candles',
        auth=self.auth,
        params={'granularity': self.granularity}).json()[::-1]
    last_entry = history[-1]
    last_time = last_entry[0]
    prices = [entry[4] for entry in history]
    last_ema12 = EMA(12, prices)
    last_ema26 = EMA(26, prices)
    return last_time, last_ema12, last_ema26

  def Sell(self):
    """Sells BTC with market order."""
    accounts = requests.get(API_BASE_URL + 'accounts', auth=self.auth).json()
    for account in accounts:
      if account['currency'] == 'BTC':
        size = '%.8f' % float(account['balance'])
        break
    params = {
        'type': 'market',
        'side': 'sell',
        'product_id': 'BTC-USD',
        'size': size,
    }
    self.Transaction(params)

  def Buy(self):
    """Buys BTC with market order."""
    accounts = requests.get(API_BASE_URL + 'accounts', auth=self.auth).json()
    for account in accounts:
      if account['currency'] == 'USD':
        funds = '%.2f' % (int(float(account['balance']) * 100) / 100)
        break
    params = {
        'type': 'market',
        'side': 'buy',
        'product_id': 'BTC-USD',
        'funds': funds,
    }
    self.Transaction(params)

  def Transaction(self, params):
    """Performs a buy or sell transaction."""
    side = params['side']
    response = requests.post(API_BASE_URL + 'orders', auth=self.auth,
                             json=params)
    if not response.ok:
      logging.error('%s failed with status %d: %s.',
                    side.capitalize(),
                    response.status_code,
                    response.json().get('message', response.reason))
    else:
      time.sleep(1)  # wait 1s for order to be filled
      order_id = response.json().get('id')
      fills = requests.get(API_BASE_URL + 'fills',
                           auth=self.auth,
                           params={'order_id': order_id})
      fill_info = ['Buy BTC with $%s' % params['funds'] if side == 'buy'
                   else 'Sell BTC of %s' % params['size']]
      if fills.ok:
        for fill in fills.json():
          fill_info.extend(['Trade ID: %s' % fill.get('trade_id'),
                            'BTC pirce: %s' % fill.get('price'),
                            'Fee: %s' % fill.get('fee')])
      self.PrintContentBlock(side.upper(), fill_info + self.GetAccountInfo())

  def Hold(self):
    """Holds current balance."""
    self.PrintContentBlock('HOLD',
                           ['Hold current balance'] + self.GetAccountInfo())

  def Trade(self, last_time, last_ema12, last_ema26):
    """Makes a trading decision."""
    new_time, new_ema12, new_ema26 = self.GetEMAs()
    while new_time == last_time:
      time.sleep(1)
      new_time, new_ema12, new_ema26 = self.GetEMAs()
    logging.info('Current EMAs: Time %s, EMA-12 %.2f, EMA-26 %.2f',
                 datetime.datetime.fromtimestamp(new_time).strftime('%H:%M'),
                 new_ema12, new_ema26)
    if (new_ema26 - new_ema12) * (last_ema26 - last_ema12) <= 0:
      if new_ema26 > new_ema12:
        self.Sell()
      else:
        self.Buy()
    else:
      self.Hold()
    return new_time, new_ema12, new_ema26

  def Start(self):
    self.PrintContentBlock('ACCOUNT INFO', self.GetAccountInfo())
    last_time, last_ema12, last_ema26 = self.GetEMAs()
    logging.info('Previous EMAs: Time %s, EMA-12 %.2f, EMA-26 %.2f',
                 datetime.datetime.fromtimestamp(last_time).strftime('%H:%M'),
                 last_ema12, last_ema26)
    if time.time() - last_time < DATA_DELAY:
      last_time -= self.granularity
    while True:
      current = time.time()
      remain_time = last_time + self.granularity + DATA_DELAY - current
      if remain_time > 0:
        logging.info('Waiting %ds for next EMA query', remain_time + 1)
        time.sleep(remain_time + 1)
      try:
        last_time, last_ema12, last_ema26 = self.Trade(
            last_time, last_ema12, last_ema26)
      except Exception as e:
        logging.exception(e)
        time.sleep(60)

  def PrintContentBlock(self, title, contents):
    msg = '\n  ' + '== [ ' + title + ' ] ' +  '=' * (72 - len(title))
    for content in contents:
      msg += '\n  ' + content
    msg += '\n  ' + '=' * 80
    logging.info(msg)


def main():
  parser = argparse.ArgumentParser(description='Coinbase Auto Trade')
  parser.add_argument(
      '--logfile', default='', help='Log file.')
  parser.add_argument(
      '--granularity', default=360, type=int, help='Granularity of EMAs.')
  args = parser.parse_args()
  handlers = [logging.StreamHandler()]
  if args.logfile:
    handlers.append(logging.FileHandler(args.logfile))
  logging.basicConfig(level=logging.INFO,
                      format="[%(asctime)s] [%(levelname)s] %(message)s",
                      datefmt='%Y-%m-%d %H:%M:%S',
                      handlers=handlers)
  auth = CoinbaseExchangeAuth(os.environ['API_KEY'],
                              os.environ['API_SECRET'],
                              os.environ['API_PASS'])
  trade = CoinbaseTrade(auth, args.granularity)
  trade.Start()


if __name__ == '__main__':
    main()
