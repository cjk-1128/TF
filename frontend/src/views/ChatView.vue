<script lang="ts">
export default { name: 'ChatView' }
</script>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownIt from 'markdown-it'
import { kbApi, ragApi } from '@/api'
import CitationList from '@/components/CitationList.vue'
import ConfidenceTag from '@/components/ConfidenceTag.vue'
import StageTimeline from '@/components/StageTimeline.vue'
import ChunkCard from '@/components/ChunkCard.vue'
import type { ChatMessageVM, Citation, Conversation, KnowledgeBase } from '@/types'

const md = new MarkdownIt({ html: false, breaks: true, linkify: true })

const kbs = ref<KnowledgeBase[]>([])
const conversations = ref<Conversation[]>([])
const conversationId = ref<string>('')
const messages = ref<ChatMessageVM[]>([])
const query = ref('')
const sending = ref(false)
const bodyRef = ref<HTMLElement | null>(null)
const rightTab = ref('trace')

const selectedKbs = ref<string[]>([])
const selectedDomains = ref<string[]>([])
const ctx = ref({ project_name: '', project_type: '', discipline: 'general', region: '' })

const previewVisible = ref(false)
const previewCitation = ref<Citation | null>(null)

const lastAssistant = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].role === 'assistant' && !messages.value[i].loading) return messages.value[i]
  }
  return null
})

const domainOptions = [
  { value: 'standard', label: '建设规范库' },
  { value: 'case', label: '项目案例库' },
  { value: 'enterprise', label: '企业知识库' }
]

const disciplineOptions = [
  { value: 'general', label: '综合' },
  { value: 'structure', label: '结构工程' },
  { value: 'geotech', label: '岩土/基坑' },
  { value: 'municipal', label: '市政道桥' },
  { value: 'bridge', label: '桥梁工程' },
  { value: 'tunnel', label: '隧道工程' },
  { value: 'hydraulic', label: '水利工程' },
  { value: 'construction', label: '施工技术' },
  { value: 'safety', label: '安全管理' },
  { value: 'cost', label: '造价管理' }
]

const scenes = [
  {
    title: '工程规范智能查询',
    q: 'C60 混凝土冬期施工的养护时间和温度要求是什么？'
  },
  {
    title: '施工质量问题分析',
    q: '现浇楼板出现宽度 0.4mm 的裂缝，可能原因和处理措施有哪些？'
  },
  {
    title: '施工方案智能生成',
    q: '请生成一份深度 8m 的基坑支护监测方案要点，包含监测项目和报警值。'
  },
  {
    title: '工程案例经验检索',
    q: '有哪些类似的地铁车站深基坑变形超限处置案例可以参考？'
  }
]

function renderAnswer(text: string): string {
  const html = md.render(text || '')
  // 将 [1] [2] 形式的引用标记高亮
  return html.replace(/\[(\d{1,2})\]/g, '<span class="cite-ref">$1</span>')
}

async function scrollBottom() {
  await nextTick()
  if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
}

async function loadKbs() {
  const res = await kbApi.list()
  kbs.value = res.data || []
}

async function loadConversations() {
  const res = await ragApi.conversations({ page: 1, page_size: 30 })
  conversations.value = res.data?.items || []
}

async function openConversation(id: string) {
  conversationId.value = id
  const res = await ragApi.messages(id)
  messages.value = (res.data || []).map((m: any) => ({
    role: m.role,
    content: m.content,
    messageId: m.id,
    citations: m.citations || [],
    confidence: m.confidence,
    confidenceLevel: m.confidence_level,
    needReview: !!m.need_human_review,
    latencyMs: m.latency_ms
  }))
  scrollBottom()
}

function newConversation() {
  conversationId.value = ''
  messages.value = []
}

async function removeConversation(id: string) {
  await ElMessageBox.confirm('确认删除该会话及其全部消息？', '提示', { type: 'warning' })
  await ragApi.removeConversation(id)
  if (conversationId.value === id) newConversation()
  loadConversations()
  ElMessage.success('已删除')
}

