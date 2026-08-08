"""进程内指标注册表（Prometheus exposition 文本格式，零外部依赖）。

提供：
  - inc_counter(name, amount=1.0, labels=None)   累加计数器
  - observe(name, value, labels=None)            直方图观测（固定 bucket）
  - set_gauge(name, value)                       瞬时量（无标签）
  - render_prometheus() -> str                   渲染 Prometheus 文本
  - snapshot() -> dict                           结构化聚合（供 admin 性能报告）
  - request_error_count() -> int                 统计 status>=500 请求数

所有操作线程安全，失败对调用方透明（调用方已 try/except 包裹）。
命名为 prom_metrics 以避开 app.core.metrics（检索评测指标模块）。
"""
from __future__ import annotations

import re
import math
import threading
from typing import Dict, List, Optional, Tuple

# 直方图固定分桶（秒）
_BUCKETS: List[float] = [
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")
]

_lock = threading.Lock()

# counters: name -> {label_key: value}
_counters: Dict[str, Dict[str, float]] = {}
# gauges: name -> float
_gauges: Dict[str, float] = {}
# histograms: name -> {label_key: {"count":int,"sum":float,"buckets":[int]}}
_histograms: Dict[str, Dict[str, Dict[str, object]]] = {}

_HELP: Dict[str, str] = {
    "terraforge_requests_total": "总请求数（按 method/path/status）",
    "terraforge_request_duration_seconds": "请求耗时分布（秒）",
    "terraforge_retrieval_duration_seconds": "混合检索耗时分布（秒）",
    "terraforge_embedding_duration_seconds": "Embedding 推理耗时分布（秒）",
    "terraforge_llm_duration_seconds": "LLM 生成耗时分布（秒）",
    "terraforge_vector_count": "向量索引条数",
    "terraforge_bm25_count": "BM25 索引条数",
    "terraforge_cache_hits_total": "缓存命中总数（L1+L2）",
    "terraforge_cache_misses_total": "缓存未命中总数",
    "terraforge_cache_hit_rate": "缓存命中率 [0,1]",
}


def _label_key(labels: Optional[Dict[str, str]]) -> str:
    if not labels:
        return ""
    parts = ['%s="%s"' % (k, str(v).replace("\\", "\\\\").replace('"', '\\"'))
             for k, v in sorted(labels.items())]
    return "{" + ",".join(parts) + "}"


def inc_counter(name: str, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
    key = _label_key(labels)
    with _lock:
        _counters.setdefault(name, {})
        _counters[name][key] = _counters[name].get(key, 0.0) + amount


def observe(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    key = _label_key(labels)
    with _lock:
        h = _histograms.setdefault(name, {}).setdefault(
            key, {"count": 0, "sum": 0.0, "buckets": [0] * len(_BUCKETS)})
        h["count"] += 1  # type: ignore[typeddict-item]
        h["sum"] = float(h["sum"]) + float(value)  # type: ignore[typeddict-item]
        for i, upper in enumerate(_BUCKETS):
            if float(value) <= upper:
                h["buckets"][i] += 1  # type: ignore[index]
                break


def set_gauge(name: str, value: float) -> None:
    with _lock:
        _gauges[name] = float(value)


def render_prometheus() -> str:
    lines: List[str] = []
    with _lock:
        # counters
        for name in sorted(_counters):
            lines.append("# HELP %s %s" % (name, _HELP.get(name, "")))
            lines.append("# TYPE %s counter" % name)
            for key, val in sorted(_counters[name].items()):
                lines.append("%s%s %s" % (name, key, _fmt_num(val)))
        # gauges
        for name in sorted(_gauges):
            lines.append("# HELP %s %s" % (name, _HELP.get(name, "")))
            lines.append("# TYPE %s gauge" % name)
            lines.append("%s %s" % (name, _fmt_num(_gauges[name])))
        # histograms
        for name in sorted(_histograms):
            lines.append("# HELP %s %s" % (name, _HELP.get(name, "")))
            lines.append("# TYPE %s histogram" % name)
            for key in sorted(_histograms[name]):
                h = _histograms[name][key]
                count = int(h["count"])
                total = float(h["sum"])
                cum = 0
                for i, upper in enumerate(_BUCKETS):
                    cum += int(h["buckets"][i])
                    le = "+Inf" if upper == float("inf") else _fmt_num(upper)
                    line_key = ("{%s,le=\"%s\"}" % (key[1:-1], le)) if key else "{le=\"%s\"}" % le
                    lines.append("%s_bucket%s %d" % (name, line_key, cum))
                lines.append("%s_sum%s %s" % (name, key, _fmt_num(total)))
                lines.append("%s_count%s %d" % (name, key, count))
    return "\n".join(lines) + "\n"


def _fmt_num(v: float) -> str:
    if v == int(v):
        return str(int(v))
    return ("%.6f" % v).rstrip("0").rstrip(".")


def _finite(v: Optional[float]) -> Optional[float]:
    """非有限浮点（NaN/inf/None）统一归零，确保 JSON 可序列化。"""
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return 0.0
    return v


def _quantile(bucket_cum: List[int], total: int, q: float) -> Optional[float]:
    """在累积桶计数上估算分位数（Prometheus 线性插值法）。"""
    if total <= 0:
        return None
    target = q * total
    prev_upper = 0.0
    prev_cum = 0
    for i, upper in enumerate(_BUCKETS):
        cum = bucket_cum[i]
        if cum >= target:
            if math.isinf(upper):
                # 末桶(+inf)无有限上界，用前一个有限桶上限作为估计（避免 inf）
                return float(prev_upper)
            if cum == prev_cum:
                return float(upper)
            frac = (target - prev_cum) / (cum - prev_cum)
            est = prev_upper + frac * (float(upper) - prev_upper)
            return est if math.isfinite(est) else float(prev_upper)
        prev_upper = float(upper)
        prev_cum = cum
    return float(prev_upper)


def snapshot() -> dict:
    """结构化聚合当前所有指标，供 admin 性能报告使用（进程内实时快照，重启归零）。"""
    with _lock:
        counters = {name: sum(_counters[name].values()) for name in _counters}
        gauges = dict(_gauges)
        histograms: Dict[str, dict] = {}
        for name, labelmap in _histograms.items():
            total_count = 0
            total_sum = 0.0
            bucket_cum = [0] * len(_BUCKETS)
            for h in labelmap.values():
                total_count += int(h["count"])  # type: ignore[typeddict-item]
                total_sum += float(h["sum"])  # type: ignore[typeddict-item]
                for i in range(len(_BUCKETS)):
                    bucket_cum[i] += int(h["buckets"][i])  # type: ignore[index]
            histograms[name] = {
                "count": total_count,
                "sum": total_sum,
                "avg": _finite((total_sum / total_count) if total_count else 0.0),
                "p50": _finite(_quantile(bucket_cum, total_count, 0.5)),
                "p95": _finite(_quantile(bucket_cum, total_count, 0.95)),
                "p99": _finite(_quantile(bucket_cum, total_count, 0.99)),
            }
    return {"counters": counters, "gauges": gauges, "histograms": histograms}


def request_error_count() -> int:
    """统计 status>=500 的请求数（从 terraforge_requests_total 的 label 解析）。"""
    total = 0
    with _lock:
        for key, val in _counters.get("terraforge_requests_total", {}).items():
            m = re.search(r'status="(\d+)"', key)
            if m and int(m.group(1)) >= 500:
                total += int(val)
    return total


__all__ = ["inc_counter", "observe", "set_gauge", "render_prometheus",
           "snapshot", "request_error_count"]
