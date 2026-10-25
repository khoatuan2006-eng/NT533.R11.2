"""Shared REST API helpers for NT533 Lab 2, questions 7 and 8.
Copy this file next to openstack_api15.py, nova.py, neutron.py and glance.py.
"""
import getpass
import ipaddress
import re
import time

import requests
from openstack_api15 import OpenStackAPI15
from nova import Nova
from neutron import Neutron
from glance import Glance

NET_NAME = "nhom15_net"
SUBNET_NAME = "nhom15_subnet"
LB_NAME = "nhom15_lb"
LISTENER_NAME = "nhom15_http_listener"
POOL_NAME = "nhom15_pool"
MONITOR_NAME = "nhom15_http_monitor"
VM_PREFIX = "nhom15_vm_"


def login():
    username = input("Tai khoan OpenStack: ").strip()
    password = getpass.getpass("Mat khau (khong hien thi): ")
    project_id = input("Project ID: ").strip()
    if not all((username, password, project_id)):
        raise ValueError("Phai nhap du tai khoan, mat khau va Project ID.")
    cloud = OpenStackAPI15(username, password, project_id)
    cloud.login()
    cloud.password = None  # Token already acquired; avoid retaining plain password.
    return cloud


def unique_name(resources, name, kind):
    matched = [r for r in resources if r.get("name") == name]
    if len(matched) > 1:
        raise RuntimeError(f"Co nhieu {kind} cung ten {name}: hay xu ly trung ten truoc.")
    return matched[0] if matched else None


def find_network_and_subnet(cloud):
    net = unique_name(Neutron(cloud).list_networks(), NET_NAME, "Network")
    if not net:
        raise RuntimeError(f"Khong tim thay Network {NET_NAME}. Kiem tra lai cau 5.")
    subs = [s for s in Neutron(cloud).list_subnets()
            if s.get("network_id") == net["id"] and s.get("name") == SUBNET_NAME]
    if len(subs) != 1:
        raise RuntimeError(f"Can dung 1 Subnet {SUBNET_NAME} thuoc {NET_NAME}, tim thay {len(subs)}.")
    sub = subs[0]
    print("Network:", net["name"], net["id"])
    print("Subnet :", sub["name"], sub.get("cidr"), sub["id"])
    return net, sub


class LBAPI:
    def __init__(self, cloud):
        self.cloud = cloud
        catalog = cloud.request("GET", cloud.identity_url + "/auth/catalog").get("catalog", [])
        entries = [s for s in catalog if s.get("type") in ("load-balancer", "loadbalancer")]
        if not entries:
            types = ", ".join(sorted({s.get("type", "?") for s in catalog}))
            raise RuntimeError(
                "Service Catalog khong co dich vu load-balancer (Octavia). "
                "Kiem tra Networks > Load Balancers va lien he GV/quan tri NC-Cloud "
                f"neu chua duoc cap dich vu. Service types hien co: {types}"
            )
        endpoints = entries[0].get("endpoints", [])
        endpoint = next((e for e in endpoints if e.get("interface") == "public"), None)
        if endpoint is None:
            endpoint = next((e for e in endpoints if e.get("interface") == "internal"), None)
        if endpoint is None:
            raise RuntimeError("Khong tim thay public/internal endpoint cho Octavia.")
        raw = endpoint["url"].replace("%(project_id)s", cloud.project_id).replace("{project_id}", cloud.project_id)
        raw = raw.rstrip("/")
        # Keystone catalogs may publish /, /v2, /v2.0 or /v2/lbaas.
        # Octavia accepts /v2 and /v2.0 as aliases. Never append the API
        # version twice, otherwise all calls fail with HTTP 404.
        if re.search(r"/v2(?:\.0)?/lbaas$", raw):
            self.url = raw
        elif re.search(r"/v2(?:\.0)?$", raw):
            self.url = raw + "/lbaas"
        else:
            self.url = raw + "/v2/lbaas"
        print("Octavia endpoint (Service Catalog):", self.url)

    def req(self, method, path, body=None):
        return self.cloud.request(method, self.url + path, body)

    def list_lbs(self):
        return self.req("GET", "/loadbalancers").get("loadbalancers", [])

    def get_lb(self, lb_id):
        return self.req("GET", f"/loadbalancers/{lb_id}")["loadbalancer"]

    def find_lb(self):
        return unique_name(self.list_lbs(), LB_NAME, "Load Balancer")

    def wait_lb(self, lb_id, timeout=1200):
        start = time.monotonic()
        last = None
        while time.monotonic() - start < timeout:
            lb = self.get_lb(lb_id)
            state = lb.get("provisioning_status")
            if state != last:
                print("Load Balancer provisioning_status:", state)
                last = state
            if state == "ACTIVE":
                return lb
            if state == "ERROR":
                raise RuntimeError("Load Balancer dang ERROR; mo NC-Cloud de xem chi tiet.")
            time.sleep(8)
        raise TimeoutError("Qua han cho Load Balancer ACTIVE. Kiem tra dashboard.")

    def get_pool(self):
        return unique_name(self.req("GET", "/pools").get("pools", []), POOL_NAME, "Pool")

    def list_members(self, pool_id):
        return self.req("GET", f"/pools/{pool_id}/members").get("members", [])

    def add_member(self, lb_id, pool_id, name, ip, subnet_id):
        ipaddress.ip_address(ip)
        old = [m for m in self.list_members(pool_id)
               if m.get("address") == ip and int(m.get("protocol_port", 0)) == 80]
        if old:
            print("Member da ton tai:", name, ip)
            return old[0]
        self.wait_lb(lb_id)
        member = self.req("POST", f"/pools/{pool_id}/members", {
            "member": {
                "name": name, "address": ip, "protocol_port": 80,
                "subnet_id": subnet_id, "admin_state_up": True
            }
        })["member"]
        print("Da them member:", name, ip)
        self.wait_lb(lb_id)
        return member

    def remove_member(self, lb_id, pool_id, member_id):
        self.wait_lb(lb_id)
        self.req("DELETE", f"/pools/{pool_id}/members/{member_id}")
        self.wait_lb(lb_id)


