import requests
from datetime import datetime, timezone
import os
import pymysql
import json
import insert_data

from dotenv import load_dotenv

load_dotenv()

def GetJobs(page: int = 1, page_size: int = 20):
    baseurl = "https://linkareer.com/activity/"
    url = "https://api.linkareer.com/graphql"

    variables = {
        "filterBy": {
            "status": "OPEN",
            "activityTypeID": "5",
            "categoryIDs": [],
        },
        "activityOrder": {
            "field": "RECENT",
            "direction": "DESC",
        },
        "page": page,
        "pageSize": page_size,
    }

    extensions = {
        "persistedQuery": {
            "version": 1,
            "sha256Hash": "e1076190cb0a0ba669a18e17907cbffb8c848d60f16ad06b896dc0171708ef80",
        }
    }

    params = {
        "operationName": "RecruitList",
        "variables": json.dumps(variables, ensure_ascii=False),
        "extensions": json.dumps(extensions, ensure_ascii=False),
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }

    res = requests.get(url, params=params, headers=headers)
    res.raise_for_status()
    data = res.json()

    activities = data["data"]["activities"]["nodes"]

    jobs = []
    for a in activities:
        close_at = None
        if a.get("recruitCloseAt"):
            close_at = datetime.fromtimestamp(a["recruitCloseAt"] / 1000.0)

        detail_url = baseurl + str(a["id"])

        job = {
            "title": a.get("title"),
            "company_name": a.get("organizationName"),
            "end_time": close_at,
            "detail": detail_url,
        }
        jobs.append(job)

    return jobs


def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        db=os.getenv("DB_NAME"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_existing_details(details: list[str]) -> set[str]:
    if not details:
        return set()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ",".join(["%s"] * len(details))
            sql = f"SELECT detail FROM job WHERE detail IN ({placeholders})"
            cursor.execute(sql, details)
            rows = cursor.fetchall()
            return {row["detail"] for row in rows}
    finally:
        conn.close()

def insert_jobs(job):
    if not job:
        return

    db = get_db_connection()
    try:
        cursor = db.cursor()

        sql = """
        INSERT INTO job (
            company_name, title, start_time, end_time, detail
        ) VALUES (
            %s, %s, %s, %s, %s
        )
        """

        cursor.execute(
            sql,
            (
                job["company_name"],
                job["title"],
                None,
                job["end_time"],
                job["detail"],
            ),
        )

        db.commit()
    finally:
        cursor.close()
        db.close()


def main():
    exitsting_jobs = insert_data.get_existing_jobs()
    PAGE_SIZE = 20
    page = 1
    total_new = 0

    while True:
        print(f"{page}페이지 크롤링")
        jobs = GetJobs(page=page, page_size=PAGE_SIZE)

        if not jobs:
            print("크롤링 종료")
            break

        page_details = [job["detail"] for job in jobs]

        existing = get_existing_details(page_details)

        new_jobs = [job for job in jobs if job["detail"] not in existing]

        if not new_jobs:
            print(f"{page} 페이지에 새로운 공고가 없습니다")
            break

        for job in new_jobs:
            if not insert_data.is_similar_job_normalize_company(job, exitsting_jobs):
                insert_jobs(job)
                total_new += len(job)
            else:
                print(f"{job} 중복 제거")

        if len(jobs) < PAGE_SIZE:
            print(f"{page}: 길이 {len(jobs)} < {PAGE_SIZE}, 마지막 페이지이므로 종료.")
            break

        page += 1

    print(f"새로 저장한 공고 수: {total_new}건")

if __name__ == "__main__":
    main()
