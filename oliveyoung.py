import os
import time
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import smtplib
from email.message import EmailMessage

# Selenium Manager 비활성화 (명시적 드라이버 사용)
os.environ["SELENIUM_MANAGER_DISABLE"] = "1"

# 한글 폰트 설정 (NanumGothic 설치 필요: sudo apt install fonts-nanum)
plt.rc('font', family='NanumGothic')

# === 크롤링 및 CSV 저장 코드 ===
def crawl_oliveyoung_ranking(category_name, category_id=""):
    base_url = "https://www.oliveyoung.co.kr/store/main/getBestList.do"
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--headless")

    # 명시적 드라이버 경로 지정
    driver_path = "/home/ubuntu/oliveyoung_crawling_4hour/chromedriver-linux64/chromedriver"
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get(base_url)
        time.sleep(3)

        if category_id:
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

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        driver.quit()

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
        plt.gca().invert_yaxis()
        plt.title(f'{category_name} 순위 변화')
        plt.xlabel('날짜')
        plt.ylabel('순위')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        plt.show()
    except FileNotFoundError:
        print(f"⚠️ {file_name} 파일이 없습니다. 먼저 데이터를 수집하세요.")

# === 이메일 전송 함수 ===
def send_email_with_attachments(subject, body, to_emails, attachments):
    # 발신자 정보 (예시: Gmail)
    sender_email = "beauscontents@gmail.com"
    sender_password = "obktouclpxkxvltc"  # 앱 비밀번호 사용
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = ", ".join(to_emails)
    msg.set_content(body)
    for file_path in attachments:
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                file_data = f.read()
            msg.add_attachment(file_data, maintype="application", subtype="octet-stream", filename=os.path.basename(file_path))
        else:
            print(f"첨부 파일 {file_path}이(가) 존재하지 않습니다.")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        print("이메일 전송 성공!")
    except Exception as e:
        print("이메일 전송 실패:", e)

# === 메인 실행 부분 ===
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
    # 선택적으로 그래프도 출력 (필요시)
    # plot_rank_trend("스킨케어")

    # 이메일 전송: 모든 CSV 파일을 첨부
    attachments = [
        os.path.join(os.getcwd(), "전체_rankings.csv"),
        os.path.join(os.getcwd(), "스킨케어_rankings.csv"),
        os.path.join(os.getcwd(), "마스크팩_rankings.csv"),
        os.path.join(os.getcwd(), "클렌징_rankings.csv"),
        os.path.join(os.getcwd(), "선케어_rankings.csv"),
        os.path.join(os.getcwd(), "메이크업_rankings.csv")
    ]
    subject = "4시간마다 전송되는 올리브영 크롤링 데이터"
    body = "첨부된 CSV 파일은 최신 올리브영 상품 순위 데이터입니다."
    recipients = ["ceo@beaus.co.kr"]  # 수신자 이메일 목록

    send_email_with_attachments(subject, body, recipients, attachments)
