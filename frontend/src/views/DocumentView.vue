<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadUserFile } from 'element-plus'
import { docApi, kbApi } from '@/api'
import type { ChunkItem, DocumentItem, KnowledgeBase } from '@/types'

const route = useRoute()
const kbs = ref<KnowledgeBase[]>([])
const list = ref<DocumentItem[]>([])
const total = ref(0)
const loading = ref(false)

const query = reactive({
  kb_id: (route.query.kb_id as string) || '',
  status: '',
  governance_status: '',
  keyword: '',
  page: 1,
  page_size: 20
})

const statusMap: Record<string, { label: string; type: string }> = {
  pending: { label: '待处理', type: 'info' },
  parsing: { label: '解析中', type: 'warning' },
  indexing: { label: '索引中', type: 'warning' },
  ready: { label: '已就绪', type: 'success' },
  failed: { label: '失败', type: 'danger' }
}

const govMap: Record<string, { label: string; type: string }> = {
  valid: { label: '现行有效', type: 'success' },
  need_update: { label: '待更新', type: 'warning' },
  deprecated: { label: '已废止', type: 'danger' },
  draft: { label: '草稿', type: 'info' }
}

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

/* ---------------- 列表 ---------------- */
async function load() {
  loading.value = true
  try {
    const res = await docApi.list({ ...query })
    list.value = res.data?.items || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

/* ---------------- 上传入库 ---------------- */
const uploadVisible = ref(false)
const uploading = ref(false)
const fileList = ref<UploadUserFile[]>([])
const uploadForm = reactive({
  kb_id: '',
  standard_code: '',
  standard_name: '',
  discipline: 'general',
  project_name: '',
  owner: '',
  version: '1.0',
  effective_date: '',
  expire_date: '',
  tags: [] as string[]
})

function openUpload() {
  uploadForm.kb_id = query.kb_id || kbs.value[0]?.id || ''
  fileList.value = []
  uploadVisible.value = true
}

async function submitUpload() {
  if (!uploadForm.kb_id) return ElMessage.warning('请选择目标知识库')
  if (!fileList.value.length) return ElMessage.warning('请先选择文件')
  uploading.value = true
  try {
    const files = fileList.value.map((f) => f.raw as File).filter(Boolean)
    const meta: Record<string, any> = {
      standard_code: uploadForm.standard_code,
      standard_name: uploadForm.standard_name,
      discipline: uploadForm.discipline,
      project_name: uploadForm.project_name,
      owner: uploadForm.owner,
      version: uploadForm.version,
      tags: uploadForm.tags
    }
    if (uploadForm.effective_date) meta.effective_date = uploadForm.effective_date
    if (uploadForm.expire_date) meta.expire_date = uploadForm.expire_date
    const res = await docApi.upload(uploadForm.kb_id, files, meta)
    ElMessage.success(`已入库 ${res.data?.length || 0} 个文件`)
    uploadVisible.value = false
    load()
  } finally {
    uploading.value = false
  }
}

/* ---------------- 文本入库 ---------------- */
const textVisible = ref(false)
const textSubmitting = ref(false)
const textForm = reactive({ kb_id: '', title: '', content: '', discipline: 'general', owner: '' })

function openText() {
  textForm.kb_id = query.kb_id || kbs.value[0]?.id || ''
  textForm.title = ''
  textForm.content = ''
  textVisible.value = true
}

async function submitText() {
  if (!textForm.kb_id || !textForm.title.trim() || textForm.content.trim().length < 10) {
    return ElMessage.warning('请填写知识库、标题，且正文不少于 10 个字')
  }
  textSubmitting.value = true
  try {
    await docApi.ingestText({
      kb_id: textForm.kb_id,
      title: textForm.title,
      content: textForm.content,
      meta: { discipline: textForm.discipline, owner: textForm.owner }
    })
    ElMessage.success('入库完成')
    textVisible.value = false
    load()
  } finally {
    textSubmitting.value = false
  }
}

/* ---------------- 编辑元数据 ---------------- */
const editVisible = ref(false)
const editForm = reactive<Record<string, any>>({})
const editingId = ref('')

function openEdit(row: DocumentItem) {
  editingId.value = row.id
  Object.assign(editForm, {
    title: row.title,
    standard_code: row.standard_code,
    standard_name: row.standard_name,
    discipline: row.discipline,
    project_name: row.project_name,
    owner: row.owner,
    version: row.version,
    governance_status: row.governance_status,
    tags: [...(row.tags || [])],
    summary: row.summary
  })
  editVisible.value = true
}

async function submitEdit() {
  await docApi.update(editingId.value, { ...editForm })
  ElMessage.success('已更新')
  editVisible.value = false
  load()
}

/* ---------------- 切片查看 ---------------- */
const chunkVisible = ref(false)
const chunks = ref<ChunkItem[]>([])
const chunkTotal = ref(0)
const chunkLoading = ref(false)
const chunkDoc = ref<DocumentItem | null>(null)
const chunkPage = reactive({ page: 1, page_size: 20, keyword: '' })

async function openChunks(row: DocumentItem) {
  chunkDoc.value = row
  chunkPage.page = 1
  chunkPage.keyword = ''
  chunkVisible.value = true
  loadChunks()
}

async function loadChunks() {
  if (!chunkDoc.value) return
  chunkLoading.value = true
  try {
    const res = await docApi.chunks(chunkDoc.value.id, { ...chunkPage })
    chunks.value = res.data?.items || []
    chunkTotal.value = res.data?.total || 0
  } finally {
    chunkLoading.value = false
  }
}

/* ---------------- 其他操作 ---------------- */
async function reindex(row: DocumentItem) {
  await ElMessageBox.confirm('将重新解析、切片并重建向量与 BM25 索引，确认继续？', '重建索引')
  await docApi.reindex(row.id)
  ElMessage.success('已重建索引')
  load()
}

async function remove(row: DocumentItem) {
  await ElMessageBox.confirm(`确认删除文档「${row.title}」及其全部切片？`, '危险操作', { type: 'warning' })
  await docApi.remove(row.id)
  ElMessage.success('已删除')
  load()
}

function fmtSize(n: number) {
  if (!n) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(2)} MB`
}

function fmtDate(s?: string) {
  return s ? s.slice(0, 10) : '—'
}

onMounted(async () => {
  const res = await kbApi.list()
  kbs.value = res.data || []
  load()
})
</script>

<template>
  <div>
    <div class="tf-card" style="padding: 16px">
      <div style="display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin-bottom: 14px">
        <div style="display: flex; gap: 10px; flex-wrap: wrap">
          <el-select v-model="query.kb_id" placeholder="全部知识库" clearable style="width: 190px"
                     @change="() => { query.page = 1; load() }">
            <el-option v-for="k in kbs" :key="k.id" :label="k.name" :value="k.id" />
          </el-select>
          <el-select v-model="query.status" placeholder="处理状态" clearable style="width: 130px"
                     @change="() => { query.page = 1; load() }">
            <el-option v-for="(v, k) in statusMap" :key="k" :label="v.label" :value="k" />
          </el-select>
          <el-select v-model="query.governance_status" placeholder="治理状态" clearable style="width: 130px"
                     @change="() => { query.page = 1; load() }">
            <el-option v-for="(v, k) in govMap" :key="k" :label="v.label" :value="k" />
          </el-select>
          <el-input v-model="query.keyword" placeholder="标题 / 标准编号 / 项目名" clearable style="width: 230px"
                    @keyup.enter="() => { query.page = 1; load() }" @clear="load">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button @click="load"><el-icon><Refresh /></el-icon>&nbsp;刷新</el-button>
        </div>
        <div>
          <el-button @click="openText"><el-icon><EditPen /></el-icon>&nbsp;文本入库</el-button>
          <el-button type="primary" @click="openUpload">
            <el-icon><UploadFilled /></el-icon>&nbsp;上传工程资料
          </el-button>
        </div>
      </div>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column label="文档" min-width="260">
          <template #default="{ row }">
            <div style="font-weight: 600">
              <span v-if="row.standard_code" style="color: var(--tf-primary)">《{{ row.standard_code }}》</span>
              {{ row.title }}
            </div>
            <div class="tf-muted" style="font-size: 12px">
              {{ row.file_name || '文本录入' }} · {{ fmtSize(row.file_size) }} · {{ row.chunk_count }} 切片
            </div>
          </template>
        </el-table-column>
        <el-table-column label="专业" width="110">
          <template #default="{ row }">
            {{ disciplineOptions.find((d) => d.value === row.discipline)?.label || row.discipline }}
          </template>
        </el-table-column>
        <el-table-column label="项目" width="150">
          <template #default="{ row }">{{ row.project_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="有效期" width="180">
          <template #default="{ row }">
            <span class="tf-muted" style="font-size: 12px">
              {{ fmtDate(row.effective_date) }} ~ {{ fmtDate(row.expire_date) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="治理状态" width="105">
          <template #default="{ row }">
            <el-tag :type="(govMap[row.governance_status]?.type as any) || 'info'" size="small" effect="light">
              {{ govMap[row.governance_status]?.label || row.governance_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="处理状态" width="100">
          <template #default="{ row }">
            <el-tooltip v-if="row.error_msg" :content="row.error_msg">
              <el-tag type="danger" size="small">失败</el-tag>
            </el-tooltip>
            <el-tag v-else :type="(statusMap[row.status]?.type as any) || 'info'" size="small" effect="plain">
              {{ statusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openChunks(row)">切片</el-button>
            <el-button link type="primary" @click="openEdit(row)">元数据</el-button>
            <el-button link type="warning" @click="reindex(row)">重建索引</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无文档，请上传规范 / 案例 / 企业资料" /></template>
      </el-table>

      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 14px; justify-content: flex-end"
        @current-change="load"
        @size-change="load"
      />
    </div>

    <!-- 上传 -->
    <el-dialog v-model="uploadVisible" title="上传工程资料" width="640px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="支持 PDF / Word / Excel / Markdown / TXT。系统将按章节-条文结构切片，保留表格块并识别强制性条文。"
        style="margin-bottom: 14px"
      />
      <el-form :model="uploadForm" label-width="96px">
        <el-form-item label="目标知识库" required>
          <el-select v-model="uploadForm.kb_id" style="width: 100%">
            <el-option v-for="k in kbs" :key="k.id" :label="`${k.name}（${k.domain_label}）`" :value="k.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件">
          <el-upload
            v-model:file-list="fileList"
            drag
            multiple
            :auto-upload="false"
            accept=".pdf,.doc,.docx,.xls,.xlsx,.md,.txt"
            style="width: 100%"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">将文件拖到此处，或<em>点击选择</em></div>
          </el-upload>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="标准编号"><el-input v-model="uploadForm.standard_code" placeholder="如 GB50204-2015" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="标准名称"><el-input v-model="uploadForm.standard_name" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="专业">
              <el-select v-model="uploadForm.discipline" style="width: 100%">
                <el-option v-for="d in disciplineOptions" :key="d.value" :label="d.label" :value="d.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属项目"><el-input v-model="uploadForm.project_name" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="生效日期">
              <el-date-picker v-model="uploadForm.effective_date" type="date" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="失效日期">
              <el-date-picker v-model="uploadForm.expire_date" type="date" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="责任人"><el-input v-model="uploadForm.owner" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="版本"><el-input v-model="uploadForm.version" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">开始入库</el-button>
      </template>
    </el-dialog>

    <!-- 文本入库 -->
    <el-dialog v-model="textVisible" title="文本直接入库（会议纪要 / FAQ / 复盘）" width="640px">
      <el-form :model="textForm" label-width="90px">
        <el-form-item label="知识库" required>
          <el-select v-model="textForm.kb_id" style="width: 100%">
            <el-option v-for="k in kbs" :key="k.id" :label="k.name" :value="k.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" required><el-input v-model="textForm.title" /></el-form-item>
        <el-form-item label="专业">
          <el-select v-model="textForm.discipline" style="width: 100%">
            <el-option v-for="d in disciplineOptions" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="正文" required>
          <el-input v-model="textForm.content" type="textarea" :rows="10"
                    placeholder="支持 Markdown 标题结构，系统会据此建立章节路径" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="textVisible = false">取消</el-button>
        <el-button type="primary" :loading="textSubmitting" @click="submitText">入库</el-button>
      </template>
    </el-dialog>

    <!-- 元数据编辑 -->
    <el-dialog v-model="editVisible" title="编辑文档元数据" width="600px">
      <el-form :model="editForm" label-width="96px">
        <el-form-item label="标题"><el-input v-model="editForm.title" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="标准编号"><el-input v-model="editForm.standard_code" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="标准名称"><el-input v-model="editForm.standard_name" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="专业">
              <el-select v-model="editForm.discipline" style="width: 100%">
                <el-option v-for="d in disciplineOptions" :key="d.value" :label="d.label" :value="d.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="治理状态">
              <el-select v-model="editForm.governance_status" style="width: 100%">
                <el-option v-for="(v, k) in govMap" :key="k" :label="v.label" :value="k" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12"><el-form-item label="所属项目"><el-input v-model="editForm.project_name" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="责任人"><el-input v-model="editForm.owner" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="摘要"><el-input v-model="editForm.summary" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 切片抽屉 -->
    <el-drawer v-model="chunkVisible" size="640px" :title="`知识切片 · ${chunkDoc?.title || ''}`">
      <div style="display: flex; gap: 8px; margin-bottom: 12px">
        <el-input v-model="chunkPage.keyword" placeholder="在切片内搜索" clearable
                  @keyup.enter="() => { chunkPage.page = 1; loadChunks() }" @clear="loadChunks" />
        <el-button @click="() => { chunkPage.page = 1; loadChunks() }">搜索</el-button>
      </div>
      <div v-loading="chunkLoading">
        <div v-for="c in chunks" :key="c.id" class="chunk-card">
          <div class="head">
            <span>
              #{{ c.seq }}
              <span v-if="c.clause_no" style="margin-left: 6px">条文 {{ c.clause_no }}</span>
              <span v-if="c.page_no" style="margin-left: 6px">P{{ c.page_no }}</span>
              <el-tag v-if="c.is_mandatory" type="danger" size="small" effect="light" style="margin-left: 6px">
                强制性条文
              </el-tag>
            </span>
            <span>{{ c.char_count }} 字</span>
          </div>
          <div v-if="c.section_path" class="tf-muted" style="font-size: 12px; margin-bottom: 4px">
            {{ c.section_path }}
          </div>
          <div class="content">{{ c.content }}</div>
        </div>
        <el-empty v-if="!chunks.length && !chunkLoading" description="暂无切片" />
      </div>
      <el-pagination
        v-model:current-page="chunkPage.page"
        :page-size="chunkPage.page_size"
        :total="chunkTotal"
        layout="total, prev, pager, next"
        style="margin-top: 10px; justify-content: flex-end"
        @current-change="loadChunks"
      />
    </el-drawer>
  </div>
</template>
