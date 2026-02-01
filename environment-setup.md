Got it — if you want **hard separation** (own kernel, virtualised hardware, clean blast-radius), a proper VM is the right call. Here’s a step-by-step “VirtualBox-style” environment that’s *meaningfully* more isolated than WSL2.

## Target architecture

* **Windows host** (your normal machine)
* **VirtualBox VM** running **Ubuntu LTS**
* Development happens **inside the VM**
* Optional: interact from Windows via **SSH** (so you can use VS Code on Windows while code executes in Linux VM)
* Optional: Docker runs **inside the VM** (so containers are isolated too)

---

# 1) Install VirtualBox (and Extension Pack if you need USB passthrough)

1. Install **Oracle VirtualBox** on Windows.
2. Install the **VirtualBox Extension Pack** *only if you need USB 2/3 passthrough or enhanced features*.

**Isolation note:** Extension Pack increases integration features; if you’re going for “super separated,” you may not want USB passthrough at all.

---

# 2) Download an Ubuntu ISO (LTS)

Download the latest **Ubuntu LTS Desktop** ISO (Desktop is easiest initially; you can move to Server later).

---

# 3) Create the VM (secure-ish defaults)

In VirtualBox → **New**:

* Name: `Tooeybot`
* Type: Linux
* Version: Ubuntu (64-bit)

Recommended VM resources (tweak to your machine):

* **RAM**: 8 GB (minimum 4 GB)
* **CPU**: 4 cores (minimum 2)
* **Disk**: 80–120 GB (dynamically allocated)

Now go into **Settings**:

### System

* **EFI**: Off (unless you prefer UEFI; either is fine)
* **Enable I/O APIC**: On
* **Hardware virtualisation**: On (VT-x/AMD-V)
* **Paravirtualisation**: Default

### Display

* Video memory: 128 MB
* 3D acceleration: optional (nice for Desktop)

### Network (choose based on your risk tolerance)

* **NAT** (default): VM has internet, but is harder to reach from LAN. Good isolation.
* If you want easy SSH from Windows, keep NAT and use port forwarding (next section).
* Avoid “Bridged” if you want extra separation (bridged puts VM directly on your LAN like a real machine).

### General → Advanced (important for isolation)

Set these to **Disabled**:

* Shared Clipboard: Disabled
* Drag’n’Drop: Disabled

(You can enable later if you decide convenience > isolation.)

---

# 4) Boot and install Ubuntu

1. Attach the Ubuntu ISO to the VM (Optical Drive).
2. Start VM → install Ubuntu normally.
3. During install:

   * Enable disk encryption if you want (optional but good practice).
   * Use a strong password.

After install finishes: eject ISO and reboot.

---

# 5) Add SSH access (so you can use Windows tools without “blurring” the boundary)

Inside Ubuntu VM:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y openssh-server git build-essential python3 python3-venv python3-pip jq
sudo systemctl enable --now ssh
```

## NAT Port Forwarding (recommended)

VirtualBox VM → Settings → Network → NAT → Advanced → Port Forwarding

Add a rule:

* Name: `ssh`
* Protocol: TCP
* Host IP: 127.0.0.1
* Host Port: 2222
* Guest IP: (leave blank)
* Guest Port: 22

Now from Windows PowerShell:

```powershell
ssh youruser@127.0.0.1 -p 2222
```

This gives you clean access without putting the VM on your LAN.

---

# 6) VS Code workflow (best of both worlds)

Option A (cleanest dev UX): **VS Code on Windows → Remote SSH into VM**

1. Install VS Code on Windows
2. Install extension: **Remote - SSH**
3. Connect to: `ssh youruser@127.0.0.1 -p 2222`
4. Open a folder in the VM, e.g. `~/dev/tooeybot`

This keeps your code and runtime *inside the VM* but lets you use your normal editor.

---

# 7) Install Docker *inside the VM* (keeps containers isolated from Windows)

Inside the Ubuntu VM:

```bash
sudo apt install -y ca-certificates curl gnupg
```

Then either:

* use Ubuntu’s `docker.io` package (simple, slightly older), or
* install Docker CE from Docker’s repo (more current).

If you want simple and stable:

```bash
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
docker run hello-world
```

---

# 8) Create the dev workspace inside the VM

Inside VM:

```bash
mkdir -p ~/dev/tooeybot/{bot,skills,memory,playground,infra}
cd ~/dev/tooeybot
git init
```

---

# 9) “Super separated” hardening tweaks (worth doing)

These reduce accidental cross-over and “oops I mounted my whole C drive.”

### In VirtualBox settings

* **Disable** Shared Clipboard & Drag’n’Drop (already done)
* **Do not use shared folders** unless you absolutely must
  (they punch a very direct hole through isolation)

### Prefer file transfer via:

* `git push/pull` to a private repo, or
* `scp` over your forwarded SSH port:

  ```powershell
  scp -P 2222 .\somefile.txt youruser@127.0.0.1:~/dev/tooeybot/playground/inputs/
  ```

### Use Snapshots aggressively

* Snapshot after base OS + tools installed
* Snapshot before any “big change” (Docker config, dependency churn)

---

# 10) Optional: even more isolation than VirtualBox

If “super separated” means “I don’t trust my host at all”:

* Put the VM on a **separate VLAN** / guest Wi-Fi
* Use a dedicated cheap mini-PC as a host for the VM
* Or use a Type-1 hypervisor like **Proxmox** (heavier lift)

But for most dev workflows, **VirtualBox + NAT + no shared folders + no clipboard** is a big step up from WSL2.
