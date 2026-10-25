"""Read validated, bounded Kronos research without loading model dependencies."""
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

HKT = timezone(timedelta(hours=8))

def brief(path=Path('kronos_forecast.json'), now=None):
    try:
        data = json.loads(Path(path).read_text())
        now = now or datetime.now(HKT)
        generated = datetime.fromisoformat(data['generated_at'])
        if not timedelta(0) <= now - generated <= timedelta(hours=26):
            raise ValueError('stale')
        rows = data['forecasts']
        if not rows or len(rows) > 2:
            raise ValueError('count')
        parts = []
        for row in rows:
            value = row['endpoint_return']
            if row['status'] != 'FORECAST_ONLY' or not math.isfinite(value):
                raise ValueError('invalid')
            code = row['ticker']
            if not code.isdigit() or len(code) != 4:
                raise ValueError('ticker')
            parts.append(f"{code} {value:+.1%}")
        return 'Kronos｜5交易日模型情景：' + '、'.join(parts) + '；未經績效驗證，期權仍須獨立風控。'
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        return 'Kronos：暫無有效新預測；不影響四分析員研究，期權仍須獨立風控。'
