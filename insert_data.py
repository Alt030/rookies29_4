# similarity_utils.py


from difflib import SequenceMatcher

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


def similarity(a, b):
    return SequenceMatcher(None, a or "", b or "").ratio()


def is_similar_job(new_job, existing_jobs, threshold=0.85):
    new_title = new_job["title"] or ""
    new_company = new_job["company_name"] or ""

    for old in existing_jobs:
        old_title = old["title"] or ""
        old_company = old["company_name"] or ""

        title_ratio = similarity(new_title, old_title)
        company_ratio = similarity(new_company, old_company)

        if title_ratio >= threshold and company_ratio >= threshold:
            print(
                f"[매칭됨] '{new_company} / {new_title}'  <--->  "
                f"'{old_company} / {old_title}' "
                f"(title={title_ratio:.3f}, company={company_ratio:.3f})"
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
