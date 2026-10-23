import base64
import time
import requests
from openstack_api15 import OpenStackAPI15
from nova import Nova
from glance import Glance
from neutron import Neutron

# Đăng nhập
username = input("Tai khoan: ")
password = input("Mat khau: ")
project_id = input("Project ID: ")

cloud = OpenStackAPI15(username, password, project_id)
cloud.login()

nova = Nova(cloud)
glance = Glance(cloud)
neutron = Neutron(cloud)

VM_NAME = "nhom15_vm_1"
NET_NAME = "nhom15_net"

# 1. Tìm Network nhóm 15
print("\nTIM NETWORK")
target_net = None
networks = neutron.list_networks()
for n in networks:
    if n["name"] == NET_NAME:
        target_net = n
        break

if not target_net:
    print(f"Khong tim thay {NET_NAME}. Vui long chon network sau:")
    for idx, n in enumerate(networks):
        print(f"[{idx + 1}]", n["name"], f"({n['id']})")
    choice = int(input("Chon so thu tu Network: ")) - 1
    target_net = networks[choice]

print("Su dung Network:", target_net["name"], f"({target_net['id']})")

# 2. Liệt kê và chọn Flavor
print("\nDANH SACH FLAVOR")
flavors = nova.list_flavors()
default_flavor_idx = 0
for idx, f in enumerate(flavors):
    print(f"[{idx + 1}]", f["name"], f["vcpus"], "CPU", f["ram"], "MB RAM", f["disk"], "GB Disk")
    if "small" in f["name"].lower() or "ds1g" in f["name"].lower():
        default_flavor_idx = idx

flavor_input = input(f"Chon Flavor (mac dinh [{default_flavor_idx + 1}]): ").strip()
selected_flavor = flavors[int(flavor_input) - 1] if flavor_input else flavors[default_flavor_idx]
print("Chon Flavor:", selected_flavor["name"])

# 3. Liệt kê và chọn Image
print("\nDANH SACH IMAGE")
images = glance.list_images()
active_images = [img for img in images if img.get("status") == "active"]
if not active_images:
    active_images = images

default_img_idx = 0
for idx, img in enumerate(active_images):
    print(f"[{idx + 1}]", img["name"], img.get("status", ""))
    if "ubuntu" in img["name"].lower() or "debian" in img["name"].lower():
        default_img_idx = idx

image_input = input(f"Chon Image (mac dinh [{default_img_idx + 1}]): ").strip()
selected_image = active_images[int(image_input) - 1] if image_input else active_images[default_img_idx]
print("Chon Image:", selected_image["name"])

vol_input = input("Dung luong volume (GB, mac dinh 20): ").strip()
volume_size = int(vol_input) if vol_input else 20

# 4. Chuẩn bị User Data script cài đặt dịch vụ Web
user_script = r"""#!/bin/bash
IP_ADDR=$(hostname -I | awk '{print $1}')
if [ -z "$IP_ADDR" ]; then
    IP_ADDR=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n1 || echo "127.0.0.1")
fi

if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y apache2
    cat <<'EOF' > /var/www/html/index.html
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Lab 2 - OpenStack API - Nhom 15</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f6f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; }
        h1 { color: #1e3c72; margin-bottom: 8px; }
        h2 { color: #2b6cb0; margin-top: 0; }
        .ip-box { font-size: 22px; color: #2563eb; background: #eff6ff; padding: 12px 24px; border-radius: 8px; font-weight: bold; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="card">
        <h1>BÀI THỰC HÀNH LAB 2 - OPENSTACK API</h1>
        <h2>THÔNG TIN NHÓM: NHÓM 15</h2>
        <div class="ip-box">IP MÁY ẢO: REPLACE_IP</div>
        <p>Triển khai tự động bằng OpenStack User Data Script</p>
    </div>
</body>
</html>
EOF
    sed -i "s/REPLACE_IP/$IP_ADDR/g" /var/www/html/index.html
    systemctl restart apache2
    systemctl enable apache2
else
    mkdir -p /opt/web
    cat <<'EOF' > /opt/web/index.html
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Nhom 15</title></head>
<body style="font-family: Arial; text-align: center; margin-top: 50px;">
    <h1>BÀI THỰC HÀNH LAB 2 - OPENSTACK API</h1>
    <h2>THÔNG TIN NHÓM: NHÓM 15</h2>
    <p style="font-size: 22px; color: blue;">IP MÁY ẢO: REPLACE_IP</p>
</body>
</html>
EOF
    sed -i "s/REPLACE_IP/$IP_ADDR/g" /opt/web/index.html
    nohup python3 -m http.server 80 --directory /opt/web > /dev/null 2>&1 &
fi
"""

