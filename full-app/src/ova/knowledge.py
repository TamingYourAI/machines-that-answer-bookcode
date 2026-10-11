"""Knowledge for the ear: retrieval that returns one speakable sentence and its source.

Documents are Markdown with a small front matter block. Sections are chunks; the heading is
part of the chunk, so a document written as questions and short answers retrieves well. A
search returns at most three passages, each with the sentence the agent may say, the source id,
a confidence, and an expiry. Below the confidence floor, or past its expiry, a passage is not
returned, and the agent says it does not know (REQUIREMENTS section 12; builders' Chapter 16).

The index is BM25 over lightly stemmed words, in memory, standard library only. It is small on
purpose: the pack's documents are pages, not a library. A vector index can sit behind the same
`search` when one is needed.
"""
from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from .speech import sentences

STOP = set("""a an the and or but if of to in on at by for with from as is are was were be been
being it its this that these those i me my we our you your he she they them their what which who
whom how when where why do does did doing have has had having can could will would should may
might must shall not no so than too very just about into over under again further then once here
there all any both each few more most other some such only own same s t don now please tell
know want need like get got yes yeah yep no nope ok okay sure thanks thank hi hello""".split())


def stem(w: str) -> str:
    for suf in ("ing", "ies", "ed", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            if suf == "ies":
                return w[:-3] + "y"
            if suf == "es" and not w.endswith(("ses", "xes", "ches", "shes")):
                return w[:-1]
            return w[: -len(suf)]
    return w


def terms(text: str) -> list[str]:
    return [stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


@dataclass
class Chunk:
    source_id: str
    doc_title: str
    heading: str
    text: str
    locator: str
    expires: dt.date | None = None
    reviewed: dt.date | None = None
    words: list[str] = field(default_factory=list)


@dataclass
class Passage:
    source_id: str
    title: str
    heading: str
    sentence: str
    text: str
    confidence: float
    expires: str | None = None


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    meta = {}
    for line in text[3:end].strip().splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, text[end + 4:].lstrip()


def _date(v: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat(v) if v else None
    except ValueError:
        return None


class KnowledgeBase:
    def __init__(self, synonyms: dict[str, list[str]] | None = None, floor: float = 0.5):
        self.chunks: list[Chunk] = []
        self.df: dict[str, int] = {}
        self.avg_len = 1.0
        self.synonyms = {stem(k): [stem(s) for s in v] for k, v in (synonyms or {}).items()}
        self.floor = floor
        self.warnings: list[str] = []

    # ------------------------------------------------------------ ingest
    def add_markdown(self, text: str, default_id: str = "doc") -> int:
        meta, body = parse_front_matter(text)
        source = meta.get("source_id", default_id)
        title = meta.get("title", source)
        expires, reviewed = _date(meta.get("expires")), _date(meta.get("reviewed"))
        heading, buf, n = title, [], 0
        path: list[str] = []

        def flush():
            nonlocal n
            body_text = " ".join(" ".join(buf).split())
            if body_text:
                slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")[:48]
                c = Chunk(source, title, heading, body_text, f"{source}#{slug}", expires,
                          reviewed)
                c.words = terms(heading + " " + heading + " " + body_text)
                self.chunks.append(c)
                n += 1
            buf.clear()

        for line in body.splitlines():
            m = re.match(r"^(#{1,4})\s+(.*)", line)
            if m:
                flush()
                level = len(m.group(1))
                path[:] = path[: level - 1] + [m.group(2).strip()]
                heading = m.group(2).strip()
                continue
            if line.strip().startswith("|") or not line.strip():
                buf.append(" ") if not line.strip() else buf.append(
                    " ".join(c.strip() for c in line.strip("|").split("|")))
                continue
            buf.append(line.strip().lstrip("-* "))
        flush()
        if n == 0:
            self.warnings.append(f"{source}: no text found")
        self._reindex()
        return n

    def add_file(self, path: Path) -> int:
        return self.add_markdown(path.read_text(encoding="utf-8"), default_id=path.stem)

    def add_dir(self, folder: Path) -> int:
        return sum(self.add_file(p) for p in sorted(folder.glob("*.md")))

    def _reindex(self) -> None:
        self.df = {}
        for c in self.chunks:
            for w in set(c.words):
                self.df[w] = self.df.get(w, 0) + 1
        self.avg_len = sum(len(c.words) for c in self.chunks) / max(1, len(self.chunks))

    # ------------------------------------------------------------ search
    def idf(self, w: str) -> float:
        n = len(self.chunks)
        return math.log(1 + (n - self.df.get(w, 0) + 0.5) / (self.df.get(w, 0) + 0.5))

    def max_idf(self) -> float:
        n = len(self.chunks)
        return math.log(1 + (n + 0.5) / 0.5)

    def expand(self, q: list[str]) -> list[str]:
        out = list(q)
        for w in q:
            out += self.synonyms.get(w, [])
            out += [k for k, vs in self.synonyms.items() if w in vs]
        return out

    def search(self, query: str, k: int = 3, today: dt.date | None = None
               ) -> list[Passage]:
        today = today or dt.date.today()
        q = self.expand(terms(query))
        if not q or not self.chunks:
            return []
        qset = set(q)
        base = set(terms(query))
        scored = []
        k1, b = 1.4, 0.7
        for c in self.chunks:
            if c.expires and c.expires < today:
                continue
            tf: dict[str, int] = {}
            for w in c.words:
                if w in qset:
                    tf[w] = tf.get(w, 0) + 1
            if not tf:
                continue
            s = 0.0
            for w, f in tf.items():
                s += self.idf(w) * f * (k1 + 1) / (f + k1 * (1 - b + b * len(c.words)
                                                              / self.avg_len))
            # confidence: the share of the question's informative weight the chunk covers.
            # A word the documents never use counts at full weight: an answer that ignores
            # "broken" in "my car was broken into" is not an answer.
            def weight(w: str) -> float:
                return self.idf(w) if w in self.df else self.max_idf()
            want = sum(weight(w) for w in base) or 1.0
            got = sum(weight(w) for w in base if w in tf or any(
                s2 in tf for s2 in self.synonyms.get(w, [])) or any(
                w in vs and kk in tf for kk, vs in self.synonyms.items()))
            head = set(terms(c.heading))
            head_bonus = 0.1 if got / want >= 0.5 and base & head else 0.0
            scored.append((s, min(1.0, got / want + head_bonus), c))
        scored.sort(key=lambda x: -x[0])
        out = []
        for s, conf, c in scored[:k]:
            if conf < self.floor:
                continue
            out.append(Passage(c.source_id, c.doc_title, c.heading,
                               self.best_sentences(c, qset), c.text, round(conf, 2),
                               c.expires.isoformat() if c.expires else None))
        return out

    @staticmethod
    def best_sentences(c: Chunk, q: set[str], limit_words: int = 38) -> str:
        """The one or two sentences a voice should say: the first that answers, and the next
        if it is short and still on the question."""
        sents = sentences(c.text)
        if not sents:
            return c.text
        scores = [len(q & set(terms(s))) for s in sents]
        i = max(range(len(sents)), key=lambda j: (scores[j], -j))
        if scores[i] == 0 or c.heading.rstrip().endswith("?"):
            i = 0                       # a question heading: its answer comes first
        out = sents[i]
        if i + 1 < len(sents) and len((out + " " + sents[i + 1]).split()) <= limit_words:
            out = out + " " + sents[i + 1]
        return out
