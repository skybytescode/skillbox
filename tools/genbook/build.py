#!/usr/bin/env python3
"""Generate docs/os-book/{content,quiz}.json + docs/assets/os-book/images from the
source PDF textbook. This is a one-time/occasional build step, not part of the Go
build. Requires poppler-utils (pdftotext, pdfimages) on PATH.

Usage: python3 tools/genbook/build.py
"""
import html
import json
import re
import subprocess
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "96308419-Introducere-in-Sisteme-de-Operare.pdf"
OUT_DIR = ROOT / "docs" / "os-book"
IMG_DIR = ROOT / "docs" / "assets" / "os-book" / "images"

BOOK_TITLE = "Introducere în Sisteme de Operare"

# ---------------------------------------------------------------------------
# Diacritic repair
#
# This PDF's ș/ț glyphs (s-comma, t-comma) are missing from its ToUnicode map,
# so pdftotext renders them as a bare letter + ", " (e.g. "și" -> "s, i").
# The fix is mechanical EXCEPT for real complete words that happen to end in
# a bare "s"/"t" right before a genuine comma (e.g. "Windows, Mac", "sunt,
# pentru", "clienți" vs "client, i"). These sets were built by inspecting
# every distinct word this pattern matches across the whole book and checking
# real context for the ambiguous ones (see conversation notes) -- anything not
# in these sets is treated as mangled and merged.
KEEP_S = {
    "windows", "emacs", "multics", "opensolaris", "solaris", "parallels",
    "torvalds", "robbins", "business", "techniques", "principles",
    "autotools", "darcs", "xargs", "ctags", "procfs", "sysfs", "sshfs",
    "ncurses", "smartmontools", "devfs", "cplusplus", "cmdlets", "ifss",
    "whereis", "apropos", "ls", "jobs", "users", "drivers", "dns", "hosts",
    "headers", "files", "blocks", "modules", "changes", "interfaces",
    "technologies", "days", "months", "seconds", "standards", "strings",
    "secrets", "status", "tags", "kbytes", "computers", "games", "fires",
    "exits", "gratis", "less", "labs", "loss", "lsass", "bss", "cttds",
    "creates", "cookies", "containers", "archives", "settings", "press",
    "this", "sons", "acces", "succes", "plus", "proces", "spus",
    "sus", "fals",
}
KEEP_T = {
    "microsoft", "internet", "ethernet", "usenet", "telnet", "unicast",
    "multicast", "git", "wget", "chroot", "checkout", "chipset", "redhat",
    "mint", "socket", "script", "toolkit", "timeout", "output", "logout",
    "host", "guest", "quit", "reset", "insert", "export", "environment",
    "list", "exit", "test", "text", "txt", "cat", "last", "root", "commit",
    "cut", "dhclient", "xinit", "svchost", "webroot", "vsplit", "umount",
    "ulimit", "splint", "prompt", "print", "object", "aeroport", "boot",
    "shift", "context", "conflict", "contrast", "agent", "element",
    "argument", "moment", "document", "pachet", "garant", "suport",
    "proiect", "sat", "target", "slashdot", "sunt", "adevarat",
    "adevărat", "implicit", "neautorizat", "necriptat",
}

WORD_S_RE = re.compile(r"([A-Za-zĂÂÎȘȚăâîșț]*[sS]), ")
WORD_T_RE = re.compile(r"([A-Za-zĂÂÎȘȚăâîșț]*[tT]), ")

# Some roots are genuinely ambiguous: "existent," is a real word (adjective,
# "existing") most of the time, but "existent, a/ei/ă" is the mangled noun
# "existența/existenței" (existence). Rather than a static keep/merge
# decision, look at what immediately follows to disambiguate.
AMBIGUOUS_T = {
    "existent": ("a", "ei", "ă", "e "),
}
AMBIGUOUS_S = {}


def _make_repl(keep_set, ambiguous, lower_target, upper_target):
    def _repl(m):
        word = m.group(1)
        wl = word.lower()
        if wl in keep_set:
            return word + ", "
        if wl in ambiguous:
            tail = m.string[m.end():m.end() + 4].lower()
            if not any(tail.startswith(suf) for suf in ambiguous[wl]):
                return word + ", "
        last = word[-1]
        new_last = upper_target if last.isupper() else lower_target
        return word[:-1] + new_last
    return _repl


