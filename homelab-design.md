# Homelab Architecture & Deployment Strategy

**Hardware:** Raspberry Pi 5 + Proxmox VE 9.2.18 server (Xeon E5-2680v4, 64 GB ECC DDR4, RTX 3060 Ti 8GB, 256GB NVMe [32GB root, no swap, rest LVM-thin], 256GB SATA SSD, 2x 500GB SATA HDD)

**Decisions locked in:** ZFS stripe for the HDDs · Ollama as the inference backend · Immich photo placement **deferred (OPEN DECISION)** — provisionally its Docker volumes go on the SATA SSD until decided.

---

## Big-Picture Architecture

The single most important decision cascades from GPU sharing: a consumer RTX 3060 Ti cannot do SR-IOV/vGPU, so VFIO passthrough binds it to exactly one VM. But if the NVIDIA driver lives on the Proxmox host, any number of LXC containers can share the GPU concurrently (the driver time-slices processes natively, and NVENC is a separate hardware block from CUDA). That makes the host-driver + LXC route the right one here.

Raspberry Pi 5 (bare metal, static IP .53)
 ├─ Technitium DNS + adblock (native install)
 └─ chrony NTP server

Proxmox Host (NVIDIA driver installed on host)
 ├─ LXC 200  jellyfin   (unprivileged, GPU dev-passthrough, bind-mount /tank/data)
 ├─ LXC 201  ollama     (unprivileged, GPU dev-passthrough) ← LLM API server
 ├─ LXC 210  dns2       (optional: secondary Technitium, tiny)
 ├─ VM  110  media      (Docker: Prowlarr/Radarr/Sonarr/Jellyseerr/SABnzbd, virtiofs /tank/data)
 ├─ VM  120  immich     (Docker: official Immich compose, data disk on SATA SSD)
 └─ VM  130  hermes     (Docker or native; NO GPU — calls Ollama over HTTP)

```
                                LAN 192.168.1.0/24
                                       │
        ┌──────────────────────────────┼──────────────────────────────────────┐
        │                              │                                      │
┌───────┴────────┐             ┌───────┴───────┐                       ┌──────┴──────┐
│ Raspberry Pi 5 │             │    Router     │                       │   Clients   │
│  192.168.1.2   │             │  DHCP opts:   │                       │ (TVs, phones│
│                │             │  6 (DNS)→Pi   │                       │  laptops)   │
│ • Technitium   │◄────DNS─────│  42 (NTP)→Pi  │                       └─────────────┘
│   (DNS+Adblock,│             └───────────────┘
│   home.lan)    │
│ • chrony (NTP) │◄───NTP──────────────────────────────┐
└────────────────┘                                     │
                                                       │
┌──────────────────────────────────────────────────────┴───────────────────────────┐
│                     PROXMOX VE HOST  192.168.1.10  (vmbr0)                       │
│                     NVIDIA driver on host · chrony → Pi                          │
│                                                                                  │
│  ┌─────────────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ LXC: media-stack    │  │ LXC: jellyfin│  │ LXC: immich  │  │ LXC: inference│  │
│  │ (unpriv + Docker)   │  │ (unpriv,     │  │ (unpriv +    │  │ (unpriv)      │  │
│  │ one docker-compose: │  │  native)     │  │  Docker)     │  │               │  │
│  │ • Prowlarr          │  │ • Jellyfin   │  │ • server     │  │ • Ollama      │  │
│  │ • Radarr            │  │   NVENC ─┐   │  │ • Postgres   │  │   CUDA ─┐     │  │
│  │ • Sonarr            │  │          │   │  │ • Redis      │  │         │     │  │
│  │ • Jellyseerr        │  │ /data ro │   │  │ • ML (opt.   │  │ :11434  │     │  │
│  │ • SABnzbd           │  │          │   │  │   GPU)──┐    │  │   ▲     │     │  │
│  │ /data rw            │  │          │   │  │         │    │  │   │     │     │  │
│  └─────────┬───────────┘  └────────┬─┼───┘  └─────────┼────┘  └───┼─────┼─────┘  │
│            │                       │ │                │           │     │        │
│            │ bind-mount            │ └────────────────┼───────────┼─────┤        │
│            ▼                       ▼                  ▼           │     ▼        │
│  ┌─────────────────────────────────────────┐   ┌──────────────────┴──────────┐   │
│  │ ZFS stripe "mediapool" (~1TB, RAID0)    │   │ RTX 3060 Ti 8GB (host drv,  │   │
│  │ 2x 500GB HDD · /mediapool/media → /data │   │ /dev/nvidia* dev-bound into │   │
│  └─────────────────────────────────────────┘   │ jellyfin + inference LXCs)  │   │
│                                                └─────────────────────────────┘   │
│  ┌──────────────────────┐  ┌───────────────────────┐  ┌───────────────────────┐  │
│  │ NVMe LVM-thin        │  │ SATA SSD 256GB        │  │ VM: hermes            │  │
│  │ • all guest root     │  │ • SABnzbd incomplete/ │  │ • Hermes Agent        │  │
│  │   disks              │  │   unpack scratch      │  │ • sandboxed, no GPU   │  │
│  │ • Immich Postgres    │  │ • Immich cache (prov.)│  │ • calls Ollama API ───┼──┘
│  └──────────────────────┘  │ • Docker volumes      │  │ • own chrony → Pi     │
│                            └───────────────────────┘  └───────────────────────┘
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Compute Allocation — LXC vs VM, service by service

**Key driver:** a single consumer GPU (RTX 3060 Ti) cannot be shared between VMs (no vGPU/SR-IOV on GeForce). It **can** be shared between any number of LXC containers, because LXCs share the host kernel and just bind the `/dev/nvidia*` device nodes. This forces GPU consumers into LXCs.

| Service | Placement | Reasoning |
|---|---|---|
| Prowlarr, Radarr, Sonarr, Jellyseerr, SABnzbd | **One unprivileged LXC ("media-stack") running Docker, single `docker-compose.yml`** | These are one logical unit: chatty inter-API traffic, shared filesystem paths (hardlinks require same mount!), same UID/GID. Splitting them into 6 LXCs multiplies maintenance for zero isolation benefit. One compose file = atomic upgrades and one backup target. |
| Jellyfin | **Own unprivileged LXC (native install, no Docker)** | Needs NVENC → device binding is simplest in a plain LXC. Separate from media-stack so a downloader-stack rebuild never kills streaming. Native install avoids Docker+NVIDIA-runtime nesting complexity. |
| Immich | **Own unprivileged LXC with Docker** | Immich is only officially supported via docker-compose (server + Postgres + Redis + ML). Heavy and independent lifecycle → isolate it. Its ML container can optionally also use the GPU. |
| LLM inference (Ollama) | **Own unprivileged LXC ("inference")** | See section 2 — dedicated inference server. |
| Hermes Agent | **VM** | A self-improving agent executes arbitrary code. LXCs share the host kernel — a kernel exploit escapes to Proxmox. A VM gives hardware-level isolation. It doesn't need the GPU itself (it calls the inference API over the network), so VM placement costs nothing. |

Note on Docker-in-LXC: Proxmox officially prefers Docker in VMs, but unprivileged LXC + `nesting=1` + `keyctl=1` is stable and the de-facto homelab standard; it wins here on RAM efficiency and GPU sharing.

---

## 2. GPU Sharing Strategy

**Split Hermes from the LLM.** Run a dedicated **inference LXC** running **Ollama** exposing an OpenAI-compatible API; Hermes (in its VM) calls `http://inference:11434`. Benefits: independent lifecycles, the agent stays sandboxed without GPU access, and other consumers (Open WebUI, Immich, scripts) can reuse the same endpoint.

