/// <reference types="../../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
import { onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { docApi, kbApi } from '@/api';
const route = useRoute();
const kbs = ref([]);
const list = ref([]);
const total = ref(0);
const loading = ref(false);
const query = reactive({
    kb_id: route.query.kb_id || '',
    status: '',
    governance_status: '',
    keyword: '',
    page: 1,
    page_size: 20
});
const statusMap = {
    pending: { label: '待处理', type: 'info' },
    parsing: { label: '解析中', type: 'warning' },
    indexing: { label: '索引中', type: 'warning' },
    ready: { label: '已就绪', type: 'success' },
    failed: { label: '失败', type: 'danger' }
};
const govMap = {
    valid: { label: '现行有效', type: 'success' },
    need_update: { label: '待更新', type: 'warning' },
    deprecated: { label: '已废止', type: 'danger' },
    draft: { label: '草稿', type: 'info' }
};
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
];
/* ---------------- 列表 ---------------- */
async function load() {
    loading.value = true;
    try {
        const res = await docApi.list({ ...query });
        list.value = res.data?.items || [];
        total.value = res.data?.total || 0;
    }
    finally {
        loading.value = false;
    }
}
/* ---------------- 上传入库 ---------------- */
const uploadVisible = ref(false);
const uploading = ref(false);
const fileList = ref([]);
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
    tags: []
});
function openUpload() {
    uploadForm.kb_id = query.kb_id || kbs.value[0]?.id || '';
    fileList.value = [];
    uploadVisible.value = true;
}
async function submitUpload() {
    if (!uploadForm.kb_id)
        return ElMessage.warning('请选择目标知识库');
    if (!fileList.value.length)
        return ElMessage.warning('请先选择文件');
    uploading.value = true;
    try {
        const files = fileList.value.map((f) => f.raw).filter(Boolean);
        const meta = {
            standard_code: uploadForm.standard_code,
            standard_name: uploadForm.standard_name,
            discipline: uploadForm.discipline,
            project_name: uploadForm.project_name,
            owner: uploadForm.owner,
            version: uploadForm.version,
            tags: uploadForm.tags
        };
        if (uploadForm.effective_date)
            meta.effective_date = uploadForm.effective_date;
        if (uploadForm.expire_date)
            meta.expire_date = uploadForm.expire_date;
        const res = await docApi.upload(uploadForm.kb_id, files, meta);
        ElMessage.success(`已入库 ${res.data?.length || 0} 个文件`);
        uploadVisible.value = false;
        load();
    }
    finally {
        uploading.value = false;
    }
}
/* ---------------- 文本入库 ---------------- */
const textVisible = ref(false);
const textSubmitting = ref(false);
const textForm = reactive({ kb_id: '', title: '', content: '', discipline: 'general', owner: '' });
function openText() {
    textForm.kb_id = query.kb_id || kbs.value[0]?.id || '';
    textForm.title = '';
    textForm.content = '';
    textVisible.value = true;
}
async function submitText() {
    if (!textForm.kb_id || !textForm.title.trim() || textForm.content.trim().length < 10) {
        return ElMessage.warning('请填写知识库、标题，且正文不少于 10 个字');
    }
    textSubmitting.value = true;
    try {
        await docApi.ingestText({
            kb_id: textForm.kb_id,
            title: textForm.title,
            content: textForm.content,
            meta: { discipline: textForm.discipline, owner: textForm.owner }
        });
        ElMessage.success('入库完成');
        textVisible.value = false;
        load();
    }
    finally {
        textSubmitting.value = false;
    }
}
/* ---------------- 编辑元数据 ---------------- */
const editVisible = ref(false);
const editForm = reactive({});
const editingId = ref('');
function openEdit(row) {
    editingId.value = row.id;
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
    });
    editVisible.value = true;
}
async function submitEdit() {
    await docApi.update(editingId.value, { ...editForm });
    ElMessage.success('已更新');
    editVisible.value = false;
    load();
}
/* ---------------- 切片查看 ---------------- */
const chunkVisible = ref(false);
const chunks = ref([]);
const chunkTotal = ref(0);
const chunkLoading = ref(false);
const chunkDoc = ref(null);
const chunkPage = reactive({ page: 1, page_size: 20, keyword: '' });
async function openChunks(row) {
    chunkDoc.value = row;
    chunkPage.page = 1;
    chunkPage.keyword = '';
    chunkVisible.value = true;
    loadChunks();
}
async function loadChunks() {
    if (!chunkDoc.value)
        return;
    chunkLoading.value = true;
    try {
        const res = await docApi.chunks(chunkDoc.value.id, { ...chunkPage });
        chunks.value = res.data?.items || [];
        chunkTotal.value = res.data?.total || 0;
    }
    finally {
        chunkLoading.value = false;
    }
}
/* ---------------- 其他操作 ---------------- */
async function reindex(row) {
    await ElMessageBox.confirm('将重新解析、切片并重建向量与 BM25 索引，确认继续？', '重建索引');
    await docApi.reindex(row.id);
    ElMessage.success('已重建索引');
    load();
}
async function remove(row) {
    await ElMessageBox.confirm(`确认删除文档「${row.title}」及其全部切片？`, '危险操作', { type: 'warning' });
    await docApi.remove(row.id);
    ElMessage.success('已删除');
    load();
}
function fmtSize(n) {
    if (!n)
        return '—';
    if (n < 1024)
        return `${n} B`;
    if (n < 1024 * 1024)
        return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1024 / 1024).toFixed(2)} MB`;
}
function fmtDate(s) {
    return s ? s.slice(0, 10) : '—';
}
onMounted(async () => {
    const res = await kbApi.list();
    kbs.value = res.data || [];
    load();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tf-card" },
    ...{ style: {} },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ style: {} },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ style: {} },
});
const __VLS_0 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.query.kb_id),
    placeholder: "全部知识库",
    clearable: true,
    ...{ style: {} },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.query.kb_id),
    placeholder: "全部知识库",
    clearable: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onChange: (() => { __VLS_ctx.query.page = 1; __VLS_ctx.load(); })
};
__VLS_3.slots.default;
for (const [k] of __VLS_getVForSourceType((__VLS_ctx.kbs))) {
    const __VLS_8 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        key: (k.id),
        label: (k.name),
        value: (k.id),
    }));
    const __VLS_10 = __VLS_9({
        key: (k.id),
        label: (k.name),
        value: (k.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
}
var __VLS_3;
const __VLS_12 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.query.status),
    placeholder: "处理状态",
    clearable: true,
    ...{ style: {} },
}));
const __VLS_14 = __VLS_13({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.query.status),
    placeholder: "处理状态",
    clearable: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_16;
let __VLS_17;
let __VLS_18;
const __VLS_19 = {
    onChange: (() => { __VLS_ctx.query.page = 1; __VLS_ctx.load(); })
};
__VLS_15.slots.default;
for (const [v, k] of __VLS_getVForSourceType((__VLS_ctx.statusMap))) {
    const __VLS_20 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        key: (k),
        label: (v.label),
        value: (k),
    }));
    const __VLS_22 = __VLS_21({
        key: (k),
        label: (v.label),
        value: (k),
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
}
var __VLS_15;
const __VLS_24 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.query.governance_status),
    placeholder: "治理状态",
    clearable: true,
    ...{ style: {} },
}));
const __VLS_26 = __VLS_25({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.query.governance_status),
    placeholder: "治理状态",
    clearable: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onChange: (() => { __VLS_ctx.query.page = 1; __VLS_ctx.load(); })
};
__VLS_27.slots.default;
for (const [v, k] of __VLS_getVForSourceType((__VLS_ctx.govMap))) {
    const __VLS_32 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        key: (k),
        label: (v.label),
        value: (k),
    }));
    const __VLS_34 = __VLS_33({
        key: (k),
        label: (v.label),
        value: (k),
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
}
var __VLS_27;
const __VLS_36 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    ...{ 'onKeyup': {} },
    ...{ 'onClear': {} },
    modelValue: (__VLS_ctx.query.keyword),
    placeholder: "标题 / 标准编号 / 项目名",
    clearable: true,
    ...{ style: {} },
}));
const __VLS_38 = __VLS_37({
    ...{ 'onKeyup': {} },
    ...{ 'onClear': {} },
    modelValue: (__VLS_ctx.query.keyword),
    placeholder: "标题 / 标准编号 / 项目名",
    clearable: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
let __VLS_40;
let __VLS_41;
let __VLS_42;
const __VLS_43 = {
    onKeyup: (() => { __VLS_ctx.query.page = 1; __VLS_ctx.load(); })
};
const __VLS_44 = {
    onClear: (__VLS_ctx.load)
};
__VLS_39.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_39.slots;
    const __VLS_45 = {}.ElIcon;
    /** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
    // @ts-ignore
    const __VLS_46 = __VLS_asFunctionalComponent(__VLS_45, new __VLS_45({}));
    const __VLS_47 = __VLS_46({}, ...__VLS_functionalComponentArgsRest(__VLS_46));
    __VLS_48.slots.default;
    const __VLS_49 = {}.Search;
    /** @type {[typeof __VLS_components.Search, ]} */ ;
    // @ts-ignore
    const __VLS_50 = __VLS_asFunctionalComponent(__VLS_49, new __VLS_49({}));
    const __VLS_51 = __VLS_50({}, ...__VLS_functionalComponentArgsRest(__VLS_50));
    var __VLS_48;
}
var __VLS_39;
const __VLS_53 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_54 = __VLS_asFunctionalComponent(__VLS_53, new __VLS_53({
    ...{ 'onClick': {} },
}));
const __VLS_55 = __VLS_54({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_54));
let __VLS_57;
let __VLS_58;
let __VLS_59;
const __VLS_60 = {
    onClick: (__VLS_ctx.load)
};
__VLS_56.slots.default;
const __VLS_61 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_62 = __VLS_asFunctionalComponent(__VLS_61, new __VLS_61({}));
const __VLS_63 = __VLS_62({}, ...__VLS_functionalComponentArgsRest(__VLS_62));
__VLS_64.slots.default;
const __VLS_65 = {}.Refresh;
/** @type {[typeof __VLS_components.Refresh, ]} */ ;
// @ts-ignore
const __VLS_66 = __VLS_asFunctionalComponent(__VLS_65, new __VLS_65({}));
const __VLS_67 = __VLS_66({}, ...__VLS_functionalComponentArgsRest(__VLS_66));
var __VLS_64;
var __VLS_56;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
const __VLS_69 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_70 = __VLS_asFunctionalComponent(__VLS_69, new __VLS_69({
    ...{ 'onClick': {} },
}));
const __VLS_71 = __VLS_70({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_70));
let __VLS_73;
let __VLS_74;
let __VLS_75;
const __VLS_76 = {
    onClick: (__VLS_ctx.openText)
};
__VLS_72.slots.default;
const __VLS_77 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_78 = __VLS_asFunctionalComponent(__VLS_77, new __VLS_77({}));
const __VLS_79 = __VLS_78({}, ...__VLS_functionalComponentArgsRest(__VLS_78));
__VLS_80.slots.default;
const __VLS_81 = {}.EditPen;
/** @type {[typeof __VLS_components.EditPen, ]} */ ;
// @ts-ignore
const __VLS_82 = __VLS_asFunctionalComponent(__VLS_81, new __VLS_81({}));
const __VLS_83 = __VLS_82({}, ...__VLS_functionalComponentArgsRest(__VLS_82));
var __VLS_80;
var __VLS_72;
const __VLS_85 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_86 = __VLS_asFunctionalComponent(__VLS_85, new __VLS_85({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_87 = __VLS_86({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_86));
let __VLS_89;
let __VLS_90;
let __VLS_91;
const __VLS_92 = {
    onClick: (__VLS_ctx.openUpload)
};
__VLS_88.slots.default;
const __VLS_93 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_94 = __VLS_asFunctionalComponent(__VLS_93, new __VLS_93({}));
const __VLS_95 = __VLS_94({}, ...__VLS_functionalComponentArgsRest(__VLS_94));
__VLS_96.slots.default;
const __VLS_97 = {}.UploadFilled;
/** @type {[typeof __VLS_components.UploadFilled, ]} */ ;
// @ts-ignore
const __VLS_98 = __VLS_asFunctionalComponent(__VLS_97, new __VLS_97({}));
const __VLS_99 = __VLS_98({}, ...__VLS_functionalComponentArgsRest(__VLS_98));
var __VLS_96;
var __VLS_88;
const __VLS_101 = {}.ElTable;
/** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
// @ts-ignore
const __VLS_102 = __VLS_asFunctionalComponent(__VLS_101, new __VLS_101({
    data: (__VLS_ctx.list),
    stripe: true,
}));
const __VLS_103 = __VLS_102({
    data: (__VLS_ctx.list),
    stripe: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_102));
__VLS_asFunctionalDirective(__VLS_directives.vLoading)(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.loading) }, null, null);
__VLS_104.slots.default;
const __VLS_105 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_106 = __VLS_asFunctionalComponent(__VLS_105, new __VLS_105({
    label: "文档",
    minWidth: "260",
}));
const __VLS_107 = __VLS_106({
    label: "文档",
    minWidth: "260",
}, ...__VLS_functionalComponentArgsRest(__VLS_106));
__VLS_108.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_108.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ style: {} },
    });
    if (row.standard_code) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ style: {} },
        });
        (row.standard_code);
    }
    (row.title);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tf-muted" },
        ...{ style: {} },
    });
    (row.file_name || '文本录入');
    (__VLS_ctx.fmtSize(row.file_size));
    (row.chunk_count);
}
var __VLS_108;
const __VLS_109 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_110 = __VLS_asFunctionalComponent(__VLS_109, new __VLS_109({
    label: "专业",
    width: "110",
}));
const __VLS_111 = __VLS_110({
    label: "专业",
    width: "110",
}, ...__VLS_functionalComponentArgsRest(__VLS_110));
__VLS_112.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_112.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    (__VLS_ctx.disciplineOptions.find((d) => d.value === row.discipline)?.label || row.discipline);
}
var __VLS_112;
const __VLS_113 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_114 = __VLS_asFunctionalComponent(__VLS_113, new __VLS_113({
    label: "项目",
    width: "150",
}));
const __VLS_115 = __VLS_114({
    label: "项目",
    width: "150",
}, ...__VLS_functionalComponentArgsRest(__VLS_114));
__VLS_116.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_116.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    (row.project_name || '—');
}
var __VLS_116;
const __VLS_117 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_118 = __VLS_asFunctionalComponent(__VLS_117, new __VLS_117({
    label: "有效期",
    width: "180",
}));
const __VLS_119 = __VLS_118({
    label: "有效期",
    width: "180",
}, ...__VLS_functionalComponentArgsRest(__VLS_118));
__VLS_120.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_120.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "tf-muted" },
        ...{ style: {} },
    });
    (__VLS_ctx.fmtDate(row.effective_date));
    (__VLS_ctx.fmtDate(row.expire_date));
}
var __VLS_120;
const __VLS_121 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_122 = __VLS_asFunctionalComponent(__VLS_121, new __VLS_121({
    label: "治理状态",
    width: "105",
}));
const __VLS_123 = __VLS_122({
    label: "治理状态",
    width: "105",
}, ...__VLS_functionalComponentArgsRest(__VLS_122));
__VLS_124.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_124.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_125 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_126 = __VLS_asFunctionalComponent(__VLS_125, new __VLS_125({
        type: (__VLS_ctx.govMap[row.governance_status]?.type || 'info'),
        size: "small",
        effect: "light",
    }));
    const __VLS_127 = __VLS_126({
        type: (__VLS_ctx.govMap[row.governance_status]?.type || 'info'),
        size: "small",
        effect: "light",
    }, ...__VLS_functionalComponentArgsRest(__VLS_126));
    __VLS_128.slots.default;
    (__VLS_ctx.govMap[row.governance_status]?.label || row.governance_status);
    var __VLS_128;
}
var __VLS_124;
const __VLS_129 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_130 = __VLS_asFunctionalComponent(__VLS_129, new __VLS_129({
    label: "处理状态",
    width: "100",
}));
const __VLS_131 = __VLS_130({
    label: "处理状态",
    width: "100",
}, ...__VLS_functionalComponentArgsRest(__VLS_130));
__VLS_132.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_132.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (row.error_msg) {
        const __VLS_133 = {}.ElTooltip;
        /** @type {[typeof __VLS_components.ElTooltip, typeof __VLS_components.elTooltip, typeof __VLS_components.ElTooltip, typeof __VLS_components.elTooltip, ]} */ ;
        // @ts-ignore
        const __VLS_134 = __VLS_asFunctionalComponent(__VLS_133, new __VLS_133({
            content: (row.error_msg),
        }));
        const __VLS_135 = __VLS_134({
            content: (row.error_msg),
        }, ...__VLS_functionalComponentArgsRest(__VLS_134));
        __VLS_136.slots.default;
        const __VLS_137 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_138 = __VLS_asFunctionalComponent(__VLS_137, new __VLS_137({
            type: "danger",
            size: "small",
        }));
        const __VLS_139 = __VLS_138({
            type: "danger",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_138));
        __VLS_140.slots.default;
        var __VLS_140;
        var __VLS_136;
    }
    else {
        const __VLS_141 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_142 = __VLS_asFunctionalComponent(__VLS_141, new __VLS_141({
            type: (__VLS_ctx.statusMap[row.status]?.type || 'info'),
            size: "small",
            effect: "plain",
        }));
        const __VLS_143 = __VLS_142({
            type: (__VLS_ctx.statusMap[row.status]?.type || 'info'),
            size: "small",
            effect: "plain",
        }, ...__VLS_functionalComponentArgsRest(__VLS_142));
        __VLS_144.slots.default;
        (__VLS_ctx.statusMap[row.status]?.label || row.status);
        var __VLS_144;
    }
}
var __VLS_132;
const __VLS_145 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_146 = __VLS_asFunctionalComponent(__VLS_145, new __VLS_145({
    label: "操作",
    width: "220",
    fixed: "right",
}));
const __VLS_147 = __VLS_146({
    label: "操作",
    width: "220",
    fixed: "right",
}, ...__VLS_functionalComponentArgsRest(__VLS_146));
__VLS_148.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_148.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_149 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_150 = __VLS_asFunctionalComponent(__VLS_149, new __VLS_149({
        ...{ 'onClick': {} },
        link: true,
        type: "primary",
    }));
    const __VLS_151 = __VLS_150({
        ...{ 'onClick': {} },
        link: true,
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_150));
    let __VLS_153;
    let __VLS_154;
    let __VLS_155;
    const __VLS_156 = {
        onClick: (...[$event]) => {
            __VLS_ctx.openChunks(row);
        }
    };
    __VLS_152.slots.default;
    var __VLS_152;
    const __VLS_157 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_158 = __VLS_asFunctionalComponent(__VLS_157, new __VLS_157({
        ...{ 'onClick': {} },
        link: true,
        type: "primary",
    }));
    const __VLS_159 = __VLS_158({
        ...{ 'onClick': {} },
        link: true,
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_158));
    let __VLS_161;
    let __VLS_162;
    let __VLS_163;
    const __VLS_164 = {
        onClick: (...[$event]) => {
            __VLS_ctx.openEdit(row);
        }
    };
    __VLS_160.slots.default;
    var __VLS_160;
    const __VLS_165 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_166 = __VLS_asFunctionalComponent(__VLS_165, new __VLS_165({
        ...{ 'onClick': {} },
        link: true,
        type: "warning",
    }));
    const __VLS_167 = __VLS_166({
        ...{ 'onClick': {} },
        link: true,
        type: "warning",
    }, ...__VLS_functionalComponentArgsRest(__VLS_166));
    let __VLS_169;
    let __VLS_170;
    let __VLS_171;
    const __VLS_172 = {
        onClick: (...[$event]) => {
            __VLS_ctx.reindex(row);
        }
    };
    __VLS_168.slots.default;
    var __VLS_168;
    const __VLS_173 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_174 = __VLS_asFunctionalComponent(__VLS_173, new __VLS_173({
        ...{ 'onClick': {} },
        link: true,
        type: "danger",
    }));
    const __VLS_175 = __VLS_174({
        ...{ 'onClick': {} },
        link: true,
        type: "danger",
    }, ...__VLS_functionalComponentArgsRest(__VLS_174));
    let __VLS_177;
    let __VLS_178;
    let __VLS_179;
    const __VLS_180 = {
        onClick: (...[$event]) => {
            __VLS_ctx.remove(row);
        }
    };
    __VLS_176.slots.default;
    var __VLS_176;
}
var __VLS_148;
{
    const { empty: __VLS_thisSlot } = __VLS_104.slots;
    const __VLS_181 = {}.ElEmpty;
    /** @type {[typeof __VLS_components.ElEmpty, typeof __VLS_components.elEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_182 = __VLS_asFunctionalComponent(__VLS_181, new __VLS_181({
        description: "暂无文档，请上传规范 / 案例 / 企业资料",
    }));
    const __VLS_183 = __VLS_182({
        description: "暂无文档，请上传规范 / 案例 / 企业资料",
    }, ...__VLS_functionalComponentArgsRest(__VLS_182));
}
var __VLS_104;
const __VLS_185 = {}.ElPagination;
/** @type {[typeof __VLS_components.ElPagination, typeof __VLS_components.elPagination, ]} */ ;
// @ts-ignore
const __VLS_186 = __VLS_asFunctionalComponent(__VLS_185, new __VLS_185({
    ...{ 'onCurrentChange': {} },
    ...{ 'onSizeChange': {} },
    currentPage: (__VLS_ctx.query.page),
    pageSize: (__VLS_ctx.query.page_size),
    total: (__VLS_ctx.total),
    pageSizes: ([10, 20, 50, 100]),
    layout: "total, sizes, prev, pager, next, jumper",
    ...{ style: {} },
}));
const __VLS_187 = __VLS_186({
    ...{ 'onCurrentChange': {} },
    ...{ 'onSizeChange': {} },
    currentPage: (__VLS_ctx.query.page),
    pageSize: (__VLS_ctx.query.page_size),
    total: (__VLS_ctx.total),
    pageSizes: ([10, 20, 50, 100]),
    layout: "total, sizes, prev, pager, next, jumper",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_186));
let __VLS_189;
let __VLS_190;
let __VLS_191;
const __VLS_192 = {
    onCurrentChange: (__VLS_ctx.load)
};
const __VLS_193 = {
    onSizeChange: (__VLS_ctx.load)
};
var __VLS_188;
const __VLS_194 = {}.ElDialog;
/** @type {[typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, ]} */ ;
// @ts-ignore
const __VLS_195 = __VLS_asFunctionalComponent(__VLS_194, new __VLS_194({
    modelValue: (__VLS_ctx.uploadVisible),
    title: "上传工程资料",
    width: "640px",
}));
const __VLS_196 = __VLS_195({
    modelValue: (__VLS_ctx.uploadVisible),
    title: "上传工程资料",
    width: "640px",
}, ...__VLS_functionalComponentArgsRest(__VLS_195));
__VLS_197.slots.default;
const __VLS_198 = {}.ElAlert;
/** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
// @ts-ignore
const __VLS_199 = __VLS_asFunctionalComponent(__VLS_198, new __VLS_198({
    type: "info",
    closable: (false),
    showIcon: true,
    title: "支持 PDF / Word / Excel / Markdown / TXT。系统将按章节-条文结构切片，保留表格块并识别强制性条文。",
    ...{ style: {} },
}));
const __VLS_200 = __VLS_199({
    type: "info",
    closable: (false),
    showIcon: true,
    title: "支持 PDF / Word / Excel / Markdown / TXT。系统将按章节-条文结构切片，保留表格块并识别强制性条文。",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_199));
const __VLS_202 = {}.ElForm;
/** @type {[typeof __VLS_components.ElForm, typeof __VLS_components.elForm, typeof __VLS_components.ElForm, typeof __VLS_components.elForm, ]} */ ;
// @ts-ignore
const __VLS_203 = __VLS_asFunctionalComponent(__VLS_202, new __VLS_202({
    model: (__VLS_ctx.uploadForm),
    labelWidth: "96px",
}));
const __VLS_204 = __VLS_203({
    model: (__VLS_ctx.uploadForm),
    labelWidth: "96px",
}, ...__VLS_functionalComponentArgsRest(__VLS_203));
__VLS_205.slots.default;
const __VLS_206 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_207 = __VLS_asFunctionalComponent(__VLS_206, new __VLS_206({
    label: "目标知识库",
    required: true,
}));
const __VLS_208 = __VLS_207({
    label: "目标知识库",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_207));
__VLS_209.slots.default;
const __VLS_210 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_211 = __VLS_asFunctionalComponent(__VLS_210, new __VLS_210({
    modelValue: (__VLS_ctx.uploadForm.kb_id),
    ...{ style: {} },
}));
const __VLS_212 = __VLS_211({
    modelValue: (__VLS_ctx.uploadForm.kb_id),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_211));
__VLS_213.slots.default;
for (const [k] of __VLS_getVForSourceType((__VLS_ctx.kbs))) {
    const __VLS_214 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_215 = __VLS_asFunctionalComponent(__VLS_214, new __VLS_214({
        key: (k.id),
        label: (`${k.name}（${k.domain_label}）`),
        value: (k.id),
    }));
    const __VLS_216 = __VLS_215({
        key: (k.id),
        label: (`${k.name}（${k.domain_label}）`),
        value: (k.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_215));
}
var __VLS_213;
var __VLS_209;
const __VLS_218 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_219 = __VLS_asFunctionalComponent(__VLS_218, new __VLS_218({
    label: "文件",
}));
const __VLS_220 = __VLS_219({
    label: "文件",
}, ...__VLS_functionalComponentArgsRest(__VLS_219));
__VLS_221.slots.default;
const __VLS_222 = {}.ElUpload;
/** @type {[typeof __VLS_components.ElUpload, typeof __VLS_components.elUpload, typeof __VLS_components.ElUpload, typeof __VLS_components.elUpload, ]} */ ;
// @ts-ignore
const __VLS_223 = __VLS_asFunctionalComponent(__VLS_222, new __VLS_222({
    fileList: (__VLS_ctx.fileList),
    drag: true,
    multiple: true,
    autoUpload: (false),
    accept: ".pdf,.doc,.docx,.xls,.xlsx,.md,.txt",
    ...{ style: {} },
}));
const __VLS_224 = __VLS_223({
    fileList: (__VLS_ctx.fileList),
    drag: true,
    multiple: true,
    autoUpload: (false),
    accept: ".pdf,.doc,.docx,.xls,.xlsx,.md,.txt",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_223));
__VLS_225.slots.default;
const __VLS_226 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_227 = __VLS_asFunctionalComponent(__VLS_226, new __VLS_226({
    ...{ class: "el-icon--upload" },
}));
const __VLS_228 = __VLS_227({
    ...{ class: "el-icon--upload" },
}, ...__VLS_functionalComponentArgsRest(__VLS_227));
__VLS_229.slots.default;
const __VLS_230 = {}.UploadFilled;
/** @type {[typeof __VLS_components.UploadFilled, ]} */ ;
// @ts-ignore
const __VLS_231 = __VLS_asFunctionalComponent(__VLS_230, new __VLS_230({}));
const __VLS_232 = __VLS_231({}, ...__VLS_functionalComponentArgsRest(__VLS_231));
var __VLS_229;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "el-upload__text" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.em, __VLS_intrinsicElements.em)({});
var __VLS_225;
var __VLS_221;
const __VLS_234 = {}.ElRow;
/** @type {[typeof __VLS_components.ElRow, typeof __VLS_components.elRow, typeof __VLS_components.ElRow, typeof __VLS_components.elRow, ]} */ ;
// @ts-ignore
const __VLS_235 = __VLS_asFunctionalComponent(__VLS_234, new __VLS_234({
    gutter: (12),
}));
const __VLS_236 = __VLS_235({
    gutter: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_235));
__VLS_237.slots.default;
const __VLS_238 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_239 = __VLS_asFunctionalComponent(__VLS_238, new __VLS_238({
    span: (12),
}));
const __VLS_240 = __VLS_239({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_239));
__VLS_241.slots.default;
const __VLS_242 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_243 = __VLS_asFunctionalComponent(__VLS_242, new __VLS_242({
    label: "标准编号",
}));
const __VLS_244 = __VLS_243({
    label: "标准编号",
}, ...__VLS_functionalComponentArgsRest(__VLS_243));
__VLS_245.slots.default;
const __VLS_246 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_247 = __VLS_asFunctionalComponent(__VLS_246, new __VLS_246({
    modelValue: (__VLS_ctx.uploadForm.standard_code),
    placeholder: "如 GB50204-2015",
}));
const __VLS_248 = __VLS_247({
    modelValue: (__VLS_ctx.uploadForm.standard_code),
    placeholder: "如 GB50204-2015",
}, ...__VLS_functionalComponentArgsRest(__VLS_247));
var __VLS_245;
var __VLS_241;
const __VLS_250 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_251 = __VLS_asFunctionalComponent(__VLS_250, new __VLS_250({
    span: (12),
}));
const __VLS_252 = __VLS_251({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_251));
__VLS_253.slots.default;
const __VLS_254 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_255 = __VLS_asFunctionalComponent(__VLS_254, new __VLS_254({
    label: "标准名称",
}));
const __VLS_256 = __VLS_255({
    label: "标准名称",
}, ...__VLS_functionalComponentArgsRest(__VLS_255));
__VLS_257.slots.default;
const __VLS_258 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_259 = __VLS_asFunctionalComponent(__VLS_258, new __VLS_258({
    modelValue: (__VLS_ctx.uploadForm.standard_name),
}));
const __VLS_260 = __VLS_259({
    modelValue: (__VLS_ctx.uploadForm.standard_name),
}, ...__VLS_functionalComponentArgsRest(__VLS_259));
var __VLS_257;
var __VLS_253;
const __VLS_262 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_263 = __VLS_asFunctionalComponent(__VLS_262, new __VLS_262({
    span: (12),
}));
const __VLS_264 = __VLS_263({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_263));
__VLS_265.slots.default;
const __VLS_266 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_267 = __VLS_asFunctionalComponent(__VLS_266, new __VLS_266({
    label: "专业",
}));
const __VLS_268 = __VLS_267({
    label: "专业",
}, ...__VLS_functionalComponentArgsRest(__VLS_267));
__VLS_269.slots.default;
const __VLS_270 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_271 = __VLS_asFunctionalComponent(__VLS_270, new __VLS_270({
    modelValue: (__VLS_ctx.uploadForm.discipline),
    ...{ style: {} },
}));
const __VLS_272 = __VLS_271({
    modelValue: (__VLS_ctx.uploadForm.discipline),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_271));
__VLS_273.slots.default;
for (const [d] of __VLS_getVForSourceType((__VLS_ctx.disciplineOptions))) {
    const __VLS_274 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_275 = __VLS_asFunctionalComponent(__VLS_274, new __VLS_274({
        key: (d.value),
        label: (d.label),
        value: (d.value),
    }));
    const __VLS_276 = __VLS_275({
        key: (d.value),
        label: (d.label),
        value: (d.value),
    }, ...__VLS_functionalComponentArgsRest(__VLS_275));
}
var __VLS_273;
var __VLS_269;
var __VLS_265;
const __VLS_278 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_279 = __VLS_asFunctionalComponent(__VLS_278, new __VLS_278({
    span: (12),
}));
const __VLS_280 = __VLS_279({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_279));
__VLS_281.slots.default;
const __VLS_282 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_283 = __VLS_asFunctionalComponent(__VLS_282, new __VLS_282({
    label: "所属项目",
}));
const __VLS_284 = __VLS_283({
    label: "所属项目",
}, ...__VLS_functionalComponentArgsRest(__VLS_283));
__VLS_285.slots.default;
const __VLS_286 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_287 = __VLS_asFunctionalComponent(__VLS_286, new __VLS_286({
    modelValue: (__VLS_ctx.uploadForm.project_name),
}));
const __VLS_288 = __VLS_287({
    modelValue: (__VLS_ctx.uploadForm.project_name),
}, ...__VLS_functionalComponentArgsRest(__VLS_287));
var __VLS_285;
var __VLS_281;
const __VLS_290 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_291 = __VLS_asFunctionalComponent(__VLS_290, new __VLS_290({
    span: (12),
}));
const __VLS_292 = __VLS_291({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_291));
__VLS_293.slots.default;
const __VLS_294 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_295 = __VLS_asFunctionalComponent(__VLS_294, new __VLS_294({
    label: "生效日期",
}));
const __VLS_296 = __VLS_295({
    label: "生效日期",
}, ...__VLS_functionalComponentArgsRest(__VLS_295));
__VLS_297.slots.default;
const __VLS_298 = {}.ElDatePicker;
/** @type {[typeof __VLS_components.ElDatePicker, typeof __VLS_components.elDatePicker, ]} */ ;
// @ts-ignore
const __VLS_299 = __VLS_asFunctionalComponent(__VLS_298, new __VLS_298({
    modelValue: (__VLS_ctx.uploadForm.effective_date),
    type: "date",
    valueFormat: "YYYY-MM-DDTHH:mm:ss",
    ...{ style: {} },
}));
const __VLS_300 = __VLS_299({
    modelValue: (__VLS_ctx.uploadForm.effective_date),
    type: "date",
    valueFormat: "YYYY-MM-DDTHH:mm:ss",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_299));
var __VLS_297;
var __VLS_293;
const __VLS_302 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_303 = __VLS_asFunctionalComponent(__VLS_302, new __VLS_302({
    span: (12),
}));
const __VLS_304 = __VLS_303({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_303));
__VLS_305.slots.default;
const __VLS_306 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_307 = __VLS_asFunctionalComponent(__VLS_306, new __VLS_306({
    label: "失效日期",
}));
const __VLS_308 = __VLS_307({
    label: "失效日期",
}, ...__VLS_functionalComponentArgsRest(__VLS_307));
__VLS_309.slots.default;
const __VLS_310 = {}.ElDatePicker;
/** @type {[typeof __VLS_components.ElDatePicker, typeof __VLS_components.elDatePicker, ]} */ ;
// @ts-ignore
const __VLS_311 = __VLS_asFunctionalComponent(__VLS_310, new __VLS_310({
    modelValue: (__VLS_ctx.uploadForm.expire_date),
    type: "date",
    valueFormat: "YYYY-MM-DDTHH:mm:ss",
    ...{ style: {} },
}));
const __VLS_312 = __VLS_311({
    modelValue: (__VLS_ctx.uploadForm.expire_date),
    type: "date",
    valueFormat: "YYYY-MM-DDTHH:mm:ss",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_311));
var __VLS_309;
var __VLS_305;
const __VLS_314 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_315 = __VLS_asFunctionalComponent(__VLS_314, new __VLS_314({
    span: (12),
}));
const __VLS_316 = __VLS_315({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_315));
__VLS_317.slots.default;
const __VLS_318 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_319 = __VLS_asFunctionalComponent(__VLS_318, new __VLS_318({
    label: "责任人",
}));
const __VLS_320 = __VLS_319({
    label: "责任人",
}, ...__VLS_functionalComponentArgsRest(__VLS_319));
__VLS_321.slots.default;
const __VLS_322 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_323 = __VLS_asFunctionalComponent(__VLS_322, new __VLS_322({
    modelValue: (__VLS_ctx.uploadForm.owner),
}));
const __VLS_324 = __VLS_323({
    modelValue: (__VLS_ctx.uploadForm.owner),
}, ...__VLS_functionalComponentArgsRest(__VLS_323));
var __VLS_321;
var __VLS_317;
const __VLS_326 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_327 = __VLS_asFunctionalComponent(__VLS_326, new __VLS_326({
    span: (12),
}));
const __VLS_328 = __VLS_327({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_327));
__VLS_329.slots.default;
const __VLS_330 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_331 = __VLS_asFunctionalComponent(__VLS_330, new __VLS_330({
    label: "版本",
}));
const __VLS_332 = __VLS_331({
    label: "版本",
}, ...__VLS_functionalComponentArgsRest(__VLS_331));
__VLS_333.slots.default;
const __VLS_334 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_335 = __VLS_asFunctionalComponent(__VLS_334, new __VLS_334({
    modelValue: (__VLS_ctx.uploadForm.version),
}));
const __VLS_336 = __VLS_335({
    modelValue: (__VLS_ctx.uploadForm.version),
}, ...__VLS_functionalComponentArgsRest(__VLS_335));
var __VLS_333;
var __VLS_329;
var __VLS_237;
var __VLS_205;
{
    const { footer: __VLS_thisSlot } = __VLS_197.slots;
    const __VLS_338 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_339 = __VLS_asFunctionalComponent(__VLS_338, new __VLS_338({
        ...{ 'onClick': {} },
    }));
    const __VLS_340 = __VLS_339({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_339));
    let __VLS_342;
    let __VLS_343;
    let __VLS_344;
    const __VLS_345 = {
        onClick: (...[$event]) => {
            __VLS_ctx.uploadVisible = false;
        }
    };
    __VLS_341.slots.default;
    var __VLS_341;
    const __VLS_346 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_347 = __VLS_asFunctionalComponent(__VLS_346, new __VLS_346({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.uploading),
    }));
    const __VLS_348 = __VLS_347({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.uploading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_347));
    let __VLS_350;
    let __VLS_351;
    let __VLS_352;
    const __VLS_353 = {
        onClick: (__VLS_ctx.submitUpload)
    };
    __VLS_349.slots.default;
    var __VLS_349;
}
var __VLS_197;
const __VLS_354 = {}.ElDialog;
/** @type {[typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, ]} */ ;
// @ts-ignore
const __VLS_355 = __VLS_asFunctionalComponent(__VLS_354, new __VLS_354({
    modelValue: (__VLS_ctx.textVisible),
    title: "文本直接入库（会议纪要 / FAQ / 复盘）",
    width: "640px",
}));
const __VLS_356 = __VLS_355({
    modelValue: (__VLS_ctx.textVisible),
    title: "文本直接入库（会议纪要 / FAQ / 复盘）",
    width: "640px",
}, ...__VLS_functionalComponentArgsRest(__VLS_355));
__VLS_357.slots.default;
const __VLS_358 = {}.ElForm;
/** @type {[typeof __VLS_components.ElForm, typeof __VLS_components.elForm, typeof __VLS_components.ElForm, typeof __VLS_components.elForm, ]} */ ;
// @ts-ignore
const __VLS_359 = __VLS_asFunctionalComponent(__VLS_358, new __VLS_358({
    model: (__VLS_ctx.textForm),
    labelWidth: "90px",
}));
const __VLS_360 = __VLS_359({
    model: (__VLS_ctx.textForm),
    labelWidth: "90px",
}, ...__VLS_functionalComponentArgsRest(__VLS_359));
__VLS_361.slots.default;
const __VLS_362 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_363 = __VLS_asFunctionalComponent(__VLS_362, new __VLS_362({
    label: "知识库",
    required: true,
}));
const __VLS_364 = __VLS_363({
    label: "知识库",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_363));
__VLS_365.slots.default;
const __VLS_366 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_367 = __VLS_asFunctionalComponent(__VLS_366, new __VLS_366({
    modelValue: (__VLS_ctx.textForm.kb_id),
    ...{ style: {} },
}));
const __VLS_368 = __VLS_367({
    modelValue: (__VLS_ctx.textForm.kb_id),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_367));
__VLS_369.slots.default;
for (const [k] of __VLS_getVForSourceType((__VLS_ctx.kbs))) {
    const __VLS_370 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_371 = __VLS_asFunctionalComponent(__VLS_370, new __VLS_370({
        key: (k.id),
        label: (k.name),
        value: (k.id),
    }));
    const __VLS_372 = __VLS_371({
        key: (k.id),
        label: (k.name),
        value: (k.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_371));
}
var __VLS_369;
var __VLS_365;
const __VLS_374 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_375 = __VLS_asFunctionalComponent(__VLS_374, new __VLS_374({
    label: "标题",
    required: true,
}));
const __VLS_376 = __VLS_375({
    label: "标题",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_375));
__VLS_377.slots.default;
const __VLS_378 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_379 = __VLS_asFunctionalComponent(__VLS_378, new __VLS_378({
    modelValue: (__VLS_ctx.textForm.title),
}));
const __VLS_380 = __VLS_379({
    modelValue: (__VLS_ctx.textForm.title),
}, ...__VLS_functionalComponentArgsRest(__VLS_379));
var __VLS_377;
const __VLS_382 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_383 = __VLS_asFunctionalComponent(__VLS_382, new __VLS_382({
    label: "专业",
}));
const __VLS_384 = __VLS_383({
    label: "专业",
}, ...__VLS_functionalComponentArgsRest(__VLS_383));
__VLS_385.slots.default;
const __VLS_386 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_387 = __VLS_asFunctionalComponent(__VLS_386, new __VLS_386({
    modelValue: (__VLS_ctx.textForm.discipline),
    ...{ style: {} },
}));
const __VLS_388 = __VLS_387({
    modelValue: (__VLS_ctx.textForm.discipline),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_387));
__VLS_389.slots.default;
for (const [d] of __VLS_getVForSourceType((__VLS_ctx.disciplineOptions))) {
    const __VLS_390 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_391 = __VLS_asFunctionalComponent(__VLS_390, new __VLS_390({
        key: (d.value),
        label: (d.label),
        value: (d.value),
    }));
    const __VLS_392 = __VLS_391({
        key: (d.value),
        label: (d.label),
        value: (d.value),
    }, ...__VLS_functionalComponentArgsRest(__VLS_391));
}
var __VLS_389;
var __VLS_385;
const __VLS_394 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_395 = __VLS_asFunctionalComponent(__VLS_394, new __VLS_394({
    label: "正文",
    required: true,
}));
const __VLS_396 = __VLS_395({
    label: "正文",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_395));
__VLS_397.slots.default;
const __VLS_398 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_399 = __VLS_asFunctionalComponent(__VLS_398, new __VLS_398({
    modelValue: (__VLS_ctx.textForm.content),
    type: "textarea",
    rows: (10),
    placeholder: "支持 Markdown 标题结构，系统会据此建立章节路径",
}));
const __VLS_400 = __VLS_399({
    modelValue: (__VLS_ctx.textForm.content),
    type: "textarea",
    rows: (10),
    placeholder: "支持 Markdown 标题结构，系统会据此建立章节路径",
}, ...__VLS_functionalComponentArgsRest(__VLS_399));
var __VLS_397;
var __VLS_361;
{
    const { footer: __VLS_thisSlot } = __VLS_357.slots;
    const __VLS_402 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_403 = __VLS_asFunctionalComponent(__VLS_402, new __VLS_402({
        ...{ 'onClick': {} },
    }));
    const __VLS_404 = __VLS_403({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_403));
    let __VLS_406;
    let __VLS_407;
    let __VLS_408;
    const __VLS_409 = {
        onClick: (...[$event]) => {
            __VLS_ctx.textVisible = false;
        }
    };
    __VLS_405.slots.default;
    var __VLS_405;
    const __VLS_410 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_411 = __VLS_asFunctionalComponent(__VLS_410, new __VLS_410({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.textSubmitting),
    }));
    const __VLS_412 = __VLS_411({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.textSubmitting),
    }, ...__VLS_functionalComponentArgsRest(__VLS_411));
    let __VLS_414;
    let __VLS_415;
    let __VLS_416;
    const __VLS_417 = {
        onClick: (__VLS_ctx.submitText)
    };
    __VLS_413.slots.default;
    var __VLS_413;
}
var __VLS_357;
const __VLS_418 = {}.ElDialog;
/** @type {[typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, ]} */ ;
// @ts-ignore
const __VLS_419 = __VLS_asFunctionalComponent(__VLS_418, new __VLS_418({
    modelValue: (__VLS_ctx.editVisible),
    title: "编辑文档元数据",
    width: "600px",
}));
const __VLS_420 = __VLS_419({
    modelValue: (__VLS_ctx.editVisible),
    title: "编辑文档元数据",
    width: "600px",
}, ...__VLS_functionalComponentArgsRest(__VLS_419));
__VLS_421.slots.default;
const __VLS_422 = {}.ElForm;
/** @type {[typeof __VLS_components.ElForm, typeof __VLS_components.elForm, typeof __VLS_components.ElForm, typeof __VLS_components.elForm, ]} */ ;
// @ts-ignore
const __VLS_423 = __VLS_asFunctionalComponent(__VLS_422, new __VLS_422({
    model: (__VLS_ctx.editForm),
    labelWidth: "96px",
}));
const __VLS_424 = __VLS_423({
    model: (__VLS_ctx.editForm),
    labelWidth: "96px",
}, ...__VLS_functionalComponentArgsRest(__VLS_423));
__VLS_425.slots.default;
const __VLS_426 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_427 = __VLS_asFunctionalComponent(__VLS_426, new __VLS_426({
    label: "标题",
}));
const __VLS_428 = __VLS_427({
    label: "标题",
}, ...__VLS_functionalComponentArgsRest(__VLS_427));
__VLS_429.slots.default;
const __VLS_430 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_431 = __VLS_asFunctionalComponent(__VLS_430, new __VLS_430({
    modelValue: (__VLS_ctx.editForm.title),
}));
const __VLS_432 = __VLS_431({
    modelValue: (__VLS_ctx.editForm.title),
}, ...__VLS_functionalComponentArgsRest(__VLS_431));
var __VLS_429;
const __VLS_434 = {}.ElRow;
/** @type {[typeof __VLS_components.ElRow, typeof __VLS_components.elRow, typeof __VLS_components.ElRow, typeof __VLS_components.elRow, ]} */ ;
// @ts-ignore
const __VLS_435 = __VLS_asFunctionalComponent(__VLS_434, new __VLS_434({
    gutter: (12),
}));
const __VLS_436 = __VLS_435({
    gutter: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_435));
__VLS_437.slots.default;
const __VLS_438 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_439 = __VLS_asFunctionalComponent(__VLS_438, new __VLS_438({
    span: (12),
}));
const __VLS_440 = __VLS_439({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_439));
__VLS_441.slots.default;
const __VLS_442 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_443 = __VLS_asFunctionalComponent(__VLS_442, new __VLS_442({
    label: "标准编号",
}));
const __VLS_444 = __VLS_443({
    label: "标准编号",
}, ...__VLS_functionalComponentArgsRest(__VLS_443));
__VLS_445.slots.default;
const __VLS_446 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_447 = __VLS_asFunctionalComponent(__VLS_446, new __VLS_446({
    modelValue: (__VLS_ctx.editForm.standard_code),
}));
const __VLS_448 = __VLS_447({
    modelValue: (__VLS_ctx.editForm.standard_code),
}, ...__VLS_functionalComponentArgsRest(__VLS_447));
var __VLS_445;
var __VLS_441;
const __VLS_450 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_451 = __VLS_asFunctionalComponent(__VLS_450, new __VLS_450({
    span: (12),
}));
const __VLS_452 = __VLS_451({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_451));
__VLS_453.slots.default;
const __VLS_454 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_455 = __VLS_asFunctionalComponent(__VLS_454, new __VLS_454({
    label: "标准名称",
}));
const __VLS_456 = __VLS_455({
    label: "标准名称",
}, ...__VLS_functionalComponentArgsRest(__VLS_455));
__VLS_457.slots.default;
const __VLS_458 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_459 = __VLS_asFunctionalComponent(__VLS_458, new __VLS_458({
    modelValue: (__VLS_ctx.editForm.standard_name),
}));
const __VLS_460 = __VLS_459({
    modelValue: (__VLS_ctx.editForm.standard_name),
}, ...__VLS_functionalComponentArgsRest(__VLS_459));
var __VLS_457;
var __VLS_453;
const __VLS_462 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_463 = __VLS_asFunctionalComponent(__VLS_462, new __VLS_462({
    span: (12),
}));
const __VLS_464 = __VLS_463({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_463));
__VLS_465.slots.default;
const __VLS_466 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_467 = __VLS_asFunctionalComponent(__VLS_466, new __VLS_466({
    label: "专业",
}));
const __VLS_468 = __VLS_467({
    label: "专业",
}, ...__VLS_functionalComponentArgsRest(__VLS_467));
__VLS_469.slots.default;
const __VLS_470 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_471 = __VLS_asFunctionalComponent(__VLS_470, new __VLS_470({
    modelValue: (__VLS_ctx.editForm.discipline),
    ...{ style: {} },
}));
const __VLS_472 = __VLS_471({
    modelValue: (__VLS_ctx.editForm.discipline),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_471));
__VLS_473.slots.default;
for (const [d] of __VLS_getVForSourceType((__VLS_ctx.disciplineOptions))) {
    const __VLS_474 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_475 = __VLS_asFunctionalComponent(__VLS_474, new __VLS_474({
        key: (d.value),
        label: (d.label),
        value: (d.value),
    }));
    const __VLS_476 = __VLS_475({
        key: (d.value),
        label: (d.label),
        value: (d.value),
    }, ...__VLS_functionalComponentArgsRest(__VLS_475));
}
var __VLS_473;
var __VLS_469;
var __VLS_465;
const __VLS_478 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_479 = __VLS_asFunctionalComponent(__VLS_478, new __VLS_478({
    span: (12),
}));
const __VLS_480 = __VLS_479({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_479));
__VLS_481.slots.default;
const __VLS_482 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_483 = __VLS_asFunctionalComponent(__VLS_482, new __VLS_482({
    label: "治理状态",
}));
const __VLS_484 = __VLS_483({
    label: "治理状态",
}, ...__VLS_functionalComponentArgsRest(__VLS_483));
__VLS_485.slots.default;
const __VLS_486 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_487 = __VLS_asFunctionalComponent(__VLS_486, new __VLS_486({
    modelValue: (__VLS_ctx.editForm.governance_status),
    ...{ style: {} },
}));
const __VLS_488 = __VLS_487({
    modelValue: (__VLS_ctx.editForm.governance_status),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_487));
__VLS_489.slots.default;
for (const [v, k] of __VLS_getVForSourceType((__VLS_ctx.govMap))) {
    const __VLS_490 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_491 = __VLS_asFunctionalComponent(__VLS_490, new __VLS_490({
        key: (k),
        label: (v.label),
        value: (k),
    }));
    const __VLS_492 = __VLS_491({
        key: (k),
        label: (v.label),
        value: (k),
    }, ...__VLS_functionalComponentArgsRest(__VLS_491));
}
var __VLS_489;
var __VLS_485;
var __VLS_481;
const __VLS_494 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_495 = __VLS_asFunctionalComponent(__VLS_494, new __VLS_494({
    span: (12),
}));
const __VLS_496 = __VLS_495({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_495));
__VLS_497.slots.default;
const __VLS_498 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_499 = __VLS_asFunctionalComponent(__VLS_498, new __VLS_498({
    label: "所属项目",
}));
const __VLS_500 = __VLS_499({
    label: "所属项目",
}, ...__VLS_functionalComponentArgsRest(__VLS_499));
__VLS_501.slots.default;
const __VLS_502 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_503 = __VLS_asFunctionalComponent(__VLS_502, new __VLS_502({
    modelValue: (__VLS_ctx.editForm.project_name),
}));
const __VLS_504 = __VLS_503({
    modelValue: (__VLS_ctx.editForm.project_name),
}, ...__VLS_functionalComponentArgsRest(__VLS_503));
var __VLS_501;
var __VLS_497;
const __VLS_506 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_507 = __VLS_asFunctionalComponent(__VLS_506, new __VLS_506({
    span: (12),
}));
const __VLS_508 = __VLS_507({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_507));
__VLS_509.slots.default;
const __VLS_510 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_511 = __VLS_asFunctionalComponent(__VLS_510, new __VLS_510({
    label: "责任人",
}));
const __VLS_512 = __VLS_511({
    label: "责任人",
}, ...__VLS_functionalComponentArgsRest(__VLS_511));
__VLS_513.slots.default;
const __VLS_514 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_515 = __VLS_asFunctionalComponent(__VLS_514, new __VLS_514({
    modelValue: (__VLS_ctx.editForm.owner),
}));
const __VLS_516 = __VLS_515({
    modelValue: (__VLS_ctx.editForm.owner),
}, ...__VLS_functionalComponentArgsRest(__VLS_515));
var __VLS_513;
var __VLS_509;
var __VLS_437;
const __VLS_518 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_519 = __VLS_asFunctionalComponent(__VLS_518, new __VLS_518({
    label: "摘要",
}));
const __VLS_520 = __VLS_519({
    label: "摘要",
}, ...__VLS_functionalComponentArgsRest(__VLS_519));
__VLS_521.slots.default;
const __VLS_522 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_523 = __VLS_asFunctionalComponent(__VLS_522, new __VLS_522({
    modelValue: (__VLS_ctx.editForm.summary),
    type: "textarea",
    rows: (3),
}));
const __VLS_524 = __VLS_523({
    modelValue: (__VLS_ctx.editForm.summary),
    type: "textarea",
    rows: (3),
}, ...__VLS_functionalComponentArgsRest(__VLS_523));
var __VLS_521;
var __VLS_425;
{
    const { footer: __VLS_thisSlot } = __VLS_421.slots;
    const __VLS_526 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_527 = __VLS_asFunctionalComponent(__VLS_526, new __VLS_526({
        ...{ 'onClick': {} },
    }));
    const __VLS_528 = __VLS_527({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_527));
    let __VLS_530;
    let __VLS_531;
    let __VLS_532;
    const __VLS_533 = {
        onClick: (...[$event]) => {
            __VLS_ctx.editVisible = false;
        }
    };
    __VLS_529.slots.default;
    var __VLS_529;
    const __VLS_534 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_535 = __VLS_asFunctionalComponent(__VLS_534, new __VLS_534({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_536 = __VLS_535({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_535));
    let __VLS_538;
    let __VLS_539;
    let __VLS_540;
    const __VLS_541 = {
        onClick: (__VLS_ctx.submitEdit)
    };
    __VLS_537.slots.default;
    var __VLS_537;
}
var __VLS_421;
const __VLS_542 = {}.ElDrawer;
/** @type {[typeof __VLS_components.ElDrawer, typeof __VLS_components.elDrawer, typeof __VLS_components.ElDrawer, typeof __VLS_components.elDrawer, ]} */ ;
// @ts-ignore
const __VLS_543 = __VLS_asFunctionalComponent(__VLS_542, new __VLS_542({
    modelValue: (__VLS_ctx.chunkVisible),
    size: "640px",
    title: (`知识切片 · ${__VLS_ctx.chunkDoc?.title || ''}`),
}));
const __VLS_544 = __VLS_543({
    modelValue: (__VLS_ctx.chunkVisible),
    size: "640px",
    title: (`知识切片 · ${__VLS_ctx.chunkDoc?.title || ''}`),
}, ...__VLS_functionalComponentArgsRest(__VLS_543));
__VLS_545.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ style: {} },
});
const __VLS_546 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_547 = __VLS_asFunctionalComponent(__VLS_546, new __VLS_546({
    ...{ 'onKeyup': {} },
    ...{ 'onClear': {} },
    modelValue: (__VLS_ctx.chunkPage.keyword),
    placeholder: "在切片内搜索",
    clearable: true,
}));
const __VLS_548 = __VLS_547({
    ...{ 'onKeyup': {} },
    ...{ 'onClear': {} },
    modelValue: (__VLS_ctx.chunkPage.keyword),
    placeholder: "在切片内搜索",
    clearable: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_547));
let __VLS_550;
let __VLS_551;
let __VLS_552;
const __VLS_553 = {
    onKeyup: (() => { __VLS_ctx.chunkPage.page = 1; __VLS_ctx.loadChunks(); })
};
const __VLS_554 = {
    onClear: (__VLS_ctx.loadChunks)
};
var __VLS_549;
const __VLS_555 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_556 = __VLS_asFunctionalComponent(__VLS_555, new __VLS_555({
    ...{ 'onClick': {} },
}));
const __VLS_557 = __VLS_556({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_556));
let __VLS_559;
let __VLS_560;
let __VLS_561;
const __VLS_562 = {
    onClick: (() => { __VLS_ctx.chunkPage.page = 1; __VLS_ctx.loadChunks(); })
};
__VLS_558.slots.default;
var __VLS_558;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalDirective(__VLS_directives.vLoading)(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.chunkLoading) }, null, null);
for (const [c] of __VLS_getVForSourceType((__VLS_ctx.chunks))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (c.id),
        ...{ class: "chunk-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "head" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (c.seq);
    if (c.clause_no) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ style: {} },
        });
        (c.clause_no);
    }
    if (c.page_no) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ style: {} },
        });
        (c.page_no);
    }
    if (c.is_mandatory) {
        const __VLS_563 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_564 = __VLS_asFunctionalComponent(__VLS_563, new __VLS_563({
            type: "danger",
            size: "small",
            effect: "light",
            ...{ style: {} },
        }));
        const __VLS_565 = __VLS_564({
            type: "danger",
            size: "small",
            effect: "light",
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_564));
        __VLS_566.slots.default;
        var __VLS_566;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (c.char_count);
    if (c.section_path) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "tf-muted" },
            ...{ style: {} },
        });
        (c.section_path);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "content" },
    });
    (c.content);
}
if (!__VLS_ctx.chunks.length && !__VLS_ctx.chunkLoading) {
    const __VLS_567 = {}.ElEmpty;
    /** @type {[typeof __VLS_components.ElEmpty, typeof __VLS_components.elEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_568 = __VLS_asFunctionalComponent(__VLS_567, new __VLS_567({
        description: "暂无切片",
    }));
    const __VLS_569 = __VLS_568({
        description: "暂无切片",
    }, ...__VLS_functionalComponentArgsRest(__VLS_568));
}
const __VLS_571 = {}.ElPagination;
/** @type {[typeof __VLS_components.ElPagination, typeof __VLS_components.elPagination, ]} */ ;
// @ts-ignore
const __VLS_572 = __VLS_asFunctionalComponent(__VLS_571, new __VLS_571({
    ...{ 'onCurrentChange': {} },
    currentPage: (__VLS_ctx.chunkPage.page),
    pageSize: (__VLS_ctx.chunkPage.page_size),
    total: (__VLS_ctx.chunkTotal),
    layout: "total, prev, pager, next",
    ...{ style: {} },
}));
const __VLS_573 = __VLS_572({
    ...{ 'onCurrentChange': {} },
    currentPage: (__VLS_ctx.chunkPage.page),
    pageSize: (__VLS_ctx.chunkPage.page_size),
    total: (__VLS_ctx.chunkTotal),
    layout: "total, prev, pager, next",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_572));
let __VLS_575;
let __VLS_576;
let __VLS_577;
const __VLS_578 = {
    onCurrentChange: (__VLS_ctx.loadChunks)
};
var __VLS_574;
var __VLS_545;
/** @type {__VLS_StyleScopedClasses['tf-card']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['el-icon--upload']} */ ;
/** @type {__VLS_StyleScopedClasses['el-upload__text']} */ ;
/** @type {__VLS_StyleScopedClasses['chunk-card']} */ ;
/** @type {__VLS_StyleScopedClasses['head']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['content']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            kbs: kbs,
            list: list,
            total: total,
            loading: loading,
            query: query,
            statusMap: statusMap,
            govMap: govMap,
            disciplineOptions: disciplineOptions,
            load: load,
            uploadVisible: uploadVisible,
            uploading: uploading,
            fileList: fileList,
            uploadForm: uploadForm,
            openUpload: openUpload,
            submitUpload: submitUpload,
            textVisible: textVisible,
            textSubmitting: textSubmitting,
            textForm: textForm,
            openText: openText,
            submitText: submitText,
            editVisible: editVisible,
            editForm: editForm,
            openEdit: openEdit,
            submitEdit: submitEdit,
            chunkVisible: chunkVisible,
            chunks: chunks,
            chunkTotal: chunkTotal,
            chunkLoading: chunkLoading,
            chunkDoc: chunkDoc,
            chunkPage: chunkPage,
            openChunks: openChunks,
            loadChunks: loadChunks,
            reindex: reindex,
            remove: remove,
            fmtSize: fmtSize,
            fmtDate: fmtDate,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
