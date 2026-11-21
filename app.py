"""
Electronic Products Stock View & Inventory — Flask + Supabase
Run:  pip install -r requirements.txt
      python seed.py   # once
      flask run --debug  (or python app.py)
"""
import os, io, datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, send_file
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-change-me")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # service_role on server — never expose to browser
LOW_STOCK = int(os.getenv("LOW_STOCK_THRESHOLD", "2"))

_supabase: Client | None = None
def supabase() -> Client:
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("Missing SUPABASE_URL / SUPABASE_KEY. Copy .env.example to .env")
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase

def parse_int(v, default=0):
    try: return int(float(v))
    except: return default

def parse_num(v, default=0):
    try: return float(v)
    except: return default

def fetch_products(search="", remarks="All", stock="All", sort="product_no", direction="asc"):
    """Filtering/sorting done in Python after one Supabase fetch — simple, fast for <10k SKUs,
    and avoids PostgREST operator quirks. For larger catalogs, move filters to .ilike/.lte()."""
    res = supabase().table("products").select("*").order("product_no").execute()
    rows = res.data or []
    if search:
        q = search.lower()
        rows = [r for r in rows if q in (r.get("item_code") or "").lower() or q in (r.get("description_brand") or "").lower() or q in (r.get("specs_size") or "").lower()]
    if remarks and remarks != "All":
        rows = [r for r in rows if (r.get("remarks") or "") == remarks]
    if stock == "low":
        rows = [r for r in rows if (r.get("stock_qty") or 0) <= LOW_STOCK]
    elif stock == "in":
        rows = [r for r in rows if (r.get("stock_qty") or 0) > 0]
    elif stock == "out":
        rows = [r for r in rows if (r.get("stock_qty") or 0) == 0]
    valid = {"product_no", "item_code", "description_brand", "stock_qty", "buy_price", "sale_price", "remarks"}
    if sort not in valid:
        sort = "product_no"
    rev = direction == "desc"
    rows.sort(key=lambda r: (r.get(sort) is None, r.get(sort) or 0 if isinstance(r.get(sort), (int, float)) else str(r.get(sort) or "").lower()), reverse=rev)
    return rows

def summary(rows):
    total_qty = sum(r.get("stock_qty") or 0 for r in rows)
    cost = sum((r.get("stock_qty") or 0) * float(r.get("buy_price") or 0) for r in rows)
    sale = sum((r.get("stock_qty") or 0) * float(r.get("sale_price") or 0) for r in rows)
    return {
        "total_skus": len(rows),
        "total_qty": total_qty,
        "cost": cost,
        "sale": sale,
        "profit": sale - cost,
        "margin_pct": round((sale - cost) / sale * 100, 1) if sale else 0,
        "low": sum(1 for r in rows if (r.get("stock_qty") or 0) <= LOW_STOCK),
    }

def distinct_remarks():
    res = supabase().table("products").select("remarks").execute()
    return sorted({r.get("remarks") for r in (res.data or []) if r.get("remarks")})

@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    remarks = request.args.get("remarks", "All")
    stock = request.args.get("stock", "All")
    sort = request.args.get("sort", "product_no")
    direction = request.args.get("dir", "asc")
    # Summary reflects ALL products, filtered table reflects filters
    all_rows = fetch_products()
    rows = fetch_products(search, remarks, stock, sort, direction)
    # Next no / code for Add modal
    max_no = max([r.get("product_no") or 0 for r in all_rows], default=0)
    max_code = 0
    for r in all_rows:
        try:
            max_code = max(max_code, int(str(r.get("item_code") or "").split("-")[1]))
        except:
            pass
    return render_template(
        "index.html",
        products=rows,
        stats=summary(all_rows),
        remarks_list=distinct_remarks(),
        q=search,
        remarks=remarks,
        stock=stock,
        sort=sort,
        direction=direction,
        next_no=max_no + 1,
        next_code=f"EL-{max_code + 1:03d}",
        low_stock=LOW_STOCK,
    )