def repair_diacritics(text: str) -> str:
    # Join words split across a line wrap first: "profesionis,\ntilor" -> "profesionis, tilor"
    text = re.sub(r"([sStT]),[ \t]*\n[ \t]*", r"\1, ", text)
    text = WORD_S_RE.sub(_make_repl(KEEP_S, AMBIGUOUS_S, "ș", "Ș"), text)
    text = WORD_T_RE.sub(_make_repl(KEEP_T, AMBIGUOUS_T, "ț", "Ț"), text)
    return text


# ---------------------------------------------------------------------------
# Extraction

def run(cmd):
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def extract_pages():
    """Returns list of page texts (1-indexed via list[0] == page 1), diacritics-repaired."""
    raw = run(["pdftotext", "-layout", str(PDF), "-"]).decode("utf-8", "replace")
    # pdftotext emits decomposed Unicode (e.g. "ă" as "a" + combining breve);
    # normalize to composed form so downstream regexes (which use precomposed
    # literals) actually match.
    raw = unicodedata.normalize("NFC", raw)
    pages = raw.split("\f")
    if pages and pages[-1].strip() == "":
        pages.pop()
    return [repair_diacritics(p) for p in pages]


HEADER_FOOTER_RES = [
    re.compile(r"^\s*\d+\s*$"),
    re.compile(r"^\s*[ivxlcdm]+\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d*\s*CAPITOLUL\s+\d+\.?.*$"),
    re.compile(r"^\s*\d*\s*ANEXA\s+[A-Z]\..*$"),
    re.compile(r"^\s*\d*\s*INTRODUCERE ÎN SISTEME DE OPERARE\s*$"),
    re.compile(r"^\s*\d*\s*CUPRINS\s*\d*$"),
    re.compile(r"^\s*\d*\s*GLOSAR\s*$"),
    re.compile(r"^\s*\d*\s*BIBLIOGRAFIE\s*$"),
    re.compile(r"^\s*\d*\s*https?://\S+\s*$"),  # bare footnote URL lines
]


def clean_page_lines(page_text):
    lines = page_text.split("\n")
    out = []
    for ln in lines:
        if any(r.match(ln) for r in HEADER_FOOTER_RES):
            continue
        out.append(ln)
    return out


def build_line_stream(pages):
    """Flatten to a list of (page_num, line) tuples with headers/footers stripped."""
    stream = []
    for i, page in enumerate(pages, start=1):
        for ln in clean_page_lines(page):
            stream.append((i, ln))
    return stream


# ---------------------------------------------------------------------------
# HTML rendering of a raw line block (a chapter/section body)

CODE_LINE_RE = re.compile(r"^\s*\d+\s{1,4}(\S.*)$")
BULLET_RE = re.compile(r"^\s*[••]\s*(.*)$")
HEADING_RE = re.compile(r"^(\d+\.\d+(?:\.\d+)?)\s{2,}(.+?)\s*$")
CHAPTER_START_RE = re.compile(r"^Capitolul\s+(\d+)\s*$")


def esc(s):
    return html.escape(s, quote=False)


def render_text_or_bullets(lines):
    """Render a run of non-code lines: either a bullet list or a plain paragraph."""
    if not lines:
        return ""
    if all(BULLET_RE.match(l) or not l.strip() for l in lines if l.strip()):
        items = []
        cur = None
        for l in lines:
            m = BULLET_RE.match(l)
            if m:
                if cur is not None:
                    items.append(cur)
                cur = m.group(1).strip()
            elif cur is not None:
                cur += " " + l.strip()
        if cur is not None:
            items.append(cur)
        return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"

    text = " ".join(l.strip() for l in lines if l.strip())
    text = re.sub(r"\s{2,}", " ", text)
    if not text:
        return ""
    return f"<p>{esc(text)}</p>"


