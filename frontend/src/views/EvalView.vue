<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { evalApi } from '@/api'

const apiKey = ref('tf-admin-seed-key')
const loading = ref(false)
const result = ref<any>(null)
const golden = ref<any[]>([])
const goldenLoading = ref(false)

// 新增黄金集样本表单
const showAdd = ref(false)
const form = ref({ id: '', query: '', expected_intent: 'spec_lookup', relevant_chunk_ids: '', note: '' })

// 趋势
const trend = ref<any>(null)
const runs = ref<any[]>([])
const trendLoading = ref(false)
const runNote = ref('')

const agg = computed(() => result.value?.aggregated || {})
const perQuery = computed(() => result.value?.per_query || [])

const statusMeta: Record<string, { label: string; type: string }> = {
  improved: { label: '↑ 优于基线', type: 'success' },
  ok: { label: '持平', type: 'info' },
  regressed: { label: '↓ 低于基线', type: 'danger' }
}

// ---- 内联 SVG 多折线趋势图（零依赖）----
const SERIES = [
  { key: 'recall_at_5', name: 'Recall@5', color: '#2a5bd7' },
  { key: 'ndcg_at_5', name: 'NDCG@5', color: '#e6a23c' },
  { key: 'mrr', name: 'MRR', color: '#1a9d5a' },
  { key: 'correct_rejection_rate', name: '正确拒答率', color: '#909399' }
]
const chart = computed(() => {
  const pts = trend.value?.points || []
  const W = 720, H = 260, PL = 44, PR = 16, PT = 16, PB = 34
  const iw = W - PL - PR, ih = H - PT - PB
  const n = pts.length
  const x = (i: number) => n <= 1 ? PL + iw / 2 : PL + (iw * i) / (n - 1)
  const y = (v: number) => PT + ih * (1 - Math.max(0, Math.min(1, v)))
  const lines = SERIES.map(s => ({
    ...s,
    d: pts.map((p: any, i: number) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p[s.key] ?? 0).toFixed(1)}`).join(' '),
    dots: pts.map((p: any, i: number) => ({ cx: x(i), cy: y(p[s.key] ?? 0), v: p[s.key] ?? 0 }))
  }))
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(v => ({ v, y: y(v) }))
  // 基线水平参考线（Recall@5）
  const baseR5 = trend.value?.baseline?.recall_at_5
  const baseLine = (baseR5 != null) ? { y: y(baseR5), v: baseR5 } : null
  const xLabels = pts.map((p: any, i: number) => ({ x: x(i), t: String(p.created_at || '').slice(5, 16).replace('T', ' ') }))
  return { W, H, PL, PR, PT, lines, yTicks, baseLine, xLabels, n }
})

async function loadTrend() {
  if (!apiKey.value) return
  trendLoading.value = true
  try {
    const [t, rs] = await Promise.all([
      evalApi.trend(apiKey.value, { limit: 30 }),
      evalApi.runs(apiKey.value, { page: 1, page_size: 30 })
    ])
    trend.value = t.data
    runs.value = rs.data?.items || []
  } catch (e: any) { /* ignore */ }
  finally { trendLoading.value = false }
}

async function removeRun(id: string) {
  try {
    await ElMessageBox.confirm(`确认删除该评测快照？`, '提示', { type: 'warning' })
  } catch { return }
  try {
    await evalApi.deleteRun(apiKey.value, id)
    ElMessage.success('已删除快照')
    await loadTrend()
  } catch (e: any) { /* ignore */ }
}

const intentLabel: Record<string, string> = {
  spec_lookup: '规范查询', quality_diagnosis: '质量分析',
  case_retrieval: '案例检索', scheme_generation: '方案生成',
  out_of_scope: '越域', chitchat: '闲聊', unknown: '未知'
}

async function runEval() {
  if (!apiKey.value) { ElMessage.warning('请填写 API Key'); return }
  loading.value = true
  try {
    const r = await evalApi.run(apiKey.value, {
      persist: true, source: 'api', note: runNote.value
    })
    result.value = r.data
    runNote.value = ''
    ElMessage.success(r.message || '评测完成')
    await loadTrend()
  } catch (e: any) {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function loadGolden() {
  if (!apiKey.value) return
  goldenLoading.value = true
  try {
    const r = await evalApi.golden(apiKey.value)
    golden.value = r.data?.items || []
  } catch (e: any) { /* ignore */ }
  finally { goldenLoading.value = false
  }
}

async function submitAdd() {
  if (!form.value.query || !form.value.relevant_chunk_ids) {
    ElMessage.warning('查询与相关 chunk_id 必填')
    return
  }
  const payload = {
    id: form.value.id || undefined,
    query: form.value.query,
    expected_intent: form.value.expected_intent,
    relevant_chunk_ids: form.value.relevant_chunk_ids.split(/[,\s]+/).filter(Boolean),
    note: form.value.note
  }
  try {
    await evalApi.addGolden(apiKey.value, payload)
    ElMessage.success('已添加样本')
    showAdd.value = false
    form.value = { id: '', query: '', expected_intent: 'spec_lookup', relevant_chunk_ids: '', note: '' }
    await loadGolden()
  } catch (e: any) { /* ignore */ }
}

async function removeItem(id: string) {
  try {
    await ElMessageBox.confirm(`确认删除样本 ${id}？`, '提示', { type: 'warning' })
  } catch { return }
  try {
    await evalApi.deleteGolden(apiKey.value, id)
    ElMessage.success('已删除')
    await loadGolden()
  } catch (e: any) { /* ignore */ }
}

onMounted(() => { loadGolden(); loadTrend() })
</script>

<template>
  <div class="eval-wrap">
    <el-card shadow="never" class="tf-card">
      <template #header>
        <div class="eval-head">
          <span>检索评测看板</span>
          <div class="eval-head-right">
            <el-input v-model="apiKey" size="small" placeholder="X-API-Key" style="width: 170px" />
            <el-input v-model="runNote" size="small" placeholder="本次改动备注（可选）" style="width: 180px" />
            <el-button type="primary" size="small" :loading="loading" @click="runEval">运行评测</el-button>
            <el-button size="small" :loading="goldenLoading" @click="loadGolden">刷新黄金集</el-button>
          </div>
        </div>
      </template>

      <el-alert
        v-if="!result"
        title="点击「运行评测」对当前租户知识库跑真实检索管线，计算 Recall@K / MRR / NDCG@K 与正确拒答率。"
        type="info" :closable="false" show-icon />

      <template v-else>
        <!-- 指标卡 -->
        <el-row :gutter="12" class="metric-row">
          <el-col :span="6"><div class="metric"><span class="m-val">{{ (agg.hit_rate * 100).toFixed(1) }}%</span><span class="m-lab">命中率</span></div></el-col>
          <el-col :span="6"><div class="metric"><span class="m-val">{{ (agg.correct_rejection_rate * 100).toFixed(1) }}%</span><span class="m-lab">正确拒答率</span></div></el-col>
          <el-col :span="6"><div class="metric"><span class="m-val">{{ (agg.delivered_mrr).toFixed(3) }}</span><span class="m-lab">MRR</span></div></el-col>
          <el-col :span="6"><div class="metric"><span class="m-val">{{ (agg.below_floor_rate * 100).toFixed(1) }}%</span><span class="m-lab">地板拒答率</span></div></el-col>
          <el-col :span="6"><div class="metric"><span class="m-val">{{ agg['delivered_recall@k']?.['1']?.toFixed(3) }}</span><span class="m-lab">Recall@1</span></div></el-col>
          <el-col :span="6"><div class="metric"><span class="m-val">{{ agg['delivered_recall@k']?.['3']?.toFixed(3) }}</span><span class="m-lab">Recall@3</span></div></el-col>
          <el-col :span="6"><div class="metric"><span class="m-val">{{ agg['delivered_recall@k']?.['5']?.toFixed(3) }}</span><span class="m-lab">Recall@5</span></div></el-col>
          <el-col :span="6"><div class="metric"><span class="m-val">{{ (agg['candidate_recall@20'] * 100).toFixed(1) }}%</span><span class="m-lab">候选Recall@20</span></div></el-col>
        </el-row>
        <div class="agg-meta">
          样本 {{ result.n_queries }}（正 {{ result.n_positive }} / 负 {{ result.n_negative }}）｜
          NDCG@5={{ agg['delivered_ndcg@k']?.['5']?.toFixed(3) }}
          <template v-if="result.status">
            ｜相对基线：
            <el-tag size="small" :type="(statusMeta[result.status]?.type as any) || 'info'">
              {{ statusMeta[result.status]?.label || result.status }}
            </el-tag>
            <span v-for="(v, k) in (result.baseline_delta || {})" :key="k" class="delta-chip"
                  :class="v > 0 ? 'up' : (v < 0 ? 'down' : '')">
              {{ k }} {{ v > 0 ? '+' : '' }}{{ v }}
            </span>
            <span v-if="result.duration_ms">｜耗时 {{ result.duration_ms }}ms</span>
          </template>
        </div>

        <!-- 逐题明细 -->
        <h4 class="sec-title">逐题明细</h4>
        <el-table :data="perQuery" size="small" border max-height="420" stripe>
          <el-table-column prop="query" label="查询" min-width="220" show-overflow-tooltip />
          <el-table-column label="期望意图" width="100">
            <template #default="{ row }">{{ intentLabel[row.expected_intent] || row.expected_intent }}</template>
          </el-table-column>
          <el-table-column label="实际意图" width="100">
            <template #default="{ row }"><el-tag size="small" :type="row.negative ? 'info' : 'success'">{{ intentLabel[row.intent] || row.intent }}</el-tag></template>
          </el-table-column>
          <el-table-column label="命中/相关" width="90" align="center">
            <template #default="{ row }">
              <span :class="row.hits_delivered > 0 ? 'ok' : 'bad'">{{ row.hits_delivered }}/{{ row.relevant_count }}</span>
            </template>
          </el-table-column>
          <el-table-column label="Recall@5" width="90" align="center">
            <template #default="{ row }">{{ (row.delivered_metrics?.recall?.['5'] ?? 0).toFixed(3) }}</template>
          </el-table-column>
          <el-table-column label="MRR" width="80" align="center">
            <template #default="{ row }">{{ (row.delivered_metrics?.mrr ?? 0).toFixed(3) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.negative" size="small" :type="row.hits_delivered === 0 ? 'success' : 'danger'">
                {{ row.hits_delivered === 0 ? '正确拒答' : '误召回' }}
              </el-tag>
              <el-tag v-else size="small" :type="row.below_floor ? 'warning' : 'success'">
                {{ row.below_floor ? '地板拦截' : '已命中' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>

    <!-- 评测趋势 -->
    <el-card shadow="never" class="tf-card">
      <template #header>
        <div class="eval-head">
          <span>评测趋势（近 {{ trend?.count || 0 }} 次）</span>
          <div class="eval-head-right">
            <el-tag v-if="trend?.regressed_count" size="small" type="danger">回归 {{ trend.regressed_count }}</el-tag>
            <el-tag v-if="trend?.improved_count" size="small" type="success">改进 {{ trend.improved_count }}</el-tag>
            <el-button size="small" :loading="trendLoading" @click="loadTrend">刷新趋势</el-button>
          </div>
        </div>
      </template>

      <el-alert v-if="!trend?.count" type="info" :closable="false" show-icon
        title="暂无历史快照。每次「运行评测」会自动落库一次快照，累计 2 次以上即可看到趋势曲线。" />

      <template v-else>
        <!-- 图例 -->
        <div class="legend">
          <span v-for="s in SERIES" :key="s.key" class="lg-item">
            <i class="lg-dot" :style="{ background: s.color }"></i>{{ s.name }}
          </span>
          <span class="lg-item"><i class="lg-dash"></i>基线 Recall@5</span>
        </div>

        <!-- 内联 SVG 折线图 -->
        <div class="chart-box">
          <svg :viewBox="`0 0 ${chart.W} ${chart.H}`" class="trend-svg">
            <!-- 网格与 Y 轴刻度 -->
            <g>
              <line v-for="t in chart.yTicks" :key="'g' + t.v"
                    :x1="chart.PL" :y1="t.y" :x2="chart.W - chart.PR" :y2="t.y"
                    stroke="#e8edf5" stroke-width="1" />
              <text v-for="t in chart.yTicks" :key="'l' + t.v"
                    :x="chart.PL - 8" :y="t.y + 4" text-anchor="end"
                    font-size="10" fill="#8595a8">{{ t.v.toFixed(2) }}</text>
            </g>
            <!-- 基线参考线 -->
            <g v-if="chart.baseLine">
              <line :x1="chart.PL" :y1="chart.baseLine.y" :x2="chart.W - chart.PR" :y2="chart.baseLine.y"
                    stroke="#d9534f" stroke-width="1.2" stroke-dasharray="5 4" opacity="0.75" />
              <text :x="chart.W - chart.PR" :y="chart.baseLine.y - 5" text-anchor="end"
                    font-size="10" fill="#d9534f">基线 {{ chart.baseLine.v.toFixed(3) }}</text>
            </g>
            <!-- 折线 -->
            <g v-for="s in chart.lines" :key="s.key">
              <path :d="s.d" fill="none" :stroke="s.color" stroke-width="2"
                    stroke-linejoin="round" stroke-linecap="round" />
              <circle v-for="(dt, i) in s.dots" :key="i" :cx="dt.cx" :cy="dt.cy" r="3"
                      :fill="s.color" stroke="#fff" stroke-width="1.5">
                <title>{{ s.name }} = {{ dt.v?.toFixed(4) }}</title>
              </circle>
            </g>
            <!-- X 轴标签（稀疏显示，避免重叠） -->
            <g>
              <text v-for="(xl, i) in chart.xLabels" :key="i"
                    v-show="chart.n <= 8 || i % Math.ceil(chart.n / 8) === 0 || i === chart.n - 1"
                    :x="xl.x" :y="chart.H - 12" text-anchor="middle"
                    font-size="9" fill="#8595a8">{{ xl.t }}</text>
            </g>
          </svg>
        </div>

        <div v-if="Object.keys(trend.first_to_latest_delta || {}).length" class="agg-meta">
          首次 → 最新变化：
          <span v-for="(v, k) in trend.first_to_latest_delta" :key="k" class="delta-chip"
                :class="v > 0 ? 'up' : (v < 0 ? 'down' : '')">
            {{ k }} {{ v > 0 ? '+' : '' }}{{ v }}
          </span>
        </div>

        <!-- 历史快照 -->
        <h4 class="sec-title">历史快照</h4>
        <el-table :data="runs" size="small" border max-height="300" stripe>
          <el-table-column label="时间" width="150">
            <template #default="{ row }">{{ String(row.created_at || '').slice(0, 19).replace('T', ' ') }}</template>
          </el-table-column>
          <el-table-column label="来源" width="80" align="center">
            <template #default="{ row }"><el-tag size="small" effect="plain">{{ row.source }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="n_queries" label="样本" width="70" align="center" />
          <el-table-column label="Recall@5" width="90" align="center">
            <template #default="{ row }">{{ (row.recall_at_5 ?? 0).toFixed(4) }}</template>
          </el-table-column>
          <el-table-column label="NDCG@5" width="90" align="center">
            <template #default="{ row }">{{ (row.ndcg_at_5 ?? 0).toFixed(4) }}</template>
          </el-table-column>
          <el-table-column label="MRR" width="80" align="center">
            <template #default="{ row }">{{ (row.mrr ?? 0).toFixed(4) }}</template>
          </el-table-column>
          <el-table-column label="拒答率" width="80" align="center">
            <template #default="{ row }">{{ ((row.correct_rejection_rate ?? 0) * 100).toFixed(0) }}%</template>
          </el-table-column>
          <el-table-column label="相对基线" width="110" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="(statusMeta[row.status]?.type as any) || 'info'">
                {{ statusMeta[row.status]?.label || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="80" align="center">
            <template #default="{ row }">{{ row.duration_ms }}ms</template>
          </el-table-column>
          <el-table-column prop="note" label="备注" min-width="140" show-overflow-tooltip />
          <el-table-column label="操作" width="70" align="center">
            <template #default="{ row }">
              <el-button size="small" type="danger" link @click="removeRun(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>

    <!-- 黄金集管理 -->
    <el-card shadow="never" class="tf-card">
      <template #header>
        <div class="eval-head">
          <span>黄金评测集（{{ golden.length }}）</span>
          <el-button size="small" type="primary" @click="showAdd = true">新增样本</el-button>
        </div>
      </template>
      <el-table :data="golden" size="small" border max-height="360" stripe>
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="query" label="查询" min-width="240" show-overflow-tooltip />
        <el-table-column label="意图" width="100">
          <template #default="{ row }">{{ intentLabel[row.expected_intent] || row.expected_intent }}</template>
        </el-table-column>
        <el-table-column prop="relevant_count" label="相关数" width="80" align="center" />
        <el-table-column prop="note" label="备注" min-width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button size="small" type="danger" link @click="removeItem(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增样本对话框 -->
    <el-dialog v-model="showAdd" title="新增评测样本" width="520px">
      <el-form label-width="110px">
        <el-form-item label="ID（可选）"><el-input v-model="form.id" placeholder="留空自动生成" /></el-form-item>
        <el-form-item label="查询"><el-input v-model="form.query" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="期望意图">
          <el-select v-model="form.expected_intent">
            <el-option v-for="(v, k) in intentLabel" :key="k" :label="v" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="相关 chunk_id">
          <el-input v-model="form.relevant_chunk_ids" type="textarea" :rows="2" placeholder="逗号或空格分隔" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.note" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" @click="submitAdd">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.eval-wrap { display: flex; flex-direction: column; gap: 14px; }
.tf-card { border-radius: 10px; }
.eval-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.eval-head-right { display: flex; gap: 8px; align-items: center; }
.metric-row { margin-bottom: 6px; }
.metric { background: #f5f8ff; border: 1px solid #e6eefc; border-radius: 8px; padding: 12px 10px; text-align: center; }
.m-val { display: block; font-size: 22px; font-weight: 700; color: #2a5bd7; }
.m-lab { display: block; font-size: 12px; color: #6b7a90; margin-top: 4px; }
.agg-meta { font-size: 12px; color: #8595a8; margin: 8px 0 4px; }
.sec-title { margin: 14px 0 8px; font-size: 14px; color: #2c3a4b; }
.ok { color: #1a9d5a; font-weight: 600; }
.bad { color: #d9534f; font-weight: 600; }
.delta-chip { display: inline-block; margin-left: 6px; padding: 0 6px; border-radius: 4px;
  font-size: 11px; background: #eef2f8; color: #6b7a90; }
.delta-chip.up { background: #e7f6ee; color: #1a9d5a; }
.delta-chip.down { background: #fbe9e8; color: #d9534f; }
.legend { display: flex; gap: 16px; flex-wrap: wrap; margin: 4px 0 8px; font-size: 12px; color: #6b7a90; }
.lg-item { display: inline-flex; align-items: center; gap: 5px; }
.lg-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.lg-dash { width: 16px; height: 0; border-top: 2px dashed #d9534f; display: inline-block; }
.chart-box { width: 100%; background: #fbfcfe; border: 1px solid #eef2f8; border-radius: 8px; padding: 6px; }
.trend-svg { width: 100%; height: auto; display: block; }
</style>
