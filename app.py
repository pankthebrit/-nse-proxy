# app.py - NSE Heatmap using Yahoo Finance batch download
# Single API call for all stocks - fast and reliable

import math, logging
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")
import yfinance as yf
yf.set_tz_cache_location("/tmp/yfinance_cache")
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# Nifty 100 + key midcap stocks with Yahoo Finance .NS suffix
SYMBOLS_NS = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","BHARTIARTL.NS","ICICIBANK.NS",
    "INFY.NS","SBIN.NS","HINDUNILVR.NS","ITC.NS","KOTAKBANK.NS",
    "LT.NS","BAJFINANCE.NS","HCLTECH.NS","AXISBANK.NS","MARUTI.NS",
    "ASIANPAINT.NS","SUNPHARMA.NS","M&M.NS","TITAN.NS","NESTLEIND.NS",
    "ULTRACEMCO.NS","DRREDDY.NS","WIPRO.NS","BAJAJFINSV.NS","POWERGRID.NS",
    "NTPC.NS","CIPLA.NS","ONGC.NS","TATASTEEL.NS","COALINDIA.NS",
    "TECHM.NS","GRASIM.NS","INDUSINDBK.NS","TATAMOTORS.NS","ADANIPORTS.NS",
    "BRITANNIA.NS","BPCL.NS","EICHERMOT.NS","SHRIRAMFIN.NS","HEROMOTOCO.NS",
    "DIVISLAB.NS","APOLLOHOSP.NS","TATACONSUM.NS","SBILIFE.NS","HDFCLIFE.NS",
    "BAJAJ-AUTO.NS","JSWSTEEL.NS","HINDALCO.NS","ADANIENT.NS","SIEMENS.NS",
    "HAL.NS","BEL.NS","ABB.NS","PIDILITIND.NS","DABUR.NS","MARICO.NS",
    "HAVELLS.NS","TATAPOWER.NS","CANBK.NS","PNB.NS","FEDERALBNK.NS",
    "IDFCFIRSTB.NS","RBLBANK.NS","AUBANK.NS","KARURVYSYA.NS","MUTHOOTFIN.NS",
    "CHOLAFIN.NS","ZOMATO.NS","NAUKRI.NS","IRCTC.NS","IRFC.NS",
    "PFC.NS","RECLTD.NS","HUDCO.NS","RVNL.NS","NBCC.NS","SJVN.NS",
    "MANKIND.NS","LUPIN.NS","AUROPHARMA.NS","TORNTPHARM.NS","ALKEM.NS",
    "LAURUSLABS.NS","GLAND.NS","PPLPHARMA.NS","AJANTPHARM.NS","GLENMARK.NS",
    "JSWINFRA.NS","LICI.NS","DMART.NS","TRENT.NS","MSTC.NS",
    "IIFL.NS","ADANIGREEN.NS","ADANIPOWER.NS","VEDL.NS","SBICARD.NS",
    "BANDHANBNK.NS","BANKBARODA.NS","INDIAMART.NS","CONCOR.NS",
]

def sf(v):
    try:
        f = float(v)
        return 0.0 if (f != f) else round(f, 2)
    except:
        return 0.0

def si(v):
    try:
        return int(float(v))
    except:
        return 0

@app.route("/")
def proxy():
    try:
        logger.info("Batch downloading " + str(len(SYMBOLS_NS)) + " stocks from Yahoo Finance...")

        # Single batch call — all stocks at once, today's data
        df = yf.download(
            tickers=SYMBOLS_NS,
            period="2d",          # 2 days to get prev close + today
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,         # parallel download
        )

        logger.info("Download complete, processing...")

        items = []
        gainers_map = {}

        for sym_ns in SYMBOLS_NS:
            sym = sym_ns.replace(".NS", "")
            try:
                close  = df["Close"][sym_ns]
                volume = df["Volume"][sym_ns]
                open_  = df["Open"][sym_ns]
                high   = df["High"][sym_ns]
                low    = df["Low"][sym_ns]

                # today = last row, prev = second-to-last
                if len(close.dropna()) < 2:
                    continue

                ltp        = sf(close.iloc[-1])
                prev_close = sf(close.iloc[-2])
                today_vol  = si(volume.iloc[-1])
                today_open = sf(open_.iloc[-1])
                today_high = sf(high.iloc[-1])
                today_low  = sf(low.iloc[-1])

                if ltp == 0 or prev_close == 0:
                    continue

                pct_change  = round((ltp - prev_close) / prev_close * 100, 2)
                turnover_cr = round(ltp * today_vol / 1e7, 2)

                item = {
                    "symbol":      sym,
                    "series":      "EQ",
                    "ltp":         ltp,
                    "prev_close":  prev_close,
                    "pct_change":  pct_change,
                    "open":        today_open,
                    "high":        today_high,
                    "low":         today_low,
                    "volume":      today_vol,
                    "turnover_cr": turnover_cr,
                    "is_gainer":   pct_change > 0,
                    "score":       0.0,
                }
                items.append(item)

                if pct_change > 0:
                    gainers_map[sym] = pct_change

            except Exception as e:
                logger.debug("Skip " + sym + ": " + str(e))

        if not items:
            return jsonify({"status":"error",
                           "message":"No data — market may be closed"}), 500

        # Composite score
        n = len(items)
        bp = sorted(items, key=lambda x: x["pct_change"],  reverse=True)
        bt = sorted(items, key=lambda x: x["turnover_cr"], reverse=True)
        pR = {d["symbol"]:(i+1)/n for i,d in enumerate(bp)}
        tR = {d["symbol"]:(i+1)/n for i,d in enumerate(bt)}
        for d in items:
            pr = 1 - pR[d["symbol"]]
            tr = 1 - tR[d["symbol"]]
            d["score"] = round(math.sqrt(max(pr,0)*max(tr,0))*100, 2)

        top20 = sorted(gainers_map, key=gainers_map.get, reverse=True)[:20]

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
