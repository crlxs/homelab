# Ansible workspace guidance

- Use fully qualified Ansible module names (`ansible.builtin.*`).
- Keep role defaults non-sensitive. Prompt for one-time values or store persistent secrets in Ansible Vault.
- Use Jinja (`{{ variable }}`) in `.j2` templates; Docker Compose `${VARIABLE}` interpolation is only for runtime Compose environment values.
- Preserve idempotency: create resources only when absent and avoid replacing user-managed configuration.
- Validate playbook changes with `ansible-playbook --syntax-check` and `git diff --check`. Set `ANSIBLE_LOCAL_TEMP` to a writable directory when required by the sandbox.
- Servarr uses native systemd services in unprivileged Debian 13 LXCs. Use the Proxmox API for creation and host SSH/pct for bind mounts and UID mappings; configure guests through `community.proxmox.proxmox_pct_remote`.
- Media/downloads must share one host filesystem and one bind mount. Keep numeric media UID/GID identical on the host and guests; do not format host disks or recursively change existing media ownership by default.
- Do not delete or stop the old Servarr VM during provisioning. New CT IDs/IPs are independent, and storage/config migration is an explicit operator step.
- Run `python3 -m unittest discover -s tests -v` for changes to the native bootstrap or UID mapping logic.
- Run `ansible-playbook tests/render-lxc.yaml` to validate native templates and the bootstrap stdin expression offline.
