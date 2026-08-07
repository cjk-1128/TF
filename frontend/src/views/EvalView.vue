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

const agg = computed(() => result.value?.aggregated || {})
const perQuery = computed(() => result.value?.per_query || [])

const intentLabel: Record<string, string> = {
  spec_lookup: '规范查询', quality_diagnosis: '质量分析',
  case_retrieval: '案例检索', scheme_generation: '方案生成',
  out_of_scope: '越域', chitchat: '闲聊', unknown: '未知'
}

async function runEval() {
  if (!apiKey.value) { ElMessage.warning('请填写 API Key'); return }
  loading.value = true
  try {
    const r = await evalApi.run(apiKey.value)
    result.value = r.data
    ElMessage.success(r.message || '评测完成')
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

onMounted(loadGolden)
</script>

<template>
  <div class="eval-wrap">
    <el-card shadow="never" class="tf-card">
      <template #header>
        <div class="eval-head">
          <span>检索评测看板</span>
          <div class="eval-head-right">
            <el-input v-model="apiKey" size="small" placeholder="X-API-Key" style="width: 200px" />
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
        <div class="agg-meta">样本 {{ result.n_queries }}（正 {{ result.n_positive }} / 负 {{ result.n_negative }}）｜
          NDCG@5={{ agg['delivered_ndcg@k']?.['5']?.toFixed(3) }}</div>

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
</style>
