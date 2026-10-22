"""P2-u 追補の照会の道具（query-rxnorm-history.py）：応答の読み取りと集計を架空の応答で、通信の規則（再試行・上限・照会する URL）を偽の通信で確かめる。通信は使わない。"""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
import urllib.error
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'scripts/research')]
spec = importlib.util.spec_from_file_location('query_rxnorm_history', ROOT/'scripts/research/query-rxnorm-history.py')
tool = importlib.util.module_from_spec(spec)
sys.modules['query_rxnorm_history'] = tool
spec.loader.exec_module(tool)


def history(status, tty='SCD', start='012020', end='', current='YES', active_start='012020', active_end='', remapped_date='', remapped=(), quantified=0):
    derived = {'ingredientConcept': [{'ingredientRxcui': 'x', 'ingredientName': 'fiction'}]}
    if remapped:
        derived['remappedConcept'] = [{'remappedRxCui': r, 'remappedName': 'fiction', 'remappedTTY': t, 'remappedActive': a} for r, t, a in remapped]
    if quantified:
        derived['quantifiedConcept'] = [{'quantifiedRxcui': 'q'+str(i)} for i in range(quantified)]
    return json.dumps({'rxcuiStatusHistory': {'metaData': {'status': status, 'source': 'RXNORM', 'releaseStartDate': start, 'releaseEndDate': end, 'isCurrent': current,
                                                           'activeStartDate': active_start, 'activeEndDate': active_end, 'remappedDate': remapped_date},
                                              'attributes': {'rxcui': '1', 'name': 'fiction', 'tty': tty}, 'definitionalFeatures': {}, 'pack': {}, 'derivedConcepts': derived}}).encode()


