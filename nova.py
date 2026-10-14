class Nova:
    def __init__(self, cloud):
        self.cloud = cloud
        self.url = cloud.compute_url

    def list_flavors(self):
        data = self.cloud.request("GET", self.url + "/flavors/detail")
        return data["flavors"]

    # Liệt kê máy ảo
    def list_instances(self):
        data = self.cloud.request("GET", self.url + "/servers/detail")
        return data["servers"]

    # Tạo máy ảo, khởi động từ volume
    def create_instance(self, name, flavor_id, image_id, network_id,
                        volume_size=20):
        data = {
            "server": {
                "name": name,
                "flavorRef": flavor_id,
                "networks": [
                    {"uuid": network_id}
                ],
                "block_device_mapping_v2": [
                    {
                        "boot_index": 0,
                        "uuid": image_id,
                        "source_type": "image",
                        "destination_type": "volume",
                        "volume_size": volume_size,
                        "delete_on_termination": True
                    }
                ]
            }
        }

        result = self.cloud.request("POST", self.url + "/servers", data)
        return result["server"]