import requests
from bs4 import BeautifulSoup
import pandas as pd
import urllib

def get_page_content(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        print(f"请求失败，状态码: {response.status_code}")
        return None


def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    questions = []
    for item in soup.find_all('div', class_='List-item'):
        question = {}
        title = item.find('h2', class_='QuestionItem-title')
        if title:
            question['title'] = title.get_text(strip=True)
        answer = item.find('span', class_='RichText ztext CopyrightRichText-richText')
        if answer:
            question['answer'] = answer.get_text(strip=True)
        questions.append(question)
    return questions


def search_zhihu(query, page=1):
    base_url = "https://www.zhihu.com/search"
    params = {
        'q': query,
        'type': 'content',
        'page': page
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    html = get_page_content(url)
    if html:
        return parse_html(html)
    return []


def main():
    query = input("请输入要搜索的问题关键词: ")
    results = []
    for page in range(1, 4):  # 搜索前5页
        page_results = search_zhihu(query, page)
        results.extend(page_results)

    df = pd.DataFrame(results)
    df.to_csv('zhihu_answers.csv', index=False, encoding='utf-8-sig')
    print(f"搜索结果已保存到 zhihu_answers.csv")


if __name__ == "__main__":
    main()
