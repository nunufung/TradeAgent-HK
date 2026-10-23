"""Optional FinRL stock research: no broker, LLM, Telegram or option entry calls."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
FINRL_ROOT = ROOT / 'external/finrl'
LOCK = json.loads((ROOT / 'integrations/finrl-lock.json').read_text())
ENV_PATH = LOCK['environment_path']
FEATURES = ['return_1', 'sma_5_ratio', 'volatility_5']
ALGORITHMS = ('a2c', 'ppo', 'ddpg', 'sac', 'td3')


def hk_ticker(raw: str) -> str:
    code = str(raw).strip().upper().removeprefix('HK.').removesuffix('.HK')
    if not re.fullmatch(r'\d{1,5}', code) or not 1 <= int(code) <= 99999:
        raise ValueError('Only numeric Hong Kong stock symbols are supported')
    return f'{int(code):04d}.HK'


def prepare_panel(raw: pd.DataFrame) -> pd.DataFrame:
    """Lag close-derived features; trade and value at the next observed open.

    No backfill or invented sessions. A complete fixed-universe panel is required.
    Quantities are synthetic single-share units, not executable HK board lots.
    """
    columns = ['date', 'tic', 'open', 'high', 'low', 'close', 'volume']
    if not set(columns) <= set(raw.columns) or raw.empty:
        raise ValueError('Historical OHLCV columns are required')
    frame = raw[columns].copy()
    frame['tic'] = frame.tic.map(hk_ticker)
    dates = pd.to_datetime(frame.date, errors='raise')
    if dates.isna().any():
        raise ValueError('Missing dates')
    frame['date'] = dates.dt.strftime('%Y-%m-%d')
    if frame.duplicated(['date', 'tic']).any():
        raise ValueError('Duplicate date/ticker rows')
    for col in columns[2:]:
        frame[col] = pd.to_numeric(frame[col], errors='raise')
    values = frame[columns[2:]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError('Finite positive prices and nonnegative volume required')
    # Corporate-action adjustment can create a few ULPs of roundoff between
    # otherwise equal prices. Accept relative numerical noise, not bad bars;
    # preserve every supplied price rather than rounding or repairing it.
    tolerance = frame[['open', 'high', 'low', 'close']].abs().max(axis=1).clip(lower=1) * 1e-12
    if ((frame.high + tolerance < frame[['open', 'close', 'low']].max(axis=1)) |
            (frame.low - tolerance > frame[['open', 'close', 'high']].min(axis=1))).any():
        raise ValueError('Inconsistent OHLC prices')
    count = frame.tic.nunique()
    if len(frame) != frame.date.nunique() * count:
        raise ValueError('Incomplete universe: supply aligned histories without missing rows')
    frame = frame.sort_values(['tic', 'date']).reset_index(drop=True)
    groups = []
    for _, group in frame.groupby('tic', sort=True):
        group = group.copy()
        returns = group.close.pct_change(fill_method=None)
        group['return_1'] = returns.shift(1)
        group['sma_5_ratio'] = (group.close / group.close.rolling(5).mean() - 1).shift(1)
        group['volatility_5'] = returns.rolling(5).std().shift(1)
        # FinRL calls its execution/valuation column "close". Here it contains
        # this session's open; all derived signals use completed prior sessions.
        group['close'] = group.open
        groups.append(group)
    panel = pd.concat(groups).dropna(subset=FEATURES)
    if panel.empty:
        raise ValueError('Insufficient history for lagged features')
    return panel[['date', 'tic', 'close'] + FEATURES].sort_values(['date', 'tic']).reset_index(drop=True)


def split_panel(panel: pd.DataFrame) -> tuple[pd.DataFrame, ...]:
    days = sorted(panel.date.unique())
    n = len(days)
    if n < 30:
        raise ValueError('At least 30 usable sessions required for chronological splits')
    first, second = int(n * .6), int(n * .8)
    parts = []
    for dates in (days[:first], days[first:second], days[second:]):
        part = panel[panel.date.isin(dates)].sort_values(['date', 'tic']).copy()
        part.index = pd.factorize(part.date, sort=True)[0]
        parts.append(part)
    return tuple(parts)


def performance(equity) -> dict:
    values = np.asarray(equity, dtype=float)
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('At least two finite positive equity marks required')
    returns = values[1:] / values[:-1] - 1
    deviation = returns.std(ddof=1) if len(returns) > 1 else 0
    return {'net_return': float(values[-1] / values[0] - 1),
            'max_drawdown': float((1 - values / np.maximum.accumulate(values)).max()),
            'annualized_sharpe': float(returns.mean() / deviation * np.sqrt(252)) if deviation > 1e-12 else None,
            'marks': len(values)}


def buy_hold(panel: pd.DataFrame, *, initial_cash: float, cost: float) -> list[float]:
    prices = panel.pivot(index='date', columns='tic', values='close').sort_index()
    shares = np.floor(initial_cash / len(prices.columns) / (prices.iloc[0] * (1 + cost)))
    cash = initial_cash - float((shares * prices.iloc[0] * (1 + cost)).sum())
    # Both policies start with a pre-trade cash mark and end with open-price
    # marked-to-market holdings. Neither assumes a cost-free final liquidation.
    return [initial_cash] + [float(cash + (shares * row).sum()) for _, row in prices.iterrows()]


def load_finrl_environment(root: Path = FINRL_ROOT):
    path = root / ENV_PATH
    if not path.is_file():
        raise RuntimeError('Initialize the external/finrl submodule before training')
    if hashlib.sha256(path.read_bytes()).hexdigest() != LOCK['environment_sha256']:
        raise RuntimeError('FinRL source differs from the reviewed lock; review before updating')
    # Upstream finrl.__init__ eagerly imports train/trade and unrelated broker
    # dependencies. Load only the pinned public environment, without stubbing or
    # modifying upstream packages or installing unused live-trading integrations.
    spec = importlib.util.spec_from_file_location('tahk_finrl_stock_environment', path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImportError as exc:
        raise RuntimeError('Install requirements-finrl.txt in a dedicated virtual environment') from exc
    return module.StockTradingEnv


def make_env(panel, initial_cash, cost):
    from gymnasium.wrappers import TimeLimit
    cls = load_finrl_environment()
    count = panel.tic.nunique()
    env = cls(df=panel, stock_dim=count, hmax=100, initial_amount=initial_cash,
               num_stock_shares=[0]*count, buy_cost_pct=[cost]*count,
               sell_cost_pct=[cost]*count, reward_scaling=1e-4,
               state_space=1+2*count+len(FEATURES)*count, action_space=count,
               tech_indicator_list=FEATURES, make_plots=False, print_verbosity=10**9)
    # End on the final genuine transition. The pinned upstream otherwise needs
    # another call to signal done, returning the previous transition's reward.
    return TimeLimit(env, max_episode_steps=panel.date.nunique()-1)


def evaluate(model, panel, initial_cash, cost):
    env = make_env(panel, initial_cash, cost)
    observation, _ = env.reset()
    # The final FinRL terminal call repeats the previous reward, so stop after
    # the last genuine transition and obtain the actual account-value memory.
    for _ in range(panel.date.nunique() - 1):
        action, _ = model.predict(np.asarray(observation, dtype=np.float32), deterministic=True)
        observation, _, terminated, truncated, _ = env.step(action)
        if terminated or truncated:
            break
    curve = [float(v) for v in env.unwrapped.asset_memory]
    # Split out the pre-trade initial mark, matching the benchmark convention.
    return curve, float(env.unwrapped.cost)


def run_research(raw, output: Path, *, algorithms=('a2c', 'ppo'), timesteps=10000,
                 initial_cash=100000., cost=.002, seed=42, data_source: str):
    if (not algorithms or len(set(algorithms)) != len(algorithms)
            or any(name not in ALGORITHMS for name in algorithms)):
        raise ValueError('Choose unique supported FinRL/SB3 algorithms')
    if not 32 <= timesteps <= 500000 or not 0 < initial_cash <= 1e12 or not 0 < cost < .1:
        raise ValueError('Invalid training budget, capital or per-side cost assumption')
    if not isinstance(data_source, str) or not data_source.strip():
        raise ValueError('Document the historical data source')
    panel = prepare_panel(raw)
    train, validation, test = split_panel(panel)
    import stable_baselines3 as sb3
    output.mkdir(parents=True, exist_ok=True)
    (output / 'models').mkdir(exist_ok=True)
    classes = {'a2c': sb3.A2C, 'ppo': sb3.PPO, 'ddpg': sb3.DDPG, 'sac': sb3.SAC, 'td3': sb3.TD3}
    models, scores = {}, {}
    for name in algorithms:
        kwargs = dict(seed=seed, verbose=0, device='cpu', policy_kwargs={'net_arch':[32, 32]})
        if name == 'ppo':
            kwargs.update(n_steps=64, batch_size=32, n_epochs=2)
        if name in ('ddpg', 'sac', 'td3'):
            kwargs.update(buffer_size=50000, learning_starts=16, batch_size=32)
        model = classes[name]('MlpPolicy', make_env(train, initial_cash, cost), **kwargs)
        model.learn(total_timesteps=timesteps)
        model.save(output / 'models' / name)
        curve, fees = evaluate(model, validation, initial_cash, cost)
        scores[name] = {**performance(curve), 'transaction_cost_hkd': fees,
                        'trained_timesteps': int(model.num_timesteps)}
        models[name] = model
    # Fixed validation objective; the test period is never used to select models.
    selected = max(algorithms, key=lambda name: scores[name]['net_return'])
    curve, fees = evaluate(models[selected], test, initial_cash, cost)
    # FinRL's last open is only a mark, with no new trade. Buy-and-hold includes
    # the first trade at the first open; align both curves to these same marks.
    baseline = buy_hold(test, initial_cash=initial_cash, cost=cost)
    baseline = [baseline[0]] + baseline[2:]
    result = {
        'schema_version': 1, 'status': 'research_only', 'instrument_type': 'stock',
        'execution_eligible': False, 'allowed_option_types': [], 'extra_llm_calls': 0,
        'generated_at': datetime.now(ZoneInfo('Asia/Hong_Kong')).isoformat(),
        'upstream': LOCK, 'data_source': data_source,
        'data_sha256': hashlib.sha256(raw.to_csv(index=False).encode()).hexdigest(),
        'universe': sorted(panel.tic.unique()), 'seed': seed,
        'initial_cash_hkd': initial_cash, 'per_side_cost_fraction': cost,
        'execution_model': 'prior-session features, observed next open, long-only synthetic single-share units',
        'selection_objective': 'maximum validation net return; first listed model wins ties',
        'periods': {label: {'start': p.date.min(), 'end': p.date.max(), 'sessions': p.date.nunique()}
                    for label, p in zip(('train','validation','test'), (train,validation,test))},
        'validation': scores, 'selected_model': selected,
        'test': {'selected_policy': {**performance(curve), 'transaction_cost_hkd': fees},
                 'equal_weight_buy_hold': performance(baseline),
                 'cash': performance([initial_cash]*len(curve))},
        'limitations': [
            'Historical stock simulation, not an option backtest or live recommendation.',
            'Fixed supplied universe has survivorship/selection bias; no rolling retraining.',
            'Assumed proportional costs include a slippage allowance, not a verified broker fee schedule.',
            'No HK board lots, minimum fees, market impact, dividends paid in cash or final liquidation.',
            'Next-open fills are idealized; adjusted prices must be applied consistently.',
            'Short smoke runs verify plumbing, not profitability; hold-out reuse invalidates independence.',
        ],
    }
    (output / 'finrl_result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    (output / 'finrl_research_input.json').write_text(json.dumps(
        {'schema_version':1, 'finrl':result}, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    pd.DataFrame({'date': ['initial_cash']+sorted(test.date.unique())[1:],
                  'selected_policy': curve, 'equal_weight_buy_hold': baseline}).to_csv(output / 'equity.csv', index=False)
    report = ['# TradeAgent-HK FinRL research',
              'Historical stock simulation | research only | no option entry authorization',
              f'Data source: {data_source}', f'Selected on validation only: {selected}',
              f"Test period: {test.date.min()} to {test.date.max()}",
              '| Policy | Net return | Maximum drawdown | Annualized Sharpe |',
              '| --- | ---: | ---: | ---: |']
    for label, metrics in result['test'].items():
        sharpe = metrics['annualized_sharpe']
        report.append(f"| {label} | {metrics['net_return']:.2%} | {metrics['max_drawdown']:.2%} | {sharpe if sharpe is not None else 'N/A'} |")
    report += ['', '## Assumptions and limits', *['- '+s for s in result['limitations']]]
    (output / 'finrl_report.md').write_text('\n'.join(report)+'\n')
    return result


def download_history(tickers, start, end):
    """Optional public STOCK history; independent of manual option-chain input."""
    import yfinance as yf
    rows = []
    for symbol in sorted(set(map(hk_ticker, tickers))):
        frame = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=True, actions=False)
        if frame.empty:
            raise ValueError(f'No historical prices for {symbol}')
        frame = frame.rename_axis('date').reset_index()
        frame.columns = [str(c).lower() for c in frame.columns]
        frame['date'] = pd.to_datetime(frame.date).dt.strftime('%Y-%m-%d')
        frame['tic'] = symbol
        rows.append(frame[['date','tic','open','high','low','close','volume']])
    return pd.concat(rows, ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--data', type=Path, help='Historical stock OHLCV table; never a Futu option CSV')
    source.add_argument('--tickers', help='Comma-separated HK stock symbols to fetch from Yahoo')
    parser.add_argument('--data-source', help='Required provenance label for local stock history')
    parser.add_argument('--start', default='2020-01-01')
    parser.add_argument('--end', default=datetime.now(ZoneInfo('Asia/Hong_Kong')).date().isoformat())
    parser.add_argument('--algorithms', default='a2c,ppo')
    parser.add_argument('--timesteps', type=int, default=10000)
    parser.add_argument('--cost-bps', type=float, default=20., help='Assumed total friction per side, not verified fees')
    parser.add_argument('--initial-cash', type=float, default=100000.)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=Path, default=Path('finrl-output'))
    args = parser.parse_args()
    if args.data and not args.data_source:
        parser.error('--data-source is required with local stock history')
    import torch
    torch.set_num_threads(1)
    if args.data:
        raw, provenance = pd.read_csv(args.data, dtype={'tic':str}), args.data_source
    else:
        raw = download_history(args.tickers.split(','), args.start, args.end)
        provenance = f'Yahoo Finance via yfinance, adjusted daily OHLCV, {args.start} to {args.end} (exclusive)'
    result = run_research(raw, args.output, algorithms=args.algorithms.split(','),
                          timesteps=args.timesteps, initial_cash=args.initial_cash,
                          cost=args.cost_bps/10000, seed=args.seed, data_source=provenance)
    print(f"FinRL research saved: {args.output}/finrl_report.md; selected={result['selected_model']}; execution_eligible=false")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
