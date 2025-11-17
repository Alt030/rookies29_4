import requests
from bs4 import BeautifulSoup

url = "https://jasoseol.com/search?dutyGroupIds=166"
baseurl = "https://jasoseol.com"

headers = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'}

r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')

lists = soup.select("#__next > div > div.responsive-layout > main > div.px-4 > div > main > div > a")

for post in lists:
    company = post.find("h5")
    title = post.find("h4")
    link = baseurl + post.get("href")
    times = post.select("div > div.flex-1.min-w-0.smUp\:mx-4 > div.mt-4.laptop\:mt-2.hidden.smUp\:block > div > div > span")

    start_time = times[0].string if len(times) > 0 else None
    end_time = times[2].string if len(times) > 2 else None
    
    print(company.string)
    print(title.string)
    print(link)
    print(start_time)
    print(end_time)
    print("===================================")