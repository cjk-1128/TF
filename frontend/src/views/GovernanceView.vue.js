/// <reference types="../../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { govApi, kbApi } from '@/api';
const tab = ref('health');
const kbs = ref([]);
const selectedKb = ref('');
/* ---------- 健康度 ---------- */
const report = ref(null);
const healthLoading = ref(false);
const issueTypeMap = {
    expired: '已过期',
    expiring_soon: '即将失效',
    no_owner: '缺少责任人',
    duplicate: '疑似重复',
    stale: '长期未更新',
    empty_summary: '缺少摘要',
    parse_failed: '解析失败',
    no_chunk: '无有效切片'
};
const severityMap = { high: 'danger', medium: 'warning', low: 'info' };
const scoreColor = computed(() => {
    const s = report.value?.score ?? 0;
    if (s >= 85)
        return '#2fa36b';
    if (s >= 70)
        return '#e6a23c';
    return '#f56c6c';
});
async function loadHealth() {
    healthLoading.value = true;
    try {
        const res = await govApi.healthReport(selectedKb.value || undefined);
        report.value = res.data;
    }
    finally {
        healthLoading.value = false;
    }
}
/* ---------- 治理事项 ---------- */
const tasks = ref([]);
const taskTotal = ref(0);
const taskLoading = ref(false);
const taskQuery = reactive({ kb_id: '', status: '', task_type: '', page: 1, page_size: 20 });
const taskTypeMap = {
    expire_check: '时效核查',
    duplicate_merge: '重复合并',
    gap_fill: '盲区补录',
    conflict_resolve: '冲突消解',
    quality_fix: '质量修复',
    owner_assign: '责任人指派'
};
const taskStatusMap = {
    open: { label: '待处理', type: 'warning' },
    in_progress: { label: '处理中', type: 'primary' },
    resolved: { label: '已完成', type: 'success' },
    ignored: { label: '已忽略', type: 'info' }
};
const priorityMap = {
    high: { label: '高', type: 'danger' },
    medium: { label: '中', type: 'warning' },
    low: { label: '低', type: 'info' }
};
async function loadTasks() {
    taskLoading.value = true;
    try {
        const res = await govApi.tasks({ ...taskQuery });
        tasks.value = res.data?.items || [];
        taskTotal.value = res.data?.total || 0;
    }
    finally {
        taskLoading.value = false;
    }
}
async function autoGenerate() {
    const res = await govApi.autoGenerate(selectedKb.value || undefined);
    ElMessage.success(`已自动生成 ${res.data?.length || 0} 条治理事项`);
    loadTasks();
}
async function changeStatus(row, status) {
    await govApi.updateTask(row.id, { status });
    ElMessage.success('已更新');
    loadTasks();
}
const taskDialog = ref(false);
const taskForm = reactive({
    task_type: 'gap_fill',
    title: '',
    description: '',
    kb_id: '',
    priority: 'medium',
    assignee: ''
});
function openTaskDialog(preset) {
    Object.assign(taskForm, {
        task_type: 'gap_fill',
        title: '',
        description: '',
        kb_id: selectedKb.value,
        priority: 'medium',
        assignee: ''
    }, preset || {});
    taskDialog.value = true;
}
async function submitTask() {
    if (!taskForm.title.trim())
        return ElMessage.warning('请填写事项标题');
    await govApi.createTask({ ...taskForm });
    ElMessage.success('已创建');
    taskDialog.value = false;
    loadTasks();
}
/* ---------- 知识盲区 ---------- */
const gaps = ref([]);
const gapDays = ref(30);
const gapLoading = ref(false);
async function loadGaps() {
    gapLoading.value = true;
    try {
        const res = await govApi.gaps(gapDays.value);
        gaps.value = res.data || [];
    }
    finally {
        gapLoading.value = false;
    }
}
function gapToTask(g) {
    openTaskDialog({
        task_type: 'gap_fill',
        title: `补录知识：${g.query}`,
        description: `近期该问题被提问 ${g.count} 次，平均置信度仅 ${(g.avg_confidence * 100).toFixed(0)}%。${g.suggestion}`,
        priority: g.count >= 3 ? 'high' : 'medium'
    });
}
/* ---------- 运营报告 ---------- */
const opReport = ref(null);
const opDays = ref(7);
const opLoading = ref(false);
async function loadOpReport() {
    opLoading.value = true;
    try {
        const res = await govApi.operationReport(opDays.value);
        opReport.value = res.data;
    }
    finally {
        opLoading.value = false;
    }
}
function onTabChange(name) {
    if (name === 'health' && !report.value)
        loadHealth();
    if (name === 'tasks')
        loadTasks();
    if (name === 'gaps' && !gaps.value.length)
        loadGaps();
    if (name === 'report' && !opReport.value)
        loadOpReport();
}
function fmtDate(s) {
    return s ? s.replace('T', ' ').slice(0, 16) : '—';
}
onMounted(async () => {
    const res = await kbApi.list();
    kbs.value = res.data || [];
    loadHealth();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tf-card" },
    ...{ style: {} },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ style: {} },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tf-section-title" },
    ...{ style: {} },
});
const __VLS_0 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.DataAnalysis;
/** @type {[typeof __VLS_components.DataAnalysis, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({}));
const __VLS_6 = __VLS_5({}, ...__VLS_functionalComponentArgsRest(__VLS_5));
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ style: {} },
});
const __VLS_8 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.selectedKb),
    placeholder: "全部知识库",
    clearable: true,
    ...{ style: {} },
}));
const __VLS_10 = __VLS_9({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.selectedKb),
    placeholder: "全部知识库",
    clearable: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
let __VLS_12;
let __VLS_13;
let __VLS_14;
const __VLS_15 = {
    onChange: (__VLS_ctx.loadHealth)
};
__VLS_11.slots.default;
for (const [k] of __VLS_getVForSourceType((__VLS_ctx.kbs))) {
    const __VLS_16 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        key: (k.id),
        label: (k.name),
        value: (k.id),
    }));
    const __VLS_18 = __VLS_17({
        key: (k.id),
        label: (k.name),
        value: (k.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
}
var __VLS_11;
const __VLS_20 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    ...{ 'onClick': {} },
    type: "primary",
    plain: true,
}));
const __VLS_22 = __VLS_21({
    ...{ 'onClick': {} },
    type: "primary",
    plain: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
let __VLS_24;
let __VLS_25;
let __VLS_26;
const __VLS_27 = {
    onClick: (__VLS_ctx.autoGenerate)
};
__VLS_23.slots.default;
const __VLS_28 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({}));
const __VLS_30 = __VLS_29({}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
const __VLS_32 = {}.MagicStick;
/** @type {[typeof __VLS_components.MagicStick, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({}));
const __VLS_34 = __VLS_33({}, ...__VLS_functionalComponentArgsRest(__VLS_33));
var __VLS_31;
var __VLS_23;
const __VLS_36 = {}.ElTabs;
/** @type {[typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    ...{ 'onTabChange': {} },
    modelValue: (__VLS_ctx.tab),
}));
const __VLS_38 = __VLS_37({
    ...{ 'onTabChange': {} },
    modelValue: (__VLS_ctx.tab),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
let __VLS_40;
let __VLS_41;
let __VLS_42;
const __VLS_43 = {
    onTabChange: (__VLS_ctx.onTabChange)
};
__VLS_39.slots.default;
const __VLS_44 = {}.ElTabPane;
/** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    label: "知识健康度",
    name: "health",
}));
const __VLS_46 = __VLS_45({
    label: "知识健康度",
    name: "health",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalDirective(__VLS_directives.vLoading)(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.healthLoading) }, null, null);
if (__VLS_ctx.report) {
    const __VLS_48 = {}.ElRow;
    /** @type {[typeof __VLS_components.ElRow, typeof __VLS_components.elRow, typeof __VLS_components.ElRow, typeof __VLS_components.elRow, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        gutter: (14),
        ...{ style: {} },
    }));
    const __VLS_50 = __VLS_49({
        gutter: (14),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    __VLS_51.slots.default;
    const __VLS_52 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        span: (6),
    }));
    const __VLS_54 = __VLS_53({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    __VLS_55.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    const __VLS_56 = {}.ElProgress;
    /** @type {[typeof __VLS_components.ElProgress, typeof __VLS_components.elProgress, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        type: "dashboard",
        percentage: (Math.round(__VLS_ctx.report.score)),
        color: (__VLS_ctx.scoreColor),
        width: (120),
        ...{ style: {} },
    }));
    const __VLS_58 = __VLS_57({
        type: "dashboard",
        percentage: (Math.round(__VLS_ctx.report.score)),
        color: (__VLS_ctx.scoreColor),
        width: (120),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tf-muted" },
        ...{ style: {} },
    });
    (__VLS_ctx.fmtDate(__VLS_ctx.report.generated_at));
    var __VLS_55;
    const __VLS_60 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
        span: (18),
    }));
    const __VLS_62 = __VLS_61({
        span: (18),
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    __VLS_63.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-grid" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
    });
    (__VLS_ctx.report.total_kb);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
    });
    (__VLS_ctx.report.total_docs);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
    });
    (__VLS_ctx.report.total_chunks);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
        ...{ style: {} },
    });
    (__VLS_ctx.report.valid_docs);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
        ...{ style: {} },
    });
    (__VLS_ctx.report.need_update_docs);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
        ...{ style: {} },
    });
    (__VLS_ctx.report.deprecated_docs);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
        ...{ style: {} },
    });
    (__VLS_ctx.report.failed_docs);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
    });
    (__VLS_ctx.report.issues.length);
    var __VLS_63;
    var __VLS_51;
    for (const [s, i] of __VLS_getVForSourceType((__VLS_ctx.report.suggestions))) {
        const __VLS_64 = {}.ElAlert;
        /** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
        // @ts-ignore
        const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
            key: (i),
            type: "info",
            closable: (false),
            showIcon: true,
            title: (s),
            ...{ style: {} },
        }));
        const __VLS_66 = __VLS_65({
            key: (i),
            type: "info",
            closable: (false),
            showIcon: true,
            title: (s),
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tf-section-title" },
        ...{ style: {} },
    });
    const __VLS_68 = {}.ElTable;
    /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
        data: (__VLS_ctx.report.issues),
        stripe: true,
        size: "small",
    }));
    const __VLS_70 = __VLS_69({
        data: (__VLS_ctx.report.issues),
        stripe: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    __VLS_71.slots.default;
    const __VLS_72 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        label: "类型",
        width: "120",
    }));
    const __VLS_74 = __VLS_73({
        label: "类型",
        width: "120",
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    __VLS_75.slots.default;
    {
        const { default: __VLS_thisSlot } = __VLS_75.slots;
        const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_76 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
            type: (__VLS_ctx.severityMap[row.severity] || 'info'),
            size: "small",
            effect: "light",
        }));
        const __VLS_78 = __VLS_77({
            type: (__VLS_ctx.severityMap[row.severity] || 'info'),
            size: "small",
            effect: "light",
        }, ...__VLS_functionalComponentArgsRest(__VLS_77));
        __VLS_79.slots.default;
        (__VLS_ctx.issueTypeMap[row.issue_type] || row.issue_type);
        var __VLS_79;
    }
    var __VLS_75;
    const __VLS_80 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        prop: "doc_title",
        label: "文档",
        minWidth: "200",
    }));
    const __VLS_82 = __VLS_81({
        prop: "doc_title",
        label: "文档",
        minWidth: "200",
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    const __VLS_84 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        prop: "detail",
        label: "问题描述",
        minWidth: "220",
    }));
    const __VLS_86 = __VLS_85({
        prop: "detail",
        label: "问题描述",
        minWidth: "220",
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    const __VLS_88 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
        prop: "suggestion",
        label: "处置建议",
        minWidth: "220",
    }));
    const __VLS_90 = __VLS_89({
        prop: "suggestion",
        label: "处置建议",
        minWidth: "220",
    }, ...__VLS_functionalComponentArgsRest(__VLS_89));
    {
        const { empty: __VLS_thisSlot } = __VLS_71.slots;
        const __VLS_92 = {}.ElEmpty;
        /** @type {[typeof __VLS_components.ElEmpty, typeof __VLS_components.elEmpty, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
            description: "未发现健康问题，知识库状态良好",
        }));
        const __VLS_94 = __VLS_93({
            description: "未发现健康问题，知识库状态良好",
        }, ...__VLS_functionalComponentArgsRest(__VLS_93));
    }
    var __VLS_71;
}
var __VLS_47;
const __VLS_96 = {}.ElTabPane;
/** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    label: "治理事项",
    name: "tasks",
}));
const __VLS_98 = __VLS_97({
    label: "治理事项",
    name: "tasks",
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
__VLS_99.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ style: {} },
});
const __VLS_100 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.taskQuery.status),
    placeholder: "全部状态",
    clearable: true,
    ...{ style: {} },
}));
const __VLS_102 = __VLS_101({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.taskQuery.status),
    placeholder: "全部状态",
    clearable: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_101));
let __VLS_104;
let __VLS_105;
let __VLS_106;
const __VLS_107 = {
    onChange: (__VLS_ctx.loadTasks)
};
__VLS_103.slots.default;
for (const [v, k] of __VLS_getVForSourceType((__VLS_ctx.taskStatusMap))) {
    const __VLS_108 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
        key: (k),
        label: (v.label),
        value: (k),
    }));
    const __VLS_110 = __VLS_109({
        key: (k),
        label: (v.label),
        value: (k),
    }, ...__VLS_functionalComponentArgsRest(__VLS_109));
}
var __VLS_103;
const __VLS_112 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.taskQuery.task_type),
    placeholder: "全部类型",
    clearable: true,
    ...{ style: {} },
}));
const __VLS_114 = __VLS_113({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.taskQuery.task_type),
    placeholder: "全部类型",
    clearable: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_113));
let __VLS_116;
let __VLS_117;
let __VLS_118;
const __VLS_119 = {
    onChange: (__VLS_ctx.loadTasks)
};
__VLS_115.slots.default;
for (const [v, k] of __VLS_getVForSourceType((__VLS_ctx.taskTypeMap))) {
    const __VLS_120 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
        key: (k),
        label: (v),
        value: (k),
    }));
    const __VLS_122 = __VLS_121({
        key: (k),
        label: (v),
        value: (k),
    }, ...__VLS_functionalComponentArgsRest(__VLS_121));
}
var __VLS_115;
const __VLS_124 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
    ...{ 'onClick': {} },
}));
const __VLS_126 = __VLS_125({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_125));
let __VLS_128;
let __VLS_129;
let __VLS_130;
const __VLS_131 = {
    onClick: (__VLS_ctx.loadTasks)
};
__VLS_127.slots.default;
const __VLS_132 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({}));
const __VLS_134 = __VLS_133({}, ...__VLS_functionalComponentArgsRest(__VLS_133));
__VLS_135.slots.default;
const __VLS_136 = {}.Refresh;
/** @type {[typeof __VLS_components.Refresh, ]} */ ;
// @ts-ignore
const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({}));
const __VLS_138 = __VLS_137({}, ...__VLS_functionalComponentArgsRest(__VLS_137));
var __VLS_135;
var __VLS_127;
const __VLS_140 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_142 = __VLS_141({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_141));
let __VLS_144;
let __VLS_145;
let __VLS_146;
const __VLS_147 = {
    onClick: (...[$event]) => {
        __VLS_ctx.openTaskDialog();
    }
};
__VLS_143.slots.default;
const __VLS_148 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({}));
const __VLS_150 = __VLS_149({}, ...__VLS_functionalComponentArgsRest(__VLS_149));
__VLS_151.slots.default;
const __VLS_152 = {}.Plus;
/** @type {[typeof __VLS_components.Plus, ]} */ ;
// @ts-ignore
const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({}));
const __VLS_154 = __VLS_153({}, ...__VLS_functionalComponentArgsRest(__VLS_153));
var __VLS_151;
var __VLS_143;
const __VLS_156 = {}.ElTable;
/** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
// @ts-ignore
const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
    data: (__VLS_ctx.tasks),
    stripe: true,
}));
const __VLS_158 = __VLS_157({
    data: (__VLS_ctx.tasks),
    stripe: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_157));
__VLS_asFunctionalDirective(__VLS_directives.vLoading)(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.taskLoading) }, null, null);
__VLS_159.slots.default;
const __VLS_160 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
    label: "类型",
    width: "110",
}));
const __VLS_162 = __VLS_161({
    label: "类型",
    width: "110",
}, ...__VLS_functionalComponentArgsRest(__VLS_161));
__VLS_163.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_163.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_164 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
        size: "small",
        effect: "plain",
    }));
    const __VLS_166 = __VLS_165({
        size: "small",
        effect: "plain",
    }, ...__VLS_functionalComponentArgsRest(__VLS_165));
    __VLS_167.slots.default;
    (__VLS_ctx.taskTypeMap[row.task_type] || row.task_type);
    var __VLS_167;
}
var __VLS_163;
const __VLS_168 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
    label: "事项",
    minWidth: "260",
}));
const __VLS_170 = __VLS_169({
    label: "事项",
    minWidth: "260",
}, ...__VLS_functionalComponentArgsRest(__VLS_169));
__VLS_171.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_171.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ style: {} },
    });
    (row.title);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tf-muted" },
        ...{ style: {} },
    });
    (row.description || '—');
}
var __VLS_171;
const __VLS_172 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
    label: "优先级",
    width: "90",
}));
const __VLS_174 = __VLS_173({
    label: "优先级",
    width: "90",
}, ...__VLS_functionalComponentArgsRest(__VLS_173));
__VLS_175.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_175.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_176 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
        type: (__VLS_ctx.priorityMap[row.priority]?.type || 'info'),
        size: "small",
    }));
    const __VLS_178 = __VLS_177({
        type: (__VLS_ctx.priorityMap[row.priority]?.type || 'info'),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_177));
    __VLS_179.slots.default;
    (__VLS_ctx.priorityMap[row.priority]?.label || row.priority);
    var __VLS_179;
}
var __VLS_175;
const __VLS_180 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
    label: "状态",
    width: "100",
}));
const __VLS_182 = __VLS_181({
    label: "状态",
    width: "100",
}, ...__VLS_functionalComponentArgsRest(__VLS_181));
__VLS_183.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_183.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_184 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
        type: (__VLS_ctx.taskStatusMap[row.status]?.type || 'info'),
        size: "small",
        effect: "light",
    }));
    const __VLS_186 = __VLS_185({
        type: (__VLS_ctx.taskStatusMap[row.status]?.type || 'info'),
        size: "small",
        effect: "light",
    }, ...__VLS_functionalComponentArgsRest(__VLS_185));
    __VLS_187.slots.default;
    (__VLS_ctx.taskStatusMap[row.status]?.label || row.status);
    var __VLS_187;
}
var __VLS_183;
const __VLS_188 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
    label: "责任人",
    width: "110",
}));
const __VLS_190 = __VLS_189({
    label: "责任人",
    width: "110",
}, ...__VLS_functionalComponentArgsRest(__VLS_189));
__VLS_191.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_191.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    (row.assignee || '未指派');
}
var __VLS_191;
const __VLS_192 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
    label: "创建时间",
    width: "150",
}));
const __VLS_194 = __VLS_193({
    label: "创建时间",
    width: "150",
}, ...__VLS_functionalComponentArgsRest(__VLS_193));
__VLS_195.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_195.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    (__VLS_ctx.fmtDate(row.created_at));
}
var __VLS_195;
const __VLS_196 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
    label: "操作",
    width: "190",
    fixed: "right",
}));
const __VLS_198 = __VLS_197({
    label: "操作",
    width: "190",
    fixed: "right",
}, ...__VLS_functionalComponentArgsRest(__VLS_197));
__VLS_199.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_199.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (row.status === 'open') {
        const __VLS_200 = {}.ElButton;
        /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
        // @ts-ignore
        const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
            ...{ 'onClick': {} },
            link: true,
            type: "primary",
        }));
        const __VLS_202 = __VLS_201({
            ...{ 'onClick': {} },
            link: true,
            type: "primary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_201));
        let __VLS_204;
        let __VLS_205;
        let __VLS_206;
        const __VLS_207 = {
            onClick: (...[$event]) => {
                if (!(row.status === 'open'))
                    return;
                __VLS_ctx.changeStatus(row, 'in_progress');
            }
        };
        __VLS_203.slots.default;
        var __VLS_203;
    }
    if (row.status !== 'resolved') {
        const __VLS_208 = {}.ElButton;
        /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
        // @ts-ignore
        const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
            ...{ 'onClick': {} },
            link: true,
            type: "success",
        }));
        const __VLS_210 = __VLS_209({
            ...{ 'onClick': {} },
            link: true,
            type: "success",
        }, ...__VLS_functionalComponentArgsRest(__VLS_209));
        let __VLS_212;
        let __VLS_213;
        let __VLS_214;
        const __VLS_215 = {
            onClick: (...[$event]) => {
                if (!(row.status !== 'resolved'))
                    return;
                __VLS_ctx.changeStatus(row, 'resolved');
            }
        };
        __VLS_211.slots.default;
        var __VLS_211;
    }
    if (row.status === 'open') {
        const __VLS_216 = {}.ElButton;
        /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
        // @ts-ignore
        const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({
            ...{ 'onClick': {} },
            link: true,
            type: "info",
        }));
        const __VLS_218 = __VLS_217({
            ...{ 'onClick': {} },
            link: true,
            type: "info",
        }, ...__VLS_functionalComponentArgsRest(__VLS_217));
        let __VLS_220;
        let __VLS_221;
        let __VLS_222;
        const __VLS_223 = {
            onClick: (...[$event]) => {
                if (!(row.status === 'open'))
                    return;
                __VLS_ctx.changeStatus(row, 'ignored');
            }
        };
        __VLS_219.slots.default;
        var __VLS_219;
    }
}
var __VLS_199;
{
    const { empty: __VLS_thisSlot } = __VLS_159.slots;
    const __VLS_224 = {}.ElEmpty;
    /** @type {[typeof __VLS_components.ElEmpty, typeof __VLS_components.elEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_225 = __VLS_asFunctionalComponent(__VLS_224, new __VLS_224({
        description: "暂无治理事项，可点击「自动生成治理事项」",
    }));
    const __VLS_226 = __VLS_225({
        description: "暂无治理事项，可点击「自动生成治理事项」",
    }, ...__VLS_functionalComponentArgsRest(__VLS_225));
}
var __VLS_159;
const __VLS_228 = {}.ElPagination;
/** @type {[typeof __VLS_components.ElPagination, typeof __VLS_components.elPagination, ]} */ ;
// @ts-ignore
const __VLS_229 = __VLS_asFunctionalComponent(__VLS_228, new __VLS_228({
    ...{ 'onCurrentChange': {} },
    currentPage: (__VLS_ctx.taskQuery.page),
    pageSize: (__VLS_ctx.taskQuery.page_size),
    total: (__VLS_ctx.taskTotal),
    layout: "total, prev, pager, next",
    ...{ style: {} },
}));
const __VLS_230 = __VLS_229({
    ...{ 'onCurrentChange': {} },
    currentPage: (__VLS_ctx.taskQuery.page),
    pageSize: (__VLS_ctx.taskQuery.page_size),
    total: (__VLS_ctx.taskTotal),
    layout: "total, prev, pager, next",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_229));
