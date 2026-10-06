# Native Servarr deployment

Run `ansible-playbook playbooks/01-deploy-servarr.yaml` from the Ansible root.
All three plays are required: provision on PVE, configure each LXC, then run
the API bootstrap from SABnzbd. Inventory is created in memory during the
first play. Avoid `--limit sabnzbd`, which would skip that prerequisite.

The API creates containers through `community.proxmox.proxmox`. Host SSH
configures bind mounts and subordinate IDs because those are root operations
in Proxmox. Guest tasks use `community.proxmox.proxmox_pct_remote`; the existing
`ansible` host user must have passwordless sudo for pct (and host preparation).
The controller needs `proxmoxer`, `requests`, `paramiko` and the collections in
`requirements.yaml`. No community installer scripts are executed.

For a distribution-installed Ansible on Debian/Ubuntu, install controller
dependencies with `sudo apt install python3-proxmoxer python3-requests
python3-paramiko`. If Ansible runs in a Python virtual environment, install
these libraries with pip inside that same environment instead.

## Shell access

Connect to the Proxmox host using its existing SSH account/key, then enter a
running container directly:

```sh
ssh -i ~/.ssh/ansible ansible@192.168.1.100
sudo pct enter 124 # SABnzbd; replace with the desired CT ID below
```

`pct enter` opens a root shell without requiring a container login password.
Use `exit` to return to the Proxmox host. The playbook does not configure
container shell passwords or guest SSH keys; the shared UI password applies
only to the web applications. The `media` account is a service account with
`/usr/sbin/nologin`, not an interactive login account.

## Configuration

Edit `inventory/group_vars/proxmox.yaml` for the node, CT IDs, static IPs,
gateway, DNS, bridge and root/template storage. Defaults are:

| Application | CT ID | Address | UI port | Media mount |
| --- | --- | --- | --- | --- |
| Radarr | 121 | 192.168.1.201 | 7878 | read/write |
| Sonarr | 122 | 192.168.1.202 | 8989 | read/write |
| Prowlarr | 123 | 192.168.1.203 | 9696 | none |
| SABnzbd | 124 | 192.168.1.204 | 8081 | read/write |
| Jellyseerr | 125 | 192.168.1.205 | 5055 | none |
| Jellyfin | 126 | 192.168.1.206 | 8096 | read/write |

Every LXC also exposes a Prometheus node exporter on 9100. These exporters
provide guest OS metrics; their metric names differ from cAdvisor, so adjust
existing Prometheus targets and Docker-specific dashboards. Proxmox remains
the source for host-level and per-container resource accounting.

The role downloads the current Debian 13 standard amd64 template automatically.
Set `servarr_lxc_template` to a filename from `pveam available` to pin it.
Template selection affects new LXCs; existing ones are not reinstalled.
Root disks live on `servarr_lxc_storage` (normally SSD-backed `local-lvm`).
Changing `disk` after creation does not automatically resize root disks; use
`pct resize <id> rootfs +<size>G` separately when expansion is needed.

Edit `inventory/group_vars/all.yaml` for the host/guest media path and numeric
IDs. Default UID/GID 1500 must be free or already belong to `media` on the
host and guests. The role refuses to renumber existing media accounts.
All other guest IDs retain the normal 100000 offset; only `media` maps directly
to the host's IDs. Changes to mappings/resources/network require a brief CT
shutdown; an unchanged rerun does not stop containers.

Radarr, Sonarr and Prowlarr use official stable Linux archives, downloaded
only when their binaries are absent. App-managed updates remain possible
because binaries are owned by `media`. Override `servarr_arr_downloads` and
`servarr_arr_checksums` before initial deployment to pin exact artifacts.
SABnzbd comes from Debian 13 backports, following its upstream Debian guide.
Jellyseerr is retained at v2.7.3, built with Node 22 and pnpm 9.15.9; this is
deliberately not an implicit migration to its successor Seerr. Its 4 GiB RAM
default supports the first source build. The role does not upgrade an existing
Jellyseerr checkout automatically.
The role applies a small compatibility patch to use the standard `Authorization`
header in Jellyseerr's source and compiled Jellyfin API client, as Jellyfin 12
no longer accepts the legacy `X-Emby-Authorization` header. Rebuilding the
application retains the patched source; the playbook reapplies it idempotently.

