# Passwordless SSH from control to managed nodes

1. On the control node, if you don't have a key, create it:

`ssh-keygen -t rsa -C "user@domain"`

2. Copy public key to each managed node:

`ssh-copy-id user@node`

3. Now you can simply connect as always, without a password:

`ssh user@node`

Now, the playbooks will be able to run
