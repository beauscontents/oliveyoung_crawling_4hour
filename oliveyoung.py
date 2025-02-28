import os
import time
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# 크롤링 함수
def crawl_oliveyoung_ranking(category_name, category_id=""):
    base_url = "https://www.oliveyoung.co.kr/store/main/getBestList.do"

    # Chrome 옵션 설정 (AWS 우분투 서버 환경 대응)
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--headless")  # 창 없이 실행

    # ChromeDriver 자동 설치 및 실행
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        if category_id == "":
            url = base_url
        else:
            url = base_url
            driver.get(url)
            time.sleep(3)

            # 카테고리 버튼 클릭 (XPath 매핑)
            category_xpath = {
                "스킨케어": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[2]/button',
                "마스크팩": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[3]/button',
                "클렌징": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[4]/button',
                "선케어": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[5]/button',
                "메이크업": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[6]/button'
            }

            if category_name in category_xpath:
                try:
                    button = driver.find_element(By.XPATH, category_xpath[category_name])
                    driver.execute_script("arguments[0].click();", button)
                    time.sleep(3)
                except Exception as e:
                    print(f"❌ {category_name} 버튼 클릭 실패: {e}")
                    driver.quit()
                    return None
            else:
                print(f"❌ {category_name}의 XPath가 존재하지 않습니다.")
                driver.quit()
                return None

        # HTML 파싱
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        driver.quit()

        # 제품 정보 추출
        product_list = soup.select('ul.cate_prd_list > li')[:10]
        if not product_list:
            print(f"⚠️ {category_name}에 대한 상품이 없습니다.")
            return None

        rankings = []
        current_date = datetime.now().strftime('%Y-%m-%d')

        for item in product_list:
            rank = item.select_one('.thumb_flag.best').text.strip() if item.select_one('.thumb_flag.best') else 'N/A'
            brand = item.select_one('.tx_brand').text.strip() if item.select_one('.tx_brand') else 'N/A'
            name = item.select_one('.tx_name').text.strip() if item.select_one('.tx_name') else 'N/A'
            orig_price = item.select_one('.tx_org .tx_num').text.strip() if item.select_one('.tx_org .tx_num') else 'N/A'
            sale_price = item.select_one('.tx_cur .tx_num').text.strip() if item.select_one('.tx_cur .tx_num') else 'N/A'
            
            # 할인율 계산
            discount_rate = 'N/A'
            if orig_price != 'N/A' and sale_price != 'N/A':
                try:
                    orig_price_num = float(orig_price.replace(',', ''))
                    sale_price_num = float(sale_price.replace(',', ''))
                    if orig_price_num > 0:
                        discount_rate = f"{int(round(((orig_price_num - sale_price_num) / orig_price_num) * 100))}%"
                except ValueError:
                    discount_rate = 'N/A'

            rankings.append({
                '날짜': current_date,
                '순위': rank,
                '브랜드': brand,
                '상품명': name,
                '원래 가격': orig_price,
                '할인 가격': sale_price,
                '할인율': discount_rate
            })
        
        return rankings

    except Exception as e:
        print(f"❌ {category_name} 크롤링 중 오류 발생: {e}")
        driver.quit()
        return None

# CSV 저장 함수
def save_to_csv(data_dict):
    for category_name, data in data_dict.items():
        df = pd.DataFrame(data)
        file_name = f'{category_name}_rankings.csv'

        try:
            existing_df = pd.read_csv(file_name)
            df = pd.concat([existing_df, df]).drop_duplicates(subset=['날짜', '상품명'], keep='last')
        except FileNotFoundError:
            pass

        df.to_csv(file_name, index=False)
        print(f"✅ {category_name} 데이터를 {file_name}에 저장 완료!")

# 순위 변화 그래프
def plot_rank_trend(category_name):
    file_name = f'{category_name}_rankings.csv'
    
    try:
        df = pd.read_csv(file_name)
        df['순위'] = pd.to_numeric(df['순위'], errors='coerce')
        df = df.dropna(subset=['순위'])

        plt.figure(figsize=(12, 6))
        for product in df['상품명'].unique():
            product_data = df[df['상품명'] == product]
            plt.plot(product_data['날짜'], product_data['순위'], marker='o', label=product)

        plt.gca().invert_yaxis()  # 순위 낮을수록 좋은 구조 반영
        plt.title(f'{category_name} 순위 변화')
        plt.xlabel('날짜')
        plt.ylabel('순위')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        plt.show()

    except FileNotFoundError:
        print(f"⚠️ {file_name} 파일이 없습니다. 먼저 데이터를 수집하세요.")

# 실행 부분
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
        print(f"🔍 {category_name} 크롤링 시작...")
        result = crawl_oliveyoung_ranking(category_name, category_id)
        if result:
            results[category_name] = result

    if results:
        save_to_csv(results)

    plot_rank_trend("스킨케어")  # 특정 카테고리 그래프 표시
