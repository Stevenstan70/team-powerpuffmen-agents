from moomoo import *
#MUST HAVE OPEND RUNNING AND LOGGED IN IN THE BACKGROUND 

# 1. Connect to the locally running OpenD gateway
quote_ctx = OpenQuoteContext(host="127.0.0.1", port=11111)

# 2. Check the connection / market status
print("Market State:", quote_ctx.get_market_state())

# 3. Fetch market data snapshots (e.g., Apple stock in the US market)
# Format is 'MARKET.SYMBOL' (e.g., US.AAPL, HK.00700)
ret, data = quote_ctx.get_market_snapshot(["US.AAPL"])

if ret == RET_OK:
print(data)
else:
print("Error fetching data:", data)

# 4. Always close the context when finished
quote_ctx.close()
