#!/usr/bin/env python3
"""Bootstrap pinned Homarr v2 through its APIs. Credentials arrive over stdin.

Only the first board layout is seeded. A private marker records completion;
reruns retain user-managed boards, integrations and passwords.
"""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request


class API:
    def __init__(self, url, cookie_path=None):
        self.url = url.rstrip('/')
        self.cookies = http.cookiejar.LWPCookieJar(str(cookie_path)) if cookie_path else http.cookiejar.CookieJar()
        if cookie_path and cookie_path.exists():
            self.cookies.load(ignore_discard=True)
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies))
        self.cookie_path = cookie_path

    def request(self, path, value=None, form=False):
        body = None if value is None else (
            urllib.parse.urlencode(value).encode() if form else json.dumps(value).encode())
        request = urllib.request.Request(self.url + path, body, headers={
            'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json',
            'Origin': self.url, 'X-Auth-Return-Redirect': '1',
        })
        try:
            with self.opener.open(request, timeout=120) as response:
                result = json.loads(response.read())
            if self.cookie_path:
                self.cookies.save(ignore_discard=True)
                os.chmod(self.cookie_path, 0o600)
            return result
        except urllib.error.HTTPError as error:
            # Homarr errors include useful validation messages; never echo inputs.
            raise RuntimeError(f'{path.split("?")[0]} returned HTTP {error.code}') from None

    def trpc(self, procedure, value=None, mutation=False):
        path = '/api/trpc/' + procedure
        if mutation:
            result = self.request(path, {'json': value})
        else:
            result = self.request(path + '?input=' + urllib.parse.quote(json.dumps({'json': value})))
        if 'error' in result:
            raise RuntimeError(f'Homarr procedure {procedure} failed')
        return result['result']['data'].get('json')

    def login(self, username, password):
        csrf = self.request('/api/auth/csrf')['csrfToken']
        self.request('/api/auth/callback/credentials', {
            'name': username, 'password': password, 'csrfToken': csrf,
            'callbackUrl': self.url, 'json': 'true',
        }, form=True)
        session = self.request('/api/auth/session')
        if not session or not session.get('user'):
            raise RuntimeError('Homarr sign-in failed; provide the existing administrator credentials.')


def stable_id(kind, name):
    digest = hashlib.sha256(('homelab:' + name).encode()).hexdigest()[:32]
    return 'onboarding_' + kind + '_' + digest


def integration_drafts(settings):
    drafts = []
    names = {'radarr': 'Radarr', 'sonarr': 'Sonarr', 'prowlarr': 'Prowlarr',
             'sabnzbd': 'SABnzbd', 'jellyseerr': 'Jellyseerr', 'jellyfin': 'Jellyfin'}
    for ct in settings['lxcs']:
        name = ct['name']
        host = ct['ip'].split('/')[0]
        url = f'http://{host}:{settings["ports"][name]}'
        secrets = [{'kind': 'apiKey', 'value': settings['keys'][name]}] if name != 'jellyfin' else [
            {'kind': 'username', 'value': settings['jellyfin_username']},
            {'kind': 'password', 'value': settings['jellyfin_password']},
        ]
        drafts.append({'sourceId': 'homelab:' + name, 'name': names[name],
                       'kind': 'sabNzbd' if name == 'sabnzbd' else name, 'url': url,
                       'iconUrl': f'https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons@master/svg/{name}.svg',
                       'pingUrl': url + ('/ping' if name in ['radarr', 'sonarr', 'prowlarr'] else '/'),
                       'secrets': secrets})
    drafts.append({'sourceId': 'homelab:proxmox', 'name': 'Proxmox', 'kind': 'proxmox',
                   'url': settings['proxmox_url'], 'secrets': [
                       {'kind': 'username', 'value': settings['proxmox_username']},
                       {'kind': 'tokenId', 'value': settings['proxmox_token_id']},
                       {'kind': 'realm', 'value': 'pve'},
                       {'kind': 'apiKey', 'value': settings['proxmox_token_secret']},
                   ]})
    return drafts


