import os
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime
import xml.etree.ElementTree as ET

app = Flask(__name__)

# --- 환경 변수에서 API 키를 안전하게 가져옵니다 ---
KAKAO_API_KEY = os.getenv('KAKAO_API_KEY')
GO_DATA_API_KEY = os.getenv('GO_DATA_API_KEY')
KAKAO_JS_KEY_FOR_HTML = os.getenv('KAKAO_JS_KEY')

# --- 카카오 API: 키워드로 좌표 및 법정동 코드 검색 ---
def get_coords_from_address(address):
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": address}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 200 and response.json()['documents']:
            doc = response.json()['documents'][0]
            if doc.get('road_address_name'):
                address_detail_url = "https://dapi.kakao.com/v2/local/search/address.json"
                address_params = {"query": doc['road_address_name']}
                address_response = requests.get(address_detail_url, headers=headers, params=address_params, timeout=5)
                if address_response.status_code == 200 and address_response.json()['documents']:
                    address_doc = address_response.json()['documents'][0]
                    if address_doc.get('address') and address_doc['address'].get('b_code'):
                        return {"lat": float(doc['y']), "lng": float(doc['x']), "b_code": address_doc['address']['b_code']}
    except requests.exceptions.Timeout:
        print("[카카오 API 타임아웃]")
    except Exception as e:
        print(f"[카카오 API 오류] {e}")
    return None

# --- 국토교통부 API: 실거래가 정보 조회 ---
def get_real_estate_transactions(b_code, deal_ymd):
    url = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTradeDev"
    params = {
        "serviceKey": GO_DATA_API_KEY,
        "LAWD_CD": b_code[:5],
        "DEAL_YMD": deal_ymd,
        "numOfRows": "50"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            transactions = []
            for item in root.findall('.//item'):
                transactions.append({
                    "price": f"{item.find('거래금액').text.strip()}만원",
                    "apt_name": item.find('아파트').text.strip(),
                    "area": f"{float(item.find('전용면적').text.strip()):.2f}㎡",
                    "date": f"{item.find('년').text.strip()}년 {item.find('월').text.strip()}월 {item.find('일').text.strip()}일"
                })
            return transactions
    except requests.exceptions.Timeout:
        print(f"[실거래가 API 타임아웃] {deal_ymd}")
    except Exception as e:
        print(f"[실거래가 API 오류] {e}")
    return []

# --- Flask 라우트 설정 ---
@app.route('/')
def index():
    return render_template('index.html', KAKAO_JS_KEY=KAKAO_JS_KEY_FOR_HTML)

import traceback

ChatGPT의 말:
위 코드에서 전체적으로는 좋은 방향으로 수정하셨지만, 다음과 같은 구조적 오류 및 문법 오류가 포함되어 있어서 정상 작동하지 않습니다.
아래에 상세 수정 포인트와 함께 정상 작동하도록 수정한 버전을 제공합니다.

✅ 주요 수정 포인트 요약
문제	설명	해결 방법
❌ search() 함수에서 location_info 정의 전 return 발생	location_info가 정의되기 전에 return 하여 오류 발생	location_info 정의 후 로직 실행되도록 순서 조정
❌ search() 함수 내부에 return이 두 번 있음	try 블록 내 return이 여러 개여서 코드 도달 불가	하나의 return으로 정리
❌ except 블록이 함수 중간에 위치	try 블록 끝나기 전에 return됨	try ... except 블록을 전체로 감싸도록 조정
✅ 로그 출력 강화는 잘 적용됨	traceback으로 로그 확인 가능	유지 가능

✅ 수정된 최종 코드
python
복사
편집
@app.route('/search', methods=['POST'])
def search():
    try:
        address = request.form.get('address')
        if not address:
            return jsonify({"error": "주소가 입력되지 않았습니다."}), 400

        location_info = get_coords_from_address(address)
        if not location_info:
            return jsonify({"error": "유효하지 않은 주소이거나 변환에 실패했습니다."}), 404

        today = datetime.now()
        transactions = []

        for i in range(12):
            month_offset = today.month - i
            year_offset = today.year
            if month_offset <= 0:
                month_offset += 12
                year_offset -= 1
            deal_ymd = f"{year_offset}{month_offset:02d}"
            data = get_real_estate_transactions(location_info['b_code'], deal_ymd)
            if data:
                transactions.extend(data)

        unique_transactions = [dict(t) for t in {tuple(d.items()) for d in transactions}]

        return jsonify({
            "center": {"lat": location_info['lat'], "lng": location_info['lng']},
            "transactions": sorted(unique_transactions, key=lambda x: x['date'], reverse=True)
        })

    except Exception as e:
        print("[에러 발생] search() 함수 내부 예외")
        print(f"에러 내용: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "서버 오류: 처리 중 문제가 발생했습니다. 관리자에게 문의하세요."}), 500

# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
# ★★★★★ 진단용 테스트 페이지: 이 페이지로 접속해서 키를 테스트합니다 ★★★★★
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
@app.route('/test-key')
def test_key():
    test_url = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTradeDev"
    test_params = {
        "serviceKey": GO_DATA_API_KEY,
        "LAWD_CD": "11680", # 테스트용 지역 코드 (강남구)
        "DEAL_YMD": "202401", # 테스트용 날짜
        "numOfRows": "1"
    }
    try:
        print(">>> 공공데이터 API 키 테스트를 시작합니다...")
        response = requests.get(test_url, params=test_params, timeout=10)
        print(f">>> 응답 코드: {response.status_code}")
        print(f">>> 응답 내용: {response.text}")
        if "SERVICE KEY IS NOT REGISTERED" in response.text:
            return "<h1>테스트 실패: 공공데이터 API 키가 잘못되었습니다.</h1><p>Render의 환경 변수에서 GO_DATA_API_KEY 값을 다시 확인해주세요.</p>"
        elif response.status_code == 200:
            return "<h1>테스트 성공: 공공데이터 API 키가 정상입니다.</h1>"
        else:
            return f"<h1>테스트 실패: 알 수 없는 오류. 응답 코드: {response.status_code}</h1><p>{response.text}</p>"
    except Exception as e:
        print(f">>> 테스트 중 예외 발생: {e}")
        return f"<h1>테스트 실패: 서버에서 예외가 발생했습니다.</h1><p>{e}</p>"

if __name__ == '__main__':
    app.run(debug=True)
