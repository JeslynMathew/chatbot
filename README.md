# DarGlobal & Wasalt AI Chatbot

A retrieval-augmented (RAG) chatbot that answers questions about **Dar Global** (international luxury real estate developer) and **Wasalt** (Saudi real estate platform), using data scraped from their public websites. It runs on a free OpenRouter model, is containerised with Docker, and is deployed on a free tier.

**Live demo:** https://chatbot-hiic.onrender.com
> The app runs on a free tier. After inactivity it sleeps, so the first load may take about a minute. The free model also has a daily request limit.

## How it works

```
Public websites -> scraper.py -> data/corpus.jsonl
                                      |
User question -> BM25 search (top 5 chunks) -> prompt with context -> OpenRouter free model -> answer + sources
```

1. **Scrape:** `scraper.py` crawls public pages of both companies (respecting `robots.txt`, with a delay between requests), cleans the text and splits it into overlapping chunks. Wasalt's blog is read through its public WordPress REST API.
2. **Retrieve:** at query time, BM25 ranks the chunks and the top matches are selected. BM25 needs no embedding model, so the container stays small and starts fast on free hardware.
3. **Generate:** the matches and the question are sent to a free OpenRouter model, instructed to answer only from the provided context. If the answer is not in the data, the bot says so.
4. **Cite:** each response lists the source URLs it used.

If one free model is unavailable, the app automatically tries the next one in its fallback list.

## Tech stack
- Python 3.11, FastAPI, Uvicorn
- requests + BeautifulSoup (scraping)
- rank-bm25 (retrieval)
- OpenRouter API (free `:free` models)
- Plain HTML/JS chat UI
- Docker, deployed on Render (free instance)

## Project structure
```
.
├── app.py              # FastAPI app: retrieval + OpenRouter call + /chat, /health
├── scraper.py          # Web scraper -> data/corpus.jsonl
├── static/index.html   # Chat UI
├── data/
│   ├── corpus.jsonl    # Scraped dataset
│   └── seed.jsonl      # Small supplementary set of public summaries (press coverage)
├── Dockerfile
├── requirements.txt
└── README.md
```

## Dataset
- **DarGlobal:** project pages, FAQ, insights, partners, tokenization, and other public pages.
- **Wasalt:** public blog posts (WordPress API).
- **Supplementary:** `seed.jsonl` holds a few short summaries of public information from press coverage of both companies.

Only publicly available pages are used. To refresh the data, run `python scraper.py`.

## Run locally

```bash
pip install -r requirements.txt
python scraper.py                       # optional, refreshes the dataset
```

Set your OpenRouter key (free at https://openrouter.ai/keys), then start the server:

```powershell
# Windows PowerShell
$env:OPENROUTER_API_KEY="sk-or-v1-..."
uvicorn app:app --port 7860
```
```bash
# macOS / Linux
export OPENROUTER_API_KEY="sk-or-v1-..."
uvicorn app:app --port 7860
```

Open http://localhost:7860. A health check is available at `/health` (shows the number of loaded chunks and whether the key is set).

## Run with Docker

```bash
docker build -t darglobal-wasalt-bot .
docker run -p 7860:7860 -e OPENROUTER_API_KEY=sk-or-v1-... darglobal-wasalt-bot
```

## Configuration

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | Your OpenRouter API key. Never commit it. |
| `MODELS` | No | Comma-separated model list tried in order, e.g. `meta-llama/llama-3.3-70b-instruct:free,openrouter/free` |
| `PORT` | No | Port to listen on (set automatically by Render; defaults to 7860) |

Free model names change over time. See https://openrouter.ai/models?q=free for current ones.


## API

`POST /chat`
```json
{ "message": "What is Dar Global?", "history": [] }
```
Response:
```json
{ "answer": "...", "sources": ["https://..."], "model": "..." }
```

## Limitations
- Answers depend on the scraped data and on a small free model, so details can occasionally be incomplete or merged incorrectly. Check the cited sources for important facts.
- Some pages that load content with JavaScript may not be captured by the scraper.
- Free-tier constraints: the instance sleeps after inactivity and the free model has a daily request cap.
- Retrieval is keyword-based (BM25), so unusual wording may retrieve less relevant chunks.

## Possible improvements
- Add embeddings-based retrieval, or a hybrid of BM25 and embeddings.
- Use a headless browser to capture JavaScript-rendered pages.
- Stream responses and add rate limiting.
