#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import random
import re
import sys
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Tegucigalpa")
NOW = datetime.now(TZ)
MAX_AGE = timedelta(hours=48)
INDEX = Path("index.html")

SOURCES = [
    {"name": "La Tribuna", "home": "https://www.latribuna.hn/"},
    {"name": "Diario Tiempo", "home": "https://tiempo.hn/"},
    {"name": "Radio HRN", "home": "https://www.radiohrn.hn/"},
    {"name": "HCH", "home": "https://hch.tv/"},
    {"name": "TuNota", "home": "https://www.tunota.com/"},
    {"name": "Proceso Digital", "home": "https://proceso.hn/"},
    {"name": "La Prensa", "home": "https://www.laprensa.hn/"},
    {"name": "El Heraldo", "home": "https://www.elheraldo.hn/"},
    {"name": "Once Noticias", "home": "https://oncenoticias.hn/"},
    {"name": "Diez", "home": "https://www.diez.hn/"},
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "Chrome/124.0 Safari/537.36 RadarActualidad/1.0"
    ),
    "Accept-Language": "es-HN,es;q=0.9,en;q=0.5",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

BAD_WORDS = {
    "viral", "tiktok", "instagram", "farándula", "farandula", "horóscopo",
    "horoscopo", "receta", "curiosidad", "entretenimiento", "celebridad",
    "influencer", "insólito", "insolito", "meme", "moda", "belleza",
}

HIGH_IMPACT = {
    "presidente": 5, "gobierno": 3, "congreso": 5, "diputado": 2,
    "corte suprema": 5, "ministerio público": 5, "ministerio publico": 5,
    "fiscal": 4, "sentencia": 4, "ley": 4, "reforma": 4, "presupuesto": 4,
    "inflación": 5, "inflacion": 5, "bch": 5, "economía": 4, "economia": 4,
    "desempleo": 5, "pobreza": 5, "combustible": 4, "energía": 4, "energia": 4,
    "enee": 4, "apagón": 4, "apagon": 4, "exportación": 4, "exportacion": 4,
    "salud": 4, "hospital": 4, "médico": 4, "medico": 4, "educación": 4,
    "educacion": 4, "unah": 4, "seguridad": 4, "homicidio": 4, "narcotráfico": 5,
    "narcotrafico": 5, "pandilla": 4, "policía": 3, "policia": 3,
    "copeco": 4, "alerta": 3, "lluvia": 2, "huracán": 5, "huracan": 5,
    "migración": 4, "migracion": 4, "empleo": 4, "onu": 4, "ee. uu.": 3,
    "estados unidos": 3, "china": 3, "españa": 3, "espana": 3,
    "selección": 3, "seleccion": 3, "mundial": 4, "concacaf": 3,
}

CATEGORY_RULES = {
    "Economía": [
        "inflación", "inflacion", "economía", "economia", "bch", "precio",
        "combustible", "empleo", "desempleo", "pobreza", "export", "import",
        "crédito", "credito", "impuesto", "presupuesto", "mipyme", "energía", "energia",
    ],
    "Seguridad y justicia": [
        "seguridad", "policía", "policia", "homicidio", "asesin", "pandilla",
        "narcotráfico", "narcotrafico", "ministerio público", "ministerio publico",
        "fiscal", "corte", "juez", "justicia", "captur", "terroris",
    ],
    "Política y gobierno": [
        "presidente", "gobierno", "congreso", "diput", "ley", "reforma",
        "gabinete", "ministro", "política", "politica", "elección", "eleccion",
    ],
    "Salud": ["salud", "hospital", "médico", "medico", "enfermer", "vacuna", "dengue"],
    "Educación": ["educación", "educacion", "escuela", "colegio", "unah", "docente", "estudiante"],
    "Ambiente y clima": ["copeco", "lluvia", "clima", "alerta", "río", "rio", "huracán", "huracan", "sequía", "sequia"],
    "Empleo y migración": ["migración", "migracion", "migrante", "deportación", "deportacion", "trabajo temporal", "empleo en españa", "empleo en espana"],
    "Internacional": ["onu", "estados unidos", "ee. uu.", "china", "europa", "guerra", "cumbre", "internacional"],
    "Deportes": ["selección", "seleccion", "fútbol", "futbol", "concacaf", "mundial", "liga nacional", "olimpia", "motagua"],
}