user_data_b64 = base64.b64encode(user_script.encode("utf-8")).decode("utf-8")

# 5. Tạo máy ảo
print("\nTAO MAY AO")
server_data = {
    "server": {
        "name": VM_NAME,
        "flavorRef": selected_flavor["id"],
        "networks": [
            {"uuid": target_net["id"]}
        ],
        "user_data": user_data_b64,
        "security_groups": [
            {"name": "default"}
        ],
        "block_device_mapping_v2": [
            {
                "boot_index": 0,
                "uuid": selected_image["id"],
                "source_type": "image",
                "destination_type": "volume",
                "volume_size": volume_size,
                "delete_on_termination": True
            }
        ]
    }
}

server_res = cloud.request("POST", cloud.compute_url + "/servers", server_data)["server"]
server_id = server_res["id"]
print("Da gui yeu cau tao may ao:", VM_NAME, f"({server_id})")

# Chờ máy ảo khởi động xong (ACTIVE)
print("Dang cho may ao ACTIVE...", end="", flush=True)
vm_status = "BUILD"
for _ in range(36):
    time.sleep(5)
    print(".", end="", flush=True)
    vm_info = cloud.request("GET", f"{cloud.compute_url}/servers/{server_id}")["server"]
    vm_status = vm_info["status"]
    if vm_status in ("ACTIVE", "ERROR"):
        break

print(" [", vm_status, "]")

# 6. Cấp phát và gắn Floating IP
print("\nGAN FLOATING IP")
ext_net = None
for n in networks:
    if n.get("router:external"):
        ext_net = n
        break

if not ext_net:
    for n in networks:
        name = n.get("name", "").lower()
        if "public" in name or "external" in name or "ext" in name:
            ext_net = n
            break

fip_data = cloud.request(
    "POST",
    cloud.network_url + "/floatingips",
    {"floatingip": {"floating_network_id": ext_net["id"]}}
)["floatingip"]

floating_ip = fip_data["floating_ip_address"]
floating_ip_id = fip_data["id"]
print("Cap phat Floating IP:", floating_ip)

# Lấy Port của máy ảo và gán Floating IP
ports_data = cloud.request("GET", f"{cloud.network_url}/ports?device_id={server_id}")["ports"]
if ports_data:
    vm_port_id = ports_data[0]["id"]
    fixed_ip = ports_data[0]["fixed_ips"][0]["ip_address"] if ports_data[0].get("fixed_ips") else "N/A"
    cloud.request(
        "PUT",
        f"{cloud.network_url}/floatingips/{floating_ip_id}",
        {"floatingip": {"port_id": vm_port_id}}
    )
    print("Gan Floating IP vao may ao thanh cong!")
else:
    fixed_ip = "N/A"
    print("Khong tim thay port cua may ao de gan Floating IP.")

print("\nHOAN THANH CÂU 6 (NHOM 15)!")
print("May ao:", VM_NAME, f"({server_id})")
print("Trang thai:", vm_status)
print("IP Private:", fixed_ip)
print("Floating IP:", floating_ip)
print(f"Truy cap Web: http://{floating_ip}")
