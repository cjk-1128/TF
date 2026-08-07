<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { qualityApi } from '@/api'

const apiKey = ref('tf-admin-seed-key')
const loading = ref(false)
const reportsLoading = ref(false)
const result = ref<any>(null)
const reports = ref<any[]>([])

// 巡检参数（高级）
const showConfig = ref(false)
const cfg = ref({
  kb_id: '',
  dup_threshold: 0.92,
  orphan_threshold: 0.12,
  max_chunk_chars: 1200,
  min_chunk_chars: 40,
  run_recall_probe: true,
  persist: true
})

// 趋势 + 告警
const scoreTrend = ref<any>(null)
const scoreTrendLoading = ref(false)
const alerts = ref<any[]>([])
const alertLoading = ref(false)
const alertFilter = ref<'all' | 'open' | 'resolved'>('all')
const scoreThreshold = ref(80)
const newHighThreshold = ref(1)
const scheduleRunning = ref(false)

const issueLabel: Record<string, string> = {
  oversized_chunk: '超大切片',
  tiny_chunk: '碎片切片',
  missing_standard_code: '缺规范编号',
  missing_location: '缺条文定位',
  duplicate_chunk: '近重复切片',
  orphan_chunk: '孤立切片',
  low_recall_intent: '低召回意图'
}
const sevType: Record<string, string> = { high: 'danger', medium: 'warning', low: 'info' }
const alertTypeMeta: Record<string, { label: string; type: string }> = {
  low_score: { label: '质量分偏低', type: 'danger' },
  new_high_severity: { label: '新增高危问题', type: 'warning' }
}
const alertStatusMeta: Record<string, { label: string; type: string }> = {
  open: { label: '未解决', type: 'danger' },
  resolved: { label: '已解决', type: 'success' }
}

const counts = computed(() => result.value?.issue_counts || {})
const issues = computed(() => result.value?.issues || [])
const scoreColor = computed(() => {
  const s = result.value?.score ?? 100
  return s >= 85 ? '#1a9d5a' : s >= 60 ? '#e6a23c' : '#d9534f'
})

