from datetime import datetime
import json, os, tempfile, types, unittest
from pathlib import Path
from unittest.mock import patch
from trading_workflows import *
from market_recommendations import write_recommendations, build_recommendations
from final_summary import render_final_summary
from daily_delivery import validate_summary, fallback_summary
from test_recommendations import signals
NOW = datetime(2026, 10, 7, 6, 15, tzinfo=HKT)
def trades():
    return [{'id':str(i), 'status':'closed', 'entry_at':'2026-10-01T10:00:00+08:00',
             'exit_at':f'2026-10-0{i+2}T11:00:00+08:00', 'net_pnl':pnl, 'capital_at_risk':1000,
             'rule_violations':['late_exit'] if i==1 else []} for i,pnl in enumerate([100,-50,0])]
def simulation():
    return {**{k:'documented test method' for k in ('strategy','universe','period','cost_model','execution_model','data_source','out_of_sample','benchmark')},
            'instrument_type':'stock','costs_included':True,'equity_marked_to_market':True,'trades':trades(),
            'equity':[{'at':f'2026-10-0{i+1}T{9 if i==0 else 12:02d}:00:00+08:00','value':v} for i,v in enumerate([1000,1100,880,1050])]}
def holdings():
    return {'as_of':NOW.isoformat(),'complete':True,'nav_hkd':1000,'cash_hkd':200,
            'holdings':[{'asset_type':'stock','underlying':'HK.00700','market_value_hkd':800}]}