Jellyfin uses its official Debian repository and `jellyfin-ffmpeg8`. With
`jellyfin_nvidia_enabled: true`, the role detects the host NVIDIA driver,
passes `/dev/nvidia*` devices into the unprivileged Jellyfin LXC using Proxmox
`devN` entries (guest ownership `media:media`, mode 0660), and installs exactly
matching userspace libraries **only inside that LXC**. It does not install a
host driver, a guest kernel module, or chmod host devices. A real H.264 NVENC
smoke test runs as `media` before deployment succeeds. Upgrade the host driver
separately, then rerun the playbook to update the guest libraries. The NVIDIA
download URL/checksum can be overridden for a pinned/local installer.

The default decoding codec list targets the current RTX 3060 Ti; override
`jellyfin_nvidia_decoding_codecs` for another GPU. AV1 encoding is not enabled.
Disable `jellyfin_nvidia_enabled` for software-only installations; disabling
does not remove existing passthrough devices or reset manually chosen encoding
settings. No changes are made to other GPU-using LXCs.

## Storage and migration

The HDD filesystem must already be mounted at `servarr_host_media_dir`,
default `/opt/media`, on PVE and mounted persistently across host reboots.
Provisioning refuses to continue if that exact path is not a mountpoint.
Alternatively, set `servarr_media_uuid` to an existing filesystem's UUID and
`servarr_media_fstype` (default `ext4`); the role mounts it on PVE and persists
the mount in `/etc/fstab`. It refuses to replace a different filesystem already
mounted at the target path. It never formats or attaches a raw disk. Move the
existing filesystem out of the VM before using it on the host; never mount
the same block filesystem in the VM and host at the same time.

```text
/media-pool                        # configured host ZFS mount; /opt/media in guests
├── movies                         # Radarr root folder
├── tv                             # Sonarr root folder
├── transcodes
│   └── jellyfin                   # temporary transcoding, not the SSD root disk
└── downloads
    ├── incomplete                 # SAB working files
    └── complete
        ├── radarr
        ├── sonarr
        └── prowlarr
```

One mount preserves consistent absolute paths and allows hardlinks/atomic
renames between downloads and the libraries. Prowlarr/Jellyseerr do not need
the media filesystem. Jellyfin uses the same UID/GID mapping and single bind
mount, without NFS. Its mount is read/write because temporary transcoding files
live on the same HDD filesystem; media deletion is not enabled by the bootstrap.
For ZFS, leave `servarr_media_uuid: ""`; ZFS manages `/media-pool` independently
of `/etc/fstab`. The role checks the mount and does not format/import the pool.

For migration, back up `/opt/servarr` from the VM and stop the old stack before
moving its media filesystem. Prepare/mount storage on PVE and run the playbook
to create the native services. Existing application databases/settings are
**not copied automatically**. To restore them, stop the new service, copy that
application's old config directory into `/opt/servarr/<app>` inside its LXC,
set ownership to `media:media`, then restart and rerun the playbook. For
Jellyseerr, restore into the same data directory, not its source checkout.
Keep a backup before opening an old database with a newer application.

Old Docker files may have different numeric ownership. Directory ownership
is prepared without recursively rewriting the library. If necessary, set
`servarr_media_repair_ownership: true` in the Proxmox group vars for one run;
then disable it again. This explicitly changes existing files to the media
account and can take time for large libraries.

The old VM 120 is not removed. It uses 192.168.1.200, so the new LXCs can be
created without an IP/ID collision. Update bookmarks/reverse proxy/DNS to
the new service addresses before retiring the VM manually.

Bind-mounted media is not included in Proxmox LXC backups. Back it up
separately if desired. App data stays on each LXC root disk and is included
in normal CT backups.

## Bootstrap and secrets

Copy `inventory/servarr.local.yaml.example` to `inventory/servarr.local.yaml`,
run `chmod 600 inventory/servarr.local.yaml`, and fill it in locally. The playbook
automatically loads this Git-ignored file without prompts; no secret belongs
in role defaults or tracked inventory. Existing copies are never overwritten.
Git ignore is not encryption: for persistent secrets, encrypt the file:

```sh
ansible-vault encrypt inventory/servarr.local.yaml
ansible-playbook playbooks/01-deploy-servarr.yaml --ask-vault-pass
```

Alternatively, use a protected Vault password source with `--vault-password-file`
to avoid even that prompt, or provide encrypted extra vars. Keep Vault password
files outside Git. Without encryption, the local file remains plaintext but
is accessible only to its owner; do not use `git add -f` on it.

