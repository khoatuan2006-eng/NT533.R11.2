import secrets
import requests

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
from flask_wtf.csrf import CSRFProtect

from openstack_api15 import OpenStackAPI15
from nova import Nova
from glance import Glance
from neutron import Neutron


app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

CSRFProtect(app)

# Mỗi phiên đăng nhập có một kết nối riêng.
# Token nằm trong bộ nhớ server, không đưa vào cookie.
connections = {}


def get_cloud():
    return connections.get(session.get("connection_id"))


# Yêu cầu đăng nhập trước khi vào các trang quản lý
@app.before_request
def check_login():
    if request.endpoint in ("login", "static", None):
        return

    if get_cloud() is None:
        return redirect(url_for("login"))


# Thông tin chung cho thanh trên của giao diện
@app.context_processor
def common_info():
    cloud = get_cloud()

    if cloud:
        return {
            "username": cloud.username,
            "project_name": cloud.project_id
        }

    return {}


# Đăng nhập
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        cloud = OpenStackAPI15(
            request.form["username"].strip(),
            request.form["password"],
            request.form["project_id"].strip(),
            request.form.get("domain", "Default").strip()
        )

        try:
            cloud.login()
        except requests.RequestException:
            flash(
                "Đăng nhập thất bại. Kiểm tra tài khoản, project "
                "và kết nối tới OpenStack.",
                "error"
            )
            return render_template("login.html")

        # Không giữ mật khẩu sau khi đã lấy token
        cloud.password = None

        old_id = session.get("connection_id")
        connections.pop(old_id, None)
        session.clear()

        connection_id = secrets.token_hex(24)
        connections[connection_id] = cloud
        session["connection_id"] = connection_id

        return redirect(url_for("instances"))

    return render_template("login.html")


# Đăng xuất
@app.route("/logout", methods=["POST"])
def logout():
    connections.pop(session.get("connection_id"), None)
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    return redirect(url_for("instances"))


# ==================== IMAGE / FLAVOR ====================

@app.route("/images-flavors")
def images_flavors():
    cloud = get_cloud()

    return render_template(
        "images_flavors.html",
        images=Glance(cloud).list_images(),
        flavors=Nova(cloud).list_flavors()
    )


# ==================== INSTANCE ====================

@app.route("/instances")
def instances():
    cloud = get_cloud()

    return render_template(
        "instances.html",
        instances=Nova(cloud).list_instances(),
        flavors=Nova(cloud).list_flavors(),
        images=Glance(cloud).list_images(),
        networks=Neutron(cloud).list_networks()
    )


@app.route("/instances/create", methods=["POST"])
def create_instance():
    try:
        volume_size = int(request.form["volume_size"])
        if volume_size < 1:
            raise ValueError
    except ValueError:
        flash("Dung lượng volume phải là số nguyên dương.", "error")
        return redirect(url_for("instances"))

    nova = Nova(get_cloud())

    nova.create_instance(
        name=request.form["name"].strip(),
        flavor_id=request.form["flavor_id"],
        image_id=request.form["image_id"],
        network_id=request.form["network_id"],
        volume_size=volume_size
    )

    flash(
        "Đã gửi yêu cầu tạo máy ảo. Tải lại trang để xem trạng thái.",
        "success"
    )
    return redirect(url_for("instances"))


# ==================== NETWORK / SUBNET ====================

@app.route("/networks")
def networks():
    neutron = Neutron(get_cloud())

    return render_template(
        "networks.html",
        networks=neutron.list_networks(),
        subnets=neutron.list_subnets()
    )


@app.route("/networks/create", methods=["POST"])
def create_network():
    neutron = Neutron(get_cloud())
    neutron.create_network(request.form["name"].strip())

    flash("Đã tạo Network.", "success")
    return redirect(url_for("networks"))


@app.route("/networks/<network_id>/delete", methods=["POST"])
def delete_network(network_id):
    neutron = Neutron(get_cloud())
    neutron.delete_network(network_id)

    flash("Đã xóa Network.", "success")
    return redirect(url_for("networks"))


@app.route("/subnets/create", methods=["POST"])
def create_subnet():
    neutron = Neutron(get_cloud())

    neutron.create_subnet(
        name=request.form["name"].strip(),
        network_id=request.form["network_id"],
        cidr=request.form["cidr"].strip()
    )

    flash("Đã tạo Subnet.", "success")
    return redirect(url_for("networks"))


@app.route("/subnets/<subnet_id>/delete", methods=["POST"])
def delete_subnet(subnet_id):
    neutron = Neutron(get_cloud())
    neutron.delete_subnet(subnet_id)

    flash("Đã xóa Subnet.", "success")
    return redirect(url_for("networks"))


# ==================== ROUTER ====================

@app.route("/routers")
def routers():
    neutron = Neutron(get_cloud())

    return render_template(
        "routers.html",
        routers=neutron.list_routers()
    )


@app.route("/routers/create", methods=["POST"])
def create_router():
    neutron = Neutron(get_cloud())
    neutron.create_router(request.form["name"].strip())

    flash("Đã tạo Router.", "success")
    return redirect(url_for("routers"))


@app.route("/routers/<router_id>/delete", methods=["POST"])
def delete_router(router_id):
    neutron = Neutron(get_cloud())
    neutron.delete_router(router_id)

    flash("Đã xóa Router.", "success")
    return redirect(url_for("routers"))


# ==================== XỬ LÝ LỖI API ====================

@app.errorhandler(requests.RequestException)
def api_error(error):
    response = getattr(error, "response", None)
    status = response.status_code if response is not None else None

    if status == 401:
        connections.pop(session.get("connection_id"), None)
        session.clear()
        flash("Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.", "error")
        return redirect(url_for("login"))

    messages = {
        400: "Dữ liệu không hợp lệ. Kiểm tra các thông tin đã nhập.",
        403: "Tài khoản không có quyền hoặc tài nguyên vượt quota.",
        404: "Không tìm thấy tài nguyên.",
        409: "Tài nguyên đang được sử dụng hoặc có cấu hình xung đột."
    }
    message = messages.get(
        status,
        "Không thực hiện được yêu cầu tới OpenStack. Vui lòng thử lại."
    )

    # POST thất bại: quay về trang danh sách tương ứng
    if request.method == "POST":
        flash(message, "error")

        if request.endpoint in ("create_instance",):
            return redirect(url_for("instances"))

        if request.endpoint in ("create_router", "delete_router"):
            return redirect(url_for("routers"))

        return redirect(url_for("networks"))

    # GET thất bại: hiển thị lỗi, tránh chuyển hướng lặp vô hạn
    return (
        f"<h2>{message}</h2>"
        '<p><a href="/">Thử lại</a> | '
        '<a href="/login">Đăng nhập lại</a></p>',
        502
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)