@app.route("/adjust/<int:pid>", methods=["GET", "POST"])
# GET = safety net: a form that lost its method/action (e.g. JS failed) must redirect, never 405.
def adjust(pid):
    if request.method == "GET":
        return redirect(url_for("index"))
    delta = parse_int(request.form.get("delta"), 0)
    if delta not in (-1, 1):
        abort(400)
    cur = supabase().table("products").select("stock_qty,item_code").eq("id", pid).single().execute()
    if not cur.data:
        abort(404)
    new_qty = (cur.data.get("stock_qty") or 0) + delta
    if new_qty < 0:
        flash(f"Cannot go below 0 for {cur.data.get('item_code')}. Stock stays at 0.", "error")
        return redirect(url_for("index", **request.args))
    supabase().table("products").update({"stock_qty": new_qty}).eq("id", pid).execute()
    flash(f"{cur.data.get('item_code')} stock → {new_qty}", "success")
    return redirect(url_for("index", **request.args))

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "GET":
        return redirect(url_for("index"))
    data = {
        "product_no": parse_int(request.form.get("product_no")),
        "item_code": (request.form.get("item_code") or "").strip().upper(),
        "description_brand": (request.form.get("description_brand") or "").strip(),
        "specs_size": (request.form.get("specs_size") or "").strip() or None,
        "stock_qty": parse_int(request.form.get("stock_qty")),
        "buy_price": parse_num(request.form.get("buy_price")),
        "sale_price": parse_num(request.form.get("sale_price")),
        "remarks": (request.form.get("remarks") or "").strip() or None,
    }
    if not data["item_code"] or not data["description_brand"]:
        flash("Item Code and Description are required.", "error")
        return redirect(url_for("index"))
    if data["stock_qty"] < 0 or data["buy_price"] < 0 or data["sale_price"] < 0:
        flash("Quantity and prices cannot be negative.", "error")
        return redirect(url_for("index"))
    try:
        supabase().table("products").insert(data).execute()
        flash(f"Added {data['item_code']} — {data['description_brand']}", "success")
    except Exception as e:
        flash(f"Could not add product (duplicate code?): {e}", "error")
    return redirect(url_for("index"))

@app.route("/edit/<int:pid>", methods=["GET", "POST"])
def edit(pid):
    if request.method == "GET":
        return redirect(url_for("index"))
    data = {
        "description_brand": (request.form.get("description_brand") or "").strip(),
        "specs_size": (request.form.get("specs_size") or "").strip() or None,
        "stock_qty": parse_int(request.form.get("stock_qty")),
        "buy_price": parse_num(request.form.get("buy_price")),
        "sale_price": parse_num(request.form.get("sale_price")),
        "remarks": (request.form.get("remarks") or "").strip() or None,
    }
    if data["stock_qty"] < 0:
        flash("Stock cannot be negative.", "error")
        return redirect(url_for("index"))
    if not data["description_brand"]:
        flash("Description / Brand is required.", "error")
        return redirect(url_for("index"))
    try:
        supabase().table("products").update(data).eq("id", pid).execute()
        flash("Product updated.", "success")
    except Exception as e:
        flash(f"Could not update product: {e}", "error")
    return redirect(url_for("index"))

@app.route("/delete/<int:pid>", methods=["GET", "POST"])
def delete(pid):
    if request.method == "GET":
        return redirect(url_for("index"))
    supabase().table("products").delete().eq("id", pid).execute()
    flash("Product deleted.", "success")
    return redirect(url_for("index"))

