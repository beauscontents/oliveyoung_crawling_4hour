import os
import time
import shutil
import logging
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

# === ✅ 로깅 설정 ===
log_filename = f"logs/{datetime.now().strftime('%Y-%m-%d')}_oliveyoung.log"
os.makedirs("logs", exist_ok=True)  # logs 폴더 없으면 생성
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.info("📌 프로그램 시작!")

# Selenium Manager 비활성화
os.environ["SELENIUM_MANAGER_DISABLE"] = "1"

# ✅ 한글 폰트 설정
font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"  # Ubuntu 기준
font_prop = fm.FontProperties(fname=font_path)
plt.rcParams["font.family"] = font_prop.get_name()
logging.info(f"✅ 한글 폰트 설정 완료: {font_prop.get_name()}")

# === 크롤링 코드 ===
def crawl_oliveyoung_ranking(category_name, category_id=""):
    logging.info(f"🔍 {category_name} 크롤링 시작...")
    
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
                logging.error(f"❌ {category_name} 버튼 클릭 실패: {e}")
                driver.quit()
                return None

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        driver.quit()

        product_list = soup.select('ul.cate_prd_list > li')[:10]
        if not product_list:
            logging.warning(f"⚠️ {category_name}에 대한 상품이 없습니다.")
            return None

        rankings = []
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
        for item in product_list:
            rank = item.select_one('.thumb_flag.best').text.strip() if item.select_one('.thumb_flag.best') else 'N/A'
            brand = item.select_one('.tx_brand').text.strip() if item.select_one('.tx_brand') else 'N/A'
            name = item.select_one('.tx_name').text.strip() if item.select_one('.tx_name') else 'N/A'
            rankings.append({'날짜': current_time, '순위': rank, '브랜드': brand, '상품명': name})

        logging.info(f"✅ {category_name} 크롤링 완료!")
        return rankings

    except Exception as e:
        logging.error(f"❌ {category_name} 크롤링 중 오류 발생: {e}")
        driver.quit()
        return None

# === CSV 저장 및 백업 ===
def save_to_csv(data_dict):
    logging.info("📂 CSV 저장 시작...")
    
    backup_folder = "csv_backups"
    os.makedirs(backup_folder, exist_ok=True)

    for category_name, data in data_dict.items():
        file_name = f'{category_name}_rankings.csv'
        backup_file = os.path.join(backup_folder, f"{category_name}_rankings_{datetime.now().strftime('%Y%m%d%H%M')}.csv")
        df_new = pd.DataFrame(data)

        try:
            df_existing = pd.read_csv(file_name)
            shutil.copy(file_name, backup_file)
            logging.info(f"🗂 기존 CSV 백업 완료: {backup_file}")
        except FileNotFoundError:
            logging.warning(f"⚠️ 기존 CSV 없음, 새로 생성: {file_name}")

        df_combined = pd.concat([df_existing, df_new], ignore_index=True) if 'df_existing' in locals() else df_new
        df_combined.to_csv(file_name, index=False, encoding='utf-8-sig')
        logging.info(f"✅ {category_name} 데이터 저장 완료!")

# === 이메일 전송 (CSV + 그래프 포함) ===
def send_email_with_attachments(subject, body, to_emails, attachments):
    logging.info("📧 이메일 전송 시작...")

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
            logging.info(f"📎 첨부 파일 추가: {file_path}")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        logging.info("✅ 이메일 전송 성공!")
    except Exception as e:
        logging.error(f"❌ 이메일 전송 실패: {e}")

# === 메인 실행 ===
if __name__ == "__main__":
    categories = {"스킨케어": "", "마스크팩": "", "클렌징": "", "선케어": "", "메이크업": ""}
    results = {name: crawl_oliveyoung_ranking(name) for name in categories if crawl_oliveyoung_ranking(name)}

    if results:
        save_to_csv(results)
        attachments = [f"{cat}_rankings.csv" for cat in categories if os.path.exists(f"{cat}_rankings.csv")]
        send_email_with_attachments("올리브영 트렌드 분석", "최신 순위 변화 데이터입니다.", ["beauscontents@gmail.com"], attachments)

    logging.info("✅ 프로그램 종료!")
