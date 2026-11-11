"""End-to-end checks for repository identity, excerpt packaging and path defaults."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'scripts' / 'tour.py'

class PortableTourTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tourrific-test-')
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        (self.repo / 'nested').mkdir()
        (self.repo / 'app.py').write_text('PRIVATE_UNUSED = 123\ndef main():\n    return "hello"\n# NOT_CITED\n')
        ref = {'path': 'app.py', 'start': 2, 'end': 3, 'symbol': 'main'}
        node = {'id': 'app', 'label': 'App', 'kind': 'ENTRY', 'description': 'Entry point', 'refs': [ref], 'position': {'x': 0, 'y': 0}}
        step = {'id': 'entry', 'title': 'Entry', 'body': 'Runs main.', 'node': 'app', 'refs': [ref], 'status': 'verified'}
        chapters = [{'id': str(i), 'title': 'Chapter', 'eyebrow': 'TOUR', 'intro': 'Overview', 'steps': [step]} for i in range(7)]
        analysis = {'schemaVersion': '1.0', 'repository': {'name': 'sample', 'description': 'Example', 'technologies': ['Python'], 'revision': None, 'generatedAt': '', 'snapshot': ''}, 'nodes': [node], 'edges': [], 'chapters': chapters, 'sources': {}}
        self.analysis = self.base / 'analysis.json'
        self.analysis.write_text(json.dumps(analysis))

    def tearDown(self): self.temp.cleanup()

    def run_cli(self, *args, cwd=None, succeeds=True):
        result = subprocess.run([sys.executable, str(CLI), *map(str, args)], cwd=cwd or self.repo, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, succeeds, result.stderr)
        return result

    def test_local_package_and_cross_repository_protection(self):
        self.run_cli('prepare', cwd=self.repo / 'nested')
        self.run_cli('package', '--analysis', self.analysis, cwd=self.repo / 'nested')
        self.run_cli('verify')
        out = self.repo / '.tourrific'
        tour = json.loads((out / 'tour.json').read_text())
        self.assertEqual(tour['sources']['app.py']['content'], '\ndef main():\n    return "hello"')
        self.assertIn('window.TOURRIFIC_TOUR=', (out / 'index.html').read_text())
        self.assertTrue((out / 'assets/viewer.js').is_file())
        self.assertTrue((out / 'assets/viewer.css').is_file())
        for file in out.rglob('*'):
            if file.is_file(): self.assertNotIn(str(self.base).encode(), file.read_bytes())
        other = self.base / 'other'; other.mkdir()
        self.run_cli('prepare', '--repo', other, '--output', out, succeeds=False)
        self.assertEqual(json.loads((out / 'tour.json').read_text()), tour)
        (self.repo / 'app.py').write_text('changed\n')
        self.run_cli('verify', succeeds=False)

    def test_risk_assessment_and_reference_validation(self):
        data = json.loads(self.analysis.read_text())
        risk = {'asset':'Data','boundary':'Client to API','scenario':'Possible misuse',
                'consequence':'Potential exposure','control':'Not established',
                'mitigation':'Review access','confidence':'Needs verification',
                'assessment':{'level':'Needs verification','rationale':'Exposure is unknown.',
                              'references':[{'title':'OWASP LLM Top 10 2026','url':'https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/'}, {'title':'OWASP Agentic Top 10 2026','url':'https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/'}]},
                'mitigationPrompt':'Review app.py:2-3 and verify controls before changing them.'}
        data['chapters'][6]['steps'][0]['risk'] = risk
        self.analysis.write_text(json.dumps(data))
        baseline = self.run_cli('snapshot').stdout.strip()
        self.run_cli('package', '--analysis', self.analysis, '--baseline', baseline, '--review-policy', 'owasp-genai-2026-v1')
        self.run_cli('check')
        for unsafe_url in ('javascript:alert(1)', 'https://owasp.org.example.com/path', 'https://owasp.org@evil.example/path'):
            risk['assessment']['references'][0]['url'] = unsafe_url
            self.analysis.write_text(json.dumps(data))
            result = self.run_cli('package', '--analysis', self.analysis, succeeds=False)
            self.assertIn('official OWASP or MITRE', result.stderr)
        risk['assessment']['references'] = []
        risk['assessment']['level'] = '8/10'
        self.analysis.write_text(json.dumps(data))
        self.run_cli('package', '--analysis', self.analysis, succeeds=False)

    def test_legacy_risk_needs_regeneration_before_reuse(self):
        data = json.loads(self.analysis.read_text())
        data['chapters'][6]['steps'][0]['risk'] = {'asset':'Data','boundary':'API','scenario':'Possible misuse',
            'consequence':'Exposure','control':'Unknown','mitigation':'Review','confidence':'Unverified'}
        self.analysis.write_text(json.dumps(data))
        baseline = self.run_cli('snapshot').stdout.strip()
        self.run_cli('package', '--analysis', self.analysis, '--baseline', baseline, '--review-policy', 'owasp-genai-2026-v1')
        result = self.run_cli('check', succeeds=False)
        self.assertIn('need qualitative assessments', result.stderr)

    def test_git_snapshot_reuse_and_changes(self):
        (self.repo / 'unrelated.txt').write_text('initial')
        (self.repo / '.gitignore').write_text('ignored.txt\nignored.py\n')
        subprocess.run(['git', '-C', str(self.repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'initial'], check=True)
        baseline = self.run_cli('snapshot').stdout.strip()
        self.assertEqual(baseline, self.run_cli('snapshot', cwd=self.repo / 'nested').stdout.strip())
        self.run_cli('package', '--analysis', self.analysis, '--baseline', baseline, '--review-policy', 'owasp-genai-2026-v1')
        self.run_cli('check')
        (self.repo / '.tourrific' / 'analysis.json').write_text('output does not invalidate the tour')
        (self.repo / 'ignored.txt').write_text('ignored by git')
        self.run_cli('check')
        (self.repo / 'ignored.py').write_text('eligible source')
        self.run_cli('check', succeeds=False)
        (self.repo / 'ignored.py').unlink()
        self.run_cli('check')
        unrelated = self.repo / 'unrelated.txt'
        unrelated.write_text('changed outside cited excerpts')
        self.run_cli('check', succeeds=False)
        self.run_cli('package', '--analysis', self.analysis, '--baseline', baseline, succeeds=False)
        unrelated.write_text('initial')
        self.run_cli('check')
        newfile = self.repo / 'new-untracked.py'
        newfile.write_text('new file')
        self.run_cli('check', succeeds=False)
        newfile.unlink()
        self.run_cli('check')
        unrelated.write_text('staged change')
        subprocess.run(['git', '-C', str(self.repo), 'add', 'unrelated.txt'], check=True)
        unrelated.write_text('initial')
        self.run_cli('check', succeeds=False)
        subprocess.run(['git', '-C', str(self.repo), 'reset', '-q', 'HEAD', '--', 'unrelated.txt'], check=True)
        self.run_cli('check')
        (self.repo / '.tourrific' / 'assets' / 'viewer.js').write_text('corrupted')
        self.run_cli('check', succeeds=False)

    def test_new_commit_invalidates_tour(self):
        subprocess.run(['git', '-C', str(self.repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'initial'], check=True)
        baseline = self.run_cli('snapshot').stdout.strip()
        self.run_cli('package', '--analysis', self.analysis, '--baseline', baseline, '--review-policy', 'owasp-genai-2026-v1')
        self.run_cli('check')
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'new revision'], check=True)
        self.run_cli('check', succeeds=False)

    def test_existing_tour_without_ai_review_needs_refresh(self):
        baseline = self.run_cli('snapshot').stdout.strip()
        self.run_cli('package', '--analysis', self.analysis, '--baseline', baseline)
        result = self.run_cli('check', succeeds=False)
        self.assertIn('AI security applicability review needs refresh', result.stderr)
        self.run_cli('package', '--analysis', self.analysis, '--baseline', baseline, '--review-policy', 'owasp-genai-2026-v1')
        self.run_cli('check')

    def test_legacy_and_non_git_never_reuse(self):
        self.run_cli('package', '--analysis', self.analysis)
        self.run_cli('check', succeeds=False)
        other = self.base / 'not-git'
        other.mkdir()
        self.run_cli('snapshot', '--repo', other, succeeds=False)

    def test_attack_path_requires_known_connected_nodes(self):
        data = json.loads(self.analysis.read_text())
        node = dict(data['nodes'][0], id='service', label='Service')
        data['nodes'].append(node)
        data['edges'] = [{'source': 'app', 'target': 'service', 'label': 'calls'}]
        data['chapters'][6]['steps'][0]['risk'] = {
            'asset': 'Data', 'boundary': 'App to service', 'scenario': 'Possible misuse',
            'consequence': 'Potential exposure', 'control': 'Not established',
            'mitigation': 'Review access', 'confidence': 'Needs verification',
            'attackPath': ['service', 'app']
        }
        self.analysis.write_text(json.dumps(data))
        self.run_cli('package', '--analysis', self.analysis)
        self.run_cli('verify')
        data['chapters'][6]['steps'][0]['risk']['attackPath'] = ['app', 'missing']
        self.analysis.write_text(json.dumps(data))
        result = self.run_cli('package', '--analysis', self.analysis, succeeds=False)
        self.assertIn('attack path references missing node', result.stderr)
        data['chapters'][6]['steps'][0]['risk']['attackPath'] = ['app', 'app']
        self.analysis.write_text(json.dumps(data))
        result = self.run_cli('package', '--analysis', self.analysis, succeeds=False)
        self.assertIn('attack path has no architecture connection', result.stderr)

    def test_explicit_output_and_unmanaged_file(self):
        out = self.base / 'custom'
        self.run_cli('prepare', '--repo', self.repo, '--output', out, cwd=self.base)
        (out / 'index.html').write_text('do not overwrite')
        self.run_cli('package', '--repo', self.repo, '--output', out, '--analysis', self.analysis, cwd=self.base, succeeds=False)
        self.assertEqual((out / 'index.html').read_text(), 'do not overwrite')

if __name__ == '__main__': unittest.main()
