"""Polite crawler for public pages of DarGlobal and Wasalt -> data/corpus.jsonl
Run:  python scraper.py
Respects robots.txt, rate-limits requests, prints why a page failed."""
import json, re, time, urllib.robotparser
from urllib.parse import urljoin, urlparse, urldefrag
import requests
from bs4 import BeautifulSoup

SITES = {
    "DarGlobal": {
        "domains": ["darglobal.co.uk", "darglobal.com"],
        "seeds": [
            "https://darglobal.co.uk/", "https://darglobal.co.uk/about",
            "https://darglobal.co.uk/projects", "https://darglobal.co.uk/press",
            "https://darglobal.co.uk/insights", "https://darglobal.co.uk/investor",
            "https://darglobal.co.uk/become-a-broker", "https://darglobal.co.uk/contact",
        ],
    },
    "Wasalt": {
        "domains": ["wasalt.sa", "wasalt.com"],
        "seeds": [
            "https://wasalt.sa/en", "https://wasalt.sa/en/corporate", "https://wasalt.com/en/about",
            "https://wasalt.sa/en/s/wasalt-business", "https://blog.wasalt.sa/en/",
        ],
    },
}
WP_BLOGS = {"Wasalt": "https://blog.wasalt.sa/en"}   # WordPress REST API (public)
MAX_PAGES = 80           # per site
DELAY = 0.6              # seconds between requests
CHUNK, OVERLAP = 900, 150
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "en",
}
SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".pdf", ".zip", ".mp4", ".css", ".js", ".ico", ".xml")
SKIP_LANG = re.compile(r"^/(ar|ru|zh|es|fr|de|el|it|tr|ko|ja|pt|hi|ur)(/|$)")
S = requests.Session(); S.headers.update(HEADERS)

def get(url):
    try:
        r = S.get(url, timeout=20)
        if r.status_code == 200:
            return r.text
        print(f"   ! {r.status_code} {url}")
    except requests.RequestException as e:
        print(f"   ! error {url}: {type(e).__name__}")
    return None

def sitemap_urls(base):
    out = []
    xml = get(urljoin(base, "/sitemap.xml"))
    if xml:
        locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", xml)
        for u in locs[:300]:
            if u.endswith(".xml"):
                x = get(u)
                if x:
                    out += re.findall(r"<loc>\s*(.*?)\s*</loc>", x)[:200]
            else:
                out.append(u)
    return out

def extract(html):
    soup = BeautifulSoup(html, "html.parser")
    links = [a["href"] for a in soup.find_all("a", href=True)]   # collect BEFORE removing nav/footer
    for t in soup(["script", "style", "noscript", "svg", "header", "footer", "nav", "form"]):
        t.decompose()
    title = soup.title.get_text(strip=True) if soup.title else ""
    parts = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "span", "div"]):
        if el.name in ("span", "div") and el.find(["p", "li", "div", "h1", "h2", "h3"]):
            continue
        t = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        if len(t) > 20 and (not parts or parts[-1] != t):
            parts.append(t)
    return title, links, "\n".join(parts)

def chunk(text):
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + CHUNK]); i += CHUNK - OVERLAP
    return out

def allowed(url, domains):
    p = urlparse(url)
    h = p.netloc.lower().replace("www.", "")
    return (any(h == d or h.endswith("." + d) for d in domains)
            and not p.path.lower().endswith(SKIP_EXT) and not SKIP_LANG.match(p.path))

def crawl(name, cfg):
    docs, seen, queue = [], set(), list(cfg["seeds"])
    for seed in cfg["seeds"][:2]:
        queue += sitemap_urls(seed)
    robots = {}
    while queue and len(seen) < MAX_PAGES:
        url = urldefrag(queue.pop(0))[0].rstrip("/")
        if not url or url in seen or not allowed(url, cfg["domains"]):
            continue
        host = urlparse(url).netloc
        if host not in robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                rp.set_url(f"https://{host}/robots.txt"); rp.read()
            except Exception:
                rp = None
            robots[host] = rp
        if robots[host] and not robots[host].can_fetch("*", url):
            continue
        seen.add(url)
        html = get(url); time.sleep(DELAY)
        if not html:
            continue
        title, links, text = extract(html)
        if len(text) > 100:
            for c in chunk(text):
                docs.append({"source": name, "url": url, "title": title, "text": c})
            print(f"[{name}] {url} ({len(text)} chars)")
        queue += [urljoin(url, l) for l in links]
    return docs

def wp_posts(name, base, pages=3):
    docs = []
    for p in range(1, pages + 1):
        raw = get(f"{base}/wp-json/wp/v2/posts?per_page=30&page={p}")
        if not raw:
            break
        try:
            posts = json.loads(raw)
        except ValueError:
            break
        for post in posts:
            text = BeautifulSoup(post["content"]["rendered"], "html.parser").get_text(" ", strip=True)
            title = BeautifulSoup(post["title"]["rendered"], "html.parser").get_text(strip=True)
            for c in chunk(re.sub(r"\s+", " ", text)):
                docs.append({"source": name, "url": post["link"], "title": title, "text": c})
        print(f"[{name}] blog API page {p}: {len(posts)} posts")
        time.sleep(DELAY)
    return docs

if __name__ == "__main__":
    all_docs = []
    for n, cfg in SITES.items():
        all_docs += crawl(n, cfg)
    for n, base in WP_BLOGS.items():
        all_docs += wp_posts(n, base)
    with open("data/corpus.jsonl", "w", encoding="utf-8") as f:
        for d in all_docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    by = {}
    for d in all_docs:
        by[d["source"]] = by.get(d["source"], 0) + 1
    print(f"Saved {len(all_docs)} chunks to data/corpus.jsonl  {by}")
