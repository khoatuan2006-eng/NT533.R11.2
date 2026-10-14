# OpenStack Lab — Flask templates

Giao diện lấy cảm hứng từ Horizon; không phải bộ template chính thức.
Giải nén templates/ và static/ vào cùng thư mục app.py hiện tại.
Đây chỉ là giao diện Jinja2, không có backend và không tự gọi API.
Không mở trực tiếp HTML: phải render qua Flask.

## Phụ thuộc backend
Cài Flask và Flask-WTF. Khởi tạo CSRFProtect(app), cấu hình SECRET_KEY.
Mọi form POST có csrf_token(). Không bỏ bảo vệ này khi nối backend.
Tất cả trang được bảo vệ đăng nhập trừ login.
Lưu token riêng theo phiên ở server; không giữ mật khẩu sau đăng nhập,
không dùng biến cloud toàn cục hoặc đưa token vào cookie session Flask mặc định.

## Endpoint Flask cần định nghĩa
Tên trong cột endpoint phải khớp url_for; đường dẫn thực tế tùy bạn.

| Endpoint | Method | Dữ liệu form / tham số |
|---|---|---|
| login | GET, POST | username, password, project_id, domain |
| logout | POST | — |
| instances | GET | — |
| images_flavors | GET | — |
| networks | GET | — |
| routers | GET | — |
| create_instance | POST | name, flavor_id, image_id, network_id, volume_size |
| create_network | POST | name |
| delete_network | POST | URL: network_id |
| create_subnet | POST | name, network_id, cidr |
| delete_subnet | POST | URL: subnet_id |
| create_router | POST | name |
| delete_router | POST | URL: router_id |

Các route delete nhận POST từ HTML rồi gọi hàm Neutron dùng HTTP DELETE.
Không tạo hoặc xóa tài nguyên trong các route GET.
Sau POST thành công: flash thông báo rồi redirect về trang danh sách.
Bắt requests.HTTPError để hiển thị lỗi đã làm sạch, không in token/mật khẩu.
Kiểm tra dữ liệu phía server: trường bắt buộc, CIDR, ID tài nguyên/quyền sở hữu,
volume_size là số nguyên dương phù hợp quota và yêu cầu Image.
Router gắn interface phải gỡ trước khi xóa.

## Dữ liệu truyền vào render_template
Trang dùng dữ liệu dict/list nguyên bản từ API, không dùng đối tượng SDK.
- Mọi trang base: username, project_name (nếu chưa có tên có thể dùng project_id).
- instances.html: instances, flavors, images, networks.
- images_flavors.html: images, flavors.
- networks.html: networks, subnets.
- routers.html: routers.
- login.html: không yêu cầu dữ liệu ngoài flash và CSRF.

Ví dụ trong route networks sau khi lấy cloud đúng phiên:
```python
neutron = Neutron(cloud)
return render_template(
    'networks.html',
    networks=neutron.list_networks(),
    subnets=neutron.list_subnets(),
    username=cloud.username,
    project_name=cloud.project_id
)
```
Các class giữ nguyên cấu trúc đã viết. Form tạo instance dùng volume_size
khớp hàm Nova.create_instance hiện tại. Chưa thêm xóa instance vì đề chỉ yêu
cầu liệt kê/tạo. Chưa có router interface, Floating IP, User Data hoặc LB.
Danh sách hiển thị đúng dữ liệu backend cung cấp; backend hiện chỉ lấy một trang.
