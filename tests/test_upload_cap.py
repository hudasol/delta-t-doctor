"""The body cap must hold for chunked uploads that carry no Content-Length."""
from fastapi.testclient import TestClient

from deltat_doctor.api import MAX_BYTES, app

client = TestClient(app)


def _chunks(total, size=1 << 20):
    sent = 0
    yield b'--B\r\nContent-Disposition: form-data; name="file"; filename="x.csv"\r\nContent-Type: text/csv\r\n\r\n'
    while sent < total:
        n = min(size, total - sent)
        sent += n
        yield b"a,b\n" * (n // 4)
    yield b"\r\n--B--\r\n"


def test_chunked_oversize_is_rejected_without_content_length():
    r = client.post("/api/diagnose", content=_chunks(MAX_BYTES + 3 * (1 << 20)),
                    headers={"content-type": "multipart/form-data; boundary=B"})
    assert r.status_code == 413


def test_declared_oversize_is_rejected():
    r = client.post("/api/diagnose", content=b"x", headers={"content-length": str(MAX_BYTES + 5_000_000),
                                                          "content-type": "multipart/form-data; boundary=B"})
    assert r.status_code in (413, 400)


def test_small_upload_still_works():
    r = client.post("/api/diagnose", files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")})
    assert r.status_code == 422      # parsed, then rejected for content, not for size
