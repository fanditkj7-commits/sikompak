from flask import Flask, request
from database import get_db
import requests
import time
from datetime import datetime, timedelta
import threading
from flask import session, redirect, request
import random
import pandas as pd
import io
from flask import send_file

FONNTE_TOKEN = "V1d14VkD1aQ9D9zkyDG3"

app = Flask(__name__)
app.secret_key = "medialert_secret_key"

USERNAME = "admin"
PASSWORD = "admin123"

@app.before_request
def require_login():
    allowed_routes = ['login', 'static', 'webhook']

    if request.endpoint is None:
        return

    if request.endpoint not in allowed_routes:
        if not session.get("login"):
            return redirect("/login")
        
MENU = """
<div style="margin-bottom:20px;">
    <a href="/dashboard" style="
        display:inline-block;
        padding:10px 16px;
        background:#0f2a44;
        color:white;
        text-decoration:none;
        border-radius:8px;
        font-family:Arial;
    ">⬅ Kembali ke Dashboard</a>
</div>
"""


def setup_database():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pasien_obat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            no_hp TEXT NOT NULL,
            nama_obat TEXT,
            waktu_minum TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pasien_kontrol (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            no_hp TEXT NOT NULL,
            tanggal_kontrol TEXT,
            tempat_kontrol TEXT,
            waktu_kontrol TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_obat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pasien_id INTEGER,
            status TEXT DEFAULT 'menunggu',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_kontrol (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pasien_id INTEGER,
            status TEXT DEFAULT 'menunggu',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jadwal_kirim (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        jenis TEXT,
        pasien_id INTEGER,
        tanggal_kirim TEXT,
        jam_kirim TEXT,
        status TEXT DEFAULT 'terjadwal',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.commit()


def normalisasi_nomor(nomor):
    nomor = str(nomor).replace(" ", "").replace("-", "").replace("+", "").strip()

    if nomor.startswith("0"):
        nomor = "62" + nomor[1:]

    return nomor

def waktu_lokal():
    # Papua / WIT = UTC+9
    return (datetime.utcnow() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")


def kirim_wa(nomor, pesan):
    url = "https://api.fonnte.com/send"
    headers = {"Authorization": FONNTE_TOKEN}
    data = {
        "target": nomor,
        "message": pesan
    }

    response = requests.post(url, headers=headers, data=data)
    print("RESPON FONNTE:", response.text)


def sidebar():
    return """
    <div class="sidebar">
        <div class="brand">
            <div class="logo">
                <img src="/static/logo.png" style="
                    width:55px;
                    height:auto;
                    object-fit:contain;
                ">
            </div>
            <div>
                <h2>SIKOMPAK</h2>
                <p>BP LANAL BIAK</p>
            </div>
        </div>

        <div class="menu-section">UTAMA</div>
        <a href="/dashboard">📊 Dashboard Utama</a>
        <a href="/jadwal_reminder">🗓 Jadwal Reminder</a>
        <a href="/log_respon">📊 Laporan</a>
        <a href="/logout">🚪 Logout</a>

        <div class="menu-section">REMINDER OBAT</div>
        <a href="/dashboard_obat">✅ Dashboard Obat</a>
        <a href="/list_pasien_obat">💊 Data Pasien Obat</a>
        <a href="/tambah_pasien_obat">➕ Tambah Pasien Obat</a>
        <a href="/kirim_obat">📨 Kirim Reminder Obat</a>

        <div class="menu-section">KONTROL / PROLANIS</div>
        <a href="/dashboard_kontrol">📋 Dashboard Kontrol</a>
        <a href="/list_pasien_kontrol">📅 Data Pasien Kontrol</a>
        <a href="/tambah_pasien_kontrol">➕ Tambah Pasien Kontrol</a>
        <a href="/kirim_kontrol">📩 Kirim Reminder Kontrol</a>
        <a href="/peringatan_tidak_hadir">⚠️ Peringatan Tidak Hadir</a>
    </div>
    """


def card(judul, jumlah, warna="#1abc9c"):
    return f"""
    <div style="
        background:white;
        padding:22px;
        border-radius:18px;
        width:210px;
        text-align:center;
        box-shadow:0 8px 20px rgba(0,0,0,0.08);
        border-top:6px solid {warna};
    ">
        <h3 style="margin:0;color:#2c3e50;">{judul}</h3>
        <div style="font-size:34px;font-weight:bold;margin-top:12px;color:{warna};">{jumlah}</div>
    </div>
    """


@app.route("/")
def home():
    return """
    <script>window.location.href='/dashboard'</script>
    """


# =============================
# DASHBOARD UTAMA
# =============================
@app.route("/dashboard")
def dashboard():
    db = get_db()
    cursor = db.cursor()

    total_obat = cursor.execute("SELECT COUNT(*) FROM pasien_obat").fetchone()[0]
    total_kontrol = cursor.execute("SELECT COUNT(*) FROM pasien_kontrol").fetchone()[0]

    sudah_minum = cursor.execute("SELECT COUNT(*) FROM log_obat WHERE status='sudah_minum'").fetchone()[0]
    belum_minum = cursor.execute("SELECT COUNT(*) FROM log_obat WHERE status='belum_minum'").fetchone()[0]
    menunggu_obat = cursor.execute("SELECT COUNT(*) FROM log_obat WHERE status='menunggu'").fetchone()[0]

    hadir = cursor.execute("SELECT COUNT(*) FROM log_kontrol WHERE status='hadir'").fetchone()[0]
    tidak_hadir = cursor.execute("SELECT COUNT(*) FROM log_kontrol WHERE status='tidak_hadir'").fetchone()[0]
    menunggu_kontrol = cursor.execute("SELECT COUNT(*) FROM log_kontrol WHERE status='menunggu'").fetchone()[0]

    total_reminder = sudah_minum + belum_minum + menunggu_obat + hadir + tidak_hadir + menunggu_kontrol

    total_respon_obat = sudah_minum + belum_minum
    persen_patuh = round((sudah_minum / total_respon_obat) * 100) if total_respon_obat > 0 else 0
    persen_tidak_patuh = round((belum_minum / total_respon_obat) * 100) if total_respon_obat > 0 else 0

    return f"""
    <html>
    <head>
        <title>Dashboard Kepatuhan</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <style>
            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                font-family: Arial, sans-serif;
                background: #f4f7fb;
                color: #1f2937;
            }}

            .layout {{
                display: flex;
                min-height: 100vh;
            }}

            .sidebar {{
                width: 235px;
                background: linear-gradient(180deg, #0f2a44, #0b1d33);
                color: white;
                padding: 24px 18px;
                position: fixed;
                top: 0;
                bottom: 0;
                left: 0;
            }}

            .brand {{
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 35px;
            }}

            .logo {{
                display: flex;
                align-items: center;
                justify-content: center;
            }}

            .brand h2 {{
                font-size: 16px;
                margin: 0;
            }}

            .brand p {{
                margin: 2px 0 0;
                font-size: 13px;
                opacity: 0.8;
            }}

            .sidebar a {{
                display: block;
                color: #dbeafe;
                text-decoration: none;
                padding: 12px 14px;
                margin-bottom: 8px;
                border-radius: 10px;
                font-size: 14px;
            }}

            .sidebar a:hover {{
                background: #2563eb;
                color: white;
            }}

            .content {{
                margin-left: 235px;
                padding: 28px;
                width: calc(100% - 235px);
            }}

            .topbar {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 24px;
            }}

            .topbar h1 {{
                margin: 0;
                font-size: 28px;
            }}

            .date-box {{
                background: white;
                padding: 12px 18px;
                border-radius: 12px;
                box-shadow: 0 4px 14px rgba(0,0,0,0.06);
            }}

            .cards {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 18px;
                margin-bottom: 22px;
            }}

            .card {{
                background: white;
                border-radius: 18px;
                padding: 22px;
                box-shadow: 0 8px 22px rgba(0,0,0,0.06);
                min-height: 145px;
            }}

            .card h3 {{
                margin: 0 0 18px;
                font-size: 15px;
                font-weight: 600;
                color: #374151;
            }}

            .card .number {{
                font-size: 30px;
                font-weight: bold;
                margin-bottom: 8px;
                color: #111827;
            }}

            .progress-bg {{
                width: 100%;
                height: 8px;
                background: #e5e7eb;
                border-radius: 10px;
                margin-top: 12px;
            }}

            .progress-green {{
                height: 8px;
                width: {persen_patuh}%;
                background: #22c55e;
                border-radius: 10px;
            }}

            .progress-red {{
                height: 8px;
                width: {persen_tidak_patuh}%;
                background: #ef4444;
                border-radius: 10px;
            }}

            .charts {{
                display: grid;
                grid-template-columns: 1.2fr 1fr;
                gap: 18px;
                margin-bottom: 22px;
            }}

            .chart-card {{
                background: white;
                border-radius: 18px;
                padding: 22px;
                box-shadow: 0 8px 22px rgba(0,0,0,0.06);
            }}

            .chart-card h3 {{
                margin-top: 0;
                margin-bottom: 18px;
            }}

            canvas {{
                max-height: 280px;
            }}

            .table-card {{
                background: white;
                border-radius: 18px;
                padding: 22px;
                box-shadow: 0 8px 22px rgba(0,0,0,0.06);
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 14px;
            }}

            th {{
                text-align: left;
                background: #f1f5f9;
                padding: 12px;
            }}

            td {{
                padding: 12px;
                border-bottom: 1px solid #e5e7eb;
            }}

            .badge-red {{
                background: #fee2e2;
                color: #b91c1c;
                padding: 6px 10px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: bold;
            }}

            @media(max-width: 900px) {{
                .sidebar {{
                    position: relative;
                    width: 100%;
                    height: auto;
                }}

                .layout {{
                    flex-direction: column;
                }}

                .content {{
                    margin-left: 0;
                    width: 100%;
                }}

                .cards, .charts {{
                    grid-template-columns: 1fr;
                }}

                .menu-section {{
                    font-size: 11px;
                    font-weight: bold;
                    color: #94a3b8;
                    margin: 18px 0 8px;
                    padding-left: 10px;
                    letter-spacing: 1px;
                }}
            }}
        </style>
    </head>

    <body>
        <div class="layout">
            {sidebar()}

            <main class="content">
                <div class="topbar">
                    <h1>Dashboard Kepatuhan</h1>
                </div>

                <div class="cards">
                    <div class="card">
                        <h3>Total Pasien Obat</h3>
                        <div class="number">{total_obat}</div>
                        <span>👥</span>
                    </div>

                    <div class="card">
                        <h3>Pasien Patuh</h3>
                        <div class="number">{sudah_minum}</div>
                        <p>{persen_patuh}%</p>
                        <div class="progress-bg">
                            <div class="progress-green"></div>
                        </div>
                    </div>

                    <div class="card">
                        <h3>Pasien Tidak Patuh</h3>
                        <div class="number">{belum_minum}</div>
                        <p>{persen_tidak_patuh}%</p>
                        <div class="progress-bg">
                            <div class="progress-red"></div>
                        </div>
                    </div>

                    <div class="card">
                        <h3>Reminder Terkirim</h3>
                        <div class="number">{total_reminder}</div>
                        <span>📨</span>
                    </div>
                </div>

                <div class="charts">
                    <div class="chart-card">
                        <h3>Tingkat Kepatuhan</h3>
                        <canvas id="lineChart"></canvas>
                    </div>

                    <div class="chart-card">
                        <h3>Kepatuhan dan Kontrol/Prolanis</h3>
                        <canvas id="donutChart"></canvas>
                    </div>
                </div>

                <div class="table-card">
                    <h3>Daftar Pasien Tidak Patuh / Tidak Hadir</h3>
                    <table>
                        <tr>
                            <th>Kategori</th>
                            <th>Jumlah</th>
                            <th>Status</th>
                        </tr>
                        <tr>
                            <td>Pasien Belum Minum Obat</td>
                            <td>{belum_minum}</td>
                            <td><span class="badge-red">Tidak Patuh</span></td>
                        </tr>
                        <tr>
                            <td>Pasien Tidak Hadir Kontrol</td>
                            <td>{tidak_hadir}</td>
                            <td><span class="badge-red">Tidak Hadir</span></td>
                        </tr>
                        <tr>
                            <td>Reminder Obat Menunggu</td>
                            <td>{menunggu_obat}</td>
                            <td><span class="badge-red">Menunggu</span></td>
                        </tr>
                    </table>
                </div>
                <div style="
                    text-align:center;
                    font-size:12px;
                    color:#94a3b8;
                    margin-top:40px;
                ">
                 © 2026 DifaCode — Made With Logic by DifaCode
                </div>
            </main>
        </div>

       <script>
setTimeout(function() {{
    const lineChart = new Chart(document.getElementById('lineChart'), {{
        type: 'line',
        data: {{
            labels: ['Jan', 'Feb', 'Mar', 'Apr', 'Mei'],
            datasets: [{{
                label: 'Kepatuhan Obat (%)',
                data: [0, 0, 0, 0, 0],
                borderColor: '#16a34a',
                backgroundColor: 'rgba(22, 163, 74, 0.15)',
                tension: 0.45,
                fill: true
            }}]
        }},
        options: {{
            responsive: true,
            animation: {{
                duration: 1800,
                easing: 'easeOutQuart'
            }},
            plugins: {{
                legend: {{
                    display: false
                }}
            }},
            scales: {{
                y: {{
                    beginAtZero: true,
                    max: 100
                }}
            }}
        }}
    }});

    const donutChart = new Chart(document.getElementById('donutChart'), {{
        type: 'doughnut',
        data: {{
            labels: ['Sudah Minum', 'Belum Minum', 'Hadir Kontrol', 'Tidak Hadir', 'Menunggu'],
            datasets: [{{
                data: [1, 1, 1, 1, 1],
                backgroundColor: ['#2563eb', '#ef4444', '#22c55e', '#f59e0b', '#94a3b8'],
                hoverOffset: 8
            }}]
        }},
        options: {{
            responsive: true,
            cutout: '65%',
            animation: {{
                duration: 1800,
                easing: 'easeOutQuart',
                animateRotate: true,
                animateScale: true
            }},
            plugins: {{
                legend: {{
                    position: 'bottom'
                }}
            }}
        }}
    }});

    setTimeout(function() {{
        lineChart.data.datasets[0].data = [45, 55, 62, 70, {persen_patuh}];
        lineChart.update();

        donutChart.data.datasets[0].data = [{sudah_minum}, {belum_minum}, {hadir}, {tidak_hadir}, {menunggu_obat + menunggu_kontrol}];
        donutChart.update();
    }}, 500);
}}, 300);
        </script>
    </body>
    </html>
    """


# =============================
# DASHBOARD OBAT
# =============================
@app.route("/dashboard_obat")
def dashboard_obat():
    bulan = request.args.get("bulan")

    db = get_db()
    cursor = db.cursor()

    filter_query = ""
    params = []

    if bulan:
        filter_query = "WHERE strftime('%Y-%m', log_obat.created_at) = ?"
        params.append(bulan)

    total = cursor.execute(f"SELECT COUNT(*) FROM log_obat {filter_query}", params).fetchone()[0]

    sudah_minum = cursor.execute(
        f"SELECT COUNT(*) FROM log_obat {filter_query} AND status='sudah_minum'" if bulan else
        "SELECT COUNT(*) FROM log_obat WHERE status='sudah_minum'",
        params
    ).fetchone()[0]

    belum_minum = cursor.execute(
        f"SELECT COUNT(*) FROM log_obat {filter_query} AND status='belum_minum'" if bulan else
        "SELECT COUNT(*) FROM log_obat WHERE status='belum_minum'",
        params
    ).fetchone()[0]

    menunggu = cursor.execute(
        f"SELECT COUNT(*) FROM log_obat {filter_query} AND status='menunggu'" if bulan else
        "SELECT COUNT(*) FROM log_obat WHERE status='menunggu'",
        params
    ).fetchone()[0]

    data = cursor.execute(f"""
        SELECT pasien_obat.nama, pasien_obat.no_hp, pasien_obat.nama_obat,
               pasien_obat.waktu_minum, log_obat.status, log_obat.created_at
        FROM log_obat
        JOIN pasien_obat ON pasien_obat.id = log_obat.pasien_id
        {filter_query}
        ORDER BY log_obat.id DESC
    """, params).fetchall()

    rows = ""
    for d in data:
        rows += f"""
        <tr>
            <td>{d['nama']}</td>
            <td>{d['no_hp']}</td>
            <td>{d['nama_obat']}</td>
            <td>{d['waktu_minum']}</td>
            <td><b>{d['status']}</b></td>
            <td>{d['created_at']}</td>
        </tr>
        """

    return f"""
    {MENU}
    <div style="font-family:Arial;padding:30px;background:#ecf0f1;min-height:100vh;">
        <h1 style="text-align:center;">💊 Dashboard Reminder Obat</h1>

        <div style="text-align:center;margin-bottom:25px;">
            <form method="get" style="display:inline-block;margin-right:10px;">
                Pilih Bulan:
                <input type="month" name="bulan" value="{bulan if bulan else ''}">
                <button type="submit">Filter</button>
            </form>

            <a href="/export_obat?bulan={bulan if bulan else ''}" style="
                padding:8px 14px;
                background:#27ae60;
                color:white;
                text-decoration:none;
                border-radius:6px;
                font-weight:bold;
            ">📥 Export Excel</a>
        </div>

        <div style="display:flex;justify-content:center;gap:20px;flex-wrap:wrap;margin:30px 0;">
            {card("Total Reminder", total, "#1abc9c")}
            {card("Sudah Minum", sudah_minum, "#27ae60")}
            {card("Belum Minum", belum_minum, "#e74c3c")}
            {card("Menunggu", menunggu, "#f39c12")}
        </div>

        <table border="1" cellpadding="10" cellspacing="0" style="background:white;width:100%;border-collapse:collapse;">
            <tr style="background:#1abc9c;color:white;">
                <th>Nama</th>
                <th>No HP</th>
                <th>Nama Obat</th>
                <th>Waktu Minum</th>
                <th>Status</th>
                <th>Tanggal</th>
            </tr>
            {rows}
        </table>
    </div>
    """

@app.route("/export_obat")
def export_obat():
    bulan = request.args.get("bulan")

    db = get_db()
    cursor = db.cursor()

    filter_query = ""
    params = []

    if bulan:
        filter_query = "WHERE strftime('%Y-%m', log_obat.created_at) = ?"
        params.append(bulan)

    data = cursor.execute(f"""
        SELECT pasien_obat.nama, pasien_obat.no_hp, pasien_obat.nama_obat,
               pasien_obat.waktu_minum, log_obat.status, log_obat.created_at
        FROM log_obat
        JOIN pasien_obat ON pasien_obat.id = log_obat.pasien_id
        {filter_query}
    """, params).fetchall()

    df = pd.DataFrame(data, columns=["Nama", "No HP", "Obat", "Waktu", "Status", "Tanggal"])

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:

        df[df["Status"] == "sudah_minum"].to_excel(writer, sheet_name="Sudah Minum", index=False)
        df[df["Status"] == "belum_minum"].to_excel(writer, sheet_name="Belum Minum", index=False)
        df[df["Status"] == "menunggu"].to_excel(writer, sheet_name="Menunggu", index=False)

    output.seek(0)

    return send_file(output, download_name="laporan_obat.xlsx", as_attachment=True)


# =============================
# DASHBOARD KONTROL
# =============================
@app.route("/dashboard_kontrol")
def dashboard_kontrol():
    bulan = request.args.get("bulan")

    db = get_db()
    cursor = db.cursor()

    filter_query = ""
    params = []

    if bulan:
        filter_query = "WHERE strftime('%Y-%m', log_kontrol.created_at) = ?"
        params.append(bulan)

    total = cursor.execute(f"SELECT COUNT(*) FROM log_kontrol {filter_query}", params).fetchone()[0]

    hadir = cursor.execute(
        f"SELECT COUNT(*) FROM log_kontrol {filter_query} AND status='hadir'" if bulan else
        "SELECT COUNT(*) FROM log_kontrol WHERE status='hadir'",
        params
    ).fetchone()[0]

    tidak_hadir = cursor.execute(
        f"SELECT COUNT(*) FROM log_kontrol {filter_query} AND status='tidak_hadir'" if bulan else
        "SELECT COUNT(*) FROM log_kontrol WHERE status='tidak_hadir'",
        params
    ).fetchone()[0]

    menunggu = cursor.execute(
        f"SELECT COUNT(*) FROM log_kontrol {filter_query} AND status='menunggu'" if bulan else
        "SELECT COUNT(*) FROM log_kontrol WHERE status='menunggu'",
        params
    ).fetchone()[0]

    data = cursor.execute(f"""
        SELECT pasien_kontrol.nama, pasien_kontrol.no_hp,
               pasien_kontrol.tanggal_kontrol, pasien_kontrol.tempat_kontrol,
               pasien_kontrol.waktu_kontrol, log_kontrol.status, log_kontrol.created_at
        FROM log_kontrol
        JOIN pasien_kontrol ON pasien_kontrol.id = log_kontrol.pasien_id
        {filter_query}
        ORDER BY log_kontrol.id DESC
    """, params).fetchall()

    rows = ""
    for d in data:
        rows += f"""
        <tr>
            <td>{d['nama']}</td>
            <td>{d['no_hp']}</td>
            <td>{d['tanggal_kontrol']}</td>
            <td>{d['tempat_kontrol']}</td>
            <td>{d['waktu_kontrol']}</td>
            <td><b>{d['status']}</b></td>
            <td>{d['created_at']}</td>
        </tr>
        """

    return f"""
    {MENU}
    <div style="font-family:Arial;padding:30px;background:#ecf0f1;min-height:100vh;">
        <h1 style="text-align:center;">📅 Dashboard Kontrol/Prolanis</h1>

        <div style="text-align:center;margin-bottom:25px;">
            <form method="get" style="display:inline-block;margin-right:10px;">
                Pilih Bulan:
                <input type="month" name="bulan" value="{bulan if bulan else ''}">
                <button type="submit">Filter</button>
            </form>

            <a href="/export_kontrol?bulan={bulan if bulan else ''}" style="
                padding:8px 14px;
                background:#27ae60;
                color:white;
                text-decoration:none;
                border-radius:6px;
                font-weight:bold;
            ">📥 Export Excel</a>
        </div>

        <div style="display:flex;justify-content:center;gap:20px;flex-wrap:wrap;margin:30px 0;">
            {card("Total Reminder", total, "#3498db")}
            {card("Hadir", hadir, "#27ae60")}
            {card("Tidak Hadir", tidak_hadir, "#e74c3c")}
            {card("Menunggu", menunggu, "#f39c12")}
        </div>

        <table border="1" cellpadding="10" cellspacing="0" style="background:white;width:100%;border-collapse:collapse;">
            <tr style="background:#3498db;color:white;">
                <th>Nama</th>
                <th>No HP</th>
                <th>Tanggal Kontrol</th>
                <th>Tempat</th>
                <th>Waktu</th>
                <th>Status</th>
                <th>Tanggal Reminder</th>
            </tr>
            {rows}
        </table>
    </div>
    """

@app.route("/export_kontrol")
def export_kontrol():
    bulan = request.args.get("bulan")

    db = get_db()
    cursor = db.cursor()

    filter_query = ""
    params = []

    if bulan:
        filter_query = "WHERE strftime('%Y-%m', log_kontrol.created_at) = ?"
        params.append(bulan)

    data = cursor.execute(f"""
        SELECT pasien_kontrol.nama, pasien_kontrol.no_hp,
               pasien_kontrol.tanggal_kontrol, pasien_kontrol.tempat_kontrol,
               pasien_kontrol.waktu_kontrol, log_kontrol.status, log_kontrol.created_at
        FROM log_kontrol
        JOIN pasien_kontrol ON pasien_kontrol.id = log_kontrol.pasien_id
        {filter_query}
    """, params).fetchall()

    df = pd.DataFrame(data, columns=["Nama", "No HP", "Tanggal", "Tempat", "Waktu", "Status", "Created"])

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:

        df[df["Status"] == "hadir"].to_excel(writer, sheet_name="Hadir", index=False)
        df[df["Status"] == "tidak_hadir"].to_excel(writer, sheet_name="Tidak Hadir", index=False)
        df[df["Status"] == "menunggu"].to_excel(writer, sheet_name="Menunggu", index=False)

    output.seek(0)

    return send_file(output, download_name="laporan_kontrol.xlsx", as_attachment=True)


# =============================
# TAMBAH PASIEN OBAT
# =============================
@app.route("/tambah_pasien_obat")
def tambah_pasien_obat():
    return f"""
    {MENU}
    <div style="padding:30px;background:#f4f7fb;min-height:100vh;font-family:Arial;">
        
        <h1 style="margin-bottom:20px;">➕ Tambah Pasien Obat</h1>

        <div style="
            background:white;
            padding:25px;
            border-radius:16px;
            box-shadow:0 8px 20px rgba(0,0,0,0.05);
            width:400px;
        ">
            <form action="/simpan_pasien_obat" method="post">

                <label>Nama</label><br>
                <input type="text" name="nama" required style="width:100%;padding:10px;margin-bottom:12px;"><br>

                <label>No HP</label><br>
                <input type="text" name="no_hp" required style="width:100%;padding:10px;margin-bottom:12px;"><br>

                <label>Nama Obat</label><br>
                <input type="text" name="nama_obat" required style="width:100%;padding:10px;margin-bottom:12px;"><br>

                <label>Waktu Minum</label><br>
                <select name="waktu_minum" style="width:100%;padding:10px;margin-bottom:15px;">
                    <option>Pagi</option>
                    <option>Siang</option>
                    <option>Sore</option>
                    <option>Malam</option>
                    <option>Pagi dan Malam</option>
                    <option>Sesuai Anjuran Dokter</option>
                </select>

                <button type="submit" style="
                    width:100%;
                    padding:12px;
                    background:#0f2a44;
                    color:white;
                    border:none;
                    border-radius:8px;
                    font-weight:bold;
                    cursor:pointer;
                ">💾 Simpan</button>

            </form>
        </div>
    </div>
    """


@app.route("/simpan_pasien_obat", methods=["POST"])
def simpan_pasien_obat():
    db = get_db()
    cursor = db.cursor()

    nama = request.form.get("nama")
    no_hp = normalisasi_nomor(request.form.get("no_hp"))
    nama_obat = request.form.get("nama_obat")
    waktu_minum = request.form.get("waktu_minum")

    cursor.execute(
        "INSERT INTO pasien_obat (nama, no_hp, nama_obat, waktu_minum) VALUES (?, ?, ?, ?)",
        (nama, no_hp, nama_obat, waktu_minum)
    )
    db.commit()

    return MENU + "<h3>Pasien obat berhasil disimpan ✅</h3><a href='/list_pasien_obat'>Lihat Data</a>"


# =============================
# TAMBAH PASIEN KONTROL
# =============================
@app.route("/tambah_pasien_kontrol")
def tambah_pasien_kontrol():
    return f"""
    {MENU}
    <div style="padding:30px;background:#f4f7fb;min-height:100vh;font-family:Arial;">
        
        <h1 style="margin-bottom:20px;">➕ Tambah Pasien Kontrol/Prolanis</h1>

        <div style="
            background:white;
            padding:25px;
            border-radius:16px;
            box-shadow:0 8px 20px rgba(0,0,0,0.05);
            width:430px;
        ">
            <form action="/simpan_pasien_kontrol" method="post">

                <label>Nama</label><br>
                <input type="text" name="nama" required style="width:100%;padding:10px;margin-bottom:12px;"><br>

                <label>No HP</label><br>
                <input type="text" name="no_hp" required style="width:100%;padding:10px;margin-bottom:12px;"><br>

                <label>Tanggal Kontrol</label><br>
                <input type="date" name="tanggal_kontrol" required style="width:100%;padding:10px;margin-bottom:12px;"><br>

                <label>Tempat Kontrol</label><br>
                <input type="text" name="tempat_kontrol" value="BP Lanal Biak" required style="width:100%;padding:10px;margin-bottom:12px;"><br>

                <label>Waktu Kontrol</label><br>
                <input type="time" name="waktu_kontrol" required style="width:100%;padding:10px;margin-bottom:15px;"><br>

                <button type="submit" style="
                    width:100%;
                    padding:12px;
                    background:#0f2a44;
                    color:white;
                    border:none;
                    border-radius:8px;
                    font-weight:bold;
                    cursor:pointer;
                ">💾 Simpan</button>

            </form>
        </div>
    </div>
    """


@app.route("/simpan_pasien_kontrol", methods=["POST"])
def simpan_pasien_kontrol():
    db = get_db()
    cursor = db.cursor()

    nama = request.form.get("nama")
    no_hp = normalisasi_nomor(request.form.get("no_hp"))
    tanggal = request.form.get("tanggal_kontrol")
    tempat = request.form.get("tempat_kontrol")
    waktu = request.form.get("waktu_kontrol")

    cursor.execute(
        """
        INSERT INTO pasien_kontrol 
        (nama, no_hp, tanggal_kontrol, tempat_kontrol, waktu_kontrol)
        VALUES (?, ?, ?, ?, ?)
        """,
        (nama, no_hp, tanggal, tempat, waktu)
    )
    db.commit()

    return MENU + "<h3>Pasien kontrol berhasil disimpan ✅</h3><a href='/list_pasien_kontrol'>Lihat Data</a>"


# =============================
# LIST PASIEN OBAT
# =============================
@app.route("/list_pasien_obat")
def list_pasien_obat():
    db = get_db()
    cursor = db.cursor()

    data = cursor.execute("SELECT * FROM pasien_obat ORDER BY id DESC").fetchall()

    rows = ""
    for p in data:
        rows += f"""
        <tr>
            <td>{p['nama']}</td>
            <td>{p['no_hp']}</td>
            <td>{p['nama_obat']}</td>
            <td>{p['waktu_minum']}</td>
            <td>
                <a href="/edit_pasien_obat?id={p['id']}" style="color:#2563eb;font-weight:bold;">✏️ Edit</a> |
                <a href="/hapus_pasien_obat?id={p['id']}" onclick="return confirm('Yakin hapus?')" style="color:#e74c3c;font-weight:bold;">🗑 Hapus</a>
            </td>
        </tr>
        """

    return f"""
    {MENU}
    <div style="padding:30px;background:#f4f7fb;min-height:100vh;font-family:Arial;">
        
        <h1 style="margin-bottom:20px;">💊 Data Pasien Obat</h1>

        <div style="
            background:white;
            padding:20px;
            border-radius:16px;
            box-shadow:0 8px 20px rgba(0,0,0,0.05);
        ">
            <table style="width:100%;border-collapse:collapse;">
                <tr style="background:#0f2a44;color:white;">
                    <th style="padding:12px;">Nama</th>
                    <th>No HP</th>
                    <th>Obat</th>
                    <th>Waktu</th>
                    <th>Aksi</th>
                </tr>
                {rows}
            </table>
        </div>
    </div>
    """


# =============================
# EDIT PASIEN OBAT
# =============================
@app.route("/edit_pasien_obat")
def edit_pasien_obat():
    id_pasien = request.args.get("id")

    db = get_db()
    cursor = db.cursor()

    p = cursor.execute(
        "SELECT * FROM pasien_obat WHERE id=?",
        (id_pasien,)
    ).fetchone()

    if not p:
        return MENU + "<h3>Data pasien obat tidak ditemukan.</h3>"

    return f"""
    {MENU}
    <h2>Edit Pasien Obat</h2>

    <form action="/update_pasien_obat" method="post">
        <input type="hidden" name="id" value="{p['id']}">

        Nama:<br>
        <input type="text" name="nama" value="{p['nama']}" required><br><br>

        No HP:<br>
        <input type="text" name="no_hp" value="{p['no_hp']}" required><br><br>

        Nama Obat:<br>
        <input type="text" name="nama_obat" value="{p['nama_obat']}" required><br><br>

        Waktu Minum:<br>
        <input type="text" name="waktu_minum" value="{p['waktu_minum']}" required><br><br>

        <button type="submit">💾 Update</button>
    </form>
    """


@app.route("/update_pasien_obat", methods=["POST"])
def update_pasien_obat():
    id_pasien = request.form.get("id")
    nama = request.form.get("nama")
    no_hp = normalisasi_nomor(request.form.get("no_hp"))
    nama_obat = request.form.get("nama_obat")
    waktu_minum = request.form.get("waktu_minum")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE pasien_obat 
        SET nama=?, no_hp=?, nama_obat=?, waktu_minum=? 
        WHERE id=?
    """, (nama, no_hp, nama_obat, waktu_minum, id_pasien))

    db.commit()

    return '<script>window.location.href="/list_pasien_obat"</script>'


# =============================
# LIST PASIEN KONTROL
# =============================
@app.route("/list_pasien_kontrol")
def list_pasien_kontrol():
    db = get_db()
    cursor = db.cursor()

    data = cursor.execute("SELECT * FROM pasien_kontrol ORDER BY id DESC").fetchall()

    rows = ""
    for p in data:
        rows += f"""
        <tr>
            <td>{p['nama']}</td>
            <td>{p['no_hp']}</td>
            <td>{p['tanggal_kontrol']}</td>
            <td>{p['tempat_kontrol']}</td>
            <td>{p['waktu_kontrol']}</td>
            <td>
                <a href="/edit_pasien_kontrol?id={p['id']}" style="color:#2563eb;font-weight:bold;">✏️ Edit</a> |
                <a href="/hapus_pasien_kontrol?id={p['id']}" onclick="return confirm('Yakin hapus?')" style="color:#e74c3c;font-weight:bold;">🗑 Hapus</a>
            </td>
        </tr>
        """

    return f"""
    {MENU}
    <div style="padding:30px;background:#f4f7fb;min-height:100vh;font-family:Arial;">
        
        <h1 style="margin-bottom:20px;">📅 Data Pasien Kontrol/Prolanis</h1>

        <div style="
            background:white;
            padding:20px;
            border-radius:16px;
            box-shadow:0 8px 20px rgba(0,0,0,0.05);
        ">
            <table style="width:100%;border-collapse:collapse;">
                <tr style="background:#0f2a44;color:white;">
                    <th style="padding:12px;">Nama</th>
                    <th>No HP</th>
                    <th>Tanggal</th>
                    <th>Tempat</th>
                    <th>Waktu</th>
                    <th>Aksi</th>
                </tr>
                {rows}
            </table>
        </div>
    </div>
    """


# =============================
# EDIT PASIEN KONTROL
# =============================
@app.route("/edit_pasien_kontrol")
def edit_pasien_kontrol():
    id_pasien = request.args.get("id")

    db = get_db()
    cursor = db.cursor()

    p = cursor.execute(
        "SELECT * FROM pasien_kontrol WHERE id=?",
        (id_pasien,)
    ).fetchone()

    if not p:
        return MENU + "<h3>Data pasien kontrol tidak ditemukan.</h3>"

    return f"""
    {MENU}
    <h2>Edit Pasien Kontrol/Prolanis</h2>

    <form action="/update_pasien_kontrol" method="post">
        <input type="hidden" name="id" value="{p['id']}">

        Nama:<br>
        <input type="text" name="nama" value="{p['nama']}" required><br><br>

        No HP:<br>
        <input type="text" name="no_hp" value="{p['no_hp']}" required><br><br>

        Tanggal Kontrol:<br>
        <input type="date" name="tanggal_kontrol" value="{p['tanggal_kontrol']}" required><br><br>

        Tempat Kontrol:<br>
        <input type="text" name="tempat_kontrol" value="{p['tempat_kontrol']}" required><br><br>

        Waktu Kontrol:<br>
        <input type="time" name="waktu_kontrol" value="{p['waktu_kontrol']}" required><br><br>

        <button type="submit">💾 Update</button>
    </form>
    """


@app.route("/update_pasien_kontrol", methods=["POST"])
def update_pasien_kontrol():
    id_pasien = request.form.get("id")
    nama = request.form.get("nama")
    no_hp = normalisasi_nomor(request.form.get("no_hp"))
    tanggal = request.form.get("tanggal_kontrol")
    tempat = request.form.get("tempat_kontrol")
    waktu = request.form.get("waktu_kontrol")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE pasien_kontrol 
        SET nama=?, no_hp=?, tanggal_kontrol=?, tempat_kontrol=?, waktu_kontrol=?
        WHERE id=?
    """, (nama, no_hp, tanggal, tempat, waktu, id_pasien))

    db.commit()

    return '<script>window.location.href="/list_pasien_kontrol"</script>'


@app.route("/hapus_pasien_obat")
def hapus_pasien_obat():
    db = get_db()
    cursor = db.cursor()
    id_pasien = request.args.get("id")

    cursor.execute("DELETE FROM log_obat WHERE pasien_id=?", (id_pasien,))
    cursor.execute("DELETE FROM pasien_obat WHERE id=?", (id_pasien,))
    db.commit()

    return "<script>window.location.href='/list_pasien_obat'</script>"


@app.route("/hapus_pasien_kontrol")
def hapus_pasien_kontrol():
    db = get_db()
    cursor = db.cursor()
    id_pasien = request.args.get("id")

    cursor.execute("DELETE FROM log_kontrol WHERE pasien_id=?", (id_pasien,))
    cursor.execute("DELETE FROM pasien_kontrol WHERE id=?", (id_pasien,))
    db.commit()

    return "<script>window.location.href='/list_pasien_kontrol'</script>"


# =============================
# PREVIEW KIRIM REMINDER OBAT
# =============================
@app.route("/kirim")
@app.route("/kirim_obat")
def kirim_obat():
    db = get_db()
    cursor = db.cursor()

    data = cursor.execute("SELECT * FROM pasien_obat ORDER BY id DESC").fetchall()

    if not data:
        return MENU + "<h3>Belum ada pasien obat.</h3>"

    rows = ""

    for p in data:
        rows += f"""
        <tr>
            <td><input type="checkbox" name="pasien_ids" value="{p['id']}"></td>
            <td>{p['nama']}</td>
            <td>{p['no_hp']}</td>
            <td>{p['nama_obat']}</td>
            <td>{p['waktu_minum']}</td>
        </tr>
        """

    return f"""
    {MENU}
    <div style="font-family:Arial;padding:25px;background:#ecf0f1;min-height:100vh;">
        <h1>💊 Pilih Pasien untuk Reminder Obat</h1>
        <p>Centang pasien yang ingin dikirim reminder obat.</p>

        <form action="/proses_kirim_obat" method="post">
            <table border="1" cellpadding="10" cellspacing="0" style="background:white;width:100%;border-collapse:collapse;">
                <tr style="background:#1abc9c;color:white;">
                    <th>Pilih</th>
                    <th>Nama</th>
                    <th>No HP</th>
                    <th>Nama Obat</th>
                    <th>Waktu Minum</th>
                </tr>
                {rows}
            </table>

            <input type="date" name="tanggal_kirim">
            <input type="time" name="jam_kirim">

            <br>

           <button type="submit" formaction="/jadwalkan_kirim_obat">📅 Jadwalkan Kirim</button>

            <button type="submit" formaction="/proses_kirim_obat">🚀 Kirim Langsung</button>
        </form>
    </div>
    """


# =============================
# PROSES KIRIM REMINDER OBAT
# =============================
@app.route("/proses_kirim_obat", methods=["POST"])
def proses_kirim_obat():
    pasien_ids = request.form.getlist("pasien_ids")

    if not pasien_ids:
        return MENU + "<h3>Belum ada pasien yang dipilih.</h3>"

    db = get_db()
    cursor = db.cursor()

    placeholders = ",".join(["?"] * len(pasien_ids))

    data = cursor.execute(
        f"SELECT * FROM pasien_obat WHERE id IN ({placeholders})",
        pasien_ids
    ).fetchall()

    hasil = MENU + "<h2>💊 Reminder Obat Berhasil Dikirim</h2><ul>"

    for pasien in data:
        cursor.execute(
            "INSERT INTO log_obat (pasien_id, status, created_at) VALUES (?, ?, ?)",
            (pasien["id"], "menunggu", waktu_lokal())
          )
        db.commit()

        pesan = (
            f"Halo Bapak/Ibu {pasien['nama']} 👋\n\n"
            "Dari BP Lanal Biak mengingatkan untuk minum obat rutin hari ini.\n\n"
            f"💊 Obat: {pasien['nama_obat']}\n"
            f"⏰ Waktu: {pasien['waktu_minum']}\n\n"
            "Minum sesuai anjuran dokter agar tekanan darah/gula darah tetap terkontrol.\n\n"
            "Mohon balas:\n"
            "✅ SUDAH (jika sudah minum obat)\n"
            "❌ BELUM (jika belum)\n\n"
            "Terima kasih, semoga sehat selalu 💙🙏\n"
            "BP LANAL BIAK"
        )

        kirim_wa(pasien["no_hp"], pesan)
        time.sleep(random.randint(10, 20))

        hasil += f"<li><b>{pasien['nama']}</b> - Reminder obat terkirim ✅</li>"

    hasil += "</ul>"
    return hasil

# =============================
# JADWAL KIRIM OBAT
# =============================
@app.route("/jadwalkan_kirim_obat", methods=["POST"])
def jadwalkan_kirim_obat():
    pasien_ids = request.form.getlist("pasien_ids")
    tanggal = request.form.get("tanggal_kirim")
    jam = request.form.get("jam_kirim")

    if not pasien_ids:
        return MENU + "<h3>Belum ada pasien yang dipilih.</h3>"

    if not tanggal or not jam:
        return MENU + "<h3>Tanggal dan jam kirim wajib diisi untuk menjadwalkan reminder.</h3>"

    db = get_db()
    cursor = db.cursor()

    for pid in pasien_ids:
        cursor.execute("""
            INSERT INTO jadwal_kirim (jenis, pasien_id, tanggal_kirim, jam_kirim, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, ("obat", pid, tanggal, jam, waktu_lokal()))

    db.commit()

    return MENU + f"""
    <h3>✅ Jadwal reminder obat berhasil dibuat.</h3>
    <p>Tanggal: <b>{tanggal}</b></p>
    <p>Jam: <b>{jam}</b></p>
    """

# =============================
# PREVIEW KIRIM REMINDER KONTROL
# =============================
@app.route("/kirim_kontrol")
def kirim_kontrol():
    db = get_db()
    cursor = db.cursor()

    data = cursor.execute("SELECT * FROM pasien_kontrol ORDER BY id DESC").fetchall()

    if not data:
        return MENU + "<h3>Belum ada pasien kontrol/Prolanis.</h3>"

    rows = ""

    for p in data:
        rows += f"""
        <tr>
            <td><input type="checkbox" name="pasien_ids" value="{p['id']}"></td>
            <td>{p['nama']}</td>
            <td>{p['no_hp']}</td>
            <td>{p['tanggal_kontrol']}</td>
            <td>{p['tempat_kontrol']}</td>
            <td>{p['waktu_kontrol']}</td>
        </tr>
        """

    return f"""
    {MENU}
    <div style="font-family:Arial;padding:25px;background:#ecf0f1;min-height:100vh;">
        <h1>📅 Pilih Pasien untuk Reminder Kontrol/Prolanis</h1>
        <p>Centang pasien yang ingin dikirim reminder kontrol/Prolanis.</p>

        <form action="/proses_kirim_kontrol" method="post">
            <table border="1" cellpadding="10" cellspacing="0" style="background:white;width:100%;border-collapse:collapse;">
                <tr style="background:#3498db;color:white;">
                    <th>Pilih</th>
                    <th>Nama</th>
                    <th>No HP</th>
                    <th>Tanggal</th>
                    <th>Tempat</th>
                    <th>Waktu</th>
                </tr>
                {rows}
            </table>

            <br>

            <button type="submit" onclick="return confirm('Yakin ingin mengirim reminder kontrol ke pasien yang dipilih?')" style="
                padding:12px 20px;
                background:#3498db;
                color:white;
                border:none;
                border-radius:8px;
                font-weight:bold;
                cursor:pointer;
            ">🚀 Kirim ke Pasien Terpilih</button>
        </form>
    </div>
    """


# =============================
# PROSES KIRIM REMINDER KONTROL
# =============================
@app.route("/proses_kirim_kontrol", methods=["POST"])
def proses_kirim_kontrol():
    pasien_ids = request.form.getlist("pasien_ids")

    if not pasien_ids:
        return MENU + "<h3>Belum ada pasien yang dipilih.</h3>"

    db = get_db()
    cursor = db.cursor()

    placeholders = ",".join(["?"] * len(pasien_ids))

    data = cursor.execute(
        f"SELECT * FROM pasien_kontrol WHERE id IN ({placeholders})",
        pasien_ids
    ).fetchall()

    hasil = MENU + "<h2>📅 Reminder Kontrol/Prolanis Berhasil Dikirim</h2><ul>"

    for pasien in data:
        cursor.execute(
            "INSERT INTO log_kontrol (pasien_id, status, created_at) VALUES (?, ?, ?)",
            (pasien["id"], "menunggu", waktu_lokal())
        )
        db.commit()

        pesan = (
            f"Halo Bapak/Ibu {pasien['nama']} 👋\n\n"
            "Kami dari BP Lanal Biak mengingatkan bahwa jadwal kontrol/Prolanis Anda adalah:\n\n"
            f"📅 Tanggal: {pasien['tanggal_kontrol']}\n"
            f"📍 Tempat: {pasien['tempat_kontrol']}\n"
            f"⏰ Waktu: {pasien['waktu_kontrol']}\n\n"
            "Mohon hadir tepat waktu untuk pemeriksaan (tekanan darah/gula darah):\n"
            "✅ HADIR\n"
            "❌ TIDAK HADIR\n\n"
            "Kami tunggu kedatangannya ya Terimakasih 💙🙏\n"
            "BP LANAL BIAK"
        )

        kirim_wa(pasien["no_hp"], pesan)
        time.sleep(random.randint(10, 20))

        hasil += f"<li><b>{pasien['nama']}</b> - Reminder kontrol terkirim ✅</li>"

    hasil += "</ul>"
    return hasil

# =============================
# PERINGATAN PASIEN TIDAK HADIR
# =============================
@app.route("/peringatan_tidak_hadir")
def peringatan_tidak_hadir():
    bulan = request.args.get("bulan")

    db = get_db()
    cursor = db.cursor()

    filter_query = """
    WHERE (
        log_kontrol.status='tidak_hadir'
        OR (
                log_kontrol.status='menunggu'
                AND datetime(log_kontrol.created_at) <= datetime('now', '-3 hours')
            )
        )
    """
    params = []

    if bulan:
        filter_query += " AND strftime('%Y-%m', log_kontrol.created_at) = ?"
        params.append(bulan)

    data = cursor.execute(f"""
        SELECT 
            pasien_kontrol.id AS pasien_id,
            pasien_kontrol.nama,
            pasien_kontrol.no_hp,
            pasien_kontrol.tanggal_kontrol,
            pasien_kontrol.tempat_kontrol,
            pasien_kontrol.waktu_kontrol,
            log_kontrol.status,
            log_kontrol.created_at
        FROM log_kontrol
        JOIN pasien_kontrol ON pasien_kontrol.id = log_kontrol.pasien_id
        {filter_query}
        ORDER BY log_kontrol.id DESC
    """, params).fetchall()

    rows = ""

    for p in data:
        if p["status"] == "tidak_hadir":
            status_label = "<span style='color:red;font-weight:bold;'>❌ Tidak Hadir</span>"
        else:
            status_label = "<span style='color:orange;font-weight:bold;'>⏳ Belum Respon > 3 Jam</span>"

        rows += f"""
        <tr>
            <td><input type="checkbox" name="pasien_ids" value="{p['pasien_id']}"></td>
            <td>{p['nama']}</td>
            <td>{p['no_hp']}</td>
            <td>{p['tanggal_kontrol']}</td>
            <td>{p['tempat_kontrol']}</td>
            <td>{p['waktu_kontrol']}</td>
            <td>{status_label}</td>
            <td>{p['created_at']}</td>
        </tr>
        """

    if not rows:
        rows = """
        <tr>
            <td colspan="8" style="text-align:center;">Tidak ada data pasien tidak hadir pada bulan ini.</td>
        </tr>
        """

    return f"""
    {MENU}
    <div style="font-family:Arial;padding:25px;background:#ecf0f1;min-height:100vh;">
        <h1 style="text-align:center;">⚠️ Peringatan Pasien Tidak Hadir</h1>

        <div style="text-align:center;margin-bottom:25px;">
            <form method="get" style="display:inline-block;margin-right:10px;">
                Pilih Bulan:
                <input type="month" name="bulan" value="{bulan if bulan else ''}">
                <button type="submit">Filter</button>
            </form>

            <a href="/export_peringatan_tidak_hadir?bulan={bulan if bulan else ''}" style="
                padding:8px 14px;
                background:#27ae60;
                color:white;
                text-decoration:none;
                border-radius:6px;
                font-weight:bold;
            ">📥 Export Excel</a>
        </div>

        <p>Centang pasien yang ingin dikirim pesan peringatan tidak hadir.</p>

        <form action="/proses_peringatan_tidak_hadir" method="post">
            <table border="1" cellpadding="10" cellspacing="0" style="background:white;width:100%;border-collapse:collapse;">
                <tr style="background:#e67e22;color:white;">
                    <th>Pilih</th>
                    <th>Nama</th>
                    <th>No HP</th>
                    <th>Tanggal Kontrol</th>
                    <th>Tempat</th>
                    <th>Waktu</th>
                    <th>Status</th>
                    <th>Tanggal Log</th>
                </tr>
                {rows}
            </table>

            <br>

            <button type="submit" onclick="return confirm('Yakin ingin mengirim peringatan ke pasien yang dipilih?')" style="
                padding:12px 20px;
                background:#e67e22;
                color:white;
                border:none;
                border-radius:8px;
                font-weight:bold;
                cursor:pointer;
            ">⚠️ Kirim Peringatan</button>
        </form>
    </div>
    """

@app.route("/export_peringatan_tidak_hadir")
def export_peringatan_tidak_hadir():
    bulan = request.args.get("bulan")

    db = get_db()
    cursor = db.cursor()

    filter_query = "WHERE log_kontrol.status='tidak_hadir'"
    params = []

    if bulan:
        filter_query += " AND strftime('%Y-%m', log_kontrol.created_at) = ?"
        params.append(bulan)

    data = cursor.execute(f"""
        SELECT 
            pasien_kontrol.nama,
            pasien_kontrol.no_hp,
            pasien_kontrol.tanggal_kontrol,
            pasien_kontrol.tempat_kontrol,
            pasien_kontrol.waktu_kontrol,
            log_kontrol.status,
            log_kontrol.created_at
        FROM log_kontrol
        JOIN pasien_kontrol ON pasien_kontrol.id = log_kontrol.pasien_id
        {filter_query}
        ORDER BY log_kontrol.id DESC
    """, params).fetchall()

    df = pd.DataFrame(data, columns=[
        "Nama",
        "No HP",
        "Tanggal Kontrol",
        "Tempat",
        "Waktu Kontrol",
        "Status",
        "Tanggal Log"
    ])

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    nama_file = f"laporan_peringatan_tidak_hadir_{bulan if bulan else 'semua'}.xlsx"

    return send_file(output, download_name=nama_file, as_attachment=True)

@app.route("/proses_peringatan_tidak_hadir", methods=["POST"])
def proses_peringatan_tidak_hadir():
    pasien_ids = request.form.getlist("pasien_ids")

    if not pasien_ids:
        return MENU + "<h3>Belum ada pasien yang dipilih.</h3>"

    db = get_db()
    cursor = db.cursor()

    placeholders = ",".join(["?"] * len(pasien_ids))

    data = cursor.execute(
        f"SELECT * FROM pasien_kontrol WHERE id IN ({placeholders})",
        pasien_ids
    ).fetchall()

    hasil = MENU + "<h2>⚠️ Peringatan Tidak Hadir Berhasil Dikirim</h2><ul>"

    for pasien in data:
        pesan = (
            f"Halo Bapak/Ibu {pasien['nama']} 🙏\n\n"
            "Kami mencatat Anda belum hadir pada jadwal kontrol Prolanis sebelumnya.\n\n"
            "Mohon segera melakukan kontrol ulang agar kondisi kesehatan tetap terpantau.\n\n"
            "Silakan hubungi kami untuk penjadwalan ulang.\n\n"
            "Terima kasih 💙\n"
            "BP Lanal Biak"
        )

        kirim_wa(pasien["no_hp"], pesan)
        time.sleep(random.randint(10, 20))

        hasil += f"<li><b>{pasien['nama']}</b> - Peringatan berhasil dikirim ✅</li>"

    hasil += "</ul>"
    return hasil

# =============================
# LOG RESPON
# =============================
@app.route("/log_respon")
def log_respon():
    db = get_db()
    cursor = db.cursor()

    obat = cursor.execute("""
        SELECT pasien_obat.nama, pasien_obat.no_hp, log_obat.status, log_obat.created_at
        FROM log_obat
        JOIN pasien_obat ON pasien_obat.id = log_obat.pasien_id
        ORDER BY log_obat.id DESC
    """).fetchall()

    kontrol = cursor.execute("""
        SELECT pasien_kontrol.nama, pasien_kontrol.no_hp, log_kontrol.status, log_kontrol.created_at
        FROM log_kontrol
        JOIN pasien_kontrol ON pasien_kontrol.id = log_kontrol.pasien_id
        ORDER BY log_kontrol.id DESC
    """).fetchall()

    hasil = MENU + "<h2>📊 Log Respon Semua Reminder</h2>"

    hasil += "<h3>💊 Log Obat</h3><ul>"
    for d in obat:
        hasil += f"<li><b>{d['nama']}</b> - {d['no_hp']} - <b>{d['status']}</b> - {d['created_at']}</li>"
    hasil += "</ul>"

    hasil += "<h3>📅 Log Kontrol/Prolanis</h3><ul>"
    for d in kontrol:
        hasil += f"<li><b>{d['nama']}</b> - {d['no_hp']} - <b>{d['status']}</b> - {d['created_at']}</li>"
    hasil += "</ul>"

    return hasil

# =============================
# HALAMAN JADWAL REMINDER
# =============================
@app.route("/jadwal_reminder")
def jadwal_reminder():
    db = get_db()
    cursor = db.cursor()

    data = cursor.execute("""
        SELECT 
            jadwal_kirim.id,
            jadwal_kirim.jenis,
            jadwal_kirim.pasien_id,
            jadwal_kirim.tanggal_kirim,
            jadwal_kirim.jam_kirim,
            jadwal_kirim.status,
            jadwal_kirim.created_at,

            pasien_obat.nama AS nama_obat_pasien,
            pasien_obat.no_hp AS no_hp_obat,

            pasien_kontrol.nama AS nama_kontrol_pasien,
            pasien_kontrol.no_hp AS no_hp_kontrol

        FROM jadwal_kirim
        LEFT JOIN pasien_obat 
            ON jadwal_kirim.jenis='obat' 
            AND jadwal_kirim.pasien_id=pasien_obat.id

        LEFT JOIN pasien_kontrol 
            ON jadwal_kirim.jenis='kontrol' 
            AND jadwal_kirim.pasien_id=pasien_kontrol.id

        ORDER BY 
            jadwal_kirim.tanggal_kirim DESC,
            jadwal_kirim.jam_kirim DESC
    """).fetchall()

    rows = ""

    for d in data:
        nama = d["nama_obat_pasien"] if d["jenis"] == "obat" else d["nama_kontrol_pasien"]
        no_hp = d["no_hp_obat"] if d["jenis"] == "obat" else d["no_hp_kontrol"]

        if d["status"] == "terjadwal":
            badge = "<span style='background:#fef3c7;color:#92400e;padding:6px 10px;border-radius:20px;font-weight:bold;'>Terjadwal</span>"
        else:
            badge = "<span style='background:#dcfce7;color:#166534;padding:6px 10px;border-radius:20px;font-weight:bold;'>Terkirim</span>"

        rows += f"""
        <tr>
            <td>{d['jenis']}</td>
            <td>{nama if nama else '-'}</td>
            <td>{no_hp if no_hp else '-'}</td>
            <td>{d['tanggal_kirim']}</td>
            <td>{d['jam_kirim']}</td>
            <td>{badge}</td>
            <td>{d['created_at']}</td>
            <td>
                <a href="/hapus_jadwal?id={d['id']}" 
                   onclick="return confirm('Yakin ingin menghapus jadwal ini?')" 
                   style="color:red;text-decoration:none;font-weight:bold;">
                   🗑 Hapus
                </a>
            </td>
        </tr>
        """

    return f"""
    {MENU}
    <div style="font-family:Arial;padding:30px;background:#ecf0f1;min-height:100vh;">
        <h1 style="text-align:center;">🗓 Jadwal Reminder</h1>
        <p style="text-align:center;">Daftar reminder yang dijadwalkan dan sudah terkirim.</p>

        <table border="1" cellpadding="10" cellspacing="0" style="
            background:white;
            width:100%;
            border-collapse:collapse;
            box-shadow:0 8px 20px rgba(0,0,0,0.08);
        ">
            <tr style="background:#0f2a44;color:white;">
                <th>Jenis</th>
                <th>Nama Pasien</th>
                <th>No HP</th>
                <th>Tanggal Kirim</th>
                <th>Jam Kirim</th>
                <th>Status</th>
                <th>Dibuat Pada</th>
                <th>Aksi</th>
            </tr>
            {rows}
        </table>
    </div>
    """

@app.route("/hapus_jadwal")
def hapus_jadwal():
    id_jadwal = request.args.get("id")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM jadwal_kirim WHERE id=?", (id_jadwal,))
    db.commit()

    return "<script>window.location.href='/jadwal_reminder'</script>"

# =============================
# LOGIN LOGOUT
# =============================
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("login"):
        return redirect("/dashboard")

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == USERNAME and password == PASSWORD:
            session["login"] = True
            return redirect("/dashboard")

    return """
<!DOCTYPE html>
<html>
<head>
    <title>Login - SIKOMPAK</title>
    <style>
        body {
            margin: 0;
            font-family: 'Segoe UI', Arial, sans-serif;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }

        /* SLIDER BACKGROUND */
        .bg-slider {
            position: fixed;
            top: 0;
            left: 0;
            width: 400%;   /* 🔥 karena 4 gambar */
            height: 100%;
            display: flex;
            animation: slide 30s linear infinite;
            z-index: 0;
        }

        .bg-slider {
            position: fixed;
            top: 0;
            left: 0;
            width: 200%;
            height: 100%;
            display: flex;
            animation: slideBg 56s infinite ease-in-out;
            z-index: 1;
        }

        .bg-slider img {
            width: 50%;
            height: 100%;
            object-fit: contain; /* tetap tidak kepotong */
        }
        @keyframes slideBg {
            0% {
                transform: translateX(0);
            }

            44% {
                transform: translateX(0);
            }

            50% {
                transform: translateX(-50%);
            }

            94% {
                transform: translateX(-50%);
            }

            100% {
                transform: translateX(0);
            }
        }

        /* OVERLAY GELAP */
        body::after {
            content: "";
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.4);
            z-index: 1;
        }

        /* LOGIN CARD */
        .login-card {
            position: relative;
            z-index: 2;
            background: rgba(255, 255, 255, 0.15); /* transparan */
            backdrop-filter: blur(12px);          /* efek kaca */
            -webkit-backdrop-filter: blur(12px);
            padding: 38px;
            width: 360px;
            border-radius: 18px;
            box-shadow: 0 12px 35px rgba(0,0,0,0.3);
            text-align: center;
            border: 1px solid rgba(255,255,255,0.3);
        }

        .login-card img {
            width: 70px;
            margin-bottom: 10px;
        }

        .login-card h2 {
            margin: 0;
            color: white !important;
            font-weight: bold;
            letter-spacing: 1px;
            text-shadow: 0 2px 6px rgba(0,0,0,0.5);
        }

        .login-card p {
            color: #e2e8f0 !important;
            margin-bottom: 25px;
            font-size: 14px;
            text-shadow: 0 1px 4px rgba(0,0,0,0.4);
        }

        input {
            width: 100%;
            padding: 12px;
            margin-bottom: 12px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.4);
            background: rgba(255,255,255,0.2);
            color: white;
        }

        input::placeholder {
            color: #ddd;
        }

        button {
            background: #1abc9c;
        }
        button:hover {
            background: #16a085;
        }

        .footer {
            margin-top: 15px;
            font-size: 12px;
            color: #aaa;
        }

        .sub-title {
            color: #a5f3fc;
            font-size: 12px;
            font-weight: bold;
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-top: 4px;
            margin-bottom: 10px;
        }

        .bg-blur {
        position: fixed;
        inset: 0;
        background-image: url('/static/bg1.jpg');
        background-size: cover;
        background-position: center;
        filter: blur(20px) brightness(0.7);
        transform: scale(1.1); /* biar blur tidak kepotong */
        z-index: 0;
    }
    </style>
</head>

<body>

    <<div class="bg-blur"></div>

    <div class="bg-slider">
        <img src="/static/bg1.jpg">
        <img src="/static/bg2.jpg">
    </div>
    <div class="login-card">
        <img src="/static/logo.png">
        <h2>SIKOMPAK</h2>
        <div class="sub-title">BP LANAL BIAK</div>
        <p>Sistem Kontrol dan Monitoring Pasien</p>

        <form method="POST">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Masuk</button>
        </form>

        <div class="footer">
            © 2026 DifaCode - Made with logic by DifaCode
        </div>
    </div>

</body>
</html>
"""

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# =============================
# WEBHOOK FONNTE
# =============================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        data = request.args
    else:
        data = request.form if request.form else request.json

    print("RAW DATA MASUK:", data)

    if not data:
        return "OK"

    nomor = data.get("sender") or data.get("from") or data.get("number") or data.get("phone")
    pesan = data.get("message") or data.get("text") or data.get("body")

    if not nomor or not pesan:
        print("❌ DATA TIDAK LENGKAP")
        return "OK"

    nomor = normalisasi_nomor(nomor)
    nomor_08 = "0" + nomor[2:] if nomor.startswith("62") else nomor

    pesan = str(pesan).lower().strip()
    pesan = pesan.replace("✅", "").replace("❌", "").strip()

    db = get_db()
    cursor = db.cursor()

    if pesan in ["sudah", "sudah minum", "1", "ya", "ok"]:
        pasien = cursor.execute(
            "SELECT * FROM pasien_obat WHERE no_hp=? OR no_hp=?",
            (nomor, nomor_08)
        ).fetchone()

        if pasien:
            log = cursor.execute(
                "SELECT * FROM log_obat WHERE pasien_id=? AND status='menunggu' ORDER BY id DESC LIMIT 1",
                (pasien["id"],)
            ).fetchone()

            if log:
                cursor.execute("UPDATE log_obat SET status='sudah_minum' WHERE id=?", (log["id"],))
                db.commit()
                kirim_wa(nomor, "Terima kasih 🙏 Status minum obat Anda berhasil dicatat: sudah minum")
                print("✅ OBAT UPDATE: sudah_minum")
                return "OK"

    if pesan in ["belum", "belum minum", "2", "tidak"]:
        pasien = cursor.execute(
            "SELECT * FROM pasien_obat WHERE no_hp=? OR no_hp=?",
            (nomor, nomor_08)
        ).fetchone()

        if pasien:
            log = cursor.execute(
                "SELECT * FROM log_obat WHERE pasien_id=? AND status='menunggu' ORDER BY id DESC LIMIT 1",
                (pasien["id"],)
            ).fetchone()

            if log:
                cursor.execute("UPDATE log_obat SET status='belum_minum' WHERE id=?", (log["id"],))
                db.commit()
                kirim_wa(nomor, "Terima kasih 🙏 Status minum obat Anda berhasil dicatat: belum minum")
                print("✅ OBAT UPDATE: belum_minum")
                return "OK"

    if pesan in ["hadir", "ya hadir"]:
        pasien = cursor.execute(
            "SELECT * FROM pasien_kontrol WHERE no_hp=? OR no_hp=?",
            (nomor, nomor_08)
        ).fetchone()

        if pasien:
            log = cursor.execute(
                "SELECT * FROM log_kontrol WHERE pasien_id=? AND status='menunggu' ORDER BY id DESC LIMIT 1",
                (pasien["id"],)
            ).fetchone()

            if log:
                cursor.execute("UPDATE log_kontrol SET status='hadir' WHERE id=?", (log["id"],))
                db.commit()
                kirim_wa(nomor, "Terima kasih 🙏 Kehadiran kontrol/Prolanis Anda berhasil dicatat: hadir")
                print("✅ KONTROL UPDATE: hadir")
                return "OK"

    if pesan in ["tidak hadir", "berhalangan"]:
        pasien = cursor.execute(
            "SELECT * FROM pasien_kontrol WHERE no_hp=? OR no_hp=?",
            (nomor, nomor_08)
        ).fetchone()

        if pasien:
            log = cursor.execute(
                "SELECT * FROM log_kontrol WHERE pasien_id=? AND status='menunggu' ORDER BY id DESC LIMIT 1",
                (pasien["id"],)
            ).fetchone()

            if log:
                cursor.execute("UPDATE log_kontrol SET status='tidak_hadir' WHERE id=?", (log["id"],))
                db.commit()
                kirim_wa(nomor, "Terima kasih 🙏 Kehadiran kontrol/Prolanis Anda berhasil dicatat: tidak hadir")
                print("✅ KONTROL UPDATE: tidak_hadir")
                return "OK"

    print("❌ FORMAT PESAN TIDAK DIKENALI:", pesan)
    return "OK"

# =============================
# JADWAL KIRIM
# =============================
def proses_jadwal_kirim():
    while True:
        db = get_db()
        cursor = db.cursor()

        tanggal = datetime.now().strftime("%Y-%m-%d")
        jam = datetime.now().strftime("%H:%M")

        data = cursor.execute("""
            SELECT * FROM jadwal_kirim 
            WHERE jenis='obat'
            AND tanggal_kirim=?
            AND jam_kirim=?
            AND status='terjadwal'
        """, (tanggal, jam)).fetchall()

        for j in data:
            pasien = cursor.execute(
                "SELECT * FROM pasien_obat WHERE id=?",
                (j["pasien_id"],)
            ).fetchone()

            if pasien:
                cursor.execute(
                    "INSERT INTO log_obat (pasien_id, status, created_at) VALUES (?, ?, ?)",
                     (pasien["id"], "menunggu", waktu_lokal())
                )

                pesan = (
                    f"Halo Bapak/Ibu {pasien['nama']} 👋\n\n"
                    "Dari BP Lanal Biak mengingatkan untuk minum obat rutin hari ini.\n\n"
                    f"💊 Obat: {pasien['nama_obat']}\n"
                    f"⏰ Waktu: {pasien['waktu_minum']}\n\n"
                         "Minum sesuai anjuran dokter agar tekanan darah/gula darah tetap terkontrol.\n\n"
                    "Mohon balas:\n"
                    "✅ SUDAH (jika sudah minum obat)\n"
                    "❌ BELUM (jika belum)\n\n"
                    "Terima kasih, semoga sehat selalu 💙🙏\n"
                    "BP LANAL BIAK"
                )

                kirim_wa(pasien["no_hp"], pesan)
                time.sleep(random.randint(10, 20))

            cursor.execute(
                "UPDATE jadwal_kirim SET status='terkirim' WHERE id=?",
                (j["id"],)
            )

        db.commit()
        time.sleep(30)

if __name__ == "__main__":
    setup_database()

    threading.Thread(target=proses_jadwal_kirim, daemon=True).start()

    app.run(debug=True, use_reloader=False)