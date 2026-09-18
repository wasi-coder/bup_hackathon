import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
case = json.loads(next(root.glob('*Sample_Cases.json')).read_text())['cases'][0]
destination = root / 'examples'
destination.mkdir(exist_ok=True)
(destination / 'sample-request.json').write_text(json.dumps(case['input'], indent=2), encoding='utf-8')
print('Wrote examples/sample-request.json')
