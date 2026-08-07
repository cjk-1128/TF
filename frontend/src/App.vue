<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { kbApi } from '@/api'

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const backendOk = ref<boolean | null>(null)
const stats = ref<Record<string, number>>({})

const menus = [
  { path: '/chat', title: '工程智能问答', icon: 'ChatDotRound' },
  { path: '/search', title: '知识片段检索', icon: 'Search' },
  { path: '/knowledge', title: '知识库管理', icon: 'Collection' },
  { path: '/documents', title: '文档与切片', icon: 'Document' },
  { path: '/governance', title: '知识治理闭环', icon: 'DataAnalysis' },
  { path: '/eval', title: '检索评测看板', icon: 'TrendCharts' },
  { path: '/quality', title: '质量巡检 Agent', icon: 'Stamp' }
]

const currentTitle = computed(() => (route.meta?.title as string) || 'TerraForge')
const subTitle = computed(() => {
  const map: Record<string, string> = {
    '/chat': 'Stage0-Stage7 全链路 RAG · 答案均来自知识库并标注出处',
    '/search': '混合检索（向量 + BM25 + RRF）与重排序结果透视',
    '/knowledge': '建设规范库 / 项目案例库 / 企业知识库三域管理',
    '/documents': '文档解析入库、工程元数据维护与切片查看',
    '/governance': '知识健康度、治理事项、知识盲区与运营报告',
    '/eval': 'Recall@K / MRR / NDCG@K 评测与逐题检索质量透视',
    '/quality': '切片级 + 检索级质量巡检 · 近重复/孤立/超大切片与低召回意图'
  }
  return map[route.path] || ''
})

async function loadStats() {
  try {
    const res = await kbApi.stats()
    stats.value = res.data || {}
  } catch {
    /* 已由拦截器提示 */
  }
}

onMounted(async () => {
  try {
    const r = await fetch('/health')
    backendOk.value = r.ok
  } catch {
    backendOk.value = false
  }
  loadStats()
})
</script>

<template>
  <el-container class="tf-layout">
    <el-aside class="tf-aside" :width="collapsed ? '64px' : '218px'">
      <div class="tf-logo">
        <div class="tf-logo-mark">TF</div>
        <div v-show="!collapsed" class="tf-logo-text">
          <b>TerraForge</b>
          <span>土木工程智能知识平台</span>
        </div>
      </div>

      <el-menu
        class="tf-menu"
        :default-active="route.path"
        :collapse="collapsed"
        background-color="transparent"
        text-color="#c3d0e2"
        active-text-color="#ffffff"
        @select="(i: string) => router.push(i)"
      >
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <template #title>{{ m.title }}</template>
        </el-menu-item>
      </el-menu>

      <div v-show="!collapsed" class="tf-aside-footer">
        <div>知识库 {{ stats.kb_count ?? '-' }} · 文档 {{ stats.doc_count ?? '-' }}</div>
        <div>切片 {{ stats.chunk_count ?? '-' }} · v1.0.0</div>
      </div>
    </el-aside>

    <el-container>
      <el-header class="tf-header">
        <div style="display: flex; align-items: center; gap: 14px">
          <el-icon style="cursor: pointer; font-size: 18px" @click="collapsed = !collapsed">
            <component :is="collapsed ? 'Expand' : 'Fold'" />
          </el-icon>
          <div class="tf-header-title">
            {{ currentTitle }}
            <small>{{ subTitle }}</small>
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 10px">
          <el-tag v-if="backendOk === true" type="success" effect="light" size="small">服务正常</el-tag>
          <el-tag v-else-if="backendOk === false" type="danger" effect="light" size="small">后端未连接</el-tag>
          <el-button size="small" text @click="loadStats">
            <el-icon><Refresh /></el-icon>
          </el-button>
          <el-link href="/docs" target="_blank" type="primary" :underline="false">API 文档</el-link>
        </div>
      </el-header>

      <el-main class="tf-main">
        <router-view v-slot="{ Component }">
          <keep-alive :include="['ChatView']">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>
