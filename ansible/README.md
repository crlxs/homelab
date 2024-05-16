# Passwordless SSH from control to managed nodes

1. On the control node, if you don't have a key, create it with:

`ssh-keygen -t rsa -C "user@domain"`

2. Copy public key to each managed node with:

`ssh-copy-id user@node`