class WorkflowTests(unittest.TestCase):
    def test_routing_keeps_evidence_and_budget(self):
        graph=types.SimpleNamespace(resolve_instrument_context=lambda *args:'original evidence')
        audit=attach_workflow_context(graph)
        text=graph.resolve_instrument_context('0700.HK')
        for phrase in ('original evidence','Ideas:','Market analyst:','News analyst:','Backtest:','Portfolio:','Journal:'):
            self.assertIn(phrase,text)
        self.assertLess(audit['bytes'],3500)
    def test_daily_writer_six_modules_and_length(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'TAHK_RESEARCH_INPUT_JSON':'','TAHK_RESEARCH_INPUT_PATH':''}):
            root=Path(d); result=write_recommendations(signals(),directory=root,now=NOW)
            text=(root/'final_summary.txt').read_text();validate_summary(text,now=NOW)
            for name in LABELS:
                self.assertIn(name+'：',text)
                self.assertIn('### '+name,(root/'recommendations.md').read_text())
            modules=result['trading_workflows']['modules']
            self.assertEqual([m['status'] for m in modules[:3]],['research_only']*3)
            self.assertTrue(all(m['status']=='blocked' for m in modules[3:]))
            self.assertEqual(result['trading_workflows']['extra_model_calls'],0)
    def test_stale_analysts_blocked(self):
        p={**signals(),'date':'2026-10-06'}
        a=build_workflows(p,build_recommendations(p,now=NOW),now=NOW)
        self.assertTrue(all(m['status']=='blocked' for m in a['modules']))
    def test_backtest_accounting_and_invalid_data(self):
        text,m=backtest(simulation(),NOW)
        self.assertAlmostEqual(m['win_rate'],1/3); self.assertEqual(m['profit_factor'],2)
        self.assertAlmostEqual(m['max_drawdown'],.2);self.assertAlmostEqual(m['mean_net_return'],.05/3)
        self.assertEqual(m['breakeven_count'],1);self.assertIn('未獨立驗證',text)
        d=simulation();d['trades']=[d['trades'][0]];self.assertIsNone(backtest(d,NOW)[1]['profit_factor'])
        for change in ({'costs_included':False},{'instrument_type':'option'},{'equity':[]}):
            with self.assertRaises(ValueError):backtest({**simulation(),**change},NOW)
    def test_portfolio_snapshot_and_nonlinear_risk(self):
        d=holdings();text,m=portfolio(d,NOW)
        self.assertAlmostEqual(m['parallel_stock_shock_nav_return'],-.16);self.assertIn('非大市預測',text)
        for change in ({'nav_hkd':2000},{'as_of':'2026-10-06T06:00:00+08:00'}):
            with self.assertRaises(ValueError):portfolio({**d,**change},NOW)
        d['holdings'][0]['asset_type']='option';self.assertIsNone(portfolio(d,NOW)[1]['stress_pnl'])
    def test_journal_three_rules_and_twenty_trade_limit(self):
        d={'as_of':NOW.isoformat(),'costs_included':True,'trades':trades()}
        m=journal(d,NOW)[1];self.assertEqual(len(m['rules']),3)
        self.assertFalse(m['rules'][0]['provisional']);self.assertTrue(m['rules'][1]['provisional'])
        d['trades']=[dict(trades()[0],id=str(i),exit_at=f'2026-10-02T11:{i:02d}:00+08:00') for i in range(25)]
        self.assertEqual(journal(d,NOW)[1]['count'],20)
        with self.assertRaises(ValueError):journal({**d,'trades':[trades()[0]]*2},NOW)
    def test_malformed_private_inputs_do_not_echo(self):
        for raw in ('PRIVATE invalid','[1]','{"schema_version":2}','x'*40001):
            with patch.dict(os.environ,{'TAHK_RESEARCH_INPUT_JSON':raw}):data,status=load_inputs()
            self.assertEqual((data,status),({},'invalid'))
        p=signals();a=build_workflows(p,build_recommendations(p,now=NOW),inputs={'portfolio':{'nav_hkd':float('nan')},'journal':None,'backtest':[]},input_status='provided',now=NOW)
        self.assertTrue(all(m['status']=='blocked' for m in a['modules'][3:]));json.dumps(a,allow_nan=False)
    def test_optional_data_runs_all_calculations_and_omits_raw_ids(self):
        data={'schema_version':1,'portfolio':holdings(),'backtest':simulation(),
              'journal':{'as_of':NOW.isoformat(),'costs_included':True,'trades':trades()}}
        data['journal']['trades'][0]['id']='PRIVATE_TRADE_ID'
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'TAHK_RESEARCH_INPUT_JSON':json.dumps(data)}):
            root=Path(d);r=write_recommendations(signals(),directory=root,now=NOW)
            self.assertTrue(all(m['status']=='computed_from_supplied_data' for m in r['trading_workflows']['modules'][3:]))
            for p in root.iterdir():self.assertNotIn('PRIVATE_TRADE_ID',p.read_text())
            validate_summary((root/'final_summary.txt').read_text(),now=NOW)
    def test_large_summary_and_failure_have_six_sections(self):
        p=signals();one=p['signals']['HK.00005'];p['signals']={f'HK.{i:05d}':dict(one) for i in (5,388,700,1810,9988)}
        a=build_workflows(p,build_recommendations(p,now=NOW),now=NOW)
        text=render_final_summary(p,now=NOW,workflow_audit=a)
        validate_summary(text,now=NOW);self.assertIn('Margin/Premium',text);self.assertIn('不開新倉',text)
        for message in (text,fallback_summary(NOW)):
            for name in LABELS:self.assertIn(name+'：',message)
            validate_summary(message,now=NOW)

    def test_all_cash_portfolio_is_valid(self):
        text, metrics = portfolio({**holdings(), 'holdings': [], 'cash_hkd': 1000}, NOW)
        self.assertEqual(metrics['gross_nav_ratio'], 0)
        self.assertEqual(metrics['largest_issuer_nav_ratio'], 0)
        self.assertEqual(metrics['parallel_stock_shock_nav_return'], 0)

    def test_extreme_finite_input_blocks_only_affected_module(self):
        data = simulation()
        data['trades'][0].update(net_pnl=1e308, capital_at_risk=1e-308)
        p = signals()
        audit = build_workflows(p, build_recommendations(p, now=NOW), inputs={'backtest': data}, input_status='provided', now=NOW)
        self.assertEqual(audit['modules'][3]['status'], 'blocked')
        self.assertEqual(audit['modules'][0]['status'], 'research_only')
        json.dumps(audit, allow_nan=False)

    def test_compact_branch_keeps_option_identifier_and_six_modules(self):
        from test_option_screen import candidate
        now = NOW.replace(hour=10, minute=30)
        p = signals()
        option = candidate(underlying='HK.00005', option_code='HK.TEST', expiry='2026-11-06', quote_time=now.strftime('%Y-%m-%d %H:%M:%S'))
        quotes = {'generated_at': now.isoformat(), 'candidates': [option], 'errors': []}
        with patch('agents.screening_agent.datetime') as clock:
            clock.strptime.side_effect = datetime.strptime
            clock.now.return_value = now
            audit = build_workflows(p, build_recommendations(p, option_audit=quotes, now=now), now=now)
            text = render_final_summary(p, option_audit=quotes, now=now, workflow_audit=audit,
                                        market_audit={'watchlist': [{'code':'0005', 'name':'長公司名稱'*200}]})
        self.assertIn('主候選（待核）', text)
        self.assertIn('HK.TEST', text)
        self.assertIn('Margin/Premium', text)
        self.assertLessEqual(len(text), 1200)
        for name in LABELS: self.assertIn(name+'：', text)