QUIZ_TEMPLATES = {
    "Economía": [
        (
            "¿Qué dato, medida o proyección económica es central en esta noticia y qué diferencia debe hacerse entre una cifra observada, una estimación y una propuesta?",
            "La respuesta debe identificar con precisión el dato o medida descrito en la noticia y aclarar si ya ocurrió, si es una proyección o si todavía depende de aprobación o ejecución."
        ),
        (
            "¿Qué grupos o sectores podrían verse afectados por este hecho económico y qué dato adicional necesitarías para medir su impacto real?",
            "Debe relacionarse el hecho con hogares, empresas, trabajadores o sectores productivos y mencionar indicadores adicionales útiles para comprobar el alcance del impacto."
        ),
    ],
    "Seguridad y justicia": [
        (
            "¿Qué institución actúa en esta noticia y qué debe comprobar un periodista antes de presentar la medida como un resultado efectivo de seguridad o justicia?",
            "Debe distinguirse entre anuncio, investigación, acusación, reforma o sentencia, y verificarse qué resultados concretos existen además de la declaración institucional."
        ),
        (
            "¿Qué diferencia existe entre la decisión o acusación descrita y una sentencia definitiva, y por qué esa diferencia es importante en una cobertura periodística?",
            "Porque una acusación, investigación o decisión administrativa no equivale automáticamente a culpabilidad o sentencia firme; la cobertura debe respetar el estado procesal."
        ),
    ],
    "Política y gobierno": [
        (
            "¿La noticia describe una propuesta, una decisión ya vigente o una declaración política? Explica por qué esa distinción cambia la manera de titularla.",
            "La respuesta debe identificar el estado real de la medida y evitar presentar como hecho consumado algo que todavía está en discusión, trámite o anuncio."
        ),
        (
            "¿Qué institución tiene la competencia principal sobre este tema y qué otra fuente debería consultarse para contrastar la versión oficial?",
            "Debe identificarse la autoridad competente y proponer una fuente independiente, técnica, jurídica, social o de oposición según el tema."
        ),
    ],
    "Salud": [
        (
            "¿Qué población resulta más afectada por este hecho y qué indicadores permitirían medir si el problema es aislado o forma parte de una crisis más amplia?",
            "La respuesta debe mencionar población afectada y datos como atenciones, tiempos de espera, abastecimiento, cobertura, mortalidad o suspensión de servicios."
        ),
    ],
    "Educación": [
        (
            "¿Qué norma, política educativa o derecho debería contrastarse con la propuesta o situación descrita para explicar el tema con equilibrio?",
            "Debe buscarse el marco legal o institucional aplicable y contrastarse con autoridades educativas, docentes, estudiantes, familias o especialistas."
        ),
    ],
    "Ambiente y clima": [
        (
            "¿Qué zonas y riesgos concretos aparecen en la noticia y por qué un pronóstico o alerta debe presentarse con fecha y vigencia exactas?",
            "Porque las condiciones meteorológicas cambian; se deben indicar territorio, nivel de alerta, período de vigencia y la institución que emite la información."
        ),
    ],
    "Empleo y migración": [
        (
            "¿La oportunidad descrita representa empleo permanente, temporal o una expectativa de contratación? ¿Qué requisitos deben verificarse antes de presentarla como una plaza disponible?",
            "Debe explicarse la modalidad real de contratación, requisitos, selección, duración, condiciones legales y si se trata de plazas confirmadas o previstas."
        ),
    ],
    "Internacional": [
        (
            "¿Cuál es la conexión concreta de este hecho internacional con Honduras y qué parte de la noticia tiene impacto directo para el país?",
            "Debe identificarse el vínculo verificable con Honduras y separarlo del contexto internacional general."
        ),
    ],
    "Deportes": [
        (
            "¿Qué competición, rival o resultado hace que esta noticia deportiva tenga relevancia nacional y qué dato de contexto necesita el lector para entender su importancia?",
            "Debe identificarse la competencia y explicar qué está en juego: clasificación, debut, título, eliminatoria o repercusión para la selección o el deporte hondureño."
        ),
    ],
}

STOPWORDS = {
    "de","la","el","los","las","un","una","unos","unas","y","o","en","a","por","para",
    "con","del","al","que","se","su","sus","es","son","como","más","mas","tras","ante",
    "honduras","hondureño","hondureno","hondureña","hondurena","hoy",
}

