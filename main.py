from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional
from dotenv import load_dotenv
import os
import io
import csv
import json
import uuid
import hmac
import secrets
import logging
import pymysql
from pymysql import Error, IntegrityError

from core import (
    compute_staff_stats,
    device_fingerprint,
    normalize_name,
    score_midpoint,
    hash_password,
    verify_password,
    validate_username,
    validate_password,
    validate_site_title,
    validate_staff_name,
)
from staff_seed import STAFF_NAMES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="DCLM Appraisal")

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")


def render_template(name, request, context=None):
    """Compatible with both starlette <0.29 (old signature) and >=0.29 (new signature)."""
    context = dict(context or {})
    context.setdefault("request", request)
    version = __import__("starlette").__version__
    major, minor = (int(part) for part in version.split(".")[:2])
    if (major, minor) >= (0, 29):
        return templates.TemplateResponse(request, name, context=context)
    return templates.TemplateResponse(name, context=context)


DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DB"),
    "connect_timeout": 60,
    "ssl": {"ssl": True},
    "charset": "utf8mb4"
}

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
SESSION_SECRET = os.getenv("SESSION_SECRET") or secrets.token_hex(32)

if not os.getenv("ADMIN_PASSWORD"):
    logger.warning("⚠️  ADMIN_PASSWORD is not set — using default 'admin'. Change it via the ADMIN_PASSWORD environment variable.")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=8 * 60 * 60,
    same_site="lax",
)

logger.info(f"Target DB: {DB_CONFIG['host']}:{DB_CONFIG['port']}")


def get_db_connection():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        if conn.open:
            logger.info("✅ CONNECTED SUCCESSFULLY TO CLOUDCLUSTERS MYSQL")
            return conn
    except Error as e:
        logger.error(f"❌ CONNECTION FAILED: {str(e)}")
        return None


def is_admin(request: Request) -> bool:
    return bool(request.session.get("admin"))


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


APPRAISAL_COLUMNS = [
    ("device_id", "VARCHAR(64) NULL"),
    ("device_fp", "CHAR(64) NULL"),
    ("device_ip", "VARCHAR(64) NULL"),
    ("device_ua", "VARCHAR(512) NULL"),
    ("staff_id", "VARCHAR(36) NULL"),
]


