from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os, functools

app = Flask(__name__)
app.secret_key = "shopsmart-secret-2026-change-this"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "shopsmart123"

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = bool(DATABASE_URL)

# SQLite fallback
if not USE_POSTGRES:
    import sqlite3
    DB = os.environ.get("DB_PATH", "/app/instance/products.db")
    os.makedirs(os.path.dirname(DB), exist_ok=True)

CATEGORIES = [
    {"key": "electronics",  "name": "Electronics",            "icon": "bi-phone"},
    {"key": "fashion",      "name": "Fashion",                "icon": "bi-bag"},
    {"key": "home",         "name": "Home & Kitchen",         "icon": "bi-house-door"},
    {"key": "beauty",       "name": "Beauty & Personal Care", "icon": "bi-droplet"},
    {"key": "books",        "name": "Books",                  "icon": "bi-book"},
    {"key": "sports",       "name": "Sports & Outdoors",      "icon": "bi-trophy"},
]

# ── DATABASE ──────────────────────────────────────────────────────────────────
def get_db():
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        conn = sqlite3.connect(DB, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

def db_execute(sql, params=()):
    conn = get_db()
    try:
        if USE_POSTGRES:
            sql = sql.replace("?", "%s")
            sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            sql = sql.replace("datetime('now')", "NOW()")
            sql = sql.replace("date('now')", "CURRENT_DATE")
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
        else:
            conn.execute(sql, params)
            conn.commit()
    finally:
        conn.close()

def db_fetch(sql, params=(), one=False):
    conn = get_db()
    try:
        if USE_POSTGRES:
            import psycopg2.extras
            sql = sql.replace("?", "%s")
            sql = sql.replace("datetime('now',", "NOW() + INTERVAL '")
            sql = sql.replace("date('now')", "CURRENT_DATE")
            sql = sql.replace("date(clicked_at)", "DATE(clicked_at)")
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                return cur.fetchone() if one else cur.fetchall()
        else:
            cur = conn.execute(sql, params)
            return cur.fetchone() if one else cur.fetchall()
    finally:
        conn.close()

def init_db():
    conn = get_db()
    try:
        if USE_POSTGRES:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        id          SERIAL PRIMARY KEY,
                        name        TEXT NOT NULL,
                        category    TEXT NOT NULL,
                        images      TEXT NOT NULL,
                        price       REAL NOT NULL,
                        old_price   REAL,
                        discount    TEXT,
                        rating      REAL DEFAULT 4.0,
                        reviews     INTEGER DEFAULT 0,
                        link        TEXT NOT NULL,
                        top_pick    INTEGER DEFAULT 0,
                        deal_of_day INTEGER DEFAULT 0
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS social_links (
                        id        SERIAL PRIMARY KEY,
                        platform  TEXT UNIQUE NOT NULL,
                        url       TEXT NOT NULL DEFAULT '#',
                        icon      TEXT NOT NULL,
                        visible   INTEGER DEFAULT 1
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS subscribers (
                        id         SERIAL PRIMARY KEY,
                        email      TEXT UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS clicks (
                        id           SERIAL PRIMARY KEY,
                        product_id   INTEGER,
                        product_name TEXT,
                        clicked_at   TIMESTAMP DEFAULT NOW()
                    )
                """)
                cur.execute("SELECT COUNT(*) FROM social_links")
                scount = cur.fetchone()[0]
                if scount == 0:
                    cur.executemany(
                        "INSERT INTO social_links (platform, url, icon, visible) VALUES (%s,%s,%s,%s)",
                        [
                            ("Facebook",  "#", "bi-facebook",  1),
                            ("Instagram", "#", "bi-instagram", 1),
                            ("YouTube",   "#", "bi-youtube",   1),
                            ("Twitter/X", "#", "bi-twitter-x", 1),
                        ]
                    )
                cur.execute("SELECT COUNT(*) FROM products")
                count = cur.fetchone()[0]
                if count == 0:
                    sample = [
                        ("Sony WH-1000XM5 Noise Cancelling Headphones", "electronics",
                         "https://m.media-amazon.com/images/I/61D6V1KV1RL._AC_SL1500_.jpg,"
                         "https://m.media-amazon.com/images/I/71o8Q5XJS5L._AC_SL1500_.jpg",
                         299.99, 399.99, "25% OFF", 4.6, 18432,
                         "https://www.amazon.com/dp/B09XS7JWHM?tag=YOUR-TAG-20", 1, 1),
                        ("Apple AirPods Pro (2nd Generation)", "electronics",
                         "https://m.media-amazon.com/images/I/61SUj2aKoEL._AC_SL1500_.jpg,"
                         "https://m.media-amazon.com/images/I/71zny7BTRlL._AC_SL1500_.jpg",
                         189.99, 249.00, "24% OFF", 4.7, 32100,
                         "https://www.amazon.com/dp/B0CHWRXH8B?tag=YOUR-TAG-20", 1, 0),
                        ("Fire-Boltt Ninja Smartwatch", "electronics",
                         "https://m.media-amazon.com/images/I/61c4N6yV1RL._AC_SL1500_.jpg,"
                         "https://m.media-amazon.com/images/I/71TRUPlZqNL._AC_SL1500_.jpg",
                         39.99, 79.99, "50% OFF", 4.1, 8765,
                         "https://www.amazon.com/dp/B0BSL2T8C8?tag=YOUR-TAG-20", 1, 1),
                        ("Levi's Men's 511 Slim Fit Jeans", "fashion",
                         "https://m.media-amazon.com/images/I/71q2ZWIU5oL._AC_UX679_.jpg,"
                         "https://m.media-amazon.com/images/I/81mNGIEqabL._AC_UX679_.jpg",
                         49.99, 79.50, "37% OFF", 4.5, 14200,
                         "https://www.amazon.com/dp/B00122DJLQ?tag=YOUR-TAG-20", 1, 0),
                        ("Nike Men's Running Shoes", "fashion",
                         "https://m.media-amazon.com/images/I/71gVk5vLiaL._AC_UX695_.jpg,"
                         "https://m.media-amazon.com/images/I/71pJ6LHzxlL._AC_UX695_.jpg",
                         89.99, 129.99, "31% OFF", 4.4, 9876,
                         "https://www.amazon.com/dp/B07NIKE567?tag=YOUR-TAG-20", 1, 1),
                        ("Instant Pot Duo 7-in-1 Pressure Cooker", "home",
                         "https://m.media-amazon.com/images/I/71V1Bqz7joL._AC_SL1500_.jpg,"
                         "https://m.media-amazon.com/images/I/81Vr6YkNiYL._AC_SL1500_.jpg",
                         79.99, 119.99, "33% OFF", 4.7, 52000,
                         "https://www.amazon.com/dp/B00FLYWNYQ?tag=YOUR-TAG-20", 1, 1),
                        ("COSORI Air Fryer 5.8QT", "home",
                         "https://m.media-amazon.com/images/I/71T-0k9IECL._AC_SL1500_.jpg,"
                         "https://m.media-amazon.com/images/I/71sBN5WZ8LL._AC_SL1500_.jpg",
                         99.99, 139.99, "29% OFF", 4.6, 31000,
                         "https://www.amazon.com/dp/B08WJMVQC9?tag=YOUR-TAG-20", 0, 1),
                        ("Neutrogena Hydro Boost Water Gel", "beauty",
                         "https://m.media-amazon.com/images/I/61vJjfmRMsL._SL1500_.jpg",
                         18.99, 27.99, "32% OFF", 4.5, 22000,
                         "https://www.amazon.com/dp/B00NR1YQHM?tag=YOUR-TAG-20", 0, 0),
                    ]
                    cur.executemany("""
                        INSERT INTO products
                        (name,category,images,price,old_price,discount,rating,reviews,link,top_pick,deal_of_day)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, sample)
            conn.commit()
        else:
            import sqlite3
            conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                    category TEXT NOT NULL, images TEXT NOT NULL, price REAL NOT NULL,
                    old_price REAL, discount TEXT, rating REAL DEFAULT 4.0,
                    reviews INTEGER DEFAULT 0, link TEXT NOT NULL,
                    top_pick INTEGER DEFAULT 0, deal_of_day INTEGER DEFAULT 0)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS social_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT UNIQUE NOT NULL,
                    url TEXT NOT NULL DEFAULT '#', icon TEXT NOT NULL, visible INTEGER DEFAULT 1)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')))
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clicks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER,
                    product_name TEXT, clicked_at TEXT DEFAULT (datetime('now')))
            """)
            scount = conn.execute("SELECT COUNT(*) FROM social_links").fetchone()[0]
            if scount == 0:
                conn.executemany(
                    "INSERT INTO social_links (platform, url, icon, visible) VALUES (?,?,?,?)",
                    [("Facebook","#","bi-facebook",1),("Instagram","#","bi-instagram",1),
                     ("YouTube","#","bi-youtube",1),("Twitter/X","#","bi-twitter-x",1)]
                )
            count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            if count == 0:
                sample = [
                    ("Sony WH-1000XM5 Noise Cancelling Headphones","electronics",
                     "https://m.media-amazon.com/images/I/61D6V1KV1RL._AC_SL1500_.jpg,"
                     "https://m.media-amazon.com/images/I/71o8Q5XJS5L._AC_SL1500_.jpg",
                     299.99,399.99,"25% OFF",4.6,18432,"https://www.amazon.com/dp/B09XS7JWHM?tag=YOUR-TAG-20",1,1),
                    ("Apple AirPods Pro (2nd Generation)","electronics",
                     "https://m.media-amazon.com/images/I/61SUj2aKoEL._AC_SL1500_.jpg,"
                     "https://m.media-amazon.com/images/I/71zny7BTRlL._AC_SL1500_.jpg",
                     189.99,249.00,"24% OFF",4.7,32100,"https://www.amazon.com/dp/B0CHWRXH8B?tag=YOUR-TAG-20",1,0),
                    ("Fire-Boltt Ninja Smartwatch","electronics",
                     "https://m.media-amazon.com/images/I/61c4N6yV1RL._AC_SL1500_.jpg,"
                     "https://m.media-amazon.com/images/I/71TRUPlZqNL._AC_SL1500_.jpg",
                     39.99,79.99,"50% OFF",4.1,8765,"https://www.amazon.com/dp/B0BSL2T8C8?tag=YOUR-TAG-20",1,1),
                ]
                conn.executemany("""
                    INSERT INTO products
                    (name,category,images,price,old_price,discount,rating,reviews,link,top_pick,deal_of_day)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, sample)
            conn.commit()
    finally:
        conn.close()

