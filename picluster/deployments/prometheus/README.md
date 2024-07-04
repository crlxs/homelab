Refs:

- https://medium.com/codex/reliable-kubernetes-on-a-raspberry-pi-cluster-monitoring-a771b497d4d3
- https://prometheus.io/docs/guides/node-exporter/

# Node monitoring with Prometheus

Install prometheus node_exporter in each node to publish metrics on port 9100 and scrape them with the prometheus deployment

1. Download the appropiate node_exporter version on each of the nodes:
    - https://github.com/prometheus/node_exporter/releases/download/v<VERSION>/node_exporter-<VERSION>.<OS>-<ARCH>.tar.gz
    - wget https://github.com/prometheus/node_exporter/releases/download/v1.8.1/node_exporter-1.8.1.linux-armv7.tar.gz

2. Install:
    - sudo tar -xvf node_exporter-1.8.1.linux-armv7.tar.gz -C /usr/local/bin/ --strip-components=1

3. Setup nodeexporter as a systemd unit service so it starts at boot:
    - Create file /etc/systemd/system/nodeexporter.service
    - Contents:


`[Unit]
Description=NodeExporter
After=network.target

[Service]
TimeoutStartSec=0
#EnvironmentFile=-/etc/default/node_exporter ##### If you use this paramater the flags passed on ExecStart wont be read, use one or the other
User=root
ExecStart=/usr/local/bin/node_exporter --collector.systemd --collector.sysctl
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target`

4. Register it:
    - sudo systemctl daemon-reload \
    && sudo systemctl enable nodeexporter \
    && sudo systemctl start nodeexporter

---

Prometheus database (TSDB) is in /prometheus inside the pod. To avoid destroying the Micro-SD card of the Pis, I hvae mounted /prometheus to a NFS share in the pi-m (172.17.0.1/mnt/prometheus) through a PersitentVolume and PersistentVolumeClaim
Prometheus container runs as uid and gid 1001, and /mnt/prometheus is chowned and to those.

Jobs for monitoring the nodes I took from here:
https://www.stackhero.io/en/services/Prometheus/documentations/Using-Node-Exporter/Configure-Prometheus-Server-to-scrape-data-from-Node-Exporter
