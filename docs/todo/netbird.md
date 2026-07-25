# WanOS Remote Configuration: Zero-Trust Mesh & SSH Hardening

This document outlines the steps to lock down your WanOS Raspberry Pi using cryptographic SSH keys and securely expose it for remote configuration using **NetBird Cloud**, a WireGuard-based zero-trust mesh network.

---

## 1. Phase 1: SSH Hardening (Key-Pair Authentication)

Before attaching the Pi to any remote network, we must disable standard password logins. Passwords can be brute-forced; cryptographic keys cannot. We will use the `Ed25519` algorithm, which is the modern industry standard for speed and security on edge devices.

### Step 1a: Generate the Key (Run on your LAPTOP/CLIENT)
Open a terminal on the computer you will use to manage WanOS (macOS, Linux, or Windows via PowerShell/Git Bash). Do not run this on the Pi.

```bash
# Generate a new Ed25519 key pair.
# -t specifies the algorithm (ed25519).
# -C is a comment to help you identify the key later.
ssh-keygen -t ed25519 -C "wanos_admin_laptop"

# When prompted for a file to save the key, press Enter to accept the default.
# When prompted for a passphrase, entering one adds a second layer of security, 
# but pressing Enter twice leaves it passwordless for automated scripts.
```

### Step 1b: Transfer the Public Key to the Pi
Your keypair consists of a private key (never share this) and a public key. The Pi needs your public key to recognize you. 

```bash
# On Linux/macOS, use the built-in copy utility:
ssh-copy-id -i ~/.ssh/id_ed25519.pub wannes@10.32.251.30

# On Windows (PowerShell), if ssh-copy-id is unavailable, run this equivalent:
# This reads your public key and appends it to the Pi's authorized_keys file.
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh wannes@10.32.251.30 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```
*Test the connection: Run `ssh wannes@10.32.251.30`. You should log in instantly without being asked for a password.*

### Step 1c: Disable Password Authentication (Run on the PI)
Now that the key works, we close the password loophole.

```bash
# Open the SSH daemon configuration file in a text editor
sudo nano /etc/ssh/sshd_config

# Find the line that says '#PasswordAuthentication yes' or 'PasswordAuthentication yes'
# Change it to exactly this (make sure to remove the '#' at the start):
PasswordAuthentication no

# Save and exit (Ctrl+O, Enter, Ctrl+X)

# Restart the SSH service to apply the lockdown
sudo systemctl restart ssh
```
Your Pi is now immune to password-guessing attacks.

---

## 2. Phase 2: Prerequisites (The Control Plane)

Now we utilize NetBird's hosted cloud to act as the handshake coordinator for our remote mesh.

1. Navigate to [app.netbird.io](https://app.netbird.io).
2. Sign in using your preferred Identity Provider (Google, Microsoft, GitHub, or Email).
3. Once logged in, you will be presented with your NetBird Admin Dashboard. Leave this tab open.

---

## 3. Phase 3: Raspberry Pi Installation (The WanOS Node)

While still SSH'd into your Raspberry Pi, execute the following commands to install the zero-trust mesh client.

### Step 3a: Run the Install Script
```bash
# Download and execute the official NetBird installation script.
# curl -fsSL : Fetches the script silently (-s) but shows errors (-f), follows redirects (-L).
# | sh       : Pipes the downloaded script directly into the shell for execution.
curl -fsSL [https://pkgs.netbird.io/install.sh](https://pkgs.netbird.io/install.sh) | sh
```

### Step 3b: Connect to the Mesh
Bring the NetBird daemon online and link it to your account.

```bash
# Bring the NetBird network interface up.
# This command will output an authentication URL directly in your terminal.
netbird up
```

**The Authentication Flow:**
1. The terminal will pause and display a URL (e.g., `https://login.netbird.io/device...`).
2. Copy that URL and paste it into the web browser on your laptop/desktop where you are logged into the NetBird dashboard.
3. Click "Confirm" in the browser. 
4. Return to your Raspberry Pi terminal. You will see a success message.

### Step 3c: Verify the Connection
```bash
# Displays the daemon status, your new 100.x.x.x IP address, 
# and the list of other connected peers (currently 0).
netbird status
```

---

## 4. Phase 4: Client Installation (Your Smartphone / Laptop)

To SSH into WanOS from a coffee shop, your remote device must also be in the mesh.

*   **For iOS / Android:** Download the "NetBird" app from the App Store or Google Play Store. Log in using the same Identity Provider account.
*   **For macOS / Windows:** Download the desktop client from the NetBird website and log in.

Once both devices are connected to NetBird, look at the NetBird app on your phone/laptop to find the Raspberry Pi's new static `100.x.x.x` IP address. 

You can now remotely configure your system securely from anywhere by running:
```bash
ssh wannes@100.x.x.x
```
*(Because your laptop holds the Ed25519 private key we made in Phase 1, the connection will authenticate automatically).*

---

## 5. Security Guardrails & Maintenance 

*   **Firewall Status:** You do *not* need to touch your home router. NetBird utilizes STUN/TURN (UDP hole punching) to establish the WireGuard connection outward. Your local network remains invisible.
*   **Auto-Start:** The script registers NetBird as a `systemd` service. If WanOS reboots after a power outage, NetBird will automatically start and reconnect in the background.

```bash
# If you ever need to manually restart the background service:
sudo netbird service restart

# To cleanly disconnect the Pi from the remote mesh:
netbird down
```

---

## 6. Architectural Alternative: Raw WireGuard

If you decide in the future that you do not want to rely on NetBird's centralized cloud servers (even just for the initial SSO handshake), the industry-standard fallback is **Raw WireGuard**.

*   **How it differs:** You completely remove the NetBird client. Instead, you install the `wireguard` kernel module directly via `apt`. You manually generate public/private keypairs using `wg genkey` and manually write a `/etc/wireguard/wg0.conf` file.
*   **The Trade-off:** Raw WireGuard operates purely peer-to-peer with zero third-party servers. However, it mandates that you log into your home router, configure Dynamic DNS (if your ISP rotates your IP), and explicitly open UDP Port 51820 to the public internet. 

Because WanOS is a critical infrastructure controller, starting with NetBird Cloud isolates your home network entirely from automated port scanners while keeping CPU overhead remarkably low.