def render_block_lines(lines):
    """Render a list of raw (non-empty) lines belonging to one paragraph/list/code
    block into an HTML fragment. A numbered terminal-transcript run is pulled out
    as a <pre><code> block wherever it appears, even mid-paragraph (a sentence
    ending in ':' immediately followed by a command listing, with no blank PDF
    line between them, is common in this book)."""
    parts = []
    text_buf = []

    def flush_text():
        if text_buf:
            parts.append(render_text_or_bullets(text_buf))
            text_buf.clear()

    i = 0
    n = len(lines)
    while i < n:
        if CODE_LINE_RE.match(lines[i]):
            j = i
            code_run = []
            while j < n and CODE_LINE_RE.match(lines[j]):
                code_run.append(CODE_LINE_RE.match(lines[j]).group(1).rstrip())
                j += 1
            flush_text()
            parts.append("<pre><code>" + esc("\n".join(code_run)) + "</code></pre>")
            i = j
        else:
            text_buf.append(lines[i])
            i += 1
    flush_text()
    return "".join(parts)


def lines_to_html(lines):
    """Split raw lines on blank-line boundaries into blocks and render each."""
    blocks = []
    cur = []
    for l in lines:
        if l.strip() == "":
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(l)
    if cur:
        blocks.append(cur)
    return "".join(render_block_lines(b) for b in blocks if b)


# ---------------------------------------------------------------------------
# Chapter splitting

def find_chapter_starts(stream):
    """Locate indices in `stream` where a body chapter begins (Capitolul N, then
    blank, then the title line), returning [(chapter_num, title, start_idx), ...]."""
    starts = []
    n = len(stream)
    i = 0
    while i < n:
        _, ln = stream[i]
        m = CHAPTER_START_RE.match(ln.strip())
        if m:
            # find next non-blank line -> title
            j = i + 1
            while j < n and stream[j][1].strip() == "":
                j += 1
            if j < n:
                title = stream[j][1].strip()
                starts.append((int(m.group(1)), title, i))
        i += 1
    return starts


def find_marker(stream, pattern, start=0):
    for i in range(start, len(stream)):
        if re.match(pattern, stream[i][1].strip()):
            return i
    return None


# ---------------------------------------------------------------------------
# Per-chapter parsing: sections, keywords, questions

def split_sections(chapter_lines_with_pages, end_marker_res):
    """chapter_lines_with_pages: list of (page, line) for the whole chapter body
    (title through just before 'Cuvinte cheie'). Returns list of section dicts."""
    # Find heading positions
    heading_idxs = []
    for idx, (_, ln) in enumerate(chapter_lines_with_pages):
        m = HEADING_RE.match(ln.strip())
        if m:
            heading_idxs.append((idx, m.group(1), m.group(2).strip()))

    sections = []
    intro_end = heading_idxs[0][0] if heading_idxs else len(chapter_lines_with_pages)
    intro_lines = chapter_lines_with_pages[:intro_end]

    for k, (idx, num, title) in enumerate(heading_idxs):
        body_start = idx + 1
        body_end = heading_idxs[k + 1][0] if k + 1 < len(heading_idxs) else len(chapter_lines_with_pages)
        body = chapter_lines_with_pages[body_start:body_end]
        pages = sorted({p for p, _ in body}) or ([chapter_lines_with_pages[idx][0]] if chapter_lines_with_pages else [])
        html_body = lines_to_html([l for _, l in body])
        level = num.count(".") + 1
        sections.append({
            "num": num,
            "title": title,
            "level": level,
            "html": html_body,
            "pageStart": min(pages) if pages else None,
            "pageEnd": max(pages) if pages else None,
        })
    return intro_lines, sections


def parse_learn_intro(intro_lines):
    text_lines = [l for _, l in intro_lines]
    joined = "\n".join(text_lines)
    m = re.search(r"Ce se învață din acest capitol\?\s*\n((?:.|\n)*)", joined)
    if not m:
        return []
    rest = m.group(1)
    items = []
    for l in rest.split("\n"):
        bm = BULLET_RE.match(l)
        if bm:
            items.append(bm.group(1).strip())
    return items


KEYWORD_LINE_RE = re.compile(r"^\s*[••]\s*(.+?)\s{2,}[••]?\s*(.*)$")