init_db()

# ── SEO META ──────────────────────────────────────────────────────────────────
SEO_META = {
    "home":       "ShopSmart - Discover the best Amazon deals, top-rated products and exclusive discounts. Handpicked recommendations updated daily.",
    "categories": "Browse all product categories on ShopSmart — Electronics, Fashion, Home and Kitchen, Beauty, Sports and more. Best Amazon deals in one place.",
    "top_deals":  "Top Amazon deals today — Limited time offers, massive discounts up to 70% off on Electronics, Fashion, Home products and more.",
    "about":      "About ShopSmart — We handpick the best products on Amazon and share them through affiliate links. Your trusted deal-finding partner.",
    "privacy":    "ShopSmart Privacy Policy — How we collect, use and protect your information. We never sell your personal data.",
    "disclaimer": "ShopSmart Affiliate Disclaimer — We earn from qualifying Amazon purchases at no extra cost to you. Full transparency guaranteed.",
    "terms":      "ShopSmart Terms of Use — Rules and guidelines for using our website.",
    "blog":       "ShopSmart Blog — Amazon buying guides, money saving tips, product reviews and deal alerts to help you shop smarter.",
    "search":     "Search results on ShopSmart — Find the best Amazon deals for any product.",
}

@app.route("/sitemap.xml")
def sitemap():
    from flask import Response
    import datetime
    today = datetime.date.today().isoformat()
    pages = [("","1.0"),("categories","0.9"),("top-deals","0.9"),("blog","0.8"),
             ("about","0.7"),("privacy-policy","0.3"),("affiliate-disclaimer","0.3"),("terms-of-use","0.3")]
    base = request.host_url.rstrip("/")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    for path, priority in pages:
        url = base if not path else f"{base}/{path}"
        xml += f"\n  <url><loc>{url}</loc><lastmod>{today}</lastmod><priority>{priority}</priority></url>"
    xml += "\n</urlset>"
    return Response(xml, mimetype="application/xml")

