import json, os, re
import requests
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from rank_bm25 import BM25Okapi

API_KEY = os.getenv("OPENROUTER_API_KEY", "")
# Free models change often; override with MODELS="a:free,b:free". "openrouter/free" auto-picks a free model.
MODELS = [m.strip() for m in os.getenv(
    "MODELS", "meta-llama/llama-3.3-70b-instruct:free,google/gemma-3-27b-it:free,openrouter/free").split(",")]

tok = lambda s: re.findall(r"\w+", s.lower())
docs = []
for fn in ("data/corpus.jsonl", "data/seed.jsonl"):
    if os.path.exists(fn):
        docs += [json.loads(l) for l in open(fn, encoding="utf-8") if l.strip()]
bm25 = BM25Okapi([tok(d["title"] + " " + d["text"]) for d in docs]) if docs else None

app = FastAPI()

class Req(BaseModel):
    message: str
    history: list[dict] = []

def retrieve(q, k=5):
    if not bm25:
        return []
    scores = bm25.get_scores(tok(q))
    idx = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)[:k]
    return [docs[i] for i in idx if scores[i] > 0]

SYSTEM = ("You are an assistant for Dar Global (luxury international real estate developer) and Wasalt "
          "(Saudi real estate platform). Answer ONLY from the provided context. If the answer is not in the "
          "context, say you don't have that information. Be concise and mention the source company.")

@app.post("/chat")
def chat(req: Req):
    ctx = retrieve(req.message)
    context = "\n\n".join(f"[{d['source']} | {d['url']}]\n{d['text']}" for d in ctx) or "No relevant context."
    messages = [{"role": "system", "content": f"{SYSTEM}\n\nCONTEXT:\n{context}"}]
    messages += [m for m in req.history[-6:] if m.get("role") in ("user", "assistant")]
    messages.append({"role": "user", "content": req.message})
    last_err = ""
    for model in MODELS:
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={"model": model, "messages": messages, "temperature": 0.2}, timeout=60)
            if r.status_code == 200:
                ans = r.json()["choices"][0]["message"]["content"]
                return {"answer": ans, "sources": sorted({d["url"] for d in ctx}), "model": model}
            last_err = f"{model}: {r.status_code} {r.text[:200]}"
        except Exception as e:
            last_err = f"{model}: {e}"
    return {"answer": f"Model unavailable. {last_err}", "sources": [], "model": None}

@app.get("/health")
def health():
    return {"chunks": len(docs), "key_set": bool(API_KEY)}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index():
    return FileResponse("static/index.html")
