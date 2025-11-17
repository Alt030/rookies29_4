# similarity_utils.py


from difflib import SequenceMatcher
import os, pymysql

# 크롤링 페이지 함수 중 get_existing_jobs 변경
# def get_existing_jobs():
#     conn = get_db_connection()
#     try:
#         with conn.cursor() as cursor:
#             cursor.execute("SELECT company_name, title FROM job")
#             rows = cursor.fetchall()
#             return rows
#     finally:
#         conn.close()

from dotenv import load_dotenv

load_dotenv()

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

def get_existing_jobs():
     conn = get_db_connection()
     try:
         with conn.cursor() as cursor:
             cursor.execute("SELECT company_name, title FROM job")
             rows = cursor.fetchall()
             return rows
     finally:
         conn.close()

def normalize_company(name : str) -> str:
    if not name:
        return ""
    n = name.lower()
    n = n.replace("주식회사", "")
    n = n.replace("(주)", "")
    n = n.replace("㈜", "")
    return n

def similarity(a, b):
    return SequenceMatcher(None, a or "", b or "").ratio()

def is_similar_job_normalize_company(new_job, existing_jobs, threshold=0.85):
    new_title = new_job.get("title", "") or ""
    new_company = normalize_company(new_job.get("company_name", ""))

    for old in existing_jobs:
        old_title = old.get("title", "") or ""
        old_company = normalize_company(old.get("company_name", ""))

        title_ratio = similarity(new_title, old_title)
        company_ratio = similarity(new_company, old_company)

        # 둘 다 기준 이상이면 같은 공고로 판단
        if title_ratio >= threshold and company_ratio >= threshold:
            print(f"[중복] {new_company}/{new_title} == {old_company}/{old_title}")
            print(
                f" (title={title_ratio:.3f}, company={company_ratio:.3f})"
            )
            return True

    return False
 
# 쓰는 방법 3) 유사도 기준으로 중복 여부 확인
    # duplicated = is_similar_job(sample_job, existing_jobs, threshold=0.85)

    # if duplicated:
    #     print("\n결과: 이 샘플 공고는 기존 공고와 '중복'으로 판단됩니다.")
    # else:
    #     print("\n결과: 이 샘플 공고는 '새로운 공고'로 판단됩니다.")
    #     insert_jobs([sample_job])
