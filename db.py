"""Tiny JSON "database" — one collection = one file in data/."""
import json
import os
import secrets
import threading

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

_lock = threading.Lock()


def _path(collection: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, f"{collection}.json")


def load(collection: str) -> list:
    try:
        with open(_path(collection), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save(collection: str, records: list) -> None:
    path = _path(collection)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _gen_id(prefix: str) -> str:
    """A random, non-sequential id like ``u_4f2a9c81d3e5``."""
    return f"{prefix}_{secrets.token_hex(6)}"


def insert(collection: str, record: dict, prefix: str) -> dict:
    with _lock:
        record["id"] = record.get("id") or _gen_id(prefix)
        records = load(collection)
        while any(r.get("id") == record["id"] for r in records):
            record["id"] = _gen_id(prefix)
        records.append(record)
        save(collection, records)
        return record


def update(collection: str, id: str, fields: dict) -> dict | None:
    with _lock:
        records = load(collection)
        for r in records:
            if r["id"] == id:
                r.update(fields)
                save(collection, records)
                return r
        return None


def find(collection: str, **filters) -> list:
    records = load(collection)
    out = []
    for r in records:
        if all(r.get(k) == v for k, v in filters.items()):
            out.append(r)
    return out


def one(collection: str, **filters) -> dict | None:
    return next(iter(find(collection, **filters)), None)