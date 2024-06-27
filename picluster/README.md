# Picluster
Kubernetes cluster of 3 Raspberry Pi 3b+ (Nodes) and a Pi 5 8GB (Master).
Created using Ansible, kubeadm and Flannel CNI, which posed some challenges (minimum hardware requirements are not met by the 3b+).

--------------------

## Preparing all the nodes

Create the cluster either by using:

### A) Ansible

#### 1. Passwordless SSH from control to managed nodes

1. On the control node, if you don't have a key, create it:

`ssh-keygen -t rsa -C "user@domain"`

2. Copy public key to each managed node:

`ssh-copy-id user@node`

3. Now you can simply connect as always, without a password:

`ssh user@node`

4. Now, the playbooks will be able to run. **SSH once into each node before running the playbook.**

#### 2. Run the playbook in ansible/

1. Add the list of hosts in ansible/inventory.yaml accordingly

2. Run the playbook:

`ansible-playbook playbook.yaml -i inventory.yaml -K`


### B) Shell script

Simply execute the shell script kubeadmcluster.sh in all the nodes.

---

## Init the master and join the workers with kubeadm

### Init the master:

Change the pod network accordingly:

`sudo kubeadm init --pod-network-cidr 10.10.0.0/16 --ignore-preflight-errors=Mem --v=10`

### Config kubectl in the master:

1. `mkdir -p $HOME/.kube`
2. `sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config`
3. `sudo chown $(id -u):$(id -g) $HOME/.kube/config`

### Config network CNI (Flannel, its simple):

1. Copy the Flannel manifest

`wget https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml`

2. Modify pod CIDR in kube-flannel.yml to match the one used to init the master.

3. Untaint master

`kubectl taint nodes --all node-role.kubernetes.io/control-plane-`

4. Apply Flannel 

`kubectl apply -f kube-flannel.yml`

5. Confirm:

`kubectl get pods -A -o wide`

6. Print the join command on the master and join the nodes:

`kubeadm token create --print-join-command`

7. List the nodes:

`kubectl get nodes -A -o wide`

---

## TODOs

1. Task for disabling swap permanently in ansible/playbook.yaml can be done better, right now it doesn't if the line has already been commented, although it shouldn't matter much since the playbook is realistically run once.

2. Current Grafana deployment is really rudimentary, although atleast it showed me it can work. Should redo-it following:
  - https://grafana.com/docs/grafana/latest/setup-grafana/installation/kubernetes/
  - https://grafana.com/grafana/dashboards/315-kubernetes-cluster-monitoring-via-prometheus/

3. Ansible tasks for swap only work with Debian and not raspbian, need to implement both.
