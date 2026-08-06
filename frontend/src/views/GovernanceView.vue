<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { govApi, kbApi } from '@/api'
import type { GovernanceTask, HealthReport, KnowledgeBase, KnowledgeGap, OperationReport } from '@/types'

const tab = ref('health')
const kbs = ref<KnowledgeBase[]>([])
const selectedKb = ref('')

/* ---------- 健康度 ---------- */
const report = ref<HealthReport | null>(null)
const healthLoading = ref(false)

const issueTypeMap: Record<string, string> = {
  expired: '已过期',
  expiring_soon: '即将失效',
  no_owner: '缺少责任人',
  duplicate: '疑似重复',
  stale: '长期未更新',
  empty_summary: '缺少摘要',
  parse_failed: '解析失败',
  no_chunk: '无有效切片'
}

const severityMap: Record<string, string> = { high: 'danger', medium: 'warning', low: 'info' }

const scoreColor = computed(() => {
  const s = report.value?.score ?? 0
  if (s >= 85) return '#2fa36b'
  if (s >= 70) return '#e6a23c'
  return '#f56c6c'
})

async function loadHealth() {
  healthLoading.value = true
  try {
    const res = await govApi.healthReport(selectedKb.value || undefined)
    report.value = res.data
  } finally {
    healthLoading.value = false
  }
}

/* ---------- 治理事项 ---------- */
const tasks = ref<GovernanceTask[]>([])
const taskTotal = ref(0)
const taskLoading = ref(false)
const taskQuery = reactive({ kb_id: '', status: '', task_type: '', page: 1, page_size: 20 })

const taskTypeMap: Record<string, string> = {
  expire_check: '时效核查',
  duplicate_merge: '重复合并',
  gap_fill: '盲区补录',
  conflict_resolve: '冲突消解',
  quality_fix: '质量修复',
  owner_assign: '责任人指派'
}

const taskStatusMap: Record<string, { label: string; type: string }> = {
  open: { label: '待处理', type: 'warning' },
  in_progress: { label: '处理中', type: 'primary' },
  resolved: { label: '已完成', type: 'success' },
  ignored: { label: '已忽略', type: 'info' }
}

const priorityMap: Record<string, { label: string; type: string }> = {
  high: { label: '高', type: 'danger' },
  medium: { label: '中', type: 'warning' },
  low: { label: '低', type: 'info' }
}

async function loadTasks() {
  taskLoading.value = true
  try {
    const res = await govApi.tasks({ ...taskQuery })
    tasks.value = res.data?.items || []
    taskTotal.value = res.data?.total || 0
  } finally {
    taskLoading.value = false
  }
}

async function autoGenerate() {
  const res = await govApi.autoGenerate(selectedKb.value || undefined)
  ElMessage.success(`已自动生成 ${res.data?.length || 0} 条治理事项`)
  loadTasks()
}

async function changeStatus(row: GovernanceTask, status: string) {
  await govApi.updateTask(row.id, { status })
  ElMessage.success('已更新')
  loadTasks()
}

const taskDialog = ref(false)
const taskForm = reactive({
  task_type: 'gap_fill',
  title: '',
  description: '',
  kb_id: '',
  priority: 'medium',
  assignee: ''
})

function openTaskDialog(preset?: Partial<typeof taskForm>) {
  Object.assign(taskForm, {
    task_type: 'gap_fill',
    title: '',
    description: '',
    kb_id: selectedKb.value,
    priority: 'medium',
    assignee: ''
  }, preset || {})
  taskDialog.value = true
}

async function submitTask() {
  if (!taskForm.title.trim()) return ElMessage.warning('请填写事项标题')
  await govApi.createTask({ ...taskForm })
  ElMessage.success('已创建')
  taskDialog.value = false
  loadTasks()
}

/* ---------- 知识盲区 ---------- */
const gaps = ref<KnowledgeGap[]>([])
const gapDays = ref(30)
const gapLoading = ref(false)

async function loadGaps() {
  gapLoading.value = true
  try {
    const res = await govApi.gaps(gapDays.value)
    gaps.value = res.data || []
  } finally {
    gapLoading.value = false
  }
}

function gapToTask(g: KnowledgeGap) {
  openTaskDialog({
    task_type: 'gap_fill',
    title: `补录知识：${g.query}`,
    description: `近期该问题被提问 ${g.count} 次，平均置信度仅 ${(g.avg_confidence * 100).toFixed(0)}%。${g.suggestion}`,
    priority: g.count >= 3 ? 'high' : 'medium'
  })
}

