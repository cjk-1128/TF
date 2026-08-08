#!/usr/bin/env python3
# 生成质量巡检看板 HTML：内嵌真实快照 JSON 兜底 + 浏览器实时拉取（失败回退快照）。
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "quality_snapshot.json")
OUT = os.path.join(HERE, "quality_dashboard.html")
# 同时写入仓库 tools/ 以便版本化
REPO_OUT = r"D:\WorkBuddy_workspace\RAG\terraforge\tools\quality_dashboard.html"

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TerraForge 质量巡检看板</title>
<style>
  :root{
    --bg:#f4f6fb; --card:#ffffff; --ink:#1f2937; --mut:#6b7280; --line:#e5e7eb;
    --blue:#2563eb; --red:#ef4444; --amber:#f59e0b; --green:#10b981; --indigo:#6366f1;
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
       background:var(--bg);color:var(--ink);font-size:14px}
  header{background:linear-gradient(90deg,#1e3a8a,#2563eb);color:#fff;padding:14px 22px;
         display:flex;align-items:center;gap:16px;flex-wrap:wrap}
  header h1{font-size:18px;margin:0;font-weight:700;letter-spacing:.5px}
  header .sub{font-size:12px;opacity:.85}
  .ctrl{margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .ctrl input{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.35);
             color:#fff;padding:5px 9px;border-radius:6px;font-size:12px;width:200px}
  .ctrl input::placeholder{color:rgba(255,255,255,.6)}
  .btn{background:#fff;color:#1e3a8a;border:none;padding:6px 14px;border-radius:6px;
       font-weight:600;cursor:pointer;font-size:13px}
  .btn:hover{background:#eef2ff}
  main{max-width:1280px;margin:18px auto;padding:0 16px}
  .kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:16px}
  .kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
  .kpi .v{font-size:26px;font-weight:800;line-height:1.1}
  .kpi .l{font-size:12px;color:var(--mut);margin-top:4px}
  .kpi .bad{color:var(--red)} .kpi .ok{color:var(--green)} .kpi .warn{color:var(--amber)}
  .grid{display:grid;grid-template-columns:1.4fr 1fr;gap:16px;margin-bottom:16px}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
  .card h3{margin:0 0 10px;font-size:15px;display:flex;align-items:center;gap:8px}
  .card h3 .tag{font-size:11px;font-weight:600;color:var(--mut);background:#f3f4f6;
               padding:2px 8px;border-radius:20px}
  svg{width:100%;height:auto;display:block}
  .legend{display:flex;flex-wrap:wrap;gap:10px;margin-top:8px;font-size:12px}
  .legend span{display:inline-flex;align-items:center;gap:5px}
  .dot{width:10px;height:10px;border-radius:3px;display:inline-block}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
  th{color:var(--mut);font-weight:600;font-size:12px}
  tr.click{cursor:pointer} tr.click:hover{background:#f8fafc}
  .pill{font-size:11px;padding:2px 9px;border-radius:20px;font-weight:600}
  .p-high{background:#fee2e2;color:#b91c1c} .p-med{background:#fef3c7;color:#92400e}
  .p-low{background:#e0f2fe;color:#0369a1} .p-ok{background:#dcfce7;color:#15803d}
  .p-warn{background:#fef3c7;color:#92400e}
  select{width:100%;padding:7px 9px;border:1px solid var(--line);border-radius:8px;font-size:13px;
         background:#fff;color:var(--ink)}
  .banner{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:#1f2937;
          color:#fff;padding:9px 16px;border-radius:10px;font-size:12px;box-shadow:0 6px 20px rgba(0,0,0,.2);
          z-index:50;max-width:90%}
  .muted{color:var(--mut);font-size:12px}
  .tiles{display:flex;gap:10px;flex-wrap:wrap}
  .tile{flex:1;min-width:90px;background:#f8fafc;border:1px solid var(--line);border-radius:10px;
        padding:10px;text-align:center}
  .tile .tv{font-size:20px;font-weight:800} .tile .tl{font-size:11px;color:var(--mut);margin-top:3px}
  .detail{margin-top:12px}
  @media(max-width:980px){.kpis{grid-template-columns:repeat(3,1fr)}.grid,.grid2{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <div>
    <h1>TerraForge 质量巡检看板</h1>
    <div class="sub" id="subtitle">加载中…</div>
  </div>
  <div class="ctrl">
    <input id="apiBase" placeholder="API 基址 http://host:8002/api/v1" value="http://192.168.88.100:8002/api/v1">
    <input id="apiKey" placeholder="X-API-Key" value="tf-admin-seed-key">
    <button class="btn" id="refresh">刷新（实时）</button>
  </div>
</header>
<main>
  <section class="kpis" id="kpis"></section>

  <section class="grid">
    <div class="card">
      <h3>质量分趋势 <span class="tag" id="trendTag"></span></h3>
      <div id="trendChart"></div>
      <div id="issueBars" style="margin-top:6px"></div>
    </div>
    <div class="card">
      <h3>问题占比 <span class="tag">按类型聚合</span></h3>
      <div id="donut"></div>
      <div class="legend" id="donutLegend"></div>
    </div>
  </section>

  <section class="grid">
    <div class="card">
      <h3>域覆盖分布 <span class="tag">切片数 / 域</span></h3>
      <div id="coverage"></div>
    </div>
    <div class="card">
      <h3>向量质量体检 <span class="tag" id="vhTag"></span></h3>
      <div id="vectorHealth"></div>
    </div>
  </section>

  <section class="grid2">
    <div class="card">
      <h3>按知识库下钻 <span class="tag">选择库查看趋势/占比</span></h3>
      <select id="kbSel"></select>
      <div id="drill" style="margin-top:12px"></div>
    </div>
    <div class="card">
      <h3>质量告警 <span class="tag" id="alertTag"></span></h3>
      <div id="alerts"></div>
    </div>
  </section>

  <section class="card">
    <h3>历史巡检快照 <span class="tag">点击查看明细</span></h3>
    <div style="overflow:auto">
      <table id="histTable"><thead><tr>
        <th>时间</th><th>范围</th><th>质量分</th><th>问题数</th><th>问题分布</th><th>切片/文档</th>
      </tr></thead><tbody></tbody></table>
    </div>
    <div class="detail" id="reportDetail" style="display:none"></div>
  </section>
</main>
<div class="banner" id="banner" style="display:none"></div>

<script id="snapshot" type="application/json">__SNAPSHOT_JSON__</script>
<script>
const ISSUE_LABEL = {
  orphan_chunk:"孤立切片", duplicate_chunk:"重复切片", oversized_chunk:"超大切片",
  tiny_chunk:"碎片切片", missing_standard_code:"缺规范编号", missing_location:"缺定位信息",
  missing_vector:"向量缺失", zero_vector:"零向量", domain_coverage_gap:"域覆盖盲区",
  low_recall_intent:"低召回意图", isolated_query:"孤立查询"
};
const ISSUE_COLOR = {
  zero_vector:"#ef4444", missing_vector:"#ef4444", low_recall_intent:"#ef4444",
  isolated_query:"#ef4444", domain_coverage_gap:"#f59e0b",
  orphan_chunk:"#f59e0b", duplicate_chunk:"#f59e0b", oversized_chunk:"#f59e0b",
  tiny_chunk:"#f59e0b", missing_standard_code:"#f59e0b", missing_location:"#f59e0b"
};
const DOMAIN_LABEL = {case:"工程案例", enterprise:"企业标准", standard:"国家/行业规范",
  law:"法规", safety:"安全", quality:"质量"};

let SNAP = JSON.parse(document.getElementById('snapshot').textContent);
let DATA = SNAP; // 当前数据源（默认快照）

function banner(msg){const b=document.getElementById('banner');b.textContent=msg;b.style.display='block';
  clearTimeout(b._t);b._t=setTimeout(()=>b.style.display='none',6000);}

async function api(path, opts={}){
  const base=document.getElementById('apiBase').value.trim().replace(/\/$/,'');
  const key=document.getElementById('apiKey').value.trim();
  const r=await fetch(base+path,{headers:{'X-API-Key':key,'X-Tenant-Id':'default'},...opts});
  if(!r.ok) throw new Error('HTTP '+r.status);
  const j=await r.json();
  if(j && j.code!==0) throw new Error('code '+j.code);
  return j.data;
}

// ---------- 图表 ----------
function donut(segs, w=320, h=220, cx=160, cy=110, rO=92, rI=58){
  const total=segs.reduce((s,x)=>s+x.value,0);
  if(total===0) return `<svg viewBox="0 0 ${w} ${h}"><text x="${cx}" y="${cy+5}" text-anchor="middle" fill="#9ca3af" font-size="13">无问题</text></svg>`;
  let a0=-Math.PI/2, paths="";
  segs.forEach(seg=>{
    const frac=seg.value/total, a1=a0+frac*2*Math.PI, large=(a1-a0)>Math.PI?1:0;
    const x0=cx+rO*Math.cos(a0),y0=cy+rO*Math.sin(a0);
    const x1=cx+rO*Math.cos(a1),y1=cy+rO*Math.sin(a1);
    const xi1=cx+rI*Math.cos(a1),yi1=cy+rI*Math.sin(a1);
    const xi0=cx+rI*Math.cos(a0),yi0=cy+rI*Math.sin(a0);
    paths+=`<path d="M${x0} ${y0} A${rO} ${rO} 0 ${large} 1 ${x1} ${y1} L${xi1} ${yi1} A${rI} ${rI} 0 ${large} 0 ${xi0} ${yi0} Z" fill="${seg.color}" stroke="#fff" stroke-width="1.5"><title>${seg.label}: ${seg.value} (${Math.round(frac*100)}%)</title></path>`;
    a0=a1;
  });
  paths+=`<text x="${cx}" y="${cy-2}" text-anchor="middle" font-size="22" font-weight="800" fill="#1f2937">${total}</text><text x="${cx}" y="${cy+15}" text-anchor="middle" font-size="11" fill="#6b7280">问题总数</text>`;
  return `<svg viewBox="0 0 ${w} ${h}">${paths}</svg>`;
}

function trendChart(points, w=560, h=240, pad=38){
  const n=points.length; if(n===0) return '';
  const x=i=>pad+(n<=1?0:(i/(n-1))*(w-2*pad));
  const y=v=>h-pad-((v-0)/100)*(h-2*pad);
  let s=`<svg viewBox="0 0 ${w} ${h}">`;
  [0,25,50,75,100].forEach(g=>{s+=`<line x1="${pad}" y1="${y(g)}" x2="${w-pad}" y2="${y(g)}" stroke="#eef0f3"/>`+
    `<text x="${pad-7}" y="${y(g)+4}" text-anchor="end" font-size="10" fill="#9ca3af">${g}</text>`;});
  s+=`<line x1="${pad}" y1="${y(80)}" x2="${w-pad}" y2="${y(80)}" stroke="#ef4444" stroke-dasharray="4 3" stroke-width="1.5"/>`+
     `<text x="${w-pad}" y="${y(80)-4}" text-anchor="end" font-size="10" fill="#ef4444">阈值 80</text>`;
  const pts=points.map((p,i)=>`${x(i)},${y(p.score)}`).join(" ");
  s+=`<polyline points="${pts}" fill="none" stroke="#2563eb" stroke-width="2.5"/>`;
  points.forEach((p,i)=>{const c=p.score<80?"#ef4444":"#2563eb";
    s+=`<circle cx="${x(i)}" cy="${y(p.score)}" r="3.6" fill="${c}"><title>${p.created_at} | 质量分 ${p.score} | 问题 ${p.issue_count}</title></circle>`;});
  const idxs=n<=1?[0]:[0,Math.floor((n-1)/2),n-1];
  idxs.forEach(i=>{const lab=(points[i].created_at||"").slice(5,16).replace("T"," ");
    s+=`<text x="${x(i)}" y="${h-12}" text-anchor="middle" font-size="9" fill="#9ca3af">${lab}</text>`;});
  s+=`</svg>`; return s;
}

function issueBars(points, w=560, h=70, pad=38){
  const n=points.length; if(n===0) return '';
  const max=Math.max(...points.map(p=>p.issue_count),1);
  const bw=Math.min(26,(w-2*pad)/n-4);
  let s=`<svg viewBox="0 0 ${w} ${h}">`;
  points.forEach((p,i)=>{const x=pad+(n<=1?0:(i/(n-1))*(w-2*pad))-bw/2;
    const bh=(p.issue_count/max)*(h-22);
    const c=p.issue_count>0?"#f59e0b":"#10b981";
    s+=`<rect x="${x}" y="${h-16-bh}" width="${bw}" height="${bh}" rx="3" fill="${c}" opacity=".85"><title>${p.created_at} 问题 ${p.issue_count}</title></rect>`;});
  s+=`<text x="${pad}" y="12" font-size="10" fill="#9ca3af">每轮问题数</text></svg>`;
  return s;
}

function hbars(items, w=520, h=0, rowH=26, top=6){
  const max=Math.max(...items.map(i=>i.value),1);
  h = top+items.length*rowH+4;
  let s=`<svg viewBox="0 0 ${w} ${h}">`;
  items.forEach((it,i)=>{const y=top+i*rowH;const bw=(it.value/max)*(w-150);
    const col=it.flag?"#ef4444":"#10b981";
    s+=`<text x="4" y="${y+15}" font-size="11" fill="#374151">${it.label}</text>`+
       `<rect x="118" y="${y+4}" width="${Math.max(bw,2)}" height="14" rx="3" fill="${col}" opacity=".85"/>`+
       `<text x="${124+bw}" y="${y+15}" font-size="11" fill="#374151">${it.value}${it.flag?" ⚠":""}</text>`;});
  s+=`</svg>`; return s;
}

// ---------- 渲染 ----------
function aggIssueCounts(reports){
  const m={};
  (reports||[]).forEach(r=>{const ic=r.issue_counts||{};
    for(const k in ic) m[k]=(m[k]||0)+ic[k];});
  return m;
}

function renderKPIs(d){
  const lr=d.latest_report||{};
  const sc=lr.score!=null?lr.score: (d.score_trend&&d.score_trend.latest!=null?d.score_trend.latest:0);
  const ic=lr.issue_count!=null?lr.issue_count:0;
  const hi=(d.score_trend&&d.score_trend.points? d.score_trend.points[d.score_trend.points.length-1].high_issue_count:0);
  const alerts=(d.alerts||[]).filter(a=>!a.resolved).length;
  const vh=lr.vector_health||{};
  const cov=lr.coverage||{};
  const sparse=(cov.sparse_domains||[]).length;
  const scoreCls = sc>=80?'ok':(sc>=60?'warn':'bad');
  const k=[
    {v:sc.toFixed(1), l:'最新质量分', c:scoreCls},
    {v:ic, l:'问题总数', c:ic>0?'warn':'ok'},
    {v:hi, l:'高危问题', c:hi>0?'bad':'ok'},
    {v:(vh.missing||0)+(vh.zero||0), l:'向量缺失/零向量', c:((vh.missing||0)+(vh.zero||0))>0?'bad':'ok'},
    {v:sparse, l:'域覆盖盲区', c:sparse>0?'warn':'ok'},
    {v:alerts, l:'未处理告警', c:alerts>0?'bad':'ok'},
  ];
  document.getElementById('kpis').innerHTML = k.map(x=>
    `<div class="kpi"><div class="v ${x.c}">${x.v}</div><div class="l">${x.l}</div></div>`).join('');
}

function renderTrend(d){
  const pts=(d.score_trend&&d.score_trend.points)||[];
  document.getElementById('trendChart').innerHTML = trendChart(pts);
  document.getElementById('issueBars').innerHTML = issueBars(pts);
  document.getElementById('trendTag').textContent = pts.length? (pts.length+' 个快照'):'';
}

function renderDonut(d){
  const ic=aggIssueCounts(d.reports);
  const segs=Object.keys(ic).map(k=>({label:ISSUE_LABEL[k]||k, value:ic[k], color:ISSUE_COLOR[k]||'#94a3b8'}));
  segs.sort((a,b)=>b.value-a.value);
  document.getElementById('donut').innerHTML = donut(segs);
  document.getElementById('donutLegend').innerHTML = segs.map(s=>
    `<span><i class="dot" style="background:${s.color}"></i>${s.label} ${s.value}</span>`).join('');
}

function renderCoverage(d){
  const cov=(d.latest_report&&d.latest_report.coverage)||{};
  const dc=cov.domain_counts||{};
  const sparse=new Set(cov.sparse_domains||[]);
  const items=Object.keys(dc).map(k=>({label:DOMAIN_LABEL[k]||k, value:dc[k], flag:sparse.has(k)}));
  items.sort((a,b)=>b.value-a.value);
  document.getElementById('coverage').innerHTML = items.length? hbars(items) :
    '<p class="muted">无域覆盖数据（早期快照）。触发一次新巡检可补充。</p>';
}

function renderVectorHealth(d){
  const vh=(d.latest_report&&d.latest_report.vector_health)||null;
  const el=document.getElementById('vectorHealth');
  document.getElementById('vhTag').textContent = vh? (vh.note? 'note':'ok'):'';
  if(!vh){el.innerHTML='<p class="muted">无向量体检数据（早期快照）。</p>';return;}
  const tiles=[
    {v:vh.checked||0,l:'已检'}, {v:vh.missing||0,l:'缺失',bad:(vh.missing||0)>0},
    {v:vh.zero||0,l:'零向量',bad:(vh.zero||0)>0}
  ];
  let h='<div class="tiles">'+tiles.map(t=>
    `<div class="tile"><div class="tv ${t.bad?'bad':''}">${t.v}</div><div class="tl">${t.l}</div></div>`).join('')+'</div>';
  if(vh.note) h+='<p class="muted" style="margin-top:10px">'+vh.note+'</p>';
  el.innerHTML=h;
}

function renderAlerts(d){
  const al=d.alerts||[];
  document.getElementById('alertTag').textContent = al.filter(a=>!a.resolved).length+' 未处理';
  if(!al.length){document.getElementById('alerts').innerHTML='<p class="muted">暂无告警。</p>';return;}
  let h='<table><thead><tr><th>级别</th><th>标题</th><th>质量分</th><th>状态</th><th>时间</th></tr></thead><tbody>';
  al.forEach(a=>{const sev=a.severity==='high'?'p-high':(a.severity==='medium'?'p-med':'p-low');
    const st=a.resolved?'<span class="pill p-ok">已处理</span>':'<span class="pill p-high">未处理</span>';
    h+=`<tr><td><span class="pill ${sev}">${a.severity}</span></td><td>${a.title}</td>`+
       `<td>${a.score}</td><td>${st}</td><td class="muted">${(a.created_at||'').replace('T',' ')}</td></tr>`;});
  h+='</tbody></table>';
  document.getElementById('alerts').innerHTML=h;
}

function renderHist(d){
  const reps=(d.reports||[]).slice().sort((a,b)=>b.created_at.localeCompare(a.created_at));
  const tb=document.querySelector('#histTable tbody');
  tb.innerHTML = reps.map(r=>{
    const ic=r.issue_counts||{};
    const dist=Object.keys(ic).map(k=>`${ISSUE_LABEL[k]||k}:${ic[k]}`).join('、')||'—';
    const scCls=r.score<80?'bad':(r.score<90?'warn':'ok');
    return `<tr class="click" data-id="${r.id}"><td class="muted">${(r.created_at||'').replace('T',' ')}</td>`+
      `<td>${r.scope==='all'?'全库':'单库'}</td>`+
      `<td class="${scCls}" style="font-weight:700">${r.score}</td>`+
      `<td>${r.issue_count}</td><td class="muted">${dist}</td>`+
      `<td class="muted">${r.total_chunks||0}/${r.total_docs||0}</td></tr>`;
  }).join('');
  tb.querySelectorAll('tr.click').forEach(tr=>tr.onclick=()=>showReport(tr.dataset.id));
}

function renderKBSelect(d){
  const sel=document.getElementById('kbSel');
  const opts=['<option value="">全库（所有知识库）</option>']
    .concat((d.knowledge_bases||[]).map(k=>`<option value="${k.id}">${k.name}（${DOMAIN_LABEL[k.domain]||k.domain}）</option>`));
  sel.innerHTML=opts.join('');
  sel.onchange=()=>drill(sel.value);
}

async function drill(kbId){
  const el=document.getElementById('drill');
  if(!kbId){el.innerHTML='<p class="muted">选择具体知识库以查看其巡检趋势与问题占比。</p>';return;}
  el.innerHTML='<p class="muted">加载中…</p>';
  try{
    const [tr,reps]=await Promise.all([
      api('/quality/score-trend?kb_id='+kbId+'&limit=100&threshold=80'),
      api('/quality/reports?kb_id='+kbId+'&page=1&page_size=50')
    ]);
    const repList=(reps.items||reps.list||[]);
    if(!repList.length){
      el.innerHTML='<p class="muted">该知识库暂无巡检历史。</p>'+
        '<button class="btn" id="seedKb">立即巡检该库</button>';
      document.getElementById('seedKb').onclick=async()=>{
        el.innerHTML='<p class="muted">巡检中（可能需 10–30s）…</p>';
        try{await api('/quality/inspect',{method:'POST',body:JSON.stringify({kb_id:kbId,persist:true})});
          banner('已触发巡检，稍后重新选择该库即可看到数据');}
        catch(e){banner('巡检失败：'+e.message);}
      };
      return;
    }
    const ic=aggIssueCounts(repList);
    const pts=tr.points||[];
    const latest=repList[0]||{};
    let h='<div class="tiles" style="margin-bottom:10px">'+
      `<div class="tile"><div class="tv">${(latest.score!=null?latest.score:0).toFixed(1)}</div><div class="tl">最新质量分</div></div>`+
      `<div class="tile"><div class="tv">${latest.issue_count||0}</div><div class="tl">问题数</div></div>`+
      `<div class="tile"><div class="tv">${repList.length}</div><div class="tl">巡检次数</div></div></div>`;
    h+=trendChart(pts);
    const segs=Object.keys(ic).map(k=>({label:ISSUE_LABEL[k]||k,value:ic[k],color:ISSUE_COLOR[k]||'#94a3b8'})).sort((a,b)=>b.value-a.value);
    h+='<div style="margin-top:8px">'+donut(segs)+'</div>';
    el.innerHTML=h;
  }catch(e){el.innerHTML='<p class="muted">拉取失败：'+e.message+'（可能跨域受限，使用快照数据）</p>';}
}

async function showReport(id){
  const box=document.getElementById('reportDetail');
  box.style.display='block'; box.innerHTML='<p class="muted">加载明细…</p>';
  try{
    const r=await api('/quality/reports/'+id);
    const cov=r.coverage||{}; const vh=r.vector_health||null;
    const issues=(r.issues||[]);
    let h=`<h3 style="margin-top:0">报告明细 · ${(r.created_at||'').replace('T',' ')}</h3>`;
    h+=`<p class="muted">质量分 ${r.score} · 问题 ${r.issue_count} · 切片 ${r.total_chunks} · 文档 ${r.total_docs}</p>`;
    const dc=cov.domain_counts||{}; const sparse=new Set(cov.sparse_domains||[]);
    const items=Object.keys(dc).map(k=>({label:DOMAIN_LABEL[k]||k,value:dc[k],flag:sparse.has(k)})).sort((a,b)=>b.value-a.value);
    if(items.length) h+='<div style="margin:10px 0"><b>域覆盖</b>'+hbars(items)+'</div>';
    if(vh) h+=`<div style="margin:10px 0"><b>向量体检</b><div class="tiles">`+
      [`已检:${vh.checked||0}`,`缺失:${vh.missing||0}`,`零向量:${vh.zero||0}`].map(t=>
        `<div class="tile"><div class="tv">${t.split(':')[1]}</div><div class="tl">${t.split(':')[0]}</div></div>`).join('')+
      `</div>${vh.note?`<p class="muted" style="margin-top:6px">${vh.note}</p>`:''}</div>`;
    if(issues.length){
      h+='<div style="margin:10px 0"><b>问题明细（前 20）</b><table><thead><tr><th>类型</th><th>级别</th><th>说明</th></tr></thead><tbody>'+
        issues.slice(0,20).map(i=>{
          const sev=i.severity==='high'?'p-high':(i.severity==='medium'?'p-med':'p-low');
          return `<tr><td>${ISSUE_LABEL[i.issue_type]||i.issue_type}</td><td><span class="pill ${sev}">${i.severity}</span></td><td class="muted">${i.detail||i.suggestion||''}</td></tr>`;
        }).join('')+'</tbody></table></div>';
    }
    if((r.suggestions||[]).length) h+='<div class="muted">建议：'+(r.suggestions||[]).join('；')+'</div>';
    box.innerHTML=h;
    box.scrollIntoView({behavior:'smooth'});
  }catch(e){box.innerHTML='<p class="muted">明细加载失败：'+e.message+'</p>';}
}

function renderAll(d){
  renderKPIs(d); renderTrend(d); renderDonut(d); renderCoverage(d);
  renderVectorHealth(d); renderAlerts(d); renderHist(d); renderKBSelect(d);
  const src = (d===SNAP)? '内嵌快照（'+ (SNAP.generated_at||'').replace('T',' ')+'）' : '实时数据';
  document.getElementById('subtitle').textContent =
    `数据源：${src} · 报告 ${d.reports.length} · 知识库 ${(d.knowledge_bases||[]).length} · 告警 ${(d.alerts||[]).length}`;
}

function loadSnapshot(){ DATA=SNAP; renderAll(SNAP); }

async function refresh(){
  try{
    const [health,kb,reps,tr,al]=await Promise.all([
      api('/health',{}).catch(()=>({})),
      api('/knowledge/kb?page_size=200').then(x=>Array.isArray(x)?x:(x.items||x.list||[])).catch(()=>SNAP.knowledge_bases||[]),
      api('/quality/reports?page=1&page_size=50').then(x=>x.items||x.list||[]).catch(()=>SNAP.reports||[]),
      api('/quality/score-trend?limit=100&threshold=80').catch(()=>SNAP.score_trend||{}),
      api('/quality/alerts?page=1&page_size=50').then(x=>x.items||x.list||[]).catch(()=>SNAP.alerts||[])
    ]);
    const latestId=(reps[0]||{}).id;
    const latest=latestId? await api('/quality/reports/'+latestId).catch(()=>SNAP.latest_report||{}) : SNAP.latest_report;
    DATA={health, knowledge_bases:kb, reports:reps, score_trend:tr, alerts:al, latest_report:latest};
    renderAll(DATA); banner('已刷新实时数据');
  }catch(e){ loadSnapshot(); banner('实时拉取失败（'+e.message+'），已回退快照数据'); }
}

document.getElementById('refresh').onclick=refresh;
// 初始：用快照保证可渲染；若浏览器允许跨域再尝试实时
loadSnapshot();
if(window.location.protocol!=='file:'){ refresh().catch(()=>{}); }
</script>
</body>
</html>
"""

def main():
    with open(SNAP, encoding="utf-8") as f:
        snap = json.load(f)
    html = HTML.replace("__SNAPSHOT_JSON__", json.dumps(snap, ensure_ascii=False))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    os.makedirs(os.path.dirname(REPO_OUT), exist_ok=True)
    with open(REPO_OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"WROTE {OUT} ({len(html)} bytes)")
    print(f"WROTE {REPO_OUT} ({len(html)} bytes)")

if __name__ == "__main__":
    main()