async function send(text?: string) {
  const q = (text ?? query.value).trim()
  if (!q) return
  if (sending.value) return

  messages.value.push({ role: 'user', content: q })
  messages.value.push({ role: 'assistant', content: '', loading: true })
  query.value = ''
  sending.value = true
  scrollBottom()

  try {
    const res = await ragApi.chat({
      query: q,
      conversation_id: conversationId.value || null,
      kb_ids: selectedKbs.value,
      domains: selectedDomains.value,
      context: ctx.value
    })
    const d = res.data
    conversationId.value = d.conversation_id
    messages.value.pop()
    messages.value.push({
      role: 'assistant',
      content: d.answer,
      messageId: d.message_id,
      citations: d.citations,
      intentLabel: d.intent_label,
      confidence: d.confidence,
      confidenceLevel: d.confidence_level,
      needReview: d.need_human_review,
      reviewHint: d.review_hint,
      latencyMs: d.latency_ms,
      traces: d.stage_traces,
      retrieved: d.retrieved
    })
    loadConversations()
  } catch (e) {
    messages.value.pop()
    messages.value.push({ role: 'assistant', content: '请求失败，请检查后端服务是否已启动。' })
  } finally {
    sending.value = false
    scrollBottom()
  }
}

async function feedback(m: ChatMessageVM, rating: number) {
  if (!m.messageId) {
    ElMessage.warning('该消息暂不支持反馈')
    return
  }
  let reason = ''
  if (rating < 0) {
    try {
      const r = await ElMessageBox.prompt('请简述问题（如：引用条文过期、答非所问、缺少依据）', '需改进', {
        inputPlaceholder: '选填'
      })
      reason = r.value || ''
    } catch {
      return
    }
  }
  await ragApi.feedback({ message_id: m.messageId, rating, reason })
  m.rated = rating
  ElMessage.success(rating > 0 ? '感谢反馈，已记录为有帮助' : '已记录，该问题将进入知识盲区分析')
}

function preview(c: Citation) {
  previewCitation.value = c
  previewVisible.value = true
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) {
    e.preventDefault()
    send()
  }
}

onMounted(() => {
  loadKbs()
  loadConversations()
})
</script>

