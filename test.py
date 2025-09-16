from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
import json

CSV_FILE = "books.csv"

def setup_driver(headless=True):
    """Thiết lập Chrome driver với chặn quảng cáo và popup"""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    
    # Các tùy chọn bảo mật và hiệu suất
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Chặn các loại nội dung có thể gây rắc rối
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")  # Tắt hình ảnh để tăng tốc
    
    # Chặn popup và redirect
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--block-new-web-contents")
    
    # Thêm user agent thực tế
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Tắt JavaScript không cần thiết (có thể gây quảng cáo)
    prefs = {
        "profile.default_content_setting_values": {
            "notifications": 2,  # Chặn thông báo
            "media_stream": 2,   # Chặn camera/mic
            "geolocation": 2,    # Chặn vị trí
        },
        # "profile.managed_default_content_settings": {
        #     "images": 2  # Chặn hình ảnh
        # }
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Thiết lập timeout để tránh chờ lâu
    driver.set_page_load_timeout(30)
    
    return driver

def get_page_data(driver):
    """Trích xuất dữ liệu từ trang hiện tại"""
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    books = []
    products = soup.select(".product-small")
    
    for item in products:
        title_tag = item.select_one(".product-title a")
        
        if title_tag:
            title = title_tag.text.strip()
            link = title_tag.get("href", "")
            
            # Lấy thông tin lượt xem và tải xuống
            views_tag = item.select_one(".tdk-product-loop-custom-product-meta .last-updated-date span")
            downloads_tag = item.select_one(".tdk-product-loop-custom-product-meta .version")
            
            views = views_tag.text.strip() if views_tag else "0"
            downloads = downloads_tag.text.strip() if downloads_tag else "0"
            
            # Lấy category
            category_tag = item.select_one(".category")
            category = category_tag.text.strip() if category_tag else "Hot"
            
            books.append({
                "title": title,
                "author": "",
                "genre": category,
                "status": "",
                "url": link,
                "file_path": "",
                "views": views,
                "downloads": downloads
            })
    
    return books

def get_pagination_info(driver):
    """Lấy thông tin phân trang từ ux-relay data"""
    try:
        relay_element = driver.find_element(By.CSS_SELECTOR, '[data-flatsome-relay]')
        relay_data = json.loads(relay_element.get_attribute('data-flatsome-relay'))
        
        current_page = relay_data.get('currentPage', 1)
        total_pages = relay_data.get('totalPages', 1)
        
        return current_page, total_pages
    except:
        # Fallback: đếm từ pagination links
        try:
            page_numbers = driver.find_elements(By.CSS_SELECTOR, '.page-numbers .page-number')
            max_page = 1
            for elem in page_numbers:
                if elem.text.strip().isdigit():
                    max_page = max(max_page, int(elem.text.strip()))
            return 1, max_page
        except:
            return 1, 1

def close_popups_and_ads(driver):
    # Đóng các popup quảng cáo có thể xuất hiện
    try:
        # Đợi một chút để popup load
        time.sleep(2)
        
        # Danh sách các selector có thể là popup/ads
        popup_selectors = [
            # Popup close buttons
            'button[class*="close"]',
            'button[class*="dismiss"]', 
            '[class*="modal"] button',
            '[class*="popup"] button',
            '.close-button',
            '.btn-close',
            
            # Ad close buttons
            '[id*="close"]',
            '[class*="ad-close"]',
            '[aria-label*="close" i]',
            '[title*="close" i]',
            
            # Overlay elements
            '.overlay',
            '.modal-backdrop',
            '.popup-overlay'
        ]
        
        for selector in popup_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        driver.execute_script("arguments[0].click();", element)
                        print(f"Đã đóng popup với selector: {selector}")
                        time.sleep(1)
                        break
            except:
                continue
                
        # Kiểm tra nếu có tab/window mới bị mở
        if len(driver.window_handles) > 1:
            print("Phát hiện tab mới, đóng và quay về tab chính...")
            main_window = driver.window_handles[0]
            for handle in driver.window_handles[1:]:
                driver.switch_to.window(handle)
                driver.close()
            driver.switch_to.window(main_window)
            
    except Exception as e:
        print(f"Lỗi khi xử lý popup: {str(e)}")

def safe_click_next_page(driver):
    # Click an toàn vào nút next page với xử lý popup
    try:
        # Đóng popup trước khi click
        close_popups_and_ads(driver)
        
        # Tìm nút next
        next_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '.next.page-number'))
        )
        
        # Scroll đến button và đợi
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
        time.sleep(5)
    
        # Lưu URL hiện tại để kiểm tra
        current_url = driver.current_url
        
        # Click bằng JavaScript để tránh các element che
        driver.execute_script("arguments[0].click();", next_button)
        print("Đã click nút Next")
        
        # Đợi AJAX load
        time.sleep(5)
        
        # Xử lý popup sau khi click
        close_popups_and_ads(driver)
        
        # Kiểm tra xem có bị redirect không
        if driver.current_url != current_url:
            print(f"Phát hiện redirect từ {current_url} sang {driver.current_url}")
            driver.get(current_url)  # Quay về trang gốc
            time.sleep(5)
            return False
        
        # Đợi nội dung mới load
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.product-small'))
        )
        
        # Thêm delay để đảm bảo hoàn tất
        time.sleep(5)
        
        return True
        
    except Exception as e:
        print(f"Lỗi khi click next page: {str(e)}")
        close_popups_and_ads(driver)
        return False

