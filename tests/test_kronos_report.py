import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from kronos_report import brief, HKT

class KronosReportTests(unittest.TestCase):
    def test_readiness_and_freshness(self):
        now=datetime(2026,10,25,7,tzinfo=HKT)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'forecast.json'
            self.assertIn('暫無',brief(p,now))
            data={'generated_at':now.isoformat(),'forecasts':[{'ticker':'0700','status':'FORECAST_ONLY','endpoint_return':0.03}]}
            p.write_text(json.dumps(data))
            self.assertIn('0700 +3.0%',brief(p,now))
            self.assertIn('暫無',brief(p,now+timedelta(hours=27)))
            data['forecasts'][0]['endpoint_return']=float('nan')
            p.write_text(json.dumps(data))
            self.assertIn('暫無',brief(p,now))

    def test_render_includes_model_with_risk_gates(self):
        from final_summary import render_final_summary
        now=datetime(2026,10,25,7,tzinfo=HKT)
        text=render_final_summary({'date':'2026-10-25','signals':{}},now=now,kronos_line='Kronos：暫無有效預測。')
        self.assertIn('Kronos',text)
        self.assertIn('不開新倉',text)
        self.assertLessEqual(len(text),1200)
