import json,tempfile,unittest
from pathlib import Path
from kronos_bluechip_report import build

class ReportTests(unittest.TestCase):
    def test_failed_stock_remains_visible_without_zero_return_substitution(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);data=root/'inputs'/'artifact'/'0005';data.mkdir(parents=True)
            rows=[dict(ticker='0005',origin='2026-05-01',target='2026-05-08',actual=.02,predicted=.01,zero=0.,trend=.03,valid=True) for _ in range(24)]
            (data/'results.json').write_text(json.dumps({'records':rows}))
            watch=root/'watch.json';watch.write_text(json.dumps({'stocks':[{'code':'0005','name':'HSBC','group':'bluechip'},{'code':'0388','name':'HKEX','group':'bluechip'},{'code':'0700','name':'Tencent','group':'technology'}]}))
            build(root/'inputs',root/'output',watch)
            result=json.loads((root/'output'/'metrics.json').read_text())
            self.assertEqual(len(result['stocks']),2)
            self.assertEqual(result['stocks'][1]['status'],'FAILED_OR_MISSING')
            self.assertEqual(result['pooled']['attempted'],24)
            self.assertIn('0388', (root/'output'/'REPORT.md').read_text())
