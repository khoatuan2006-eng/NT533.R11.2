import requests
from openstack_api15 import OpenStackAPI15
from neutron import Neutron

# Đăng nhập
username = input("Tai khoan: ").strip()
password = input("Mat khau: ").strip()
project_id = input("Project ID: ").strip()

cloud = OpenStackAPI15(username, password, project_id)

def check_login_diagnostics(cloud):
    try:
        cloud.login()
        return True
    except requests.exceptions.HTTPError:
        pass

    # Thử biến thể domain id: "default"
    payload_id = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": cloud.username,
                        "domain": {"id": "default"},
                        "password": cloud.password
                    }
                }
            },
            "scope": {"project": {"id": cloud.project_id}}
        }
    }
    r1 = requests.post(cloud.identity_url + "/auth/tokens", json=payload_id, timeout=30)
    if r1.status_code == 201:
        cloud.headers = {"X-Auth-Token": r1.headers["X-Subject-Token"]}
        print("Dang nhap thanh cong!")
        return True

    # Thử unscoped để kiểm tra riêng tài khoản & mật khẩu
    payload_unscoped = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": cloud.username,
                        "domain": {"name": "Default"},
                        "password": cloud.password
                    }
                }
            }
        }
    }
    r2 = requests.post(cloud.identity_url + "/auth/tokens", json=payload_unscoped, timeout=30)
    if r2.status_code == 401:
        print("\n" + "=" * 50)
        print("❌ KẾT QUẢ KIỂM TRA: MẬT KHẨU HOẶC TÀI KHOẢN KHÔNG ĐÚNG!")
        print("Máy chủ từ chối xác thực tài khoản và mật khẩu bạn vừa nhập.")
        print("Gợi ý: Kiểm tra xem trình duyệt bạn có lưu mật khẩu tự động không,")
        print("hoặc kiểm tra lại chữ hoa/thường trong mật khẩu.")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("⚠️ KẾT QUẢ KIỂM TRA: TÀI KHOẢN VÀ MẬT KHẨU CHÍNH XÁC!")
        print(f"Nhưng máy chủ từ chối quyền vào Project ID: '{cloud.project_id}'.")
        print("Hãy vào tab 'API Access' trên web để copy lại đúng Project ID.")
        print("=" * 50)
    return False

if not check_login_diagnostics(cloud):
    exit(1)

neutron = Neutron(cloud)

NET_NAME = "nhom15_net"
SUBNET_NAME = "nhom15_subnet"
CIDR = "192.168.15.0/24"
GATEWAY_IP = "192.168.15.1"
ROUTER_NAME = "nhom15_router"

# 1. Tìm External Network
print("\nTIM EXTERNAL NETWORK")
external_net_id = None
networks = neutron.list_networks()
for n in networks:
    if n.get("router:external"):
        external_net_id = n["id"]
        print("External Network:", n["name"], f"({n['id']})")
        break

if not external_net_id:
    for n in networks:
        name = n.get("name", "").lower()
        if "public" in name or "external" in name or "ext" in name:
            external_net_id = n["id"]
            print("External Network:", n["name"], f"({n['id']})")
            break

# 2. Thiết lập Network nhóm 15
print("\nTHIET LAP NETWORK")
nhom_net = None
for n in neutron.list_networks():
    if n["name"] == NET_NAME:
        nhom_net = n
        print("Network da ton tai:", nhom_net["name"], f"({nhom_net['id']})")
        break

if not nhom_net:
    nhom_net = neutron.create_network(NET_NAME)
    print("Tao Network thanh cong:", nhom_net["name"], f"({nhom_net['id']})")

# 3. Thiết lập Subnet nhóm 15
print("\nTHIET LAP SUBNET")
nhom_subnet = None
for s in neutron.list_subnets():
    if s["name"] == SUBNET_NAME or (s["network_id"] == nhom_net["id"] and s["cidr"] == CIDR):
        nhom_subnet = s
        print("Subnet da ton tai:", nhom_subnet["name"], nhom_subnet["cidr"], f"({nhom_subnet['id']})")
        break

if not nhom_subnet:
    subnet_data = {
        "subnet": {
            "name": SUBNET_NAME,
            "network_id": nhom_net["id"],
            "ip_version": 4,
            "cidr": CIDR,
            "gateway_ip": GATEWAY_IP,
            "dns_nameservers": ["8.8.8.8", "1.1.1.1"]
        }
    }
    res = cloud.request("POST", cloud.network_url + "/subnets", subnet_data)
    nhom_subnet = res["subnet"]
    print("Tao Subnet thanh cong:", nhom_subnet["name"], nhom_subnet["cidr"], f"({nhom_subnet['id']})")

# 4. Thiết lập Router (External Gateway + Subnet Interface)
print("\nTHIET LAP ROUTER")
nhom_router = None
for r in neutron.list_routers():
    if r["name"] == ROUTER_NAME:
        nhom_router = r
        print("Router da ton tai:", nhom_router["name"], f"({nhom_router['id']})")
        break

if not nhom_router:
    router_data = {
        "router": {
            "name": ROUTER_NAME,
            "admin_state_up": True,
            "external_gateway_info": {
                "network_id": external_net_id
            } if external_net_id else None
        }
    }
    nhom_router = cloud.request("POST", cloud.network_url + "/routers", router_data)["router"]
    print("Tao Router thanh cong:", nhom_router["name"], f"({nhom_router['id']})")

# Kết nối Interface Router với Subnet
try:
    cloud.request(
        "PUT",
        f"{cloud.network_url}/routers/{nhom_router['id']}/add_router_interface",
        {"subnet_id": nhom_subnet["id"]}
    )
    print("Da noi Router voi Subnet:", SUBNET_NAME)
except requests.RequestException:
    print("Interface Subnet da duoc noi truoc do hoac da san sang.")

# 5. Cấu hình Security Group (Mở HTTP port 80, ICMP, SSH port 22)
print("\nCAU HINH SECURITY GROUP")
res_sg = cloud.request("GET", cloud.network_url + "/security-groups")
secgroups = res_sg.get("security_groups") or res_sg.get("security-groups") or []
default_sg = None
for sg in secgroups:
    if sg.get("name") == "default":
        default_sg = sg
        break

if default_sg:
    print("Security Group:", default_sg["name"], f"({default_sg['id']})")
    rules = [
        {"desc": "HTTP", "protocol": "tcp", "port": 80},
        {"desc": "SSH", "protocol": "tcp", "port": 22},
        {"desc": "ICMP", "protocol": "icmp", "port": None}
    ]

    for item in rules:
        rule_data = {
            "security_group_rule": {
                "direction": "ingress",
                "ethertype": "IPv4",
                "protocol": item["protocol"],
                "security_group_id": default_sg["id"],
                "remote_ip_prefix": "0.0.0.0/0"
            }
        }
        if item["port"] is not None:
            rule_data["security_group_rule"]["port_range_min"] = item["port"]
            rule_data["security_group_rule"]["port_range_max"] = item["port"]

        try:
            cloud.request("POST", cloud.network_url + "/security-group-rules", rule_data)
            print("Da mo rule:", item["desc"])
        except requests.RequestException:
            print("Rule da ton tai:", item["desc"])

print("\nHOAN THANH THIET LAP MANG CÂU 5 (NHOM 15)!")