@app.route("/robots.txt")
def robots():
    from flask import Response
    txt = f"User-agent: *\nAllow: /\nDisallow: /0289472776admin\nDisallow: /api/\n\nSitemap: {request.host_url}sitemap.xml"
    return Response(txt, mimetype="text/plain")

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

def row_to_dict(row):
    if USE_POSTGRES:
        d = dict(row)
    else:
        d = dict(row)
    raw = d.get("images", "") or ""
    d["image_list"] = [u.strip() for u in raw.split(",") if u.strip()]
    return d

def get_social_links():
    rows = db_fetch("SELECT * FROM social_links WHERE visible=1 ORDER BY id")
    return [dict(r) for r in rows]

@app.context_processor
def inject_globals():
    return {"social_links": get_social_links()}

@app.route("/")
def home():
    rows = db_fetch("SELECT * FROM products WHERE top_pick=1 LIMIT 8")
    products = [row_to_dict(r) for r in rows]
    return render_template("home.html", products=products, categories=CATEGORIES, meta_desc=SEO_META["home"])

@app.route("/categories")
@app.route("/categories/<cat_key>")
def categories(cat_key=None):
    if cat_key:
        rows = db_fetch("SELECT * FROM products WHERE category=?", (cat_key,))
        cat_name = next((c["name"] for c in CATEGORIES if c["key"] == cat_key), "Category")
    else:
        rows = db_fetch("SELECT * FROM products")
        cat_key = "all"
        cat_name = "All Products"
    products = [row_to_dict(r) for r in rows]
    return render_template("categories.html", products=products, categories=CATEGORIES,
                           active_cat=cat_key, cat_name=cat_name, meta_desc=SEO_META["categories"])

