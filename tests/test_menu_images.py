import io
from PIL import Image
from tests.test_workflow import api


def test_menu_photo_lifecycle_and_permissions(api):
    c, auth = api
    manager, cashier = auth("manager"), auth("cashier")
    cat = c.post("/menu/categories", headers=manager, json={"name": "BBQ"}).json()["id"]
    item = c.post(
        "/menu/items",
        headers=manager,
        json={"name": "Tikka", "category_id": cat, "price": 12000},
    ).json()["id"]
    out = io.BytesIO()
    Image.new("RGB", (40, 30), "red").save(out, format="PNG")
    path = f"/menu/items/{item}/image"
    assert (
        c.post(
            path, headers=cashier, files={"file": ("x.png", out.getvalue())}
        ).status_code
        == 403
    )
    assert (
        c.post(
            path, headers=manager, files={"file": ("x.png", b"not a photo")}
        ).status_code
        == 415
    )
    assert (
        c.post(
            path,
            headers=manager,
            files={"file": ("x.jpg", b"x" * (5 * 1024 * 1024 + 1))},
        ).status_code
        == 413
    )
    result = c.post(path, headers=manager, files={"file": ("x.png", out.getvalue())})
    assert result.status_code == 200
    url = result.json()["image_url"]
    assert c.get(url).status_code == 401
    photo = c.get(url, headers=cashier)
    assert photo.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(photo.content)).size == (40, 30)
    assert c.get("/menu/items", headers=cashier).json()[0]["image_url"] == url
    assert c.delete(path, headers=cashier).status_code == 403
    assert c.delete(path, headers=manager).status_code == 200
    assert c.get("/menu/items", headers=cashier).json()[0]["image_url"] is None
