class Neutron:
    def __init__(self, cloud):
        self.cloud = cloud
        self.url = cloud.network_url

    def list_networks(self):
        data = self.cloud.request("GET", self.url + "/networks")
        return data["networks"]

    def create_network(self, name):
        data = {"network": {"name": name}}

        result = self.cloud.request("POST", self.url + "/networks", data)
        return result["network"]

    def delete_network(self, network_id):
        self.cloud.request("DELETE", self.url + "/networks/" + network_id)

    def list_subnets(self):
        data = self.cloud.request("GET", self.url + "/subnets")
        return data["subnets"]

    def create_subnet(self, name, network_id, cidr):
        data = {
            "subnet": {
                "name": name,
                "network_id": network_id,
                "ip_version": 4,
                "cidr": cidr
            }
        }

        result = self.cloud.request("POST", self.url + "/subnets", data)
        return result["subnet"]

    def delete_subnet(self, subnet_id):
        self.cloud.request("DELETE", self.url + "/subnets/" + subnet_id)

    def list_routers(self):
        data = self.cloud.request("GET", self.url + "/routers")
        return data["routers"]

    def create_router(self, name):
        data = {
            "router": {
                "name": name,
                "admin_state_up": True
            }
        }

        result = self.cloud.request("POST", self.url + "/routers", data)
        return result["router"]

    def delete_router(self, router_id):
        self.cloud.request("DELETE", self.url + "/routers/" + router_id)