import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode

ExcludeClosed = "true"
baseurl = "https://jasoseol.com"

duty_ids = ",".join([
    "160","164","165","166","167","168","169","170","171","172",
    "173","174","175","176","177","178","179","180","181","182"
])

headers = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'}

MAX_PAGE = 20

index = 0

for page in range(1, MAX_PAGE + 1):

    params = {
        "page": page,
        "dutyGroupIds": duty_ids,
        "excludeClosed": "true"
    }

    url = f"{baseurl}/search?{urlencode(params)}"

    print(f"============={page} 페이지=============")
    print(url)

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')

    lists = soup.select("#__next > div > div.responsive-layout > main > div.px-4 > div > main > div > a")

    if not lists or len(lists) < 3:
        print("크롤링 종료.")
        break

    for post in lists:
        company = post.find("h5")
        title = post.find("h4")
        link = baseurl + post.get("href")
        times = post.select("div > div.flex-1.min-w-0.smUp\:mx-4 > div.mt-4.laptop\:mt-2.hidden.smUp\:block > div > div > span")

        start_time = times[0].string if len(times) > 0 else None
        end_time = times[2].string if len(times) > 2 else None

        index += 1

        print(company.string)
        print(title.string)
        print(link)
        print(start_time)
        print(end_time)
        print("===================================")

print(f"{index}개 채용 공고 크롤링 완료.")