def parse_keywords(lines):
    kws = []
    for l in lines:
        if not l.strip():
            continue
        # keyword block is two columns separated by wide whitespace, each
        # prefixed with a bullet
        parts = re.split(r"\s{2,}", l.strip())
        for p in parts:
            m = BULLET_RE.match(p)
            if m and m.group(1).strip():
                kws.append(m.group(1).strip())
    return kws


QUESTION_START_RE = re.compile(r"^\s*(\d+)\.\s+(.+)$")
OPTION_RE = re.compile(r"^\s*q\s+(.+)$")


def parse_questions(lines):
    """lines: raw lines of the 'Întrebări' section (after the heading)."""
    questions = []
    cur = None
    cur_field = None  # 'q' or 'o'
    for l in lines:
        s = l.rstrip()
        if not s.strip():
            continue
        qm = QUESTION_START_RE.match(s)
        om = OPTION_RE.match(s)
        if qm and not om:
            if cur:
                questions.append(cur)
            cur = {"num": int(qm.group(1)), "text": qm.group(2).strip(), "options": []}
            cur_field = "q"
        elif om:
            if cur is None:
                continue
            cur["options"].append(om.group(1).strip())
            cur_field = "o"
        else:
            # continuation of previous question text or option
            if cur is None:
                continue
            if cur_field == "o" and cur["options"]:
                cur["options"][-1] += " " + s.strip()
            elif cur_field == "q":
                cur["text"] += " " + s.strip()
    if cur:
        questions.append(cur)
    # drop footnote-number artifacts like trailing digits from superscript refs
    return [q for q in questions if len(q["options"]) >= 2]


ANSWER_START_RE = re.compile(r"^\s*(\d+)\.\s+(.+)$")


def parse_answers(lines):
    entries = []
    cur = None
    for l in lines:
        s = l.rstrip()
        if not s.strip():
            continue
        m = ANSWER_START_RE.match(s)
        if m:
            if cur:
                entries.append(cur)
            cur = {"num": int(m.group(1)), "text": m.group(2).strip()}
        else:
            if cur is None:
                continue
            cur["text"] += " " + s.strip()
    if cur:
        entries.append(cur)
    parsed = []
    for e in entries:
        # split on first en-dash / hyphen surrounded by spaces
        m = re.search(r"\s[–-]\s", e["text"])
        if m:
            answer = e["text"][:m.start()].strip()
            rationale = e["text"][m.end():].strip()
        else:
            answer, rationale = e["text"].strip(), ""
        parsed.append({"num": e["num"], "answer": answer, "rationale": rationale})
    return parsed


def match_answer_to_option(answer_text, options):
    best_i, best_score = -1, 0.0
    norm = lambda s: re.sub(r"[.,;:!?]+$", "", s.strip().lower())
    a = norm(answer_text)
    for i, opt in enumerate(options):
        o = norm(opt)
        score = SequenceMatcher(None, a, o).ratio()
        if a in o or o in a:
            score = max(score, 0.9)
        if score > best_score:
            best_score, best_i = score, i
    return best_i, best_score


ANEXA_RE = re.compile(r"^Anexa\s+A\s*$")
BIBLIO_RE = re.compile(r"^Bibliografie\s*$")
CUVINTE_RE = re.compile(r"^Cuvinte cheie\s*$")
INTREBARI_RE = re.compile(r"^Întrebări\s*$")


def build_chapters(stream):
    starts = find_chapter_starts(stream)
    anexa_idx = find_marker(stream, ANEXA_RE.pattern)
    end_of_book = anexa_idx if anexa_idx is not None else len(stream)

    chapters = []
    for k, (num, title, start_idx) in enumerate(starts):
        chap_end = starts[k + 1][2] if k + 1 < len(starts) else end_of_book
        body = stream[start_idx:chap_end]

        cuvinte_i = None
        intreb_i = None
        for idx, (_, ln) in enumerate(body):
            s = ln.strip()
            if cuvinte_i is None and CUVINTE_RE.match(s):
                cuvinte_i = idx
            elif intreb_i is None and INTREBARI_RE.match(s):
                intreb_i = idx
        content_end = cuvinte_i if cuvinte_i is not None else len(body)
        content_lines = body[:content_end]
        keyword_lines = body[cuvinte_i + 1:intreb_i] if cuvinte_i is not None and intreb_i is not None else []
        question_lines = body[intreb_i + 1:] if intreb_i is not None else []

        chapters.append({
            "num": num,
            "start_idx": start_idx,
            "title": title,
            "content_lines": content_lines,
            "keyword_lines": [l for _, l in keyword_lines],
            "question_lines": [l for _, l in question_lines],
        })
    return chapters, anexa_idx, stream


