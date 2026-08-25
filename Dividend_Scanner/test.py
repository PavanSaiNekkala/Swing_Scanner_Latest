import yfinance as yf

ticker = yf.Ticker("SAIL.NS")

print(ticker.info.get("symbol"))
print(ticker.info.get("longName"))
print(ticker.info.get("shortName"))
print(ticker.info.get("exchange"))
print(ticker.info.get("quoteType"))

hist = ticker.history(period="5d")
print(hist.head())