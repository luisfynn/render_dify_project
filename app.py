import os
from flask import Flask, request, render_template_string
import requests
import re
import json

app = Flask(__name__)

# ---------------------------------------------------------
# 설정 (Render 환경변수 또는 직접 입력)
# ---------------------------------------------------------
DIFY_API_KEY = os.environ.get("DIFY_API_KEY")
DIFY_URL = "https://api.dify.ai/v1/chat-messages"

# ---------------------------------------------------------
# 프론트엔드 (HTML + JS) - [수정됨: 이미지 렌더링 기능 강화]
# ---------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 쇼핑 에이전트</title>
    <style>
        body { font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px; }
        .chat-container { max-width: 500px; margin: 0 auto; background: white; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden; height: 90vh; display: flex; flex-direction: column; }
        
        #chat-history { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 15px; }
        .message { padding: 12px 16px; border-radius: 15px; max-width: 85%; line-height: 1.6; font-size: 15px; word-break: break-word; }
        .user-msg { align-self: flex-end; background-color: #007bff; color: white; border-bottom-right-radius: 2px; }
        .ai-msg { align-self: flex-start; background-color: #f1f3f5; color: #333; border-bottom-left-radius: 2px; }
        
        /* 이미지 스타일 */
        .ai-msg img { max-width: 100%; border-radius: 10px; margin-top: 10px; display: block; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        
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
            <div class="message ai-msg">안녕하세요! (주)파이썬샵 쇼핑 에이전트입니다. <br>원하시는 상품 이미지를 찾아드리고 결제까지 도와드려요!</div>
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
                
                if (!response.ok) {
                    throw new Error("서버 연결 실패");
                }

                loadingMsg.remove();
                
                // 스트리밍 데이터 처리 (전체 합치기)
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullAnswer = "";

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value, { stream: true });
                    // Dify 스트리밍 포맷 파싱
                    const lines = chunk.split('\\n');
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const json = JSON.parse(line.substring(6));
                                if (json.answer) fullAnswer += json.answer;
                            } catch (e) {}
                        }
                    }
                }
                
                // [PAYMENT_ACTION] 태그 확인 및 제거
                let showPayment = false;
                if (fullAnswer.includes('[PAYMENT_ACTION]')) {
                    showPayment = true;
                    fullAnswer = fullAnswer.replace('[PAYMENT_ACTION]', '');
                }

                // 메시지 표시 (마크다운 파싱 적용됨)
                appendMessage(fullAnswer, 'ai-msg');

                // 결제 버튼 표시
                if (showPayment) {
                    const payDiv = document.createElement('div');
                    payDiv.className = 'payment-card';
                    payDiv.innerHTML = `
                        <p style="margin:0 0 10px 0; color:#333; font-weight:bold;">💳 마음에 드시나요?</p>
                        <button class="pay-btn" onclick="alert('결제 완료! (데모)')">바로 구매하기</button>
                    `;
                    chatHistory.appendChild(payDiv);
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                }

            } catch (err) {
                loadingMsg.innerText = "오류가 발생했습니다: " + err.message;
            }
        }

        // [중요] 텍스트를 HTML로 변환하는 함수
        function appendMessage(text, className) {
            const chatHistory = document.getElementById('chat-history');
            const div = document.createElement('div');
            div.className = `message ${className}`;
            
            // 1. 사용자 메시지는 그냥 텍스트로 표시
            if (className === 'user-msg') {
                div.innerText = text;
            } 
            // 2. AI 메시지는 마크다운(이미지)을 해석해서 표시
            else {
                // (1) 줄바꿈 문자(\n)를 <br>로 변환
                let formatted = text.replace(/\\n/g, '<br>');
                
                // (2) 마크다운 이미지 문법 ![설명](URL) 을 <img src="URL"> 태그로 변환 (정규식 사용)
                formatted = formatted.replace(/!\\[(.*?)\\]\\((.*?)\\)/g, '<br><img src="$2" alt="$1"><br>');
                
                // HTML로 넣기 (그래야 이미지가 보임)
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
# 백엔드 로직
# ---------------------------------------------------------
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/ask', methods=['POST'])
def ask_agent():
    user_query = request.json.get('query')
    
    # 헤더 설정
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 페이로드 설정 (streaming 모드)
    payload = {
        "inputs": {},
        "query": user_query,
        "response_mode": "streaming",
        "user": "agent-user-001"
    }

    # Dify로 요청 보내고 응답을 그대로 클라이언트에게 패스 (Proxy)
    # 이렇게 하면 파이썬에서 조립하지 않고 브라우저가 직접 조각을 받아서 처리합니다. (더 빠름)
    resp = requests.post(DIFY_URL, json=payload, headers=headers, stream=True)
    return resp.raw.read(), resp.status_code, resp.headers.items()

if __name__ == '__main__':
    app.run(debug=True)