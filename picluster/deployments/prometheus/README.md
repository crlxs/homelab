Refs:

- https://medium.com/codex/reliable-kubernetes-on-a-raspberry-pi-cluster-monitoring-a771b497d4d3
- https://prometheus.io/docs/guides/node-exporter/

Steps:

1. Download the appropiate node_exporter version on each of the nodes:
  - https://github.com/prometheus/node_exporter/releases/download/v<VERSION>/node_exporter-<VERSION>.<OS>-<ARCH>.tar.gz
  - wget https://github.com/prometheus/node_exporter/releases/download/v1.8.1/node_exporter-1.8.1.linux-armv7.tar.gz

2. Install:
  - sudo tar -xvf node_exporter-1.8.1.linux-armv7.tar.gz -C /usr/local/bin/ --strip-components=1

3. Setup nodeexporter as a systemd unit service so it starts at boot:
  - Create file /etc/systemd/system/nodeexporter.service
  - Contents:

        [Unit]
        Description=NodeExporter
        [Service]
        TimeoutStartSec=0
        ExecStart=/usr/local/bin/node_exporter
        [Install]
        WantedBy=multi-user.target

4. Register it:
  - sudo systemctl daemon-reload \
  && sudo systemctl enable nodeexporter \
  && sudo systemctl start nodeexporter
