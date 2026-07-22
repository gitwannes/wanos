# WanOS: NGINX Reverse Proxy & SSL Migration Guide

This document outlines the exact steps to securely migrate WanOS behind an NGINX reverse proxy. This allows to serve encrypted HTTPS on port 443, automatically redirect legacy port 8000 traffic, and protect the Python Uvicorn engine from direct external access.

---

## [ ] Step 1: Install NGINX & Generate SSL Certificates
First, we need to install the web server and generate a self-signed certificate that will encrypt the traffic for the next 10 years.

```bash
# Update the package manager and install NGINX
sudo apt update && sudo apt install nginx -y

# Generate a 10-year self-signed RSA certificate
# We place the key in /private/ and the certificate in /certs/
sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /etc/ssl/private/wanos.key \
  -out /etc/ssl/certs/wanos.crt \
  -subj "/C=BE/ST=Flanders/L=Ghent/O=WanOS/CN=wanos.local"
```

## [ ] Step 2: Create the NGINX Configuration File
We need to tell NGINX how to route traffic, handle the SSL certificates, and—most importantly—how to keep the Server-Sent Events (SSE) stream open for the Alpine.js frontend.

```bash
# Open a new configuration file in a text editor
sudo vi /etc/nginx/sites-available/wanos
```

**Paste the following configuration into the file:**

```nginx
# ==============================================================================
# 1. LEGACY BACKWARD COMPATIBILITY (Port 8000)
# ==============================================================================
# If any old tablets or bookmarks hit port 8000, NGINX intercepts it 
# and instantly forces a 301 redirect to the secure 443 port.
server {
    listen 8000;
    server_name _;
    return 301 https://$host$request_uri;
}

# ==============================================================================
# 2. STANDARD HTTP REDIRECT (Port 80)
# ==============================================================================
# Forces standard HTTP traffic to upgrade to HTTPS automatically.
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

# ==============================================================================
# 3. MAIN WANOS HTTPS SERVER (Port 443)
# ==============================================================================
server {
    listen 443 ssl http2;
    server_name _;

    # Point to the self-generated SSL keys
    ssl_certificate /etc/ssl/certs/wanos.crt;
    ssl_certificate_key /etc/ssl/private/wanos.key;

    location / {
        # THE REVERSE PROXY
        # NGINX takes the 443 traffic and safely pipes it to Uvicorn on localhost
        proxy_pass [http://127.0.0.1:8080](http://127.0.0.1:8080);
        
        # Pass the original client IPs and Headers through to WanOS
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # CRITICAL FOR WANOS SSE STREAM (Server-Sent Events)
        # NGINX buffers HTTP traffic by default. If we don't turn this off, 
        # the live telemetry stream to the UI will freeze.
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
        
        # Prevent NGINX from dropping the SSE connection if no data is sent 
        # (The ping payload in main.py also helps prevent this, but this is a failsafe)
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

## [ ] Step 3: Enable the Configuration & Restart NGINX
Now we link the configuration file to the "enabled" folder, remove the default NGINX welcome page, and restart the service to apply the changes.

```bash
# Create a symbolic link to enable the site
sudo ln -s /etc/nginx/sites-available/wanos /etc/nginx/sites-enabled/

# Remove the default NGINX placeholder site
sudo rm /etc/nginx/sites-enabled/default

# Verify the NGINX syntax is correct before restarting
sudo nginx -t

# Restart NGINX to apply the new proxy rules
sudo systemctl restart nginx
```

## [ ] Step 4: Lock Down Uvicorn (Modify `wanos.service`)
Right now, Uvicorn is bound to `0.0.0.0:8000`. We need to lock it to `127.0.0.1:8080` so that it ONLY accepts traffic coming from the NGINX proxy.

```bash
# Edit the Systemd service file
sudo vi /etc/systemd/system/wanos.service
```

**Find the `ExecStart` line and modify the host and port arguments:**

```ini
# Force Uvicorn to listen ONLY to internal localhost traffic on port 8080
ExecStart=/home/wannes/wanos/wanos_venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8080
# NOTE: --reload is only for development: it forces Uvicorn to constantly monitor the hard drive for file changes and restart the engine if it sees one
```

## [ ] Step 5: Reload Systemd & Restart WanOS
Tell the Linux kernel that the service file has changed, and bounce WanOS.

```bash
# Reload the systemd daemon to read the updated wanos.service file
sudo systemctl daemon-reload

# Restart WanOS
sudo systemctl restart wanos.service

# Verify WanOS is running securely on 127.0.0.1:8080
sudo systemctl status wanos.service
```

### Completion
Navigate to `https://10.32.251.30` and the UI will load securely.
Any requests to `http://10.32.251.30:8000` will be instantly redirected to the secure portal.