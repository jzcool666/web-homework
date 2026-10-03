"""SPEC-007 第 4 节：课程语料的 TF-IDF 检索。

规则来自 ADR-007 第 1 条与 SPEC-007 第 4 节：
- 文本去空白归一化；`TfidfVectorizer(analyzer='char', ngram_range=(2,4))` + 余弦相似度；
- 索引只含**已发布**的知识点与问答条目，不含测评题目与答案；
- 每个知识点贡献「标题」与「正文」两条语料（标题独立打分，见下方常量说明），
  问答条目贡献一条；命中按知识点归并，最多返回 3 个知识点；
- 语料指纹由参与索引的条目 ID 与版本构成，指纹变化时下一次查询重建索引；
- 并发请求只让一个线程构建，构建失败保留旧索引并显式报错，不返回混合版本。

向量索引是可重建的内存数据，不落库（SPEC-007 第 3 节）。检索结果只表示文本相近，
不是正确概率，接口层与页面都必须这样表述（SPEC-007 第 4 节第 2 条）。
"""

from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import dataclass

from sqlalchemy import select

from .models_content import KnowledgePoint
from .models_qa import QAEntry

# 索引算法版本：随索引口径变化递增，与语料指纹一起构成 corpus_version
INDEX_VERSION = "v1"

KIND_KNOWLEDGE = "knowledge"
# 标题单独成一条语料：短查询（「时钟上升沿的作用是什么」）与长正文的余弦会被正文
# 归一化稀释，标题独立打分后这类查询才排得进 Top3。标题语料只用于打分，
# 摘要始终取该知识点的正文或问答条目。
KIND_KNOWLEDGE_TITLE = "knowledge_title"
KIND_QA = "qa"

# 默认相似度阈值：待校准参数（SPEC-007 第 4 节第 2 条），不是正确概率
SIMILARITY_THRESHOLD = 0.2

MAX_MATCHES = 3
EXCERPT_MAX = 300
QUERY_MIN = 2
QUERY_MAX = 200

_WHITESPACE = re.compile(r"\s+")


class IndexUnavailable(RuntimeError):
    """语料索引重建失败。

    此时保留旧索引并让本次请求显式失败：用旧指纹的结果回答新语料的问题
    等于返回混合版本（SPEC-007 第 4 节第 3 条）。
    """


def normalize(text: str | None) -> str:
    """去空白归一化：索引与查询用同一口径，避免空白造成伪差异。"""
    return _WHITESPACE.sub("", text or "")


@dataclass(frozen=True)
class Document:
    """参与索引的一条语料。"""

    kind: str
    entry_id: int
    knowledge_id: int
    title: str
    text: str
    source_url: str | None


@dataclass(frozen=True)
class Match:
    knowledge_id: int
    title: str
    excerpt: str
    source_url: str | None
    similarity: float

    def as_dict(self) -> dict:
        return {
            "knowledge_id": self.knowledge_id,
            "title": self.title,
            "excerpt": self.excerpt,
            "source_url": self.source_url,
            "similarity": self.similarity,
        }


@dataclass(frozen=True)
class _Index:
    fingerprint: str
    documents: tuple[Document, ...]
    texts: tuple[str, ...]
    vectorizer: object | None
    matrix: object | None


_LOCK = threading.Lock()
_INDEX: _Index | None = None
_BUILDS = 0


# ---- 语料 ----

def load_corpus(session) -> list[Document]:
    """已发布知识点（标题与正文各一条）+ 已发布问答条目。

    问答条目的知识点未发布时整条跳过：学生看不到那个知识点，就不应通过检索
    拿到它的正文（SPEC-007 第 4 节第 1 条）。
    """
    points = list(
        session.scalars(
            select(KnowledgePoint)
            .where(KnowledgePoint.published == 1)
            .order_by(KnowledgePoint.id)
        )
    )
    by_id = {point.id: point for point in points}

    documents: list[Document] = []
    for point in points:
        documents.append(
            Document(
                kind=KIND_KNOWLEDGE_TITLE,
                entry_id=point.id,
                knowledge_id=point.id,
                title=point.title,
                text=normalize(point.title),
                source_url=point.source_url,
            )
        )
        documents.append(
            Document(
                kind=KIND_KNOWLEDGE,
                entry_id=point.id,
                knowledge_id=point.id,
                title=point.title,
                text=normalize(f"{point.title}\n{point.body_md}"),
                source_url=point.source_url,
            )
        )

    entries = session.scalars(
        select(QAEntry).where(QAEntry.published == 1).order_by(QAEntry.id)
    )
    for entry in entries:
        point = by_id.get(entry.knowledge_id)
        if point is None:
            continue
        documents.append(
            Document(
                kind=KIND_QA,
                entry_id=entry.id,
                knowledge_id=point.id,
                title=point.title,
                text=normalize(f"{entry.question}\n{entry.answer_md}"),
                source_url=entry.source_url or point.source_url,
            )
        )
    return documents


