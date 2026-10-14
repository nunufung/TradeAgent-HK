"""Offline/manual JSON enrichment; no API keys or order routing."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fincept_bridge import analyze_snapshot


def main():
    parser = argparse.ArgumentParser(description='Fincept research analytics on manually supplied JSON')
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', default='fincept_analytics.json')
    parser.add_argument('--now', help='Explicit ISO observation time for historical replay; never used by daily entry gates')
    args = parser.parse_args()
    source = Path(args.input)
    if source.stat().st_size > 120_000:
        raise ValueError('Input exceeds manual snapshot budget')
    now = datetime.fromisoformat(args.now) if args.now else None
    if now is not None and now.tzinfo is None:
        raise ValueError('--now must include a timezone')
    result = analyze_snapshot(json.loads(source.read_text()), now=now)
    result['historical_replay'] = args.now is not None
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    print('Fincept research analytics:', result['status'])


if __name__ == '__main__':
    main()
