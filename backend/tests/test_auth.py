from bson import ObjectId


def test_register_login_and_me(client, make_user):
    headers, user, password = make_user()
    assert user["role"] == "student"
    assert user["quota_bytes"] == 100 * 1024 * 1024

    res = client.post("/api/auth/login", json={"email": user["email"], "password": password})
    assert res.status_code == 200
    assert "refresh_token" in res.cookies

    me = client.get("/api/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == user["email"]
    assert "password_hash" not in me.json()


def test_register_duplicate_email_and_weak_password(client, make_user):
    _, user, _ = make_user()
    dup = client.post("/api/auth/register", json={"name": "X Y", "email": user["email"], "password": "secret123"})
    assert dup.status_code == 409
    weak = client.post("/api/auth/register", json={"name": "X Y", "email": "weak@test.com", "password": "short"})
    assert weak.status_code == 422


def test_password_is_hashed(db, make_user):
    _, user, password = make_user()
    stored = db.users.find_one({"_id": ObjectId(user["id"])})
    assert stored["password_hash"] != password
    assert stored["password_hash"].startswith("$argon2")


def test_wrong_password_and_no_token(client, make_user):
    _, user, _ = make_user()
    assert client.post("/api/auth/login", json={"email": user["email"], "password": "wrong12345"}).status_code == 401
    assert client.get("/api/users/me").status_code == 401
    assert client.get("/api/users/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_refresh_returns_new_access_token(client, make_user):
    _, user, password = make_user()
    client.post("/api/auth/login", json={"email": user["email"], "password": password})
    res = client.post("/api/auth/refresh")
    assert res.status_code == 200
    assert res.json()["user"]["email"] == user["email"]


def test_profile_update(client, make_user):
    headers, _, _ = make_user()
    res = client.patch("/api/users/me", headers=headers, json={"name": "New Name"})
    assert res.status_code == 200
    assert res.json()["name"] == "New Name"


def test_password_change_revokes_old_tokens(client, make_user):
    old_headers, user, password = make_user()
    bad = client.post("/api/users/me/password", headers=old_headers,
                      json={"current_password": "wrong12345", "new_password": "newpass123"})
    assert bad.status_code == 400

    res = client.post("/api/users/me/password", headers=old_headers,
                      json={"current_password": password, "new_password": "newpass123"})
    assert res.status_code == 200
    new_headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

    assert client.get("/api/users/me", headers=old_headers).status_code == 401
    assert client.get("/api/users/me", headers=new_headers).status_code == 200
    assert client.post("/api/auth/login", json={"email": user["email"], "password": "newpass123"}).status_code == 200


def test_suspended_user_is_blocked(client, db, make_user):
    headers, user, password = make_user()
    db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"status": "suspended"}})
    assert client.get("/api/users/me", headers=headers).status_code == 403
    assert client.post("/api/auth/login", json={"email": user["email"], "password": password}).status_code == 403


def test_login_rate_limit(client):
    codes = [client.post("/api/auth/login", json={"email": "nobody@test.com", "password": "x"}).status_code
             for _ in range(12)]
    assert 429 in codes
