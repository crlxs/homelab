# 🖥 Homelab 
My homelab documentation. Network/System diagrams, configuration files, apps, scripts and else.

--------------------

## Services

- Samba DC
- DNS Server
- NTP Server
- DHCP Server
- MDADM USB Array on a Raspberry Pi as an NFS/SMB share (Mostly for read operations, as the USBs won't handle many write cycles).
- Prometheus/Grafana
- qBitTorrent
- *rr suite (Prowlarr, Lidarr, Sonarr, Radarr)
- Torrent-exclusive VPN
- Wireguard VPN for outside access
- DynDNS
- PVE (Proxmox Virtual Environment on my Dell R620)
- Raspberry Pi 3b+ Kubernetes Cluster, where most of these services are hosted.

- *To add service matrix(table)*

-------------------

## L1 Diagram

![L1Diagram](diagrams/L1Diagram.jpg)

--------------------

## L3 Diagram

![L3Diagram](diagrams/L3Diagram.jpg)

--------------------

## Addressing Plan

### Networks

| NET | VLAN | CIDR           | GW           | DNS | DHCP         | DHCP Range       | Static IPs Range |
| :-- | :--- | :------------- | :----------- | :-- | :----------- | :--------------- | :--------------- |
| 192 | N/A  | 192.168.1.0/24 | 192.168.1.1  | ??? | 192.168.1.1  | .151 - .200      | .1 - .150        |
| 172 | N/A  | 172.17.0.0/16  | 172.17.0.254 | ??? | 172.17.0.254 | .69.0 - .69.255  | .0.1 - .10.255   |

### Hosts

| HOSTNAME | DEVICE              | NIC | MAC | IP  | CONNECTED TO | 
| :------: | :-----------------: | :-: | :-: | :-: | :----------: |
| piw      | Raspberry Pi 5 8GB  |     |     |     |              |
| pix      | Raspberry Pi 3 B+   |     |     |     |              |
| piy      | Raspberry Pi 3 B+   |     |     |     |              |
| piz      | Raspberry Pi 3 B+   |     |     |     |              |


--------------------

## Other

#### Why use a git repository

I have tried different ways of documenting my homelab environment (simple .txt files, docs, spreadsheets). The simplicity of a git repo and having everything condensed on a README.md is really convenient, easy to access, modify, track and share.

#### Security concerns (?)

Yes, sharing my internal network in such detail goes against all and any security practices. That being said, I'm realistically a target to no one.

--------------------
