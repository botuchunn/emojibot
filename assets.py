"""assets.py — shablon JSON fayllarini bitta siqilgan arxivdan (templates_pack.zip)
o'qiydi. Papkada oddiy .json fayl bo'lsa, avval o'shani ishlatadi.

Arxivni yangilash: py assets.py pack   (templates/ va templates_tgs/ ni qayta yig'adi)
"""
import json
import os
import sys
import threading
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(BASE, "templates_pack.zip")
_DIRS = ("templates", "templates_tgs")
_lock = threading.Lock()
_zip = None


def _pack():
    global _zip
    if _zip is None and os.path.exists(PACK):
        _zip = zipfile.ZipFile(PACK)
    return _zip


def _key(path: str) -> str:
    return os.path.relpath(os.path.abspath(path), BASE).replace(os.sep, "/")


def load_json(path: str):
    """path: eski usuldagi to'liq yo'l (…/templates/name.json)."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    with _lock:
        z = _pack()
        if z is None:
            raise FileNotFoundError(path)
        return json.loads(z.read(_key(path)).decode("utf-8"))


def list_json(dirname: str):
    """dirname papkasidagi barcha .json fayl nomlari (papka + arxiv)."""
    names = set()
    d = os.path.join(BASE, dirname)
    if os.path.isdir(d):
        names |= {f for f in os.listdir(d) if f.endswith(".json")}
    with _lock:
        z = _pack()
        if z:
            pre = dirname + "/"
            names |= {n[len(pre):] for n in z.namelist() if n.startswith(pre) and n.endswith(".json")}
    return sorted(names)


def pack_all():
    """Faqat papkalardagi oddiy .json fayllardan arxiv yig'adi."""
    files = []
    for d in _DIRS:
        dd = os.path.join(BASE, d)
        if os.path.isdir(dd):
            files += [(os.path.join(dd, f), f"{d}/{f}") for f in sorted(os.listdir(dd)) if f.endswith(".json")]
    if not files:
        sys.exit("XATO: templates/ yoki templates_tgs/ papkalarida .json topilmadi.")
    global _zip
    with _lock:
        if _zip is not None:
            _zip.close()
            _zip = None
    tmp = PACK + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for src, arc in files:
            z.write(src, arc)
    os.replace(tmp, PACK)
    print("OK:", len(files), "fayl ->", PACK, round(os.path.getsize(PACK) / 1e6, 2), "MB")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "pack":
        pack_all()
    else:
        print(__doc__)
