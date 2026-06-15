from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional
from dotenv import load_dotenv
import os
import uuid
import logging
import pymysql
from pymysql import Error

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="DCLM Appraisal")

# ✅ FIXED: Removed ../ — now points CORRECTLY inside /app folder
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")  # ✅ Fixed path

# ✅ CloudClusters config — 100% UNCHANGED
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT")),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DB"),
    "connect_timeout": 60,
    "ssl": {"ssl": True},
    "charset": "utf8mb4"
}

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

def create_table():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
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
            conn.commit()
            logger.info("✅ Table ready")
        except Error as e:
            logger.error(f"❌ Table error: {str(e)}")
        finally:
            if conn and conn.open:
                conn.close()

@app.on_event("startup")
async def startup():
    create_table()

@app.get("/health")
async def health():
    conn = get_db_connection()
    if conn:
        conn.close()
        return {"status": "ok", "message": "✅ Database connected"}
    return {"status": "error", "message": "❌ Database failed"}, 500

@app.get("/", response_class=HTMLResponse)
async def form(request: Request):
    return templates.TemplateResponse(
        "index.html",
        context={"request": request}
    )

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
    improvements: Optional[str] = Form(None)
):
    if not all([staff_name, christian_conduct, job_performance, reliability, teamwork, communication, initiative, adaptability, overall_assessment]):
        return templates.TemplateResponse(
            "index.html",
            context={"request": request, "error": "Fill all required fields"}
        )

    conn = get_db_connection()
    if not conn:
        return templates.TemplateResponse(
            "index.html",
            context={"request": request, "error": "❌ Database connection failed — check CloudClusters remote access"}
        )

    try:
        appraisal_id = str(uuid.uuid4())
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO appraisals 
        (id, staff_name, christian_conduct, job_performance, reliability, teamwork, communication, initiative, adaptability, overall_assessment, strengths, improvements)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            appraisal_id, staff_name, christian_conduct, job_performance, reliability,
            teamwork, communication, initiative, adaptability, overall_assessment,
            strengths or "", improvements or ""
        ))
        conn.commit()
        logger.info(f"✅ Saved: {appraisal_id}")
        return templates.TemplateResponse(
            "index.html",
            context={"request": request, "success": "✅ Submitted successfully!"}
        )
    finally:
        conn.close()

@app.get("/api/submissions")
async def get_all():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="DB connection failed")
    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM appraisals ORDER BY created_at DESC")
        return {"total": cursor.rowcount, "data": cursor.fetchall()}
    finally:
        conn.close()