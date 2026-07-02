# app.py - NSE Heatmap Proxy using Yahoo Finance
# No proxy needed. No blocking. Free forever.
# yfinance fetches NSE data (SYMBOL.NS) directly from Yahoo Finance servers

import math, logging
import yfinance as yf
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# Nifty 100 stocks — covers large + mid cap universe for gainers scan
SYMBOLS = [
    "RELIANCE","TCS","HDFCBANK","BHARTIARTL","ICICIBANK","INFY","SBIN",
    "HINDUNILVR","ITC","KOTAKBANK","LT","BAJFINANCE","HCLTECH","AXISBANK",
    "MARUTI","ASIANPAINT","SUNPHARMA","M&M","TITAN","NESTLEIND","ULTRACEMCO",
    "DRREDDY","WIPRO","BAJAJFINSV","POWERGRID","NTPC","CIPLA","ONGC",
    "TATASTEEL","COALINDIA","TECHM","GRASIM","INDUSINDBK","TATAMOTORS",
    "ADANIPORTS","BRITANNIA","BPCL","EICHERMOT","SHRIRAMFIN","HEROMOTOCO",
    "DIVISLAB","APOLLOHOSP","TATACONSUM","SBILIFE","HDFCLIFE","BAJAJ-AUTO",
    "JSWSTEEL","HINDALCO","VEDL","ADANIENT","SIEMENS","HAL","BEL","ABB",
    "PIDILITIND","DABUR","MARICO","GODREJCP","MCDOWELL-N","COLPAL","HAVELLS",
    "VOLTAS","BERGEPAINT","TATAPOWER","ADANIGREEN","ADANIPOWER","CANBK",
    "BANKBARODA","PNB","FEDERALBNK","IDFCFIRSTB","BANDHANBNK","RBLBANK",
    "AUBANK","KARURVYSYA","MUTHOOTFIN","CHOLAFIN","BAJAJHLDNG","HDFCAMC",
    "LICI","ICICIGI","SBICARD","ZOMATO","PAYTM","NAUKRI","POLICYBZR",
    "DMART","TRENT","TITAN","JUBLFOOD","INDIAMART","IRCTC","CONCOR",
    "IRFC","PFC","RECLTD","HUDCO","RVNL","NBCC","NTPC","SJVN",
    "MANKIND","LUPIN","AUROPHARMA","TORNTPHARM","ALKEM","IPCALAB",
    "LAURUS","GLAND","PPLPHARMA","AJANTPHARM","LAURUSLABS","GLENMARK"
]

YF_SYMBOLS = [s + ".NS" for s in SYMBOLS]

def sf(v):
    try:
        f = float(v)
        return 0.0 if (f != f) else f   # handle NaN
    except: return 0.0

def fetch_nse_data():
    logger.info("Downloading data for " + str(len(YF_SYMBOLS)) + " stocks via Yahoo Finance...")
    tickers = yf.Tickers(" ".join(YF_SYMBOLS))

    results = []
    for sym, ticker in tickers.tickers.items():
        try:
            info = ticker.fast_info
            nse_sym = sym.replace(".NS", "")

            ltp        = sf(info.last_price)
            prev_close = sf(info.previous_close)
            if ltp == 0 or prev_close == 0:
                continue

            pct_change = round((ltp - prev_close) / prev_close * 100, 2)
            volume     = int(sf(info.three_month_average_volume or 0))
            # Use day_volume if available
            try:
                day_vol = int(sf(info.shares))
            except:
                day_vol = volume

            turnover_cr = round(ltp * day_vol / 1e7, 2)

            results.append({
                "symbol":      nse_sym,
                "series":      "EQ",
                "ltp":         round(ltp, 2),
                "prev_close":  round(prev_close, 2),
                "pct_change":  pct_change,
                "open":        sf(info.open),
                "high":        sf(info.day_high),
                "low":         sf(info.day_low),
                "volume":      day_vol,
                "turnover_cr": turnover_cr,
                "is_gainer":   pct_change > 0,
                "score":       0.0,
            })
        except Exception as e:
            logger.debug("Skip " + sym + ": " + str(e))

    logger.info("Got data for " + str(len(results)) + " stocks")
    return results

def add_scores(items):
    n = len(items)
    if not n: return items
    bp = sorted(items, key=lambda x: x["pct_change"],  reverse=True)
    bt = sorted(items, key=lambda x: x["turnover_cr"], reverse=True)
    pR = {d["symbol"]:(i+1)/n for i,d in enumerate(bp)}
    tR = {d["symbol"]:(i+1)/n for i,d in enumerate(bt)}
    for d in items:
        pr = 1 - pR[d["symbol"]]
        tr = 1 - tR[d["symbol"]]
        d["score"] = round(math.sqrt(max(pr,0)*max(tr,0))*100, 2)
    return items

@app.route("/")
def proxy():
    try:
        items = fetch_nse_data()
        if not items:
            return jsonify({"status":"error","message":"No data returned from Yahoo Finance"}), 500

        items = add_scores(items)
        gainers = [d["symbol"] for d in items if d["pct_change"] > 0]
        gainers.sort(key=lambda s: next(d["pct_change"] for d in items if d["symbol"]==s), reverse=True)
        top20 = gainers[:20]

        logger.info("OK - " + str(len(items)) + " stocks, " + str(len(top20)) + " gainers")
        return jsonify({
            "status":        "ok",
            "data":          items,
            "top20_gainers": top20,
            "count":         len(items)
        })
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return jsonify({"status":"error","message":str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"status":"ok"})

if __name__ == "__main__":
    app.run(debug=False)
