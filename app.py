import os
import re
import csv
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

# ---------- LOGGING ----------
LOG_FILE = "logs.csv"

def log_interaction(question, answer):
    try:
        file_exists = os.path.exists(LOG_FILE)
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "question", "answer_length"])
            writer.writerow([
                datetime.now().isoformat(timespec="seconds"),
                question,
                len(answer)
            ])
    except Exception:
        pass

# ---------- GUARDRAILS ----------
BLOCKED_PATTERNS = [
    r"\bsex\b", r"\bdrugs?\b", r"\bweapon\b",
    r"\bcrypto\b", r"\bstock\b", r"\bcheat\b"
]

def is_blocked(text):
    text = text.lower()
    return any(re.search(p, text) for p in BLOCKED_PATTERNS)

# ---------- API ----------
class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
def chat(req: ChatRequest):
    user_msg = req.message

    if is_blocked(user_msg):
        return {"answer": "Only K-12 educational questions are allowed."}

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "system",
                    "content": """You are a K-12 tutor.

Always respond in this format:
- Use short paragraphs
- Use bullet points when helpful
- Highlight key terms using **bold**
- End with:

Quick recap:
- point 1
- point 2
"""
                },
                {
                    "role": "user",
                    "content": f"Explain simply:\n{user_msg}"
                }
            ]
        )

        answer = response.choices[0].message.content

    except Exception as e:
        answer = f"Error: {str(e)}"

    log_interaction(user_msg, answer)

    return {"answer": answer}

# ---------- UI ----------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>AI Tutor</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0f172a;
            color: white;
        }

        .container {
            max-width: 800px;
            margin: auto;
            display: flex;
            flex-direction: column;
            height: 100vh;
        }

        header {
            padding: 15px;
            font-size: 20px;
            font-weight: bold;
            border-bottom: 1px solid #1e293b;
        }

        #chat {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }

        .msg {
            margin-bottom: 15px;
            max-width: 75%;
            padding: 12px 16px;
            border-radius: 12px;
            line-height: 1.5;
        }

        .user {
            background: #2563eb;
            margin-left: auto;
            text-align: right;
        }

        .bot {
            background: #1e293b;
            margin-right: auto;
        }

        footer {
            display: flex;
            padding: 10px;
            border-top: 1px solid #1e293b;
        }

        input {
            flex: 1;
            padding: 12px;
            border-radius: 10px;
            border: none;
            outline: none;
            font-size: 14px;
        }

        button {
            margin-left: 10px;
            padding: 12px 18px;
            border: none;
            border-radius: 10px;
            background: #2563eb;
            color: white;
            cursor: pointer;
        }

        button:hover {
            background: #1d4ed8;
        }

        ul {
            margin: 5px 0;
            padding-left: 20px;
        }

        .typing {
            font-size: 12px;
            color: #94a3b8;
        }
    </style>
</head>

<body>
<div class="container">
    <header>🎓 AI Tutor</header>

    <div id="chat"></div>

    <footer>
        <input id="msg" placeholder="Ask anything..." onkeydown="if(event.key==='Enter') send()" />
        <button onclick="send()">Send</button>
    </footer>
</div>

<script>

function formatResponse(text) {
    if (!text) return "";

    // bold
    text = text.replace(/\\*\\*(.*?)\\*\\*/g, "<b>$1</b>");

    // bullets
    text = text.replace(/^- (.*$)/gim, "<li>$1</li>");
    text = text.replace(/(<li>.*<\\/li>)/g, "<ul>$1</ul>");

    // line breaks
    text = text.replace(/\\n/g, "<br>");

    return text;
}

async function send() {
    const msgBox = document.getElementById("msg");
    const message = msgBox.value.trim();
    if (!message) return;

    const chat = document.getElementById("chat");

    chat.innerHTML += `<div class="msg user">${message}</div>`;

    const typingId = "typing-" + Date.now();
    chat.innerHTML += `<div id="${typingId}" class="typing">Thinking...</div>`;
    chat.scrollTop = chat.scrollHeight;

    msgBox.value = "";

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({message})
        });

        const data = await res.json();

        document.getElementById(typingId).remove();

        chat.innerHTML += `<div class="msg bot">${formatResponse(data.answer)}</div>`;
        chat.scrollTop = chat.scrollHeight;

    } catch (e) {
        document.getElementById(typingId).remove();
        chat.innerHTML += `<div class="msg bot">Error connecting to server</div>`;
    }
}
</script>

</body>
</html>
"""