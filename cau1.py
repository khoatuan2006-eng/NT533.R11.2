from openstack_api15 import OpenStackAPI15
from nova import Nova
from glance import Glance

# Đăng nhập
username = input("Tai khoan: ")
password = input("Mat khau: ")
project_id = input("Project ID: ")

cloud = OpenStackAPI15(username, password, project_id)
cloud.login()

# Các dịch vụ dùng chung kết nối đã đăng nhập
nova = Nova(cloud)
glance = Glance(cloud)

# Liệt kê Flavor
print("\nDANH SACH FLAVOR")
for f in nova.list_flavors():
    print(
        f["id"], f["name"],
        f["vcpus"], "CPU",
        f["ram"], "MB RAM",
        f["disk"], "GB Disk"
    )

# Liệt kê Image
print("\nDANH SACH IMAGE")
for i in glance.list_images():
    print(i["id"], i["name"], i["status"])