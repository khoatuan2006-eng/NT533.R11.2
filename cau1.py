from openstack_api15 import OpenStackAPI15

# Khởi tạo đối tượng và đăng nhập
username = input("Tai khoan: ")
password = input("Mat khau: ")
project_id = input("Project ID: ")

cloud = OpenStackAPI15(username, password, project_id)
cloud.login()

# Liệt kê Flavor
data = cloud.request("GET", cloud.compute_url + "/flavors/detail")

print("\nDANH SACH FLAVOR")
for f in data["flavors"]:
    print(f["id"], f["name"], f["vcpus"], "CPU", f["ram"], "MB RAM")

# Liệt kê Image
data = cloud.request("GET", cloud.image_url + "/images")

print("\nDANH SACH IMAGE")
for i in data["images"]:
    print(i["id"], i["name"], i["status"])