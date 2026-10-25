"""Question 8: Scale VM count and auto-register/unregister from Octavia Pool.
Usage: py cau8.py scale 2 | scale 1 | status
"""
import base64
from pathlib import Path
import re
import sys
import time

import requests
from lab78_common import (
    LBAPI, POOL_NAME, VM_PREFIX, find_network_and_subnet,
    login, print_status, vm_private_ip,
)
from nova import Nova
from glance import Glance

FLAVOR_NAME = "gp.tiny-1c"
IMAGE_NAME = "Ubuntu 22.04"
VOLUME_GB = 20


def get_managed_vms(cloud):
    result = {}
    for vm in Nova(cloud).list_instances():
        m = re.fullmatch(r"nhom15_vm_(\d+)", vm.get("name", ""))
        if not m:
            continue
        index = int(m.group(1))
        if index in result:
            raise RuntimeError(f"Trung ten VM {vm['name']}; phai xu ly trung ten truoc.")
        if vm["status"] != "ACTIVE":
            raise RuntimeError(f"VM {vm['name']} dang {vm['status']} - doi/xu ly truoc khi scale.")
        result[index] = vm
    return result


def choose_flavor_image(cloud):
    flavor = next((f for f in Nova(cloud).list_flavors() if f.get("name") == FLAVOR_NAME), None)
    image = next((i for i in Glance(cloud).list_images()
                  if i.get("name") == IMAGE_NAME and i.get("status") == "active"), None)
    if not flavor:
        raise RuntimeError(f"Khong tim thay Flavor '{FLAVOR_NAME}' - sua FLAVOR_NAME trong cau8.py.")
    if not image:
        raise RuntimeError(f"Khong tim thay Image active '{IMAGE_NAME}' - sua IMAGE_NAME trong cau8.py.")
    print("Flavor:", flavor["name"], "| Image:", image["name"], "| Volume:", VOLUME_GB, "GB")
    return flavor, image


def wait_vm(cloud, vm_id, timeout=900):
    start = time.monotonic()
    last = None
    while time.monotonic() - start < timeout:
        vm = cloud.request("GET", cloud.compute_url + "/servers/" + vm_id)["server"]
        state = vm.get("status")
        if state != last:
            print("VM status:", state)
            last = state
        if state == "ACTIVE":
            return vm
        if state == "ERROR":
            raise RuntimeError(f"VM {vm_id} ERROR. Kiem tra quota va NC-Cloud console.")
        time.sleep(8)
    raise TimeoutError(f"Qua han cho VM {vm_id} ACTIVE.")


def create_vm(cloud, vm_name, net_id, flavor, image):
    userdata = Path(__file__).with_name("web_userdata.sh").read_text(encoding="utf-8")
    userdata_b64 = base64.b64encode(userdata.encode("utf-8")).decode("ascii")
    payload = {
        "server": {
            "name": vm_name,
            "flavorRef": flavor["id"],
            "networks": [{"uuid": net_id}],
            "user_data": userdata_b64,
            "security_groups": [{"name": "default"}],
            "block_device_mapping_v2": [{
                "boot_index": 0,
                "uuid": image["id"],
                "source_type": "image",
                "destination_type": "volume",
                "volume_size": VOLUME_GB,
                "delete_on_termination": True,
            }],
        }
    }
    vm = cloud.request("POST", cloud.compute_url + "/servers", payload)["server"]
    print("Da gui POST /servers:", vm_name, vm["id"])
    wait_vm(cloud, vm["id"])
    print("VM ACTIVE. Luat Health Monitor se kiem tra Web sau khi cloud-init cai Apache.")
    return vm


def sync_existing_members(cloud, lbapi, lb, pool, net, sub):
    vms = get_managed_vms(cloud)
    for vm in vms.values():
        ip = vm_private_ip(cloud, vm["id"], net["id"], sub["id"])
        lbapi.add_member(lb["id"], pool["id"], vm["name"], ip, sub["id"])
    return vms