def corpus_fingerprint(session) -> str:
    """语料指纹：由参与索引的条目 ID 与版本构成（SPEC-007 第 3 节）。

    发布状态、正文或任何可写字段的修改都会递增版本或改变参与集合，因此指纹随之变化。
    """
    point_rows = session.execute(
        select(KnowledgePoint.id, KnowledgePoint.version)
        .where(KnowledgePoint.published == 1)
        .order_by(KnowledgePoint.id)
    ).all()
    published_ids = {row[0] for row in point_rows}
    qa_rows = session.execute(
        select(QAEntry.id, QAEntry.version, QAEntry.knowledge_id)
        .where(QAEntry.published == 1)
        .order_by(QAEntry.id)
    ).all()

    parts = [f"knowledge:{row[0]}:{row[1]}" for row in point_rows]
    parts += [f"qa:{row[0]}:{row[1]}:{row[2]}" for row in qa_rows if row[2] in published_ids]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{INDEX_VERSION}-{digest}"


# ---- 索引 ----

def _build_index(fingerprint: str, documents: list[Document]) -> _Index:
    texts = tuple(document.text for document in documents)
    if not documents:
        # 空语料是合法状态：查询一律 matched=false，不编造解释（T-007-02）
        return _Index(fingerprint, (), (), None, None)
    try:
        # 延迟导入：缺库时只在真正查询时报错，不影响应用启动与其他接口
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError as exc:  # pragma: no cover - 依赖缺失路径
        raise IndexUnavailable("检索依赖 scikit-learn 未安装") from exc

    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4))
    matrix = vectorizer.fit_transform(texts)
    return _Index(fingerprint, tuple(documents), texts, vectorizer, matrix)


def _index_for(session, fingerprint: str) -> _Index:
    """取当前指纹的索引；指纹变化时在锁内重建，并发只让一个线程构建。"""
    global _INDEX, _BUILDS

    cached = _INDEX
    if cached is not None and cached.fingerprint == fingerprint:
        return cached

    with _LOCK:
        cached = _INDEX
        if cached is not None and cached.fingerprint == fingerprint:
            return cached  # 等待期间已有线程重建完成
        try:
            built = _build_index(fingerprint, load_corpus(session))
        except IndexUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - 任何构建失败都按同一口径处理
            raise IndexUnavailable("检索索引重建失败") from exc
        _INDEX = built
        _BUILDS += 1
        return built


def _cosine(vectorizer, matrix, text: str):
    from sklearn.metrics.pairwise import cosine_similarity

    query_vector = vectorizer.transform([text])
    return cosine_similarity(query_vector, matrix)[0]


def excerpt(text: str, query: str, limit: int = EXCERPT_MAX) -> str:
    """以查询的首个公共二字组为中心取窗口，保证摘要在 300 字以内。"""
    text = text.strip()
    if len(text) <= limit:
        return text

    position = -1
    for start in range(len(query) - 1):
        found = text.find(query[start : start + 2])
        if found >= 0 and (position < 0 or found < position):
            position = found
    if position < 0:
        return text[:limit]

    window = max(1, limit - 2)  # 预留省略号
    begin = max(0, min(position - window // 3, len(text) - window))
    end = begin + window
    prefix = "…" if begin > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[begin:end]}{suffix}"[:limit]


def search(session, query: str) -> tuple[str, list[Match]]:
    """返回 (corpus_version, matches)。matches 按相似度倒序，最多 3 条。"""
    text = normalize(query)
    fingerprint = corpus_fingerprint(session)
    index = _index_for(session, fingerprint)
    if not index.documents:
        return fingerprint, []

    scores = _cosine(index.vectorizer, index.matrix, text)

    # 同一知识点可能由标题、正文与多条问答同时命中：按知识点归并取最高分，
    # 这样「最多 3 条」表示最多 3 个相关知识点，而不是同一知识点的多条文本。
    grouped: dict[int, dict] = {}
    for position, document in enumerate(index.documents):
        score = float(scores[position])
        bucket = grouped.setdefault(
            document.knowledge_id,
            {"best": -1.0, "winner": None, "content": None, "content_score": -1.0},
        )
        if score > bucket["best"]:
            bucket["best"] = score
            bucket["winner"] = document
        if document.kind != KIND_KNOWLEDGE_TITLE and score > bucket["content_score"]:
            bucket["content_score"] = score
            bucket["content"] = document

    scored = [
        (knowledge_id, bucket)
        for knowledge_id, bucket in grouped.items()
        if bucket["best"] >= SIMILARITY_THRESHOLD
    ]
    scored.sort(key=lambda item: (-item[1]["best"], item[0]))

    matches: list[Match] = []
    for knowledge_id, bucket in scored[:MAX_MATCHES]:
        # 摘要与来源取该知识点有内容的语料；标题语料只用于打分
        source = bucket["content"] or bucket["winner"]
        matches.append(
            Match(
                knowledge_id=knowledge_id,
                title=source.title,
                excerpt=excerpt(source.text, text),
                source_url=source.source_url,
                similarity=round(bucket["best"], 4),
            )
        )
    return fingerprint, matches


# ---- 测试与运行观测用的缓存控制 ----

def reset_index_cache() -> None:
    """清空内存索引；测试用它隔离用例，运行时不调用。"""
    global _INDEX, _BUILDS
    with _LOCK:
        _INDEX = None
        _BUILDS = 0


def build_count() -> int:
    """索引实际构建次数，用于验证「指纹不变不重建」。"""
    return _BUILDS
