import os
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import pymysql

load_dotenv()

# DB 연결
conn = pymysql.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    charset="utf8mb4"
)
cursor = conn.cursor()


HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/142.0.0.0 Safari/537.36'
    )
}

KEYWORDS = "정보보호"

BASE_URL = (
    "https://www.saramin.co.kr/zf_user/search"
    f"?search_area=main&search_done=y&search_optional_item=n"
    f"&searchType=search&searchword={KEYWORDS}"
)

PAGE_LIMIT = 2


# 날짜 
import re
from datetime import datetime

def parse_date(text: str):
    """
    사람인 마감일 파싱:
      - "2025.03.14", "2025-03-14" 같은 연도 포함 형식
      - "~ 12/13(토)" 처럼 MM/DD(요일)만 있는 형식
      - 그 외(상시채용 등)는 None
    """
    if not text:
        return None

    text = text.strip()


    # "~ 12/13(토)" 처럼 MM/DD만 있는 경우
    m = re.search(r"(\d{1,2})/(\d{1,2})", text)
    if m:
        mo, d = map(int, m.groups())
        year = datetime.now().year   # 현재 연도 기준

        try:
            dt = datetime(year, mo, d)
        except ValueError:
            return None

        # 연말에 크롤링했는데 날짜가 이미 훨씬 과거라면 → 내년 걸로 보정
        today = datetime.now()
        if dt < today and (today - dt).days > 200:
            # 예: 오늘이 12/30인데 마감이 01/05 이런 경우 대비
            try:
                dt = datetime(year + 1, mo, d)
            except ValueError:
                return None

        return dt

    # 3) 그 외("상시채용", "채용시까지" 등)은 날짜 없음
    return None


# 크롤링 
for page in range(1, PAGE_LIMIT + 1):

    url = f"{BASE_URL}&recruitPage={page}"
    print(f"\n======= {page} 페이지 처리 중 =======")

    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    title_tags = soup.select("#recruit_info_list > div.content > div > div.area_job > h2 > a")
    company_tags = soup.select("#recruit_info_list > div.content > div > div.area_corp > strong > a")
    end_date_tags = soup.select("#recruit_info_list > div.content > div > div.area_job > div.job_date > span")

    for title_tag, company_tag, end_tag in zip(title_tags, company_tags, end_date_tags):

        title = title_tag.get_text(strip=True)
        company_name = company_tag.get_text(strip=True)
        end_date_text = end_tag.get_text(strip=True)
        end_time = parse_date(end_date_text)

        # 상세공고 URL
        detail_url = title_tag.get("href", "")
        if detail_url and not detail_url.startswith("http"):
            detail_url = "https://www.saramin.co.kr" + detail_url

        start_time = None   # 사람인은 시작일 없음 → NULL

        

        # INSERT
        insert_sql = """
            INSERT INTO job
                (company_name, title, start_time, end_time, detail)
            VALUES
                (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_sql, (
            company_name,
            title,
            start_time,
            end_time,
            detail_url
        ))
        conn.commit()

        print(f"[저장 완료] {company_name} - {title}")


cursor.close()
conn.close()

print("\n===== 전체 작업 완료 =====")