@app.route("/top-deals")
def top_deals():
    rows = db_fetch("SELECT * FROM products WHERE deal_of_day=1")
    products = [row_to_dict(r) for r in rows]
    return render_template("top_deals.html", products=products, categories=CATEGORIES, meta_desc=SEO_META["top_deals"])

@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if q:
        rows = db_fetch("SELECT * FROM products WHERE name LIKE ? OR category LIKE ?",
                        (f"%{q}%", f"%{q}%"))
    else:
        rows = []
    products = [row_to_dict(r) for r in rows]
    return render_template("search.html", products=products, query=q, categories=CATEGORIES)

@app.route("/about")
def about():
    return render_template("about.html", categories=CATEGORIES, meta_desc=SEO_META["about"])

@app.route("/privacy-policy")
def privacy():
    return render_template("privacy.html", categories=CATEGORIES, meta_desc=SEO_META["privacy"])

@app.route("/affiliate-disclaimer")
def disclaimer():
    return render_template("disclaimer.html", categories=CATEGORIES, meta_desc=SEO_META["disclaimer"])

@app.route("/terms-of-use")
def terms():
    return render_template("terms.html", categories=CATEGORIES, meta_desc=SEO_META["terms"])

@app.route("/blog")
def blog():
    return render_template("blog.html", categories=CATEGORIES, meta_desc=SEO_META["blog"])

@app.route("/blog/<slug>")
def blog_post(slug):
    return render_template(f"blog_{slug}.html", categories=CATEGORIES)

@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])
    rows = db_fetch("SELECT id, name, category, images, price FROM products")
    starts, others = [], []
    for r in rows:
        d = dict(r)
        name_lower = d["name"].lower()
        if name_lower.startswith(q):
            starts.append(d)
        elif q in name_lower:
            others.append(d)
    results = []
    for r in starts + others:
        imgs = [u.strip() for u in (r["images"] or "").split(",") if u.strip()]
        results.append({"id": r["id"], "name": r["name"], "cat": r["category"],
                        "image": imgs[0] if imgs else "", "price": r["price"]})
    return jsonify(results[:8])

