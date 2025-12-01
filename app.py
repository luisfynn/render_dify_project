import os
from flask import Flask, request, render_template_string
import requests
import re
import json

app = Flask(__name__)

# ---------------------------------------------------------
# 설정 (Render 환경변수에서 가져옴)
# ---------------------------------------------------------
DIFY_API_KEY = os.environ.get("DIFY_API_KEY")
DIFY_URL = "https://api.dify.ai/v1/chat-messages"

# ---------------------------------------------------------
# 프론트엔드 (오류 없는 깔끔한 버전)
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
        .message { padding: 12px 16px; border-radius: 15px; max-width: 85%; line-height: 1.6; font-size: 15px; word-break: break-word; }
        .user-msg { align-self: flex-end; background-color: #007bff; color: white; border-bottom-right-radius: 2px; }
        .ai-msg { align-self: flex-start; background-color: #f1f3f5; color: #333; border-bottom-left-radius: 2px; }
        
        /* 이미지 스타일 */
        .ai-msg img { max-width: 100%; border-radius: 10px; margin-top: 10px; display: block; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        
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
            <div class="message ai-msg">안녕하세요! 메타원 쇼핑입니다.<br>원하는 이미지를 찾아드리고 결제까지 도와드려요!</div>
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

            // UI 업데이트
            appendMessage(query, 'user-msg');
            input.value = '';
            btn.disabled = true; // 중복 전송 방지
            const loadingMsg = appendMessage("생각 중... (서버가 깨어나는 중일 수 있습니다)", 'ai-msg');

            try {
                // 서버로 전송
                const response = await fetch('/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ query: query })
                });
                
                const data = await response.json();
                loadingMsg.remove(); // 로딩 삭제

                // AI 응답 처리
                let aiText = data.answer;
                let showPayment = false;

                // 결제 태그 확인
                if (aiText.includes('[PAYMENT_ACTION]')) {
                    showPayment = true;
                    aiText = aiText.replace('[PAYMENT_ACTION]', '');
                }

                // 메시지 표시 (이미지 변환 포함)
                appendMessage(aiText, 'ai-msg');

                // 결제 버튼 표시
                if (showPayment) {
                    const payDiv = document.createElement('div');
                    payDiv.className = 'payment-card';
                    payDiv.innerHTML = `
                        <p style="margin:0 0 10px 0; font-weight:bold;">💳 결제를 진행하시겠습니까?</p>
                        <button class="pay-btn" onclick="alert('결제 완료!')">바로 구매하기</button>
                    `;
                    chatHistory.appendChild(payDiv);
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                }

            } catch (err) {
                loadingMsg.innerText = "오류 발생: " + err.message;
            } finally {
                btn.disabled = false; // 버튼 다시 활성화
            }
        }

        // 텍스트를 HTML로 변환 (마크다운 이미지 처리)
        function appendMessage(text, className) {
            const chatHistory = document.getElementById('chat-history');
            const div = document.createElement('div');
            div.className = `message ${className}`;
            
            if (className === 'user-msg') {
                div.innerText = text;
            } else {
                // 줄바꿈 처리
                let formatted = text.replace(/\\n/g, '<br>');
                // 마크다운 이미지 문법 ![설명](URL) -> <img src="URL"> 로 변환
                formatted = formatted.replace(/!\\[(.*?)\\]\\((.*?)\\)/g, '<br><img src="$2" alt="$1"><br>');
                div.innerHTML = formatted;
            }

            chatHistory.appendChild(div);
            chatHistory.scrollTop = chatHistory.scrollHeight;
            return div;
        }
    </script>
</body>
</html>
"""

# ---------------------------------------------------------
# 백엔드 로직 (안정적인 데이터 수집 방식)
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
    
    # 1. Dify에 스트리밍으로 요청 (Agent 필수)
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

        # 2. 스트리밍 데이터를 Python이 모두 모음 (버퍼링)
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
        
        # 3. 완성된 문장 하나만 프론트엔드로 보냄
        return {"answer": full_answer}

    except Exception as e:
        print(f"Error: {e}")
        return {"answer": f"서버 오류: {str(e)}"}

if __name__ == '__main__':
    app.run(debug=True)