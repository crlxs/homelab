## 🏗️ Storage Architecture: ZFS to NAS LXC

This setup leverages Proxmox **Bind Mounts** and a **Privileged Container** to serve ZFS datasets over the network with near-native performance.

### 1. ZFS Backend (Proxmox Host)
* **Pool:** 6-disk RAIDZ2 pool (`vault`) for dual-disk fault tolerance.
* **Datasets:** Managed via CLI for granular control:
  * `vault/media`: Optimized with `recordsize=1M` for large media file streaming, with a `quota=1T`.
  * `vault/personal`: With a `quota=200G`.
* **Properties:** All datasets utilize `lz4` compression and `atime=off` to minimize IOPS overhead.

### 2. The NAS Gateway (LXC)
* **Type:** Privileged Debian container.
  * **Reasoning:** Syncs UIDs/GIDs between the host and container, simplifying permission management for SMB/NFS.
* **Resources:** 512MB RAM, 1 vCPU, 8GB Root disk.
* **Features Enabled:** `NFS` and `CIFS` support enabled in Proxmox container options and NFS/SAMBA server installed on it.

### 3. Data Integration (Bind Mounts)
Direct mapping of host paths to container paths via `/etc/pve/lxc/[CONTAINER-ID].conf`:
* `mp0: /vault/personal,mp=/mnt/personal`
* `mp1: /vault/media,mp=/mnt/media`

### 4. Permission Logic
* **Ownership:** Files on the host are mapped to `UID:1000` (Main User) and `GID:2000` (Media Group).
* **Inheritance:** The `setgid` bit (`chmod g+s`) is applied to the Media directory, ensuring all newly created content inherits the `media` group for seamless access by Sonarr, Radarr, and Plex.

### 5. Network Sharing Protocols

| Protocol | Target | Configuration |
| :--- | :--- | :--- |
| **Samba (SMB)** | Windows Clients | Authenticated access for `Personal`, Guest/User access for `Media`. | 
| **NFS v4** | Linux VMs/LXCs | Kernel-level sharing for high-performance mounting by "Arr" automation apps. |
