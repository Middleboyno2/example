import requests
from bs4 import BeautifulSoup
import pandas as pd
import os

CSV_FILE = "books.csv"

def scrape_books(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    
    books = []
    genre = soup.select_one(".tieu_de").text.strip() if soup.select_one(".tieu_de") else ""
    
    for item in soup.select(".product-small"):
        title_tag = item.select_one(".product-title a")
        
        title = title_tag.text.strip() if title_tag else ""
        link = title_tag["href"] if title_tag else ""
        
        status = ""
        
        books.append({
            "title": title,
            "author": "",
            "genre": genre,
            "status": status,
            "url": link,
            "file_path": ""
        })
        print("update:", title)

    
    return pd.DataFrame(books)

def update_csv(new_data: pd.DataFrame):
    if not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0:
        combined = new_data
    else:
        try:
            old_data = pd.read_csv(CSV_FILE)
            combined = pd.concat([old_data, new_data]).drop_duplicates(subset=["title"])
        except pd.errors.EmptyDataError:
            combined = new_data
    
    combined.to_csv(CSV_FILE, index=False)

# Chạy update
url_epub_tien_hiep = "https://ebookvie.com/ebook-hot/" 
new_books = scrape_books(url_epub_tien_hiep)
update_csv(new_books)

print("Đã cập nhật dữ liệu. Tổng số truyện:", len(pd.read_csv(CSV_FILE)))
