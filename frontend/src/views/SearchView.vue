<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { kbApi, ragApi } from '@/api'
import ChunkCard from '@/components/ChunkCard.vue'
import type { KnowledgeBase, RetrievedChunk } from '@/types'

const kbs = ref<KnowledgeBase[]>([])
const results = ref<RetrievedChunk[]>([])
const loading = ref(false)
const searched = ref(false)

const explain = ref<any>(null)
const explainLoading = ref(false)
const explainVisible = ref(false)

const form = ref({
  query: '',
  kb_ids: [] as string[],
  domains: [] as string[],
  top_k: 10,
  use_rerank: true
})

const domainOptions = [
  { value: 'standard', label: '建设规范库' },
  { value: 'case', label: '项目案例库' },
  { value: 'enterprise', label: '企业知识库' }
]

const samples = ['基坑监测报警值', '混凝土养护时间', '脚手架连墙件设置', '防水混凝土抗渗等级', '楼板裂缝处理']

async function doSearch() {
  if (!form.value.query.trim()) return
  loading.value = true
  try {
    const res = await ragApi.search({ ...form.value })
    results.value = res.data || []
    searched.value = true
  } finally {
    loading.value = false
  }
}

async function doExplain() {
  if (!form.value.query.trim()) return
  explainLoading.value = true
  explainVisible.value = true
  try {
    const res = await ragApi.explain({ query: form.value.query, kb_ids: form.value.kb_ids, domains: form.value.domains, top_k: form.value.top_k })
    explain.value = res.data || null
  } finally {
    explainLoading.value = false
  }
}

function useSample(s: string) {
  form.value.query = s
  doSearch()
}

onMounted(async () => {
  const res = await kbApi.list()
  kbs.value = res.data || []
})
</script>