let __VLS_232;
let __VLS_233;
let __VLS_234;
const __VLS_235 = {
    onCurrentChange: (__VLS_ctx.loadTasks)
};
var __VLS_231;
var __VLS_99;
const __VLS_236 = {}.ElTabPane;
/** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
// @ts-ignore
const __VLS_237 = __VLS_asFunctionalComponent(__VLS_236, new __VLS_236({
    label: "知识盲区",
    name: "gaps",
}));
const __VLS_238 = __VLS_237({
    label: "知识盲区",
    name: "gaps",
}, ...__VLS_functionalComponentArgsRest(__VLS_237));
__VLS_239.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ style: {} },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "tf-muted" },
});
const __VLS_240 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.gapDays),
    ...{ style: {} },
}));
const __VLS_242 = __VLS_241({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.gapDays),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_241));
let __VLS_244;
let __VLS_245;
let __VLS_246;
const __VLS_247 = {
    onChange: (__VLS_ctx.loadGaps)
};
__VLS_243.slots.default;
const __VLS_248 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({
    value: (7),
    label: "近 7 天",
}));
const __VLS_250 = __VLS_249({
    value: (7),
    label: "近 7 天",
}, ...__VLS_functionalComponentArgsRest(__VLS_249));
const __VLS_252 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_253 = __VLS_asFunctionalComponent(__VLS_252, new __VLS_252({
    value: (30),
    label: "近 30 天",
}));
const __VLS_254 = __VLS_253({
    value: (30),
    label: "近 30 天",
}, ...__VLS_functionalComponentArgsRest(__VLS_253));
const __VLS_256 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_257 = __VLS_asFunctionalComponent(__VLS_256, new __VLS_256({
    value: (90),
    label: "近 90 天",
}));
const __VLS_258 = __VLS_257({
    value: (90),
    label: "近 90 天",
}, ...__VLS_functionalComponentArgsRest(__VLS_257));
var __VLS_243;
const __VLS_260 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_261 = __VLS_asFunctionalComponent(__VLS_260, new __VLS_260({
    ...{ 'onClick': {} },
}));
const __VLS_262 = __VLS_261({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_261));
let __VLS_264;
let __VLS_265;
let __VLS_266;
const __VLS_267 = {
    onClick: (__VLS_ctx.loadGaps)
};
__VLS_263.slots.default;
const __VLS_268 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_269 = __VLS_asFunctionalComponent(__VLS_268, new __VLS_268({}));
const __VLS_270 = __VLS_269({}, ...__VLS_functionalComponentArgsRest(__VLS_269));
__VLS_271.slots.default;
const __VLS_272 = {}.Refresh;
/** @type {[typeof __VLS_components.Refresh, ]} */ ;
// @ts-ignore
const __VLS_273 = __VLS_asFunctionalComponent(__VLS_272, new __VLS_272({}));
const __VLS_274 = __VLS_273({}, ...__VLS_functionalComponentArgsRest(__VLS_273));
var __VLS_271;
var __VLS_263;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "tf-muted" },
    ...{ style: {} },
});
const __VLS_276 = {}.ElTable;
/** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
// @ts-ignore
const __VLS_277 = __VLS_asFunctionalComponent(__VLS_276, new __VLS_276({
    data: (__VLS_ctx.gaps),
    stripe: true,
}));
const __VLS_278 = __VLS_277({
    data: (__VLS_ctx.gaps),
    stripe: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_277));
__VLS_asFunctionalDirective(__VLS_directives.vLoading)(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.gapLoading) }, null, null);
__VLS_279.slots.default;
const __VLS_280 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_281 = __VLS_asFunctionalComponent(__VLS_280, new __VLS_280({
    prop: "query",
    label: "未被有效回答的问题",
    minWidth: "300",
}));
const __VLS_282 = __VLS_281({
    prop: "query",
    label: "未被有效回答的问题",
    minWidth: "300",
}, ...__VLS_functionalComponentArgsRest(__VLS_281));
const __VLS_284 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_285 = __VLS_asFunctionalComponent(__VLS_284, new __VLS_284({
    prop: "count",
    label: "提问次数",
    width: "100",
    sortable: true,
}));
const __VLS_286 = __VLS_285({
    prop: "count",
    label: "提问次数",
    width: "100",
    sortable: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_285));
const __VLS_288 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_289 = __VLS_asFunctionalComponent(__VLS_288, new __VLS_288({
    label: "平均置信度",
    width: "130",
}));
const __VLS_290 = __VLS_289({
    label: "平均置信度",
    width: "130",
}, ...__VLS_functionalComponentArgsRest(__VLS_289));
__VLS_291.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_291.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_292 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_293 = __VLS_asFunctionalComponent(__VLS_292, new __VLS_292({
        type: "danger",
        size: "small",
        effect: "plain",
    }));
    const __VLS_294 = __VLS_293({
        type: "danger",
        size: "small",
        effect: "plain",
    }, ...__VLS_functionalComponentArgsRest(__VLS_293));
    __VLS_295.slots.default;
    ((row.avg_confidence * 100).toFixed(0));
    var __VLS_295;
}
var __VLS_291;
const __VLS_296 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_297 = __VLS_asFunctionalComponent(__VLS_296, new __VLS_296({
    prop: "suggestion",
    label: "补录建议",
    minWidth: "250",
}));
const __VLS_298 = __VLS_297({
    prop: "suggestion",
    label: "补录建议",
    minWidth: "250",
}, ...__VLS_functionalComponentArgsRest(__VLS_297));
const __VLS_300 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_301 = __VLS_asFunctionalComponent(__VLS_300, new __VLS_300({
    label: "操作",
    width: "120",
    fixed: "right",
}));
const __VLS_302 = __VLS_301({
    label: "操作",
    width: "120",
    fixed: "right",
}, ...__VLS_functionalComponentArgsRest(__VLS_301));
__VLS_303.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_303.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_304 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_305 = __VLS_asFunctionalComponent(__VLS_304, new __VLS_304({
        ...{ 'onClick': {} },
        link: true,
        type: "primary",
    }));
    const __VLS_306 = __VLS_305({
        ...{ 'onClick': {} },
        link: true,
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_305));
    let __VLS_308;
    let __VLS_309;
    let __VLS_310;
    const __VLS_311 = {
        onClick: (...[$event]) => {
            __VLS_ctx.gapToTask(row);
        }
    };
    __VLS_307.slots.default;
    var __VLS_307;
}
var __VLS_303;
{
    const { empty: __VLS_thisSlot } = __VLS_279.slots;
    const __VLS_312 = {}.ElEmpty;
    /** @type {[typeof __VLS_components.ElEmpty, typeof __VLS_components.elEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_313 = __VLS_asFunctionalComponent(__VLS_312, new __VLS_312({
        description: "暂无知识盲区，知识覆盖良好",
    }));
    const __VLS_314 = __VLS_313({
        description: "暂无知识盲区，知识覆盖良好",
    }, ...__VLS_functionalComponentArgsRest(__VLS_313));
}
var __VLS_279;
var __VLS_239;
const __VLS_316 = {}.ElTabPane;
/** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
// @ts-ignore
const __VLS_317 = __VLS_asFunctionalComponent(__VLS_316, new __VLS_316({
    label: "运营报告",
    name: "report",
}));
const __VLS_318 = __VLS_317({
    label: "运营报告",
    name: "report",
}, ...__VLS_functionalComponentArgsRest(__VLS_317));
__VLS_319.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ style: {} },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "tf-muted" },
});
const __VLS_320 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_321 = __VLS_asFunctionalComponent(__VLS_320, new __VLS_320({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.opDays),
    ...{ style: {} },
}));
const __VLS_322 = __VLS_321({
    ...{ 'onChange': {} },
    modelValue: (__VLS_ctx.opDays),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_321));
let __VLS_324;
let __VLS_325;
let __VLS_326;
const __VLS_327 = {
    onChange: (__VLS_ctx.loadOpReport)
};
__VLS_323.slots.default;
const __VLS_328 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_329 = __VLS_asFunctionalComponent(__VLS_328, new __VLS_328({
    value: (7),
    label: "周报（7 天）",
}));
const __VLS_330 = __VLS_329({
    value: (7),
    label: "周报（7 天）",
}, ...__VLS_functionalComponentArgsRest(__VLS_329));
const __VLS_332 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_333 = __VLS_asFunctionalComponent(__VLS_332, new __VLS_332({
    value: (30),
    label: "月报（30 天）",
}));
const __VLS_334 = __VLS_333({
    value: (30),
    label: "月报（30 天）",
}, ...__VLS_functionalComponentArgsRest(__VLS_333));
var __VLS_323;
const __VLS_336 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_337 = __VLS_asFunctionalComponent(__VLS_336, new __VLS_336({
    ...{ 'onClick': {} },
}));
const __VLS_338 = __VLS_337({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_337));
let __VLS_340;
let __VLS_341;
let __VLS_342;
const __VLS_343 = {
    onClick: (__VLS_ctx.loadOpReport)
};
__VLS_339.slots.default;
const __VLS_344 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_345 = __VLS_asFunctionalComponent(__VLS_344, new __VLS_344({}));
const __VLS_346 = __VLS_345({}, ...__VLS_functionalComponentArgsRest(__VLS_345));
__VLS_347.slots.default;
const __VLS_348 = {}.Refresh;
/** @type {[typeof __VLS_components.Refresh, ]} */ ;
// @ts-ignore
const __VLS_349 = __VLS_asFunctionalComponent(__VLS_348, new __VLS_348({}));
const __VLS_350 = __VLS_349({}, ...__VLS_functionalComponentArgsRest(__VLS_349));
var __VLS_347;
var __VLS_339;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalDirective(__VLS_directives.vLoading)(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.opLoading) }, null, null);
if (__VLS_ctx.opReport) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tf-muted" },
        ...{ style: {} },
    });
    (__VLS_ctx.fmtDate(__VLS_ctx.opReport.start));
    (__VLS_ctx.fmtDate(__VLS_ctx.opReport.end));
    (__VLS_ctx.opReport.period);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-grid" },
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
    });
    (__VLS_ctx.opReport.new_docs);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
    });
    (__VLS_ctx.opReport.new_chunks);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
    });
    (__VLS_ctx.opReport.total_queries);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
        ...{ style: ({ color: __VLS_ctx.opReport.answer_rate >= 0.8 ? 'var(--tf-success)' : 'var(--tf-warn)' }) },
    });
    ((__VLS_ctx.opReport.answer_rate * 100).toFixed(1));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
    });
    ((__VLS_ctx.opReport.avg_confidence * 100).toFixed(0));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
    });
    (__VLS_ctx.opReport.avg_latency_ms);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
        ...{ style: {} },
    });
    (__VLS_ctx.opReport.unanswered_queries);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "value" },
    });
    (__VLS_ctx.opReport.pending_tasks);
    const __VLS_352 = {}.ElRow;
    /** @type {[typeof __VLS_components.ElRow, typeof __VLS_components.elRow, typeof __VLS_components.ElRow, typeof __VLS_components.elRow, ]} */ ;
    // @ts-ignore
    const __VLS_353 = __VLS_asFunctionalComponent(__VLS_352, new __VLS_352({
        gutter: (14),
    }));
    const __VLS_354 = __VLS_353({
        gutter: (14),
    }, ...__VLS_functionalComponentArgsRest(__VLS_353));
    __VLS_355.slots.default;
    const __VLS_356 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_357 = __VLS_asFunctionalComponent(__VLS_356, new __VLS_356({
        span: (12),
    }));
    const __VLS_358 = __VLS_357({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_357));
    __VLS_359.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tf-section-title" },
    });
    const __VLS_360 = {}.ElTable;
    /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
    // @ts-ignore
    const __VLS_361 = __VLS_asFunctionalComponent(__VLS_360, new __VLS_360({
        data: (__VLS_ctx.opReport.hot_topics),
        size: "small",
        stripe: true,
    }));
    const __VLS_362 = __VLS_361({
        data: (__VLS_ctx.opReport.hot_topics),
        size: "small",
        stripe: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_361));
    __VLS_363.slots.default;
    const __VLS_364 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_365 = __VLS_asFunctionalComponent(__VLS_364, new __VLS_364({
        prop: "topic",
        label: "主题",
    }));
    const __VLS_366 = __VLS_365({
        prop: "topic",
        label: "主题",
    }, ...__VLS_functionalComponentArgsRest(__VLS_365));
    const __VLS_368 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_369 = __VLS_asFunctionalComponent(__VLS_368, new __VLS_368({
        prop: "count",
        label: "提及次数",
        width: "110",
    }));
    const __VLS_370 = __VLS_369({
        prop: "count",
        label: "提及次数",
        width: "110",
    }, ...__VLS_functionalComponentArgsRest(__VLS_369));
    {
        const { empty: __VLS_thisSlot } = __VLS_363.slots;
        const __VLS_372 = {}.ElEmpty;
        /** @type {[typeof __VLS_components.ElEmpty, typeof __VLS_components.elEmpty, ]} */ ;
        // @ts-ignore
        const __VLS_373 = __VLS_asFunctionalComponent(__VLS_372, new __VLS_372({
            description: "暂无数据",
            imageSize: (60),
        }));
        const __VLS_374 = __VLS_373({
            description: "暂无数据",
            imageSize: (60),
        }, ...__VLS_functionalComponentArgsRest(__VLS_373));
    }
    var __VLS_363;
    var __VLS_359;
    const __VLS_376 = {}.ElCol;
    /** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
    // @ts-ignore
    const __VLS_377 = __VLS_asFunctionalComponent(__VLS_376, new __VLS_376({
        span: (12),
    }));
    const __VLS_378 = __VLS_377({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_377));
    __VLS_379.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tf-section-title" },
    });
    const __VLS_380 = {}.ElTable;
    /** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
    // @ts-ignore
    const __VLS_381 = __VLS_asFunctionalComponent(__VLS_380, new __VLS_380({
        data: (__VLS_ctx.opReport.knowledge_gaps),
        size: "small",
        stripe: true,
    }));
    const __VLS_382 = __VLS_381({
        data: (__VLS_ctx.opReport.knowledge_gaps),
        size: "small",
        stripe: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_381));
    __VLS_383.slots.default;
    const __VLS_384 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_385 = __VLS_asFunctionalComponent(__VLS_384, new __VLS_384({
        prop: "query",
        label: "问题",
        showOverflowTooltip: true,
    }));
    const __VLS_386 = __VLS_385({
        prop: "query",
        label: "问题",
        showOverflowTooltip: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_385));
    const __VLS_388 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_389 = __VLS_asFunctionalComponent(__VLS_388, new __VLS_388({
        prop: "count",
        label: "次数",
        width: "70",
    }));
    const __VLS_390 = __VLS_389({
        prop: "count",
        label: "次数",
        width: "70",
    }, ...__VLS_functionalComponentArgsRest(__VLS_389));
    {
        const { empty: __VLS_thisSlot } = __VLS_383.slots;
        const __VLS_392 = {}.ElEmpty;
        /** @type {[typeof __VLS_components.ElEmpty, typeof __VLS_components.elEmpty, ]} */ ;
        // @ts-ignore
        const __VLS_393 = __VLS_asFunctionalComponent(__VLS_392, new __VLS_392({
            description: "暂无数据",
            imageSize: (60),
        }));
        const __VLS_394 = __VLS_393({
            description: "暂无数据",
            imageSize: (60),
        }, ...__VLS_functionalComponentArgsRest(__VLS_393));
    }
    var __VLS_383;
    var __VLS_379;
    var __VLS_355;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tf-section-title" },
        ...{ style: {} },
    });
    for (const [s, i] of __VLS_getVForSourceType((__VLS_ctx.opReport.suggestions))) {
        const __VLS_396 = {}.ElAlert;
        /** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
        // @ts-ignore
        const __VLS_397 = __VLS_asFunctionalComponent(__VLS_396, new __VLS_396({
            key: (i),
            type: "success",
            closable: (false),
            showIcon: true,
            title: (s),
            ...{ style: {} },
        }));
        const __VLS_398 = __VLS_397({
            key: (i),
            type: "success",
            closable: (false),
            showIcon: true,
            title: (s),
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_397));
    }
    if (!__VLS_ctx.opReport.suggestions.length) {
        const __VLS_400 = {}.ElEmpty;
        /** @type {[typeof __VLS_components.ElEmpty, typeof __VLS_components.elEmpty, ]} */ ;
        // @ts-ignore
        const __VLS_401 = __VLS_asFunctionalComponent(__VLS_400, new __VLS_400({
            description: "本周期运行平稳，无特别建议",
            imageSize: (70),
        }));
        const __VLS_402 = __VLS_401({
            description: "本周期运行平稳，无特别建议",
            imageSize: (70),
        }, ...__VLS_functionalComponentArgsRest(__VLS_401));
    }
}
var __VLS_319;
var __VLS_39;
const __VLS_404 = {}.ElDialog;
/** @type {[typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, ]} */ ;
// @ts-ignore
const __VLS_405 = __VLS_asFunctionalComponent(__VLS_404, new __VLS_404({
    modelValue: (__VLS_ctx.taskDialog),
    title: "新建治理事项",
    width: "560px",
}));
const __VLS_406 = __VLS_405({
    modelValue: (__VLS_ctx.taskDialog),
    title: "新建治理事项",
    width: "560px",
}, ...__VLS_functionalComponentArgsRest(__VLS_405));
__VLS_407.slots.default;
const __VLS_408 = {}.ElForm;
/** @type {[typeof __VLS_components.ElForm, typeof __VLS_components.elForm, typeof __VLS_components.ElForm, typeof __VLS_components.elForm, ]} */ ;
// @ts-ignore
const __VLS_409 = __VLS_asFunctionalComponent(__VLS_408, new __VLS_408({
    model: (__VLS_ctx.taskForm),
    labelWidth: "90px",
}));
const __VLS_410 = __VLS_409({
    model: (__VLS_ctx.taskForm),
    labelWidth: "90px",
}, ...__VLS_functionalComponentArgsRest(__VLS_409));
__VLS_411.slots.default;
const __VLS_412 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_413 = __VLS_asFunctionalComponent(__VLS_412, new __VLS_412({
    label: "类型",
}));
const __VLS_414 = __VLS_413({
    label: "类型",
}, ...__VLS_functionalComponentArgsRest(__VLS_413));
__VLS_415.slots.default;
const __VLS_416 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_417 = __VLS_asFunctionalComponent(__VLS_416, new __VLS_416({
    modelValue: (__VLS_ctx.taskForm.task_type),
    ...{ style: {} },
}));
const __VLS_418 = __VLS_417({
    modelValue: (__VLS_ctx.taskForm.task_type),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_417));
