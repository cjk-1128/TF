import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/chat' },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('@/views/ChatView.vue'),
    meta: { title: '工程智能问答', icon: 'ChatDotRound' }
  },
  {
    path: '/search',
    name: 'search',
    component: () => import('@/views/SearchView.vue'),
    meta: { title: '知识片段检索', icon: 'Search' }
  },
  {
    path: '/knowledge',
    name: 'knowledge',
    component: () => import('@/views/KnowledgeBaseView.vue'),
    meta: { title: '知识库管理', icon: 'Collection' }
  },
  {
    path: '/documents',
    name: 'documents',
    component: () => import('@/views/DocumentView.vue'),
    meta: { title: '文档与切片', icon: 'Document' }
  },
  {
    path: '/governance',
    name: 'governance',
    component: () => import('@/views/GovernanceView.vue'),
    meta: { title: '知识治理闭环', icon: 'DataAnalysis' }
  },
  {
    path: '/eval',
    name: 'eval',
    component: () => import('@/views/EvalView.vue'),
    meta: { title: '检索评测看板', icon: 'TrendCharts' }
  },
  {
    path: '/quality',
    name: 'quality',
    component: () => import('@/views/QualityView.vue'),
    meta: { title: '质量巡检 Agent', icon: 'Stamp' }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/chat'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.afterEach((to) => {
  const title = (to.meta?.title as string) || ''
  document.title = title ? `${title} · TerraForge 土木工程智能知识平台` : 'TerraForge 土木工程智能知识平台'
})

export default router
