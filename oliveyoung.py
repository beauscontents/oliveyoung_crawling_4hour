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
    plt.rcParams["font.family"] = "NanumGothic"  # 폰트의 실제 이름으로 설정
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
def plot_rank_trend(category_name: str) -> Optional[str]:
    """
    카테고리별 순위 변화 그래프를 생성합니다.
    최신 크롤링 데이터를 기준으로 상위 10위 상품의 순위 변화만 표시합니다.
    
    Args:
        category_name (str): 카테고리 이름
    
    Returns:
        Optional[str]: 생성된 그래프 파일 경로 또는 None
    """
    file_path = f"{CONFIG['csv_dir']}/{category_name}_rankings.csv"
    
    # 파일 존재 여부 확인
    if not os.path.exists(file_path):
        print(f"⚠️ {file_path} 파일 없음. 그래프 생성 건너뜀.")
        logging.warning(f"{file_path} 파일 없음. 그래프 생성 건너뜀.")
        return None

    try:
        # 데이터 로드 및 전처리
        df = pd.read_csv(file_path)
        
        # 날짜 형식 변환
        df['날짜'] = pd.to_datetime(df['날짜'], format='%Y-%m-%d %p %I:%M', errors='coerce')
        if df['날짜'].isna().all():
            print(f"⚠️ {category_name}: 유효한 날짜 데이터 없음. 그래프 생성 건너뜀.")
            logging.warning(f"{category_name}: 유효한 날짜 데이터 없음.")
            return None
        df = df.dropna(subset=['날짜'])

        # 순위 숫자 변환
        df['순위'] = pd.to_numeric(df['순위'], errors='coerce')
        df = df.dropna(subset=['순위'])

        if df.empty:
            print(f"⚠️ {category_name}: 유효한 순위 데이터 없음. 그래프 생성 건너뜀.")
            logging.warning(f"{category_name}: 유효한 순위 데이터 없음.")
            return None

        # 최신 크롤링 데이터 기준 상위 10위 상품 추출
        latest_date = df['날짜'].max()
        latest_data = df[df['날짜'] == latest_date]
        top_10_products = latest_data[latest_data['순위'] <= 10]['상품명'].unique()

        if len(top_10_products) == 0:
            print(f"⚠️ {category_name}: 최신 데이터에서 상위 10위 상품 없음. 그래프 생성 건너뜀.")
            logging.warning(f"{category_name}: 최신 데이터에서 상위 10위 상품 없음.")
            return None

        # 상위 10위 상품 데이터만 필터링 (과거 데이터 포함)
        df = df[df['상품명'].isin(top_10_products)]

        if df.empty:
            print(f"⚠️ {category_name}: 상위 10위 상품 관련 데이터 없음. 그래프 생성 건너뜀.")
            logging.warning(f"{category_name}: 상위 10위 상품 관련 데이터 없음.")
            return None

        # 그래프 생성
        plt.figure(figsize=(12, 6))
        for product in df['상품명'].unique():
            product_data = df[df['상품명'] == product].sort_values('날짜')
            
            # 데이터가 1개일 경우 (최신 데이터만 있는 경우)
            if len(product_data) == 1:
                plt.plot(product_data['날짜'], product_data['순위'], 'o', label=product)
                plt.text(product_data['날짜'].iloc[0], product_data['순위'].iloc[0], '신규', 
                        fontsize=8, ha='right')
                logging.info(f"{category_name}: 신규 상품 감지 - {product}")
            else:
                # 데이터가 여러 개일 경우 선으로 연결
                gaps = (product_data['날짜'].diff() > pd.Timedelta(hours=8)).cumsum()
                for gap in range(gaps.max() + 1):
                    subset = product_data[gaps == gap]
                    if len(subset) > 0:
                        linestyle = '-' if gap == 0 else '--'  # 누락된 구간은 점선으로 표시
                        plt.plot(subset['날짜'], subset['순위'], marker='o', linestyle=linestyle, 
                                label=product if gap == 0 else "")

        # 순위권 이탈 상품 확인 (최신 데이터 기준 상위 10위에 없는 경우는 제외)
        for product in df['상품명'].unique():
            product_data = df[df['상품명'] == product].sort_values('날짜')
            if product_data['날짜'].max() < latest_date:
                last_data = product_data.iloc[-1]
                plt.text(last_data['날짜'], last_data['순위'], '이탈', fontsize=8, ha='left')
                logging.info(f"{category_name}: 순위권 이탈 상품 감지 - {product}")

        # 그래프 설정
        plt.gca().invert_yaxis()
        plt.title(f"{category_name} 순위 변화 (최신 상위 10위 상품)")
        
        # x축 간격 동적 조정
        time_range = (df['날짜'].max() - df['날짜'].min()).total_seconds() / 3600  # 시간 차이 계산
        if time_range < 24:
            plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
        else:
            plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=1))
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.xticks(rotation=45, ha='right')
        plt.xlabel("날짜 및 시간")
        plt.ylabel("순위")
        plt.legend(loc="upper left", bbox_to_anchor=(1.05, 1), fontsize=7)
        plt.tight_layout()

        # 그래프 저장
        graph_path = f"{CONFIG['graph_dir']}/{category_name}_rank_trend.png"
        plt.savefig(graph_path, bbox_inches="tight")
        print(f"📊 그래프 저장 완료: {graph_path}")
        logging.info(f"📊 그래프 저장 완료: {graph_path}")
        return graph_path

    except Exception as e:
        print(f"⚠️ {category_name} 그래프 생성 실패: {e}")
        logging.error(f"{category_name} 그래프 생성 실패: {e}")
        return None
    finally:
        plt.close()  # 메모리 누수 방지

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
