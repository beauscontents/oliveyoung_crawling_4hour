from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import matplotlib.pyplot as plt

# 크롤링 함수
def crawl_oliveyoung_ranking(category_name, category_id=""):
    base_url = "https://www.oliveyoung.co.kr/store/main/getBestList.do"
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)

    if category_id == "":
        url = base_url
        driver.get(url)
        time.sleep(3)
    else:
        driver.get(base_url)
        time.sleep(3)
        category_xpath = {
            "스킨케어": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[2]/button',
            "마스크팩": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[3]/button',
            "클렌징": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[4]/button',
            "선케어": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[5]/button',
            "메이크업": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[6]/button'
        }
        try:
            button = driver.find_element(By.XPATH, category_xpath[category_name])
            driver.execute_script("arguments[0].click();", button)
            time.sleep(3)
        except Exception as e:
            print(f"Failed to click button for {category_name}: {e}")
            driver.quit()
            return None

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()

    product_list = soup.select('ul.cate_prd_list > li')[:10]
    if not product_list:
        print(f"No products found for {category_name}")
        return None

    rankings = []
    current_date = datetime.now().strftime('%Y-%m-%d')  # 현재 날짜 추가
    for item in product_list:
        rank = item.select_one('.thumb_flag.best').text.strip() if item.select_one('.thumb_flag.best') else 'N/A'
        brand = item.select_one('.tx_brand').text.strip() if item.select_one('.tx_brand') else 'N/A'
        name = item.select_one('.tx_name').text.strip() if item.select_one('.tx_name') else 'N/A'
        orig_price = item.select_one('.tx_org .tx_num').text.strip() if item.select_one('.tx_org .tx_num') else 'N/A'
        sale_price = item.select_one('.tx_cur .tx_num').text.strip() if item.select_one('.tx_cur .tx_num') else 'N/A'
        discount_rate = 'N/A'
        if orig_price != 'N/A' and sale_price != 'N/A':
            try:
                orig_price_num = float(orig_price.replace(',', ''))
                sale_price_num = float(sale_price.replace(',', ''))
                if orig_price_num > 0:
                    discount_rate = int(round(((orig_price_num - sale_price_num) / orig_price_num) * 100))
                    discount_rate = f"{discount_rate}%"
            except ValueError:
                discount_rate = 'N/A'

        rankings.append({
            '날짜': current_date,  # 날짜 열 추가
            '순위': rank,
            '브랜드': brand,
            '상품명': name,
            '원래 가격': orig_price,
            '할인 가격': sale_price,
            '할인율': discount_rate
        })
    
    return rankings

# CSV에 데이터 저장 (기존 데이터에 추가)
def save_to_csv(data_dict):
    for category_name, data in data_dict.items():
        df = pd.DataFrame(data)
        file_name = f'{category_name}_rankings.csv'
        # 기존 파일이 있으면 추가, 없으면 새로 생성
        try:
            existing_df = pd.read_csv(file_name)
            df = pd.concat([existing_df, df]).drop_duplicates(subset=['날짜', '상품명'], keep='last')
        except FileNotFoundError:
            pass
        df.to_csv(file_name, index=False)
        print(f"{category_name} 데이터를 {file_name}에 저장했습니다")

# 순위 변화 그래프 그리기
def plot_rank_trend(category_name):
    file_name = f'{category_name}_rankings.csv'
    try:
        df = pd.read_csv(file_name)
        # 순위를 숫자로 변환 (N/A는 제외)
        df['순위'] = pd.to_numeric(df['순위'], errors='coerce')
        df = df.dropna(subset=['순위'])  # 순위가 없는 행 제거

        plt.figure(figsize=(12, 6))
        for product in df['상품명'].unique():
            product_data = df[df['상품명'] == product]
            plt.plot(product_data['날짜'], product_data['순위'], marker='o', label=product)
        
        plt.gca().invert_yaxis()  # 순위는 낮을수록 좋으므로 Y축 반전
        plt.title(f'{category_name} 순위 변화')
        plt.xlabel('날짜')
        plt.ylabel('순위')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        plt.show()
    except FileNotFoundError:
        print(f"{file_name} 파일이 없습니다. 먼저 데이터를 수집해주세요.")

# 메인 실행
if __name__ == "__main__":
    categories = {
        "전체": "",
        "스킨케어": "10000010001",
        "마스크팩": "10000010009",
        "클렌징": "10000010010",
        "선케어": "10000010011",
        "메이크업": "10000010002"
    }

    results = {}
    for category_name, category_id in categories.items():
        print(f"Crawling {category_name}...")
        result = crawl_oliveyoung_ranking(category_name, category_id)
        if result:
            results[category_name] = result

    # CSV에 저장
    if results:
        save_to_csv(results)

    # 특정 카테고리 그래프 보기 (예: 스킨케어)
    plot_rank_trend("스킨케어")