/* ---------- 运营报告 ---------- */
const opReport = ref<OperationReport | null>(null)
const opDays = ref(7)
const opLoading = ref(false)

async function loadOpReport() {
  opLoading.value = true
  try {
    const res = await govApi.operationReport(opDays.value)
    opReport.value = res.data
  } finally {
    opLoading.value = false
  }
}

function onTabChange(name: string) {
  if (name === 'health' && !report.value) loadHealth()
  if (name === 'tasks') loadTasks()
  if (name === 'gaps' && !gaps.value.length) loadGaps()
  if (name === 'report' && !opReport.value) loadOpReport()
}

function fmtDate(s?: string) {
  return s ? s.replace('T', ' ').slice(0, 16) : '—'
}

onMounted(async () => {
  const res = await kbApi.list()
  kbs.value = res.data || []
  loadHealth()
})
</script>

<template>
  <div class="tf-card" style="padding: 16px">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px">
      <div class="tf-section-title" style="margin: 0">
        <el-icon><DataAnalysis /></el-icon> Stage7 知识治理闭环
      </div>
      <div style="display: flex; gap: 10px">
        <el-select v-model="selectedKb" placeholder="全部知识库" clearable style="width: 190px" @change="loadHealth">
          <el-option v-for="k in kbs" :key="k.id" :label="k.name" :value="k.id" />
        </el-select>
        <el-button type="primary" plain @click="autoGenerate">
          <el-icon><MagicStick /></el-icon>&nbsp;自动生成治理事项
        </el-button>
      </div>
    </div>

    <el-tabs v-model="tab" @tab-change="onTabChange">
      <!-- 健康度 -->
      <el-tab-pane label="知识健康度" name="health">
        <div v-loading="healthLoading">
          <template v-if="report">
            <el-row :gutter="14" style="margin-bottom: 14px">
              <el-col :span="6">
                <div class="stat-card" style="text-align: center">
                  <div class="label">知识库健康评分</div>
                  <el-progress
                    type="dashboard"
                    :percentage="Math.round(report.score)"
                    :color="scoreColor"
                    :width="120"
                    style="margin-top: 6px"
                  />
                  <div class="tf-muted" style="font-size: 12px">
                    生成时间 {{ fmtDate(report.generated_at) }}
                  </div>
                </div>
              </el-col>
              <el-col :span="18">
                <div class="stat-grid">
                  <div class="stat-card"><div class="label">知识库</div><div class="value">{{ report.total_kb }}</div></div>
                  <div class="stat-card"><div class="label">文档总数</div><div class="value">{{ report.total_docs }}</div></div>
                  <div class="stat-card"><div class="label">知识切片</div><div class="value">{{ report.total_chunks }}</div></div>
                  <div class="stat-card"><div class="label">现行有效</div><div class="value" style="color: var(--tf-success)">{{ report.valid_docs }}</div></div>
                  <div class="stat-card"><div class="label">待更新</div><div class="value" style="color: var(--tf-warn)">{{ report.need_update_docs }}</div></div>
                  <div class="stat-card"><div class="label">已废止</div><div class="value" style="color: var(--tf-danger)">{{ report.deprecated_docs }}</div></div>
                  <div class="stat-card"><div class="label">解析失败</div><div class="value" style="color: var(--tf-danger)">{{ report.failed_docs }}</div></div>
                  <div class="stat-card"><div class="label">待办问题</div><div class="value">{{ report.issues.length }}</div></div>
                </div>
              </el-col>
            </el-row>

            <el-alert
              v-for="(s, i) in report.suggestions"
              :key="i"
              type="info"
              :closable="false"
              show-icon
              :title="s"
              style="margin-bottom: 8px"
            />

            <div class="tf-section-title" style="margin-top: 16px">健康问题清单</div>
            <el-table :data="report.issues" stripe size="small">
              <el-table-column label="类型" width="120">
                <template #default="{ row }">
                  <el-tag :type="(severityMap[row.severity] as any) || 'info'" size="small" effect="light">
                    {{ issueTypeMap[row.issue_type] || row.issue_type }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="doc_title" label="文档" min-width="200" />
              <el-table-column prop="detail" label="问题描述" min-width="220" />
              <el-table-column prop="suggestion" label="处置建议" min-width="220" />
              <template #empty><el-empty description="未发现健康问题，知识库状态良好" /></template>
            </el-table>
          </template>
        </div>
      </el-tab-pane>

      <!-- 治理事项 -->
      <el-tab-pane label="治理事项" name="tasks">
        <div style="display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap">
          <el-select v-model="taskQuery.status" placeholder="全部状态" clearable style="width: 130px" @change="loadTasks">
            <el-option v-for="(v, k) in taskStatusMap" :key="k" :label="v.label" :value="k" />
          </el-select>
          <el-select v-model="taskQuery.task_type" placeholder="全部类型" clearable style="width: 140px" @change="loadTasks">
            <el-option v-for="(v, k) in taskTypeMap" :key="k" :label="v" :value="k" />
          </el-select>
          <el-button @click="loadTasks"><el-icon><Refresh /></el-icon>&nbsp;刷新</el-button>
          <el-button type="primary" @click="openTaskDialog()">
            <el-icon><Plus /></el-icon>&nbsp;新建事项
          </el-button>
        </div>

        <el-table :data="tasks" v-loading="taskLoading" stripe>
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ taskTypeMap[row.task_type] || row.task_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="事项" min-width="260">
            <template #default="{ row }">
              <div style="font-weight: 600">{{ row.title }}</div>
              <div class="tf-muted" style="font-size: 12px">{{ row.description || '—' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="90">
            <template #default="{ row }">
              <el-tag :type="(priorityMap[row.priority]?.type as any) || 'info'" size="small">
                {{ priorityMap[row.priority]?.label || row.priority }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="(taskStatusMap[row.status]?.type as any) || 'info'" size="small" effect="light">
                {{ taskStatusMap[row.status]?.label || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="责任人" width="110">
            <template #default="{ row }">{{ row.assignee || '未指派' }}</template>
          </el-table-column>
          <el-table-column label="创建时间" width="150">
            <template #default="{ row }">{{ fmtDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.status === 'open'" link type="primary" @click="changeStatus(row, 'in_progress')">开始处理</el-button>
              <el-button v-if="row.status !== 'resolved'" link type="success" @click="changeStatus(row, 'resolved')">标记完成</el-button>
              <el-button v-if="row.status === 'open'" link type="info" @click="changeStatus(row, 'ignored')">忽略</el-button>
            </template>
          </el-table-column>
          <template #empty><el-empty description="暂无治理事项，可点击「自动生成治理事项」" /></template>
        </el-table>

        <el-pagination
          v-model:current-page="taskQuery.page"
          :page-size="taskQuery.page_size"
          :total="taskTotal"
          layout="total, prev, pager, next"
          style="margin-top: 12px; justify-content: flex-end"
          @current-change="loadTasks"
        />
      </el-tab-pane>

      <!-- 知识盲区 -->
      <el-tab-pane label="知识盲区" name="gaps">
        <div style="display: flex; gap: 10px; margin-bottom: 12px; align-items: center">
          <span class="tf-muted">统计窗口</span>
          <el-select v-model="gapDays" style="width: 120px" @change="loadGaps">
            <el-option :value="7" label="近 7 天" />
            <el-option :value="30" label="近 30 天" />
            <el-option :value="90" label="近 90 天" />
          </el-select>
          <el-button @click="loadGaps"><el-icon><Refresh /></el-icon>&nbsp;刷新</el-button>
          <span class="tf-muted" style="font-size: 12px">
            盲区来自低置信/无召回的提问记录，是知识补录的最优先输入
          </span>
        </div>
        <el-table :data="gaps" v-loading="gapLoading" stripe>
          <el-table-column prop="query" label="未被有效回答的问题" min-width="300" />
          <el-table-column prop="count" label="提问次数" width="100" sortable />
          <el-table-column label="平均置信度" width="130">
            <template #default="{ row }">
              <el-tag type="danger" size="small" effect="plain">
                {{ (row.avg_confidence * 100).toFixed(0) }}%
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="suggestion" label="补录建议" min-width="250" />
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="gapToTask(row)">生成补录事项</el-button>
            </template>
          </el-table-column>
          <template #empty><el-empty description="暂无知识盲区，知识覆盖良好" /></template>
        </el-table>
      </el-tab-pane>

      <!-- 运营报告 -->
      <el-tab-pane label="运营报告" name="report">
        <div style="display: flex; gap: 10px; margin-bottom: 14px; align-items: center">
          <span class="tf-muted">报告周期</span>
          <el-select v-model="opDays" style="width: 130px" @change="loadOpReport">
            <el-option :value="7" label="周报（7 天）" />
            <el-option :value="30" label="月报（30 天）" />
          </el-select>
          <el-button @click="loadOpReport"><el-icon><Refresh /></el-icon>&nbsp;生成</el-button>
        </div>

        <div v-loading="opLoading">
          <template v-if="opReport">
            <div class="tf-muted" style="font-size: 12px; margin-bottom: 10px">
              统计区间：{{ fmtDate(opReport.start) }} ~ {{ fmtDate(opReport.end) }}（{{ opReport.period }}）
            </div>
            <div class="stat-grid" style="margin-bottom: 16px">
              <div class="stat-card"><div class="label">新增文档</div><div class="value">{{ opReport.new_docs }}</div></div>
              <div class="stat-card"><div class="label">新增切片</div><div class="value">{{ opReport.new_chunks }}</div></div>
              <div class="stat-card"><div class="label">提问总数</div><div class="value">{{ opReport.total_queries }}</div></div>
              <div class="stat-card">
                <div class="label">有效回答率</div>
                <div class="value" :style="{ color: opReport.answer_rate >= 0.8 ? 'var(--tf-success)' : 'var(--tf-warn)' }">
                  {{ (opReport.answer_rate * 100).toFixed(1) }}%
                </div>
              </div>
              <div class="stat-card"><div class="label">平均置信度</div><div class="value">{{ (opReport.avg_confidence * 100).toFixed(0) }}%</div></div>
              <div class="stat-card"><div class="label">平均响应</div><div class="value">{{ opReport.avg_latency_ms }}<span style="font-size: 13px">ms</span></div></div>
              <div class="stat-card"><div class="label">未答问题</div><div class="value" style="color: var(--tf-danger)">{{ opReport.unanswered_queries }}</div></div>
              <div class="stat-card"><div class="label">待办事项</div><div class="value">{{ opReport.pending_tasks }}</div></div>
            </div>

            <el-row :gutter="14">
              <el-col :span="12">
                <div class="tf-section-title">热点主题 TOP</div>
                <el-table :data="opReport.hot_topics" size="small" stripe>
                  <el-table-column prop="topic" label="主题" />
                  <el-table-column prop="count" label="提及次数" width="110" />
                  <template #empty><el-empty description="暂无数据" :image-size="60" /></template>
                </el-table>
              </el-col>
              <el-col :span="12">
                <div class="tf-section-title">知识盲区 TOP</div>
                <el-table :data="opReport.knowledge_gaps" size="small" stripe>
                  <el-table-column prop="query" label="问题" show-overflow-tooltip />
                  <el-table-column prop="count" label="次数" width="70" />
                  <template #empty><el-empty description="暂无数据" :image-size="60" /></template>
                </el-table>
              </el-col>
            </el-row>

            <div class="tf-section-title" style="margin-top: 16px">运营建议</div>
            <el-alert
              v-for="(s, i) in opReport.suggestions"
              :key="i"
              type="success"
              :closable="false"
              show-icon
              :title="s"
              style="margin-bottom: 8px"
            />
            <el-empty v-if="!opReport.suggestions.length" description="本周期运行平稳，无特别建议" :image-size="70" />
          </template>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建事项 -->
    <el-dialog v-model="taskDialog" title="新建治理事项" width="560px">
      <el-form :model="taskForm" label-width="90px">
        <el-form-item label="类型">
          <el-select v-model="taskForm.task_type" style="width: 100%">
            <el-option v-for="(v, k) in taskTypeMap" :key="k" :label="v" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" required><el-input v-model="taskForm.title" /></el-form-item>
        <el-form-item label="知识库">
          <el-select v-model="taskForm.kb_id" clearable placeholder="不限" style="width: 100%">
            <el-option v-for="k in kbs" :key="k.id" :label="k.name" :value="k.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="taskForm.priority">
            <el-radio-button value="high">高</el-radio-button>
            <el-radio-button value="medium">中</el-radio-button>
            <el-radio-button value="low">低</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="责任人"><el-input v-model="taskForm.assignee" placeholder="如：技术质量部-李工" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="taskForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialog = false">取消</el-button>
        <el-button type="primary" @click="submitTask">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>
