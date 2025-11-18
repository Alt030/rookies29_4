import os
import random
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash,
)
from flask_mail import Mail, Message
from dotenv import load_dotenv
from db import get_connection
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

mail = Mail(app)

VERIFICATION_CODE_LENGTH = 6


def send_email(to_email: str, subject: str, body: str):
    """실제 메일 설정이 없으면 콘솔에만 출력, 있으면 Flask-Mail로 발송"""
    if not app.config.get("MAIL_SERVER") or not app.config.get("MAIL_USERNAME"):
        print("\nTest")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print("Body:")
        print(body)
        print("-" * 40)
        return

    msg = Message(subject=subject, recipients=[to_email])
    msg.body = body
    mail.send(msg)


@app.route("/", methods=["GET", "POST"])
def home():
    """
    GET  → index.html 기본 화면
    POST → 
      1) verification_code 있으면: 이메일 인증 처리 → 비밀번호 설정 화면으로 이동
      2) set_password_* 있으면: 비밀번호 설정 처리
      3) 그 외: 알림 등록(이메일+키워드) / 구독 취소(이메일+비번)
    """

    if request.method == "GET":
        return render_template(
            "index.html",
            is_pending_verification=False,
            is_setting_password=False,
            pending_email=None,
            email_to_set_password=None,
            verification_code_length=VERIFICATION_CODE_LENGTH,
        )

    form = request.form

    verification_code = form.get("verification_code", "").strip()
    if verification_code:
        email = form.get("email", "").strip()

        if not email:
            flash("이메일 정보가 없습니다. 처음부터 다시 시도해주세요.", "danger")
            return redirect(url_for("home"))

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, auth_code, auth_expires_at, is_verified
                    FROM user
                    WHERE email = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (email,),
                )
                row = cursor.fetchone()

                if not row:
                    flash("해당 이메일로 요청된 인증 정보가 없습니다.", "danger")
                    return redirect(url_for("home"))

                if row["is_verified"]:
                    flash("이미 인증이 완료된 사용자입니다.", "warning")
                    return redirect(url_for("home"))

                if row["auth_code"] != verification_code:
                    flash("인증 코드가 올바르지 않습니다.", "danger")
                    return render_template(
                        "index.html",
                        is_pending_verification=True,
                        is_setting_password=False,
                        pending_email=email,
                        email_to_set_password=None,
                        verification_code_length=VERIFICATION_CODE_LENGTH,
                    )

                if row["auth_expires_at"] and row["auth_expires_at"] < datetime.now():
                    flash("인증 코드가 만료되었습니다. 다시 요청해주세요.", "danger")
                    return redirect(url_for("home"))

                cursor.execute(
                    """
                    UPDATE user
                    SET is_verified = 1, auth_code = NULL, auth_expires_at = NULL
                    WHERE id = %s
                    """,
                    (row["id"],),
                )
            conn.commit()

        flash("이메일 인증이 완료되었습니다. 이제 비밀번호를 설정해주세요.", "success")
        return render_template(
            "index.html",
            is_pending_verification=False,
            is_setting_password=True,
            pending_email=None,
            email_to_set_password=email,
            verification_code_length=VERIFICATION_CODE_LENGTH,
        )

    set_pw1 = form.get("set_password_1", "").strip()
    set_pw2 = form.get("set_password_2", "").strip()
    email_for_pw = form.get("email_to_set_password", "").strip()

    if set_pw1 or set_pw2:
        if not email_for_pw:
            flash("이메일 정보가 없습니다. 처음부터 다시 시도해주세요.", "danger")
            return redirect(url_for("home"))

        if set_pw1 != set_pw2:
            flash("두 비밀번호가 서로 일치하지 않습니다.", "danger")
            return render_template(
                "index.html",
                is_pending_verification=False,
                is_setting_password=True,
                pending_email=None,
                email_to_set_password=email_for_pw,
                verification_code_length=VERIFICATION_CODE_LENGTH,
            )

        if len(set_pw1) != 4 or not set_pw1.isdigit():
            flash("비밀번호는 숫자 4자리여야 합니다.", "danger")
            return render_template(
                "index.html",
                is_pending_verification=False,
                is_setting_password=True,
                pending_email=None,
                email_to_set_password=email_for_pw,
                verification_code_length=VERIFICATION_CODE_LENGTH,
            )

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE user
                    SET password = %s
                    WHERE email = %s
                    """,
                    (set_pw1, email_for_pw),
                )
            conn.commit()

        flash("비밀번호 설정이 완료되었습니다. 이제 서비스 이용이 가능합니다.", "success")
        return redirect(url_for("home"))

    email = form.get("email", "").strip()
    keyword = form.get("keyword", "").strip()
    password = form.get("psword", "").strip()

    if not email:
        flash("이메일은 필수입니다.", "danger")
        return redirect(url_for("home"))

    if keyword and not password:
        code = f"{random.randint(0, 10**VERIFICATION_CODE_LENGTH - 1):0{VERIFICATION_CODE_LENGTH}d}"
        expires_at = datetime.now() + timedelta(minutes=10)

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO user (email, keyword, auth_code, auth_expires_at, is_verified, created_at)
                    VALUES (%s, %s, %s, %s, 0, NOW())
                    ON DUPLICATE KEY UPDATE
                        keyword = VALUES(keyword),
                        auth_code = VALUES(auth_code),
                        auth_expires_at = VALUES(auth_expires_at),
                        is_verified = 0
                    """,
                    (email, keyword, code, expires_at),
                )
            conn.commit()

        subject = "[JOB-FINDER] 이메일 인증 코드 안내"
        body = f"인증 코드: {code}\n10분 이내에 입력해주세요."
        send_email(email, subject, body)

        flash(f"인증 코드가 {email} 로 발송되었습니다.", "info")

        return render_template(
            "index.html",
            is_pending_verification=True,
            is_setting_password=False,
            pending_email=email,
            email_to_set_password=None,
            verification_code_length=VERIFICATION_CODE_LENGTH,
        )

    if password and not keyword:
        if len(password) != 4 or not password.isdigit():
            flash("비밀번호는 숫자 4자리여야 합니다.", "danger")
            return redirect(url_for("home"))

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, password
                    FROM user
                    WHERE email = %s
                    LIMIT 1
                    """,
                    (email,),
                )
                row = cursor.fetchone()

                if not row or str(row["password"]) != password:
                    flash("이메일 또는 비밀번호가 올바르지 않습니다.", "danger")
                    return redirect(url_for("home"))

                cursor.execute(
                    """
                    UPDATE user
                    SET keyword = NULL
                    WHERE id = %s
                    """,
                    (row["id"],),
                )
            conn.commit()

        flash("구독이 해지되었습니다.", "success")
        return redirect(url_for("home"))

    flash("입력 조건이 맞지 않습니다. 안내 문구를 다시 확인해주세요.", "warning")
    return redirect(url_for("home"))



@app.route("/search", methods=["POST"])
def search():
    """검색 폼에서 넘어온 키워드로 job 테이블 조회 후 results.html 렌더링"""
    query = (request.form.get("query") or "").strip()
    if not query:
        flash("검색 키워드를 입력해주세요.", "danger")
        return redirect(url_for("home"))

    first_keyword = query.split(",")[0].strip()
    like = f"%{first_keyword}%"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    company_name,
                    title,
                    end_time,
                    detail,
                    created_at
                FROM job
                WHERE
                    title LIKE %s
                    OR detail LIKE %s
                    OR company_name LIKE %s
                ORDER BY end_time ASC
                LIMIT 100
                """,
                (like, like, like),
            )
            rows = cursor.fetchall()

    job_list = []
    keywords_for_display = [kw.strip() for kw in query.split(",") if kw.strip()]

    for r in rows:
        job_list.append(
            {
                "title": r["title"],
                "company": r["company_name"],
                "deadline": r["end_time"],
                "url": "#",
                "keywords": keywords_for_display,
            }
        )

    return render_template("result.html", query=query, job_list=job_list)