def clean_text(s: str | None) -> str:
    if not s:
        return ""
    s = BeautifulSoup(str(s), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", s).strip()

def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def same_domain(a: str, b: str) -> bool:
    ha = urlparse(a).netloc.lower().removeprefix("www.")
    hb = urlparse(b).netloc.lower().removeprefix("www.")
    return ha == hb

def fetch(url: str, timeout: int = 18) -> requests.Response | None:
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
            return r
    except Exception:
        pass
    return None

def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = dateparser.parse(value)
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    except Exception:
        return None

def date_from_url(url: str) -> datetime | None:
    m = re.search(r"/(20\d{2})[/\-](\d{1,2})[/\-](\d{1,2})(?:/|$)", url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 12, 0, tzinfo=TZ)
    except Exception:
        return None

def jsonld_dates(soup: BeautifulSoup) -> list[str]:
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in {"datePublished", "dateCreated", "uploadDate"} and isinstance(v, str):
                        out.append(v)
                    else:
                        walk(v)
            elif isinstance(obj, list):
                for x in obj:
                    walk(x)
        walk(data)
    return out

def find_meta(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    return ""

def infer_category(title: str, desc: str, section: str = "") -> str:
    hay = normalize(" ".join([title, desc, section]))
    best_cat, best_score = "Política y gobierno", 0
    for cat, words in CATEGORY_RULES.items():
        score = sum(2 if normalize(w) in hay else 0 for w in words)
        if score > best_score:
            best_cat, best_score = cat, score
    return best_cat

def importance(title: str, desc: str, cat: str) -> float:
    hay = normalize(title + " " + desc)
    score = 0.0
    for phrase, weight in HIGH_IMPACT.items():
        if normalize(phrase) in hay:
            score += weight
    for bad in BAD_WORDS:
        if normalize(bad) in hay:
            score -= 12
    if re.search(r"\b\d+(?:[.,]\d+)?\s*%|\bL\s?\d|\b\d{3,}\b", title + " " + desc, re.I):
        score += 2
    if cat in {"Economía","Seguridad y justicia","Política y gobierno","Salud","Educación"}:
        score += 2
    if cat == "Deportes" and not any(x in hay for x in ["seleccion","mundial","concacaf"]):
        score -= 3
    return score

def discover_candidates(source: dict) -> list[tuple[str, str, datetime | None]]:
    home = source["home"]
    r = fetch(home)
    if not r:
        print(f"[aviso] No se pudo abrir {source['name']}: {home}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    candidates = []
    seen = set()

    # RSS/Atom descubierto en la portada
    feeds = []
    for link in soup.find_all("link"):
        typ = (link.get("type") or "").lower()
        rel = " ".join(link.get("rel") or []).lower()
        if ("rss" in typ or "atom" in typ or "alternate" in rel) and link.get("href"):
            if "rss" in typ or "atom" in typ:
                feeds.append(urljoin(home, link["href"]))

    for feed_url in feeds[:2]:
        try:
            feed = feedparser.parse(feed_url)
            for e in feed.entries[:20]:
                url = e.get("link")
                if not url or not same_domain(home, url):
                    continue
                title = clean_text(e.get("title", ""))
                hint = parse_datetime(e.get("published") or e.get("updated"))
                if url not in seen:
                    candidates.append((url, title, hint))
                    seen.add(url)
        except Exception:
            pass

    # Enlaces de la portada
    for a in soup.find_all("a", href=True):
        url = urljoin(home, a["href"]).split("#")[0]
        if not same_domain(home, url):
            continue
        path = urlparse(url).path.lower()
        if len(path.strip("/")) < 12:
            continue
        if re.search(r"\.(jpg|jpeg|png|webp|gif|svg|pdf|mp4)(?:$|\?)", path):
            continue
        if any(x in path for x in ["/tag/", "/autor/", "/author/", "/categoria/", "/category/", "/contact", "/politica-de-privacidad"]):
            continue
        title = clean_text(a.get_text(" ", strip=True))
        if len(title) < 22:
            continue
        if url not in seen:
            candidates.append((url, title, None))
            seen.add(url)

    return candidates[:28]

def parse_article(url: str, source: str, hint_title: str = "", hint_date: datetime | None = None) -> dict | None:
    r = fetch(url)
    if not r:
        return None
    final_url = r.url.split("#")[0]
    soup = BeautifulSoup(r.text, "html.parser")

    title = find_meta(soup, "og:title", "twitter:title")
    if not title:
        h1 = soup.find("h1")
        title = clean_text(h1.get_text(" ", strip=True)) if h1 else clean_text(hint_title)
    title = re.sub(r"\s*[|\-–—]\s*(La Prensa|El Heraldo|HCH|HRN|TuNota|Proceso Digital|Diario Tiempo).*$", "", title, flags=re.I)
    if len(title) < 15:
        return None

    desc = find_meta(soup, "og:description", "twitter:description", "description")
    if len(desc) < 35:
        p = soup.find("p")
        desc = clean_text(p.get_text(" ", strip=True)) if p else desc
    desc = desc[:560].strip()

    image = find_meta(soup, "og:image", "twitter:image")
    if image:
        image = urljoin(final_url, image)

    section = find_meta(soup, "article:section")

    raw_dates = [
        find_meta(soup, "article:published_time", "datePublished", "pubdate", "publishdate"),
        *jsonld_dates(soup),
    ]
    for t in soup.find_all("time", datetime=True):
        raw_dates.append(t.get("datetime"))

    published = None
    for raw in raw_dates:
        published = parse_datetime(raw)
        if published:
            break
    published = published or hint_date or date_from_url(final_url)
    if not published:
        return None

    age = NOW - published
    if age < timedelta(hours=-6) or age > MAX_AGE:
        return None

    cat = infer_category(title, desc, section)
    score = importance(title, desc, cat)

    # Evita notas claramente ligeras.
    if score < 0:
        return None

    keys = []
    numbers = re.findall(r"(?:L\s*)?\d+(?:[.,]\d+)?\s*%?|\b20\d{2}\b", title + " " + desc)
    if numbers:
        keys.append("Dato a recordar: " + ", ".join(dict.fromkeys(numbers[:3])))
    keys.append("Tema: " + cat)
    keys.append("Medio: " + source)

    return {
        "title": title,
        "url": final_url,
        "source": source,
        "publishedAt": published.isoformat(),
        "dateLabel": published.strftime("%d %b · %I:%M %p").replace("AM","a. m.").replace("PM","p. m."),
        "category": cat,
        "summary": desc or "Consulta la fuente original para ampliar el contexto de esta noticia.",
        "keys": keys[:3],
        "image": image or None,
        "featured": False,
        "_score": score,
    }

def title_tokens(title: str) -> set[str]:
    return {x for x in normalize(title).split() if len(x) > 3 and x not in STOPWORDS}

def is_duplicate(a: dict, b: dict) -> bool:
    ta, tb = normalize(a["title"]), normalize(b["title"])
    ratio = SequenceMatcher(None, ta, tb).ratio()
    sa, sb = title_tokens(a["title"]), title_tokens(b["title"])
    jac = len(sa & sb) / max(1, len(sa | sb))
    return ratio >= 0.70 or jac >= 0.48

def choose_articles(items: list[dict], limit: int = 16) -> list[dict]:
    items = sorted(items, key=lambda x: (x["_score"], x["publishedAt"]), reverse=True)
    selected = []
    per_source = defaultdict(int)
    per_cat = defaultdict(int)

    for item in items:
        if any(is_duplicate(item, prev) for prev in selected):
            continue
        if per_source[item["source"]] >= 3:
            continue
        if per_cat[item["category"]] >= 4:
            continue
        selected.append(item)
        per_source[item["source"]] += 1
        per_cat[item["category"]] += 1
        if len(selected) >= limit:
            break

    # Segunda pasada para completar si las restricciones dejaron muy pocos.
    if len(selected) < 10:
        for item in items:
            if item in selected or any(is_duplicate(item, prev) for prev in selected):
                continue
            if per_source[item["source"]] >= 4:
                continue
            selected.append(item)
            per_source[item["source"]] += 1
            if len(selected) >= limit:
                break

    if selected:
        selected[0]["featured"] = True
    for x in selected:
        x.pop("_score", None)
    return selected

def build_quiz(articles: list[dict]) -> list[dict]:
    seed = int(NOW.strftime("%Y%m%d"))
    rng = random.Random(seed)

    pool = articles[:]
    rng.shuffle(pool)
    picked = []
    used_sources, used_cats = set(), set()

    # Primero busca diversidad de fuente y categoría.
    for a in pool:
        if a["source"] in used_sources or a["category"] in used_cats:
            continue
        picked.append(a)
        used_sources.add(a["source"])
        used_cats.add(a["category"])
        if len(picked) == 5:
            break

    for a in pool:
        if len(picked) == 5:
            break
        if a not in picked and a["source"] not in used_sources:
            picked.append(a)
            used_sources.add(a["source"])

    for a in pool:
        if len(picked) == 5:
            break
        if a not in picked:
            picked.append(a)

    quiz = []
    for i, a in enumerate(picked[:5], 1):
        templates = QUIZ_TEMPLATES.get(a["category"]) or QUIZ_TEMPLATES["Política y gobierno"]
        q, guidance = templates[(seed + i) % len(templates)]
        answer = (
            f"Noticia base: «{a['title']}». {guidance} "
            f"Contexto disponible en la síntesis: {a['summary']}"
        )
        quiz.append({
            "n": i,
            "type": f"{a['category']} · {a['source']}",
            "q": q + f" Toma como caso: «{a['title']}».",
            "a": answer,
            "url": a["url"],
            "source": a["source"],
        })
    return quiz

def update_index(articles: list[dict], quiz: list[dict]) -> None:
    if not INDEX.exists():
        raise SystemExit("No existe index.html en la raíz del repositorio.")

    text = INDEX.read_text(encoding="utf-8")

    # Serialización segura para incrustar JSON dentro de una etiqueta <script>.
    # Escapamos caracteres que podrían cerrar accidentalmente la etiqueta o
    # introducir saltos interpretados por JavaScript.
    a_json = json.dumps(articles, ensure_ascii=False, separators=(",", ":"))
    q_json = json.dumps(quiz, ensure_ascii=False, separators=(",", ":"))
    a_json = a_json.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    q_json = q_json.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    replacement = f"const ARTICLES = {a_json};\\nconst QUIZ = {q_json};"

    # IMPORTANTE: usar una función como reemplazo evita que re.sub interprete
    # secuencias con barra invertida procedentes del JSON (por ejemplo \\n).
    text, n1 = re.subn(
        r"const ARTICLES\s*=\s*.*?;\s*const QUIZ\s*=\s*.*?;",
        lambda _m: replacement,
        text,
        count=1,
        flags=re.S,
    )
    if n1 != 1:
        raise SystemExit("No encontré los bloques const ARTICLES / const QUIZ en index.html.")

    months = [
        "enero","febrero","marzo","abril","mayo","junio",
        "julio","agosto","septiembre","octubre","noviembre","diciembre"
    ]
    edition = f"{NOW.day} de {months[NOW.month-1]} de {NOW.year}"
    text = re.sub(
        r"(Radar de Actualidad · Edición del )[^<]+",
        rf"\g<1>{edition}",
        text,
        count=1,
    )

    # Comprobaciones estructurales antes de sobrescribir el archivo.
    required_fragments = [
        "const ARTICLES = ",
        "const QUIZ = ",
        'id="newsGrid"',
        'id="quizGrid"',
        "drawCards();",
        "drawQuiz();",
    ]
    missing = [x for x in required_fragments if x not in text]
    if missing:
        raise SystemExit("HTML generado incompleto. Faltan: " + ", ".join(missing))

    INDEX.write_text(text, encoding="utf-8")

def main():
    all_items = []
    print(f"Actualizando Radar de Actualidad: {NOW.isoformat()}")

    for source in SOURCES:
        print(f"\n== {source['name']} ==")
        candidates = discover_candidates(source)
        print(f"Candidatos descubiertos: {len(candidates)}")
        parsed = 0

        for url, hint_title, hint_date in candidates[:18]:
            item = parse_article(url, source["name"], hint_title, hint_date)
            if item:
                all_items.append(item)
                parsed += 1
            time.sleep(0.18)
        print(f"Noticias válidas <48 h: {parsed}")

    articles = choose_articles(all_items, 16)

    # Si el scraping falla de forma general, aborta: GitHub conservará el despliegue anterior.
    if len(articles) < 5:
        raise SystemExit(
            f"Solo se encontraron {len(articles)} noticias válidas. "
            "Se aborta el despliegue para no reemplazar la página por una edición incompleta."
        )

    quiz = build_quiz(articles)
    update_index(articles, quiz)

    print(f"\nEdición generada: {len(articles)} noticias y {len(quiz)} preguntas.")
    for a in articles:
        print(f"- [{a['source']}] {a['title']}")

if __name__ == "__main__":
    main()
