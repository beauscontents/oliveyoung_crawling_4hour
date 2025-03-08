import os
import time
import shutil
import logging
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.dates as mdates
from datetime import datetime
from zoneinfo import ZoneInfo  # 서울 시간대 사용을 위한 모듈 추가
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
    "driver_path": "/home/ubuntu/Downloads/chromedriver",  # 이미 올바른 경로
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

# ✅ 한글 폰트 설정 (한글 깨짐 문제 해결)
font_path = CONFIG["font_path"]
if os.path.exists(font_path):
    fm.fontManager.addfont(font_path)
    plt.rcParams["font.family"] = "Nanum Gothic"  # 폰트의 실제 이름으로 설정
    plt.rcParams['axes.unicode_minus'] = False   # 음수 기호 깨짐 방지
else:
    print("지정한 폰트 파일이 존재하지 않습니다.")

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

# === ✅ 이메일 전송 함수 ===
def send_email_with_attachments(subject, body, to_emails, attachments):
    sender_email = CONFIG["email"]["sender"]
    sender_password = CONFIG["email"]["password"]
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
            logging.warning(f"첨부 파일 {file_path}이(가) 존재하지 않습니다.")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        print("이메일 전송 성공!")
        logging.info("이메일 전송 성공!")
    except Exception as e:
        print(f"이메일 전송 실패: {e}")
        logging.error(f"이메일 전송 실패: {e}")

# === ✅ 데이터 저장 ===
def save_to_csv(category_name: str, data: List[Dict]) -> str:
    file_path = f"{CONFIG['csv_dir']}/{category_name}_rankings.csv"
    df_new = pd.DataFrame(data)
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

# === ✅ 트렌드 그래프 생성 ===
def plot_rank_trend(category_name: str) -> Optional[str]:
    file_path = f"{CONFIG['csv_dir']}/{category_name}_rankings.csv"
    if not os.path.exists(file_path):
        print(f"⚠️ {file_path} 파일 없음. 그래프 생성 건너뜀.")
        logging.warning(f"{file_path} 파일 없음. 그래프 생성 건너뜀.")
        return None

    df = pd.read_csv(file_path)
    # 날짜 형식을 정확히 인식하도록 format 수정
    df['날짜'] = pd.to_datetime(df['날짜'], format='%Y-%m-%d %p %I:%M', errors='coerce')
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
    logging.info(f"📊 그래프 저장 완료: {graph_path}")
    return graph_path

# === ✅ 카테고리별 크롤링 함수 ===
def crawl_category(driver, category_name, xpath):
    try:
        driver.get(CONFIG["base_url"])
        time.sleep(2)  # 페이지 로드 대기
        category_button = driver.find_element(By.XPATH, xpath)
        category_button.click()
        time.sleep(2)  # 카테고리 로드 대기

        soup = BeautifulSoup(driver.page_source, "html.parser")
        items = soup.select(".prd_info")  # 실제 Olive Young 상품 리스트 셀렉터로 수정 필요
        data = []
        for rank, item in enumerate(items[:10], 1):  # 상위 10개만 가져오기
            brand = item.select_one(".tx_brand").text.strip() if item.select_one(".tx_brand") else "N/A"
            name = item.select_one(".prd_name").text.strip() if item.select_one(".prd_name") else "N/A"
            # 서울 시간대로 시간 정보를 설정하여 CSV에 추가
            data.append({
                "날짜": datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %p %I:%M"),
                "순위": str(rank),
                "브랜드": brand,
                "상품명": name
            })
        print(f"✅ {category_name} 크롤링 완료: {len(data)}개 항목")
        logging.info(f"{category_name} 크롤링 완료: {len(data)}개 항목")
        return data
    except Exception as e:
        print(f"{category_name} 크롤링 실패: {e}")
        logging.error(f"{category_name} 크롤링 실패: {e}")
        return []

# === ✅ 자동 크롤링 및 데이터 저장 ===
def run_crawling():
    print("🔄 자동 크롤링 실행 중...")
    logging.info("자동 크롤링 실행 시작")
    try:
        options = Options()
        options.add_argument("--headless")  # 백그라운드 실행
        options.add_argument("--no-sandbox")  # 리눅스 환경에서 필요
        options.add_argument("--disable-dev-shm-usage")  # 리눅스 메모리 문제 방지
        driver = webdriver.Chrome(service=Service(CONFIG["driver_path"]), options=options)
    except WebDriverException as e:
        print(f"WebDriver 초기화 실패: {e}")
        logging.error(f"WebDriver 초기화 실패: {e}")
        return

    csv_files = []
    try:
        for category, xpath in CONFIG["categories"].items():
            new_data = crawl_category(driver, category, xpath)
            if new_data:  # 데이터가 있을 경우에만 저장
                csv_path = save_to_csv(category, new_data)
                csv_files.append(csv_path)
    except Exception as e:
        print(f"크롤링 중 오류: {e}")
        logging.error(f"크롤링 중 오류: {e}")
    finally:
        driver.quit()

    try:
        graph_files = [plot_rank_trend(cat) for cat in CONFIG["categories"] if os.path.exists(f"{CONFIG['csv_dir']}/{cat}_rankings.csv")]
        attachments = csv_files + [g for g in graph_files if g]
        if attachments:
            print("📂 이메일에 첨부할 파일:", attachments)
            send_email_with_attachments("올리브영 트렌드 분석", "최신 순위 변화 데이터입니다.", CONFIG["email"]["recipients"], attachments)
        else:
            print("⚠️ 첨부할 파일이 없습니다.")
            logging.warning("첨부할 파일이 없습니다.")
    except Exception as e:
        print(f"그래프 생성 또는 이메일 전송 중 오류: {e}")
        logging.error(f"그래프 생성 또는 이메일 전송 중 오류: {e}")

    print("✅ 자동 크롤링 완료!")
    logging.info("자동 크롤링 완료")

# === ✅ 실행 ===
if __name__ == "__main__":
    setup_logging()
    run_crawling()