class Response(io.BytesIO):
    def __init__(self, body, status=200):
        super().__init__(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ParsingTests(unittest.TestCase):
    def test_every_documented_status_is_read(self):
        for status in tool.STATUSES:
            self.assertEqual(tool.parse_history(history(status))['status'], status)
        parsed = tool.parse_history(history('Remapped', 'SBD', end='092026', current='NO', active_end='082026', remapped_date='092026', remapped=[('2', 'SBD', 'YES'), ('3', 'SBD', 'NO')]))
        self.assertEqual((parsed['tty'], parsed['release_end'], parsed['remapped_date'], [(r['rxcui'], r['active']) for r in parsed['remapped']]),
                         ('SBD', '092026', '092026', [('2', 'YES'), ('3', 'NO')]))
        self.assertEqual(tool.parse_history(history('Quantified', quantified=2))['quantified'], 2)
        self.assertEqual(tool.parse_history(history('Active'))['remapped'], [])

    def test_an_unexpected_shape_is_reported_not_guessed(self):
        for body in (b'{}', b'{"rxcuiStatusHistory": {}}', b'{"rxcuiStatusHistory": {"metaData": {}}}', b'[]', b'{"rxcuiStatusHistory": []}'):
            self.assertTrue(tool.parse_history(body)['shape_error'], body)
        with self.assertRaises(ValueError):
            tool.parse_history(b'not json')

    def test_names_are_never_read_into_the_parsed_record(self):
        parsed = tool.parse_history(history('Remapped', remapped=[('2', 'SBD', 'YES')]))
        self.assertNotIn('fiction', json.dumps(parsed))

    def test_the_version_is_read(self):
        self.assertEqual(tool.parse_version(b'{"version": "05-Oct-2026", "apiVersion": "3.1.356"}'), {'version': '05-Oct-2026', 'apiVersion': '3.1.356'})


class NetworkRuleTests(unittest.TestCase):
    def test_the_rate_limit_is_a_quarter_of_the_documented_ceiling_and_only_the_documented_host_is_used(self):
        self.assertLessEqual(tool.MAX_PER_SECOND, 5)
        self.assertEqual(tool.API, 'https://rxnav.nlm.nih.gov/REST')

    def test_only_the_given_references_are_queried_with_the_documented_path_and_spaced_in_time(self):
        urls, now = [], [0.0]

        def opener(request, timeout):
            urls.append((request.full_url, now[0], request.get_header('User-agent')))
            return Response(history('Active'))

        def sleep(seconds):
            now[0] += seconds
        records = tool.query(['11', '22', '33'], opener, sleep, clock=lambda: now[0])
        self.assertEqual([u for u, _, _ in urls], [f'https://rxnav.nlm.nih.gov/REST/rxcui/{r}/historystatus.json' for r in ('11', '22', '33')])
        self.assertTrue(all(agent == tool.USER_AGENT for _, _, agent in urls))
        times = [t for _, t, _ in urls]
        self.assertTrue(all(b - a >= 1.0/tool.MAX_PER_SECOND - 1e-9 for a, b in zip(times, times[1:])), times)
        self.assertEqual([r['http_status'] for r in records], [200]*3)
        self.assertEqual(records[0]['sha256'], hashlib.sha256(history('Active')).hexdigest())

    def test_a_server_error_is_retried_a_client_error_is_not_and_failures_are_reported(self):
        calls, slept = [], []

        def flaky(request, timeout):
            calls.append(request.full_url)
            if len(calls) < 3:
                raise urllib.error.HTTPError(request.full_url, 503, 'busy', {}, None)
            return Response(b'{"version": "v"}')
        self.assertEqual(tool.fetch('https://x/y', flaky, attempts=3, sleep=slept.append)[0], 200)
        self.assertEqual((len(calls), len(slept)), (3, 2))
        calls.clear()

        def missing(request, timeout):
            calls.append(1)
            raise urllib.error.HTTPError(request.full_url, 404, 'gone', {}, None)
        self.assertEqual(tool.fetch('https://x/y', missing, attempts=3, sleep=lambda s: None), (404, None, 'http_404'))
        self.assertEqual(len(calls), 1)

        def down(request, timeout):
            raise urllib.error.URLError('offline')
        self.assertEqual(tool.fetch('https://x/y', down, attempts=3, sleep=lambda s: None), (None, None, 'URLError'))
        records = tool.query(['1'], down, sleep=lambda s: None, clock=lambda: 0.0)
        self.assertEqual((records[0]['parsed'], records[0]['failure']), (None, 'URLError'))


class SummaryTests(unittest.TestCase):
    def test_counts_groups_remapped_targets_and_the_month_of_leaving(self):
        def record(rxcui, body):
            return {'rxcui': rxcui, 'parsed': tool.parse_history(body) if body else None}
        records = [record('1', history('Active')), record('2', history('Obsolete', 'SBD', current='NO', active_end='092026')),
                   record('3', history('Remapped', 'SCD', end='092026', current='NO', remapped=[('90', 'SCD', 'YES')])),
                   record('4', history('Remapped', 'SBD', end='082026', current='NO', remapped=[('91', 'SBD', 'NO'), ('92', 'SBD', 'YES')])),
                   record('5', history('Remapped', 'SBD', end='092026', current='NO')), record('6', history('NotCurrent', end='092026')), record('7', None)]
        tty_of = {'1': {'BN'}, '2': {'SBD'}, '3': {'SCD', 'PSN'}, '4': {'SBD'}, '5': {'SBD'}, '6': {'SCDC'}, '7': {'IN'}}
        summary = tool.summarize(records, tty_of, new_ids={'90', '92'})
        self.assertEqual(summary['status'], {'Active': 1, 'NotCurrent': 1, 'Obsolete': 1, 'Remapped': 3, 'unreadable_or_failed': 1})
        self.assertEqual(summary['by_group'], {'dispensable': {'Obsolete': 1, 'Remapped': 3}, 'other': {'Active': 1, 'NotCurrent': 1}})
        self.assertEqual(summary['remapped'], {'remapped': 3, 'with_target': 2, 'target_in_new_cpc': 2, 'target_active': 2, 'multiple_targets': 1})
        self.assertEqual(summary['release_end_of_remapped_or_notcurrent'], {'082026': 1, '092026': 3})
        self.assertEqual((summary['active_end_of_obsolete'], summary['is_current_by_status']['Obsolete:NO'], summary['is_current_by_status']['Active:YES']), ({'092026': 1}, 1, 1))

    def test_the_statuses_are_those_of_the_documentation(self):
        self.assertEqual(tool.STATUSES, ('Active', 'Obsolete', 'Remapped', 'Quantified', 'NotCurrent', 'Unknown'))
        ledger = {m['id']: m for m in json.loads((ROOT/'docs/research/03-materials.json').read_text())['materials']}
        material = ledger['nlm-rxnorm-api-historystatus']
        self.assertEqual((material['acquisition_status'], material['commit_payload']), ('acquired_file_checks_passed', False))
        page = ROOT/material['local_path']
        if page.is_file():
            import re, html
            text = html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', page.read_text(encoding='utf-8', errors='replace'))))
            self.assertEqual(hashlib.sha256(page.read_bytes()).hexdigest(), material['local_sha256'])
            for status in tool.STATUSES:
                self.assertIn(f' {status} ', text, status)


if __name__ == '__main__':
    unittest.main()
