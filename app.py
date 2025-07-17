import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime
import xml.etree.ElementTree as ET

app = Flask(__name__)
import os # 맨 위에 추가
# ★★★★★ 중요: 발급받은 API 키를 여기에 입력하세요 ★★★★★
KAKAO_API_KEY = "d513459fed9ef1d35fff8f4d4683e586"
GO_DATA_API_KEY = "Ey6bVfRVh4C0Cq1rGSFXGB0CwrvjExVFojpYYkv+VTYJDhV52GrxrzmhM2ydvKtcdq4ehvHxmW9dXKY00VvYzg=="
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

# 카카오 주소 -> 좌표 변환 API
# (이 부분을 아래 코드로 통째로 교체하세요)

# 카카오 키워드 -> 좌표 및 주소 변환 API
def get_coords_from_address(address):
    # API 엔드포인트를 '키워드 검색'으로 변경
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": address}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200 and response.json()['documents']:
        # 키워드 검색 결과에서 첫 번째 항목을 사용
        doc = response.json()['documents'][0]

        # 도로명 주소가 있는 경우, 해당 주소의 상세 정보 요청
        if doc.get('road_address_name'):
            address_detail_url = "https://dapi.kakao.com/v2/local/search/address.json"
            address_params = {"query": doc['road_address_name']}
            address_response = requests.get(address_detail_url, headers=headers, params=address_params)
            if address_response.status_code == 200 and address_response.json()['documents']:
                address_doc = address_response.json()['documents'][0]
                if address_doc.get('address') and address_doc['address'].get('b_code'):
                     return {
                        "lat": float(doc['y']),
                        "lng": float(doc['x']),
                        "b_code": address_doc['address']['b_code']
                    }
    return None # 검색 결과가 없으면 None 반환

# 국토교통부 실거래가 조회 API
def get_real_estate_transactions(b_code, deal_ymd):
    url = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTradeDev"
    params = {
        "serviceKey": GO_DATA_API_KEY,
        "LAWD_CD": b_code[:5],  # b_code의 앞 5자리만 사용해야 함
        "DEAL_YMD": deal_ymd,
        "numOfRows": "50"
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            transactions = []
            for item in root.findall('.//item'):
                price = item.find('거래금액').text.strip()
                apt_name = item.find('아파트').text.strip()
                area = item.find('전용면적').text.strip()
                deal_year = item.find('년').text.strip()
                deal_month = item.find('월').text.strip()
                deal_day = item.find('일').text.strip()
                transactions.append({
                    "price": f"{price}만원",
                    "apt_name": apt_name,
                    "area": f"{float(area):.2f}㎡",
                    "date": f"{deal_year}년 {deal_month}월 {deal_day}일"
                })
            return transactions
    except Exception as e:
        print(f"[실거래가 API 오류] {e}")
    return []


@app.route('/')
def index():
    # ★★★★★ 중요: index.html 렌더링 시 카카오 JavaScript 키를 함께 전달합니다. ★★★★★
    return render_template('index.html', KAKAO_JS_KEY="efc55d84df34922094681d91d24bf86d")

@app.route('/search', methods=['POST'])
def search():
    address = request.form.get('address')
    if not address:
        return jsonify({"error": "주소가 입력되지 않았습니다."}), 400

    location_info = get_coords_from_address(address)
    if not location_info:
        return jsonify({"error": "유효하지 않은 주소이거나 변환에 실패했습니다."}), 404

    try:
        today = datetime.now()
        transactions = []
        for i in range(12):  # 최근 12개월
            month_offset = today.month - i
            year_offset = today.year
            if month_offset <= 0:
                month_offset += 12
                year_offset -= 1
            deal_ymd = f"{year_offset}{month_offset:02d}"
            result = get_real_estate_transactions(location_info['b_code'], deal_ymd)
            if result:
                transactions.extend(result)

        unique_transactions = [dict(t) for t in {tuple(d.items()) for d in transactions}]

        return jsonify({
            "center": {"lat": location_info['lat'], "lng": location_info['lng']},
            "transactions": sorted(unique_transactions, key=lambda x: x['date'], reverse=True)
        })
    except Exception as e:
        return jsonify({"error": f"서버 오류: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True)