__VLS_419.slots.default;
for (const [v, k] of __VLS_getVForSourceType((__VLS_ctx.taskTypeMap))) {
    const __VLS_420 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_421 = __VLS_asFunctionalComponent(__VLS_420, new __VLS_420({
        key: (k),
        label: (v),
        value: (k),
    }));
    const __VLS_422 = __VLS_421({
        key: (k),
        label: (v),
        value: (k),
    }, ...__VLS_functionalComponentArgsRest(__VLS_421));
}
var __VLS_419;
var __VLS_415;
const __VLS_424 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_425 = __VLS_asFunctionalComponent(__VLS_424, new __VLS_424({
    label: "标题",
    required: true,
}));
const __VLS_426 = __VLS_425({
    label: "标题",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_425));
__VLS_427.slots.default;
const __VLS_428 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_429 = __VLS_asFunctionalComponent(__VLS_428, new __VLS_428({
    modelValue: (__VLS_ctx.taskForm.title),
}));
const __VLS_430 = __VLS_429({
    modelValue: (__VLS_ctx.taskForm.title),
}, ...__VLS_functionalComponentArgsRest(__VLS_429));
var __VLS_427;
const __VLS_432 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_433 = __VLS_asFunctionalComponent(__VLS_432, new __VLS_432({
    label: "知识库",
}));
const __VLS_434 = __VLS_433({
    label: "知识库",
}, ...__VLS_functionalComponentArgsRest(__VLS_433));
__VLS_435.slots.default;
const __VLS_436 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_437 = __VLS_asFunctionalComponent(__VLS_436, new __VLS_436({
    modelValue: (__VLS_ctx.taskForm.kb_id),
    clearable: true,
    placeholder: "不限",
    ...{ style: {} },
}));
const __VLS_438 = __VLS_437({
    modelValue: (__VLS_ctx.taskForm.kb_id),
    clearable: true,
    placeholder: "不限",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_437));
