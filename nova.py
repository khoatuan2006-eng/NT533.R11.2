class Nova:
    def __init__(self, cloud):
        self.cloud = cloud
        self.url = cloud.compute_url

    def list_flavors(self):
        data = self.cloud.request("GET", self.url + "/flavors/detail")
        return data["flavors"]