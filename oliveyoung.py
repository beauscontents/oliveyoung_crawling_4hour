import os
import time
import shutil
import logging
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.dates as mdates
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
    },
    "font_path": "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
}

# ✅ 한글 폰트 설정
font_path = CONFIG["font_path"]
if os.path.exists(font_path):
    font_prop = fm.FontProperties(fname=font_path)
    plt.rcParams["font.family"] = font_prop.get_name()

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

# === ✅ 트렌드 그래프 생성 ===
def plot_rank_trend(category_name: str) -> Optional[str]:
    file_name = f"{category_name}_rankings.csv"
    if not os.path.exists(file_name):
        print(f"⚠️ {file_name} 파일 없음. 그래프 생성 건너뜀.")
        logging.warning(f"⚠️ {file_name} 파일 없음. 그래프 생성 건너뜀.")
        return None

    df = pd.read_csv(file_name)
    df['날짜'] = pd.to_datetime(df['날짜'])
    df['순위'] = pd.to_numeric(df['순위'], errors='coerce')
    df = df.dropna(subset=['순위'])

    plt.figure(figsize=(12, 6))
    for product in df['상품명'].unique():
        product_data = df[df['상품명'] == product]
        plt.plot(product_data['날짜'], product_data['순위'], marker='o', label=product)

    plt.gca().invert_yaxis()
    plt.title(f"{category_name} 순위 변화")

    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    plt.xticks(rotation=45, ha='right')

    plt.xlabel("날짜 및 시간")
    plt.ylabel("순위")
    plt.legend(loc="upper left", bbox_to_anchor=(1.05, 1), fontsize=7)

    plt.tight_layout()
    graph_path = f"{category_name}_rank_trend.png"
    plt.savefig(graph_path, bbox_inches="tight")
    print(f"📊 그래프 저장 완료: {graph_path}")
    logging.info(f"📊 그래프 저장 완료: {graph_path}")
    return graph_path

# === ✅ Email Sender (CSV + 그래프 첨부) ===
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

# === ✅ Main Execution (CSV + 그래프 첨부) ===
def main():
    setup_logging()
    email_sender = EmailSender()

    csv_files = [f"{cat}_rankings.csv" for cat in CONFIG["categories"] if os.path.exists(f"{cat}_rankings.csv")]
    graph_files = [plot_rank_trend(cat) for cat in CONFIG["categories"] if os.path.exists(f"{cat}_rankings.csv")]

    # None 값 제거 (존재하는 파일만 첨부)
    attachments = [f for f in csv_files + graph_files if f is not None]

    if attachments:
        print("📂 이메일에 첨부할 파일:", attachments)
        email_sender.send_email(
            subject="올리브영 트렌드 분석",
            body="최신 순위 변화 데이터입니다.",
            attachments=attachments
        )
    else:
        print("⚠️ 첨부할 파일이 없습니다.")
        logging.warning("⚠️ 첨부할 파일이 없습니다.")

    print("✅ 프로그램 종료!")
    logging.info("✅ 프로그램 종료!")

if __name__ == "__main__":
    main()
