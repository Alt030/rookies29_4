import requests
from bs4 import BeautifulSoup
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

# 🔹 .env 파일 로드 (DB 접속 정보 불러오기)
load_dotenv()


# ============================================
# 🔹 채용공고 크롤링 함수
# ============================================
def crawl_jobs(max_pages=20):
    # 크롤링 대상 URL
    url = "https://jasoseol.com/search?dutyGroupIds=166%2C175%2C176%2C177%2C178&excludeClosed=true"
    jobs = []  # 크롤링한 데이터 저장 리스트

    # 1~20페이지까지 반복 크롤링
    for page in range(1, max_pages + 1):
        params = {"page": page}  # GET 파라미터 설정
        res = requests.get(url, params=params)
        res.raise_for_status()   # 요청 실패 시 오류 발생

        soup = BeautifulSoup(res.text, "html.parser")

        # 채용공고 목록에서 <a> 태그만 선택
        items = soup.select("main a")

        for item in items:
            href = item.get("href")  # 상세 페이지 URL

            # 회사명 추출
            company_tag = item.select_one("h5")
            company = company_tag.get_text(strip=True) if company_tag else "정보없음"

            # 채용 제목 추출
            title_tag = item.select_one("h4")
            title = title_tag.get_text(strip=True) if title_tag else "정보없음"

            # 채용 기간 텍스트 추출
            period_tag = item.select_one("div:nth-of-type(2) > div:nth-of-type(4) > div > div")
            period_text = period_tag.get_text(strip=True) if period_tag else "정보없음"

            # "시작일~종료일" 형태일 때 분리
            if "~" in period_text:
                start_date, end_date = [x.strip() for x in period_text.split("~", 1)]
            else:
                start_date = period_text
                end_date = "정보없음"

            # 상세 페이지 링크 생성
            detail_url = "https://jasoseol.com" + href if href else "정보없음"

            # 리스트에 저장
            jobs.append({
                "company": company,
                "title": title,
                "start_date": start_date,
                "end_date": end_date,
                "detail": detail_url
            })

    return jobs


# ============================================
# 🔹 크롤링 결과 txt 파일 저장 + 출력 함수
# ============================================
def save_and_print(jobs, filename="pj01_test.txt"):
    with open(filename, "w", encoding="utf-8") as f:
        for job in jobs:
            # 한 채용공고 출력 포맷
            line = (
                f"회사명: {job['company']}\n"
                f"제목: {job['title']}\n"
                f"채용시작일: {job['start_date']}\n"
                f"채용마감일: {job['end_date']}\n"
                f"링크: {job['detail']}\n"
                "--------------------------\n"
            )
            f.write(line)  # 파일 저장
            print(line)    # 화면 출력


# ============================================
# 🔹 MySQL DB 저장 함수
# ============================================
def save_to_mysql(jobs):
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        cursor = conn.cursor()

        # 🔹 DB 중복 체크용 SQL
        check_sql = "SELECT COUNT(*) FROM job WHERE detail = %s"

        # 🔹 신규 데이터 저장 SQL
        insert_sql = """
        INSERT INTO job (company_name, title, start_time, end_time, detail)
        VALUES (%s, %s, %s, %s, %s)
        """

        inserted_count = 0  # 실제 저장된 개수 계산

        for job in jobs:
            # 🔸 detail 기준 중복 체크
            cursor.execute(check_sql, (job["detail"],))
            result = cursor.fetchone()

            if result[0] > 0:
                print(f"중복 데이터 스킵됨: {job['detail']}")
                continue  # 중복 → 저장 안함

            # 🔸 중복 아니면 INSERT
            cursor.execute(insert_sql, (
                job["company"],
                job["title"],
                job["start_date"],
                job["end_date"],
                job["detail"]
            ))

            inserted_count += 1

        conn.commit()
        print(f"DB 저장 완료: {inserted_count}건 저장 / {len(jobs)}건 중복 제외됨")

    except Error as e:
        print("MySQL 오류:", e)

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()



# ============================================
# 🔹 메인 실행
# ============================================
if __name__ == "__main__":
    # 1~20페이지 크롤링
    job_list = crawl_jobs(max_pages=20)

    if job_list:
        save_and_print(job_list)   # txt 저장 + 출력
        save_to_mysql(job_list)    # DB 저장

        print(f"채용공고 {len(job_list)}건 크롤링 완료 / pj01_test.txt 저장 완료")
    else:
        print("크롤링된 채용공고가 없음")
