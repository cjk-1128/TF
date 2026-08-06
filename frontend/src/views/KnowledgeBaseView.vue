<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { kbApi } from '@/api'
import type { KnowledgeBase } from '@/types'

const router = useRouter()
const list = ref<KnowledgeBase[]>([])
const loading = ref(false)
const stats = ref<Record<string, number>>({})
const filter = reactive({ domain: '', keyword: '' })

const dialogVisible = ref(false)
const editing = ref<KnowledgeBase | null>(null)
const form = reactive({
  name: '',
  domain: 'standard',
  description: '',
  owner: '',
  tags: [] as string[]
})

const domainOptions = [
  { value: 'standard', label: '建设规范库', desc: '国家/行业/地方标准、规范、图集、强制性条文' },
  { value: 'case', label: '项目案例库', desc: '典型工程案例、事故复盘、变更与索赔记录' },
  { value: 'enterprise', label: '企业知识库', desc: '企业标准、施工工法、专家经验、内部制度' }
]

const domainTagType: Record<string, string> = {
  standard: 'primary',
  case: 'success',
  enterprise: 'warning'
}

async function load() {
  loading.value = true
  try {
    const res = await kbApi.list({
      domain: filter.domain || undefined,
      keyword: filter.keyword || undefined
    })
    list.value = res.data || []
    const s = await kbApi.stats()
    stats.value = s.data || {}
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { name: '', domain: 'standard', description: '', owner: '', tags: [] })
  dialogVisible.value = true
}

function openEdit(row: KnowledgeBase) {
  editing.value = row
  Object.assign(form, {
    name: row.name,
    domain: row.domain,
    description: row.description,
    owner: row.owner,
    tags: [...(row.tags || [])]
  })
  dialogVisible.value = true
}

async function submit() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写知识库名称')
    return
  }
  if (editing.value) {
    await kbApi.update(editing.value.id, {
      name: form.name,
      description: form.description,
      owner: form.owner,
      tags: form.tags
    })
    ElMessage.success('更新成功')
  } else {
    await kbApi.create({ ...form } as any)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  load()
}

async function remove(row: KnowledgeBase) {
  await ElMessageBox.confirm(
    `确认删除知识库「${row.name}」？其下 ${row.doc_count} 篇文档与 ${row.chunk_count} 个切片将一并移除。`,
    '危险操作',
    { type: 'warning', confirmButtonText: '确认删除', confirmButtonClass: 'el-button--danger' }
  )
  await kbApi.remove(row.id)
  ElMessage.success('已删除')
  load()
}

function gotoDocs(row: KnowledgeBase) {
  router.push({ path: '/documents', query: { kb_id: row.id } })
}

onMounted(load)
</script>

<template>
  <div>
    <div class="stat-grid" style="margin-bottom: 14px">
      <div class="stat-card">
        <div class="label">知识库总数</div>
        <div class="value">{{ stats.kb_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="label">文档总数</div>
        <div class="value">{{ stats.doc_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="label">知识切片</div>
        <div class="value">{{ stats.chunk_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="label">规范类文档</div>
        <div class="value">{{ stats.standard_docs ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="label">案例类文档</div>
        <div class="value">{{ stats.case_docs ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="label">企业类文档</div>
        <div class="value">{{ stats.enterprise_docs ?? 0 }}</div>
      </div>
    </div>

    <div class="tf-card" style="padding: 16px">
      <div style="display: flex; justify-content: space-between; margin-bottom: 14px; gap: 10px; flex-wrap: wrap">
        <div style="display: flex; gap: 10px">
          <el-select v-model="filter.domain" placeholder="全部知识域" clearable style="width: 160px" @change="load">
            <el-option v-for="d in domainOptions" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
          <el-input
            v-model="filter.keyword"
            placeholder="搜索名称或描述"
            clearable
            style="width: 230px"
            @keyup.enter="load"
            @clear="load"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button @click="load"><el-icon><Refresh /></el-icon>&nbsp;刷新</el-button>
        </div>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>&nbsp;新建知识库
        </el-button>
      </div>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column label="知识库" min-width="230">
          <template #default="{ row }">
            <div style="font-weight: 600">{{ row.name }}</div>
            <div class="tf-muted" style="font-size: 12px">{{ row.description || '—' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="知识域" width="120">
          <template #default="{ row }">
            <el-tag :type="domainTagType[row.domain] || 'info'" effect="light">
              {{ row.domain_label || row.domain }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="文档 / 切片" width="130">
          <template #default="{ row }">{{ row.doc_count }} / {{ row.chunk_count }}</template>
        </el-table-column>
        <el-table-column prop="owner" label="责任人" width="110">
          <template #default="{ row }">{{ row.owner || '—' }}</template>
        </el-table-column>
        <el-table-column label="标签" min-width="150">
          <template #default="{ row }">
            <el-tag v-for="t in row.tags" :key="t" size="small" effect="plain" style="margin-right: 4px">
              {{ t }}
            </el-tag>
            <span v-if="!row.tags?.length" class="tf-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="gotoDocs(row)">文档</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无知识库，建议先创建「建设规范库 / 项目案例库 / 企业知识库」三域" />
        </template>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑知识库' : '新建知识库'" width="560px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：国家建设标准规范库" />
        </el-form-item>
        <el-form-item label="知识域">
          <el-radio-group v-model="form.domain" :disabled="!!editing">
            <el-radio-button v-for="d in domainOptions" :key="d.value" :value="d.value">
              {{ d.label }}
            </el-radio-button>
          </el-radio-group>
          <div class="tf-muted" style="font-size: 12px; margin-top: 4px">
            {{ domainOptions.find((d) => d.value === form.domain)?.desc }}
          </div>
        </el-form-item>
        <el-form-item label="责任人">
          <el-input v-model="form.owner" placeholder="如：技术质量部-张工" />
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="form.tags" multiple filterable allow-create default-first-option style="width: 100%"
                     placeholder="回车创建标签，如 结构、地基基础">
            <el-option v-for="t in ['结构', '地基基础', '市政', '桥梁', '隧道', '安全', '质量', '造价']"
                       :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="说明该知识库的收录范围与用途" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
