import os
import time
import shutil
import logging
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup
import smtplib
from email.message import EmailMessage
from pathlib import Path

# === ✅ Configuration Setup ===
CONFIG = {
    "log_dir": "logs",
    "backup_dir": "csv_backups",
    "driver_path": "/home/ubuntu/oliveyoung_crawling_4hour/chromedriver-linux64/chromedriver",
    "base_url": "https://www.oliveyoung.co.kr/store/main/getBestList.do",
    "categories": {
        "스킨케어": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[2]/button',
        "마스크팩": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[3]/button',
        "클렌징": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[4]/button',
        "선케어": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[5]/button',
        "메이크업": '/html/body/div[3]/div[8]/div[2]/div[1]/ul/li[6]/button'
    },
    "email": {
        "sender": "beauscontents@gmail.com",
        "password": "obktouclpxkxvltc",
        "recipients": ["beauscontents@gmail.com"]
    }
}

# === ✅ Logging + 터미널 출력 설정 ===
def setup_logging():
    Path(CONFIG["log_dir"]).mkdir(exist_ok=True)
    log_filename = f"{CONFIG['log_dir']}/{datetime.now().strftime('%Y-%m-%d')}_oliveyoung.log"
    logging.basicConfig(
        filename=log_filename,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    print("📌 프로그램 시작!")
    os.environ["SELENIUM_MANAGER_DISABLE"] = "1"

# === ✅ Web Crawler ===
class OliveYoungCrawler:
    def __init__(self):
        self.options = Options()
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--headless')
        self.service = Service(CONFIG["driver_path"])

    def crawl_category(self, category_name: str) -> Optional[List[Dict]]:
        print(f"🔍 {category_name} 크롤링 시작...")
        logging.info(f"🔍 {category_name} 크롤링 시작...")

        driver = None
        try:
            driver = webdriver.Chrome(service=self.service, options=self.options)
            driver.get(CONFIG["base_url"])
            time.sleep(3)

            xpath = CONFIG["categories"].get(category_name)
            if xpath:
                button = driver.find_element(By.XPATH, xpath)
                driver.execute_script("arguments[0].click();", button)
                time.sleep(3)

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            product_list = soup.select('ul.cate_prd_list > li')[:10]
            
            if not product_list:
                print(f"⚠️ {category_name}에 대한 상품이 없습니다.")
                logging.warning(f"⚠️ {category_name}에 대한 상품이 없습니다.")
                return None

            current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            rankings = [
                {
                    '날짜': current_time,
                    '순위': item.select_one('.thumb_flag.best').text.strip() if item.select_one('.thumb_flag.best') else 'N/A',
                    '브랜드': item.select_one('.tx_brand').text.strip() if item.select_one('.tx_brand') else 'N/A',
                    '상품명': item.select_one('.tx_name').text.strip() if item.select_one('.tx_name') else 'N/A'
                }
                for item in product_list
            ]
            
            print(f"✅ {category_name} 크롤링 완료!")
            logging.info(f"✅ {category_name} 크롤링 완료!")
            return rankings

        except WebDriverException as e:
            print(f"❌ {category_name} WebDriver 오류: {e}")
            logging.error(f"❌ {category_name} WebDriver 오류: {e}")
            return None
        except Exception as e:
            print(f"❌ {category_name} 크롤링 중 오류 발생: {e}")
            logging.error(f"❌ {category_name} 크롤링 중 오류 발생: {e}")
            return None
        finally:
            if driver:
                driver.quit()

# === ✅ Email Sender (터미널 출력 포함) ===
class EmailSender:
    @staticmethod
    def send_email(subject: str, body: str, attachments: List[str]):
        print("📧 이메일 전송 시작...")
        logging.info("📧 이메일 전송 시작...")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = CONFIG["email"]["sender"]
        msg["To"] = ", ".join(CONFIG["email"]["recipients"])
        msg.set_content(body)

        for file_path in attachments:
            path = Path(file_path)
            if path.exists():
                with path.open("rb") as f:
                    msg.add_attachment(
                        f.read(),
                        maintype="application",
                        subtype="octet-stream",
                        filename=path.name
                    )
                print(f"📎 첨부 파일 추가: {file_path}")
                logging.info(f"📎 첨부 파일 추가: {file_path}")

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(CONFIG["email"]["sender"], CONFIG["email"]["password"])
                smtp.send_message(msg)
            print("✅ 이메일 전송 성공!")
            logging.info("✅ 이메일 전송 성공!")
        except Exception as e:
            print(f"❌ 이메일 전송 실패: {e}")
            logging.error(f"❌ 이메일 전송 실패: {e}")

# === ✅ Main Execution (터미널 출력) ===
def main():
    setup_logging()
    crawler = OliveYoungCrawler()
    email_sender = EmailSender()

    results = {
        category: crawler.crawl_category(category)
        for category in CONFIG["categories"].keys()
    }
    
    filtered_results = {k: v for k, v in results.items() if v}
    if filtered_results:
        csv_files = [f"{cat}_rankings.csv" for cat in filtered_results if Path(f"{cat}_rankings.csv").exists()]
        print("📂 크롤링된 CSV 파일 목록:", csv_files)
        email_sender.send_email(
            subject="올리브영 트렌드 분석",
            body="최신 순위 변화 데이터입니다.",
            attachments=csv_files
        )

    print("✅ 프로그램 종료!")
    logging.info("✅ 프로그램 종료!")

if __name__ == "__main__":
    main()
