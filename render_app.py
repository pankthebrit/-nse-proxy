# app.py - NSE Proxy for Render.com
# Render IPs are NOT blocked by NSE

import math, time, logging
import requests
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

BASE = "https://www.nseindia.com"
URLS = {
    "gainers": BASE + "/api/live-analysis-variations?index=gainers&limit=20",
    "active":  BASE + "/api/live-analysis-most-active-securities?index=value&limit=50",
    "volume":  BASE + "/api/live-analysis-volume-spurts?index=loosers",
}
HTML_HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
API_HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/market-data/top-gainers-losers",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

def get_session():
    s = requests.Session()
    try:
        s.get(BASE, headers=HTML_HDR, timeout=15)
        time.sleep(2)
        s.get(BASE + "/market-data/top-gainers-losers", headers=HTML_HDR, timeout=15)
        time.sleep(1)
    except Exception as e:
        logger.warning("Session: " + str(e))
    return s

def sf(v):
    try: return float(v or 0)
    except: return 0.0

def si(v):
    try: return int(float(v or 0))
    except: return 0

def parse(data, is_gainer=False):
    rows = data if isinstance(data, list) else data.get("data", [])
    out = {}
    for it in rows:
        sym = str(it.get("symbol","")).strip()
        if not sym: continue
        out[sym] = {
            "symbol":      sym,
            "series":      it.get("series","EQ"),
            "ltp":         sf(it.get("lastPrice",    it.get("ltp",0))),
            "prev_close":  sf(it.get("previousClose",it.get("previousPrice",0))),
            "pct_change":  sf(it.get("pChange",0)),
            "open":        sf(it.get("open",0)),
            "high":        sf(it.get("dayHigh",  it.get("high",0))),
            "low":         sf(it.get("dayLow",   it.get("low",0))),
            "volume":      si(it.get("totalTradedVolume",it.get("quantityTraded",0))),
            "turnover_cr": round(sf(it.get("totalTradedValue",
                                   it.get("turnover",0)))/1e7, 2),
            "is_gainer":   is_gainer,
            "score":       0.0,
        }
    return out

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
        s = get_session()
        logger.info("Fetching gainers...")
        g = parse(s.get(URLS["gainers"], headers=API_HDR, timeout=20).json(), True)
        logger.info("Fetching most active...")
        a = parse(s.get(URLS["active"],  headers=API_HDR, timeout=20).json())
        v = {}
        try:
            v = parse(s.get(URLS["volume"], headers=API_HDR, timeout=20).json())
        except: pass
        merged = {**a, **v, **g}
        for sym, d in merged.items(): d["is_gainer"] = sym in g
        all_items = add_scores(list(merged.values()))
        logger.info("OK - " + str(len(all_items)) + " stocks")
        return jsonify({"status":"ok","data":all_items,
                        "top20_gainers":list(g.keys()),
                        "count":len(all_items)})
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return jsonify({"status":"error","message":str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"status":"ok"})

if __name__ == "__main__":
    app.run(debug=False)
