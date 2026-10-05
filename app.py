from flask import Flask, render_template, jsonify, request
from analyzer import analyze
from data_fetcher import get_recent_trading_dates
import json
import os

app = Flask(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cached_result(date_str):
    cache_file = os.path.join(CACHE_DIR, f"result_{date_str}.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_cached_result(date_str, result):
    cache_file = os.path.join(CACHE_DIR, f"result_{date_str}.json")
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/analyze')
def api_analyze():
    date_str = request.args.get('date', None)
    if date_str is None:
        dates = get_recent_trading_dates(2)
        date_str = dates[0]

    cached = get_cached_result(date_str)
    if cached:
        return jsonify(cached)

    try:
        result = analyze(date_str)
        save_cached_result(date_str, result)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/dates')
def api_dates():
    dates = get_recent_trading_dates(30)
    return jsonify(dates)


@app.route('/api/rankings')
def api_rankings():
    date_str = request.args.get('date', None)
    if date_str is None:
        dates = get_recent_trading_dates(2)
        date_str = dates[0]

    cached = get_cached_result(date_str)
    if cached:
        return jsonify(cached.get('rankings', {}))

    try:
        result = analyze(date_str)
        save_cached_result(date_str, result)
        return jsonify(result.get('rankings', {}))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("  法人買賣超選股系統 - 麥克連選股法")
    print("  開啟瀏覽器訪問: http://localhost:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
