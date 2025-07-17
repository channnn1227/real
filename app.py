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
        "LAWD_CD": b_code[:5],  # API 규격에 맞게 법정동 코드 앞 5자리만 사용
        "DEAL_YMD": deal_ymd,
        "numOfRows": "50"
    }
    try:
        response = requests.get(url, params=params, timeout=10) # 타임아웃을 10초로 넉넉하게 설정
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

@app.route('/search', methods=['POST'])
def search():
    address = request.form.get('address')
    if not address:
        return jsonify({"error": "주소가 입력되지 않았습니다."}), 400

    location_info = get_coords_from_address(address)
    if not location_info:
        return jsonify({"error": "주소를 찾을 수 없거나 변환에 실패했습니다."}), 404

    today = datetime.now()
    transactions = []
    for i in range(12): # 최근 12개월
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

if __name__ == '__main__':
    # 이 부분은 Render에서 Gunicorn을 사용할 때는 실행되지 않습니다.
    # 로컬 PC에서 직접 테스트할 때만 사용됩니다.
    app.run(debug=True)
