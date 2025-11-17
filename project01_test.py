import requests
from bs4 import BeautifulSoup
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

load_dotenv()

def crawl_jobs(max_pages=20):
    url = "https://jasoseol.com/search?dutyGroupIds=166%2C175%2C176%2C177%2C178&excludeClosed=true"
    jobs = []

    for page in range(1, max_pages + 1):
        params = {"page": page}
        res = requests.get(url, params=params)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        items = soup.select("main a")

        for item in items:
            href = item.get("href")

            company_tag = item.select_one("h5")
            company = company_tag.get_text(strip=True) if company_tag else "정보없음"

            title_tag = item.select_one("h4")
            title = title_tag.get_text(strip=True) if title_tag else "정보없음"

            period_tag = item.select_one("div:nth-of-type(2) > div:nth-of-type(4) > div > div")
            period_text = period_tag.get_text(strip=True) if period_tag else "정보없음"

            if "~" in period_text:
                start_date, end_date = [x.strip() for x in period_text.split("~", 1)]
            else:
                start_date = period_text
                end_date = "정보없음"

            detail_url = "https://jasoseol.com" + href

            jobs.append({
                "company": company,
                "title": title,
                "start_date": start_date,
                "end_date": end_date,
                "detail": detail_url
            })

    return jobs

def save_and_print(jobs, filename="pj01_test.txt"):
    with open(filename, "w", encoding="utf-8") as f:
        for job in jobs:
            line = (
                f"회사명: {job['company']}\n"
                f"제목: {job['title']}\n"
                f"채용시작일: {job['start_date']}\n"
                f"채용마감일: {job['end_date']}\n"
                f"링크: {job['detail']}\n"
                "--------------------------\n"
            )
            f.write(line)
            print(line)

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

        sql = """
        INSERT INTO job (company_name, title, start_time, end_time, detail)
        VALUES (%s, %s, %s, %s, %s)
        """

        for job in jobs:
            cursor.execute(sql, (
                job["company"],
                job["title"],
                job["start_date"],
                job["end_date"],
                job["detail"]
            ))

        conn.commit()
        print(f"DB에 채용공고 {len(jobs)}건 저장 완료")

    except Error as e:
        print("MySQL 오류:", e)

    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    job_list = crawl_jobs(max_pages=20)
    if job_list:
        save_and_print(job_list)
        save_to_mysql(job_list)

        print(f"채용공고 {len(job_list)}건 크롤링 완료 / pj01_test.txt 저장 완료")
    else:
        print("크롤링된 채용공고가 없음")

