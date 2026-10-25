#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y apache2
IP_ADDR=$(hostname -I | awk '{print $1}')
if [ -z "$IP_ADDR" ]; then IP_ADDR="unknown"; fi
cat > /var/www/html/index.html <<'EOF'
<!doctype html>
<html lang="vi"><head><meta charset="UTF-8"><title>Lab 2 - OpenStack API - Nhom 15</title>
<style>body{font-family:Arial;background:#f4f6f9;margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh}.card{background:#fff;border-radius:12px;padding:36px;text-align:center;box-shadow:0 4px 16px #0002}h1{color:#1e3c72}h2{color:#2b6cb0}.ip{font-size:22px;font-weight:bold;color:#2563eb}</style></head>
<body><div class="card"><h1>BÀI THỰC HÀNH LAB 2 - OPENSTACK API</h1>
<h2>THÔNG TIN NHÓM: NHÓM 15</h2>
<p class="ip">IP MÁY ẢO: REPLACE_IP</p>
<p>Web Server duoc cai dat tu User Data</p></div></body></html>
EOF
sed -i "s/REPLACE_IP/$IP_ADDR/g" /var/www/html/index.html
systemctl enable apache2
systemctl restart apache2
