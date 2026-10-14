from openstack_api15 import OpenStackAPI15
from neutron import Neutron

username = input("Tai khoan: ")
password = input("Mat khau: ")
project_id = input("Project ID: ")

cloud = OpenStackAPI15(username, password, project_id)
cloud.login()

neutron = Neutron(cloud)

# Liệt kê Network
for n in neutron.list_networks():
    print(n["id"], n["name"])

# Liệt kê Subnet
for s in neutron.list_subnets():
    print(s["id"], s["name"], s["cidr"])