def media_definition(integration_id, proxmox_id, node_name):
    return {'$schema': 'homarr-custom-widget-v2', 'name': 'Homelab media storage',
            'description': 'Live capacity of the shared media/download filesystem and the Proxmox system disk.',
            'sources': {'default': {'type': 'integration', 'integrationKind': 'sabNzbd',
                                    'integrationId': integration_id},
                        'node': {'type': 'integration', 'integrationKind': 'proxmox',
                                 'integrationId': proxmox_id}},
            'requests': {'capacity': {'path': '/api', 'query': {'mode': 'queue', 'output': 'json'},
                                       'cacheSeconds': 15},
                         'node': {'source': 'node', 'path': f'/api2/json/nodes/{urllib.parse.quote(node_name, safe="")}/status',
                                  'cacheSeconds': 15}}, 'options': {},
            'template': Path(__file__).with_name('media-storage.jsx').read_text()}


def customize_board(api, settings, board, media_id):
    """Set a fresh board's desktop and mobile layouts in one atomic API save."""
    name_to_id = {name: stable_id('integration', name) for name in [
        'radarr', 'sonarr', 'prowlarr', 'sabnzbd', 'jellyfin', 'jellyseerr', 'proxmox']}
    sections = [section for section in board['sections'] if section['kind'] == 'empty']
    root = next(section for section in sections if section['xOffset'] == 0)
    # Each spec: kind, title, integration names, options, desktop (x,y,w,h).
    specs = []
    for index, name in enumerate(['proxmox', 'radarr', 'sonarr', 'prowlarr', 'sabnzbd', 'jellyseerr', 'jellyfin']):
        specs.append(('app', None, [], {'appId': stable_id('app', name), 'openInNewTab': True,
                                       'showTitle': True}, (index, 0, 1, 1)))
    specs += [
        ('clock', None, [], {'timezone': settings['timezone'], 'useCustomTimezone': True,
                            'showWeather': False}, (10, 0, 2, 1)),
        ('healthMonitoring', 'Proxmox · node, guests & storage', ['proxmox'],
         {'defaultTab': 'cluster', 'showUptime': True, 'cpu': True, 'memory': True,
          'visibleClusterSections': ['node', 'lxc', 'qemu', 'storage']}, (0, 1, 4, 4)),
        ('downloads', 'Downloads · progress, speed & ETA', ['sabnzbd'],
         {'columns': ['name', 'progress', 'size', 'downSpeed', 'time', 'state'],
          'showCompletedUsenet': True, 'includeArchivedHistory': False}, (4, 1, 8, 3)),
        ('customApi', 'Media capacity', [], {'definitionId': media_id, 'refreshInterval': 30}, (4, 4, 4, 2)),
        ('mediaMissing', 'Movies & TV · missing and queued', ['radarr', 'sonarr'],
         {'showMissing': True, 'showQueued': True, 'pageSize': '10'}, (8, 4, 4, 3)),
        ('indexerManager', 'Prowlarr · indexer health', ['prowlarr'], {}, (0, 5, 4, 2)),
        ('mediaRequests-requestStats', 'Request overview', ['jellyseerr'], {}, (4, 6, 4, 1)),
        ('mediaRequests-requestList', 'Media requests', ['jellyseerr'], {}, (0, 7, 4, 3)),
        ('mediaServer', 'Jellyfin · currently playing', ['jellyfin'], {}, (4, 7, 4, 3)),
        ('calendar', 'Upcoming movies & episodes', ['radarr', 'sonarr'], {}, (8, 7, 4, 3)),
    ]
    # Reuse the app/widget IDs generated during onboarding whenever possible.
    existing = list(board['items'])
    items = []
    mobile_y = 0
    for index, (kind, title, integrations, options, desktop) in enumerate(specs):
        match = next((item for item in existing if item['kind'] == kind and (
            kind != 'app' or item['options'].get('appId') == options['appId'])), None)
        if match:
            existing.remove(match)
        item = {'id': match['id'] if match else hashlib.sha256(
                    (board['id'] + ':' + str(index)).encode()).hexdigest()[:24],
                'kind': kind, 'options': {**(match['options'] if match else {}), **options},
                'integrationIds': [name_to_id[name] for name in integrations],
                'advancedOptions': {'title': title, 'customCssClasses': [], 'borderColor': ''},
                'layouts': []}
        for layout in board['layouts']:
            if layout['role'] == 'mobile':
                if kind == 'app':
                    position = (index % 3, index // 3, 1, 1)
                    mobile_y = 3
                else:
                    position = (0, mobile_y, 3, max(1, desktop[3]))
            else:
                position = desktop
            x, y, width, height = position
            item['layouts'].append({'layoutId': layout['id'], 'sectionId': root['id'],
                                    'xOffset': x, 'yOffset': y, 'width': width, 'height': height})
        if kind != 'app':
            mobile_y += max(1, desktop[3])
        items.append(item)
    api.trpc('board.saveBoard', {'id': board['id'], 'sections': sections, 'items': items}, mutation=True)
    api.trpc('board.savePartialBoardSettings', {
        'id': board['id'], 'pageTitle': 'Homelab', 'metaTitle': 'Homelab · Proxmox & Servarr',
        'disableStatus': False, 'customCss': 'body { background-color: #16181c; }',
    }, mutation=True)


def write_state(marker, state):
    temp = marker.with_suffix('.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(state, handle)
    os.replace(temp, marker)


def bootstrap(api, settings, marker):
    state = json.loads(marker.read_text()) if marker.exists() else {}
    if state.get('complete'):
        # Preserve edited board, password, icons and integration configuration.
        print('UNCHANGED: Existing Homarr dashboard retained.')
        return
    drafts = integration_drafts(settings)
    stage = api.trpc('onboard.currentStep')
    if not state:
        if stage['current'] not in ['start', 'user', 'setup']:
            raise RuntimeError('Homarr already completed onboarding without the Ansible marker; refusing to replace its board.')
        state = {'board_name': settings['board_name']}
        write_state(marker, state)
    if stage['current'] in ['start', 'user']:
        api.request('/api/onboarding/claim', {})
        if stage['current'] == 'start':
            api.trpc('onboard.nextStep', mutation=True)
        api.trpc('user.initUser', {'username': settings['admin_username'],
                                  'password': settings['admin_password'],
                                  'confirmPassword': settings['admin_password']}, mutation=True)
    api.login(settings['admin_username'], settings['admin_password'])
    stage = api.trpc('onboard.currentStep')
    if stage['current'] == 'setup':
        api.request('/api/onboarding/claim', {})
        # Fail before completing onboarding if any integration cannot connect.
        for draft in drafts:
            if not api.trpc('onboard.testIntegration', draft, mutation=True).get('success'):
                raise RuntimeError('Integration connection failed: ' + draft['name'])
        result = api.trpc('onboard.completeSetup', {
            'server': {'defaultLocale': 'en', 'defaultColorScheme': 'dark', 'analyticsEnabled': False},
            'board': {'name': state['board_name'], 'primaryColor': '#f97316',
                      'secondaryColor': '#38bdf8', 'itemRadius': 'lg', 'columnCount': 12,
                      'layoutPreset': 'wide'}, 'integrations': drafts, 'apps': [],
            'selectedWidgetKinds': ['clock'],
        }, mutation=True)
        state['board_id'] = result['boardId']
        write_state(marker, state)
    board = api.trpc('board.getBoardByName', {'name': state['board_name']})
    if state.get('board_id') and board['id'] != state['board_id']:
        raise RuntimeError('Managed board identity changed; refusing to replace another board.')
    state['board_id'] = board['id']
    if not state.get('media_widget_id'):
        media = api.trpc('customWidget.create', media_definition(
            stable_id('integration', 'sabnzbd'), stable_id('integration', 'proxmox'), settings['proxmox_node']), mutation=True)
        state['media_widget_id'] = media['id']
        write_state(marker, state)
    customize_board(api, settings, board, state['media_widget_id'])
    state['complete'] = True
    write_state(marker, state)
    if api.cookie_path and api.cookie_path.exists():
        api.cookie_path.unlink()
    print('CHANGED: Homarr administrator, integrations and dashboard configured.')


if __name__ == '__main__':
    try:
        marker = Path(sys.argv[2])
        bootstrap(API(sys.argv[1], marker.with_suffix('.cookies')), json.load(sys.stdin), marker)
    except Exception as error:
        print('Homarr bootstrap failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
