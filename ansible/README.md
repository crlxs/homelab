# Ansible setup for homelab provisioning on Proxmox

## Requirements

Install the ansible-galaxy collections defined in the requirements file:

```
ansible-galaxy collection install -r ansible/requirements.yaml
```

The Proxmox modules also require some Python packages:

```
python3 -m pip install proxmoxer requests
```

## Proxmox API Variables

The provisioning playbooks run locally and authenticate against the Proxmox API, defined in ansible/group_vars/all.yaml
