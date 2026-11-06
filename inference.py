import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InferenceError(RuntimeError):
    pass


class BaseProvider:
    def get_initial_request(self):
        raise NotImplementedError

    def get_replanned_request(self, denial_feedback):
        raise NotImplementedError

    def get_scoped_response(self, approved_request):
        raise NotImplementedError

    def get_agent_a_code(self):
        raise NotImplementedError

    def get_report_code(self):
        raise NotImplementedError


AGENT_A_CODE = '''
import csv
import json
from pathlib import Path

with Path('/workspace/customers.csv').open(newline='') as source:
    rows = list(csv.DictReader(source))
revenue_by_segment = {}
for row in rows:
    segment = row['segment']
    revenue_by_segment[segment] = revenue_by_segment.get(segment, 0) + float(row['revenue'])
output = {key: int(value) for key, value in sorted(revenue_by_segment.items())}
Path('/output/revenue_by_segment.json').write_text(json.dumps(output, indent=2))
print(json.dumps(output))
'''

REPORT_CODE = '''
import html
import json
from pathlib import Path

with Path('/workspace/revenue_by_segment.json').open() as source:
    data = json.load(source)
label_map = {'enterprise': 'Enterprise', 'mid_market': 'Mid-market', 'small_business': 'Small business'}
rows = ''.join(
    f"<tr><td>{html.escape(label_map.get(key, key))}</td><td>${value:,.0f}</td></tr>"
    for key, value in data.items()
)
report = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Revenue Report</title>
<style>body {{ font-family: Arial, sans-serif; margin: 2rem; }} table {{ border-collapse: collapse; width: 320px; }} th, td {{ border: 1px solid #ccc; padding: 0.6rem; text-align: left; }}</style>
</head><body><h1>Revenue Report</h1><table><thead><tr><th>Segment</th><th>Revenue</th></tr></thead><tbody>{rows}</tbody></table></body></html>"""
Path('/output/report.html').write_text(report)
print('report generated')
'''


class MockProvider(BaseProvider):
    provider_name = 'mock'
    def get_initial_request(self):
        return 'Customer-level records and revenue data.'

    def get_replanned_request(self, denial_feedback):
        return 'Provide revenue aggregated by customer segment for the current report.'

    def get_scoped_response(self, approved_request):
        return 'I can provide revenue aggregated by customer segment for this report.'

    def get_agent_a_code(self):
        return AGENT_A_CODE

    def get_report_code(self):
        return REPORT_CODE


class VultrProvider(BaseProvider):
    provider_name = 'vultr'
    def __init__(self):
        self.base_url = os.getenv('VULTR_INFERENCE_BASE_URL', '').strip().rstrip('/')
        self.api_key = os.getenv('VULTR_INFERENCE_API_KEY', '').strip()
        self.model = os.getenv('VULTR_MODEL', '').strip()
        if not all((self.base_url, self.api_key, self.model)):
            raise InferenceError('Vultr inference requires VULTR_INFERENCE_BASE_URL, VULTR_INFERENCE_API_KEY, and VULTR_MODEL')
        if not self.base_url.startswith('https://'):
            raise InferenceError('VULTR_INFERENCE_BASE_URL must use HTTPS')

    def _complete(self, user_prompt):
        payload = json.dumps({
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': 'You are an agent in a secure data-sharing demo. Return one concise plain-text sentence only. Follow the user instruction exactly.'},
                {'role': 'user', 'content': user_prompt},
            ],
            'max_completion_tokens': 1024,
            'temperature': 0,
        }).encode()
        request = Request(
            self.base_url + '/chat/completions', data=payload, method='POST',
            headers={'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'},
        )
        try:
            with urlopen(request, timeout=60) as response:
                body = json.load(response)
            content = body['choices'][0]['message']['content']
            if not isinstance(content, str) or not content.strip():
                raise ValueError('empty completion')
            return content.strip()
        except HTTPError as exc:
            raise InferenceError(f'Vultr inference HTTP {exc.code}') from None
        except URLError:
            raise InferenceError('Vultr inference connection failed') from None
        except TimeoutError:
            raise InferenceError('Vultr inference timed out') from None
        except (KeyError, IndexError, TypeError, ValueError):
            raise InferenceError('Vultr inference returned an invalid completion') from None

    def get_initial_request(self):
        return self._complete('You are Agent B preparing a revenue report. Make an initial request to Agent A for customer-level records and revenue data. Include the exact phrase customer-level records. This request is expected to be denied by policy.')

    def get_replanned_request(self, denial_feedback):
        return self._complete('Your initial request was denied. Structured policy feedback: ' + json.dumps(denial_feedback, sort_keys=True) + '. Replan with a request for revenue aggregated by customer segment for the current report. Do not request customer-level data or identifiers.')

    def get_scoped_response(self, approved_request):
        return self._complete('You are Agent A. Respond to this approved request with a one-sentence commitment limited to the aggregate revenue_by_segment.json artifact for the current revenue report. Request: ' + approved_request)

    def get_agent_a_code(self):
        return AGENT_A_CODE

    def get_report_code(self):
        return REPORT_CODE


def get_provider():
    provider_name = (os.getenv('LLM_PROVIDER', 'mock') or 'mock').strip().lower()
    if provider_name == 'mock':
        return MockProvider()
    if provider_name == 'vultr':
        return VultrProvider()
    raise InferenceError('LLM_PROVIDER must be mock or vultr')
