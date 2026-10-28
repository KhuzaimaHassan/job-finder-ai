"""Disposable data stores and PDFs for local regression tests; no cloud clients."""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4


def make_pdf(text="Local Test Candidate | Python, SQL, FastAPI | Backend engineering experience"):
    lines = [text[i:i + 85] for i in range(0, len(text), 85)]
    commands = ["BT /F1 12 Tf 40 750 Td"]
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.extend([f"({safe}) Tj", "0 -18 Td"])
    stream = ("\n".join(commands) + "\nET").encode("ascii")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)


class MemoryStorage:
    def __init__(self):
        self.files = {}

    def from_(self, _bucket):
        return self

    def upload(self, path, content, **_kwargs):
        if path in self.files:
            raise RuntimeError("Existing PDF must not be overwritten")
        self.files[path] = content

    def remove(self, paths):
        for path in paths:
            self.files.pop(path, None)


class UniqueViolation(Exception):
    code = "23505"


class MemoryQuery:
    def __init__(self, db, table):
        self.db, self.name = db, table
        self.filters, self.ordering = [], None
        self.window, self.maximum = None, None
        self.operation, self.payload = "select", None

    def select(self, *_args): return self
    def eq(self, key, value): self.filters.append(lambda r: r.get(key) == value); return self
    def gte(self, key, value): self.filters.append(lambda r: r.get(key, "") >= value); return self
    def order(self, key, desc=False): self.ordering = (key, desc); return self
    def limit(self, n): self.maximum = n; return self
    def range(self, start, end): self.window = (start, end); return self
    def insert(self, payload): self.operation, self.payload = "insert", payload; return self
    def upsert(self, payload, **_kwargs): self.operation, self.payload = "upsert", payload; return self
    def update(self, payload): self.operation, self.payload = "update", payload; return self
    def delete(self): self.operation = "delete"; return self

    def execute(self):
        rows = self.db.rows.setdefault(self.name, [])
        selected = [r for r in rows if all(f(r) for f in self.filters)]
        if self.operation in ("insert", "upsert"):
            if self.name in self.db.fail_insert:
                raise RuntimeError("Synthetic insert failure")
            data = self.payload if isinstance(self.payload, list) else [self.payload]
            changed = []
            for item in data:
                record = deepcopy(item)
                now = datetime.now(timezone.utc).isoformat()
                record.setdefault("id", str(uuid4()))
                if self.name == "applications":
                    record.setdefault("updated_at", now)
                    record.setdefault("applied_date", now)
                old = next((r for r in rows if r.get("id") == record["id"]), None)
                if self.operation == "insert" and old is not None:
                    raise UniqueViolation("Duplicate primary key")
                if self.operation == "upsert" and old is not None:
                    old.update(record)
                else:
                    rows.append(record)
                changed.append(record)
            return SimpleNamespace(data=deepcopy(changed))
        if self.operation == "delete":
            self.db.deletes.append(self.name)
            self.db.rows[self.name] = [r for r in rows if r not in selected]
        elif self.operation == "update":
            for row in selected: row.update(self.payload)
        if self.ordering:
            key, desc = self.ordering
            selected.sort(key=lambda r: r.get(key) or "", reverse=desc)
        if self.window:
            start, end = self.window
            selected = selected[start:end + 1]
        if self.maximum is not None:
            selected = selected[:self.maximum]
        return SimpleNamespace(data=deepcopy(selected))


class MemoryDB:
    def __init__(self, rows=None):
        self.rows = deepcopy(rows or {})
        self.storage, self.fail_insert, self.deletes = MemoryStorage(), set(), []

    def table(self, name):
        return MemoryQuery(self, name)
