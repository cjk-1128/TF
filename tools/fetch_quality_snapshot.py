#!/usr/bin/env python3
# 从 VM(8002) 拉质量巡检数据 -> quality_snapshot.json（看板兜底）。
# 修正：KB 路径 /knowledge/kb；health 走根 /health；若最新报告缺 coverage/vector_health 则触发一次新巡检补齐。
import json, urllib.request, urllib.error, sys, os, time

BASE = "http://192.168.88.100:8002/api/v1"
ROOT = "http://192.168.88.100:8002"
KEY = "tf-admin-seed-key"
TENANT = "default"
HEADERS = {"X-API-Key": KEY, "X-Tenant-Id": TENANT, "Content-Type": "application/json"}

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quality_snapshot.json")

def req(method, path, body=None, timeout=120, base=BASE):
    url = base + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"

def get_detail(report_id):
    st, det = req("GET", f"/quality/reports/{report_id}")
    if isinstance(det, dict) and det.get("code") == 0:
        return det.get("data", det)
    return None

def main():
    snap = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "base": BASE, "errors": []}

    st, h = req("GET", "/health", base=ROOT)
    snap["health_ok"] = (st == 200)
    snap["health"] = h.get("data", h) if isinstance(h, dict) else h

    # KB 列表（下钻选择器）
    st, kb = req("GET", "/knowledge/kb?page=1&page_size=200")
    kbs = []
    if isinstance(kb, dict) and kb.get("code") == 0:
        d = kb.get("data")
        items = d if isinstance(d, list) else ((d or {}).get("items") or (d or {}).get("list") or [])
        for it in items:
            kbs.append({"id": it.get("id"), "name": it.get("name"), "domain": it.get("domain")})
    else:
        snap["errors"].append(f"kb_list: {st} {kb}")
    snap["knowledge_bases"] = kbs

    # 报告列表
    st, rep = req("GET", "/quality/reports?page=1&page_size=50")
    reports = []
    if isinstance(rep, dict) and rep.get("code") == 0:
        reports = (rep.get("data") or {}).get("items") or (rep.get("data") or {}).get("list") or []
    else:
        snap["errors"].append(f"reports: {st} {rep}")

    # 若最新报告缺 coverage/vector_health（早期快照 NULL），触发一次新巡检补齐真实数据
    seeded = False
    if reports:
        latest = get_detail(reports[0].get("id"))
        if latest is None or (latest.get("coverage") is None and latest.get("vector_health") is None):
            st, ins = req("POST", "/quality/inspect", {"kb_id": "", "persist": True}, timeout=180)
            if isinstance(ins, dict) and ins.get("code") == 0:
                seeded = True
                st, rep = req("GET", "/quality/reports?page=1&page_size=50")
                if isinstance(rep, dict) and rep.get("code") == 0:
                    reports = (rep.get("data") or {}).get("items") or (rep.get("data") or {}).get("list") or []
    snap["seeded_inspect"] = seeded
    snap["reports"] = reports

    # 最新报告明细
    if reports:
        snap["latest_report"] = get_detail(reports[0].get("id"))

    # 趋势
    st, tr = req("GET", "/quality/score-trend?limit=100&threshold=80")
    snap["score_trend"] = tr.get("data", tr) if isinstance(tr, dict) else None
    if not isinstance(snap.get("score_trend"), dict):
        snap["errors"].append(f"score_trend: {st} {tr}")

    # 告警
    st, al = req("GET", "/quality/alerts?page=1&page_size=50")
    if isinstance(al, dict) and al.get("code") == 0:
        snap["alerts"] = (al.get("data") or {}).get("items") or (al.get("data") or {}).get("list") or []
    else:
        snap["errors"].append(f"alerts: {st} {al}")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)

    print("=== SNAPSHOT SUMMARY ===")
    print(f"health_ok={snap.get('health_ok')} kbs={len(kbs)} reports={len(reports)} "
          f"seeded={seeded} alerts={len(snap.get('alerts', []))}")
    trd = snap.get("score_trend") or {}
    print(f"trend_points={len(trd.get('points', []))} latest={trd.get('latest')} "
          f"delta={trd.get('first_to_latest_delta')}")
    lr = snap.get("latest_report") or {}
    print(f"latest score={lr.get('score')} issue_count={lr.get('issue_count')} "
          f"issue_counts={lr.get('issue_counts')}")
    print(f"latest coverage={'YES' if lr.get('coverage') else 'NO'} "
          f"vector_health={'YES' if lr.get('vector_health') else 'NO'}")
    if snap["errors"]:
        print("ERRORS:", json.dumps(snap["errors"], ensure_ascii=False)[:600])
    print(f"WROTE {OUT}")

if __name__ == "__main__":
    main()
