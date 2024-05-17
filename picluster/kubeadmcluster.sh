#!/bin/bash

# Based on:
# https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/
# https://medium.com/@bsatnam98/setup-of-a-kubernetes-cluster-v1-29-on-raspberry-pis-a95b705c04c1
# https://www.youtube.com/watch?v=xX52dc3u2HU

# CHANGE DISTRO IN LINE 31 and 36

sudo apt update -y
sudo apt upgrade -y

# Disable swap
# sudo swapoff -a
# sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab

# For raspbian 'sudo dphys-swapfile swapoff'. To make it permanent:
sudo dphys-swapfile swapoff
sudo dphys-swapfile uninstall
sudo update-rc.d dhpys-swapfile remove
sudo apt purge dphys-swapfile -y

# For raspbian, enable memory cgroup
# Add cgroup_enable=memory AND cgroup_memory=1 in /boot/firmware/cmdline.txt
# Also add cgroup_enable=cpuset

# Installing containerd

# Enable IPv4 packet forwarding
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.ipv4.ip_forward = 1
EOF

# Apply sysctl parameters without reboot
sudo sysctl --system

# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install containerd
sudo apt-get install containerd.io -y

# Remove CRI from the disabled_plugins list in /etc/containerd/config.toml. NO LONGER NEEDED WITH NEXT COMMANDS CREATING THE DEFAULT CONFIG FILE
# sudo sed -i.bak '/disabled_plugins/d' /etc/containerd/config.toml

# Create the default config file and enable systemd cgroup by find and replace with sed
sudo sh -c 'containerd config default > /etc/containerd/config.toml'
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/g' /etc/containerd/config.toml

#Restart containerd to apply changes to config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd

# --------------------------------------------------------------
# --------------------------------------------------------------

# Installing kubeadm, kubelet and kubectl

sudo apt-get update

# apt-transport-https may be a dummy package; if so, you can skip that package
sudo apt-get install -y apt-transport-https ca-certificates curl gpg -y

curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.30/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.30/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list

sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl

# Exclude all Kubernetes packages from any system upgrades. This is because kubeadm and Kubernetes require special attention to upgrade.
sudo apt-mark hold kubelet kubeadm kubectl

# sudo systemctl enable --now kubelet

sudo systemctl restart containerd
sudo systemctl restart kubelet

# --------------------------------------------------------------
# --------------------------------------------------------------

# From here:
# 1. kube init the master node, e.g.: sudo kubeadm init --pod-network-cidr 10.10.0.0/16 --ignore-preflight-errors=Mem --v=10
# 2. Config kubectl:
#    mkdir -p $HOME/.kube
#    sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
#    sudo chown $(id -u):$(id -g) $HOME/.kube/config
# 3. Config net CNI:
#    wget https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml
#    Modify pod CIDR in kube-flannel.yml to match the one used with kubeadm init
#    Untaint master kubectl: kubectl taint nodes --all node-role.kubernetes.io/control-plane-
# kubectl apply -f kube-flannel.yml
# kubectl get pods -A -o wide
