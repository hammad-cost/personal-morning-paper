"""Running online: pictures in Supabase Storage, CORS for the Vercel site, API links in emails."""
from app import mailer, photos, storage


def supabase_on(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")


# ---------- pictures survive a restart ----------

def test_pictures_are_uploaded_and_read_back_after_the_disk_is_wiped(monkeypatch, client):
    supabase_on(monkeypatch)
    bucket = {}
    monkeypatch.setattr(storage, "upload", lambda name, data, content_type="image/jpeg": bucket.__setitem__(name, data))
    monkeypatch.setattr(storage, "download", lambda name: bucket.get(name))

    name = photos.vale_illustration("AI Agents")
    assert name in bucket
    (photos.images_dir() / name).unlink()  # Render restarted: local disk is empty

    r = client.get(f"/api/images/{name}")
    assert r.status_code == 200 and r.content == bucket[name]
    assert (photos.images_dir() / name).is_file()  # cached locally again
    assert photos.read_local(f"/api/images/{name}") == bucket[name]  # the PDF finds it too


def test_missing_pictures_and_bad_names_are_404(monkeypatch, client):
    supabase_on(monkeypatch)
    monkeypatch.setattr(storage, "download", lambda name: None)
    assert client.get("/api/images/abc123.jpg").status_code == 404
    assert client.get("/api/images/..%2Fstore.json").status_code == 404


def test_a_failed_upload_still_keeps_the_local_picture(monkeypatch):
    supabase_on(monkeypatch)

    def down(*a, **k):
        raise RuntimeError("storage offline")

    monkeypatch.setattr(storage, "upload", down)
    name = photos.vale_illustration("Space")
    assert (photos.images_dir() / name).is_file()


def test_storage_calls_supabase_with_the_secret_key(monkeypatch):
    supabase_on(monkeypatch)
    import importlib

    real = importlib.reload(storage)  # undo the conftest block for this module's real functions
    calls = []

    class R:
        def __init__(self, status=200, text="", content=b""):
            self.status_code, self.text, self.content = status, text, content

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(self.status_code)

    def post(url, **kw):
        calls.append(("POST", url, kw.get("headers", {}), kw.get("json")))
        return R(400, '{"error":"Duplicate","message":"The resource already exists"}') if url.endswith("/bucket") else R()

    monkeypatch.setattr(real.httpx, "post", post)
    monkeypatch.setattr(real.httpx, "get", lambda url, **kw: calls.append(("GET", url, kw["headers"], None)) or R(content=b"jpg"))
    real.upload("a.jpg", b"jpg")
    real.upload("b.jpg", b"jpg")  # bucket is checked once per run
    assert [c[1] for c in calls] == [
        "https://proj.supabase.co/storage/v1/bucket",
        "https://proj.supabase.co/storage/v1/object/vale-images/a.jpg",
        "https://proj.supabase.co/storage/v1/object/vale-images/b.jpg",
    ]
    assert calls[0][3] == {"id": "vale-images", "name": "vale-images", "public": False}  # private bucket
    assert calls[1][2]["apikey"] == "sb_secret_test" and calls[1][2]["x-upsert"] == "true"
    assert real.download("a.jpg") == b"jpg"
    real.reset()


# ---------- CORS for the website ----------

def test_cors_allows_the_site_and_exposes_the_pdf_filename(client):
    r = client.options("/api/state", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
                                               "Access-Control-Request-Headers": "authorization"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert "content-disposition" in r.headers["access-control-expose-headers"].lower()


def test_cors_blocks_other_sites(client):
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_allowed_origins_come_from_the_environment(monkeypatch):
    from app import main

    monkeypatch.setenv("ALLOWED_ORIGINS", "https://vale.vercel.app/, http://localhost:5173")
    assert main.allowed_origins() == ["https://vale.vercel.app", "http://localhost:5173"]


# ---------- email links point at the API ----------

def test_email_links_use_the_api_address_when_set(monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_URL", "https://vale.vercel.app")
    assert mailer.api_url() == "https://vale.vercel.app"  # same place locally
    monkeypatch.setenv("PUBLIC_API_URL", "https://vale-api.onrender.com/")
    assert mailer.api_url() == "https://vale-api.onrender.com"
    assert mailer.app_url() == "https://vale.vercel.app"


def test_on_render_the_api_address_comes_from_render_itself(monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_URL", "https://vale-web.onrender.com")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://vale-api-ab12.onrender.com")
    assert mailer.api_url() == "https://vale-api-ab12.onrender.com"
    monkeypatch.setenv("PUBLIC_API_URL", "https://api.example.com")
    assert mailer.api_url() == "https://api.example.com"  # an explicit setting wins
