<script setup lang="ts">
import type { Citation } from '@/types'

defineProps<{ citations: Citation[] }>()
const emit = defineEmits<{ (e: 'preview', c: Citation): void }>()

const domainLabel: Record<string, string> = {
  standard: '建设规范',
  case: '项目案例',
  enterprise: '企业知识'
}
</script>

<template>
  <div v-if="citations && citations.length" class="cite-list">
    <div class="tf-muted" style="font-size: 12px; margin-bottom: 4px">
      引用来源（{{ citations.length }}）—— 点击查看原文片段
    </div>
    <div
      v-for="c in citations"
      :key="c.index_no + c.chunk_id"
      class="cite-item"
      @click="emit('preview', c)"
    >
      <span class="cite-no">{{ c.index_no }}</span>
      <div style="flex: 1">
        <div class="cite-title">
          {{ c.standard_code ? `《${c.standard_code}》 ` : '' }}{{ c.doc_title }}
          <el-tag size="small" effect="plain" style="margin-left: 6px">
            {{ domainLabel[c.domain] || c.domain }}
          </el-tag>
        </div>
        <div class="cite-path">
          <template v-if="c.clause_no">第 {{ c.clause_no }} 条 · </template>
          <template v-if="c.section_path">{{ c.section_path }} · </template>
          <template v-if="c.page_no">P{{ c.page_no }} · </template>
          相关度 {{ (c.score * 100).toFixed(0) }}%
        </div>
      </div>
    </div>
  </div>
</template>
