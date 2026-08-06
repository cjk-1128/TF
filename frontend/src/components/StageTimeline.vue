<script setup lang="ts">
import type { StageTrace } from '@/types'

defineProps<{ traces: StageTrace[] }>()

function fmt(detail: Record<string, any>): string {
  if (!detail) return ''
  return Object.entries(detail)
    .map(([k, v]) => {
      let val: string
      if (Array.isArray(v)) val = v.slice(0, 4).join('、') || '-'
      else if (typeof v === 'object' && v !== null) val = JSON.stringify(v)
      else val = String(v)
      if (val.length > 90) val = val.slice(0, 90) + '…'
      return `${k}: ${val}`
    })
    .join('　|　')
}
</script>

<template>
  <div>
    <div v-if="!traces || !traces.length" class="tf-muted" style="font-size: 12px">
      暂无执行链路数据，发起一次提问后即可查看 Stage0-Stage7 的完整轨迹。
    </div>
    <div v-for="t in traces" :key="t.stage" class="stage-item">
      <div class="stage-head">
        <span>{{ t.stage.toUpperCase() }} · {{ t.name }}</span>
        <span class="tf-muted" style="font-weight: 400">{{ t.elapsed_ms }}ms</span>
      </div>
      <div class="stage-detail">{{ fmt(t.detail) }}</div>
    </div>
  </div>
</template>
