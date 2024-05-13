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
- Ansible

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

<table>
  <thead>
    <tr>
      <th>NET</th>
      <th>VLAN</th>
      <th>CIDR</th>
      <th>GW</th>
      <th>DNS</th>
      <th>DHCP</th>
      <th>DHCP Range</th>
      <th>Static IPs Range</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>192</td>
      <td>N/A</td>
      <td>192.168.1.0/24</td>
      <td>192.168.1.1</td>
      <td>???</td>
      <td>192.168.1.1</td>
      <td>.151 to.200</td>
      <td>.1 to.150</td>
    </tr>
    <tr>
      <td>172</td>
      <td>N/A</td>
      <td>172.17.0.0/16</td>
      <td>172.17.0.254</td>
      <td>???</td>
      <td>172.17.0.254</td>
      <td>.69.0 to.69.255</td>
      <td>.0.1 to.10.255</td>
    </tr>
  </tbody>
</table>


### Hosts

<table>
  <thead>
    <tr>
      <th>HOSTNAME</th>
      <th>DEVICE</th>
      <th>NIC</th>
      <th>MAC</th>
      <th>IP</th>
      <th>CONNECTED TO</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>pix(pi1)</td>
      <td rowspan="3">Raspberry Pi 3 B+</td>
      <td></td>
      <td>00-00-00-00-00-00</td>
      <td>172.17.0.1</td>
      <td>gs1920 PX</td>
    </tr>
    <tr>
      <td>piy(pi2)</td>
      <td></td>
      <td>00-00-00-00-00-00</td>
      <td>172.17.0.2</td>
      <td>gs1920 PX</td>
    </tr>
    <tr>
      <td>piz(pi3)</td>
      <td></td>
      <td>00-00-00-00-00-00</td>
      <td>172.17.0.3</td>
      <td>gs1920 PX</td>
    </tr>
    <tr>
      <td>piw(pi4)</td>
      <td>Raspberry Pi 5 8GB</td>
      <td></td>
      <td>00-00-00-00-00-00</td>
      <td>172.17.0.4</td>
      <td>gs1920 PX</td>
    </tr>
    <tr>
      <td>z10</td>
      <td>My Workstation</td>
      <td></td>
      <td>00-00-00-00-00-00</td>
      <td>172.17.0.10</td>
      <td>gs1920 PX</td>
    </tr>
    <tr>
      <td>erx</td>
      <td>UbiQuiti EdgeRouter X</td>
      <td></td>
      <td>00-00-00-00-00-00</td>
      <td>XX</td>
      <td>XX</td>
    </tr>
    <tr>
      <td>r620</td>
      <td>Dell PowerEdge R620</td>
      <td></td>
      <td>00-00-00-00-00-00</td>
      <td>172.17.0.100</td>
      <td>XX</td>
    </tr>
    <tr>
      <td>gs1920</td>
      <td>ZyXEL GS1920-24</td>
      <td></td>
      <td>00-00-00-00-00-00</td>
      <td>172.17.0.253</td>
      <td>XX</td>
    </tr>
  </tbody>
</table>

--------------------

## Other

#### Why use a git repository

I have tried different ways of documenting my homelab environment (simple .txt files, docs, spreadsheets). The simplicity of a git repo and having everything condensed on a README.md is really convenient, easy to access, modify, track and share.

#### Security concerns (?)

Yes, sharing my internal network in such detail goes against all and any security practices. That being said, I'm realistically a target to no one.

--------------------