@app.route("/export-xlsx")
def export_xlsx():
    try:
        import openpyxl
    except ImportError:
        flash("openpyxl not installed. Run: pip install openpyxl", "error")
        return redirect(url_for("index"))

    rows = fetch_products(
        request.args.get("q", "").strip(),
        request.args.get("remarks", "All"),
        request.args.get("stock", "All"),
        request.args.get("sort", "product_no"),
        request.args.get("dir", "asc"),
    )
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Stock Inventory"
    headers = [
        "No", "Item Code", "Description / Brand", "Specs / Size",
        "Stock Qty", "Buy Price", "Sale Price", "Remarks",
        "Stock Cost", "Sale Value"
    ]
    ws.append(headers)
    for r in rows:
        cost = (r.get("stock_qty") or 0) * float(r.get("buy_price") or 0)
        sale = (r.get("stock_qty") or 0) * float(r.get("sale_price") or 0)
        ws.append([
            r.get("product_no"),
            r.get("item_code"),
            r.get("description_brand"),
            r.get("specs_size"),
            r.get("stock_qty"),
            r.get("buy_price"),
            r.get("sale_price"),
            r.get("remarks"),
            cost,
            sale,
        ])
    wb.save(buf)
    buf.seek(0)
    filename = f"stock-export-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        download_name=filename,
        as_attachment=True,
    )

@app.route("/import-xlsx", methods=["GET", "POST"])
def import_xlsx():
    if request.method == "GET":
        return redirect(url_for("index"))
    try:
        from openpyxl import load_workbook
    except ImportError:
        flash("openpyxl not installed. Run: pip install openpyxl", "error")
        return redirect(url_for("index"))

    if "file" not in request.files:
        flash("No file part", "error")
        return redirect(url_for("index"))

    file = request.files["file"]
    if file.filename == "":
        flash("No selected file", "error")
        return redirect(url_for("index"))
    if not file.filename.lower().endswith(".xlsx"):
        flash("Only .xlsx files allowed", "error")
        return redirect(url_for("index"))

    def clean_num(val, default=0.0):
        if val is None or val == "":
            return default
        if isinstance(val, (int, float)):
            return float(val)
        try:
            return float(str(val).replace(",", "").strip())
        except ValueError:
            return default

    try:
        wb = load_workbook(file, data_only=True)
        ws = wb.active

        rows_by_code = {}
        skipped = 0

        for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not row or all(cell is None or str(cell).strip() == "" for cell in row):
                continue

            product_no = parse_int(clean_num(row[0], idx - 1)) if len(row) > 0 else idx - 1
            item_code = str(row[1]).strip().upper() if len(row) > 1 and row[1] is not None else ""
            description_brand = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
            specs_size = str(row[3]).strip() if len(row) > 3 and row[3] is not None else None
            stock_qty = int(clean_num(row[4], 0)) if len(row) > 4 else 0
            buy_price = clean_num(row[5], 0.0) if len(row) > 5 else 0.0
            sale_price = clean_num(row[6], 0.0) if len(row) > 6 else 0.0
            remarks = str(row[7]).strip() if len(row) > 7 and row[7] is not None else None

            if not item_code or not description_brand:
                skipped += 1
                continue

            if stock_qty < 0 or buy_price < 0 or sale_price < 0:
                flash(f"Row {idx} ({item_code}): Negative quantity or prices are not allowed.", "error")
                return redirect(url_for("index"))

            rows_by_code[item_code] = {
                "product_no": product_no,
                "item_code": item_code,
                "description_brand": description_brand,
                "specs_size": specs_size or None,
                "stock_qty": stock_qty,
                "buy_price": buy_price,
                "sale_price": sale_price,
                "remarks": remarks or None,
            }

        payload = list(rows_by_code.values())
        if not payload:
            flash("No valid product rows found in the XLSX file.", "error")
            return redirect(url_for("index"))

        supabase().table("products").upsert(payload, on_conflict="item_code").execute()

        msg = f"Imported/updated {len(payload)} products successfully."
        if skipped:
            msg += f" ({skipped} incomplete rows skipped)"
        flash(msg, "success")

    except Exception as e:
        flash(f"Import failed: {str(e)}", "error")

    return redirect(url_for("index"))

@app.route("/api/products")
def api_products():
    return jsonify(fetch_products(request.args.get("q", ""), request.args.get("remarks", "All"), request.args.get("stock", "All")))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
# Vercel serverless entrypoint imports this module: `from app import app` (see api/index.py).
# Do NOT call app.run() on Vercel — the `if __name__ == "__main__"` guard below already prevents it.
