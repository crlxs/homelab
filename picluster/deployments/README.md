## Prep

1. Partition new disk.
2. Format new disk to ext4.
3. Create dir for mounting (/mnt/hdd/grafana)
4. Assign dir to proper UID and GUID and give necessary permissions
> sudo chown -R 472:472 /mnt/hdd/grafana
> sudo chmod -R 755 /mnt/hdd/grafana
5. Mount
> sudo mount /dev/sdXx /mnt/hdd
6. Edit /etc/fstab for mount at boot

## K8s comenads
1. Create namespace
> kubectl create namespace grafana
2. Create pv
> kubectl apply -f grafana-pv.yaml
3. Create pvc, deployment and service
> kubectl apply -f grafana.yaml --namespace=grafana
