import httpx
from bs4 import BeautifulSoup
resp = httpx.get('https://github.com/trending', headers={'User-Agent': 'Mozilla/5.0'}, follow_redirects=True, timeout=30)
soup = BeautifulSoup(resp.text, 'html.parser')
articles = soup.select('article.Box-row')
with open('c:\\users\\jembo\\projects\\radar\\debug_out.txt', 'w', encoding='utf-8') as f:
    for i, a in enumerate(articles):
        h2 = a.select_one('h2')
        a_tag = h2.select_one('a') if h2 else None
        href = a_tag.get('href','').strip('/') if a_tag else 'NO LINK'
        desc_tag = a.select_one('p')
        desc = desc_tag.get_text(strip=True)[:60] if desc_tag else 'NO DESC'
        f.write(f'{i}: {href}: "{desc}"\n')
