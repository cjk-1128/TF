<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { kbApi, ragApi } from '@/api'
import ChunkCard from '@/components/ChunkCard.vue'
import type { KnowledgeBase, RetrievedChunk } from '@/types'

const kbs = ref<KnowledgeBase[]>([])
const results = ref<RetrievedChunk[]>([])
const loading = ref(false)
const searched = ref(false)

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
  </div>
</template>
