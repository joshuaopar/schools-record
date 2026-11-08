import csv
import io
import os
import sqlite3
from datetime import date
from urllib.parse import quote

from flask import (Flask, Response, redirect, render_template_string,
                   request, send_file, session)

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
PASSWORD = os.environ.get("RECORDS_PASSWORD", "demo1234")  # change this
SCHOOL = "Your Aviation School"  # change this
DB = "records.db"


@app.template_filter("money")
def money(x):
    return "{:,.0f}".format(x or 0)


@app.template_filter("wa")
def wa(student):
    """WhatsApp link with a ready reminder message."""
    phone = "".join(c for c in (student["phone"] or "") if c.isdigit())
    if not phone:
        return ""
    if phone.startswith("0"):
        phone = "256" + phone[1:]
    msg = (f"Dear {student['name']}, this is a friendly reminder from {SCHOOL}. "
           f"Your outstanding fee balance is UGX {student['balance']:,.0f}. Thank you.")
    return f"https://wa.me/{phone}?text={quote(msg)}"


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def setup():
    conn = db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            phone TEXT, course TEXT, total_fee REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
            amount REAL NOT NULL, paid_on TEXT);
        CREATE TABLE IF NOT EXISTS licences (
            id INTEGER PRIMARY KEY AUTOINCREMENT, person TEXT NOT NULL,
            doc_type TEXT NOT NULL, expiry_date TEXT NOT NULL, notes TEXT);
    """)
    conn.commit()
    conn.close()


STYLE = """
<style>
:root { --bg:#f5f5f7; --card:#fff; --text:#1d1d1f; --muted:#6e6e73; --line:#e8e8ed;
        --blue:#0071e3; --red:#d70015; --green:#248a3d; --orange:#c93400; --yellow:#9a6700;
        --bar:rgba(255,255,255,.72); }
@media (prefers-color-scheme: dark) {
  :root { --bg:#000; --card:#1c1c1e; --text:#f5f5f7; --muted:#98989d; --line:#38383a;
          --blue:#2997ff; --red:#ff453a; --green:#30d158; --orange:#ff9f0a; --yellow:#ffd60a;
          --bar:rgba(28,28,30,.72); } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased; }
header { position:sticky; top:0; z-index:10; background:var(--bar);
  backdrop-filter:saturate(180%) blur(20px); -webkit-backdrop-filter:saturate(180%) blur(20px);
  border-bottom:1px solid var(--line); padding:12px 20px; display:flex;
  align-items:center; gap:20px; flex-wrap:wrap; }
header b { font-size:17px; letter-spacing:-.2px; }
header nav { display:flex; gap:18px; flex:1; flex-wrap:wrap; }
header a { color:var(--text); text-decoration:none; font-size:14px; opacity:.8; }
header a:hover { opacity:1; color:var(--blue); }
main { max-width:980px; margin:0 auto; padding:24px 16px 60px; }
h1 { font-size:32px; letter-spacing:-.6px; margin:8px 0 18px; }
h2 { letter-spacing:-.4px; margin:0 0 8px; }
.card { background:var(--card); border-radius:18px; padding:18px; margin-bottom:16px;
  box-shadow:0 1px 3px rgba(0,0,0,.06); }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:16px; }
.stat { background:var(--card); border-radius:18px; padding:16px; box-shadow:0 1px 3px rgba(0,0,0,.06); }
.stat .n { font-size:26px; font-weight:600; letter-spacing:-.5px; }
.stat .l { color:var(--muted); font-size:13px; margin-top:2px; }
table { width:100%; border-collapse:collapse; }
th { text-align:left; font-size:12px; text-transform:uppercase; letter-spacing:.5px;
  color:var(--muted); font-weight:600; padding:8px 10px; border-bottom:1px solid var(--line); }
