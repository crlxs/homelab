# General considerations:

1. Prometheus node_exporter will be installed as a systemd unit in every node to publish metrics on port 9100.
2. Prometheus snmp_exporter as a k8s deployment to scrape snmp metrics of the other devices (erx, 3505vw, gs1920, etc).
3. Prometheus server as a k8s deployment to scrape the metrics.
4. Grafana deployment to visualize k8s.


# Persistency

As prometheus/grafana pods get destroyed and recreated they will loose the configurations made. To avoid this, I have:

  1. Attached an SSD to the pi-m, new gpt table + 1 partition with fdisk, formatted the partition to ext4 with mkfs.ext4 and mounted it through /etc/fstab on /mnt.
  2. Mkdired /mnt/grafana and /mnt/prometheus.
  3. Chowned /mnt/grafana to UID/GID 472 (runAs for the grafana pod) and /mnt/prometheus to UID/GID 1001 (runAs for the prometheus pod).
  4. Setup an NFS server on the pi-m to expose /mnt/grafana and /mnt/prometheus.
  5. Created a PV for each of the NFS shares.
  6. Created a PVC for each of the deployments that points to the respective NFS shares.
  7. Mounted the directories requiring persistency (/var/lib/grafana, /etc/grafana/grafana.ini, /etc/prometheus/prometheus.yml and /prometheus) to the NFS share through container VolumeMounts specified in the manifest.

A quick example with the Grafana directory:

  1. Partition new disk.
  2. Format new partition to ext4.
  3. Mount to /mnt, edit fstab accordingly to mount at boot.
  4. Create directory for grafana (/mnt/grafana)
  5. Assign dir to proper UID and GUID for grafana and give necessary permissions
    ```
    sudo chown -R 472:472 /mnt/grafana
    sudo chmod -R 755 /mnt/grafana
    ```
  6. Edit /etc/fstab accordingly to mount at boot
  7. Configure nfsshare (/etc/exports) for /mnt/grafana
  8. Deploy all the resources (PV, PVC, Deployment and Services) on the monitoring namespace through the manifest at deployments/monitoring/grafana/grafana.yaml
    > kubectl apply -f grafana.yaml -n monitoring