def send_daily():
    since = datetime.now() - timedelta(days=1)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT email, keyword
                FROM user
                WHERE is_verified = 1
                  AND keyword IS NOT NULL
                  AND keyword <> ''
            """)
            users = cursor.fetchall()

            for u in users:
                email = u["email"]
                keyword = u["keyword"]
                like = f"%{keyword}%"

                cursor.execute("""
                    SELECT company_name, title, start_time, end_time, detail, created_at
                    FROM job
                    WHERE created_at >= %s
                      AND (title LIKE %s OR detail LIKE %s OR company_name LIKE %s)
                    ORDER BY created_at DESC
                """, (since, like, like, like))

                jobs = cursor.fetchall()
                if not jobs:
                    continue

                lines = [f"[{keyword}] 최근 24시간 동안 추가된 공고 목록입니다.", ""]
                for j in jobs:
                    lines.append(f"- {j['company_name']} / {j['title']} / 등록일: {j['created_at']}")
                    if j["detail"]:
                        lines.append(f"  상세: {j['detail']}")
                    lines.append("")

                body = "\n".join(lines)
                subject = f"[취업 알림] '{keyword}' 관련 신규 공고 {len(jobs)}건 안내"

                send_email(email, subject, body)

scheduler = BackgroundScheduler(timezone="Asia/Seoul")
scheduler.add_job(
    func=send_daily,
    trigger=CronTrigger(hour=13, minute=0),
    id="send_daily_job",
    replace_existing=True
)

scheduler.start()

if __name__ == "__main__":
    app.run(debug=True, port=5000)