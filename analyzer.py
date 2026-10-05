import pandas as pd
from data_fetcher import fetch_all_data, get_recent_trading_dates

RANK_LIMIT = 30


def get_rankings(df, market_label):
    if df is None or df.empty:
        return {}

    df = df[df['code'].str.match(r'^\d{4,6}$')].copy()

    foreign_buy = df.nlargest(RANK_LIMIT, 'foreign_net')[['code', 'name', 'foreign_net']].copy()
    foreign_buy = foreign_buy[foreign_buy['foreign_net'] > 0]
    foreign_sell = df.nsmallest(RANK_LIMIT, 'foreign_net')[['code', 'name', 'foreign_net']].copy()
    foreign_sell = foreign_sell[foreign_sell['foreign_net'] < 0]

    trust_buy = df.nlargest(RANK_LIMIT, 'trust_net')[['code', 'name', 'trust_net']].copy()
    trust_buy = trust_buy[trust_buy['trust_net'] > 0]
    trust_sell = df.nsmallest(RANK_LIMIT, 'trust_net')[['code', 'name', 'trust_net']].copy()
    trust_sell = trust_sell[trust_sell['trust_net'] < 0]

    return {
        'foreign_buy': foreign_buy.reset_index(drop=True),
        'foreign_sell': foreign_sell.reset_index(drop=True),
        'trust_buy': trust_buy.reset_index(drop=True),
        'trust_sell': trust_sell.reset_index(drop=True),
        'market': market_label,
        'raw_df': df,
    }


def _build_stock_lookup(rankings):
    lookup = {}
    raw = rankings.get('raw_df')
    if raw is not None and not raw.empty:
        for _, row in raw.iterrows():
            lookup[row['code']] = {
                'name': row['name'],
                'foreign_net': row['foreign_net'],
                'trust_net': row['trust_net'],
            }
    return lookup


def color_code(rankings_today, rankings_yesterday=None):
    results = []

    for market_key, market_label in [('tse', '上市'), ('otc', '上櫃')]:
        today = rankings_today.get(market_key, {})
        yesterday = (rankings_yesterday or {}).get(market_key, {})

        if not today:
            continue

        fb = set(today.get('foreign_buy', pd.DataFrame()).get('code', []))
        fs = set(today.get('foreign_sell', pd.DataFrame()).get('code', []))
        tb = set(today.get('trust_buy', pd.DataFrame()).get('code', []))
        ts = set(today.get('trust_sell', pd.DataFrame()).get('code', []))

        y_fb = set(yesterday.get('foreign_buy', pd.DataFrame()).get('code', []) if yesterday else [])
        y_fs = set(yesterday.get('foreign_sell', pd.DataFrame()).get('code', []) if yesterday else [])
        y_tb = set(yesterday.get('trust_buy', pd.DataFrame()).get('code', []) if yesterday else [])
        y_ts = set(yesterday.get('trust_sell', pd.DataFrame()).get('code', []) if yesterday else [])

        all_codes = fb | fs | tb | ts
        lookup = _build_stock_lookup(today)

        for code in all_codes:
            info = lookup.get(code, {})
            name = info.get('name', '')
            foreign_net = info.get('foreign_net', 0)
            trust_net = info.get('trust_net', 0)

            color = None
            reasons = []

            if code in fb and code in tb:
                color = 'red'
                reasons.append('外資+投信同步買超')
            elif code in fs and code in ts:
                color = 'red'
                reasons.append('外資+投信同步賣超')
            elif (code in fb and code in y_fb) or (code in tb and code in y_tb):
                color = 'blue'
                reasons.append('連續2日法人買超')
            elif (code in fs and code in y_fs) or (code in ts and code in y_ts):
                color = 'blue'
                reasons.append('連續2日法人賣超')
            elif (code in fb and code in ts) or (code in tb and code in fs):
                color = 'green'
                reasons.append('外資投信方向相反')
            else:
                color = 'yellow'
                reasons.append('新進榜')

            is_buy_dominant = (code in fb or code in tb) and not (code in fs or code in ts)
            is_sell_dominant = (code in fs or code in ts) and not (code in fb or code in tb)

            focus_market = '外資' if market_label == '上市' else '投信'

            results.append({
                'code': code,
                'name': name,
                'color': color,
                'market': market_label,
                'market_key': market_key,
                'foreign_net': foreign_net,
                'trust_net': trust_net,
                'in_foreign_buy': code in fb,
                'in_foreign_sell': code in fs,
                'in_trust_buy': code in tb,
                'in_trust_sell': code in ts,
                'was_in_foreign_buy_yesterday': code in y_fb,
                'was_in_trust_buy_yesterday': code in y_tb,
                'is_buy_dominant': is_buy_dominant,
                'is_sell_dominant': is_sell_dominant,
                'focus_market': focus_market,
                'reasons': reasons,
            })

    return results


