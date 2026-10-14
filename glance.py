class Glance:
    def __init__(self, cloud):
        self.cloud = cloud
        self.url = cloud.image_url

    def list_images(self):
        data = self.cloud.request("GET", self.url + "/images")
        return data["images"]