def ensure_schema(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff_names (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            position VARCHAR(255) NULL,
            email VARCHAR(255) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cursor.execute("SELECT COUNT(*) AS c FROM staff_names")
        if cursor.fetchone()[0] == 0:
            for name in STAFF_NAMES:
                cursor.execute(
                    "INSERT INTO staff_names (id, name) VALUES (%s, %s)",
                    (str(uuid.uuid4()), name),
                )
            logger.info(f"✅ Seeded {len(STAFF_NAMES)} staff names")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS appraisals (
            id VARCHAR(36) PRIMARY KEY,
            staff_name VARCHAR(255) NOT NULL,
            christian_conduct VARCHAR(50) NOT NULL,
            job_performance VARCHAR(50) NOT NULL,
            reliability VARCHAR(50) NOT NULL,
            teamwork VARCHAR(255) NOT NULL,
            communication VARCHAR(255) NOT NULL,
            initiative VARCHAR(255) NOT NULL,
            adaptability VARCHAR(255) NOT NULL,
            overall_assessment VARCHAR(255) NOT NULL,
            strengths TEXT,
            improvements TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_settings (
            setting_key VARCHAR(64) PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cursor.execute("SELECT COUNT(*) AS c FROM admin_settings")
        if cursor.fetchone()[0] == 0:
            seed = {
                "admin_username": os.getenv("ADMIN_USERNAME", "admin"),
                "admin_password": hash_password(os.getenv("ADMIN_PASSWORD", "admin")),
                "site_title": os.getenv("APP_TITLE", "DCLM HQ STAFF PEER ASSESSMENT"),
            }
            for key, value in seed.items():
                cursor.execute(
                    "INSERT INTO admin_settings (setting_key, setting_value) VALUES (%s, %s)",
                    (key, value),
                )
            logger.info("✅ Seeded admin settings")

        cursor.execute(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'appraisals'"
        )
        existing_columns = {row[0] for row in cursor.fetchall()}
        for column, ddl in APPRAISAL_COLUMNS:
            if column not in existing_columns:
                cursor.execute(f"ALTER TABLE appraisals ADD COLUMN {column} {ddl}")
                logger.info(f"✅ Added column appraisals.{column}")

        cursor.execute(
            "SELECT INDEX_NAME FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'appraisals' "
            "AND INDEX_NAME = 'uq_appraisals_device_staff'"
        )
        if not cursor.fetchone():
            try:
                cursor.execute(
                    "ALTER TABLE appraisals ADD UNIQUE INDEX uq_appraisals_device_staff "
                    "(device_id, staff_name(191))"
                )
                logger.info("✅ Added unique index uq_appraisals_device_staff")
            except Error as e:
                logger.warning(f"⚠️  Could not create unique index: {e}")

    conn.commit()


@app.on_event("startup")
async def startup():
    conn = get_db_connection()
    if conn:
        try:
            ensure_schema(conn)
        finally:
            if conn.open:
                conn.close()


def find_staff_member(conn, raw_name):
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT id, name FROM staff_names")
    for row in cursor.fetchall():
        if normalize_name(row["name"]) == normalize_name(raw_name):
            return row
    return None


def existing_appraisal(conn, staff_id, device_id, device_fp):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM appraisals "
        "WHERE staff_id = %s AND (device_id = %s OR device_fp = %s) LIMIT 1",
        (staff_id, device_id, device_fp),
    )
    return cursor.fetchone() is not None


def get_all_staff(conn):
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT id, name FROM staff_names ORDER BY name")
    return cursor.fetchall()


def get_setting(conn, key, default=None):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT setting_value FROM admin_settings WHERE setting_key = %s",
        (key,),
    )
    row = cursor.fetchone()
    return row[0] if row else default


def set_setting(conn, key, value):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO admin_settings (setting_key, setting_value) VALUES (%s, %s) "
        "ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)",
        (key, value),
    )
    conn.commit()


def base_context(conn):
    rows = get_all_staff(conn) if conn else []
    names = [row["name"] for row in rows]
    return {
        "staff_names": names,
        "staff_names_json": json.dumps(names),
        "site_title": get_setting(conn, "site_title", "DCLM HQ STAFF PEER ASSESSMENT"),
    }


@app.get("/health")
async def health():
    conn = get_db_connection()
    if conn:
        conn.close()
        return {"status": "ok", "message": "✅ Database connected"}
    return {"status": "error", "message": "❌ Database failed"}, 500


@app.get("/", response_class=HTMLResponse)
async def form(request: Request):
    conn = get_db_connection()
    if not conn:
        return render_template(
            "index.html",
            request,
            {"error": "❌ Database connection failed — please try again later."},
        )
    try:
        return render_template("index.html", request, base_context(conn))
    finally:
        conn.close()


@app.post("/submit")
async def submit(
    request: Request,
    staff_name: str = Form(...),
    christian_conduct: str = Form(...),
    job_performance: str = Form(...),
    reliability: str = Form(...),
    teamwork: str = Form(...),
    communication: str = Form(...),
    initiative: str = Form(...),
    adaptability: str = Form(...),
    overall_assessment: str = Form(...),
    strengths: Optional[str] = Form(None),
    improvements: Optional[str] = Form(None),
    device_id: Optional[str] = Form(None),
):
    required = all([
        staff_name, christian_conduct, job_performance, reliability,
        teamwork, communication, initiative, adaptability, overall_assessment,
    ])
    if not required:
        return render_template(
            "index.html",
            request,
            {"error": "Fill all required fields"},
        )

    conn = get_db_connection()
    if not conn:
        return render_template(
            "index.html",
            request,
            {"error": "❌ Database connection failed — check CloudClusters remote access"},
        )

    try:
        ctx = base_context(conn)
        staff = find_staff_member(conn, staff_name)
        if not staff:
            ctx["error"] = (
                f"⚠️ '{staff_name}' is not a registered staff member. "
                "Please pick an exact name from the suggestions."
            )
            return render_template("index.html", request, ctx)

        canonical_name = staff["name"]
        staff_id = staff["id"]
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("user-agent") or ""
        device_fp = device_fingerprint(device_id, client_ip, user_agent)

        if existing_appraisal(conn, staff_id, device_id, device_fp):
            ctx["error"] = (
                f"⚠️ You have already submitted an appraisal for {canonical_name} "
                "from this device. Each person may be assessed only once."
            )
            return render_template("index.html", request, ctx)

        appraisal_id = str(uuid.uuid4())
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO appraisals
        (id, staff_name, staff_id, christian_conduct, job_performance, reliability,
         teamwork, communication, initiative, adaptability, overall_assessment,
         strengths, improvements, device_id, device_fp, device_ip, device_ua)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            appraisal_id, canonical_name, staff_id, christian_conduct, job_performance,
            reliability, teamwork, communication, initiative, adaptability,
            overall_assessment, strengths or "", improvements or "",
            device_id, device_fp, client_ip, user_agent,
        ))
        conn.commit()
        logger.info(f"✅ Saved: {appraisal_id} for {canonical_name}")
        ctx["success"] = "✅ Submitted successfully! Thank you for your appraisal."
        return render_template("index.html", request, ctx)
    except IntegrityError as e:
        conn.rollback()
        ctx = base_context(conn)
        if "uq_appraisals_device_staff" in str(e):
            ctx["error"] = (
                "⚠️ You have already submitted an appraisal for this staff member "
                "from this device."
            )
            return render_template("index.html", request, ctx)
        raise e
    finally:
        conn.close()


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_admin(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return render_template("login.html", request)


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    valid_auth = False
    conn = get_db_connection()
    if conn:
        try:
            stored_user = get_setting(conn, "admin_username", ADMIN_USERNAME)
            stored_hash = get_setting(conn, "admin_password", "")
            if stored_hash and verify_password(password, stored_hash):
                valid_auth = hmac.compare_digest(username, stored_user)
            elif not stored_hash:
                valid_auth = (
                    hmac.compare_digest(username, ADMIN_USERNAME)
                    and hmac.compare_digest(password, ADMIN_PASSWORD)
                )
        finally:
            conn.close()
    else:
        valid_auth = (
            hmac.compare_digest(username, ADMIN_USERNAME)
            and hmac.compare_digest(password, ADMIN_PASSWORD)
        )

    if valid_auth:
        request.session["admin"] = True
        return RedirectResponse(url="/dashboard", status_code=303)
    return render_template("login.html", request, {"error": "❌ Invalid username or password"})


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)

    conn = get_db_connection()
    kpis = {"total": 0, "staff": 0, "devices": 0, "overall_avg": None}
    staff_list = []
    site_title = "DCLM HQ STAFF PEER ASSESSMENT"
    if conn:
        try:
            site_title = get_setting(conn, "site_title", site_title)
            staff_list = get_all_staff(conn)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM appraisals")
            kpis["total"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(DISTINCT staff_name) FROM appraisals")
            kpis["staff"] = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(DISTINCT device_fp) FROM appraisals "
                "WHERE device_fp IS NOT NULL"
            )
            kpis["devices"] = cursor.fetchone()[0]
            cursor.execute("SELECT overall_assessment FROM appraisals")
            points = [
                score_midpoint(row[0])
                for row in cursor.fetchall()
                if score_midpoint(row[0]) is not None
            ]
            if points:
                kpis["overall_avg"] = round(sum(points) / len(points), 2)
        finally:
            conn.close()

    return render_template(
        "dashboard.html",
        request,
        {"staff_list": staff_list, "kpis": kpis, "site_title": site_title},
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    if not is_admin(request):
        return RedirectResponse(url="/login", status_code=303)
    conn = get_db_connection()
    context = {
        "admin_username": ADMIN_USERNAME,
        "site_title": "DCLM HQ STAFF PEER ASSESSMENT",
        "staff_list": [],
    }
    if conn:
        try:
            context["admin_username"] = get_setting(conn, "admin_username", ADMIN_USERNAME)
            context["site_title"] = get_setting(conn, "site_title", "DCLM HQ STAFF PEER ASSESSMENT")
            context["staff_list"] = get_all_staff(conn)
        finally:
            conn.close()
    return render_template("settings.html", request, context)


@app.post("/api/settings/credentials")
async def update_credentials(request: Request):
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    body = await request.json()
    current_password = str(body.get("current_password") or "")
    new_username = str(body.get("username") or "").strip()
    new_password = str(body.get("new_password") or "")

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB connection failed")
    try:
        stored_user = get_setting(conn, "admin_username", ADMIN_USERNAME)
        stored_hash = get_setting(conn, "admin_password", "")
        if stored_hash:
            current_ok = verify_password(current_password, stored_hash)
        else:
            current_ok = hmac.compare_digest(current_password, ADMIN_PASSWORD)
        if not current_ok:
            raise HTTPException(status_code=400, detail="Current password is incorrect.")

        if new_username and new_username != stored_user:
            valid, message = validate_username(new_username)
            if not valid:
                raise HTTPException(status_code=400, detail=message)
            set_setting(conn, "admin_username", new_username)

        if new_password:
            valid, message = validate_password(new_password)
            if not valid:
                raise HTTPException(status_code=400, detail=message)
            if new_password != str(body.get("confirm_password") or ""):
                raise HTTPException(status_code=400, detail="New passwords do not match.")
            set_setting(conn, "admin_password", hash_password(new_password))

        return {"ok": True}
    finally:
        conn.close()


@app.post("/api/settings/site")
async def update_site_title(request: Request):
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    body = await request.json()
    valid, message = validate_site_title(body.get("site_title"))
    if not valid:
        raise HTTPException(status_code=400, detail=message)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB connection failed")
    try:
        set_setting(conn, "site_title", message)
        return {"ok": True, "site_title": message}
    finally:
        conn.close()


@app.post("/api/settings/staff")
async def update_staff(request: Request):
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    body = await request.json()
    action = body.get("action")

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB connection failed")
    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        if action == "add":
            valid, name = validate_staff_name(body.get("name"))
            if not valid:
                raise HTTPException(status_code=400, detail=name)
            if find_staff_member(conn, name):
                raise HTTPException(status_code=400, detail=f"{name} already exists.")
            cursor.execute(
                "INSERT INTO staff_names (id, name) VALUES (%s, %s)",
                (str(uuid.uuid4()), name),
            )
            conn.commit()
            return {"ok": True, "name": name}

        if action == "rename":
            staff_id = str(body.get("id") or "")
            valid, name = validate_staff_name(body.get("name"))
            if not valid:
                raise HTTPException(status_code=400, detail=name)
            cursor.execute("SELECT id FROM staff_names WHERE id = %s", (staff_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Staff member not found.")
            cursor.execute(
                "SELECT id FROM staff_names WHERE name = %s AND id != %s",
                (name, staff_id),
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail=f"{name} already exists.")
            cursor.execute(
                "UPDATE staff_names SET name = %s WHERE id = %s",
                (name, staff_id),
            )
            cursor.execute(
                "UPDATE appraisals SET staff_name = %s WHERE staff_id = %s",
                (name, staff_id),
            )
            conn.commit()
            return {"ok": True, "name": name}

        if action == "delete":
            staff_id = str(body.get("id") or "")
            cursor.execute("SELECT id FROM staff_names WHERE id = %s", (staff_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Staff member not found.")
            cursor.execute(
                "SELECT COUNT(*) AS c FROM appraisals WHERE staff_id = %s",
                (staff_id,),
            )
            if cursor.fetchone()["c"] > 0:
                raise HTTPException(
                    status_code=409,
                    detail="Cannot delete: this staff member already has appraisals.",
                )
            cursor.execute("DELETE FROM staff_names WHERE id = %s", (staff_id,))
            conn.commit()
            return {"ok": True}

        raise HTTPException(status_code=400, detail="Unknown action.")
    finally:
        conn.close()


@app.get("/api/submissions")
async def get_all(request: Request):
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB connection failed")
    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM appraisals ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return {"total": cursor.rowcount, "data": jsonable_encoder(rows)}
    finally:
        conn.close()


@app.get("/api/staff/{staff_id}")
async def staff_breakdown(request: Request, staff_id: str):
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB connection failed")
    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT id, name FROM staff_names WHERE id = %s", (staff_id,))
        staff = cursor.fetchone()
        if not staff:
            raise HTTPException(status_code=404, detail="Staff member not found")
        cursor.execute(
            "SELECT * FROM appraisals WHERE staff_id = %s ORDER BY created_at ASC",
            (staff_id,),
        )
        rows = cursor.fetchall()
        stats = compute_staff_stats(rows)
        stats["staff_id"] = staff_id
        stats["staff_name"] = staff["name"]
        return jsonable_encoder(stats)
    finally:
        conn.close()


@app.get("/api/export.csv")
async def export_csv(request: Request):
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB connection failed")
    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM appraisals ORDER BY created_at DESC")
        rows = cursor.fetchall()

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=[
            "created_at", "staff_name", "christian_conduct", "job_performance",
            "reliability", "teamwork", "communication", "initiative",
            "adaptability", "overall_assessment", "strengths", "improvements",
            "device_id", "device_ip",
        ])
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "created_at": str(row.get("created_at") or ""),
                "staff_name": row.get("staff_name"),
                "christian_conduct": row.get("christian_conduct"),
                "job_performance": row.get("job_performance"),
                "reliability": row.get("reliability"),
                "teamwork": row.get("teamwork"),
                "communication": row.get("communication"),
                "initiative": row.get("initiative"),
                "adaptability": row.get("adaptability"),
                "overall_assessment": row.get("overall_assessment"),
                "strengths": row.get("strengths"),
                "improvements": row.get("improvements"),
                "device_id": row.get("device_id"),
                "device_ip": row.get("device_ip"),
            })
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="appraisals.csv"'},
        )
    finally:
        conn.close()