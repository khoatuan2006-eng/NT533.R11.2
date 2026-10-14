from openstack_api15 import OpenStackAPI15
from neutron import Neutron

username = input("Tai khoan: ")
password = input("Mat khau: ")
project_id = input("Project ID: ")

cloud = OpenStackAPI15(username, password, project_id)
cloud.login()

neutron = Neutron(cloud)

for r in neutron.list_routers():
    print(r["id"], r["name"], r["status"])