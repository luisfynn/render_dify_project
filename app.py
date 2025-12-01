import os
from flask import Flask, request, render_template_string
import requests
import re
import json

app = Flask(__name__)

# ---------------------------------------------------------
# 설정 (Render 환경변수)
# ---------------------------------------------------------
DIFY_API_KEY = os.environ.get("DIFY_API_KEY")
DIFY_URL = "https://api.dify.ai/v1/chat-messages"

# ---------------------------------------------------------
# 프론트엔드 (Marked 라이브러리 적용 버전)
# ---------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 쇼핑 에이전트</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        body { font-family: 'Pretendard', sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px; }
        .chat-container { max-width: 600px; margin: 0 auto; background: white; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden; height: 90vh; display: flex; flex-direction: column; }
        
        #chat-history { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 15px; }
        .message { padding: 15px; border-radius: 15px; max-width: 85%; line-height: 1.6; font-size: 15px; word-break: break-word; }
        .user-msg { align-self: flex-end; background-color: #007bff; color: white; border-bottom-right-radius: 2px; }
        .ai-msg { align-self: flex-start; background-color: #f1f3f5; color: #333; border-bottom-left-radius: 2px; }
        
        /* 이미지 스타일 - 화면에 꽉 차게 예쁘게 나옴 */
        .ai-msg img { max-width: 100%; height: auto; border-radius: 10px; margin-top: 10px; display: block; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .ai-msg p { margin: 0 0 10px 0; } /* 문단 간격 */
        
        .input-area { padding: 20px; background: white; border-top: 1px solid #eee; display: flex; gap: 10px; }
        input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 25px; outline: none; padding-left: 20px; }
        button { background: #007bff; color: white; border: none; padding: 0 20px; border-radius: 25px; cursor: pointer; font-weight: bold; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        
        .payment-card { margin-top: 10px; padding: 15px; background: #e3f2fd; border-radius: 10px; text-align: center; border: 1px solid #90caf9; animation: slideUp 0.3s; }
        .pay-btn { background: #ff4757; color: white; padding: 10px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; font-weight: bold; margin-top: 5px; }
        
        @keyframes slideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <div class="chat-container">
        <div id="chat-history">
            <div class="message ai-msg">안녕하세요! 쇼핑 에이전트입니다.</div>
        </div>
        <div class="input-area">
            <input type="text" id="user-input" placeholder="예: 화사한 산 그림 보여줘" onkeypress="if(event.keyCode==13) sendMessage()">
            <button id="send-btn" onclick="sendMessage()">전송</button>
        </div>
    </div>

    <script>
        async function sendMessage() {
            const input = document.getElementById('user-input');
            const btn = document.getElementById('send-btn');
            const chatHistory = document.getElementById('chat-history');
            const query = input.value.trim();
            
            if (!query) return;

            // 사용자 메시지 표시
            appendMessage(query, 'user-msg');
            input.value = '';
            btn.disabled = true;
            
            // 로딩 표시
            const loadingId = 'loading-' + Date.now();
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'message ai-msg';
            loadingDiv.id = loadingId;
            loadingDiv.innerText = "생각 중...";
            chatHistory.appendChild(loadingDiv);
            chatHistory.scrollTop = chatHistory.scrollHeight;

            try {
                const response = await fetch('/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ query: query })
                });
                
                const data = await response.json();
                document.getElementById(loadingId).remove(); // 로딩 삭제

                let aiText = data.answer;
                let showPayment = false;

                if (aiText.includes('[PAYMENT_ACTION]')) {
                    showPayment = true;
                    aiText = aiText.replace('[PAYMENT_ACTION]', '');
                }

                // [핵심] Marked 라이브러리로 마크다운 -> HTML 변환 (이미지, 볼드체 등 완벽 지원)
                // parse 함수가 ![...](url)을 <img src="url">로 바꿔줍니다.
                const htmlContent = marked.parse(aiText);
                appendHTMLMessage(htmlContent, 'ai-msg');

                if (showPayment) {
                    const payDiv = document.createElement('div');
                    payDiv.className = 'payment-card';
                    payDiv.innerHTML = `
                        <p style="margin:0 0 10px 0; font-weight:bold;">💳 결제를 진행하시겠습니까?</p>
                        <a href="https://luisfynn.pythonanywhere.com/payment" target="_top">
                            <button class="pay-btn">결제하러 가기</button>
                        </a>
                    `;
                    chatHistory.appendChild(payDiv);
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                }

            } catch (err) {
                if(document.getElementById(loadingId)) document.getElementById(loadingId).innerText = "오류: " + err.message;
            } finally {
                btn.disabled = false;
            }
        }

        function appendMessage(text, className) {
            const chatHistory = document.getElementById('chat-history');
            const div = document.createElement('div');
            div.className = `message ${className}`;
            div.innerText = text;
            chatHistory.appendChild(div);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }

        // HTML을 그대로 넣는 함수 (AI 메시지용 - 이미지 렌더링)
        function appendHTMLMessage(html, className) {
            const chatHistory = document.getElementById('chat-history');
            const div = document.createElement('div');
            div.className = `message ${className}`;
            div.innerHTML = html; // 변환된 HTML 삽입
            chatHistory.appendChild(div);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
    </script>
</body>
</html>
"""

# ---------------------------------------------------------
# 백엔드 로직
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
    
    payload = {
        "inputs": {},
        "query": user_query,
        "response_mode": "streaming",
        "user": "agent-user-001"
    }

    try:
        response = requests.post(DIFY_URL, json=payload, headers=headers, stream=True)
        if response.status_code != 200:
            return {"answer": f"⛔ 연결 실패! 상태코드: {response.status_code}, 이유: {response.text}"}

        full_answer = ""
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    try:
                        json_data = json.loads(decoded_line[6:])
                        chunk = json_data.get('answer', '')
                        full_answer += chunk
                    except:
                        pass
        
        return {"answer": full_answer}

    except Exception as e:
        print(f"Error: {e}")
        return {"answer": f"서버 오류: {str(e)}"}

if __name__ == '__main__':
    app.run(debug=True)