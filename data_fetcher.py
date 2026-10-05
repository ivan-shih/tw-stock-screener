import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

TSE_PREFIXES = {'1', '2', '6'}
OTC_PREFIXES = {'3', '4', '5', '8', '9'}


def _parse_number(s):
    if s is None:
        return 0
    s = str(s).replace(',', '').replace(' ', '').strip()
    if s in ('', '-', '--', 'N/A', 'X'):
        return 0
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return 0


def _classify_market(code):
    if code.startswith('0'):
        return None
    first = code[0]
    if first in TSE_PREFIXES:
        return 'TSE'
    if first in OTC_PREFIXES:
        return 'OTC'
    return 'TSE'


def fetch_twse_t86(date_str):
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.encoding = 'utf-8'
    data = resp.json()
    if data.get('stat') != 'OK':
        return None, None

    tse_rows = []
    otc_rows = []
    for row in data.get('data', []):
        code = row[0].strip()
        name = row[1].strip()
        market = _classify_market(code)
        if market is None:
            continue

        entry = {
            'code': code,
            'name': name,
            'foreign_buy': _parse_number(row[2]),
            'foreign_sell': _parse_number(row[3]),
            'foreign_net': _parse_number(row[4]),
            'trust_buy': _parse_number(row[8]),
            'trust_sell': _parse_number(row[9]),
            'trust_net': _parse_number(row[10]),
            'dealer_net': _parse_number(row[11]),
            'total_net': _parse_number(row[18]),
            'market': market,
        }
        if market == 'TSE':
            tse_rows.append(entry)
        else:
            otc_rows.append(entry)

    tse_df = pd.DataFrame(tse_rows) if tse_rows else pd.DataFrame()
    otc_df = pd.DataFrame(otc_rows) if otc_rows else pd.DataFrame()
    return tse_df, otc_df


def fetch_market_index(date_str):
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={date_str}&response=json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        data = resp.json()
        if data.get('stat') == 'OK' and data.get('data'):
            latest = data['data'][-1]
            close = _parse_number(latest[4].replace(',', ''))
            change = _parse_number(latest[5].replace(',', ''))
            return {'close': close, 'change': change, 'direction': 'up' if change > 0 else 'down'}
    except Exception:
        pass
    return {'close': 0, 'change': 0, 'direction': 'unknown'}


def fetch_all_data(date_str):
    cache_file = os.path.join(DATA_DIR, f"raw_{date_str}.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            cached = json.load(f)
            tse_df = pd.DataFrame(cached['tse']) if cached.get('tse') else pd.DataFrame()
            otc_df = pd.DataFrame(cached['otc']) if cached.get('otc') else pd.DataFrame()
            index_info = cached.get('index', {'close': 0, 'change': 0, 'direction': 'unknown'})
            return tse_df, otc_df, index_info

    print(f"[INFO] Fetching TWSE data for {date_str}...")
    tse_df, otc_df = fetch_twse_t86(date_str)
    if tse_df is None:
        tse_df = pd.DataFrame()
    if otc_df is None:
        otc_df = pd.DataFrame()

    index_info = fetch_market_index(date_str)

    print(f"[INFO] {date_str}: TSE={len(tse_df)} stocks, OTC={len(otc_df)} stocks")

    if not tse_df.empty or not otc_df.empty:
        cache = {
            'tse': tse_df.to_dict(orient='records') if not tse_df.empty else [],
            'otc': otc_df.to_dict(orient='records') if not otc_df.empty else [],
            'index': index_info,
            'date': date_str,
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

    return tse_df, otc_df, index_info


def get_recent_trading_dates(n=3):
    dates = []
    d = datetime.now()
    while len(dates) < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            dates.append(d.strftime('%Y%m%d'))
    return dates


def clear_cache():
    import glob
    for f in glob.glob(os.path.join(DATA_DIR, '*.json')):
        os.remove(f)
    print("[INFO] Cache cleared")


if __name__ == '__main__':
    dates = get_recent_trading_dates(3)
    print(f"Recent trading dates: {dates}")
    for d in dates:
        tse, otc, idx = fetch_all_data(d)
        print(f"  {d}: TSE={len(tse)} stocks, OTC={len(otc)} stocks, Index={idx}")
