# Ansible setup for homelab provisioning on Proxmox

## Requirements

Install the ansible-galaxy collections defined in the requirements file:

```
ansible-galaxy collection install -r requirements.yaml
```

The Proxmox modules also require some Python packages on the Ansible controller:

```
python3 -m pip install proxmoxer requests
```

## Layout

```
ansible/
├── ansible.cfg                       # inventory + roles path defaults
├── inventory/
│   ├── hosts.yaml                    # proxmox group (localhost, API-driven)
│   └── group_vars/
│       ├── all.yaml                  # shared vars (ansible user, SSH keys, DNS)
│       └── proxmox.yaml              # Proxmox API settings + VM definitions
├── playbooks/
│   ├── 00-create-template.yaml       # build the Debian cloud-init template
│   └── 10-provision-vms.yaml         # clone VMs from the template
└── roles/
    ├── proxmox_debian_template/      # download image, create + finalize template
    ├── proxmox_vm/                   # clone, configure cloud-init, start VMs
    └── docker/                       # install Docker engine on Debian guests
```

## Proxmox API variables

The provisioning playbooks run locally and authenticate against the Proxmox
API. Connection settings live in `inventory/group_vars/proxmox.yaml`.

The API token secret is not committed. Provide it either via an
ansible-vault encrypted variable (`vault_proxmox_api_token_secret`) or via
the environment:

```
export PROXMOX_TOKEN_SECRET='...'
```

## Usage

Run from the `ansible/` directory so `ansible.cfg` is picked up:

```
ansible-playbook playbooks/00-create-template.yaml
ansible-playbook playbooks/10-provision-vms.yaml
```

VM definitions (name, vmid, ip, resources) are declared in
`inventory/group_vars/proxmox.yaml` under `proxmox_vms`.