COLOR_PRIORITY = {'red': 0, 'blue': 1, 'yellow': 2, 'green': 3}


def filter_and_sort(stocks, market_direction='up'):
    filtered = []
    for s in stocks:
        if s['color'] == 'green':
            filtered.append(s)
        elif market_direction == 'up' and s['is_buy_dominant']:
            filtered.append(s)
        elif market_direction == 'down' and s['is_sell_dominant']:
            filtered.append(s)
        elif market_direction == 'unknown':
            filtered.append(s)

    filtered.sort(key=lambda x: (COLOR_PRIORITY.get(x['color'], 9), -abs(x['foreign_net'] + x['trust_net'])))
    return filtered


def _rankings_to_serializable(rankings):
    result = {}
    for k, v in rankings.items():
        if k == 'raw_df':
            continue
        if isinstance(v, pd.DataFrame):
            result[k] = v.to_dict('records')
        else:
            result[k] = v
    return result


def analyze(date_str=None):
    if date_str is None:
        dates = get_recent_trading_dates(3)
        date_str = dates[0]

    tse_df, otc_df, index_info = fetch_all_data(date_str)

    dates = get_recent_trading_dates(5)
    yesterday_str = None
    for d in dates:
        if d < date_str:
            yesterday_str = d
            break

    rankings_today = {
        'tse': get_rankings(tse_df, '上市'),
        'otc': get_rankings(otc_df, '上櫃'),
    }

    rankings_yesterday = None
    if yesterday_str:
        try:
            tse_y, otc_y, _ = fetch_all_data(yesterday_str)
            rankings_yesterday = {
                'tse': get_rankings(tse_y, '上市'),
                'otc': get_rankings(otc_y, '上櫃'),
            }
        except Exception:
            pass

    all_stocks = color_code(rankings_today, rankings_yesterday)
    market_direction = index_info.get('direction', 'unknown')

    buy_stocks = filter_and_sort(all_stocks, 'up')
    sell_stocks = filter_and_sort(all_stocks, 'down')
    recommended = filter_and_sort(all_stocks, market_direction)

    priority_label = '買超' if market_direction == 'up' else '賣超' if market_direction == 'down' else '全部'

    tse_r = rankings_today['tse']
    otc_r = rankings_today['otc']

    return {
        'date': date_str,
        'market_direction': market_direction,
        'market_close': index_info.get('close', 0),
        'market_change': index_info.get('change', 0),
        'priority_label': priority_label,
        'recommended': recommended,
        'buy_stocks': buy_stocks,
        'sell_stocks': sell_stocks,
        'all_stocks': all_stocks,
        'stats': {
            'total_screened': len(all_stocks),
            'red_count': sum(1 for s in all_stocks if s['color'] == 'red'),
            'blue_count': sum(1 for s in all_stocks if s['color'] == 'blue'),
            'green_count': sum(1 for s in all_stocks if s['color'] == 'green'),
            'yellow_count': sum(1 for s in all_stocks if s['color'] == 'yellow'),
            'recommended_count': len(recommended),
        },
        'rankings': {
            'tse_foreign_buy': _rankings_to_serializable(tse_r).get('foreign_buy', []) if tse_r else [],
            'tse_foreign_sell': _rankings_to_serializable(tse_r).get('foreign_sell', []) if tse_r else [],
            'tse_trust_buy': _rankings_to_serializable(tse_r).get('trust_buy', []) if tse_r else [],
            'tse_trust_sell': _rankings_to_serializable(tse_r).get('trust_sell', []) if tse_r else [],
            'otc_foreign_buy': _rankings_to_serializable(otc_r).get('foreign_buy', []) if otc_r else [],
            'otc_foreign_sell': _rankings_to_serializable(otc_r).get('foreign_sell', []) if otc_r else [],
            'otc_trust_buy': _rankings_to_serializable(otc_r).get('trust_buy', []) if otc_r else [],
            'otc_trust_sell': _rankings_to_serializable(otc_r).get('trust_sell', []) if otc_r else [],
        }
    }


if __name__ == '__main__':
    result = analyze()
    print(f"Date: {result['date']}")
    print(f"Market: {result['market_direction']} (close={result['market_close']}, change={result['market_change']})")
    print(f"Stats: {result['stats']}")
    print(f"\nRecommended ({result['priority_label']}):")
    for s in result['recommended'][:20]:
        fn = s['foreign_net']
        tn = s['trust_net']
        print(f"  [{s['color'].upper():6}] {s['market']} {s['code']} {s['name']:10} foreign={fn:>12,} trust={tn:>12,} | {', '.join(s['reasons'])}")
