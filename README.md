# Ansible setup for homelab provisioning on Proxmox

VMs are provisioned with a **golden image** approach: a Debian 13 template is
created manually on the Proxmox node (with users, SSH keys and base packages
baked in), and Ansible only clones it, applies per-VM configuration
(resources, network via cloud-init) and starts the VMs.

## Layout

```
ansible/
├── ansible.cfg                       # inventory + roles path defaults
├── requirements.yaml                 # ansible-galaxy collections
├── inventory/
│   ├── hosts.yaml                    # proxmox node + (optional) static VM entries
│   └── group_vars/
│       ├── all.yaml                  # shared vars (ansible user, SSH key)
│       └── proxmox.yaml              # Proxmox API settings + VM definitions
├── playbooks/
│   └── 00-provision-vms.yaml         # clone VMs from the golden image
└── roles/
    ├── proxmox_vm/                   # clone template, configure, start VMs
    └── docker/                       # install Docker engine on Debian guests
```

## Proxmox node requirements

Provisioning talks to the Proxmox API (no SSH needed for cloning), but the
node is also kept in the inventory for node-level management tasks.

### 1. Create the API user + token

1. **Create the Proxmox user**: Datacenter -> Permissions -> Users -> Add.
    - **Username**: ansible
    - **Realm**: Proxmox VE authentication server (NOT PAM)
    - **Password**: Empty

2. **Generate the API token**: Datacenter -> Permissions -> API Tokens -> Add.
    - **User**: ansible@pve
    - **TokenId**: ansible (must match `proxmox_api_token_id` in `inventory/group_vars/proxmox.yaml`)
    - **Privilege Separation**: Uncheck. (If checked, you would have to manually assign the permissions from the next step to the token itself. Unchecking it allows the token to inherit the user's permissions.)

3. **Assign permissions to both the user and the API token**: Datacenter -> Permissions -> Add -> User Permission and API Token Permission.
    - **Path**: /
    - **User**: ansible@pve
    - **Role**: Administrator

### 2. Add the ansible system user + SSH key on the node

* **Create the system user from within the node**:

    ```
    adduser ansible
    ```

* **Install sudo**:

    ```
    apt update && apt install sudo -y
    ```

* **Grant the user sudo privileges**:

    ```
    usermod -aG sudo ansible
    ```

* **Switch to the ansible user and create the .ssh directory**:

    ```
    su - ansible
    mkdir -p ~/.ssh
    chmod 700 ~/.ssh
    ```

* **Add the public key**:

    ```
    vim ~/.ssh/authorized_keys
    chmod 600 ~/.ssh/authorized_keys
    ```

* **Add a NOPASSWD rule for the ansible user**:

    ```
    echo "ansible ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ansible
    chmod 440 /etc/sudoers.d/ansible
    ```

* **Test the connection**:

    ```
    ssh ansible@192.168.1.100 -i $SSH_KEY_NAME
    ```

## Golden image prerequisites

The template (default vmid `9000`, see `roles/proxmox_vm/defaults/main.yaml`)
is created manually and must contain:

- `cloud-init` and `qemu-guest-agent` packages installed
- a cloud-init drive attached (`ide2: <storage>:cloudinit`)
- the `ansible` user with the SSH public key baked in and NOPASSWD sudo
- root disk on `scsi0` (the role's disk resize targets `scsi0`)
- cloud-init drive
- run `cloud-init clean` inside the VM before converting it to a template, so
  clones re-run cloud-init on first boot (this is what applies the per-VM
  hostname and IP configuration)
- **GPT partition table and no swap partition** so the proxmox_vm role can grow the
  partition if you change the disk size from the default. Enable swapfile

Proxmox passes each clone's VM name to cloud-init as the hostname, and the
role sets `ipconfig0` (static IP/gateway or DHCP) per VM, so no SSH access is
needed during provisioning.

Cloud init install steps:

```
apt install -y cloud-init cloud-initramfs-growroot
systemctl enable cloud-init-local
systemctl enable cloud-init
systemctl enable cloud-config
systemctl enable cloud-final
truncate -s 0 /etc/machine-id
rm -f /var/lib/dbus/machine-id
ln -s /etc/machine-id /var/lib/dbus/machine-id
cloud-init clean --logs --seed
```

## Ansible control node requirements (where you run the playbook from)

1. Install the ansible-galaxy collections defined in the requirements file:

    ```
    ansible-galaxy collection install -r ansible/requirements.yaml
    ```

2. The Proxmox modules also require some Python packages on the controller:

    ```
    python3 -m pip install proxmoxer requests requests_toolbelt
    ```

3. Proxmox API connection settings live in `inventory/group_vars/proxmox.yaml`.
   The API token secret is not committed. Provide it either via an
   ansible-vault encrypted variable (`vault_proxmox_api_token_secret`) or via
   the environment:

    ```
    export PROXMOX_TOKEN_SECRET='...'
    ```

## Usage

VM definitions (name, vmid, ip, resources) are declared in
`inventory/group_vars/proxmox.yaml` under `proxmox_vms`; supported keys are
documented in `roles/proxmox_vm/defaults/main.yaml`.

Run from the `ansible/` directory so `ansible.cfg` is picked up:

```
ansible-playbook playbooks/00-provision-vms.yaml
```

The playbook clones each VM from the golden image, applies its configuration,
starts it, and (for VMs with a static `ip`) waits until it is reachable over
SSH.
