---
title: DarGlobal Wasalt Chatbot
emoji: 🏙️
colorFrom: gray
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---
# DarGlobal & Wasalt RAG Chatbot
Scraper (requests + BeautifulSoup) -> BM25 retrieval -> OpenRouter free LLM -> FastAPI UI, packaged with Docker.

Local run:
```
pip install -r requirements.txt
python scraper.py
export OPENROUTER_API_KEY=sk-or-...
uvicorn app:app --port 7860
```
Docker: `docker build -t chatbot . && docker run -p 7860:7860 -e OPENROUTER_API_KEY=sk-or-... chatbot`
