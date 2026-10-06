#!/usr/bin/env python3
"""Run on PVE as root; return secrets only to Ansible's no_log task."""
import configparser
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


def run(*args):
    return subprocess.check_output(args, text=True)


def collect(settings):
    changed = False
    user = settings['username'] + '@pve'
    token_id = settings['token_id']
    users = json.loads(run('pveum', 'user', 'list', '--output-format', 'json'))
    if not any(row['userid'] == user for row in users):
        run('pveum', 'user', 'add', user, '--comment', 'Homarr read-only monitoring')
        changed = True
    tokens = json.loads(run('pveum', 'user', 'token', 'list', user, '--output-format', 'json'))
    token_exists = any(row['tokenid'] == token_id for row in tokens)
    path = Path(settings['token_file'])
    if token_exists and not path.exists():
        raise RuntimeError('Monitoring token already exists but its secret file is missing; restore the file or select a new token ID.')
    if not token_exists:
        if path.exists():
            raise RuntimeError('Saved monitoring token was removed from PVE; select a new token ID/file or restore the token.')
        token = json.loads(run('pveum', 'user', 'token', 'add', user, token_id,
                               '--privsep', '1', '--output-format', 'json'))
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump(token, handle)
        changed = True
    token = json.loads(path.read_text())
    os.chmod(path, 0o600)
    # A privilege-separated token needs permissions on both the user and token.
    acls = json.loads(run('pveum', 'acl', 'list', '--output-format', 'json'))
    for kind, identity, flag in [('user', user, '--users'), ('token', user + '!' + token_id, '--tokens')]:
        if not any(row['type'] == kind and row['ugid'] == identity and row['path'] == '/'
                   and row['roleid'] == 'PVEAuditor' and row['propagate'] == 1 for row in acls):
            run('pveum', 'acl', 'modify', '/', flag, identity, '--roles', 'PVEAuditor', '--propagate', '1')
            changed = True
    keys = {}
    for ct in settings['lxcs']:
        name = ct['name']
        if name in ['radarr', 'sonarr', 'prowlarr']:
            contents = run('pct', 'exec', str(ct['vmid']), '--', 'cat',
                           settings['conf_dir'] + '/' + name + '/config.xml')
            keys[name] = ET.fromstring(contents).findtext('ApiKey', '').strip()
        elif name == 'sabnzbd':
            contents = run('pct', 'exec', str(ct['vmid']), '--', 'cat',
                           settings['sabnzbd_conf_dir'] + '/sabnzbd.ini')
            # SABnzbd uses ConfigObj nested sections; only parse its misc section.
            misc = contents.split('[misc]', 1)[1].split('\n[', 1)[0]
            config = configparser.ConfigParser(interpolation=None)
            config.read_string('[misc]\n' + misc)
            keys[name] = config['misc']['api_key'].strip().strip('"\'')
        elif name == 'jellyseerr':
            contents = run('pct', 'exec', str(ct['vmid']), '--', 'cat',
                           settings['conf_dir'] + '/jellyseerr/settings.json')
            keys[name] = json.loads(contents)['main']['apiKey']
    if any(not key for key in keys.values()) or len(keys) != 5:
        raise RuntimeError('Existing Servarr API keys are incomplete; deploy Servarr first.')
    return {'changed': changed, 'keys': keys, 'proxmox_username': settings['username'],
            'proxmox_token_id': token_id, 'proxmox_token_secret': token['value']}


if __name__ == '__main__':
    try:
        print(json.dumps(collect(json.load(sys.stdin))))
    except Exception as error:
        # Do not echo command output or credentials on error.
        print('Credential discovery failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