The bootstrap waits for readiness with bounded timeouts, reads app API keys
into Ansible memory, and sends credentials to its scripts on stdin with
`no_log: true`. No standalone plaintext UI-password file or transferred
config/API-key file is left on PVE or in the guests. Applications still
persist their own required credentials/API keys in their normal private
configuration (notably SABnzbd's provider credentials).

The first run creates UI accounts using one shared password, configures
SABnzbd folders/categories/provider (SSL defaults to on for port 563), adds
SABnzbd to all three Arr apps, registers Radarr/Sonarr in Prowlarr and sets
`movies`/`tv` as their root folders. It also creates NZBGeek from Prowlarr's
native Newznab schema and an enabled sync profile, then synchronizes indexers
to the registered apps. SAB API calls originate on localhost,
retaining its hostname protections. Service integrations use real LXC IPs.

Reruns preserve existing UI passwords and provider passwords, avoid duplicate
root folders/clients/applications/indexers, and reconcile bootstrap-owned connection
fields when IPs or API keys change. Differently named SAB clients remain
user-managed. Provider non-secret settings and media paths are reconciled;
password rotation is an explicit app UI/API operation. Supplied passwords
are only used to create accounts/provider credentials when absent.
When an Arr API masks its stored key, the bootstrap uses the provider's test
endpoint to verify that the saved connection works instead of rewriting the
key on every run. A stale connection is repaired with the current source key;
no plaintext key cache is created. Empty optional fields and schema metadata
returned by the APIs do not cause spurious updates.

The Jellyfin bootstrap creates its initial administrator using the shared UI
password (override `jellyfin_admin_username`/`jellyfin_admin_password` in the
private file if desired), completes its wizard, adds Movies/TV Shows libraries,
sets the transcoding directory and enables NVENC. It creates Jellyseerr's initial
Jellyfin administrator and server API token, enables those libraries and completes
the connection wizard. Sign into Jellyseerr using the Jellyfin login option and
that account. When no existing service settings are present, Radarr and Sonarr
are added as default request services using their `HD-1080p` quality profiles
and `movies`/`tv` roots. Override `jellyseerr_radarr_quality_profile_name` and
`jellyseerr_sonarr_quality_profile_name` for another first-run choice. Existing
Jellyseerr service/quality choices are never replaced on reruns.

Reruns preserve established accounts, extra libraries, encoding settings other
than the managed path/NVENC fields, and other Jellyseerr library selections.
An existing different Jellyfin server connection is rejected rather than
silently replaced. Update the private file when changing the Jellyfin admin
password in its UI, since the API bootstrap authenticates with it on reruns.
NZBGeek's managed URL/API key are reconciled (including key rotation); other
indexer fields are preserved. A differently named existing NZBGeek remains
user-managed and is not duplicated.

## Validation

```sh
ANSIBLE_LOCAL_TEMP=/tmp/ansible-local ansible-playbook --syntax-check playbooks/01-deploy-servarr.yaml
ANSIBLE_LOCAL_TEMP=/tmp/ansible-local ansible-playbook tests/render-lxc.yaml
python3 -m unittest discover -s tests -v
git diff --check
```

The tests exercise bootstrap creation, unchanged reruns, endpoint/key changes,
preservation of existing credentials and UID/GID mapping ranges. They do not
replace an integration run against a Proxmox node. Proxmox provisioning does
not support a complete `--check` run; use syntax checks for offline validation.

Upstream references:

- [Proxmox LXC management](https://docs.ansible.com/projects/ansible/latest/collections/community/proxmox/proxmox_module.html)
- [Ansible pct connection](https://docs.ansible.com/projects/ansible/latest/collections/community/proxmox/proxmox_pct_remote_connection.html)
- [Unprivileged container UID mapping](https://pve.proxmox.com/wiki/Unprivileged_LXC_containers)
- [Servarr native installer reference](https://github.com/Servarr/Wiki/blob/master/servarr/servarr-install-script.sh)
- [SABnzbd Debian installation](https://sabnzbd.org/wiki/installation/install-debian)
- [Jellyseerr pinned build requirements](https://github.com/Fallenbagel/jellyseerr/blob/v2.7.3/package.json)
- [Jellyfin NVIDIA acceleration](https://jellyfin.org/docs/general/post-install/transcoding/hardware-acceleration/nvidia/)
- [Community Jellyfin installer reference](https://github.com/community-scripts/ProxmoxVE/blob/main/install/jellyfin-install.sh)