@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = request.form.get("email", "").strip().lower()
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if not email or "@" not in email:
        if is_ajax:
            return jsonify({"status": "error"})
        flash("❌ Valid email enter karein.", "danger")
        return redirect(request.referrer or url_for("home"))
    try:
        db_execute("INSERT INTO subscribers (email) VALUES (?)", (email,))
        if is_ajax:
            return jsonify({"status": "success"})
        flash("subscribed_ok", "success")
    except Exception:
        if is_ajax:
            return jsonify({"status": "already"})
        flash("subscribed_already", "info")
    return redirect(request.referrer or url_for("home"))

@app.route("/track-click", methods=["POST"])
def track_click():
    pid = request.form.get("pid", "")
    name = request.form.get("name", "")
    db_execute("INSERT INTO clicks (product_id, product_name) VALUES (?,?)", (pid, name))
    return jsonify({"status": "ok"})

@app.route("/0289472776admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if (request.form["username"] == ADMIN_USERNAME and
                request.form["password"] == ADMIN_PASSWORD):
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        flash("❌ Wrong username or password!", "danger")
    return render_template("admin/login.html")

@app.route("/0289472776admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/0289472776admin")
@login_required
def admin_dashboard():
    conn = get_db()
    try:
        if USE_POSTGRES:
            import psycopg2.extras
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM products ORDER BY id DESC")
                products = [row_to_dict(r) for r in cur.fetchall()]
                cur.execute("SELECT * FROM subscribers ORDER BY created_at DESC")
                subscribers = cur.fetchall()
                cur.execute("SELECT * FROM social_links ORDER BY id")
                social = cur.fetchall()
                filter_val = request.args.get("filter", "all")
                date_filter = ""
                if filter_val == "today":
                    date_filter = "AND DATE(clicked_at) = CURRENT_DATE"
                elif filter_val == "yesterday":
                    date_filter = "AND DATE(clicked_at) = CURRENT_DATE - INTERVAL '1 day'"
                elif filter_val == "week":
                    date_filter = "AND clicked_at >= NOW() - INTERVAL '7 days'"
                elif filter_val == "month":
                    date_filter = "AND clicked_at >= NOW() - INTERVAL '30 days'"
                elif filter_val == "6month":
                    date_filter = "AND clicked_at >= NOW() - INTERVAL '180 days'"
                elif filter_val == "year":
                    date_filter = "AND clicked_at >= NOW() - INTERVAL '365 days'"
                cur.execute(f"SELECT COUNT(*) FROM clicks WHERE 1=1 {date_filter}")
                total_clicks = cur.fetchone()["count"]
                cur.execute(f"""
                    SELECT product_name, COUNT(*) as cnt FROM clicks
                    WHERE 1=1 {date_filter}
                    GROUP BY product_name ORDER BY cnt DESC LIMIT 5
                """)
                top_clicked = cur.fetchall()
        else:
            products = [row_to_dict(r) for r in conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()]
            subscribers = conn.execute("SELECT * FROM subscribers ORDER BY created_at DESC").fetchall()
            social = conn.execute("SELECT * FROM social_links ORDER BY id").fetchall()
            filter_val = request.args.get("filter", "all")
            if filter_val == "today":
                date_filter = "AND date(clicked_at) = date('now')"
            elif filter_val == "yesterday":
                date_filter = "AND date(clicked_at) = date('now','-1 day')"
            elif filter_val == "week":
                date_filter = "AND clicked_at >= datetime('now','-7 days')"
            elif filter_val == "month":
                date_filter = "AND clicked_at >= datetime('now','-30 days')"
            elif filter_val == "6month":
                date_filter = "AND clicked_at >= datetime('now','-180 days')"
            elif filter_val == "year":
                date_filter = "AND clicked_at >= datetime('now','-365 days')"
            else:
                date_filter = ""
            total_clicks = conn.execute(f"SELECT COUNT(*) FROM clicks WHERE 1=1 {date_filter}").fetchone()[0]
            top_clicked = conn.execute(f"""
                SELECT product_name, COUNT(*) as cnt FROM clicks
                WHERE 1=1 {date_filter}
                GROUP BY product_name ORDER BY cnt DESC LIMIT 5
            """).fetchall()
    finally:
        conn.close()
    return render_template("admin/dashboard.html",
                           products=products, categories=CATEGORIES,
                           subscribers=subscribers, social_settings=social,
                           total_clicks=total_clicks, top_clicked=top_clicked,
                           active_filter=filter_val)