// ---- 内联 SVG 质量分趋势图（0~100，带阈值参考线）----
const scoreChart = computed(() => {
  const pts = scoreTrend.value?.points || []
  const W = 720, H = 260, PL = 44, PR = 16, PT = 16, PB = 34
  const iw = W - PL - PR, ih = H - PT - PB
  const n = pts.length
  const x = (i: number) => n <= 1 ? PL + iw / 2 : PL + (iw * i) / (n - 1)
  const y = (v: number) => PT + ih * (1 - Math.max(0, Math.min(100, v)) / 100)
  const d = pts.map((p: any, i: number) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.score ?? 100).toFixed(1)}`).join(' ')
  const dots = pts.map((p: any, i: number) => ({ cx: x(i), cy: y(p.score ?? 100), v: p.score ?? 100, hi: p.high_issue_count || 0 }))
  const yTicks = [0, 20, 40, 60, 80, 100].map(v => ({ v, y: y(v) }))
  const baseY = y(scoreThreshold.value)
  const xLabels = pts.map((p: any, i: number) => ({ x: x(i), t: String(p.created_at || '').slice(5, 16).replace('T', ' ') }))
  return { W, H, PL, PR, PT, d, dots, yTicks, baseY, xLabels, n }
})
const openAlertCount = computed(() => alerts.value.filter((a: any) => !a.resolved).length)

async function runInspect() {
  if (!apiKey.value) { ElMessage.warning('请填写 API Key'); return }
  loading.value = true
  try {
    const payload: any = { ...cfg.value }
    if (!payload.kb_id) delete payload.kb_id
    const r = await qualityApi.inspect(apiKey.value, payload)
    result.value = r.data
    ElMessage.success(r.message || '巡检完成')
    await loadReports()
  } catch (e: any) { /* 拦截器已提示 */ }
  finally { loading.value = false }
}

async function loadReports() {
  if (!apiKey.value) return
  reportsLoading.value = true
  try {
    const r = await qualityApi.reports(apiKey.value, { page: 1, page_size: 10 })
    reports.value = r.data?.items || []
  } catch (e: any) { /* ignore */ }
  finally { reportsLoading.value = false }
}

async function viewReport(id: string) {
  try {
    const r = await qualityApi.report(apiKey.value, id)
    result.value = r.data
  } catch (e: any) { /* ignore */ }
}

async function convertIssue(row: any) {
  try {
    await ElMessageBox.confirm(
      `将「${issueLabel[row.issue_type] || row.issue_type}」问题采纳为治理任务？`,
      '采纳为治理任务', { type: 'warning' })
  } catch { return }
  try {
    await qualityApi.convert(apiKey.value, {
      issue_type: row.issue_type,
      doc_id: row.doc_id || '',
      kb_id: row.kb_id || '',
      title: `[质量巡检] ${issueLabel[row.issue_type] || row.issue_type} - ${row.doc_title || ''}`,
      detail: row.detail || '',
      suggestion: row.suggestion || '',
      priority: row.severity === 'high' ? 'high' : row.severity === 'low' ? 'low' : 'medium'
    })
    ElMessage.success('已生成治理任务，可在「知识治理」查看')
  } catch (e: any) { /* ignore */ }
}

async function loadScoreTrend() {
  if (!apiKey.value) return
  scoreTrendLoading.value = true
  try {
    const r = await qualityApi.scoreTrend(apiKey.value, { limit: 30, threshold: scoreThreshold.value })
    scoreTrend.value = r.data
  } catch (e: any) { /* ignore */ }
  finally { scoreTrendLoading.value = false }
}

async function loadAlerts() {
  if (!apiKey.value) return
  alertLoading.value = true
  try {
    const params: any = { page: 1, page_size: 50 }
    if (alertFilter.value === 'open') params.resolved = false
    else if (alertFilter.value === 'resolved') params.resolved = true
    const r = await qualityApi.alerts(apiKey.value, params)
    alerts.value = r.data?.items || []
  } catch (e: any) { /* ignore */ }
  finally { alertLoading.value = false }
}

async function triggerSchedule() {
  if (!apiKey.value) { ElMessage.warning('请填写 API Key'); return }
  scheduleRunning.value = true
  try {
    const r = await qualityApi.triggerSchedule(apiKey.value, {
      score_threshold: scoreThreshold.value,
      new_high_threshold: newHighThreshold.value
    })
    const a = r.data?.alerts || []
    ElMessage.success(r.message || '巡检完成')
    if (a.length) {
      ElMessage.warning(`触发 ${a.length} 条告警，请在下方告警列表查看`)
    }
    await Promise.all([loadReports(), loadScoreTrend(), loadAlerts()])
  } catch (e: any) { /* 拦截器已提示 */ }
  finally { scheduleRunning.value = false }
}

async function resolveOne(row: any) {
  try {
    await ElMessageBox.confirm('将该告警标记为已解决？', '解决告警', { type: 'warning' })
  } catch { return }
  try {
    await qualityApi.resolveAlert(apiKey.value, row.id)
    ElMessage.success('告警已解决')
    await loadAlerts()
  } catch (e: any) { /* ignore */ }
}

async function removeAlert(row: any) {
  try {
    await ElMessageBox.confirm('确认删除该告警记录？', '提示', { type: 'warning' })
  } catch { return }
  try {
    await qualityApi.deleteAlert(apiKey.value, row.id)
    ElMessage.success('已删除')
    await loadAlerts()
  } catch (e: any) { /* ignore */ }
}

onMounted(() => { loadReports(); loadScoreTrend(); loadAlerts() })
</script>

<template>
  <div class="q-wrap">
    <el-card shadow="never" class="tf-card">
      <template #header>
        <div class="q-head">
          <span>知识库质量巡检 Agent</span>
          <div class="q-head-right">
            <el-input v-model="apiKey" size="small" placeholder="X-API-Key" style="width: 190px" />
            <el-button size="small" @click="showConfig = true">参数</el-button>
            <el-button type="primary" size="small" :loading="loading" @click="runInspect">运行巡检</el-button>
            <el-button type="warning" size="small" :loading="scheduleRunning" @click="triggerSchedule">立即巡检并告警</el-button>
            <el-button size="small" :loading="reportsLoading" @click="loadReports">刷新历史</el-button>
          </div>
        </div>
      </template>

      <el-alert
        v-if="!result"
        title="巡检在治理「文档级体检」之上补齐切片级 + 检索级质量：近重复/孤立切片、超大/碎片切片、缺规范编号/条文定位、低召回意图，可一键采纳为治理任务。"
        type="info" :closable="false" show-icon />

      <template v-else>
        <!-- 概览 -->
        <el-row :gutter="12" class="metric-row">
          <el-col :span="6">
            <div class="metric"><span class="m-val" :style="{ color: scoreColor }">{{ (result.score).toFixed(1) }}</span><span class="m-lab">质量分</span></div>
          </el-col>
          <el-col :span="6"><div class="metric"><span class="m-val">{{ result.total_docs }}</span><span class="m-lab">文档数</span></div></el-col>
          <el-col :span="6"><div class="metric"><span class="m-val">{{ result.total_chunks }}</span><span class="m-lab">切片数</span></div></el-col>
          <el-col :span="6"><div class="metric"><span class="m-val" :style="{ color: result.issue_count ? '#d9534f' : '#1a9d5a' }">{{ result.issue_count }}</span><span class="m-lab">问题数</span></div></el-col>
        </el-row>

        <!-- 问题分布 -->
        <div class="counts-row" v-if="Object.keys(counts).length">
          <el-tag v-for="(v, k) in counts" :key="k" size="small" class="cnt-tag"
                  :type="sevType[k] || ''">{{ issueLabel[k] || k }} × {{ v }}</el-tag>
        </div>

        <!-- 建议 -->
        <div class="sugg" v-if="result.suggestions?.length">
          <div class="sugg-title">巡检建议</div>
          <ul><li v-for="(s, i) in result.suggestions" :key="i">{{ s }}</li></ul>
        </div>

        <!-- 问题明细 -->
        <h4 class="sec-title">问题明细（{{ issues.length }}）</h4>
        <el-table :data="issues" size="small" border max-height="440" stripe>
          <el-table-column label="类型" width="110">
            <template #default="{ row }">{{ issueLabel[row.issue_type] || row.issue_type }}</template>
          </el-table-column>
          <el-table-column label="级别" width="72" align="center">
            <template #default="{ row }"><el-tag size="small" :type="sevType[row.severity] || ''">{{ row.severity }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="doc_title" label="文档" width="150" show-overflow-tooltip />
          <el-table-column prop="detail" label="详情" min-width="260" show-overflow-tooltip />
          <el-table-column prop="suggestion" label="建议" min-width="180" show-overflow-tooltip />
          <el-table-column label="操作" width="90" align="center" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" link @click="convertIssue(row)">采纳</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>

    <!-- 质量分趋势 -->
    <el-card shadow="never" class="tf-card">
      <template #header>
        <div class="q-head">
          <span>质量分趋势（近 {{ scoreTrend?.count || 0 }} 次）</span>
          <div class="q-head-right">
            <el-tag v-if="openAlertCount" size="small" type="danger">未解决 {{ openAlertCount }}</el-tag>
            <el-button size="small" :loading="scoreTrendLoading" @click="loadScoreTrend">刷新趋势</el-button>
          </div>
        </div>
      </template>

      <el-alert v-if="!scoreTrend?.count" type="info" :closable="false" show-icon
        title="暂无巡检快照。点击「立即巡检并告警」或「运行巡检」后会累计快照，2 次以上即可看到质量分趋势曲线。" />

      <template v-else>
        <div class="legend">
          <span class="lg-item"><i class="lg-dot" style="background:#2a5bd7"></i>质量分</span>
          <span class="lg-item"><i class="lg-dash"></i>告警阈值 {{ scoreThreshold }}</span>
        </div>
        <div class="chart-box">
          <svg :viewBox="`0 0 ${scoreChart.W} ${scoreChart.H}`" class="trend-svg">
            <g>
              <line v-for="t in scoreChart.yTicks" :key="'g'+t.v"
                    :x1="scoreChart.PL" :y1="t.y" :x2="scoreChart.W-scoreChart.PR" :y2="t.y"
                    stroke="#e8edf5" stroke-width="1" />
              <text v-for="t in scoreChart.yTicks" :key="'l'+t.v"
                    :x="scoreChart.PL-8" :y="t.y+4" text-anchor="end" font-size="10" fill="#8595a8">{{ t.v }}</text>
            </g>
            <line :x1="scoreChart.PL" :y1="scoreChart.baseY" :x2="scoreChart.W-scoreChart.PR" :y2="scoreChart.baseY"
                  stroke="#d9534f" stroke-width="1.2" stroke-dasharray="5 4" opacity="0.75" />
            <text :x="scoreChart.W-scoreChart.PR" :y="scoreChart.baseY-5" text-anchor="end" font-size="10" fill="#d9534f">阈值 {{ scoreThreshold }}</text>
            <path :d="scoreChart.d" fill="none" stroke="#2a5bd7" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
            <circle v-for="(dt, i) in scoreChart.dots" :key="i" :cx="dt.cx" :cy="dt.cy" r="3" fill="#2a5bd7" stroke="#fff" stroke-width="1.5">
              <title>质量分 {{ dt.v?.toFixed(1) }}{{ dt.hi ? ' | 高危 '+dt.hi : '' }}</title>
            </circle>
            <g>
              <text v-for="(xl, i) in scoreChart.xLabels" :key="i"
                    v-show="scoreChart.n<=8 || i%Math.ceil(scoreChart.n/8)===0 || i===scoreChart.n-1"
                    :x="xl.x" :y="scoreChart.H-12" text-anchor="middle" font-size="9" fill="#8595a8">{{ xl.t }}</text>
            </g>
          </svg>
        </div>
        <div v-if="scoreTrend?.first_to_latest_delta != null" class="agg-meta">
          首次 → 最新质量分变化：
          <span class="delta-chip" :class="scoreTrend.first_to_latest_delta > 0 ? 'up' : (scoreTrend.first_to_latest_delta < 0 ? 'down' : '')">
            最新 {{ scoreTrend.first_to_latest_delta > 0 ? '+' : '' }}{{ scoreTrend.first_to_latest_delta }}
          </span>
        </div>
      </template>
    </el-card>

    <!-- 质量巡检告警 -->
    <el-card shadow="never" class="tf-card">
      <template #header>
        <div class="q-head">
          <span>质量巡检告警（{{ alerts.length }}）</span>
          <div class="q-head-right">
            <el-radio-group v-model="alertFilter" size="small" @change="loadAlerts">
              <el-radio-button value="all">全部</el-radio-button>
              <el-radio-button value="open">未解决</el-radio-button>
              <el-radio-button value="resolved">已解决</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>

      <el-alert v-if="!alerts.length" type="info" :closable="false" show-icon
        title="暂无告警。当综合质量分低于阈值，或相对上次巡检新增高危问题时，会自动生成告警记录（后台定时巡检或「立即巡检并告警」均会触发）。" />

      <el-table v-else :data="alerts" size="small" border max-height="360" stripe>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="(alertTypeMeta[row.alert_type]?.type) || 'info'">
              {{ alertTypeMeta[row.alert_type]?.label || row.alert_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="质量分" width="80" align="center">
          <template #default="{ row }"><span :class="row.score < scoreThreshold ? 'bad' : 'ok'">{{ (row.score ?? 0).toFixed(1) }}</span></template>
        </el-table-column>
        <el-table-column label="新增高危" width="90" align="center">
          <template #default="{ row }"><span :class="row.new_high_issue_count ? 'bad' : 'ok'">{{ row.new_high_issue_count }}</span></template>
        </el-table-column>
        <el-table-column prop="title" label="概要" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="(!row.resolved ? alertStatusMeta.open.type : alertStatusMeta.resolved.type)">
              {{ !row.resolved ? alertStatusMeta.open.label : alertStatusMeta.resolved.label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" align="center" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.resolved" size="small" type="success" link @click="resolveOne(row)">解决</el-button>
            <el-button size="small" type="danger" link @click="removeAlert(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 历史快照（趋势） -->
    <el-card shadow="never" class="tf-card">
      <template #header>
        <div class="q-head"><span>巡检历史快照（{{ reports.length }}）</span></div>
      </template>
      <el-table :data="reports" size="small" border max-height="320" stripe>
        <el-table-column label="时间" width="180">
          <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="范围" width="80">
          <template #default="{ row }">{{ row.scope === 'kb' ? '单库' : '全库' }}</template>
        </el-table-column>
        <el-table-column label="质量分" width="90" align="center">
          <template #default="{ row }">
            <span :class="row.score >= 85 ? 'ok' : row.score >= 60 ? '' : 'bad'">{{ row.score.toFixed(1) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="total_docs" label="文档" width="70" align="center" />
        <el-table-column prop="total_chunks" label="切片" width="70" align="center" />
        <el-table-column prop="issue_count" label="问题" width="70" align="center" />
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="viewReport(row.id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 巡检参数 -->
    <el-dialog v-model="showConfig" title="巡检参数" width="480px">
      <el-form label-width="130px">
        <el-form-item label="知识库ID（可选）"><el-input v-model="cfg.kb_id" placeholder="留空=全租户全部" /></el-form-item>
        <el-form-item label="近重复阈值">
          <el-slider v-model="cfg.dup_threshold" :min="0.5" :max="0.99" :step="0.01" show-input />
        </el-form-item>
        <el-form-item label="孤立阈值">
          <el-slider v-model="cfg.orphan_threshold" :min="0" :max="0.9" :step="0.01" show-input />
        </el-form-item>
        <el-form-item label="超大切片(字)"><el-input-number v-model="cfg.max_chunk_chars" :min="200" :max="8000" :step="100" /></el-form-item>
        <el-form-item label="碎片切片(字)"><el-input-number v-model="cfg.min_chunk_chars" :min="1" :max="500" :step="5" /></el-form-item>
        <el-form-item label="召回探针"><el-switch v-model="cfg.run_recall_probe" /></el-form-item>
        <el-form-item label="快照落库"><el-switch v-model="cfg.persist" /></el-form-item>
        <el-divider content-position="left">定时告警阈值</el-divider>
        <el-form-item label="低分告警阈值">
          <el-input-number v-model="scoreThreshold" :min="0" :max="100" :step="5" />
        </el-form-item>
        <el-form-item label="新高危阈值">
          <el-input-number v-model="newHighThreshold" :min="0" :max="20" :step="1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showConfig = false">取消</el-button>
        <el-button type="primary" @click="showConfig = false; runInspect()">保存并巡检</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.q-wrap { display: flex; flex-direction: column; gap: 14px; }
.tf-card { border-radius: 10px; }
.q-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.q-head-right { display: flex; gap: 8px; align-items: center; }
.metric-row { margin-bottom: 10px; }
.metric { background: #f5f8ff; border: 1px solid #e6eefc; border-radius: 8px; padding: 12px 10px; text-align: center; }
.m-val { display: block; font-size: 22px; font-weight: 700; color: #2a5bd7; }
.m-lab { display: block; font-size: 12px; color: #6b7a90; margin-top: 4px; }
.counts-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 10px; }
.cnt-tag { font-weight: 600; }
.sugg { background: #fbfcfe; border: 1px solid #eef2f8; border-radius: 8px; padding: 10px 14px; margin-bottom: 6px; }
.sugg-title { font-size: 13px; font-weight: 600; color: #2c3a4b; margin-bottom: 4px; }
.sugg ul { margin: 0; padding-left: 18px; }
.sugg li { font-size: 12.5px; color: #5a6b80; line-height: 1.8; }
.sec-title { margin: 14px 0 8px; font-size: 14px; color: #2c3a4b; }
.ok { color: #1a9d5a; font-weight: 600; }
.bad { color: #d9534f; font-weight: 600; }
.agg-meta { font-size: 12px; color: #8595a8; margin: 8px 0 4px; }
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
