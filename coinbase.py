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
  def __init__(self, auth):
    self.auth = auth

  def GetAccountInfo(self):
    accounts = requests.get(API_BASE_URL + 'accounts', auth=self.auth).json()
    for account in accounts:
      if account['currency'] == 'USD':
        usd_account = account
      elif account['currency'] == 'BTC':
        btc_account = account
    return ['USD: %.2f' % float(usd_account['balance']),
            'BTC: %.8f' % float(btc_account['balance'])]

  def GetEMAs(self):

    def EMA(N, prices):
      res = prices[0]
      k = 2 / (N + 1)
      for i in range(1, len(prices)):
        res = prices[i] * k + res * (1 - k)
      return res

    history = requests.get(API_BASE_URL + 'products/BTC-USD/candles',
                           auth=self.auth,
                           params={'granularity': 300}).json()[::-1]
    last_entry = history[-1]
    last_time = last_entry[0]
    prices = [entry[4] for entry in history]
    last_ema12 = EMA(12, prices)
    last_ema26 = EMA(26, prices)
    return last_time, last_ema12, last_ema26

  def Sell(self):
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
    response = requests.post(API_BASE_URL + 'orders', auth=self.auth,
                             json=params)
    if not response.ok:
      logging.error('Sell failed with status %d: %s.',
                    response.status_code,
                    response.json().get('message', response.reason))
    else:
      self.PrintContentBlock('SELL',
                             ['Sell BTC of %s' % size,
                              'Transaction ID: %s' % response.json().get('id'),
                              'BTC Price: %s' % response.json().get('price'),
                              'Status: %s' % response.json().get('status')] +
                             self.GetAccountInfo())

  def Buy(self):
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
    response = requests.post(API_BASE_URL + 'orders', auth=self.auth,
                             json=params)
    if not response.ok:
      logging.error('Buy failed with status %d: %s.',
                    response.status_code,
                    response.json().get('message', response.reason))
    else:
      self.PrintContentBlock('BUY',
                             ['Buy BTC with $%s' % funds,
                              'Transaction ID: %s' % response.json().get('id'),
                              'BTC Price: %s' % response.json().get('price'),
                              'Status: %s' % response.json().get('status')] +
                             self.GetAccountInfo())

  def Hold(self):
    self.PrintContentBlock('HOLD',
                           ['Hold current balance'] + self.GetAccountInfo())

  def Trade(self, last_time, last_ema12, last_ema26):
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
    if time.time() - last_time < 300:
      last_time -= 300
    while True:
      current = time.time()
      remain_time = last_time + 600 - current
      if remain_time > 0:
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
  trade = CoinbaseTrade(auth)
  trade.Start()


if __name__ == '__main__':
    main()
