# Homarr dashboard LXC

Homarr v2.2.0 runs as a native systemd service in its own unprivileged Debian 13
LXC. Its official prebuilt Debian release and Node.js v24.18.0 are pinned with
SHA-256 checksums. Redis stays local and nginx exposes port 7575. The application
runs as the `homarr` service account. Docker nesting and media bind mounts are
not required.

The standalone server binds to `localhost` with IPv4-first DNS so Next.js
locale rewrites keep their internal origin; this avoids the upstream
[standalone redirect issue](https://github.com/vercel/next.js/issues/94342).
Redis's `PrivateUsers` setting is disabled in a small systemd override because
the LXC already provides an unprivileged user namespace; its other package
hardening settings remain in place.

The initial dark board includes:

- Clickable icons and HTTP status for Proxmox and every Servarr application.
- Proxmox CPU, memory, uptime, node/VM/LXC status, guest resources and storage.
- SABnzbd active downloads, progress, speed, ETA and recent completed jobs.
- A media capacity card showing available/total space, a usage bar and a red
  indication below 10% free. It reads SABnzbd's actual download filesystem;
  media and downloads share that filesystem in this repository.
  The card also reports available space and utilization of the Proxmox system disk.
- Radarr/Sonarr missing and queued media, plus upcoming releases/episodes.
- Prowlarr indexer health, Jellyseerr requests/stats and Jellyfin activity.

Desktop and mobile layouts are seeded automatically. No weather or stock
integrations are configured.

## Deploy

The full `01-deploy-servarr.yaml` playbook includes Homarr after Servarr bootstrap.
For an existing stack, deploy the dashboard independently:

```sh
cd ansible
ansible-playbook playbooks/02-deploy-homarr.yaml
```

Defaults in `inventory/group_vars/proxmox.yaml` allocate CT **127**, IP
**192.168.1.207/24**, 2 cores, 2 GiB RAM and a 12 GiB root disk on `local-lvm`.
Check availability before changing the ID/IP. Existing unrelated guests are
never repurposed. Open **http://192.168.1.207:7575**. The administrator defaults
to `servarr_ui_username` / `servarr_ui_password`; a password of at least eight
characters is required. Optional `homarr_admin_username` and
`homarr_admin_password` overrides belong in the existing private
`inventory/servarr.local.yaml` file or Vault, not committed defaults.

The playbook retrieves API keys from the running Servarr containers without
logging them. Jellyfin uses its existing administrator credentials. A dedicated
`homarr@pve!monitoring` token gets `PVEAuditor` at `/` on both the user and the
privilege-separated token. Its secret lives in root-only
`/etc/homarr/proxmox-token.json` on PVE. The provisioning token is never handed
to Homarr. The Proxmox CA is installed for certificate verification.

The storage custom widget makes GET requests to SABnzbd and Proxmox using Homarr's saved
integrations; it embeds no credentials in the board or browser. Administrators
can edit it under Management → Custom Widgets.

## Reruns, recovery and backups

Application configuration persists in `/appdata` inside the dashboard LXC.
Back up the entire directory, especially `db/db.sqlite`, `secrets.env`,
`trusted-certificates/` and `ansible-bootstrap.json`, together with the CT.
Keep the encryption key unchanged: losing it makes saved integration
credentials unreadable. The PVE token file needs a separate host backup.

`ansible-bootstrap.json` records bootstrap progress without secrets. A failed
initial run can resume without creating another board or resetting the admin
password. Once complete, reruns preserve edited boards, icons, credentials and
integrations. Do not remove the marker to reset a live instance: an already
configured instance without a marker is deliberately left alone. Later password
or API key changes should be applied in Homarr's UI.

Runtime session cookies are kept privately only during unfinished bootstrap
and removed after successful completion. Secrets are passed to helpers over
stdin with Ansible `no_log`, not command arguments or templates.

To upgrade, explicitly change `homarr_version` and `homarr_release_checksum`;
similarly update the Node version/checksum when required by upstream. Back up
`/appdata` first. Release extraction preserves the database and migrations run
at service startup. Existing releases remain available, though a downgrade
after a database migration may require restoring the matching backup.

Logs: `journalctl -u homarr` inside CT 127. Also check `nginx` and `redis-server`.
Dashboard status: `curl http://192.168.1.207:7575/api/health/ready`.

## Validation

```sh
ANSIBLE_LOCAL_TEMP=/tmp/ansible-local ansible-playbook --syntax-check playbooks/02-deploy-homarr.yaml
ANSIBLE_LOCAL_TEMP=/tmp/ansible-local ansible-playbook tests/render-homarr.yaml
python3 -m unittest discover -s tests -v
git diff --check
```

Upstream references: [Proxmox installation](https://homarr.dev/docs/getting-started/installation/proxmox/),
[Proxmox integration](https://homarr.dev/docs/integrations/proxmox/),
[Homarr v2.2.0](https://github.com/homarr-labs/homarr/releases/tag/v2.2.0).
