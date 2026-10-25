"""Question 7: Create Octavia LB + listener + pool + health monitor via REST API.
Usage: py cau7.py setup | status | test 12
"""
import re
import sys
import time

import requests
from lab78_common import (
    LBAPI, LB_NAME, LISTENER_NAME, POOL_NAME, MONITOR_NAME,
    active_vms, detect_fip, ensure_lb_fip, find_network_and_subnet,
    login, print_status, unique_name, vm_private_ip,
)


def setup(cloud, api):
    net, sub = find_network_and_subnet(cloud)
    lb = api.find_lb()
    if not lb:
        print("Tao Load Balancer:", LB_NAME)
        lb = api.req("POST", "/loadbalancers", {
            "loadbalancer": {"name": LB_NAME, "vip_subnet_id": sub["id"], "admin_state_up": True}
        })["loadbalancer"]
    else:
        print("Su dung Load Balancer da ton tai:", lb["id"])
        if lb.get("vip_subnet_id") != sub["id"]:
            raise RuntimeError("LB hien co dang dung Subnet khac. Khong thay doi tu dong.")
    lb = api.wait_lb(lb["id"])

    listeners = api.req("GET", "/listeners").get("listeners", [])
    # Tìm theo tên LISTENER_NAME hoặc tìm listener cổng 80 trên chính Load Balancer này
    listener = next((l for l in listeners if l.get("name") == LISTENER_NAME), None)
    if not listener:
        listener = next((l for l in listeners if l.get("protocol_port") == 80 and any(
            lb_ref.get("id") == lb["id"] for lb_ref in l.get("loadbalancers", [])
        )), None)
    if not listener:
        print("Tao Listener HTTP:80")
        listener = api.req("POST", "/listeners", {
            "listener": {
                "name": LISTENER_NAME, "loadbalancer_id": lb["id"],
                "protocol": "HTTP", "protocol_port": 80, "admin_state_up": True
            }
        })["listener"]
    else:
        print("Listener da ton tai:", listener.get("name"), listener["id"])
    api.wait_lb(lb["id"])

    pool = api.get_pool()
    if not pool:
        print("Tao Pool ROUND_ROBIN")
        pool = api.req("POST", "/pools", {
            "pool": {
                "name": POOL_NAME, "protocol": "HTTP", "lb_algorithm": "ROUND_ROBIN",
                "listener_id": listener["id"], "admin_state_up": True
            }
        })["pool"]
    else:
        print("Pool da ton tai:", pool["id"])
    api.wait_lb(lb["id"])

    monitors = api.req("GET", "/healthmonitors").get("healthmonitors", [])
    # Pool có thể chứa healthmonitor_id hoặc monitor có pools: [{'id': ...}]
    pool_hm_id = pool.get("healthmonitor_id")
    monitor = None
    if pool_hm_id:
        monitor = next((m for m in monitors if m.get("id") == pool_hm_id), {"id": pool_hm_id})
    if not monitor:
        monitor = next((m for m in monitors if any(p.get("id") == pool["id"] for p in m.get("pools", []))
                        or m.get("pool_id") == pool["id"]
                        or m.get("name") == MONITOR_NAME), None)
    if not monitor:
        print("Tao Health Monitor HTTP GET /")
        try:
            api.req("POST", "/healthmonitors", {
                "healthmonitor": {
                    "name": MONITOR_NAME, "pool_id": pool["id"], "type": "HTTP",
                    "delay": 5, "timeout": 3, "max_retries": 3,
                    "url_path": "/", "expected_codes": "200", "admin_state_up": True
                }
            })
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 409:
                print("Pool da co Health Monitor san (bo qua tao moi).")
            else:
                raise
    else:
        print("Health Monitor da ton tai:", monitor["id"])
    api.wait_lb(lb["id"])

    vms = active_vms(cloud)
    print("So VM nhom15 dang ACTIVE:", len(vms))
    if not vms:
        print("Chua co VM ACTIVE. Kiem tra cau 6 va chay lai 'py cau7.py setup'.")
    for vm in vms:
        ip = vm_private_ip(cloud, vm["id"], net["id"], sub["id"])
        api.add_member(lb["id"], pool["id"], vm["name"], ip, sub["id"])

    lb = api.get_lb(lb["id"])
    print("\nVIP noi bo:", lb.get("vip_address"))
    if lb.get("vip_port_id"):
        try:
            ip = ensure_lb_fip(cloud, lb["vip_port_id"])
            if ip:
                print("Truy cap HTTP Load Balancer: http://" + ip)
        except requests.RequestException as exc:
            print("Khong tao/gan duoc Floating IP (kiem tra quota/quyen):", exc)
            print("Load Balancer van ton tai voi VIP noi bo:", lb.get("vip_address"))
    print("\nHOAN THANH CAU 7 - CAN KIEM TRA OPERATING_STATUS ONLINE")
    print_status(cloud, api)


def test(cloud, api, count):
    lb = api.find_lb()
    if not lb:
        raise RuntimeError("Chua co LB. Chay: py cau7.py setup")
    url_ip = detect_fip(cloud, lb["vip_port_id"]) if lb.get("vip_port_id") else None
    if not url_ip:
        print("LB chua co Floating IP, chua the test tu may tinh ca nhan.")
        print("VIP private:", lb.get("vip_address"))
        return
    url = "http://" + url_ip + "/"
    seen = {}
    print("Kiem tra", url, "voi", count, "HTTP requests (moi request la ket noi moi)")
    for i in range(count):
        try:
            r = requests.get(url, timeout=15, headers={"Connection": "close", "Cache-Control": "no-cache"})
            r.encoding = "utf-8"
            match = re.search(r"class=[\"']ip-box[\"']>\s*IP[^:]*:\s*((?:\d{1,3}\.){3}\d{1,3})", r.text, re.IGNORECASE)
            if not match:
                match = re.search(r"IP[^<:]*:\s*((?:\d{1,3}\.){3}\d{1,3})", r.text, re.IGNORECASE)
            if not match:
                match = re.search(r"(192\.168\.1\.\d+)", r.text)
            backend = match.group(1) if match else "khong_doc_duoc_IP_trang_web"
            seen[backend] = seen.get(backend, 0) + 1
            print(f"[{i+1:02}] HTTP {r.status_code}: {backend}")
        except requests.RequestException as exc:
            print(f"[{i+1:02}] LOI:", exc)
        time.sleep(0.4)
    print("Thong ke so yeu cau theo IP Web Server:", seen)
    print("Luu y: Round Robin va health checking phai duoc xac nhan boi cac member ONLINE.")


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command not in ("setup", "status", "test"):
        raise ValueError("Cu phap: py cau7.py setup | status | test 12")
    cloud = login()
    api = LBAPI(cloud)
    if command == "setup":
        setup(cloud, api)
    elif command == "status":
        print_status(cloud, api)
    else:
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 12
        if not 1 <= count <= 100:
            raise ValueError("So request phai trong khoang 1..100")
        test(cloud, api, count)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, TimeoutError, requests.RequestException) as exc:
        print("\nLOI:", exc)
        sys.exit(1)
