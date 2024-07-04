# Considerations:

1. Prometheus node_exporter will be installed as a systemd unit in every node to publish metrics on port 9100.
2. Prometheus snmp_exporter to scrape snmp metrics of the other devices (erx, 3505vw, gs1920, etc).
3. Prometheus k8s deployment to scrape the data.
4. Grafana deployment to visualize k8s.




## Prep

1. Partition new disk.
2. Format new partition to ext4.
3. Mount to /mnt, edit fstab accordingly to mount at boot.
4. Create directory for grafana (/mnt/grafana)
5. Assign dir to proper UID and GUID for grafana and give necessary permissions
> sudo chown -R 472:472 /mnt/grafana
<!-- -->
> sudo chmod -R 755 /mnt/grafana
6. Edit /etc/fstab accordingly to mount at boot
7. Configure nfsshare (/etc/exports) for /mnt/grafana

## K8s commands
1. Create namespace, pv, pvc, deployment and service on the monitoring namespace
> kubectl apply -f grafana.yaml --namespace=monitoring

The grafana persistent volume (nfs-grafana-pv) references the nfs share created earlier.