@app.route("/0289472776admin/add", methods=["GET", "POST"])
@login_required
def admin_add():
    if request.method == "POST":
        f = request.form
        imgs = [f.get(f"image{i}", "").strip() for i in range(1, 4)]
        images_str = ",".join(i for i in imgs if i) or "https://placehold.co/400x500/eef0ff/6c63ff?text=No+Image"
        db_execute("""
            INSERT INTO products
            (name,category,images,price,old_price,discount,rating,reviews,link,top_pick,deal_of_day)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (f["name"], f["category"], images_str, float(f["price"]),
              float(f["old_price"]) if f["old_price"] else None, f["discount"],
              float(f["rating"]), int(f["reviews"]) if f["reviews"] else 0,
              f["link"], 1 if f.get("top_pick") else 0, 1 if f.get("deal_of_day") else 0))
        flash("✅ Product successfully added!", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/add_product.html", categories=CATEGORIES)

@app.route("/0289472776admin/edit/<int:pid>", methods=["GET", "POST"])
@login_required
def admin_edit(pid):
    product = row_to_dict(db_fetch("SELECT * FROM products WHERE id=?", (pid,), one=True))
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        f = request.form
        imgs = [f.get(f"image{i}", "").strip() for i in range(1, 4)]
        images_str = ",".join(i for i in imgs if i) or product["images"]
        db_execute("""
            UPDATE products SET name=?, category=?, images=?, price=?, old_price=?,
            discount=?, rating=?, reviews=?, link=?, top_pick=?, deal_of_day=? WHERE id=?
        """, (f["name"], f["category"], images_str, float(f["price"]),
              float(f["old_price"]) if f["old_price"] else None, f["discount"],
              float(f["rating"]), int(f["reviews"]) if f["reviews"] else 0,
              f["link"], 1 if f.get("top_pick") else 0, 1 if f.get("deal_of_day") else 0, pid))
        flash("✅ Product updated!", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/add_product.html", product=product, categories=CATEGORIES, edit=True)

@app.route("/0289472776admin/delete/<int:pid>", methods=["POST"])
@login_required
def admin_delete(pid):
    db_execute("DELETE FROM products WHERE id=?", (pid,))
    flash("🗑️ Product deleted.", "info")
    return redirect(url_for("admin_dashboard"))

@app.route("/0289472776admin/social", methods=["POST"])
@login_required
def admin_social():
    conn = get_db()
    try:
        if USE_POSTGRES:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM social_links")
                social = cur.fetchall()
                for s in social:
                    sid = s[0]
                    url = request.form.get(f"url_{sid}", "#").strip() or "#"
                    visible = 1 if request.form.get(f"visible_{sid}") else 0
                    cur.execute("UPDATE social_links SET url=%s, visible=%s WHERE id=%s", (url, visible, sid))
        else:
            social = conn.execute("SELECT * FROM social_links").fetchall()
            for s in social:
                url = request.form.get(f"url_{s['id']}", "#").strip() or "#"
                visible = 1 if request.form.get(f"visible_{s['id']}") else 0
                conn.execute("UPDATE social_links SET url=?, visible=? WHERE id=?", (url, visible, s['id']))
        conn.commit()
    finally:
        conn.close()
    flash("✅ Social links updated!", "success")
    return redirect(url_for("admin_dashboard") + "#social")

@app.route("/0289472776admin/subscriber/delete/<int:sid>", methods=["POST"])
@login_required
def admin_delete_subscriber(sid):
    db_execute("DELETE FROM subscribers WHERE id=?", (sid,))
    flash("🗑️ Subscriber removed.", "info")
    return redirect(url_for("admin_dashboard") + "#subscribers")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)