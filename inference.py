import os


class BaseProvider:
    def get_initial_request(self):
        raise NotImplementedError

    def get_replanned_request(self, denial_feedback):
        raise NotImplementedError

    def get_agent_a_code(self):
        raise NotImplementedError

    def get_report_code(self):
        raise NotImplementedError


class MockProvider(BaseProvider):
    def get_initial_request(self):
        return "Customer-level records and revenue data."

    def get_replanned_request(self, denial_feedback):
        return "Provide revenue aggregated by customer segment for the current report."

    def get_agent_a_code(self):
        return '''
import csv
import json
from pathlib import Path

path = Path('/workspace/customers.csv')
out = Path('/workspace/revenue_by_segment.json')
rows = []
with path.open(newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

revenue_by_segment = {}
for row in rows:
    segment = row['segment']
    revenue_by_segment[segment] = revenue_by_segment.get(segment, 0) + float(row['revenue'])

output = {key: int(value) for key, value in sorted(revenue_by_segment.items())}
out.write_text(json.dumps(output, indent=2))
print(json.dumps(output))
'''

    def get_report_code(self):
        return '''
import json
from pathlib import Path

infile = Path('/workspace/revenue_by_segment.json')
outfile = Path('/workspace/report.html')
with infile.open() as f:
    data = json.load(f)

rows = "\\n".join(
    f"<tr><td>{key}</td><td>${value:,.0f}</td></tr>" for key, value in data.items()
)
html = f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\">
  <title>Revenue Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; width: 320px; }}
    th, td {{ border: 1px solid #ccc; padding: 0.6rem; text-align: left; }}
  </style>
</head>
<body>
  <h1>Revenue Report</h1>
  <table>
    <thead><tr><th>Segment</th><th>Revenue</th></tr></thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
"""
outfile.write_text(html)
print('report generated')
'''


class VultrProvider(BaseProvider):
    def __init__(self):
        self.base_url = os.getenv('VULTR_INFERENCE_BASE_URL', '').strip()
        self.api_key = os.getenv('VULTR_INFERENCE_API_KEY', '').strip()
        self.model = os.getenv('VULTR_MODEL', '').strip()

    def get_initial_request(self):
        return MockProvider().get_initial_request()

    def get_replanned_request(self, denial_feedback):
        return MockProvider().get_replanned_request(denial_feedback)

    def get_agent_a_code(self):
        return MockProvider().get_agent_a_code()

    def get_report_code(self):
        return MockProvider().get_report_code()


def get_provider():
    provider_name = (os.getenv('LLM_PROVIDER', 'mock') or 'mock').lower()
    if provider_name == 'vultr':
        return VultrProvider()
    return MockProvider()
