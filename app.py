# app.py - NSE Proxy for Render.com
# Uses ScraperAPI to route through Indian residential IPs (bypasses NSE block)

import math, logging
import requests
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# ── ScraperAPI key ──────────────────────────────────────────────────────────
# Sign up free at scraperapi.com — paste your key here
SCRAPER_KEY = "6cc24218f80cbe809c31ead716449724"

BASE = "https://www.nseindia.com"
URLS = {
    "gainers": BASE + "/api/live-analysis-variations?index=gainers&limit=20",
    "active":  BASE + "/api/live-analysis-most-active-securities?index=value&limit=50",
    "volume":  BASE + "/api/live-analysis-volume-spurts?index=loosers",
}

def get_session():
    # ScraperAPI handles all cookies and headers automatically
    return requests.Session()

def fetch(url):
    # Route every NSE request through ScraperAPI Indian residential IP
    proxy_url = (
        "https://api.scraperapi.com"
        "?api_key="6cc24218f80cbe809c31ead716449724"
        "&url=" + requests.utils.quote(url, safe="") +
        "&country_code=in"
        "&render=false"
    )
    r = requests.get(proxy_url, timeout=60)
    r.raise_for_status()
    return r.json()

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
        logger.info("Fetching gainers via ScraperAPI...")
        g = parse(fetch(URLS["gainers"]), True)

        logger.info("Fetching most active...")
        a = parse(fetch(URLS["active"]))

        v = {}
        try:
            logger.info("Fetching volume spurts...")
            v = parse(fetch(URLS["volume"]))
        except Exception as e:
            logger.warning("Volume skipped: " + str(e))

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
