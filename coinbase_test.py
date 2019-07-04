#!/usr/bin/env python3
import base64
import coinbase
import logging
import os
import requests
import time
import unittest
from unittest.mock import patch
from unittest.mock import Mock


class MockAccountResponse(object):
  def __init__(self):
    pass

  def json(self):
    return [{'currency': 'USD', 'balance': '100.129456'},
            {'currency': 'BTC', 'balance': '0.123456789'}]


class MockOrderResponse(object):
  def __init__(self, status_code=200, reason=''):
    self.status_code = status_code
    self.reason = reason
    self.ok = status_code == 200

  def json(self):
    return {'id': 'order_id', 'status': 'pending'}


class MockFillResponse(object):
  def __init__(self):
    self.ok = True

  def json(self):
    return [{'trade_id': 'trade_id', 'fee': '0.25',
            'price': '12345'}]


class MockCandleResponse(object):
  def __init__(self, trend):
    self.trend = trend

  def json(self):
    if self.trend == 'up':
      return [[t, t+1, t+2, t+3, t+4, 100] for t in range(200, 100, -1)]
    else:
      return [[t, 1000-t, 1000-t, 1000-t, 1000-t, 100]
              for t in range(200, 100, -1)]


class CoinbaseTradeTest(unittest.TestCase):
  def setUp(self):
    self.trade = coinbase.CoinbaseTrade(Mock())

  def testBuySuccess(self):
    with patch.object(requests, 'get',
                      side_effect=[MockAccountResponse(),
                                   MockFillResponse(),
                                   MockAccountResponse()]):
      with patch.object(requests, 'post',
                        return_value=MockOrderResponse()) as buy:
        with patch.object(coinbase.CoinbaseTrade, 'PrintContentBlock') as block:
          with patch.object(time, 'sleep'):
            self.trade.Buy()
            buy.assert_called_once()
            block.assert_called_once()

  def testBuyFailure(self):
    with patch.object(requests, 'get', return_value=MockAccountResponse()):
      with patch.object(requests, 'post',
                        return_value=MockOrderResponse(400, 'Unknown')) as buy:
        with patch.object(logging, 'error') as log:
          self.trade.Buy()
          buy.assert_called_once()
          log.assert_called_once()

  def testSellSuccess(self):
    with patch.object(requests, 'get',
                      side_effect=[MockAccountResponse(),
                                   MockFillResponse(),
                                   MockAccountResponse()]):
      with patch.object(requests, 'post',
                        return_value=MockOrderResponse()) as sell:
        with patch.object(coinbase.CoinbaseTrade, 'PrintContentBlock') as block:
          with patch.object(time, 'sleep'):
            self.trade.Sell()
            sell.assert_called_once()
            block.assert_called_once()

  def testSellFailure(self):
    with patch.object(requests, 'get',
                      return_value=MockAccountResponse()):
      with patch.object(requests, 'post',
                        return_value=MockOrderResponse(400, 'Unknown')) as sell:
        with patch.object(logging, 'error') as log:
          self.trade.Sell()
          sell.assert_called_once()
          log.assert_called_once()

  def testHold(self):
    with patch.object(coinbase.CoinbaseTrade, 'GetAccountInfo') as account:
      self.trade.Hold()
      account.assert_called_once()

  def testGetEMAs(self):
    with patch.object(requests, 'get',
                      return_value=MockCandleResponse('up')):
      t, ema12, ema26 = self.trade.GetEMAs()
      self.assertGreater(ema12, ema26)
      self.assertEqual(t, 200)

  def testTradeHold(self):
    with patch.object(requests, 'get',
                      return_value=MockCandleResponse('up')):
      with patch.object(coinbase.CoinbaseTrade, 'Hold') as hold:
        self.trade.Trade(199, 100, 90)
        hold.assert_called_once()

  def testTradeBuy(self):
    with patch.object(requests, 'get',
                      return_value=MockCandleResponse('up')):
      with patch.object(coinbase.CoinbaseTrade, 'Buy') as buy:
        self.trade.Trade(199, 90, 100)
        buy.assert_called_once()

  def testTradeSell(self):
    with patch.object(requests, 'get',
                      return_value=MockCandleResponse('down')):
      with patch.object(coinbase.CoinbaseTrade, 'Sell') as sell:
        self.trade.Trade(199, 100, 90)
        sell.assert_called_once()

  def testPrintContentBlock(self):
    with patch.object(logging, 'info') as log:
      self.trade.PrintContentBlock('title', ['contents'])
      log.assert_called_once()

  def testStart(self):
    with patch.object(coinbase.CoinbaseTrade, 'GetEMAs',
                      return_value = (time.time(), 0, 0)):
      with patch.object(coinbase.CoinbaseTrade, 'GetAccountInfo'):
        with patch.object(coinbase.CoinbaseTrade, 'Trade',
                          side_effect=Exception) as trade:
          with patch.object(time, 'sleep',
                            side_effect=[None, Exception]):
            with patch.object(logging, 'exception') as log:
              with self.assertRaises(Exception):
                self.trade.Start()
              trade.assert_called_once()
              log.assert_called_once()

  def testMain(self):
    with patch.object(coinbase.CoinbaseTrade, 'Start') as start:
      with patch.object(logging, 'basicConfig') as config:
        with patch.dict(os.environ, {'API_KEY': 'fake_key',
                                     'API_SECRET': 'fake_secret',
                                     'API_PASS': 'fake_pass'}):
          coinbase.main()
          start.assert_called_once()
          config.assert_called_once()


class CoinbaseExchangeAuthTest(unittest.TestCase):
  def testCall(self):
    auth = coinbase.CoinbaseExchangeAuth('fake_api_key',
                                         base64.b64encode(b'fake_secret_key'),
                                         'fake_pass_phrase')
    request = requests.Request('POST', 'http://localhost',
                               json={'key': 'value'})
    updated_request = auth(request.prepare())
    self.assertEqual(updated_request.headers['CB-ACCESS-KEY'],
                     'fake_api_key')
    self.assertEqual(updated_request.headers['CB-ACCESS-PASSPHRASE'],
                     'fake_pass_phrase')


if __name__ == '__main__':
    unittest.main()
