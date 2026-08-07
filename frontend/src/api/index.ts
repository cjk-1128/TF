import axios from 'axios'
import { ElMessage } from 'element-plus'
import type {
  ApiResponse, ChatResponse, ChunkItem, Conversation, DocumentItem,
  GovernanceTask, HealthReport, KnowledgeBase, KnowledgeGap,
  OperationReport, PageData, RetrievedChunk
} from '@/types'

const http = axios.create({ baseURL: '/api/v1', timeout: 120000 })

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.message || err.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(err)
  }
)

// ---------------- 知识库 ----------------
export const kbApi = {
  list: (params?: { domain?: string; keyword?: string }) =>
    http.get('/knowledge/kb', { params }) as unknown as Promise<ApiResponse<KnowledgeBase[]>>,
  create: (data: Partial<KnowledgeBase>) =>
    http.post('/knowledge/kb', data) as unknown as Promise<ApiResponse<KnowledgeBase>>,
  update: (id: string, data: Partial<KnowledgeBase>) =>
    http.put(`/knowledge/kb/${id}`, data) as unknown as Promise<ApiResponse<KnowledgeBase>>,
  remove: (id: string) =>
    http.delete(`/knowledge/kb/${id}`) as unknown as Promise<ApiResponse<any>>,
  stats: () =>
    http.get('/knowledge/stats') as unknown as Promise<ApiResponse<Record<string, number>>>
}

// ---------------- 文档 ----------------
export const docApi = {
  list: (params: Record<string, any>) =>
    http.get('/knowledge/documents', { params }) as unknown as Promise<ApiResponse<PageData<DocumentItem>>>,
  upload: (kbId: string, files: File[], meta: Record<string, any> = {}) => {
    const fd = new FormData()
    fd.append('kb_id', kbId)
    fd.append('meta', JSON.stringify(meta))
    files.forEach((f) => fd.append('files', f))
    return http.post('/knowledge/documents/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }) as unknown as Promise<ApiResponse<DocumentItem[]>>
  },
  ingestText: (data: { kb_id: string; title: string; content: string; meta?: any }) =>
    http.post('/knowledge/documents/text', data) as unknown as Promise<ApiResponse<DocumentItem>>,
  update: (id: string, data: Record<string, any>) =>
    http.put(`/knowledge/documents/${id}`, data) as unknown as Promise<ApiResponse<DocumentItem>>,
  remove: (id: string) =>
    http.delete(`/knowledge/documents/${id}`) as unknown as Promise<ApiResponse<any>>,
  reindex: (id: string) =>
    http.post(`/knowledge/documents/${id}/reindex`) as unknown as Promise<ApiResponse<DocumentItem>>,
  chunks: (id: string, params?: Record<string, any>) =>
    http.get(`/knowledge/documents/${id}/chunks`, { params }) as unknown as Promise<ApiResponse<PageData<ChunkItem>>>
}

// ---------------- 问答 ----------------
export const ragApi = {
  chat: (data: Record<string, any>) =>
    http.post('/rag/chat', data) as unknown as Promise<ApiResponse<ChatResponse>>,
  search: (data: Record<string, any>) =>
    http.post('/rag/search', data) as unknown as Promise<ApiResponse<RetrievedChunk[]>>,
  conversations: (params?: Record<string, any>) =>
    http.get('/rag/conversations', { params }) as unknown as Promise<ApiResponse<PageData<Conversation>>>,
  messages: (id: string) =>
    http.get(`/rag/conversations/${id}/messages`) as unknown as Promise<ApiResponse<any[]>>,
  removeConversation: (id: string) =>
    http.delete(`/rag/conversations/${id}`) as unknown as Promise<ApiResponse<any>>,
  feedback: (data: { message_id: string; rating: number; reason?: string; comment?: string }) =>
    http.post('/rag/feedback', data) as unknown as Promise<ApiResponse<any>>,
  explain: (data: Record<string, any>) =>
    http.post('/rag/explain', data) as unknown as Promise<ApiResponse<any>>
}

// ---------------- 治理 ----------------
export const govApi = {
  healthReport: (kbId?: string) =>
    http.get('/governance/health-report', { params: { kb_id: kbId } }) as unknown as Promise<ApiResponse<HealthReport>>,
  tasks: (params?: Record<string, any>) =>
    http.get('/governance/tasks', { params }) as unknown as Promise<ApiResponse<PageData<GovernanceTask>>>,
  createTask: (data: Record<string, any>) =>
    http.post('/governance/tasks', data) as unknown as Promise<ApiResponse<GovernanceTask>>,
  autoGenerate: (kbId?: string, assignee = '') =>
    http.post('/governance/tasks/auto-generate', null, {
      params: { kb_id: kbId, assignee }
    }) as unknown as Promise<ApiResponse<GovernanceTask[]>>,
  updateTask: (id: string, data: Record<string, any>) =>
    http.put(`/governance/tasks/${id}`, data) as unknown as Promise<ApiResponse<GovernanceTask>>,
  gaps: (days = 30) =>
    http.get('/governance/knowledge-gaps', { params: { days } }) as unknown as Promise<ApiResponse<KnowledgeGap[]>>,
  operationReport: (days = 7) =>
    http.get('/governance/operation-report', { params: { days } }) as unknown as Promise<ApiResponse<OperationReport>>
}

// ---------------- 评测 ----------------
export const evalApi = {
  run: (apiKey: string) =>
    http.post('/eval/run', {}, { headers: { 'X-API-Key': apiKey } }) as unknown as Promise<ApiResponse<any>>,
  golden: (apiKey: string) =>
    http.get('/eval/golden', { headers: { 'X-API-Key': apiKey } }) as unknown as Promise<ApiResponse<any>>,
  addGolden: (apiKey: string, data: Record<string, any>) =>
    http.post('/eval/golden', data, { headers: { 'X-API-Key': apiKey } }) as unknown as Promise<ApiResponse<any>>,
  deleteGolden: (apiKey: string, id: string) =>
    http.delete(`/eval/golden/${id}`, { headers: { 'X-API-Key': apiKey } }) as unknown as Promise<ApiResponse<any>>
}

// ---------------- 质量巡检 ----------------
export const qualityApi = {
  inspect: (apiKey: string, data: Record<string, any>) =>
    http.post('/quality/inspect', data, { headers: { 'X-API-Key': apiKey } }) as unknown as Promise<ApiResponse<any>>,
  reports: (apiKey: string, params?: Record<string, any>) =>
    http.get('/quality/reports', { params, headers: { 'X-API-Key': apiKey } }) as unknown as Promise<ApiResponse<any>>,
  report: (apiKey: string, id: string) =>
    http.get(`/quality/reports/${id}`, { headers: { 'X-API-Key': apiKey } }) as unknown as Promise<ApiResponse<any>>,
  convert: (apiKey: string, data: Record<string, any>) =>
    http.post('/quality/issues/convert', data, { headers: { 'X-API-Key': apiKey } }) as unknown as Promise<ApiResponse<any>>
}

export default http
