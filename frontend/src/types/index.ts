export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  trace_id: string
}

export interface PageData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface KnowledgeBase {
  id: string
  name: string
  domain: string
  domain_label: string
  description: string
  owner: string
  tags: string[]
  doc_count: number
  chunk_count: number
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface DocumentItem {
  id: string
  kb_id: string
  title: string
  file_name: string
  file_type: string
  file_size: number
  standard_code: string
  standard_name: string
  discipline: string
  project_name: string
  governance_status: string
  owner: string
  version: string
  summary: string
  keywords: string[]
  tags: string[]
  status: string
  error_msg: string
  chunk_count: number
  effective_date?: string
  expire_date?: string
  created_at?: string
  updated_at?: string
}

export interface ChunkItem {
  id: string
  doc_id: string
  seq: number
  content: string
  char_count: number
  section_path: string
  clause_no: string
  page_no: number
  is_mandatory: boolean
  domain: string
}

export interface Citation {
  index_no: number
  chunk_id: string
  doc_id: string
  doc_title: string
  standard_code: string
  section_path: string
  clause_no: string
  page_no: number
  snippet: string
  score: number
  domain: string
}

export interface RetrievedChunk {
  chunk_id: string
  doc_id: string
  doc_title: string
  standard_code: string
  section_path: string
  clause_no: string
  page_no: number
  domain: string
  content: string
  is_mandatory: boolean
  vector_score: number
  bm25_score: number
  fusion_score: number
  rerank_score: number
  final_score: number
}

export interface StageTrace {
  stage: string
  name: string
  elapsed_ms: number
  detail: Record<string, any>
}

export interface ChatResponse {
  conversation_id: string
  message_id: string
  query: string
  rewritten_query: string
  intent: string
  intent_label: string
  answer: string
  citations: Citation[]
  confidence: number
  confidence_level: string
  need_human_review: boolean
  review_hint: string
  retrieved: RetrievedChunk[]
  stage_traces: StageTrace[]
  latency_ms: number
  token_usage: Record<string, number>
}

export interface Conversation {
  id: string
  title: string
  user_id: string
  project_name: string
  project_type: string
  discipline: string
  region: string
  kb_ids: string[]
  message_count: number
  created_at?: string
  updated_at?: string
}

export interface HealthIssue {
  issue_type: string
  severity: string
  doc_id: string
  doc_title: string
  kb_id: string
  detail: string
  suggestion: string
}

export interface HealthReport {
  generated_at: string
  total_kb: number
  total_docs: number
  total_chunks: number
  valid_docs: number
  need_update_docs: number
  deprecated_docs: number
  failed_docs: number
  issues: HealthIssue[]
  score: number
  suggestions: string[]
}

export interface GovernanceTask {
  id: string
  task_type: string
  title: string
  description: string
  target_doc_ids: string[]
  kb_id: string
  priority: string
  status: string
  assignee: string
  watchers: string[]
  due_date?: string
  created_at?: string
}

export interface KnowledgeGap {
  query: string
  count: number
  avg_confidence: number
  suggestion: string
}

export interface OperationReport {
  period: string
  start: string
  end: string
  new_docs: number
  new_chunks: number
  total_queries: number
  unanswered_queries: number
  answer_rate: number
  avg_confidence: number
  avg_latency_ms: number
  hot_topics: { topic: string; count: number }[]
  knowledge_gaps: KnowledgeGap[]
  pending_tasks: number
  suggestions: string[]
}

export interface ChatMessageVM {
  role: 'user' | 'assistant'
  content: string
  messageId?: string
  rated?: number
  citations?: Citation[]
  intentLabel?: string
  confidence?: number
  confidenceLevel?: string
  needReview?: boolean
  reviewHint?: string
  latencyMs?: number
  traces?: StageTrace[]
  retrieved?: RetrievedChunk[]
  loading?: boolean
}