def parse_bibliography(stream, anexa_idx):
    biblio_idx = find_marker(stream, BIBLIO_RE.pattern, start=anexa_idx or 0)
    if biblio_idx is None:
        return []
    lines = [l for _, l in stream[biblio_idx + 1:]]
    # entries are typically bracketed refs like "[1] Author, Title, ..."
    entries = []
    cur = None
    for l in lines:
        s = l.strip()
        if not s:
            continue
        if re.match(r"^\[\d+\]", s):
            if cur:
                entries.append(cur)
            cur = s
        elif cur is not None:
            cur += " " + s
    if cur:
        entries.append(cur)
    return entries


def parse_answers_appendix(stream, anexa_idx):
    """Returns {chapter_num: [{num, answer, rationale}, ...]}"""
    if anexa_idx is None:
        return {}
    biblio_idx = find_marker(stream, BIBLIO_RE.pattern, start=anexa_idx)
    end = biblio_idx if biblio_idx is not None else len(stream)
    lines_with_pages = stream[anexa_idx:end]

    chap_hdr_re = re.compile(r"^Capitolul\s+(\d+)\.")
    chap_positions = []
    for idx, (_, ln) in enumerate(lines_with_pages):
        m = chap_hdr_re.match(ln.strip())
        if m:
            chap_positions.append((int(m.group(1)), idx))

    result = {}
    for k, (cnum, idx) in enumerate(chap_positions):
        end_idx = chap_positions[k + 1][1] if k + 1 < len(chap_positions) else len(lines_with_pages)
        body = [l for _, l in lines_with_pages[idx + 1:end_idx]]
        result[cnum] = parse_answers(body)
    return result


