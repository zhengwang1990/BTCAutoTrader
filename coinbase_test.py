#!/usr/bin/env python3
import coinbase
import logging
import requests
import unittest
from unittest.mock import patch
from unittest.mock import Mock


class MockAccountResponse(object):
  def __init__(self):
    pass

  def json(self):
    return [{'currency': 'USD', 'balance': '100.123456'},
            {'currency': 'BTC', 'balance': '0.123456789'}]


class MockTransactionResponse(object):
  def __init__(self, status_code=200, reason=''):
    self.status_code = status_code
    self.reason = reason
    self.ok = status_code == 200

  def json(self):
    return {'id': 'transaction_id', 'status': 'pending'}


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
    self.mock_accounts_response = Mock(return_value=MockAccountResponse())
    self.mock_success_transaction = Mock(return_value=MockTransactionResponse())
    self.mock_fail_transaction = Mock(
        return_value=MockTransactionResponse(400, 'Unknown'))
    self.mock_candles_up = Mock(return_value=MockCandleResponse('up'))
    self.mock_candles_down = Mock(return_value=MockCandleResponse('down'))

  def testBuySuccess(self):
    with patch.object(requests, 'get',
                      side_effect=self.mock_accounts_response):
      with patch.object(requests, 'post',
                        side_effect=self.mock_success_transaction) as buy:
        with patch.object(coinbase.CoinbaseTrade, 'PrintContentBlock') as block:
          self.trade.Buy()
          buy.assert_called_once()
          block.assert_called_once()

  def testBuyFailure(self):
    with patch.object(requests, 'get',
                      side_effect=self.mock_accounts_response):
      with patch.object(requests, 'post',
                        side_effect=self.mock_fail_transaction) as buy:
        with patch.object(logging, 'error') as log:
          self.trade.Buy()
          buy.assert_called_once()
          log.assert_called_once()

  def testSellSuccess(self):
    with patch.object(requests, 'get',
                      side_effect=self.mock_accounts_response):
      with patch.object(requests, 'post',
                        side_effect=self.mock_success_transaction) as sell:
        with patch.object(coinbase.CoinbaseTrade, 'PrintContentBlock') as block:
          self.trade.Sell()
          sell.assert_called_once()
          block.assert_called_once()

  def testSellFailure(self):
    with patch.object(requests, 'get',
                      side_effect=self.mock_accounts_response):
      with patch.object(requests, 'post',
                        side_effect=self.mock_fail_transaction) as sell:
        with patch.object(logging, 'error') as log:
          self.trade.Sell()
          sell.assert_called_once()
          log.assert_called_once()

  def testGetEMAs(self):
    with patch.object(requests, 'get',
                      side_effect=self.mock_candles_up):
      t, ema12, ema26 = self.trade.GetEMAs()
      self.assertGreater(ema12, ema26)
      self.assertEqual(t, 200)

  def testTradeHold(self):
    with patch.object(requests, 'get',
                      side_effect=self.mock_candles_up):
      with patch.object(coinbase.CoinbaseTrade, 'Hold') as hold:
        self.trade.Trade(199, 100, 90)
        hold.assert_called_once()

  def testTradeBuy(self):
    with patch.object(requests, 'get',
                      side_effect=self.mock_candles_up):
      with patch.object(coinbase.CoinbaseTrade, 'Buy') as buy:
        self.trade.Trade(199, 90, 100)
        buy.assert_called_once()

  def testTradeSell(self):
    with patch.object(requests, 'get',
                      side_effect=self.mock_candles_down):
      with patch.object(coinbase.CoinbaseTrade, 'Sell') as sell:
        self.trade.Trade(199, 100, 90)
        sell.assert_called_once()


if __name__ == '__main__':
    unittest.main()