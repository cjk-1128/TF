<script setup lang="ts">
import type { RetrievedChunk } from '@/types'

defineProps<{ chunk: RetrievedChunk; rank?: number }>()

const domainLabel: Record<string, string> = {
  standard: '建设规范',
  case: '项目案例',
  enterprise: '企业知识'
}
</script>

<template>
  <div class="chunk-card">
    <div class="head">
      <span>
        <el-tag v-if="rank" size="small" type="info" effect="plain">#{{ rank }}</el-tag>
        <b style="margin-left: 6px; color: var(--tf-text)">
          {{ chunk.standard_code ? `《${chunk.standard_code}》` : chunk.doc_title }}
        </b>
        <span v-if="chunk.clause_no" style="margin-left: 6px">第 {{ chunk.clause_no }} 条</span>
        <el-tag v-if="chunk.is_mandatory" size="small" type="danger" effect="light" style="margin-left: 6px">
          强制性条文
        </el-tag>
      </span>
      <el-tag size="small" effect="plain">{{ domainLabel[chunk.domain] || chunk.domain }}</el-tag>
    </div>
    <div v-if="chunk.section_path" class="tf-muted" style="font-size: 12px; margin-bottom: 4px">
      {{ chunk.section_path }}
    </div>
    <div class="content">{{ chunk.content }}</div>
    <div style="margin-top: 8px">
      <div class="score-bar"><i :style="{ width: Math.min(100, chunk.final_score * 100) + '%' }" /></div>
      <div class="tf-muted" style="font-size: 11px; margin-top: 4px">
        最终 {{ chunk.final_score.toFixed(3) }} ·
        向量 {{ chunk.vector_score.toFixed(3) }} ·
        BM25 {{ chunk.bm25_score.toFixed(3) }} ·
        融合 {{ chunk.fusion_score.toFixed(3) }} ·
        重排 {{ chunk.rerank_score.toFixed(3) }}
      </div>
    </div>
  </div>
</template>