**Configuration (host-driver + LXC device binding, no PCI passthrough):**

1. On the Proxmox **host**: blacklist `nouveau`, install the NVIDIA driver (`.run` installer or pve repo), verify `nvidia-smi`. Add `nvidia-uvm` modules to `/etc/modules-load.d/`.
2. In each GPU LXC config (Jellyfin, inference, optionally Immich-ML), bind:
   ```
   dev0: /dev/nvidia0
   dev1: /dev/nvidiactl
   dev2: /dev/nvidia-uvm
   dev3: /dev/nvidia-uvm-tools
   ```
   (Proxmox 8/9 `dev:` entries handle cgroup device allow + idmap automatically.)
3. Inside each container: install the **same driver version with `--no-kernel-module`** (userland only), plus `nvidia-container-toolkit` where Docker is used (Immich-ML).
4. Contention management on 8 GB VRAM: Jellyfin NVENC uses ~300–500 MB per transcode (encode engines, not compute); keep the LLM to **7B–8B Q4 models (~5–6 GB)** and set `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_KEEP_ALIVE=5m` so VRAM frees when idle. They coexist fine because they stress different engines (NVENC vs CUDA cores).

**Why not VM passthrough:** full passthrough gives the GPU exclusively to one VM — Jellyfin and the LLM could never share it.

**Why Ollama (decision):** easiest to run/maintain, OpenAI-compatible API, automatic VRAM unload — best fit for an 8 GB card shared with Jellyfin (vs llama.cpp server = lighter but more manual model management; vLLM = highest throughput but VRAM-hungry and unsuited to sharing 8 GB).

---

## 3. Storage Layout

| Device | Role |
|---|---|
| 256 GB NVMe (LVM-thin) | Root disks of **all** LXCs/VMs + Postgres data (Immich DB). Fast, thin-provisioned, snapshot-able. |
| 256 GB SATA SSD | **App-data & scratch**: SABnzbd `incomplete/` + unpack dir (protects NVMe write endurance from Usenet unrar churn), Immich upload/thumbnail cache (provisional — see OPEN DECISION), Docker volumes. Format ext4, add as Proxmox **directory storage** or mount + bind-mount. |
| 2× 500 GB HDD | **RAID0 ~1 TB media pool** (ZFS stripe) for completed downloads + Jellyfin library. |
| RAM (tmpfs) | Jellyfin transcode temp directory — you have 64 GB; zero disk wear, fastest possible. |

