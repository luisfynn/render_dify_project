import os
from flask import Flask, request, render_template_string
import requests
import re

app = Flask(__name__)

# ---------------------------------------------------------
# 1. 설정 (Render 환경변수에서 가져옴)
# ---------------------------------------------------------
# 로컬 테스트할 땐 "sk-..." 부분에 실제 키를 넣어도 되지만,
# Render 배포 시에는 Render 대시보드에서 환경변수로 설정하는 게 안전합니다.
DIFY_API_KEY = os.environ.get("DIFY_API_KEY", "여기에_임시로_키_입력_가능")
DIFY_URL = "https://api.dify.ai/v1/chat-messages"

# ---------------------------------------------------------
# 2. 프론트엔드 HTML (사용자 화면)
# ---------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 이미지 검색 에이전트</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; text-align: center; background-color: #f0f2f5; padding: 20px; }
        .chat-container { max-width: 600px; margin: 0 auto; background: white; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding: 20px; }
        h1 { color: #333; margin-bottom: 30px; }
        .input-group { display: flex; gap: 10px; margin-bottom: 20px; }
        input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 16px; outline: none; }
        input:focus { border-color: #007bff; }
        button { padding: 12px 24px; background-color: #007bff; color: white; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; transition: background 0.2s; }
        button:hover { background-color: #0056b3; }
        button:disabled { background-color: #ccc; }
        #result-area { margin-top: 20px; min-height: 200px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        img { max-width: 100%; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-top: 15px; animation: fadeIn 0.5s; }
        .text-msg { color: #555; line-height: 1.5; font-size: 1.1rem; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <div class="chat-container">
        <h1>🎨 AI 이미지 큐레이터</h1>
        <div class="input-group">
            <input type="text" id="user-input" placeholder="예: 화사한 느낌의 산 그림 찾아줘" onkeypress="if(event.keyCode==13) search()">
            <button onclick="search()" id="btn">검색</button>
        </div>
        <div id="result-area">
            <p class="text-msg">원하는 이미지를 설명하면 AI가 찾아드립니다.</p>
        </div>
    </div>

    <script>
        async function search() {
            const input = document.getElementById('user-input');
            const resultDiv = document.getElementById('result-area');
            const btn = document.getElementById('btn');
            
            if (!input.value.trim()) return;

            // 로딩 상태
            btn.disabled = true;
            btn.innerText = "찾는 중...";
            resultDiv.innerHTML = '<p class="text-msg">AI가 지식 베이스를 검색 중입니다... 🔍</p>';

            try {
                const response = await fetch('/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ query: input.value })
                });
                
                const data = await response.json();
                
                // 결과 렌더링
                let html = `<p class="text-msg">${data.answer}</p>`;
                if (data.image_url) {
                    html += `<img src="${data.image_url}" alt="검색 결과">`;
                }
                resultDiv.innerHTML = html;

            } catch (err) {
                resultDiv.innerHTML = '<p class="text-msg" style="color:red">오류가 발생했습니다.</p>';
                console.error(err);
            } finally {
                btn.disabled = false;
                btn.innerText = "검색";
            }
        }
    </script>
</body>
</html>
"""

# ---------------------------------------------------------
# 3. 라우팅 (URL 처리)
# ---------------------------------------------------------
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/ask', methods=['POST'])
def ask_agent():
    user_query = request.json.get('query')
    
    # Dify API 호출
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": {},
        "query": user_query,
        "response_mode": "blocking",
        "user": "render-user-01"
    }

    try:
        response = requests.post(DIFY_URL, json=payload, headers=headers)
        if response.status_code != 200:
            return {"answer": f"API 오류: {response.status_code}", "image_url": None}
            
        dify_data = response.json()
        full_answer = dify_data.get('answer', '')

        # 텍스트에서 이미지 URL 추출 (정규표현식)
        # http(s)로 시작하고 이미지 확장자로 끝나는 주소 찾기
        img_match = re.search(r'(https?://[^\s]+(?:\.jpg|\.png|\.jpeg|\.gif|\.webp))', full_answer)
        
        image_url = img_match.group(0) if img_match else None
        
        # (선택사항) 답변 텍스트에서 URL은 지우고 깔끔한 텍스트만 보내고 싶으면:
        # clean_text = full_answer.replace(image_url, '') if image_url else full_answer
        
        return {"answer": full_answer, "image_url": image_url}

    except Exception as e:
        return {"answer": f"서버 내부 오류: {str(e)}", "image_url": None}

if __name__ == '__main__':
    app.run(debug=True)