<template>
  <div>
    <div class="tf-card" style="padding: 16px; margin-bottom: 14px">
      <div class="tf-section-title">
        <el-icon><Search /></el-icon> 混合检索（Stage3 向量 + BM25 → RRF 融合 → Stage4 重排序）
      </div>
      <el-form :model="form" label-width="88px">
        <el-form-item label="检索语句">
          <el-input
            v-model="form.query"
            placeholder="输入工程关键词或完整问题，例如：深基坑支护结构水平位移报警值"
            clearable
            @keyup.enter="doSearch"
          >
            <template #append>
              <el-button :loading="loading" type="primary" @click="doSearch">检索</el-button>
              <el-button :loading="explainLoading" @click="doExplain">可解释性</el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="快捷示例">
          <el-tag
            v-for="s in samples"
            :key="s"
            style="margin-right: 8px; cursor: pointer"
            effect="plain"
            @click="useSample(s)"
          >
            {{ s }}
          </el-tag>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="知识库">
              <el-select v-model="form.kb_ids" multiple collapse-tags clearable placeholder="全部" style="width: 100%">
                <el-option v-for="k in kbs" :key="k.id" :label="k.name" :value="k.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="知识域">
              <el-select v-model="form.domains" multiple collapse-tags clearable placeholder="全部" style="width: 100%">
                <el-option v-for="d in domainOptions" :key="d.value" :label="d.label" :value="d.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="Top-K">
              <el-input-number v-model="form.top_k" :min="1" :max="50" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="重排序">
              <el-switch v-model="form.use_rerank" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </div>

    <div class="tf-card" style="padding: 16px" v-loading="loading">
      <div class="tf-section-title">
        检索结果
        <span class="tf-muted" style="font-weight: 400">（{{ results.length }} 条）</span>
      </div>
      <el-empty v-if="searched && !results.length" description="未检索到相关知识，建议补充相应规范或案例资料" />
      <div v-else-if="!searched" class="tf-muted" style="font-size: 13px">
        该页面用于验证检索链路质量，可对比向量得分、BM25 得分、融合得分与重排序得分。
      </div>
      <ChunkCard v-for="(c, i) in results" :key="c.chunk_id" :chunk="c" :rank="i + 1" />
    </div>

    <!-- 检索可解释性面板 -->
    <div class="tf-card" style="padding: 16px; margin-top: 14px" v-if="explainVisible" v-loading="explainLoading">
      <div class="tf-section-title">
        <el-icon><View /></el-icon> 检索可解释性（意图路由 + 多路打分明细）
      </div>
      <el-empty v-if="!explainLoading && !explain" description="暂无可解释性数据" />
      <template v-if="explain">
        <!-- 路由决策 -->
        <el-descriptions :column="4" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="识别意图">
            {{ explain.intent_label || explain.intent }}
          </el-descriptions-item>
          <el-descriptions-item label="意图置信度">{{ explain.intent_confidence }}</el-descriptions-item>
          <el-descriptions-item label="检索策略">{{ explain.retrieval_strategy }}</el-descriptions-item>
          <el-descriptions-item label="越域">
            <el-tag :type="explain.out_of_scope ? 'danger' : 'info'" size="small">
              {{ explain.out_of_scope ? '是' : '否' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="改写后查询" :span="2">
            <span v-if="explain.rewritten_query">{{ explain.rewritten_query }}</span>
            <span v-else class="tf-muted">—</span>
          </el-descriptions-item>
          <el-descriptions-item label="抽取规范编号" :span="2">
            <el-tag v-for="c in (explain.extracted_codes || [])" :key="c" size="small" style="margin-right: 4px">{{ c }}</el-tag>
            <span v-if="!(explain.extracted_codes || []).length" class="tf-muted">—</span>
          </el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="explain.below_relevance_floor"
          type="warning"
          :closable="false"
          show-icon
          :title="'相关性未达门槛，已按「无证据不作答」拦截'"
          :description="explain.rejection_reason || '检索命中但证据不足'"
          style="margin-bottom: 12px"
        />
        <el-alert
          v-else-if="!explain.need_retrieval"
          type="info"
          :closable="false"
          show-icon
          title="意图判定无需检索（如闲聊）"
          style="margin-bottom: 12px"
        />

        <div class="tf-section-subtitle" style="margin: 8px 0">
          候选切片打分明细
          <span class="tf-muted">（候选 {{ explain.candidate_count }} 条 · 最终入选 {{ explain.final_count }} 条）</span>
        </div>
        <el-table :data="explain.candidates" size="small" border stripe max-height="460"
                  :default-sort="{ prop: 'final_score', order: 'descending' }">
          <el-table-column type="index" label="#" width="42" />
          <el-table-column prop="doc_title" label="来源文档" min-width="180" show-overflow-tooltip />
          <el-table-column prop="domain" label="域" width="80" />
          <el-table-column prop="vector_score" label="向量分" width="92" sortable />
          <el-table-column prop="bm25_score" label="BM25分" width="92" sortable />
          <el-table-column prop="fusion_score" label="融合分" width="92" sortable />
          <el-table-column prop="rerank_score" label="重排分" width="92" sortable />
          <el-table-column prop="final_score" label="最终分" width="92" sortable />
          <el-table-column label="命中词" min-width="180">
            <template #default="{ row }">
              <el-tag v-for="t in (row.matched_terms || [])" :key="t" size="small"
                      type="success" effect="plain" style="margin: 2px">{{ t }}</el-tag>
              <span v-if="!(row.matched_terms || []).length" class="tf-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="84">
            <template #default="{ row }">
              <el-tag v-if="row.used" type="success" size="small">入选</el-tag>
              <el-tag v-else-if="explain.below_relevance_floor" type="warning" size="small">被拒</el-tag>
              <el-tag v-else type="info" size="small">未入选</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="强制/状态" width="92">
            <template #default="{ row }">
              <el-tag v-if="row.is_mandatory" type="danger" size="small">强制条文</el-tag>
              <el-tag v-else-if="row.governance_status && row.governance_status !== 'valid'"
                      size="small" type="warning">{{ row.governance_status }}</el-tag>
              <span v-else class="tf-muted">正常</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </div>
  </div>
</template>
