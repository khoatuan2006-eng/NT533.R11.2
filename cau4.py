from openstack_api15 import OpenStackAPI15
from nova import Nova

username = input("Tai khoan: ")
password = input("Mat khau: ")
project_id = input("Project ID: ")

cloud = OpenStackAPI15(username, password, project_id)
cloud.login()

nova = Nova(cloud)

for vm in nova.list_instances():
    print(vm["id"], vm["name"], vm["status"])