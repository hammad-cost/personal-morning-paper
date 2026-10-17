import pytest
from fastapi.testclient import TestClient

from app import ai_editor, auth, editions, gatherer, images, logos, mailer, photos, storage, store
from app import main
from app.main import app


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    """Point the store at a temp file so tests never touch data/store.json."""
    path = tmp_path / "store.json"
    monkeypatch.setattr(store, "STORE_PATH", path)
    return path


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests never call the real AI or the internet, even if backend/.env holds a key."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # Local mode (no sign-in, file storage) unless a test turns Supabase on itself.
    for name in ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_PUBLISHABLE_KEY", "BREVO_API_KEY", "MAIL_FROM_EMAIL",
                 "CRON_SECRET", "PUBLIC_APP_URL", "PUBLIC_API_URL", "DAILY_EMAIL_HOUR", "DAILY_EMAIL_TIMEZONE",
                 "SUPABASE_IMAGES_BUCKET"):
        monkeypatch.delenv(name, raising=False)
    auth.clear_cache()
    main._emails_saved.clear()
    monkeypatch.delenv("MAX_EXTRA_EDITIONS_PER_DAY", raising=False)  # default limit (2) in tests

    def blocked(*args, **kwargs):
        raise AssertionError("real network call attempted in a test")

    monkeypatch.setattr(ai_editor, "call_llm", blocked)
    monkeypatch.setattr(ai_editor, "call_llm_story", blocked)
    monkeypatch.setattr(gatherer.httpx, "get", blocked)
    monkeypatch.setattr(images, "fetch_text", blocked)
    monkeypatch.setattr(images, "post_form", blocked)
    monkeypatch.setattr(images, "fetch_image", lambda url: None)
    monkeypatch.setattr(photos, "wiki_search", blocked)
    monkeypatch.setattr(mailer, "send_via_brevo", blocked)
    monkeypatch.setattr(logos, "fetch", blocked)
    monkeypatch.setattr(storage, "upload", blocked)
    monkeypatch.setattr(storage, "download", blocked)
    storage.reset()
    logos.clear_cache()
    monkeypatch.setenv("LINK_SECRET", "test-link-secret")
    images.clear_cache()
    photos._topic_cache.clear()
    gatherer.clear_cache()
    editions.reset_status()


@pytest.fixture
def client():
    return TestClient(app)