# The foreword is set in italic type in the source PDF, and pdftotext drops
# "ă" and "fi"-ligatures wholesale in that font (confirmed via grep to be
# isolated to these 2 pages -- the other 547 pages extract cleanly). Rather
# than leave it mangled, this is a verified-by-hand transcription of the
# actual foreword text.
FOREWORD_HTML = (
    "<p>Noțiunea de sistem de operare reprezintă, probabil, unul dintre termenii cei mai "
    "des întâlniți în domeniul calculatoarelor, și nu numai. De la formele greoaie "
    "dezvoltate în anii '60, cunoscute doar profesioniștilor, sistemele de operare au "
    "cunoscut o transformare continuă, strâns corelată cu dezvoltarea sistemelor de "
    "calcul și a tehnologiilor asociate. În ziua de astăzi, sistemele de operare oferă o "
    "interfață facilă și prietenoasă atât utilizatorilor obișnuiți ai serviciilor "
    "Internet, cât și utilizatorilor comerciali ai aplicațiilor dedicate, celor ce "
    "folosesc facilitățile multimedia și jocuri, sau celor profesioniști care dezvoltă "
    "aplicații sau întrețin sisteme de calcul și rețele de calculatoare. Evoluția "
    "tehnologică a dus la dezvoltarea sistemelor de operare pentru un număr tot mai mare "
    "de dispozitive, de la sisteme server, desktop și laptop la PDA-uri și "
    "smartphone-uri.</p>"
    "<p>Cartea de față își propune familiarizarea cititorului cu lumea sistemelor de "
    "operare și, în particular, cu latura preponderent tehnică a acestora. Am creat "
    "această lucrare având în permanență în vedere cunoștințele de bază și cadrul "
    "conceptual necesare unui student la o facultate de calculatoare. În această "
    "structură, cartea este însă construită pentru a fi utilă oricărui cititor care "
    "caută un prim contact cu domeniul sistemelor de operare. Sperăm ca parcurgerea sa "
    "să ofere și un set de deprinderi și abordări în soluționarea problemelor care "
    "depășesc sfera sistemelor de operare.</p>"
    "<p>Diversitatea subiectelor abordate a reprezentat o dificultate în crearea unei "
    "succesiuni clare de capitole. Strategia aleasă este una stratificată, fiecare "
    "capitol bazându-se pe cele studiate anterior. Totuși, au existat momente în care a "
    "trebuit să utilizăm anumite noțiuni înainte de a fi definit cadrul conceptual, sau "
    "la câteva capitole distanță de prezentarea lor. În astfel de situații cititorului îi "
    "sunt oferite referințe către capitolele în care sunt clarificate noțiunile "
    "invocate.</p>"
    "<p>Cartea urmărește prezentarea și discutarea noțiunilor de bază necesare unui "
    "student în primii ani de facultate, în domeniul calculatoarelor. Diversitatea "
    "subiectelor și nivelul de detaliu recomandă o asimilare în profunzime a "
    "informațiilor, dincolo de durata unui semestru sau a unui an. Sperăm ca studentul "
    "dornic de aprofundare să răsfoiască această carte în momentele în care caută "
    "sprijin suplimentar pentru rezolvarea unei probleme din domeniu.</p>"
    "<p>Din punct de vedere tehnic, materialul de față oferă o perspectivă ce aparține "
    "preponderent universului Linux. Am considerat contactul cu Linux ca pe o "
    "oportunitate aparte pentru o majoritate a utilizatorilor ce provin din mediul "
    "Windows, în care deseori alternativele în domeniul sistemelor de operare nu "
    "reprezintă o opțiune luată în considerare. Dorința noastră este ca utilizarea unui "
    "nou sistem de operare, cu o răspândire și o evoluție tot mai intense, să ofere o "
    "nouă perspectivă asupra lumii calculatoarelor în general și a sistemelor de operare "
    "în particular. Deși cartea este focalizată pe Linux, fiecare capitol include "
    "secțiuni de studii de caz în care sunt prezentate mecanismele similare dintr-un "
    "sistem Windows.</p>"
    "<p>Structura cărții este concepută pentru a oferi atât o prezentare a cadrului "
    "conceptual, cât și o parte aplicativă construită prin exemple. Fiecare capitol este "
    "prefațat de o mică secțiune „Ce se învață în acest capitol?”, utilă pentru "
    "reperarea principalelor noțiuni. Capitolele se încheie cu o secțiune de „Cuvinte "
    "cheie” și apoi de „Întrebări”, pentru a permite cititorului o autoevaluare a "
    "cunoștințelor dobândite. Unele secțiuni sunt marcate cu simboluri grafice cu o "
    "semnificație specială: important, notă, OZN (pentru tehnologiile recente de tipul "
    "„bleeding edge”) și atom (pentru aspecte tehnice avansate).</p>"
    "<p>Recomandăm parcurgerea secvențială a cărții, dar cititorul avansat poate sări "
    "direct la un capitol de interes particular. Dat fiind conținutul practic detaliat, "
    "este utilă folosirea calculatorului pentru rularea comenzilor prezentate și pentru "
    "explorarea opțiunilor existente, în paralel cu parcurgerea noțiunilor teoretice.</p>"
    "<p>Mulțumim tuturor celor care au contribuit la realizarea cărții. Modul de "
    "organizare și prezentare, ca și diversitatea informațiilor prezentate se bazează pe "
    "efortul continuu și pasiunea unei echipe entuziaste. În primul rând, îi mulțumim "
    "domnului profesor Nicolae Țăpuș, precum și colegilor noștri Vlad Dogaru, Mihai "
    "Maruseac, Daniel Rosner și Andrei Buhaiu, a căror implicare a constituit un "
    "beneficiu direct în elaborarea acestei cărți. Mulțumim, de asemenea, colegilor Alex "
    "Eftimie și Andrei Faur pentru contribuția adusă, și colegilor Alex Juncu, Lucian "
    "Grijincu, Călin Iorgulescu, Voichița Iancu, Andrei Dumitru, Laura Gheorghe pentru "
    "revizuirea materialului pe parcursul finalizării acestuia.</p>"
    "<p>Adresăm mulțumiri speciale echipei cursului de Utilizarea Sistemelor de Operare "
    "care ne-a oferit o atmosferă de suport, implicare și energie pentru realizarea "
    "cărții. Forma actuală a cărții se bazează pe efortul susținut depus de-a lungul "
    "numeroaselor activități din jurul cursului de Utilizarea Sistemelor de Operare.</p>"
    "<p>Nu în ultimul rând, mulțumim cititorilor, la primul pas în domeniul plin de "
    "provocări și de satisfacții al calculatoarelor. Ei sunt cei cărora le dedicăm "
    "această carte. Ne-a făcut plăcere să o scriem, și sperăm că măcar o parte din "
    "entuziasmul nostru să se convertească în pasiune pentru cititorii acestor "
    "pagini.</p>"
    "<p style=\"text-align:right\"><em>Autorii</em></p>"
)

