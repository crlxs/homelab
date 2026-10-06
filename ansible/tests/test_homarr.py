"""Exercise onboarding recovery, preservation and responsive board placement."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).parents[1] / 'roles/homarr/files/bootstrap.py'
SPEC = importlib.util.spec_from_file_location('homarr_bootstrap', MODULE)
homarr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(homarr)


def settings():
    names = ['radarr', 'sonarr', 'prowlarr', 'sabnzbd', 'jellyseerr', 'jellyfin']
    return {'lxcs': [{'name': name, 'ip': f'192.0.2.{index + 1}/24'} for index, name in enumerate(names)],
            'ports': dict(zip(names, [7878, 8989, 9696, 8081, 5055, 8096])),
            'keys': {name: 'dummy-key' for name in names if name != 'jellyfin'},
            'jellyfin_username': 'admin', 'jellyfin_password': 'dummy-password',
            'proxmox_username': 'homarr', 'proxmox_token_id': 'monitoring',
            'proxmox_token_secret': 'dummy-token', 'proxmox_url': 'https://192.0.2.100:8006', 'proxmox_node': 'pve',
            'board_name': 'Homelab', 'admin_username': 'admin', 'admin_password': 'dummy-password',
            'timezone': 'Europe/Madrid'}


class FakeAPI:
    cookie_path = None

    def __init__(self, stage='start', failed_integration=None, fail_layout=False):
        self.stage = stage
        self.failed_integration = failed_integration
        self.fail_layout = fail_layout
        self.calls = []
        self.board = {'id': 'board-1', 'sections': [{'id': 'root-1', 'kind': 'empty', 'xOffset': 0, 'yOffset': 0}],
                      'layouts': [{'id': 'mobile', 'role': 'mobile', 'columnCount': 3},
                                  {'id': 'base', 'role': 'base', 'columnCount': 12}], 'items': []}

    def request(self, path, value=None):
        self.calls.append((path, value))
        return {}

    def login(self, username, password):
        self.calls.append(('login', username))

    def trpc(self, procedure, value=None, mutation=False):
        self.calls.append((procedure, value))
        if procedure == 'onboard.currentStep':
            return {'current': self.stage}
        if procedure == 'onboard.nextStep':
            self.stage = 'user'
        if procedure == 'user.initUser':
            self.stage = 'setup'
        if procedure == 'onboard.testIntegration':
            return {'success': value['name'] != self.failed_integration}
        if procedure == 'onboard.completeSetup':
            self.stage = 'finish'
            return {'boardId': self.board['id']}
        if procedure == 'customWidget.create':
            return {'id': 'media-1'}
        if procedure == 'board.getBoardByName':
            return self.board
        if procedure == 'board.saveBoard':
            if self.fail_layout:
                raise RuntimeError('temporary layout error')
            self.saved = value


class HomarrBootstrapTests(unittest.TestCase):
    def run_bootstrap(self, api, marker):
        with contextlib.redirect_stdout(io.StringIO()):
            homarr.bootstrap(api, settings(), marker)

    def test_completed_bootstrap_never_contacts_api_or_resets_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'state.json'
            marker.write_text(json.dumps({'complete': True, 'board_id': 'edited-board'}))
            api = FakeAPI()
            self.run_bootstrap(api, marker)
            self.assertEqual(api.calls, [])
            self.assertEqual(json.loads(marker.read_text())['board_id'], 'edited-board')

    def test_unmanaged_existing_dashboard_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'state.json'
            api = FakeAPI(stage='finish')
            with self.assertRaisesRegex(RuntimeError, 'refusing to replace'):
                self.run_bootstrap(api, marker)
            self.assertFalse(marker.exists())
            self.assertEqual([call[0] for call in api.calls], ['onboard.currentStep'])

    def test_failed_connection_leaves_onboarding_retryable(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'state.json'
            api = FakeAPI(failed_integration='Sonarr')
            with self.assertRaisesRegex(RuntimeError, 'Sonarr'):
                self.run_bootstrap(api, marker)
            self.assertNotIn('onboard.completeSetup', [call[0] for call in api.calls])
            api.failed_integration = None
            self.run_bootstrap(api, marker)
            self.assertTrue(json.loads(marker.read_text())['complete'])

    def test_partial_layout_failure_resumes_without_duplicate_board_or_widget(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'state.json'
            api = FakeAPI(fail_layout=True)
            with self.assertRaisesRegex(RuntimeError, 'temporary layout'):
                self.run_bootstrap(api, marker)
            api.fail_layout = False
            self.run_bootstrap(api, marker)
            calls = [call[0] for call in api.calls]
            self.assertEqual(calls.count('onboard.completeSetup'), 1)
            self.assertEqual(calls.count('customWidget.create'), 1)
            state = json.loads(marker.read_text())
            self.assertTrue(state['complete'])
            self.assertNotIn('dummy-password', marker.read_text())
            self.assertNotIn('dummy-token', marker.read_text())
            self.assertEqual(marker.stat().st_mode & 0o777, 0o600)

    def test_desktop_and_mobile_fit_without_overlaps_and_have_all_links(self):
        api = FakeAPI()
        homarr.customize_board(api, settings(), api.board, 'media-1')
        items = api.saved['items']
        self.assertEqual(sum(item['kind'] == 'app' for item in items), 7)
        self.assertNotIn('weather', [item['kind'] for item in items])
        self.assertEqual(next(item for item in items if item['kind'] == 'clock')['options']['showWeather'], False)
        for layout_id, columns in [('mobile', 3), ('base', 12)]:
            placements = [next(row for row in item['layouts'] if row['layoutId'] == layout_id) for item in items]
            for index, row in enumerate(placements):
                self.assertLessEqual(row['xOffset'] + row['width'], columns)
                for other in placements[index + 1:]:
                    overlaps = (row['xOffset'] < other['xOffset'] + other['width']
                                and other['xOffset'] < row['xOffset'] + row['width']
                                and row['yOffset'] < other['yOffset'] + other['height']
                                and other['yOffset'] < row['yOffset'] + row['height'])
                    self.assertFalse(overlaps, (layout_id, row, other))


if __name__ == '__main__':
    unittest.main()
