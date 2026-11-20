"""古籍混合检索：BM25、向量召回、RRF 融合和交叉编码器重排。"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Annotated

import jieba
from langchain_core.tools import tool
from rank_bm25 import BM25Okapi

PROJECT_DIR = Path(__file__).resolve().parents[1]
# 这里使用的模型把文本编码成向量。终端里配置的 DeepSeek 负责对话和选工具。
EMBED_MODEL = "shibing624/text2vec-base-chinese"
RERANK_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
EMBED_MAX_TOKENS = 128
WINDOW_SIZE, WINDOW_OVERLAP = 110, 20
# 每路保留至多 30 条候选。RRF_K 是倒数排名公式中的平滑常数。
RECALL_K = 30
RRF_K = 60
# 供 jieba 识别的命理词典，尽量保留「七杀」「卯酉冲」等术语。
BAZI_TERMS = (
    "八字 四柱 日主 日干 月令 月支 日支 时支 年柱 月柱 日柱 时柱 "
    "十神 藏干 五行 旺衰 身旺 身弱 强根 格局 正财格 偏财格 "
    "正官格 七杀格 食神格 伤官格 正印格 偏印格 财格 官格 印格 从格 "
    "比肩 劫财 食神 伤官 正财 偏财 正官 七杀 正印 偏印 财星 官星 "
    "官杀 财官 印绶 夫星 妻星 夫妻宫 配偶宫 夫妻 婚姻 六亲 父母 子女 "
    "扶抑 调候 通关 病药 用神 喜神 忌神 相神 寒暖 燥湿 喜忌 "
    "大运 起运 流年 流月 岁运 交运 顺行 逆行 刑冲 合冲 合化 六合 三合 六冲 "
    "子午冲 子丑合 卯酉冲 寅申冲 辰戌冲 巳亥冲 丑未冲 驿马 桃花 神煞 纳音 旬空 "
    "甲木 乙木 丙火 丁火 戊土 己土 庚金 辛金 壬水 癸水 "
    "子月 丑月 寅月 卯月 辰月 巳月 午月 未月 申月 酉月 戌月 亥月 "
    "三春 三夏 三秋 三冬 穷通宝鉴 子平真诠 三命通会 渊海子平 滴天髓 神峰通考"
).split()


def split_passages(row, size=360, overlap=60):
    """尽量按句末切分，保留章节 ID 和原文字偏移供引用。"""
    text = row["text"]
    start = 0
    while start < len(text):
        stop = min(start + size, len(text))
        if stop < len(text):
            # 在候选片段后半段找最后一个标点，优先在句尾结束。
            boundaries = [m.end() for m in re.finditer(r"[。！？；\n]", text[start:stop])
                          if m.end() >= size // 2]
            if boundaries:
                stop = start + boundaries[-1]
        passage = text[start:stop]
        if passage.strip():
            # 原章节 ID 和字符范围组成片段 ID，两路召回和最终引用用同一标识。
            yield {
                "passage_id": f"{row['chunk_id']}@{start}-{stop}",
                "chunk_id": row["chunk_id"], "book": row["book"],
                "chapter": row.get("chapter_title", ""), "start": start, "end": stop,
                "text": passage,
            }
        if stop == len(text):
            break
        # 回退一段作为重叠，让跨边界的句子还能在相邻片段里被搜索到。
        start = max(start + 1, stop - overlap)


def load_corpus(directory):
    passages, seen = [], set()
    # 每行 JSON 对应一条古籍章节记录。先检查来源字段和 ID，再拆成检索片段。
    for path in sorted(directory.glob("*.jsonl")):
        with path.open(encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict) or not all(
                    isinstance(row.get(key), str) and row[key].strip()
                    for key in ("chunk_id", "book", "text")
                ):
                    raise ValueError(f"古籍字段不完整：{path.name}:{line_no}")
                if row["chunk_id"] in seen:
                    raise ValueError(f"重复古籍章节 ID：{row['chunk_id']}")
                seen.add(row["chunk_id"])
                passages.extend(split_passages(row))
    if not passages:
        raise ValueError(f"没有可检索的古籍片段：{directory}")
    return passages


def reciprocal_rank_fusion(rankings, limit, *, tie_breaker=None):
    """rankings 的值是各查询或通道按相关度排列的片段索引。"""
    # 收集片段在各榜单的首次名次，只用 1/(60+名次) 相加来比较。
    ranks = defaultdict(dict)
    for name, indices in rankings.items():
        for rank, index in enumerate(indices, start=1):
            ranks[index].setdefault(name, rank)
    scores = {index: sum(1 / (RRF_K + rank) for rank in positions.values())
              for index, positions in ranks.items()}
    # 先按融合分数排，再用稳定的标识打破同分，便于重复运行时对照。
    tie_key = tie_breaker or (lambda index: index)
    ordered = sorted(scores, key=lambda index: (-scores[index], tie_key(index)))[:limit]
    return [(index, scores[index], ranks[index]) for index in ordered]


class BM25Index:
    def __init__(self, passages):
        # 将书名、篇名和正文一起分词。词列表用于 BM25，集合用于判断是否匹配。
        self.segmenter = jieba.Tokenizer()
        for term in BAZI_TERMS:
            self.segmenter.add_word(term, freq=100000)
        tokens = [self.tokenize(f"{p['book']} {p['chapter']} {p['text']}") for p in passages]
        self.token_sets = [set(words) for words in tokens]
        self.index = BM25Okapi(tokens)

    def tokenize(self, text):
        # 语料和查询走同一套分词。NFKC 能统一全角半角等字符形式。
        normalized = unicodedata.normalize("NFKC", text).lower()
        return [word for word in self.segmenter.cut_for_search(normalized)
                if re.search(r"[\u4e00-\u9fffA-Za-z0-9]", word)]

    def search(self, queries):
        rankings = {}
        # 每组词单独打分，只保留至少命中一个词的片段，再融合关键词通道内的排名。
        for query in queries:
            terms = set(self.tokenize(query))
            if not terms:
                continue
            scores = self.index.get_scores(sorted(terms))
            matches = [index for index, tokens in enumerate(self.token_sets) if terms & tokens]
            rankings[query] = sorted(matches, key=lambda index: (-scores[index], index))[:RECALL_K]
        return [index for index, _, _ in reciprocal_rank_fusion(rankings, RECALL_K)]


class VectorIndex:
    def __init__(self, passages, cache_dir):
        # 延迟加载推理依赖，普通对话和排盘阶段无需加载向量模型。
        import torch
        import transformers
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.tokenizer = self.load_model(AutoTokenizer)
        self.model = self.load_model(AutoModel).to(self.device).eval()
        self.passage_count = len(passages)
        # 向量模型读更短的窗口。parents 记下每个窗口属于哪个约 360 字的父片段。
        windows, parents = [], []
        for index, passage in enumerate(passages):
            text = passage["text"]
            for start in range(0, len(text), WINDOW_SIZE - WINDOW_OVERLAP):
                window = text[start:start + WINDOW_SIZE]
                if window.strip():
                    windows.append(window)
                    parents.append(index)
                if start + WINDOW_SIZE >= len(text):
                    break
        self.parents = torch.tensor(parents, dtype=torch.long)
        # 缓存文件名由语料、模型版本及切分参数决定。与 Notebook 一致时可直接复用。
        metadata = {
            "model": EMBED_MODEL,
            "revision": getattr(self.model.config, "_commit_hash", None),
            "transformers": transformers.__version__, "pooling": "mean_l2_v1",
            "max_tokens": EMBED_MAX_TOKENS, "window_size": WINDOW_SIZE,
            "overlap": WINDOW_OVERLAP,
            "passages": [(p["passage_id"], p["text"]) for p in passages],
        }
        digest = hashlib.sha256(json.dumps(metadata, ensure_ascii=False).encode("utf-8")).hexdigest()
        self.vectors = self.load_vectors(windows, cache_dir / f"embeddings-{digest}.pt")

    @staticmethod
    def load_model(loader):
        # 优先从本机 Hugging Face 缓存加载，只有未找到时才尝试联网加载。
        try:
            return loader.from_pretrained(EMBED_MODEL, local_files_only=True)
        except OSError:
            return loader.from_pretrained(EMBED_MODEL)

    def load_vectors(self, windows, cache_path):
        if cache_path.is_file():
            # 一个窗口对应一行向量，读取后检查两边数量是否一致。
            data = self.torch.load(cache_path, map_location="cpu", weights_only=True)
            if data["vectors"].shape[0] != len(windows):
                raise ValueError(f"向量缓存与古籍片段数量不一致：{cache_path}")
            return data["vectors"]

        vectors, truncated = self.encode(windows)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        # 先写临时文件再替换正式缓存，避免中断时留下只写了一半的文件。
        with NamedTemporaryFile(dir=cache_path.parent, suffix=".tmp", delete=False) as temp:
            temp_path = Path(temp.name)
        try:
            self.torch.save({"vectors": vectors, "truncated": truncated}, temp_path)
            temp_path.replace(cache_path)
        finally:
            temp_path.unlink(missing_ok=True)
        return vectors

    def encode(self, texts):
        torch = self.torch
        vectors, truncated = [], 0
        # 查询和语料共用编码：分批转 token，统计超长输入，再截断到模型上限。
        for start in range(0, len(texts), 24):
            batch = texts[start:start + 24]
            token_ids = self.tokenizer(batch, truncation=False, verbose=False)["input_ids"]
            truncated += sum(len(ids) > EMBED_MAX_TOKENS for ids in token_ids)
            inputs = self.tokenizer(batch, padding=True, truncation=True,
                                    max_length=EMBED_MAX_TOKENS, return_tensors="pt")
            inputs = inputs.to(self.device)
            with torch.inference_mode():
                hidden = self.model(**inputs).last_hidden_state
                # 只对实际文字的 token 向量取平均。归一化后点积等于余弦相似度。
                mask = inputs["attention_mask"].unsqueeze(-1)
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
                vectors.append(torch.nn.functional.normalize(pooled, dim=1).cpu())
        return torch.cat(vectors), truncated

    def search(self, queries):
        torch = self.torch
        query_vectors, truncated = self.encode(queries)
        rankings = {}
        # 矩阵里的每一行是一条查询与所有古籍窗口的相似度。
        for query, similarities in zip(queries, query_vectors @ self.vectors.T):
            # 向量窗口的相似度取最大值，再按父片段与 BM25 结果合并。
            scores = torch.full((self.passage_count,), float("-inf"))
            scores.scatter_reduce_(0, self.parents, similarities, reduce="amax", include_self=True)
            top = scores.topk(min(RECALL_K, self.passage_count))
            rankings[query] = [index for index, score in zip(top.indices.tolist(), top.values.tolist())
                               if score != float("-inf")]
        # 多条语义查询各有自己的榜单，先在向量通道内部融合。
        return [index for index, _, _ in reciprocal_rank_fusion(rankings, RECALL_K)], truncated


class CrossEncoderReranker:
    def __init__(self):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

        def load(loader):
            try:
                return loader.from_pretrained(RERANK_MODEL, local_files_only=True)
            except OSError:
                return loader.from_pretrained(RERANK_MODEL)

        self.tokenizer = load(AutoTokenizer)
        self.model = load(AutoModelForSequenceClassification).to(self.device).eval()

    def rerank(self, candidates, question, keywords, phrases, limit):
        # 与 Notebook 一样，将问题、语义查询和关键词与每个候选片段成对评分。
        query = ("用户问题：" + question + "\n语义查询：" + "；".join(phrases)
                 + "\n关键词：" + "；".join(keywords))
        ranked, truncated = [], 0
        for start in range(0, len(candidates), 8):
            batch = candidates[start:start + 8]
            texts = [f"{item['book']} {item['chapter']}\n{item['text']}" for item in batch]
            lengths = self.tokenizer([query] * len(batch), texts, truncation=False, verbose=False)["input_ids"]
            truncated += sum(len(ids) > 512 for ids in lengths)
            inputs = self.tokenizer([query] * len(batch), texts, padding=True, truncation=True,
                                    max_length=512, return_tensors="pt").to(self.device)
            with self.torch.inference_mode():
                scores = self.model(**inputs).logits.reshape(-1).tolist()
            ranked.extend({**item, "rerank_score": float(score)} for item, score in zip(batch, scores))
        ranked.sort(key=lambda item: -item["rerank_score"])
        return ranked[:limit], truncated


class HybridRAG:
    def __init__(self, corpus_dir=PROJECT_DIR / "classics", cache_dir=PROJECT_DIR / ".rag_cache"):
        self.corpus_dir = corpus_dir
        self.cache_dir = cache_dir
        self.passages = None
        self.keyword_index = None
        self.vector_index = None
        self.reranker = None
        # ToolNode 可以并发执行工具，同一索引只在首次需要时构建一次。
        self.lock = Lock()

    def search(self, keyword_queries, semantic_queries, limit=5, question=""):
        # 1. 接收 Agent 给出的两组查询，去掉空项和重复项。
        keywords = list(dict.fromkeys(query.strip() for query in keyword_queries if query.strip()))
        phrases = list(dict.fromkeys(query.strip() for query in semantic_queries if query.strip()))
        if not keywords or not phrases:
            raise ValueError("混合检索需要同时提供 BM25 关键词和向量检索语句。")
        if not 1 <= limit <= RECALL_K:
            raise ValueError(f"limit 应在 1 到 {RECALL_K} 之间。")

        # 2. 首次查询时加载语料和索引，再分别取 BM25 与向量通道的排名。
        with self.lock:
            if self.passages is None:
                self.passages = load_corpus(self.corpus_dir)
            if self.keyword_index is None:
                self.keyword_index = BM25Index(self.passages)
            if self.vector_index is None:
                self.vector_index = VectorIndex(self.passages, self.cache_dir)
            keyword_hits = self.keyword_index.search(keywords)
            vector_hits, truncated = self.vector_index.search(phrases)
            # 3. 先融合最多 30 条候选，再重排；不能先按最终 limit 截断。
            rankings = {"keyword": keyword_hits, "vector": vector_hits}
            fused = reciprocal_rank_fusion(rankings, RECALL_K, tie_breaker=lambda i: self.passages[i]["passage_id"])
            candidates = [
                {**self.passages[index], "rrf_score": score, "route_ranks": ranks}
                for index, score, ranks in fused
            ]
            if candidates:
                if self.reranker is None:
                    self.reranker = CrossEncoderReranker()
                hits, rerank_truncated = self.reranker.rerank(candidates, question, keywords, phrases, limit)
            else:
                hits, rerank_truncated = [], 0
        notices = []
        if truncated:
            notices.append(f"{truncated} 条语义查询超过 {EMBED_MAX_TOKENS} tokens，编码时已截断。")
        if rerank_truncated:
            notices.append(f"{rerank_truncated} 条重排输入超过 512 tokens，评分时已截断。")
        return {"passages": hits, "route_counts": {name: len(items) for name, items in rankings.items()},
                "notices": notices}


# 工具共用一个检索实例，可跨对话复用已经建好的古籍索引。
_classics = HybridRAG()


@tool
def search_classics(
    keyword_queries: Annotated[list[str], "BM25 使用的术语或短词组列表，每项独立检索。至少提供一项。"],
    semantic_queries: Annotated[list[str], "向量检索使用的自然语言查询列表，每项表达想查的古籍规则。至少提供一项。"],
    limit: Annotated[int, "重排后最多返回的片段数，范围 1 到 30，默认 5。"] = 5,
    question: Annotated[str, "用户当前的问题，供交叉编码器重排时参考。"] = "",
) -> dict:
    """需要古籍规则支持解读时，根据用户问题和已计算的命盘调用混合检索。
    当前语料主要为八字古籍。keyword_queries 是 BM25 关键词字符串列表，semantic_queries 是向量检索语句字符串列表，两组都至少提供一项。
    工具以 RRF 融合两路排名，再按用户问题、查询和关键词进行交叉编码器重排，返回原文、出处和可引用的 passage_id。
    limit 控制返回片段数，默认 5，最多 30。
    """
    return _classics.search(keyword_queries, semantic_queries, limit, question)