FOREWORD_RE = re.compile(r"^Cuvânt înainte\s*$")
CUPRINS_RE = re.compile(r"^Cuprins\s*$")
ABREVIERI_RE = re.compile(r"^Abrevieri\s*$")
ABBR_LINE_RE = re.compile(r"^([A-Z][A-Za-z0-9.\\]*) [–-] (.+)$")


def parse_front_matter(stream, first_chapter_idx):
    fw_idx = find_marker(stream, FOREWORD_RE.pattern)
    ab_idx = find_marker(stream, ABREVIERI_RE.pattern)
    foreword_html = FOREWORD_HTML if fw_idx is not None else ""
    abbrevs = []
    if ab_idx is not None:
        for _, ln in stream[ab_idx + 1:first_chapter_idx]:
            s = ln.strip()
            m = ABBR_LINE_RE.match(s)
            if m:
                abbrevs.append({"abbr": m.group(1), "full": m.group(2)})
    return {"foreword": foreword_html, "abbreviations": abbrevs}


# ---------------------------------------------------------------------------
# Images

def extract_images():
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    for f in IMG_DIR.glob("*"):
        f.unlink()
    out = subprocess.run(
        ["pdfimages", "-png", "-p", "-print-filenames", str(PDF), str(IMG_DIR / "img")],
        capture_output=True, check=True,
    ).stdout.decode("utf-8", "replace")
    by_page = {}
    for line in out.splitlines():
        path = Path(line.strip())
        if not path.exists():
            continue
        m = re.search(r"-(\d+)-\d+$", path.stem)
        if not m:
            continue
        page = int(m.group(1))
        # drop tiny decorative artifacts (icons/masks under ~2KB)
        if path.stat().st_size < 2048:
            path.unlink()
            continue
        by_page.setdefault(page, []).append(f"../assets/os-book/images/{path.name}")
    return by_page


# ---------------------------------------------------------------------------
# Main assembly

def slugify_chapter(num):
    return f"ch{num}"


