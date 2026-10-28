"""Fetch the small real data samples used by docs/research/REAL_DATA_CONTACT.md into external/ (gitignored). Never executed, only read.

usage: python scripts/fetch_real_data.py [--dk-meters 40]

Sources (licences and checksums are recorded in docs/research/REAL_DATA_SEARCH.md):

* DK: Schaffer, Tvedebrink and Marszal-Pomianowska (2022), "Three years of hourly data from 3021 smart heat meters installed in Danish
  residential buildings", Zenodo record 6563114, CC BY 4.0. The archive is 3.3 GB, so only the members needed are read with HTTP range
  requests; zipfile checks each member's CRC32. A fixed seed picks the meters.
* NIS: Cvetkovic, Zdravkovic and Ignjatovic (2024), "XAI4HEAT SCADA Dataset 2024", Mendeley Data 10.17632/2mwc6x6kwb.1, CC BY 4.0.
  Each file is checked against the sha256 published by Mendeley.

Writes external/<dataset>/... and external/fetch_manifest.json (file, bytes, sha256, source, date).
"""
import argparse, datetime, hashlib, http.client, io, json, os, sys, time, urllib.request, zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
EXT = os.path.join(ROOT, "external")
DK_URL = "https://zenodo.org/api/records/6563114/files/3_years_3021_smart_heat_meters_residential_denmark.zip/content"
NIS = {  # file name: (Mendeley file id, published sha256)
    "xai4heat_scada_L4_processed.csv": ("132758d2-75af-447a-aa69-55d2dfd28c75", "fcda21ad40fc0e08eb43e8603c725935037558a75531e5c602e6b5fbef19cf44"),
    "xai4heat_scada_L8_processed.csv": ("6ea34ad0-79d6-4aaa-b70e-0185aa64887a", "8be894e75d7e78a1ee1f6f096fadb7e539fc486dfecebc6980f441560d3e3fc4"),
    "xai4heat_scada_L12_processed.csv": ("8d1347aa-68ee-45b6-9239-fd0c77206082", "6fa7ff01ca21ecd40ef68a9a7573a11a4cef7112566a9402ba20dbd51077b57d"),
    "xai4heat_scada_L17_processed.csv": ("bb7d3b73-4a94-4fd6-be67-f904c2789215", "b900a5495557b9dd2a16b32d877f8f231f80a2a4c8628c1d6006a0d5da26a7ad"),
    "xai4heat_scada_L22_processed.csv": ("d9376a74-86cf-4371-9599-acd4d47124af", "edafcd07399e031ba0b4b536bb2515e308fdf1eb77cce5ab0857e691b5216db8"),
}
NIS_URL = "https://data.mendeley.com/public-files/datasets/2mwc6x6kwb/files/{}/file_downloaded"


def _read(req, timeout=600):
    """urlopen + read with retries: the connection here drops now and then."""
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r
        except (OSError, http.client.HTTPException):
            if attempt == 5:
                raise
            time.sleep(5 * (attempt + 1))


class RangeFile(io.RawIOBase):
    """A read-only, seekable view of a remote file, read with HTTP range requests."""

    def __init__(self, url):
        _, r = _read(urllib.request.Request(url, method="HEAD"), timeout=60)
        self.size, self.url = int(r.headers["Content-Length"]), r.url
        self.pos = 0

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"})
        data, _ = _read(req)
        b[:len(data)] = data
        self.pos += len(data)
        return len(data)


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def fetch_dk(n_meters, manifest):
    out = os.path.join(EXT, "dk_smart_heat_6563114")
    os.makedirs(out, exist_ok=True)
    z = zipfile.ZipFile(io.BufferedReader(RangeFile(DK_URL), buffer_size=1 << 20))
    names = sorted(n for n in z.namelist() if n.startswith("01_Data/02_processed_final_data/") and n.endswith(".csv"))
    import random
    pick = random.Random(0).sample(names, n_meters)
    for m in ["01_Data/03_context_data/contextual_data.csv", "01_Data/05_data_description.pdf"] + pick:
        dst = os.path.join(out, os.path.basename(m))
        if not os.path.exists(dst):
            with z.open(m) as src, open(dst, "wb") as fh:     # zipfile raises on a CRC mismatch
                fh.write(src.read())
        manifest.append({"dataset": "dk_smart_heat_6563114", "member": m, "file": os.path.relpath(dst, ROOT).replace(os.sep, "/"),
                         "bytes": os.path.getsize(dst), "sha256": sha256(dst), "source": DK_URL})
        print("dk", m, flush=True)


def fetch_nis(manifest):
    out = os.path.join(EXT, "nis_xai4heat_2mwc6x6kwb")
    os.makedirs(out, exist_ok=True)
    for name, (fid, want) in NIS.items():
        dst = os.path.join(out, name)
        if not os.path.exists(dst):
            data, _ = _read(urllib.request.Request(NIS_URL.format(fid)))
            with open(dst, "wb") as fh:
                fh.write(data)
        got = sha256(dst)
        if got != want:
            os.remove(dst)
            sys.exit(f"{name}: sha256 {got} does not match the published {want}; file removed")
        manifest.append({"dataset": "nis_xai4heat_2mwc6x6kwb", "file": os.path.relpath(dst, ROOT).replace(os.sep, "/"),
                         "bytes": os.path.getsize(dst), "sha256": got, "published_sha256": want, "source": NIS_URL.format(fid)})
        print("nis", name, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dk-meters", type=int, default=40)
    a = ap.parse_args()
    manifest = []
    fetch_nis(manifest)
    fetch_dk(a.dk_meters, manifest)
    json.dump({"fetched_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "files": manifest},
              open(os.path.join(EXT, "fetch_manifest.json"), "w"), indent=2)
    print("done", len(manifest), "files")