def scrape_all_pages_selenium(url, max_pages=None):
    # Cào tất cả trang sử dụng Selenium
    driver = setup_driver(headless=False)  # Set False để xem quá trình
    all_books = []
    
    try:
        print(f"Đang truy cập: {url}")
        driver.get(url)
        
        # Đợi trang load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.product-small'))
        )
        
        current_page, total_pages = get_pagination_info(driver)
        print(f"Phát hiện {total_pages} trang")
        
        if max_pages:
            total_pages = min(total_pages, max_pages)
            print(f"Giới hạn cào {max_pages} trang")
        
        page_count = 0
        
        while page_count < total_pages:
            page_count += 1
            current_page, _ = get_pagination_info(driver)
            
            print(f"Đang cào trang {current_page}...")
            
            # Lấy dữ liệu trang hiện tại
            page_data = get_page_data(driver)
            all_books.extend(page_data)
            
            print(f"Đã cào {len(page_data)} sách từ trang {current_page}")
            
            # Nếu chưa đến trang cuối thì click next
            if page_count < total_pages:
                if not safe_click_next_page(driver):
                    print("Không thể chuyển sang trang tiếp theo hoặc bị redirect")
                    break
                    
                # Kiểm tra lại pagination sau khi chuyển trang
                time.sleep(2)
                new_current, _ = get_pagination_info(driver)
                if new_current <= current_page:
                    print("Phát hiện không chuyển trang được, dừng lại")
                    break
        
        print(f"\nTổng cộng đã cào {len(all_books)} sách từ {page_count} trang")
        
    finally:
        driver.quit()
    
    return pd.DataFrame(all_books)

def update_csv(new_data: pd.DataFrame):
    if new_data.empty:
        print("Không có dữ liệu mới để cập nhật")
        return
    
    if not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0:
        combined = new_data
        print("Tạo file CSV mới")
    else:
        try:
            old_data = pd.read_csv(CSV_FILE)
            print(f"Dữ liệu cũ: {len(old_data)} sách")
            combined = pd.concat([old_data, new_data]).drop_duplicates(subset=["title", "url"])
            print(f"Sau khi loại bỏ trùng lặp: {len(combined)} sách")
        except pd.errors.EmptyDataError:
            combined = new_data
            print("File CSV cũ trống, tạo mới")
    
    combined.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')
    print(f"Đã lưu {len(combined)} sách vào {CSV_FILE}")

# cào dữ liệu
if __name__ == "__main__":
    url = "https://ebookvie.com/ebook-hot/"
    
    print("Bắt đầu cào dữ liệu với Selenium...")
    print("Lưu ý: Cần cài đặt ChromeDriver và selenium")
    print("pip install selenium")
    
    # Cào dữ liệu
    all_books_data = scrape_all_pages_selenium(
        url=url,
        # max_pages=None 
    )
    
    # Cập nhật CSV
    update_csv(all_books_data)
    
    # Thống kê
    if os.path.exists(CSV_FILE):
        final_data = pd.read_csv(CSV_FILE)
        print(f"\nThống kê cuối cùng:")
        print(f"- Tổng số sách: {len(final_data)}")
        if 'genre' in final_data.columns:
            print(f"- Các thể loại: {final_data['genre'].nunique()} loại")