def delete_vm(cloud, lbapi, lb, pool, net, sub, vm):
    if vm["name"] == VM_PREFIX + "1":
        raise RuntimeError("Khong duoc xoa nhom15_vm_1 (VM goc cua cau 6).")
    ip = vm_private_ip(cloud, vm["id"], net["id"], sub["id"])
    matches = [m for m in lbapi.list_members(pool["id"])
               if m.get("address") == ip and int(m.get("protocol_port", 0)) == 80]
    for m in matches:
        print("Go member khoi Load Balancer:", vm["name"], ip)
        lbapi.remove_member(lb["id"], pool["id"], m["id"])
    print("Xoa VM:", vm["name"], vm["id"])
    cloud.request("DELETE", cloud.compute_url + "/servers/" + vm["id"])
    start = time.monotonic()
    while time.monotonic() - start < 600:
        time.sleep(7)
        try:
            cloud.request("GET", cloud.compute_url + "/servers/" + vm["id"])
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                print("Xoa thanh cong:", vm["name"])
                return
            raise
    raise TimeoutError("Da gui xoa VM nhung chua xac nhan duoc DELETE hoan tat.")


def scale(cloud, lbapi, target):
    if not (1 <= target <= 5):
        raise ValueError("Chi cho phep target 1..5 (van phai phu hop quota).")
    net, sub = find_network_and_subnet(cloud)
    lb = lbapi.find_lb()
    pool = lbapi.get_pool()
    if not lb or not pool:
        raise RuntimeError("Chua co LB/Pool. Hay chay 'py cau7.py setup' truoc.")
    lbapi.wait_lb(lb["id"])
    vms = get_managed_vms(cloud)
    if 1 not in vms:
        raise RuntimeError("Khong tim thay nhom15_vm_1 ACTIVE; kiem tra cau 6 truoc.")
    print("So luong VM hien tai:", len(vms), "| Muc tieu:", target)
    if len(vms) == target:
        print("Khong can tao/xoa VM; dong bo lai Pool.")
        sync_existing_members(cloud, lbapi, lb, pool, net, sub)
        print_status(cloud, lbapi)
        return

    if len(vms) < target:
        # Register already existing backend(s) first.
        sync_existing_members(cloud, lbapi, lb, pool, net, sub)
        flavor, image = choose_flavor_image(cloud)
        while len(vms) < target:
            n = next(i for i in range(2, 1000) if i not in vms)
            name = VM_PREFIX + str(n)
            vm = create_vm(cloud, name, net["id"], flavor, image)
            ip = vm_private_ip(cloud, vm["id"], net["id"], sub["id"])
            lbapi.add_member(lb["id"], pool["id"], name, ip, sub["id"])
            vms[n] = vm
            print("Da scale out:", name, ip)
    else:
        to_delete = sorted([n for n in vms if n != 1], reverse=True)[:len(vms)-target]
        if len(to_delete) != len(vms)-target:
            raise RuntimeError("Khong the giam them vi VM1 duoc bao ve.")
        print("Can xoa nhung VM:", ", ".join(vms[n]["name"] for n in to_delete))
        answer = input("Nhap XOA de xac nhan xoa vinh vien VM nay: ").strip()
        if answer != "XOA":
            print("Da huy yeu cau scale down, khong xoa tai nguyen.")
            return
        for n in to_delete:
            delete_vm(cloud, lbapi, lb, pool, net, sub, vms[n])
        sync_existing_members(cloud, lbapi, lb, pool, net, sub)

    print("\nHOAN THANH SCALE. Cho Health Monitor chuyen member sang ONLINE.")
    print_status(cloud, lbapi)


def main():
    if len(sys.argv) < 2:
        raise ValueError("Cu phap: py cau8.py status | scale 2 | scale 1")
    command = sys.argv[1]
    if command not in ("scale", "status"):
        raise ValueError("Cu phap: py cau8.py status | scale 2 | scale 1")
    if command == "scale" and len(sys.argv) != 3:
        raise ValueError("Cu phap: py cau8.py scale <so_VM_muc_tieu>")
    cloud = login()
    lbapi = LBAPI(cloud)
    if command == "status":
        print_status(cloud, lbapi)
    else:
        scale(cloud, lbapi, int(sys.argv[2]))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, TimeoutError, requests.RequestException) as exc:
        print("\nLOI:", exc)
        sys.exit(1)
