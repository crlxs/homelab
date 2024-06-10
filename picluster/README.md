# Picluster
Kubernetes cluster of 3 Raspberry Pi 3b+ (Nodes) and a Pi 5 8GB (Master).
Created using Ansible, kubeadm and Flannel CNI, which posed some challenges (minimum hardware requirements are not met by the 3b+).

--------------------

## Initial Setup

--------------------

Current Grafan deployment is really rudimentary, although atleast it showed me it can work. Should redo-it following:
- https://grafana.com/docs/grafana/latest/setup-grafana/installation/kubernetes/
- https://grafana.com/grafana/dashboards/315-kubernetes-cluster-monitoring-via-prometheus/