__VLS_439.slots.default;
for (const [k] of __VLS_getVForSourceType((__VLS_ctx.kbs))) {
    const __VLS_440 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_441 = __VLS_asFunctionalComponent(__VLS_440, new __VLS_440({
        key: (k.id),
        label: (k.name),
        value: (k.id),
    }));
    const __VLS_442 = __VLS_441({
        key: (k.id),
        label: (k.name),
        value: (k.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_441));
}
var __VLS_439;
var __VLS_435;
const __VLS_444 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_445 = __VLS_asFunctionalComponent(__VLS_444, new __VLS_444({
    label: "优先级",
}));
const __VLS_446 = __VLS_445({
    label: "优先级",
}, ...__VLS_functionalComponentArgsRest(__VLS_445));
__VLS_447.slots.default;
const __VLS_448 = {}.ElRadioGroup;
/** @type {[typeof __VLS_components.ElRadioGroup, typeof __VLS_components.elRadioGroup, typeof __VLS_components.ElRadioGroup, typeof __VLS_components.elRadioGroup, ]} */ ;
// @ts-ignore
const __VLS_449 = __VLS_asFunctionalComponent(__VLS_448, new __VLS_448({
    modelValue: (__VLS_ctx.taskForm.priority),
}));
const __VLS_450 = __VLS_449({
    modelValue: (__VLS_ctx.taskForm.priority),
}, ...__VLS_functionalComponentArgsRest(__VLS_449));
__VLS_451.slots.default;
const __VLS_452 = {}.ElRadioButton;
/** @type {[typeof __VLS_components.ElRadioButton, typeof __VLS_components.elRadioButton, typeof __VLS_components.ElRadioButton, typeof __VLS_components.elRadioButton, ]} */ ;
// @ts-ignore
const __VLS_453 = __VLS_asFunctionalComponent(__VLS_452, new __VLS_452({
    value: "high",
}));
const __VLS_454 = __VLS_453({
    value: "high",
}, ...__VLS_functionalComponentArgsRest(__VLS_453));
__VLS_455.slots.default;
var __VLS_455;
const __VLS_456 = {}.ElRadioButton;
/** @type {[typeof __VLS_components.ElRadioButton, typeof __VLS_components.elRadioButton, typeof __VLS_components.ElRadioButton, typeof __VLS_components.elRadioButton, ]} */ ;
// @ts-ignore
const __VLS_457 = __VLS_asFunctionalComponent(__VLS_456, new __VLS_456({
    value: "medium",
}));
const __VLS_458 = __VLS_457({
    value: "medium",
}, ...__VLS_functionalComponentArgsRest(__VLS_457));
__VLS_459.slots.default;
var __VLS_459;
const __VLS_460 = {}.ElRadioButton;
/** @type {[typeof __VLS_components.ElRadioButton, typeof __VLS_components.elRadioButton, typeof __VLS_components.ElRadioButton, typeof __VLS_components.elRadioButton, ]} */ ;
// @ts-ignore
const __VLS_461 = __VLS_asFunctionalComponent(__VLS_460, new __VLS_460({
    value: "low",
}));
const __VLS_462 = __VLS_461({
    value: "low",
}, ...__VLS_functionalComponentArgsRest(__VLS_461));
__VLS_463.slots.default;
var __VLS_463;
var __VLS_451;
var __VLS_447;
const __VLS_464 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_465 = __VLS_asFunctionalComponent(__VLS_464, new __VLS_464({
    label: "责任人",
}));
const __VLS_466 = __VLS_465({
    label: "责任人",
}, ...__VLS_functionalComponentArgsRest(__VLS_465));
__VLS_467.slots.default;
const __VLS_468 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_469 = __VLS_asFunctionalComponent(__VLS_468, new __VLS_468({
    modelValue: (__VLS_ctx.taskForm.assignee),
    placeholder: "如：技术质量部-李工",
}));
const __VLS_470 = __VLS_469({
    modelValue: (__VLS_ctx.taskForm.assignee),
    placeholder: "如：技术质量部-李工",
}, ...__VLS_functionalComponentArgsRest(__VLS_469));
var __VLS_467;
const __VLS_472 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_473 = __VLS_asFunctionalComponent(__VLS_472, new __VLS_472({
    label: "说明",
}));
const __VLS_474 = __VLS_473({
    label: "说明",
}, ...__VLS_functionalComponentArgsRest(__VLS_473));
__VLS_475.slots.default;
const __VLS_476 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_477 = __VLS_asFunctionalComponent(__VLS_476, new __VLS_476({
    modelValue: (__VLS_ctx.taskForm.description),
    type: "textarea",
    rows: (3),
}));
const __VLS_478 = __VLS_477({
    modelValue: (__VLS_ctx.taskForm.description),
    type: "textarea",
    rows: (3),
}, ...__VLS_functionalComponentArgsRest(__VLS_477));
var __VLS_475;
var __VLS_411;
{
    const { footer: __VLS_thisSlot } = __VLS_407.slots;
    const __VLS_480 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_481 = __VLS_asFunctionalComponent(__VLS_480, new __VLS_480({
        ...{ 'onClick': {} },
    }));
    const __VLS_482 = __VLS_481({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_481));
    let __VLS_484;
    let __VLS_485;
    let __VLS_486;
    const __VLS_487 = {
        onClick: (...[$event]) => {
            __VLS_ctx.taskDialog = false;
        }
    };
    __VLS_483.slots.default;
    var __VLS_483;
    const __VLS_488 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_489 = __VLS_asFunctionalComponent(__VLS_488, new __VLS_488({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_490 = __VLS_489({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_489));
    let __VLS_492;
    let __VLS_493;
    let __VLS_494;
    const __VLS_495 = {
        onClick: (__VLS_ctx.submitTask)
    };
    __VLS_491.slots.default;
    var __VLS_491;
}
var __VLS_407;
/** @type {__VLS_StyleScopedClasses['tf-card']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['value']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-section-title']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            tab: tab,
            kbs: kbs,
            selectedKb: selectedKb,
            report: report,
            healthLoading: healthLoading,
            issueTypeMap: issueTypeMap,
            severityMap: severityMap,
            scoreColor: scoreColor,
            loadHealth: loadHealth,
            tasks: tasks,
            taskTotal: taskTotal,
            taskLoading: taskLoading,
            taskQuery: taskQuery,
            taskTypeMap: taskTypeMap,
            taskStatusMap: taskStatusMap,
            priorityMap: priorityMap,
            loadTasks: loadTasks,
            autoGenerate: autoGenerate,
            changeStatus: changeStatus,
            taskDialog: taskDialog,
            taskForm: taskForm,
            openTaskDialog: openTaskDialog,
            submitTask: submitTask,
            gaps: gaps,
            gapDays: gapDays,
            gapLoading: gapLoading,
            loadGaps: loadGaps,
            gapToTask: gapToTask,
            opReport: opReport,
            opDays: opDays,
            opLoading: opLoading,
            loadOpReport: loadOpReport,
            onTabChange: onTabChange,
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
