import os
import time
import shutil
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.dates as mdates
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import smtplib
from email.message import EmailMessage

# Selenium Manager 비활성화
os.environ["SELENIUM_MANAGER_DISABLE"] = "1"

# ✅ 한글 폰트 설정
font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"  # Ubuntu 기준
font_prop = fm.FontProperties(fname=font_path)
plt.rcParams["font.family"] = font_prop.get_name()
print(f"✅ 한글 폰트 설정 완료: {font_prop.get_name()}")

# === 크롤링 코드 ===
def crawl_oliveyoung_ranking(category_name, category_id=""):
    base_url = "https://www.oliveyoung.co.kr/store/main/getBestList.do"
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--headless")

    driver_path = "/home/ubuntu/oliveyoung_crawling_4hour/chromedriver-linux64/chromedriver"
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get(base_url)
        time.sleep(3)

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

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        driver.quit()

        product_list = soup.select('ul.cate_prd_list > li')[:10]
        if not product_list:
            print(f"⚠️ {category_name}에 대한 상품이 없습니다.")
            return None

        rankings = []
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M')  # ✅ 날짜 + 시간 저장
        for item in product_list:
            rank = item.select_one('.thumb_flag.best').text.strip() if item.select_one('.thumb_flag.best') else 'N/A'
            brand = item.select_one('.tx_brand').text.strip() if item.select_one('.tx_brand') else 'N/A'
            name = item.select_one('.tx_name').text.strip() if item.select_one('.tx_name') else 'N/A'
            rankings.append({'날짜': current_time, '순위': rank, '브랜드': brand, '상품명': name})
        return rankings

    except Exception as e:
        print(f"❌ {category_name} 크롤링 중 오류 발생: {e}")
        driver.quit()
        return None

# === CSV 저장 및 백업 ===
def save_to_csv(data_dict):
    backup_folder = "csv_backups"
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    for category_name, data in data_dict.items():
        file_name = f'{category_name}_rankings.csv'
        backup_file = os.path.join(backup_folder, f"{category_name}_rankings_{datetime.now().strftime('%Y%m%d%H%M')}.csv")
        df_new = pd.DataFrame(data)

        try:
            df_existing = pd.read_csv(file_name)
            shutil.copy(file_name, backup_file)
        except FileNotFoundError:
            df_new.to_csv(file_name, index=False, encoding='utf-8-sig')
            continue

        df_existing['날짜'] = pd.to_datetime(df_existing['날짜'])
        df_new['날짜'] = pd.to_datetime(df_new['날짜'])

        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        df_combined = df_combined.drop_duplicates(subset=['날짜', '상품명'], keep='last')
        df_combined.to_csv(file_name, index=False, encoding='utf-8-sig')

# === 트렌드 그래프 ===
def plot_rank_trend(category_name):
    file_name = f'{category_name}_rankings.csv'
    try:
        df = pd.read_csv(file_name)
        df['날짜'] = pd.to_datetime(df['날짜'])
        df['순위'] = pd.to_numeric(df['순위'], errors='coerce')
        df = df.dropna(subset=['순위'])

        plt.figure(figsize=(12, 6))
        for product in df['상품명'].unique():
            product_data = df[df['상품명'] == product]
            plt.plot(product_data['날짜'], product_data['순위'], marker='o', label=product)

        plt.gca().invert_yaxis()
        plt.title(f'{category_name} 순위 변화')

        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.xticks(rotation=45, ha='right')

        plt.xlabel('날짜 및 시간')
        plt.ylabel('순위')
        plt.legend(loc='upper left', bbox_to_anchor=(1.05, 1), fontsize=7)

        plt.tight_layout()
        graph_path = f"{category_name}_rank_trend.png"
        plt.savefig(graph_path, bbox_inches='tight')
        return graph_path

    except FileNotFoundError:
        return None

# === 이메일 전송 (CSV + 그래프 포함) ===
def send_email_with_attachments(subject, body, to_emails, attachments):
    sender_email = "beauscontents@gmail.com"
    sender_password = "obktouclpxkxvltc"
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

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender_email, sender_password)
        smtp.send_message(msg)

# === 메인 실행 (모든 카테고리 처리) ===
if __name__ == "__main__":
    categories = {"스킨케어": "", "마스크팩": "", "클렌징": "", "선케어": "", "메이크업": ""}
    results = {name: crawl_oliveyoung_ranking(name) for name in categories if crawl_oliveyoung_ranking(name)}

    if results:
        save_to_csv(results)
        attachments = [plot_rank_trend(cat) for cat in categories if os.path.exists(f"{cat}_rankings.csv")]
        send_email_with_attachments("올리브영 트렌드 분석", "최신 순위 변화 데이터입니다.", ["beauscontents@gmail.com"], attachments)
