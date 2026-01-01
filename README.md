# 🖥 Homelab 
My homelab documentation; network/system diagrams, config files, scripts, source code of my apps and anything else.

--------------------

## To do

- [X] **DNS Server** (Technitium on pi)
- [ ] **Prometheus**
- [ ] **Grafana**
- [ ] **Youtube DL**
-------------------

## L1 Diagram

![L1Diagram](diagrams/L1Diagram.jpg)

--------------------

## L3 Diagram

![L3Diagram](diagrams/L3Diagram.jpg)

--------------------


## Service Matrix

<table>
  <thead>
    <tr>
      <th>Service</th>
      <th>Deployed As</th>
      <th>Endpoint</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>DNS Server</td>
      <td>Technitium server on pi</td>
      <td>192.168.1.100 TCP+UDP/53 & TCP 5380 (Web portal)</td>
    </tr>
    <tr>
      <td>NTP Server</td>
      <td>Chrony server on pi</td>
      <td>192.168.1.100 UDP/123</td>
    </tr>
    <tr>
      <td>DHCP Server for 172 network</td>
      <td>DHCP service on ER-X</td>
      <td>172.17.0.254</td>
    </tr>
   </tbody>
 </table>


--------------------

## ER-X Port-maps Table

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
      <td>.151 to .200</td>
      <td>.1 to .150</td>
    </tr>
    <tr>
      <td>172</td>
      <td>N/A</td>
      <td>172.17.0.0/16</td>
      <td>172.17.0.254</td>
      <td>???</td>
      <td>172.17.0.254</td>
      <td>.69.0 to .69.255</td>
      <td>.0.1 to .10.255</td>
    </tr>
 </tbody>
</table>

### Hosts

<details>
<table>
  <thead>
    <tr>
      <th>HOSTNAME</th>
      <th>DEVICE</th>
      <th>NIC</th>
      <th>MAC</th>
      <th>BOND/LACP</th>
      <th>IP</th>
      <th>CONNECTED TO</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>pi</td>
      <td>Raspberry Pi 5 8GB</td>
      <td>eth0</td>
      <td>2c:cf:67:26:4a:55</td>
      <td>N/A</td>
      <td>192.168.1.100</td>
      <td>gs1920 P18</td>
    </tr>
   <!-- Z10 -->
    <tr>
      <td rowspan="3">z10</td>
      <td rowspan="3">My Workstation</td>
      <td>NICX</td>
      <td>00-00-00-00-00-00</td>
      <td>N/A</td>
      <td>DHCP</td>
      <td>gs1920 P26</td>
    </tr>
    <tr>
      <td>NIC2</td>
      <td>00-00-00-00-00-04</td>
      <td>N/A</td>
      <td>X</td>
      <td>gs1920 PX</td>
    </tr>
    <tr>
      <td>NIC3</td>
      <td>00-00-00-00-00-04</td>
      <td>N/A</td>
      <td>X</td>
      <td>gs1920 PX</td>
    </tr>
    <!-- ERX -->
    <tr>
      <td rowspan="5">erx</td>
      <td rowspan="5">UbiQuiti EdgeRouter X</td>
      <td>ETH0</td>
      <td>00-00-00-00-00-03</td>
      <td>N/A</td>
      <td>X</td>
      <td>gs1920 P10</td>
    </tr>
    <tr>
      <td>ETH1</td>
      <td>00-00-00-00-00-04</td>
      <td rowspan="2">bond1</td>
	  <td>N/A</td>
      <td>gs1920 P12</td>
    </tr>
    <tr>
      <td>ETH2</td>
      <td>00-00-00-00-00-05</td>
      <td>N/A</td>
      <td>gs1920 P14</td>
    </tr>
    <tr>
      <td>ETH3</td>
      <td>00-00-00-00-00-05</td>
      <td>N/A</td>
      <td>X</td>
      <td>gs1920 P16</td>
    </tr>
    <tr>
      <td>ETH4</td>
      <td>00-00-00-00-00-05</td>
      <td>N/A</td>
      <td>X</td>
      <td>n/a</td>
    </tr>
    <!-- 3505VW -->
    <tr>
      <td rowspan="4">3505vw</td>
      <td rowspan="4">HGU Askey 3505VW</td>
      <td>ETH1</td>
      <td>00-00-00-00-00-03</td>
      <td>N/A</td>
      <td>X</td>
      <td>X</td>
    </tr>
    <tr>
      <td>ETH2</td>
      <td>00-00-00-00-00-04</td>
      <td>N/A</td>
      <td>X</td>
      <td>X</td>
    </tr>
    <tr>
      <td>ETH3</td>
      <td>00-00-00-00-00-05</td>
      <td>N/A</td>
      <td>X</td>
      <td>X</td>
    </tr>
    <tr>
      <td>ETH4</td>
      <td>00-00-00-00-00-05</td>
      <td>N/A</td>
      <td>X</td>
      <td>gs1920 P2</td>
    </tr>
    <!-- R620 -->
    <tr>
      <td rowspan="5">r620</td>
      <td rowspan="5">Dell PowerEdge R620</td>
      <td>idrac</td>
      <td>00-00-00-00-00-00</td>
      <td>N/A</td>
      <td>172.17.0.1</td>
      <td>gs1920 P19</td>
    </tr>
    <tr>
      <td>NIC1</td>
      <td>00-00-00-00-00-04</td>
      <td>N/A</td>
      <td>X</td>
      <td>gs1920 P21</td>
    </tr>
    <tr>
      <td>NIC2</td>
      <td>00-00-00-00-00-05</td>
      <td>N/A</td>
      <td>X</td>
      <td>gs1920 P23</td>
    </tr>
    <tr>
      <td>NIC3</td>
      <td>00-00-00-00-00-05</td>
      <td>N/A</td>
      <td>X</td>
      <td>XX</td>
    </tr>
    <tr>
      <td>NIC4</td>
      <td>00-00-00-00-00-05</td>
      <td>N/A</td>
      <td>X</td>
      <td>XX</td>
    </tr>
    <!-- GS1920 -->
    <tr>
      <td>gs1920</td>
      <td>ZyXEL GS1920-24</td>
      <td>NICX</td>
      <td>00-00-00-00-00-00</td>
      <td>N/A</td>
      <td>192.168.1.253</td>
      <td>XX</td>
    </tr>
  </tbody>
</table>
</details>

--------------------

## Other

#### Why use a git repository

I have tried different ways of documenting my homelab environment (simple .txt files, docs, spreadsheets). The simplicity of a git repo and having everything condensed on a README.md is really convenient, easy to access, modify, track and share.

#### Security concerns (?)

Yes, sharing my internal network in such detail goes against all and any security practices.

--------------------