**RAID0 walkthrough — ZFS stripe (decision: native in Proxmox, lz4 compression, datasets, easy bind-mounts, checksums detect (not repair) corruption; RAM usage fine with 64 GB):**

```bash
# on the Proxmox host
wipefs -a /dev/sdb /dev/sdc
zpool create -o ashift=12 -O compression=lz4 -O atime=off mediapool /dev/sdb /dev/sdc
zfs create mediapool/media
mkdir -p /mediapool/media/{downloads/incomplete,downloads/complete,library/movies,library/tv}
chown -R 101000:101000 /mediapool/media   # maps to uid/gid 1000 inside unprivileged LXCs
```

Bind-mount into the LXCs (`/etc/pve/lxc/<id>.conf`):

```
mp0: /mediapool/media,mp=/data
```

- media-stack LXC sees `/data` → compose maps it into every *arr + SABnzbd container at the **same path** so Radarr/Sonarr can hardlink instead of copy.
- Jellyfin LXC gets the same `mp0`, read-only is fine: `mp0: /mediapool/media,mp=/data,ro=1`.
- Exclude `/data` mountpoints from vzdump backups (`backup=0` flag) — it's disposable media by design.

---

## 4. Network & DNS

- **Static IPs** (reserve in router/DHCP): Pi5 = e.g. `192.168.1.2`, Proxmox = `192.168.1.10`. All guests on `vmbr0` (bridged, same LAN).
- **Pi 5:** Technitium (native or Docker) as DNS with adblock lists + local zone (e.g. `home.lan`) registering every host/LXC; `chrony` as the NTP server (`allow 192.168.1.0/24`).
- **DHCP:** set router DHCP **option 6 (DNS) = Pi IP** and **option 42 (NTP) = Pi IP** → everything on the LAN uses them automatically.
- **Proxmox host:** DNS → Pi in `/etc/resolv.conf` (via GUI: Node → DNS); `chrony` → `server 192.168.1.2 iburst`.
- **LXCs:** inherit host DNS by default (leave "use host settings"); **no NTP needed inside LXCs** — they share the host kernel clock. **VMs (Hermes)** need their own chrony pointed at the Pi + qemu-guest-agent.
- **Resilience:** the Pi is a DNS single-point-of-failure. Configure Technitium's upstream forwarders (e.g. Quad9/Cloudflare DoH), and set the router as a *secondary* DNS only if you accept adblock bypass during Pi outages. Register all services in Technitium so you address `jellyfin.home.lan` instead of IPs.

---

## 5. Automation (redeployability)

Layered, all in one Git repo:

1. **Proxmox host bootstrap — Ansible playbook** (idempotent): repos, NVIDIA driver, ZFS pool creation, SATA SSD mount, storage definitions, LXC template download.
2. **Guest provisioning — OpenTofu/Terraform with the `bpg/proxmox` provider** (declarative LXC/VM inventory: cores, RAM, mounts, `dev:` GPU entries, network) — or Ansible `community.general.proxmox` modules if you prefer one tool.
3. **In-guest configuration — Ansible roles** per guest (docker install, native Jellyfin, Ollama, chrony for the VM), inventoried by Technitium DNS names.
4. **Applications — docker-compose files** in the repo (`media-stack/`, `immich/`), deployed by Ansible, pinned image tags, `.env` secrets via **ansible-vault or sops**.
5. **Pi 5 — its own Ansible playbook** (Technitium + chrony + zone records).
6. **State that matters** (Immich DB, *arr configs): vzdump/PBS backups of LXC root disks; media pool explicitly excluded.

Redeploy = `ansible-playbook host.yml` → `tofu apply` → `ansible-playbook guests.yml`. VM templates add little here since Terraform+cloud-init/LXC templates already cover it — skip Packer-built templates for this scale.

---

## Open decision pending

**Immich photo library placement** — the one dataset that contradicts the "no redundancy" stance: photos on a RAID0 stripe means one dead HDD loses everything. Options considered:

| Option | Trade-off |
|---|---|
| SATA SSD, 256 GB cap (was recommended) | Photos safe from HDD stripe failure, limited to ~200 GB usable. Add off-site backup later. |
| RAID0 HDD pool | Max space (~1 TB shared with media), but one HDD failure loses all photos. Only if phones remain the primary copy. |
| Split: originals HDD, DB+thumbs SSD | Compromise: bulk originals on the stripe, database and thumbnails on SSD; accepts photo-loss risk. |

**Status: deferred by owner** ("I will take care of this later"). Provisional placement until decided: Immich Docker volumes on the SATA SSD, Postgres on NVMe LVM-thin.

All other decisions are locked: **ZFS stripe** for RAID0, **Ollama** for inference, compute/GPU/network/automation layout as above.
