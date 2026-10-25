import json,tempfile,unittest
from datetime import datetime,timedelta
from pathlib import Path
from fincept_report import brief,HKT

class ArtifactTests(unittest.TestCase):
    def test_valid_partial_stale_and_invalid_artifacts(self):
        now=datetime(2026,10,25,7,tzinfo=HKT)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'f.json'
            self.assertIn('暫無',brief(p,now))
            d={'schema_version':1,'lookback':400,'horizon':5,'order':[1,1,1],'source_commit':'3d8617cae3f13c93874d4bee4fb0f2846e9c83bc','generated_at':now.isoformat(),'data_cutoff':'2026-10-23','universe':[{'code':'0005','group':'bluechip'},{'code':'1299','group':'bluechip'}],'forecasts':[{'ticker':'0005','status':'FORECAST_ONLY','data_cutoff':'2026-10-23','endpoint_return':.01,'last_close':100,'forecast':[101]*5}]}
            p.write_text(json.dumps(d));self.assertIn('1/2標的',brief(p,now))
            self.assertIn('暫無',brief(p,now+timedelta(hours=27)))
            d['forecasts'][0]['forecast']=[];p.write_text(json.dumps(d));self.assertIn('暫無',brief(p,now))
            d['forecasts'][0]['forecast']=[101]*5
            d['forecasts'][0]['endpoint_return']=float('nan');p.write_text(json.dumps(d));self.assertIn('暫無',brief(p,now))
            d['forecasts'][0]['endpoint_return']=.01;d['source_commit']='unknown';p.write_text(json.dumps(d));self.assertIn('暫無',brief(p,now))

    def test_daily_summary_contains_both_models_without_authorizing_options(self):
        from final_summary import render_final_summary
        text=render_final_summary({'date':'2026-10-25','signals':{}},now=datetime(2026,10,25,7,tzinfo=HKT),kronos_line='Kronos：輔助情景。',fincept_line='Fincept ARIMA：輔助情景。')
        self.assertIn('Kronos',text);self.assertIn('Fincept',text);self.assertIn('不開新倉',text);self.assertLessEqual(len(text),1200)
