<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ value: number; level?: string }>()

const type = computed(() => {
  if (props.value >= 0.75) return 'success'
  if (props.value >= 0.45) return 'warning'
  return 'danger'
})

const label = computed(() => {
  if (props.level === 'high' || props.value >= 0.75) return '高置信'
  if (props.level === 'medium' || props.value >= 0.45) return '中置信'
  return '低置信'
})
</script>

<template>
  <el-tooltip
    placement="top"
    :content="`置信度综合了检索相关性、引用覆盖、来源权威性与一致性等信号；低于 0.45 时建议人工复核`"
  >
    <el-tag :type="type" size="small" effect="light">
      {{ label }} {{ (value * 100).toFixed(0) }}%
    </el-tag>
  </el-tooltip>
</template>
