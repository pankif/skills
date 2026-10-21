"""Проверки происхождения фрагментов, модели и автономной сборки. Без зависимостей."""
import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import build_map as build


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.example = json.loads((build.SKILL / "assets" / "example.json").read_text(encoding="utf-8"))
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)

    def captured(self):
        model = copy.deepcopy(self.example)
        build.validate(model)
        build.capture_sources(model, {"demo": build.SKILL / "assets" / "example-project"})
        build.validate(model, captured=True)
        return model

    def test_exact_excerpts_and_offline_rebuild(self):
        model = self.captured()
        source = model["sources"]["access"]
        self.assertEqual(source["code"], '4: def submit_report(user, request_key, reports, jobs):\n'
                         '5:     if not user["active"]:\n6:         raise PermissionError("Доступ закрыт")')
        raw = (build.SKILL / "assets" / "example-project" / "app.py").read_bytes()
        self.assertEqual(source["fileHash"], hashlib.sha256(raw).hexdigest())
        captured_at = model["snapshot"]["capturedAt"]
        build.capture_sources(model, {})
        self.assertEqual(model["snapshot"]["capturedAt"], captured_at)
        self.assertIn('<!doctype html>', build.render(model))
        self.assertNotIn('<!doctype html>', build.render(model, fragment=True))
        self.assertNotIn('__SYSTEM_MAP_DATA__', build.render(model))

    def test_script_end_in_source_is_data(self):
        model = self.captured()
        model["sources"]["access"]["code"] = '</script><script>window.injected=true</script>'
        model["snapshot"]["name"] = '<img src=x onerror="alert(1)">'
        result = build.render(model)
        self.assertEqual(result.count('<script>'), 1)
        self.assertEqual(result.count('</script>'), 1)
        self.assertIn('\\u003c/script\\u003e', result)
        self.assertIn('&lt;img', result)
        self.assertNotIn('<script src=', result)
        self.assertNotIn('<link ', result)

    def test_facts_need_existing_proof(self):
        for bad_source in ([], 'missing-source'):
            with self.subTest(source=bad_source):
                model = copy.deepcopy(self.example)
                model['views']['overview']['nodes'][0]['source'] = bad_source
                with self.assertRaises(build.MapError):
                    build.validate(model)

    def test_uncertainty_requires_explanation_and_stays_visible(self):
        node = self.example['views']['overview']['nodes'][0]
        node.update(certainty='inferred', source=[])
        with self.assertRaises(build.MapError):
            build.validate(self.example)
        node['gap'] = 'Вызывающая сторона не предоставлена.'
        build.validate(self.example)
        self.assertTrue(node['unknown'])
        self.assertEqual(node['certainty'], 'inferred')

    def test_graph_references_and_positions(self):
        def bad_edge(model):
            model['views']['overview']['edges'][0]['to'] = 'missing'
        def bad_drilldown(model):
            model['views']['overview']['nodes'][0]['scenario'] = 'missing'
        def duplicate_position(model):
            model['views']['overview']['nodes'][1].update(row=0, col=0)
        def duplicate_node(model):
            model['views']['overview']['nodes'].append(copy.deepcopy(model['views']['overview']['nodes'][0]))
        def bad_default(model):
            model['defaultView'] = 'missing'
        def bad_related(model):
            model['views']['overview']['related'] = ['missing']
        for mutate in (bad_edge, bad_drilldown, duplicate_position, duplicate_node, bad_default, bad_related):
            with self.subTest(case=mutate.__name__):
                model = copy.deepcopy(self.example)
                mutate(model)
                with self.assertRaises(build.MapError):
                    build.validate(model)

    def test_path_and_line_boundaries(self):
        for bad_path in ('../outside.py', '/outside.py', 'C:/outside.py', 'folder\\outside.py'):
            with self.subTest(path=bad_path):
                model = copy.deepcopy(self.example)
                model['sources']['access']['path'] = bad_path
                with self.assertRaises(build.MapError):
                    build.validate(model)
        model = copy.deepcopy(self.example)
        model['sources']['access']['end'] = 9999
        with self.assertRaises(build.MapError):
            build.capture_sources(model, {'demo': build.SKILL / 'assets' / 'example-project'})

    def test_multiple_roots_and_no_local_paths_in_result(self):
        model = copy.deepcopy(self.example)
        second = self.root / 'second'
        second.mkdir()
        (second / 'settings.yaml').write_text('mode: strict\n', encoding='utf-8')
        model['snapshot']['repositories'].append({'id':'config', 'name':'Настройки'})
        model['sources']['config'] = dict(repo='config', path='settings.yaml', start=1, end=1, kind='config')
        build.validate(model)
        build.capture_sources(model, {'demo': build.SKILL / 'assets' / 'example-project', 'config': second})
        build.validate(model, captured=True)
        self.assertEqual(model['sources']['config']['code'], '1: mode: strict')
        self.assertNotIn(str(self.root), json.dumps(model))

    def test_redaction_keeps_secret_out_of_outputs(self):
        secret = 'sensitive-value-92817'
        (self.root / '.env').write_text('TOKEN=' + secret + '\n', encoding='utf-8')
        model = copy.deepcopy(self.example)
        model['sources'] = {'secret': dict(repo='demo', path='.env', start=1, end=1, kind='config')}
        with self.assertRaises(build.MapError):
            build.capture_sources(model, {'demo': self.root})
        model['sources']['secret'].update(redact=True, note='Только имя TOKEN')
        build.capture_sources(model, {'demo': self.root})
        self.assertNotIn(secret, json.dumps(model))
        self.assertNotIn(secret, build.render(model))
        self.assertEqual(model['sources']['secret']['fileHash'], hashlib.sha256((self.root/'.env').read_bytes()).hexdigest())
        model['sources']['secret']['code'] = secret
        build.capture_sources(model, {})
        self.assertNotIn(secret, json.dumps(model))

    def test_commit_link_tracks_content_and_subdirectory(self):
        def run(*args):
            return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                                  capture_output=True, encoding='utf-8').stdout.strip()
        try:
            run('init')
        except (OSError, subprocess.CalledProcessError):
            self.skipTest('Git недоступен')
        package = self.root / 'pkg'
        package.mkdir()
        file = package / 'module.py'
        file.write_bytes(b'answer = 42\n')
        run('add', 'pkg/module.py')
        run('-c', 'user.name=Skill Test', '-c', 'user.email=skill-test@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-m', 'fixture')
        run('remote', 'add', 'origin', 'https://github.com/example/sample.git')
        model = copy.deepcopy(self.example)
        model['sources'] = {'sample':dict(repo='demo',path='module.py',start=1,end=1,kind='code')}
        build.capture_sources(model, {'demo': package})
        self.assertFalse(model['sources']['sample']['local'])
        self.assertIn('/pkg/module.py#L1-L1', model['sources']['sample']['url'])
        head = run('rev-parse', 'HEAD')
        self.assertIn(head, model['sources']['sample']['url'])
        file.write_bytes(b'answer = 42\r\n')
        build.capture_sources(model, {'demo': package})
        self.assertFalse(model['sources']['sample']['local'])
        file.write_text('answer = 43\n', encoding='utf-8')
        build.capture_sources(model, {'demo': package})
        self.assertTrue(model['sources']['sample']['local'])
        self.assertIsNone(model['sources']['sample']['url'])

    def test_check_does_not_write_and_build_keeps_input(self):
        model_path = self.root / 'input.json'
        model_path.write_text(json.dumps(self.example), encoding='utf-8')
        before = model_path.read_bytes()
        output = self.root / 'generated' / 'map.html'
        bindings = ['--root', 'demo=' + str(build.SKILL / 'assets' / 'example-project')]
        self.assertEqual(build.main([str(model_path), *bindings, '--check']), 0)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['input.json'])
        self.assertEqual(build.main([str(model_path), *bindings, '-o', str(output)]), 0)
        self.assertTrue(output.is_file())
        self.assertTrue(output.with_suffix('.json').is_file())
        self.assertEqual(model_path.read_bytes(), before)
        self.assertEqual(build.main([str(output.with_suffix('.json')), '--check']), 0)
        self.assertEqual(build.main([str(output.with_suffix('.json')), '-o', str(output)]), 1)


if __name__ == '__main__':
    unittest.main()
