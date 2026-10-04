# Ansible workspace guidance

- Use fully qualified Ansible module names (`ansible.builtin.*`).
- Keep role defaults non-sensitive. Prompt for one-time values or store persistent secrets in Ansible Vault.
- Use Jinja (`{{ variable }}`) in `.j2` templates; Docker Compose `${VARIABLE}` interpolation is only for runtime Compose environment values.
- Preserve idempotency: create resources only when absent and avoid replacing user-managed configuration.
- Validate playbook changes with `ansible-playbook --syntax-check` and `git diff --check`. Set `ANSIBLE_LOCAL_TEMP` to a writable directory when required by the sandbox.