def build_all():
    print("Extracting text from PDF...", file=sys.stderr)
    pages = extract_pages()
    print(f"{len(pages)} pages extracted.", file=sys.stderr)
    stream = build_line_stream(pages)
    chapters_raw, anexa_idx, _ = build_chapters(stream)
    answers_by_chapter = parse_answers_appendix(stream, anexa_idx)
    biblio = parse_bibliography(stream, anexa_idx)
    front_matter = parse_front_matter(stream, chapters_raw[0]["start_idx"] if chapters_raw else len(stream))

    print("Extracting images...", file=sys.stderr)
    images_by_page = extract_images()
    total_images = sum(len(v) for v in images_by_page.values())
    print(f"{total_images} images kept.", file=sys.stderr)

    chapters_out = []
    quiz_out = []
    unmatched_report = []
    used_images = set()

    for ch in chapters_raw:
        intro_lines, sections = split_sections(ch["content_lines"], None)
        learn_intro = parse_learn_intro(intro_lines)
        keywords = parse_keywords(ch["keyword_lines"])
        questions = parse_questions(ch["question_lines"])
        answers = {a["num"]: a for a in answers_by_chapter.get(ch["num"], [])}

        for s in sections:
            imgs = []
            if s["pageStart"] is not None:
                for p in range(s["pageStart"], s["pageEnd"] + 1):
                    for img in images_by_page.get(p, []):
                        if img not in used_images:
                            imgs.append(img)
                            used_images.add(img)
            s["images"] = imgs
            del s["pageStart"]
            del s["pageEnd"]

        chap_id = slugify_chapter(ch["num"])
        chapters_out.append({
            "id": chap_id,
            "num": ch["num"],
            "title": ch["title"],
            "learnIntro": learn_intro,
            "sections": sections,
            "keywords": keywords,
            "quizCount": len(questions),
        })

        for q in questions:
            a = answers.get(q["num"])
            if not a:
                continue
            idx, score = match_answer_to_option(a["answer"], q["options"])
            if idx == -1 or score < 0.5:
                unmatched_report.append((ch["num"], q["num"]))
                continue
            quiz_out.append({
                "id": f"{chap_id}-q{q['num']}",
                "chapter": ch["num"],
                "category": f"{ch['num']}. {ch['title']}",
                "difficulty": "medium",
                "question": q["text"],
                "options": q["options"],
                "answer": idx,
                "explanation": a["rationale"] or a["answer"],
            })

    if unmatched_report:
        print(f"WARNING: {len(unmatched_report)} questions could not be matched to an "
              f"answer and were dropped: {unmatched_report}", file=sys.stderr)

    # Validate quiz bank the same way internal/quiz.NewBank does.
    seen_ids = set()
    for q in quiz_out:
        assert q["id"] not in seen_ids, f"duplicate quiz id {q['id']}"
        seen_ids.add(q["id"])
        assert len(q["options"]) >= 2, f"{q['id']}: too few options"
        assert 0 <= q["answer"] < len(q["options"]), f"{q['id']}: answer index out of range"

    content = {
        "title": BOOK_TITLE,
        "frontMatter": front_matter,
        "chapters": chapters_out,
        "bibliography": biblio,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "content.json").write_text(json.dumps(content, ensure_ascii=False, indent=None), encoding="utf-8")
    (OUT_DIR / "quiz.json").write_text(json.dumps(quiz_out, ensure_ascii=False, indent=None), encoding="utf-8")

    print(f"Wrote {len(chapters_out)} chapters, "
          f"{sum(len(c['sections']) for c in chapters_out)} sections, "
          f"{len(quiz_out)} quiz questions, {len(biblio)} bibliography entries.", file=sys.stderr)


def debug_report():
    pages = extract_pages()
    print(f"{len(pages)} pages extracted.", file=sys.stderr)
    stream = build_line_stream(pages)
    chapters, anexa_idx, _ = build_chapters(stream)
    answers_by_chapter = parse_answers_appendix(stream, anexa_idx)
    biblio = parse_bibliography(stream, anexa_idx)
    print(f"Bibliography entries: {len(biblio)}", file=sys.stderr)

    total_q, total_matched = 0, 0
    for ch in chapters:
        kws = parse_keywords(ch["keyword_lines"])
        qs = parse_questions(ch["question_lines"])
        answers = answers_by_chapter.get(ch["num"], [])
        ans_by_num = {a["num"]: a for a in answers}
        matched = 0
        unmatched = []
        for q in qs:
            a = ans_by_num.get(q["num"])
            if not a:
                unmatched.append((q["num"], "NO ANSWER ENTRY"))
                continue
            idx, score = match_answer_to_option(a["answer"], q["options"])
            if idx == -1 or score < 0.55:
                unmatched.append((q["num"], f"score={score:.2f} answer={a['answer']!r} opts={q['options']}"))
            else:
                matched += 1
        total_q += len(qs)
        total_matched += matched
        print(f"Ch{ch['num']:>2} {ch['title']!r}: {len(kws)} keywords, {len(qs)} questions, "
              f"{matched}/{len(qs)} matched", file=sys.stderr)
        for num, info in unmatched:
            print(f"    UNMATCHED q{num}: {info}", file=sys.stderr)
    print(f"\nTOTAL: {total_matched}/{total_q} questions matched to an answer option", file=sys.stderr)


if __name__ == "__main__":
    if "--debug" in sys.argv:
        debug_report()
    else:
        build_all()
