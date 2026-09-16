# Ansible setup for homelab provisioning on Proxmox

## Proxmox Node requirements

Ansible uses SSH to perform actions on the machines, but the Proxmox API is also usable. For this, we need to add the SSH key that the ansible user will use and an API token.

1. How to create the API token + user
    * **Create the Proxmox user**: Navigate to Datacenter -> Permissions -> Users and click Add.
        - **Username**: ansible
        - **Realm**: Proxmox VE authentication server (NOT PAM)
        - **Password**: Empty

    * **Generate API Token**: Navigate to Datacenter -> Permissions -> API Toklens and click Add.
        - **User**: ansible@pve
        - **TokenId**: ansible (must match the proxmox_api_token_id at ansible/inventory/group_vars/proxmox.yaml)
        - **Privilege Separation**: Uncheck this box. (If checked, you would have to manually assign the permissions from Step 2 to the token itself. Unchecking it allows the token to inherit the user's permissions).

    * **Assign permissions both for the user and API key**: Navigate to Datacenter -> Permissions and click Add -> User Permission and API Token permission
    
    - Path: /
    - User: ansible@pve
    - Role: Administrator



## Requirements

1. Install the ansible-galaxy collections defined in the requirements file:

```
ansible-galaxy collection install -r ansible/requirements.yaml
```

2. The Proxmox modules also require some Python packages on the Ansible controller:

```
python3 -m pip install proxmoxer requests requests_toolbelt
```

3. Proxmox API. The provisioning playbooks run locally and authenticate against the Proxmox API. Connection settings live in `inventory/group_vars/proxmox.yaml`.

The API token secret is not committed. Provide it either via an ansible-vault encrypted variable (`vault_proxmox_api_token_secret`) or via the environment:

```
export PROXMOX_TOKEN_SECRET='...'
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

### How to create the API token + user

1. Create the Proxmox user

Navigate to Datacenter -> Permissions -> Users and click Add.

    - Username: ansible
    - Realm: Proxmox VE authentication server (NOT PAM)
    - Password: Empty

2. Generate API Token

Navigate to Datacenter -> Permissions -> API Toklens and click Add.

    - User: ansible@pve
    - TokenId: ansible (must match the proxmox_api_token_id at ansible/inventory/group_vars/proxmox.yaml)
    - Privilege Separation: Uncheck this box. (If checked, you would have to manually assign the permissions from Step 2 to the token itself. Unchecking it allows the token to inherit the user's permissions).

3. Assign permissions both for the user and API key

Navigate to Datacenter -> Permissions and click Add -> User Permission and API Token permission
    
    - Path: /
    - User: ansible@pve
    - Role: Administrator


## Usage

Run from the `ansible/` directory so `ansible.cfg` is picked up:

```
ansible-playbook playbooks/00-create-template.yaml
ansible-playbook playbooks/10-provision-vms.yaml
```

VM definitions (name, vmid, ip, resources) are declared in
`inventory/group_vars/proxmox.yaml` under `proxmox_vms`.

