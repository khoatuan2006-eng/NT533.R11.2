import requests


class OpenStackAPI15:
    def __init__(self, username, password, project_id, domain="Default"):
        self.identity_url = "https://cloud-identity.uitiot.vn/v3"
        self.compute_url = "https://cloud-compute.uitiot.vn/v2.1"
        self.image_url = "https://cloud-image.uitiot.vn/v2"
        self.network_url = "https://cloud-network.uitiot.vn/v2.0"

        self.username = username
        self.password = password
        self.project_id = project_id
        self.domain = domain
        self.headers = {}

    # Chứng thực
    def login(self):
        data = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": self.username,
                            "domain": {"name": self.domain},
                            "password": self.password
                        }
                    }
                },
                "scope": {
                    "project": {"id": self.project_id}
                }
            }
        }

        r = requests.post(
            self.identity_url + "/auth/tokens",
            json=data,
            timeout=30
        )
        r.raise_for_status()

        token = r.headers["X-Subject-Token"]
        self.headers = {"X-Auth-Token": token}
        print("Dang nhap thanh cong!")

    # Gửi yêu cầu REST API
    def request(self, method, url, data=None):
        r = requests.request(
            method,
            url,
            headers=self.headers,
            json=data,
            timeout=30
        )
        if not r.ok:
            try:
                err_detail = r.json()
            except Exception:
                err_detail = r.text
            print(f"\n[Chi tiet loi {r.status_code} tu OpenStack]: {err_detail}\n")
        r.raise_for_status()

        if r.content:
            return r.json()
        return None