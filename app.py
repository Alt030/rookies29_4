import os
import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_mail import Mail, Message
from dotenv import load_dotenv
from db import get_connection

load_dotenv()

app = Flask(__name__)

app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

mail = Mail(app)


def send_email(to_email: str, subject: str, body: str):
    """
    테스트용
    """
    if not app.config.get("MAIL_SERVER") or not app.config.get("MAIL_USERNAME"):
        print("\nTEST")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print("Body:")
        print(body)
        print("-" * 40)
        return

    msg = Message(subject=subject, recipients=[to_email])
    msg.body = body
    mail.send(msg)

@app.route("/")
def index():
    return "ㅎㅇ"

# 키워드 검색 API
@app.route("/jobs", methods=["GET"])
def get_jobs():
    keyword = request.args.get("keyword", "").strip()

    if not keyword:
        return jsonify({"keyword 필요"}), 400

    like = f"%{keyword}%"

    sql = """
        SELECT
            id,
            company_name,
            title,
            start_time,
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
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (like, like, like))
            rows = cursor.fetchall()

    return jsonify(rows)

# 이메일 인증코드
@app.route("/auth/request-code", methods=["POST"])
def request_code():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip()

    if not email or "@" not in email:
        return jsonify({"error": "유효한 이메일을 입력하세요"}), 400

    code = f"{random.randint(0, 999999):06d}"
    expires_at = datetime.now() + timedelta(minutes=10)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO user (email, auth_code, auth_expires_at, is_verified, created_at)
                VALUES (%s, %s, %s, 0, NOW())
                ON DUPLICATE KEY UPDATE
                    auth_code = VALUES(auth_code),
                    auth_expires_at = VALUES(auth_expires_at),
                    is_verified = 0
            """
            cursor.execute(sql, (email, code, expires_at))
        conn.commit()

    subject = "[관심직업 알림 서비스] 이메일 인증코드 안내"
    body = f"인증코드: {code}\n10분 이내에 인증을 완료해주세요"
    send_email(email, subject, body)

    return jsonify({"message": "인증코드를 이메일로 발송했습니다."})

# 이메일 인증 및 사용자 정보
@app.route("/auth/verify", methods=["POST"])
def verify_and_register():
    data = request.get_json(silent=True) or request.form

    email = (data.get("email") or "").strip()
    code = (data.get("code") or "").strip()
    password = (data.get("password") or "").strip()
    keyword = (data.get("keyword") or "").strip()

    if not (email and code and password and keyword):
        return jsonify({"error": "email, code, password, keyword 모두 필요합니다."}), 400

    if len(password) != 4 or not password.isdigit():
        return jsonify({"error": "password는 숫자 4자리여야 합니다."}), 400

    with get_connection() as conn:
        with conn.cursor() as cursor:
            sql_select = """
                SELECT id, auth_code, auth_expires_at, is_verified
                FROM user
                WHERE email = %s
                LIMIT 1
            """
            cursor.execute(sql_select, (email,))
            user_row = cursor.fetchone()

            if not user_row:
                return jsonify({"error": "해당 이메일로 요청된 인증 정보가 없습니다."}), 400

            if user_row["auth_code"] != code:
                return jsonify({"error": "인증코드가 올바르지 않습니다."}), 400

            if not user_row["auth_expires_at"] or user_row["auth_expires_at"] < datetime.now():
                return jsonify({"error": "인증코드가 만료되었습니다."}), 400

            sql_update = """
                UPDATE user
                SET
                    password = %s,
                    keyword = %s,
                    is_verified = 1,
                    auth_code = NULL,
                    auth_expires_at = NULL
                WHERE id = %s
            """
            cursor.execute(sql_update, (password, keyword, user_row["id"]))

        conn.commit()

    return jsonify({
        "message": "이메일 인증 및 정보 설정이 완료되었습니다.",
        "email": email,
        "keyword": keyword
    })

# 이메일로 관련정보 발송
@app.route("/send-daily", methods=["GET"])
def send_daily():
    since = datetime.now() - timedelta(days=1)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT email, keyword
                FROM user
                WHERE
                    is_verified = 1
                    AND keyword IS NOT NULL
                    AND keyword <> ''
            """)
            users = cursor.fetchall()

            total_sent = 0

            for u in users:
                email = u["email"]
                keyword = u["keyword"]
                like = f"%{keyword}%"

                sql_jobs = """
                    SELECT
                        company_name,
                        title,
                        start_time,
                        end_time,
                        detail,
                        created_at
                    FROM job
                    WHERE
                        created_at >= %s
                        AND (
                            title LIKE %s
                            OR detail LIKE %s
                            OR company_name LIKE %s
                        )
                    ORDER BY created_at DESC
                """
                cursor.execute(sql_jobs, (since, like, like, like))
                jobs = cursor.fetchall()

                if not jobs:
                    continue

                lines = [f"[{keyword}] 키워드에 대한 최근 24시간 새 공고 목록입니다.", ""]
                for j in jobs:
                    line = f"- {j['company_name']} / {j['title']} / 등록일: {j['created_at']}"
                    lines.append(line)
                    if j["detail"]:
                        lines.append(f"  상세: {j['detail']}")
                    lines.append("")

                body = "\n".join(lines)
                subject = f"[취업 알림] '{keyword}' 관련 새 공고 {len(jobs)}건 안내"

                send_email(email, subject, body)
                total_sent += 1

    return jsonify({
        "message": "24시간 이내 새 공고 메일 발송 작업 완료",
        "target_users": len(users),
        "sent_to": total_sent
    })

# 구독 취소(keyword를 삭제하여 이메일 발송대상 제외)
@app.route("/unsubscribe", methods=["POST"])
def unsubscribe():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not (email and password):
        return jsonify({"error": "email, password 모두 필요합니다."}), 400

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, password
                FROM user
                WHERE email = %s
                LIMIT 1
            """, (email,))
            row = cursor.fetchone()

            if not row or str(row["password"]) != password:
                return jsonify({"error": "이메일 또는 비밀번호가 올바르지 않습니다."}), 400

            cursor.execute("""
                UPDATE user
                SET keyword = NULL
                WHERE id = %s
            """, (row["id"],))
        conn.commit()

    return jsonify({"message": "구독이 해지되었습니다."})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
