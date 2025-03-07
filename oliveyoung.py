import os
import time
import shutil
import logging
import schedule
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.dates as mdates
from datetime import datetime
from typing import Dict, List, Optional
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
    "csv_dir": "csv_files",
    "graph_dir": "graphs",
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

# ✅ 폴더 자동 생성
Path(CONFIG["log_dir"]).mkdir(exist_ok=True)
Path(CONFIG["csv_dir"]).mkdir(exist_ok=True)
Path(CONFIG["graph_dir"]).mkdir(exist_ok=True)

# ✅ 한글 폰트 설정
font_path = CONFIG["font_path"]
if os.path.exists(font_path):
    font_prop = fm.FontProperties(fname=font_path)
    plt.rcParams["font.family"] = font_prop.get_name()

# === ✅ Logging 설정 ===
def setup_logging():
    log_filename = f"{CONFIG['log_dir']}/{datetime.now().strftime('%Y-%m-%d')}_oliveyoung.log"
    logging.basicConfig(
        filename=log_filename,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    print("📌 프로그램 시작!")
    os.environ["SELENIUM_MANAGER_DISABLE"] = "1"

# === ✅ 이메일 전송 함수 (send_email_with_attachments) 구현 ===
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
        else:
            print(f"첨부 파일 {file_path}이(가) 존재하지 않습니다.")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        print("이메일 전송 성공!")
    except Exception as e:
        print("이메일 전송 실패:", e)

# === ✅ 데이터 저장 (Recursive 구조) ===
def save_to_csv(category_name: str, data: List[Dict]) -> str:
    file_path = f"{CONFIG['csv_dir']}/{category_name}_rankings.csv"
    
    df_new = pd.DataFrame(data)
    
    # ✅ 기존 데이터와 병합 (중복 제거)
    if os.path.exists(file_path):
        df_existing = pd.read_csv(file_path)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        df_combined.drop_duplicates(subset=["날짜", "상품명"], keep="last", inplace=True)
    else:
        df_combined = df_new

    df_combined.to_csv(file_path, index=False, encoding="utf-8-sig")
    print(f"📂 CSV 저장 완료: {file_path}")
    logging.info(f"📂 CSV 저장 완료: {file_path}")
    return file_path

# === ✅ 트렌드 그래프 생성 (Recursive 반영) ===
def plot_rank_trend(category_name: str) -> Optional[str]:
    file_path = f"{CONFIG['csv_dir']}/{category_name}_rankings.csv"
    if not os.path.exists(file_path):
        print(f"⚠️ {file_path} 파일 없음. 그래프 생성 건너뜀.")
        return None

    df = pd.read_csv(file_path)

    df['날짜'] = pd.to_datetime(df['날짜'], format='mixed', errors='coerce')
    df = df.dropna(subset=['날짜'])
    df['순위'] = pd.to_numeric(df['순위'], errors='coerce')
    df = df.dropna(subset=['순위'])

    plt.figure(figsize=(12, 6))
    for product in df['상품명'].unique():
        product_data = df[df['상품명'] == product]
        plt.plot(product_data['날짜'], product_data['순위'], marker='o', label=product)

    plt.gca().invert_yaxis()
    plt.title(f"{category_name} 순위 변화")

    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %p %I:%M'))
    plt.xticks(rotation=45, ha='right')

    plt.xlabel("날짜 및 시간")
    plt.ylabel("순위")
    plt.legend(loc="upper left", bbox_to_anchor=(1.05, 1), fontsize=7)

    plt.tight_layout()
    graph_path = f"{CONFIG['graph_dir']}/{category_name}_rank_trend.png"
    plt.savefig(graph_path, bbox_inches="tight")
    print(f"📊 그래프 저장 완료: {graph_path}")
    return graph_path

# === ✅ 자동 크롤링 및 데이터 저장 ===
def run_crawling():
    print("🔄 자동 크롤링 실행 중...")

    # 현재 시간 저장 (오전/오후 표시)
    current_time = datetime.now().strftime("%Y-%m-%d %p %I:%M")

    csv_files = []
    for category in CONFIG["categories"]:
        new_data = [
            {
                "날짜": current_time,
                "순위": "1",  # ✅ 더미 데이터 (실제 크롤링 데이터 삽입 필요)
                "브랜드": "Sample Brand",
                "상품명": "Sample Product"
            }
        ]
        csv_path = save_to_csv(category, new_data)
        csv_files.append(csv_path)

    # 그래프 생성
    graph_files = [plot_rank_trend(cat) for cat in CONFIG["categories"] if os.path.exists(f"{CONFIG['csv_dir']}/{cat}_rankings.csv")]

    # ✅ 이메일 전송 (CSV + 그래프 첨부)
    attachments = csv_files + [g for g in graph_files if g]
    if attachments:
        print("📂 이메일에 첨부할 파일:", attachments)
        send_email_with_attachments("올리브영 트렌드 분석", "최신 순위 변화 데이터입니다.", CONFIG["email"]["recipients"], attachments)
    else:
        print("⚠️ 첨부할 파일이 없습니다.")

    print("✅ 자동 크롤링 완료!")

# === ✅ 스케줄링 (4시간마다 실행) ===
#schedule.every().day.at("09:00").do(run_crawling)
#schedule.every().day.at("13:00").do(run_crawling)
#schedule.every().day.at("17:00").do(run_crawling)
#schedule.every().day.at("21:00").do(run_crawling)
#schedule.every().day.at("01:00").do(run_crawling)
#schedule.every().day.at("05:00").do(run_crawling)

# === ✅ 실행 루프 ===
if __name__ == "__main__":
    setup_logging()
    while True:
        #schedule.run_pending()
        #time.sleep(10)  # 1분마다 스케줄 확인