<template>
  <div class="chat-wrap">
    <!-- 左侧：会话列表 -->
    <div class="chat-left tf-card">
      <div style="padding: 12px 12px 8px">
        <el-button type="primary" style="width: 100%" @click="newConversation">
          <el-icon><Plus /></el-icon>&nbsp;新建会话
        </el-button>
      </div>
      <el-scrollbar style="flex: 1">
        <div style="padding: 0 8px 10px">
          <div v-if="!conversations.length" class="tf-muted" style="padding: 12px; font-size: 12px">
            暂无历史会话
          </div>
          <div
            v-for="c in conversations"
            :key="c.id"
            class="conv-item"
            :class="{ active: c.id === conversationId }"
            @click="openConversation(c.id)"
          >
            <span class="txt">{{ c.title }}</span>
            <el-icon style="flex: 0 0 auto" @click.stop="removeConversation(c.id)"><Delete /></el-icon>
          </div>
        </div>
      </el-scrollbar>
      <div style="border-top: 1px solid var(--tf-border); padding: 10px 12px">
        <div class="tf-muted" style="font-size: 12px; margin-bottom: 6px">工程上下文（Stage0）</div>
        <el-input v-model="ctx.project_name" size="small" placeholder="项目名称" style="margin-bottom: 6px" />
        <el-input v-model="ctx.project_type" size="small" placeholder="项目类型，如地铁车站" style="margin-bottom: 6px" />
        <el-select v-model="ctx.discipline" size="small" style="width: 100%; margin-bottom: 6px">
          <el-option v-for="d in disciplineOptions" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
        <el-input v-model="ctx.region" size="small" placeholder="所在地区" />
      </div>
    </div>

    <!-- 中间：对话区 -->
    <div class="chat-center tf-card">
      <div ref="bodyRef" class="chat-body">
        <div v-if="!messages.length" class="chat-empty">
          <el-icon style="font-size: 42px; color: var(--tf-primary)"><ChatDotRound /></el-icon>
          <h3>TerraForge 工程知识助手</h3>
          <div style="font-size: 13px">
            所有回答均来自平台知识库并标注条文出处，置信度不足时会提示人工复核
          </div>
          <div class="scene-cards">
            <div v-for="s in scenes" :key="s.title" class="scene-card" @click="send(s.q)">
              <b>{{ s.title }}</b>
              <span class="tf-muted">{{ s.q }}</span>
            </div>
          </div>
        </div>

        <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
          <div class="msg-avatar" :class="m.role === 'user' ? 'user' : 'bot'">
            <el-icon><component :is="m.role === 'user' ? 'User' : 'Cpu'" /></el-icon>
          </div>
          <div class="msg-bubble">
            <template v-if="m.loading">
              <span class="tf-muted">正在执行 Stage0→Stage7 检索与生成…</span>
              <el-progress :percentage="100" :indeterminate="true" :show-text="false" style="margin-top: 8px" />
            </template>
            <template v-else-if="m.role === 'user'">{{ m.content }}</template>
            <template v-else>
              <div class="msg-meta">
                <el-tag v-if="m.intentLabel" size="small" effect="plain">{{ m.intentLabel }}</el-tag>
                <ConfidenceTag v-if="m.confidence !== undefined" :value="m.confidence" :level="m.confidenceLevel" />
                <span v-if="m.latencyMs" class="tf-muted" style="font-size: 12px">{{ m.latencyMs }}ms</span>
              </div>
              <el-alert
                v-if="m.needReview"
                type="warning"
                :closable="false"
                show-icon
                :title="m.reviewHint || '本回答置信度较低，请由专业工程师复核后使用'"
                style="margin-bottom: 10px"
              />
              <div class="answer-md" v-html="renderAnswer(m.content)" />
              <CitationList :citations="m.citations || []" @preview="preview" />
              <div v-if="m.messageId" style="margin-top: 8px">
                <el-button size="small" text :type="m.rated === 1 ? 'primary' : ''" @click="feedback(m, 1)">
                  <el-icon><Select /></el-icon>&nbsp;有帮助
                </el-button>
                <el-button size="small" text :type="m.rated === -1 ? 'danger' : ''" @click="feedback(m, -1)">
                  <el-icon><CloseBold /></el-icon>&nbsp;需改进
                </el-button>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="chat-input">
        <div class="chat-input-tools">
          <el-select
            v-model="selectedKbs"
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            size="small"
            placeholder="全部知识库"
            style="width: 220px"
          >
            <el-option v-for="k in kbs" :key="k.id" :label="k.name" :value="k.id" />
          </el-select>
          <el-select
            v-model="selectedDomains"
            multiple
            collapse-tags
            clearable
            size="small"
            placeholder="全部知识域"
            style="width: 190px"
          >
            <el-option v-for="d in domainOptions" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
          <span class="tf-muted" style="font-size: 12px">Enter 发送 / Shift+Enter 换行</span>
        </div>
        <el-input
          v-model="query"
          type="textarea"
          :rows="3"
          resize="none"
          placeholder="请输入工程问题，例如：地下室外墙防水混凝土的抗渗等级如何确定？"
          @keydown="onKeydown"
        />
        <div class="chat-input-actions">
          <span class="tf-muted" style="font-size: 12px">
            回答严格基于知识库内容，禁止无依据推测；如无匹配知识将提示补充资料
          </span>
          <el-button type="primary" :loading="sending" @click="send()">
            发送<el-icon class="el-icon--right"><Promotion /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 右侧：链路与召回 -->
    <div class="chat-right tf-card" style="padding: 12px">
      <el-tabs v-model="rightTab">
        <el-tab-pane label="执行链路" name="trace">
          <StageTimeline :traces="lastAssistant?.traces || []" />
        </el-tab-pane>
        <el-tab-pane :label="`召回片段 (${lastAssistant?.retrieved?.length || 0})`" name="chunks">
          <div v-if="!lastAssistant?.retrieved?.length" class="tf-muted" style="font-size: 12px">
            暂无召回结果
          </div>
          <ChunkCard
            v-for="(c, i) in lastAssistant?.retrieved || []"
            :key="c.chunk_id"
            :chunk="c"
            :rank="i + 1"
          />
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 引用原文预览 -->
    <el-drawer v-model="previewVisible" title="引用原文" size="520px">
      <template v-if="previewCitation">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="文档">{{ previewCitation.doc_title }}</el-descriptions-item>
          <el-descriptions-item v-if="previewCitation.standard_code" label="标准编号">
            {{ previewCitation.standard_code }}
          </el-descriptions-item>
          <el-descriptions-item v-if="previewCitation.clause_no" label="条文号">
            {{ previewCitation.clause_no }}
          </el-descriptions-item>
          <el-descriptions-item v-if="previewCitation.section_path" label="章节路径">
            {{ previewCitation.section_path }}
          </el-descriptions-item>
          <el-descriptions-item label="相关度">
            {{ (previewCitation.score * 100).toFixed(1) }}%
          </el-descriptions-item>
        </el-descriptions>
        <div class="chunk-card" style="margin-top: 14px">
          <div class="content">{{ previewCitation.snippet }}</div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>
