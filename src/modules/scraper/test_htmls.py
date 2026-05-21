
from bs4 import BeautifulSoup
import quopri

with open('D:\\datasets\\ruoubia-thuocla-sua\\htmls\\shoppee-đồ uống có cồn\\[Chính hãng] - Rượu Vang Đỏ Pháp Francis Gillot Shiraz - 750ml (13,5%) Mia Wine _ Shopee Việt Nam.mhtml', 'r', encoding='utf-8') as f:
    content = f.read()

# Tìm đoạn HTML thực sự (sau boundary)
start = content.find('<!DOCTYPE html')
html = content[start:]

# Giải mã quoted-printable
html = quopri.decodestring(html).decode('utf-8', errors='ignore')

soup = BeautifulSoup(html, 'html.parser')

title = soup.title.string if soup.title else ''
og_title = soup.find('meta', property='og:title')
og_desc = soup.find('meta', property='og:description')
og_image = soup.find('meta', property='og:image')

print('Title:', title)
print('OG Title:', og_title['content'] if og_title else '')
print('OG Description:', og_desc['content'] if og_desc else '')
print('OG Image:', og_image['content'] if og_image else '')

# Giá sản phẩm
price = ''
price_tag = soup.find('div', class_='IZPeQz B67UQ0')
if price_tag:
    price = price_tag.get_text(strip=True)

# Thuộc tính sản phẩm
attributes = {}
for attr in soup.select('div.ybxj32'):
    key_tag = attr.find('h3', class_='VJOnTD')
    value_tag = key_tag.find_next_sibling('div') if key_tag else None
    if key_tag and value_tag:
        key = key_tag.get_text(strip=True)
        value = value_tag.get_text(strip=True)
        attributes[key] = value

# Mô tả chi tiết
desc = ''
desc_block = soup.find('div', class_='e8lZp3')
if desc_block:
    desc = '\n'.join(p.get_text(strip=True) for p in desc_block.find_all('p', class_='QN2lPu'))

print('Giá:', price)
print('Thuộc tính:', attributes)
print('Mô tả chi tiết:', desc)