import os
from flask import Flask, request, render_template_string
import requests
import re
import json # [추가] JSON 처리를 위해 필요

app = Flask(__name__)

# ---------------------------------------------------------
# 설정 (Render 환경변수 또는 직접 입력)
# ---------------------------------------------------------
DIFY_API_KEY = os.environ.get("DIFY_API_KEY")
DIFY_URL = "https://api.dify.ai/v1/chat-messages"

# ---------------------------------------------------------
# 프론트엔드 (HTML + JS)
# ---------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 쇼핑 에이전트</title>
    <style>
        body { font-family: 'Pretendard', sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px; }
        .chat-container { max-width: 500px; margin: 0 auto; background: white; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden; height: 90vh; display: flex; flex-direction: column; }
        
        #chat-history { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 15px; }
        .message { padding: 12px 16px; border-radius: 15px; max-width: 80%; line-height: 1.5; font-size: 15px; }
        .user-msg { align-self: flex-end; background-color: #007bff; color: white; border-bottom-right-radius: 2px; }
        .ai-msg { align-self: flex-start; background-color: #f1f3f5; color: #333; border-bottom-left-radius: 2px; }
        
        .ai-msg img { max-width: 100%; border-radius: 10px; margin-top: 10px; display: block; }
        
        .input-area { padding: 20px; background: white; border-top: 1px solid #eee; display: flex; gap: 10px; }
        input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 25px; outline: none; padding-left: 20px; }
        button#send-btn { background: #007bff; color: white; border: none; padding: 0 20px; border-radius: 25px; cursor: pointer; font-weight: bold; }
        
        .payment-card { margin-top: 10px; padding: 15px; background: #e3f2fd; border-radius: 10px; text-align: center; border: 1px solid #90caf9; animation: slideUp 0.3s; }
        .pay-btn { background: #ff4757; color: white; padding: 10px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; font-weight: bold; margin-top: 5px; }
        .pay-btn:hover { background: #ff6b81; }

        @keyframes slideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <div class="chat-container">
        <div id="chat-history">
            <div class="message ai-msg">안녕하세요! 무엇을 도와드릴까요? <br>상품 추천부터 결제까지 도와드립니다.</div>
        </div>
        <div class="input-area">
            <input type="text" id="user-input" placeholder="예: 화사한 산 그림 보여줘" onkeypress="if(event.keyCode==13) sendMessage()">
            <button id="send-btn" onclick="sendMessage()">전송</button>
        </div>
    </div>

    <script>
        async function sendMessage() {
            const input = document.getElementById('user-input');
            const chatHistory = document.getElementById('chat-history');
            const query = input.value.trim();
            
            if (!query) return;

            appendMessage(query, 'user-msg');
            input.value = '';
            const loadingMsg = appendMessage("생각 중...", 'ai-msg');

            try {
                const response = await fetch('/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ query: query })
                });
                const data = await response.json();
                
                loadingMsg.remove();

                let aiText = data.answer;
                let showPayment = false;
                if (aiText.includes('[PAYMENT_ACTION]')) {
                    showPayment = true;
                    aiText = aiText.replace('[PAYMENT_ACTION]', '');
                }

                const msgDiv = appendMessage(aiText, 'ai-msg');
                
                if (data.image_url) {
                    const img = document.createElement('img');
                    img.src = data.image_url;
                    msgDiv.appendChild(img);
                }

                if (showPayment) {
                    const payDiv = document.createElement('div');
                    payDiv.className = 'payment-card';
                    payDiv.innerHTML = `
                        <p style="margin:0 0 10px 0; color:#333; font-weight:bold;">💳 결제를 진행하시겠습니까?</p>
                        <button class="pay-btn" onclick="alert('결제 페이지로 이동합니다! (데모)')">바로 구매하기</button>
                    `;
                    chatHistory.appendChild(payDiv);
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                }

            } catch (err) {
                loadingMsg.innerText = "오류가 발생했습니다.";
            }
        }

        function appendMessage(text, className) {
            const chatHistory = document.getElementById('chat-history');
            const div = document.createElement('div');
            div.className = `message ${className}`;
            div.innerText = text;
            chatHistory.appendChild(div);
            chatHistory.scrollTop = chatHistory.scrollHeight;
            return div;
        }
    </script>
</body>
</html>
"""

# ---------------------------------------------------------
# 백엔드 로직 (수정된 부분)
# ---------------------------------------------------------
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/ask', methods=['POST'])
def ask_agent():
    user_query = request.json.get('query')
    
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # [수정 1] Agent 앱은 반드시 streaming 모드를 써야 합니다.
    payload = {
        "inputs": {},
        "query": user_query,
        "response_mode": "streaming",  # blocking -> streaming 변경
        "user": "agent-user-001"
    }

    try:
        # [수정 2] stream=True 옵션 추가
        response = requests.post(DIFY_URL, json=payload, headers=headers, stream=True)
        
        if response.status_code != 200:
            error_msg = f"⛔ 연결 실패! 상태코드: {response.status_code}, 이유: {response.text}"
            print(error_msg)
            return {"answer": error_msg}

        # [수정 3] 스트리밍 데이터 조각 모으기
        full_answer = ""
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    try:
                        # "data: " 뒤에 있는 JSON 파싱
                        json_data = json.loads(decoded_line[6:])
                        # Agent는 'answer' 필드에 텍스트 조각을 줍니다.
                        chunk = json_data.get('answer', '')
                        full_answer += chunk
                    except:
                        pass
        
        # 이미지 URL 추출 (정규식)
        img_match = re.search(r'(https?://[^\s)]+(?:\.jpg|\.png|\.jpeg|\.gif|\.webp))', full_answer)
        image_url = img_match.group(0) if img_match else None
        
        return {"answer": full_answer, "image_url": image_url}

    except Exception as e:
        print(f"Error: {e}")
        return {"answer": f"서버 오류: {str(e)}"}

if __name__ == '__main__':
    app.run(debug=True)