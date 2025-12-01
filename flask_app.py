import os
import pandas as pd
import google.generativeai as genai
from flask import Flask, render_template, request, redirect, url_for
from git import Repo
from dotenv import load_dotenv

# .env 파일을 절대 경로로 명시적으로 로드 (PythonAnywhere 호환성 강화)
project_folder = os.path.expanduser('~/mysite')
load_dotenv(os.path.join(project_folder, '.env'))

app = Flask(__name__)
# 업로드 용량 제한 해제 (16MB)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- setting
GITHUB_USER = os.getenv("GITHUB_USER") # .env에서 가져오도록 수정 (보안)
GITHUB_REPO = os.getenv("GITHUB_REPO") # .env에서 가져오도록 수정 (보안)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# file path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_IMG_DIR = os.path.join(BASE_DIR, 'static/images')
CSV_PATH = os.path.join(BASE_DIR, 'data.csv')

# Gemini setting (예외 처리 추가)
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('models/gemini-flash-latest')

# main page (chatbot + image upload)
@app.route('/')
def index():
    images = []
    if os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH)
            # 최신순으로 정렬 (역순)
            images = df.to_dict(orient='records')[::-1]
        except Exception as e:
            print(f"Error reading CSV: {e}")

    # [수정] images 변수를 HTML로 넘겨줘야 갤러리가 보입니다!
    return render_template('index.html', images=images)

# upload image & auto update
@app.route('/upload', methods=['POST'])
def upload_image():
    try:
        # [수정] HTML form의 name="image"와 일치해야 함 ('images' 아님)
        if 'image' not in request.files:
            return 'Error: No image part in request'

        file = request.files['image'] # [수정] 'images' -> 'image'
        if file.filename == '':
            return 'Error: No selected file'

        # save image
        filename = file.filename.lower()

        if not os.path.exists(STATIC_IMG_DIR):
            os.makedirs(STATIC_IMG_DIR)

        save_path = os.path.join(STATIC_IMG_DIR, filename)
        file.save(save_path)

        # request image explanation for gemini
        description = f"new art ({filename})"
        try:
            if GEMINI_KEY:
                sample_file = genai.upload_file(save_path)

                # [핵심 1] 프롬프트 강력 수정: "오직 키워드만 줘!"
                prompt = """
                Analyze this image and provide exactly 10 keywords for online shopping.
                Include both factual objects (e.g., Mountain, River) and emotional atmosphere (e.g., Serene, Majestic).

                CRITICAL RULE:
                - Output ONLY the keywords separated by commas.
                - Do NOT write 'Product Description', 'Keywords:', or any introduction.
                - Do NOT use bullet points or numbering.

                Format example: Mount Fuji, Sunset, Peaceful, Red, Nature, Dreamy, Art, Landscape, Calm, Beautiful
                """

                response = model.generate_content([prompt, sample_file])
                raw_text = response.text.strip()

                # [핵심 2] 전처리 (파이썬으로 혹시 모를 찌꺼기 제거)
                # 1. 마크다운 볼드체(**) 제거
                clean_text = raw_text.replace('**', '')
                # 2. 'Keywords:' 같은 라벨이 있으면 그 뒷부분만 잘라내기
                if ':' in clean_text:
                    clean_text = clean_text.split(':')[-1].strip()
                # 3. 줄바꿈을 쉼표로 변경 (혹시 리스트로 줄 경우 대비)
                clean_text = clean_text.replace('\n', ', ')

                description = clean_text

        except Exception as e:
            print(f"Gemini Error: {e}")

        # github url setting (main branch)
        raw_url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/static/images/{filename}"

        # update csv
        new_row = {"description": description, "url": raw_url}

        if os.path.exists(CSV_PATH):
            df = pd.read_csv(CSV_PATH)
            new_df = pd.DataFrame([new_row]) # [수정] pd.DataFrame (대문자 F)
            df = pd.concat([df, new_df], ignore_index=True)
        else:
            df = pd.DataFrame([new_row]) # [수정] pd.DataFrame

        df.to_csv(CSV_PATH, index=False)

        # Git Push
        try:
            repo = Repo(BASE_DIR)

            # git setting (최초 1회 설정용, 에러 방지)
            with repo.config_writer() as git_config:
                if not git_config.has_option('user', 'email'):
                    git_config.set_value('user', 'email', 'auto@bot.com')
                    git_config.set_value('user', 'name', 'AutoUploader')

            repo.index.add([save_path, CSV_PATH])
            repo.index.commit(f"Add image {filename} via Web")

            # use Token for Push URL [수정] https 사용
            remote_url = f"https://{GITHUB_USER}:{GITHUB_TOKEN}@github.com/{GITHUB_USER}/{GITHUB_REPO}.git"

            # 리모트 설정 안전하게 처리
            if 'origin' in repo.remotes:
                repo.remotes.origin.set_url(remote_url)
                repo.remotes.origin.push()
            else:
                repo.create_remote('origin', remote_url)
                repo.remotes.origin.push()

        except Exception as e:
            return f"Git push failed: {e}"

        return redirect(url_for('index'))

    except Exception as e:
        return f"Server Error: {str(e)}"

# payment
@app.route('/payment')
def payment():
    images = []
    if os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        images = df.to_dict(orient='records')
    return render_template('payment.html', images=images)

# payment success
@app.route('/success')
def success():
    return render_template('success.html')

if __name__ == '__main__':
    app.run()