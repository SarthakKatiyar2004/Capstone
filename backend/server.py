#!/usr/bin/env python3
"""Backend for the Act Reactions dashboard.

Serves the REST API under /api and the static frontend from ../frontend.
Standard library only (http.server + sqlite3).

Usage:  python3 backend/server.py [--host 127.0.0.1] [--port 8000]
"""
import argparse
import csv
import io
import json
import mimetypes
import re
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_csv  # noqa: E402

FRONTEND = import_csv.ROOT / "frontend"

# frontend short key -> acts column
KEYMAP = {
    "id": "id", "t": "title", "y": "year", "j": "jurisdiction", "dp": "department",
    "mn": "ministry", "lv": "level", "n": "n_total", "r": "n_relevant", "ng": "n_negative",
    "nu": "n_neutral", "ps": "n_positive", "net": "net_sentiment", "sh": "net_sentiment_shrunk",
    "po": "polarisation", "dm": "dominant", "cf": "mean_confidence", "rl": "reliable",
    "tier": "tier", "dom": "domain", "ty": "act_type", "sp": "split", "dt": "split_date",
    "stc": "strict_test",
}
EDITABLE = {"t", "y", "j", "dom", "ty", "dp", "mn", "lv"}
SCEN = {"t": "title", "j": "jurisdiction", "dom": "domain", "ty": "act_type", "y": "year",
        "ens": "expected_net", "sim": "similar_net"}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def connect():
    if not import_csv.DB_PATH.exists():
        import_csv.build()
    con = sqlite3.connect(import_csv.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def act_json(row, neighbors):
    d = {short: row[col] for short, col in KEYMAP.items()}
    d["rl"] = bool(d["rl"])
    d["stc"] = None if d["sp"] is None else bool(d["stc"])
    d["nb"] = neighbors.get(row["id"], [])
    return d


def list_tables(con):
    out = []
    rows = con.execute(
        "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') "
        "AND name NOT LIKE 'sqlite_%' ORDER BY type DESC, name").fetchall()
    for r in rows:
        name = r["name"]
        cols = [{"name": c["name"], "type": c["type"] or "TEXT"} for c in con.execute(f'PRAGMA table_info("{name}")')]
        count = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        src = import_csv.SOURCES.get(name)
        out.append({"name": name, "kind": r["type"], "rows": count, "columns": cols,
                    "source": src and f"data/{src}" or import_csv.DERIVED.get(name, "derived")})
    return out


def bootstrap(con):
    nb = {}
    for r in con.execute("SELECT act_id, neighbor_id, similarity FROM neighbors ORDER BY act_id, rank"):
        nb.setdefault(r["act_id"], []).append([int(r["neighbor_id"].split("-")[-1]), r["similarity"]])
    acts = [act_json(r, nb) for r in con.execute("SELECT * FROM acts ORDER BY rowid")]
    reg = [dict(r) for r in con.execute("SELECT * FROM model_regression")]
    cls = [dict(r) for r in con.execute("SELECT * FROM model_classification")]
    pred = []
    for r in con.execute("SELECT * FROM test_predictions"):
        d = dict(r)
        pred.append({
            "id": d["Research_ID"], "t": d["Title"], "net": d["net_sentiment"], "dm": d["dominant"],
            "pn": {k.split("_")[2]: v for k, v in d.items() if k.startswith("pred_net_")},
            "pc": {k.split("_")[2]: v for k, v in d.items() if k.startswith("pred_class_")},
        })
    info = {r["key"]: json.loads(r["value"]) for r in con.execute("SELECT * FROM run_info")}
    return {"acts": acts, "reg": reg, "cls": cls, "pred": pred, "info": info,
            "scenarios": scenarios(con), "tables": list_tables(con)}


def scenarios(con):
    return [{"id": r["id"], "t": r["title"], "j": r["jurisdiction"], "dom": r["domain"], "ty": r["act_type"],
             "y": r["year"], "ens": r["expected_net"], "sim": r["similar_net"]}
            for r in con.execute("SELECT * FROM scenarios ORDER BY id")]


def create_act(con, body):
    title = str(body.get("t", "")).strip()
    if not title:
        raise ApiError(400, "Title is required")
    try:
        int(body.get("y"))
    except (TypeError, ValueError):
        raise ApiError(400, "Year must be a number")
    if not body.get("id"):
        raise ApiError(400, "Missing id")
    data = {KEYMAP[k]: v for k, v in body.items() if k in KEYMAP}
    for flag in ("reliable", "strict_test"):
        if flag in data:
            data[flag] = int(bool(data[flag]))
    cols = ", ".join(data)
    try:
        con.execute(f"INSERT INTO acts ({cols}) VALUES ({','.join('?' * len(data))})", list(data.values()))
    except sqlite3.IntegrityError:
        raise ApiError(409, "An act with this id already exists")


def update_act(con, act_id, body):
    data = {KEYMAP[k]: v for k, v in body.items() if k in EDITABLE}
    if not data:
        raise ApiError(400, "No editable fields supplied")
    sets = ", ".join(f"{c} = ?" for c in data)
    cur = con.execute(f"UPDATE acts SET {sets} WHERE id = ?", [*data.values(), act_id])
    if cur.rowcount == 0:
        raise ApiError(404, "Act not found")


def delete_act(con, act_id):
    cur = con.execute("DELETE FROM acts WHERE id = ?", (act_id,))
    if cur.rowcount == 0:
        raise ApiError(404, "Act not found")
    con.execute("DELETE FROM neighbors WHERE act_id = ? OR neighbor_id = ?", (act_id, act_id))


def table_names(con):
    return {t["name"]: t for t in list_tables(con)}


def table_rows(con, name, query):
    tables = table_names(con)
    if name not in tables:
        raise ApiError(404, "Unknown table")
    cols = [c["name"] for c in tables[name]["columns"]]
    limit = max(1, min(int(query.get("limit", ["1000"])[0]), 20000))
    offset = max(0, int(query.get("offset", ["0"])[0]))
    q = query.get("q", [""])[0].strip()
    where, args = "", []
    if q:
        where = " WHERE " + " OR ".join(f'CAST("{c}" AS TEXT) LIKE ?' for c in cols)
        args = [f"%{q}%"] * len(cols)
    total = con.execute(f'SELECT COUNT(*) FROM "{name}"{where}', args).fetchone()[0]
    rows = [dict(r) for r in con.execute(f'SELECT * FROM "{name}"{where} LIMIT ? OFFSET ?', [*args, limit, offset])]
    return {"name": name, "columns": tables[name]["columns"], "rows": rows, "total": total}


def table_csv(con, name):
    tables = table_names(con)
    if name not in tables:
        raise ApiError(404, "Unknown table")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([c["name"] for c in tables[name]["columns"]])
    w.writerows(tuple(r) for r in con.execute(f'SELECT * FROM "{name}"'))
    return buf.getvalue().encode("utf-8-sig")


class Handler(BaseHTTPRequestHandler):
    server_version = "ActReactions/1.0"

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # ---- helpers
    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except json.JSONDecodeError:
            raise ApiError(400, "Request body must be valid JSON")

    def serve_static(self, path):
        rel = unquote(path).lstrip("/") or "index.html"
        target = (FRONTEND / rel).resolve()
        if FRONTEND.resolve() not in target.parents and target != FRONTEND.resolve():
            raise ApiError(403, "Forbidden")
        if not target.is_file():
            raise ApiError(404, "Not found")
        body = target.read_bytes()
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix == ".js":
            ctype = "text/javascript"
        self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # ---- routing
    def route(self, method):
        url = urlparse(self.path)
        parts = [unquote(p) for p in url.path.strip("/").split("/")]
        query = parse_qs(url.query)
        if parts[0] != "api":
            if method != "GET":
                raise ApiError(405, "Method not allowed")
            return self.serve_static(url.path)
        if parts[1:] == ["reset"] and method == "POST":
            import_csv.build()  # rebuild from the CSV files before any connection is opened
            return self.send_json({"ok": True})
        con = connect()
        try:
            res = self.api(con, method, parts[1:], query)
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        if isinstance(res, bytes):  # CSV download
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{parts[2]}.csv"')
            self.send_header("Content-Length", str(len(res)))
            self.end_headers()
            self.wfile.write(res)
        else:
            self.send_json(res)

    def api(self, con, method, p, query):
        if p == ["health"]:
            return {"status": "ok"}
        if p == ["bootstrap"] and method == "GET":
            return bootstrap(con)
        if p == ["acts"]:
            if method == "GET":
                return bootstrap(con)["acts"]
            if method == "POST":
                create_act(con, self.read_body())
                return {"ok": True}
        if len(p) == 2 and p[0] == "acts":
            if method == "PUT":
                update_act(con, p[1], self.read_body())
                return {"ok": True}
            if method == "DELETE":
                delete_act(con, p[1])
                return {"ok": True}
        if p == ["scenarios"]:
            if method == "GET":
                return scenarios(con)
            if method == "POST":
                b = self.read_body()
                if not str(b.get("t", "")).strip():
                    raise ApiError(400, "Title is required")
                data = {SCEN[k]: v for k, v in b.items() if k in SCEN}
                if isinstance(b.get("id"), int):
                    data["id"] = b["id"]
                con.execute(f"INSERT OR REPLACE INTO scenarios ({', '.join(data)}) VALUES ({','.join('?' * len(data))})",
                            list(data.values()))
                return {"ok": True}
        if len(p) == 2 and p[0] == "scenarios" and method == "DELETE":
            con.execute("DELETE FROM scenarios WHERE id = ?", (p[1],))
            return {"ok": True}
        if p == ["tables"] and method == "GET":
            return list_tables(con)
        if len(p) == 2 and p[0] == "tables" and method == "GET":
            return table_rows(con, p[1], query)
        if len(p) == 3 and p[0] == "tables" and p[2] == "export.csv" and method == "GET":
            return table_csv(con, p[1])
        raise ApiError(404, "Unknown endpoint")

    def handle_any(self, method):
        try:
            self.route(method)
        except ApiError as e:
            self.send_json({"error": str(e)}, e.status)
        except Exception as e:  # noqa: BLE001
            self.send_json({"error": f"Server error: {e}"}, 500)

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def do_PUT(self):
        self.handle_any("PUT")

    def do_DELETE(self):
        self.handle_any("DELETE")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    if not import_csv.DB_PATH.exists():
        print("Database not found, building it from data/*.csv ...")
        import_csv.build(verbose=True)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Act Reactions dashboard running at http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