td { padding:12px 10px; border-bottom:1px solid var(--line); font-size:15px; }
tr:last-child td { border-bottom:0; }
a { color:var(--blue); text-decoration:none; }
input, select { padding:11px 14px; margin:4px 4px 4px 0; border:1px solid var(--line);
  border-radius:12px; font-size:15px; background:var(--bg); color:var(--text);
  font-family:inherit; }
input:focus, select:focus { outline:2px solid var(--blue); border-color:transparent; }
button, .btn { padding:10px 18px; background:var(--blue); color:#fff; border:0;
  border-radius:980px; font-size:14px; cursor:pointer; font-family:inherit; display:inline-block; }
button.del { background:transparent; color:var(--red); padding:6px 10px; }
.btn.green { background:#25d366; }
.btn.gray { background:var(--line); color:var(--text); }
.red { color:var(--red); font-weight:600; } .green { color:var(--green); font-weight:600; }
.orange { color:var(--orange); font-weight:600; } .yellow { color:var(--yellow); font-weight:600; }
form.inline { display:inline; } .muted { color:var(--muted); font-size:13px; }
.scroll { overflow-x:auto; }
</style>
"""

LAYOUT = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>School Records</title>""" + STYLE + """</head><body>
<header><b>&#9992;&#65039; School Records</b>
<nav><a href="/">Students</a><a href="/expiry">Licences &amp; medicals</a>
<a href="/backup">Backup</a></nav><a href="/logout">Log out</a></header>
<main>{{ body|safe }}</main></body></html>"""

LOGIN = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Log in</title>""" + STYLE + """</head><body>
<main style="max-width:360px;padding-top:12vh;text-align:center">
<div style="font-size:48px">&#9992;&#65039;</div><h1>School Records</h1>
<div class="card"><form method="post">
<input type="password" name="password" placeholder="Password" style="width:100%" autofocus>
{% if error %}<p class="red">Wrong password</p>{% endif %}
<button style="width:100%;margin-top:8px">Sign in</button></form></div></main></body></html>"""

RECEIPT = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Receipt</title>""" + STYLE + """
<style>@media print { .noprint { display:none } body { background:#fff } .card { box-shadow:none } }</style>
</head><body><main style="max-width:520px">
<div class="card"><h2>{{ school }}</h2><p class="muted">Payment receipt</p><hr style="border:0;border-top:1px solid var(--line)">
<table>
<tr><td>Receipt no.</td><td><b>R-{{ '%05d' % p.id }}</b></td></tr>
<tr><td>Date</td><td>{{ p.paid_on }}</td></tr>
<tr><td>Received from</td><td>{{ s.name }}</td></tr>
<tr><td>Course</td><td>{{ s.course or '-' }}</td></tr>
<tr><td>Amount paid</td><td><b>UGX {{ p.amount|money }}</b></td></tr>
<tr><td>Balance after payment</td><td>UGX {{ balance|money }}</td></tr></table>
<p class="muted" style="margin-top:24px">Signed: ______________________</p></div>
<p class="noprint"><button onclick="window.print()">Print receipt</button>
<a class="btn gray" href="/student/{{ s.id }}">Back</a></p></main></body></html>"""

HOME = """
<h1>Students &amp; fees</h1>
<div class="grid">
  <div class="stat"><div class="n">{{ count }}</div><div class="l">Students</div></div>
  <div class="stat"><div class="n">{{ total|money }}</div><div class="l">Expected (UGX)</div></div>
  <div class="stat"><div class="n green">{{ paid|money }}</div><div class="l">Collected (UGX)</div></div>
  <div class="stat"><div class="n red">{{ (total - paid)|money }}</div><div class="l">Outstanding (UGX)</div></div>
  <div class="stat"><div class="n {{ 'red' if due_soon else 'green' }}">{{ due_soon }}</div>
    <div class="l"><a href="/expiry">Documents due in 30 days</a></div></div>
</div>
<div class="card">
  <form method="post" action="/add">
    <input name="name" placeholder="Student name" required>
    <input name="phone" placeholder="Phone (07...)">
    <input name="course" placeholder="Course">
    <input name="total_fee" type="number" step="any" min="0" placeholder="Total fee (UGX)" required>
    <button>Add student</button>
  </form>
</div>
<div class="card">
  <form method="get" action="/">
    <input name="q" placeholder="Search by name" value="{{ q }}">
    <button>Search</button>
    <a href="/export" style="margin-left:12px">Download CSV</a>
  </form>
</div>
<div class="card scroll"><table>
  <tr><th>Name</th><th>Course</th><th>Total</th><th>Paid</th><th>Balance</th><th></th></tr>
  {% for r in rows %}
  <tr>
    <td><a href="/student/{{ r.id }}">{{ r.name }}</a></td>
    <td>{{ r.course or '' }}</td><td>{{ r.total_fee|money }}</td><td>{{ r.paid|money }}</td>
    <td class="{{ 'red' if r.balance > 0 else 'green' }}">{{ r.balance|money }}</td>
    <td>{% if r.balance > 0 and (r|wa) %}<a class="btn green" target="_blank" href="{{ r|wa }}">Remind</a>{% endif %}</td>
  </tr>
  {% else %}<tr><td colspan="6">No students yet. Add one above.</td></tr>{% endfor %}
</table></div>
"""

DETAIL = """
<div class="card">
  <h2>{{ s.name }}</h2>
  <p class="muted">Phone: {{ s.phone or '-' }} &nbsp;|&nbsp; Course: {{ s.course or '-' }}</p>
  <p>Total {{ s.total_fee|money }} &nbsp;|&nbsp; Paid {{ paid|money }} &nbsp;|&nbsp;
     Balance <span class="{{ 'red' if balance > 0 else 'green' }}">{{ balance|money }}</span></p>
  <form method="post" action="/student/{{ s.id }}/pay">
    <input name="amount" type="number" step="any" min="1" placeholder="Amount paid" required>
    <button>Record payment</button>
  </form>
  <p>
    {% if link and balance > 0 %}<a class="btn green" target="_blank" href="{{ link }}">WhatsApp reminder</a>{% endif %}
    <a class="btn gray" href="/student/{{ s.id }}/edit">Edit</a>
    <form class="inline" method="post" action="/student/{{ s.id }}/delete"
          onsubmit="return confirm('Delete this student and all payments?')">
      <button class="del">Delete student</button></form>
  </p>
</div>
<div class="card"><h2>Payment history</h2><table>
  <tr><th>Date</th><th>Amount</th><th></th></tr>
  {% for p in payments %}
  <tr><td>{{ p.paid_on }}</td><td>{{ p.amount|money }}</td>
    <td><a href="/receipt/{{ p.id }}" target="_blank">Receipt</a>
      <form class="inline" method="post" action="/payment/{{ p.id }}/delete"
            onsubmit="return confirm('Delete this payment?')"><button class="del">Delete</button></form></td></tr>
  {% else %}<tr><td colspan="3">No payments yet.</td></tr>{% endfor %}
</table></div>
<p><a href="/">&larr; All students</a></p>
"""

EDIT = """
<div class="card"><h2>Edit student</h2>
  <form method="post">
    <input name="name" value="{{ s.name }}" required>
    <input name="phone" value="{{ s.phone or '' }}" placeholder="Phone">
    <input name="course" value="{{ s.course or '' }}" placeholder="Course">
    <input name="total_fee" type="number" step="any" min="0" value="{{ s.total_fee }}" required>
    <button>Save</button>
  </form></div>
<p><a href="/student/{{ s.id }}">Cancel</a></p>
"""

EXPIRY = """
<h1>Licences &amp; medicals</h1>
<div class="card"><form method="post" action="/expiry/add">
  <input name="person" placeholder="Person" required>
  <select name="doc_type"><option>Medical certificate</option><option>Pilot licence</option>
    <option>Engineer licence</option><option>Instructor rating</option><option>Other</option></select>
  <input name="expiry_date" type="date" required>
  <input name="notes" placeholder="Notes (optional)">
  <button>Add</button></form></div>
<div class="card scroll"><table>
  <tr><th>Person</th><th>Document</th><th>Expires</th><th>Status</th><th>Notes</th><th></th></tr>
  {% for l in items %}
  <tr><td>{{ l.person }}</td><td>{{ l.doc_type }}</td><td>{{ l.expiry_date }}</td>
    <td class="{{ l.css }}">{{ l.label }}</td><td>{{ l.notes or '' }}</td>
    <td><form class="inline" method="post" action="/expiry/{{ l.id }}/delete"
          onsubmit="return confirm('Delete this entry?')"><button class="del">Delete</button></form></td></tr>
  {% else %}<tr><td colspan="6">Nothing added yet.</td></tr>{% endfor %}
</table></div>
<p class="muted">Red = expired &middot; orange = within 30 days &middot; yellow = within 60 days &middot; green = fine</p>
"""


def page(tpl, **ctx):
    return render_template_string(LAYOUT, body=render_template_string(tpl, **ctx))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def licence_items():
    conn = db()
    rows = conn.execute("SELECT * FROM licences ORDER BY expiry_date").fetchall()
    conn.close()
    items = []
    for r in rows:
        try:
            days = (date.fromisoformat(r["expiry_date"]) - date.today()).days
        except ValueError:
            days = 9999
        if days < 0:
            css, label = "red", f"Expired {-days} days ago"
        elif days <= 30:
            css, label = "orange", f"Due in {days} days"
        elif days <= 60:
            css, label = "yellow", f"Due in {days} days"
        else:
            css, label = "green", f"Valid ({days} days left)"
        d = dict(r)
        d.update(days=days, css=css, label=label)
        items.append(d)
    return items


@app.before_request
def require_login():
    if request.endpoint not in ("login", "static") and not session.get("ok"):
        return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session["ok"] = True
            return redirect("/")
        return render_template_string(LOGIN, error=True)
    return render_template_string(LOGIN, error=False)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    conn = db()
    raw = conn.execute(
        """SELECT s.id, s.name, s.phone, s.course, s.total_fee,
                  COALESCE(SUM(p.amount), 0) AS paid
           FROM students s LEFT JOIN payments p ON p.student_id = s.id
           WHERE s.name LIKE ? GROUP BY s.id ORDER BY s.name""", (f"%{q}%",)).fetchall()
    conn.close()
    rows = []
    for r in raw:
        d = dict(r)
        d["balance"] = d["total_fee"] - d["paid"]
        rows.append(d)
    due = sum(1 for i in licence_items() if i["days"] <= 30)
    return page(HOME, rows=rows, q=q, count=len(rows),
                total=sum(r["total_fee"] for r in rows),
                paid=sum(r["paid"] for r in rows), due_soon=due)


@app.route("/add", methods=["POST"])
def add():
    name = request.form.get("name", "").strip()
    if name:
        conn = db()
        conn.execute("INSERT INTO students (name, phone, course, total_fee) VALUES (?,?,?,?)",
                     (name, request.form.get("phone", "").strip(),
                      request.form.get("course", "").strip(), num(request.form.get("total_fee"))))
        conn.commit()
        conn.close()
    return redirect("/")


def load_student(sid):
    conn = db()
    s = conn.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    pays = conn.execute("SELECT * FROM payments WHERE student_id = ? ORDER BY id DESC", (sid,)).fetchall()
    conn.close()
    return s, pays


@app.route("/student/<int:sid>")
def student(sid):
    s, pays = load_student(sid)
    if s is None:
        return redirect("/")
    paid = sum(p["amount"] for p in pays)
    balance = s["total_fee"] - paid
    link = wa({"name": s["name"], "phone": s["phone"], "balance": balance})
    return page(DETAIL, s=s, payments=pays, paid=paid, balance=balance, link=link)


@app.route("/student/<int:sid>/pay", methods=["POST"])
def pay(sid):
    amount = num(request.form.get("amount"))
    if amount > 0:
        conn = db()
        conn.execute("INSERT INTO payments (student_id, amount, paid_on) VALUES (?,?,?)",
                     (sid, amount, date.today().isoformat()))
        conn.commit()
        conn.close()
    return redirect(f"/student/{sid}")


@app.route("/receipt/<int:pid>")
def receipt(pid):
    conn = db()
    p = conn.execute("SELECT * FROM payments WHERE id = ?", (pid,)).fetchone()
    conn.close()
    if p is None:
        return redirect("/")
    s, pays = load_student(p["student_id"])
    balance = s["total_fee"] - sum(x["amount"] for x in pays if x["id"] <= p["id"])
    return render_template_string(RECEIPT, p=p, s=s, balance=balance, school=SCHOOL)


@app.route("/student/<int:sid>/edit", methods=["GET", "POST"])
def edit(sid):
    s, _ = load_student(sid)
    if s is None:
        return redirect("/")
    if request.method == "POST":
        conn = db()
        conn.execute("UPDATE students SET name=?, phone=?, course=?, total_fee=? WHERE id=?",
                     (request.form.get("name", "").strip() or s["name"],
                      request.form.get("phone", "").strip(),
                      request.form.get("course", "").strip(),
                      num(request.form.get("total_fee")), sid))
        conn.commit()
        conn.close()
        return redirect(f"/student/{sid}")
    return page(EDIT, s=s)


@app.route("/student/<int:sid>/delete", methods=["POST"])
def delete_student(sid):
    conn = db()
    conn.execute("DELETE FROM payments WHERE student_id = ?", (sid,))
    conn.execute("DELETE FROM students WHERE id = ?", (sid,))
    conn.commit()
    conn.close()
    return redirect("/")


@app.route("/payment/<int:pid>/delete", methods=["POST"])
def delete_payment(pid):
    conn = db()
    row = conn.execute("SELECT student_id FROM payments WHERE id = ?", (pid,)).fetchone()
    conn.execute("DELETE FROM payments WHERE id = ?", (pid,))
    conn.commit()
    conn.close()
    return redirect(f"/student/{row['student_id']}" if row else "/")


@app.route("/expiry")
def expiry():
    return page(EXPIRY, items=licence_items())


@app.route("/expiry/add", methods=["POST"])
def expiry_add():
    person = request.form.get("person", "").strip()
    exp = request.form.get("expiry_date", "").strip()
    if person and exp:
        conn = db()
        conn.execute("INSERT INTO licences (person, doc_type, expiry_date, notes) VALUES (?,?,?,?)",
                     (person, request.form.get("doc_type", "Other"), exp,
                      request.form.get("notes", "").strip()))
        conn.commit()
        conn.close()
    return redirect("/expiry")


@app.route("/expiry/<int:lid>/delete", methods=["POST"])
def expiry_delete(lid):
    conn = db()
    conn.execute("DELETE FROM licences WHERE id = ?", (lid,))
    conn.commit()
    conn.close()
    return redirect("/expiry")


@app.route("/backup")
def backup():
    return send_file(DB, as_attachment=True,
                     download_name=f"records-backup-{date.today().isoformat()}.db")


@app.route("/export")
def export():
    conn = db()
    rows = conn.execute(
        """SELECT s.name, s.phone, s.course, s.total_fee, COALESCE(SUM(p.amount), 0) AS paid
           FROM students s LEFT JOIN payments p ON p.student_id = s.id
           GROUP BY s.id ORDER BY s.name""").fetchall()
    conn.close()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Name", "Phone", "Course", "Total fee", "Paid", "Balance"])
    for r in rows:
        w.writerow([r["name"], r["phone"], r["course"], r["total_fee"], r["paid"],
                    r["total_fee"] - r["paid"]])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=students.csv"})


if __name__ == "__main__":
    setup()
    app.run(port=5002)

