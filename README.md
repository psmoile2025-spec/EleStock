<div align="center">

# ⚡ Electronic Products — Stock View & Inventory

**Real-time stock viewing, live search, profit calculation, and XLSX import/export built with Python Flask & Supabase.**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Web%20App-000000?style=for-the-badge&logo=flask&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-UI-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)

</div>

---

## ✨ Key Features

* **📊 Summary Dashboard:** Displays Total SKUs, Total Stock Qty, Stock Cost, Sale Value, Estimated Profit & Margin %, and Low Stock count at a glance.
* **🔍 Instant Live Search:** Filter products in real time by `item_code`, `description_brand`, `specs_size`, or `remarks` with a quick clear button.
* **🃏 1-Column Colorful Product Cards:** Clean single-column layout highlighting origin (`China` / `Thailand`), low-stock warnings, stock quantity, buy/sale prices, and per-unit / total profit.
* **➕ Add, Edit & Delete Products:** Modal-based product creation with auto-suggested next `product_no` and `EL-xxx` code, reusable edit modal, and delete confirmation.
* **📥 Import & 📤 Export XLSX:** Upload `.xlsx` spreadsheets via modal with automatic `upsert` on `item_code` (no duplicate errors) and export inventory data to `.xlsx`.
* **🔌 JSON API Endpoint:** Exposes `/api/products` for querying inventory data programmatically.

---

## 🗂️ Project Structure

```text
electronic-stock-view/
├── app.py                  # Flask routes, Supabase client, XLSX import/export & summary logic
├── seed.py                 # Initial seed script for sample electronic items (EL-001 to EL-045)
├── schema.sql              # Supabase PostgreSQL table, indexes & updated_at trigger
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── static/                 # Optional static assets (e.g., favicon.png)
└── templates/
    ├── base.html           # Sticky header, favicon, Import XLSX modal & toast notifications
    └── index.html          # Summary cards, live search, 1-column cards & Add/Edit modals