def active_vms(cloud):
    return [vm for vm in Nova(cloud).list_instances()
            if re.fullmatch(r"nhom15_vm_\d+", vm.get("name", ""))
            and vm.get("status") == "ACTIVE"]


def vm_private_ip(cloud, vm_id, net_id, subnet_id):
    ports = cloud.request("GET", cloud.network_url + "/ports?device_id=" + vm_id).get("ports", [])
    for p in ports:
        if p.get("network_id") != net_id:
            continue
        for fixed in p.get("fixed_ips", []):
            if fixed.get("subnet_id") == subnet_id:
                return fixed["ip_address"]
    raise RuntimeError(f"VM {vm_id} chua co fixed IP tren Subnet can su dung.")


def detect_fip(cloud, port_id):
    ips = cloud.request("GET", cloud.network_url + "/floatingips").get("floatingips", [])
    matches = [f for f in ips if f.get("port_id") == port_id]
    return matches[0]["floating_ip_address"] if matches else None


def ensure_lb_fip(cloud, vip_port_id):
    existing = detect_fip(cloud, vip_port_id)
    if existing:
        print("Floating IP cua Load Balancer da co:", existing)
        return existing
    networks = Neutron(cloud).list_networks()
    ext = next((n for n in networks if n.get("router:external") is True), None)
    if not ext:
        ext = next((n for n in networks if "public" in n.get("name", "").lower()), None)
    if ext is None:
        print("Khong tim thay External Network: chi truy cap VIP trong mang noi bo.")
        return None
    # Never reassign VM_1's existing FIP: allocate a separate FIP for the LB.
    fip = cloud.request("POST", cloud.network_url + "/floatingips", {
        "floatingip": {"floating_network_id": ext["id"]}
    })["floatingip"]
    try:
        cloud.request("PUT", cloud.network_url + "/floatingips/" + fip["id"], {
            "floatingip": {"port_id": vip_port_id}
        })
    except requests.RequestException:
        print("Khong gan duoc Floating IP vao LB; IP vua cap phat van dang chua gan:", fip["id"])
        print("Can kiem tra/thu hoi FIP chua gan trong NC-Cloud de tranh ton quota.")
        raise
    print("Floating IP cua Load Balancer:", fip["floating_ip_address"])
    return fip["floating_ip_address"]


def print_status(cloud, api):
    lb = api.find_lb()
    if not lb:
        print("Chua co Load Balancer", LB_NAME)
        return
    lb = api.get_lb(lb["id"])
    print("\nLOAD BALANCER", lb["name"])
    print("ID:", lb["id"])
    print("VIP private:", lb.get("vip_address"))
    print("Floating IP:", detect_fip(cloud, lb["vip_port_id"]) if lb.get("vip_port_id") else "N/A")
    print("Provisioning:", lb.get("provisioning_status"), "Operating:", lb.get("operating_status"))
    pool = api.get_pool()
    if not pool:
        print("Chua co Pool", POOL_NAME)
        return
    print("Pool:", pool["name"], pool["id"])
    print("THANH VIEN:")
    for m in api.list_members(pool["id"]):
        print(f" - {m.get('name')} {m.get('address')}:{m.get('protocol_port')} "
              f"provisioning={m.get('provisioning_status')} operating={m.get('operating_status')}")
