# BTC Audo Trade

![BTC](https://en.bitcoin.it//w/images/en/2/29/BC_Logo_.png)

Automatically trade BTC-USD on [Coinbase Pro](https://pro.coinbase.com).

## Trading Strategy
 * Get historical trading data at granularity of 5 min.
 * Calculate exponential moving average (EMA) for EMA-12 and EMA-26.
 * If EMA-12 and EMA-26 have a cross, perform one of the following actions.
   * If EMA-12 goes above EMA-26, buy BTC with all UST balance.
   * If EMA-12 goes below EMA-26, sell all BTC.

## How To Run
 * In order to run the code, one has to properly set `API_KEY`, `API_SECRET` and
   `API_PASS` as environment variables. These can be found in your Coinbase Pro
   profile. An example of starting script is as follows.
   ```shell
   export API_KEY="<your_API_key>"
   export API_SECRET="<your_API_secret>"
   export API_PASS="<your_API_pass>"
   python3 ./coinbase.py --logfile coinbase.log
   ```
 * The text output will always be written to standard error. Besides,
   `--logfile` is an optional flag, which will also writes text output to
   provided file.

## API Reference
 * [Coinbase Pro REST API](https://docs.pro.coinbase.com/#api)