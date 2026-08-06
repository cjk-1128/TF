/// <reference types="../../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
import { onMounted, ref } from 'vue';
import { kbApi, ragApi } from '@/api';
import ChunkCard from '@/components/ChunkCard.vue';
const kbs = ref([]);
const results = ref([]);
const loading = ref(false);
const searched = ref(false);
const form = ref({
    query: '',
    kb_ids: [],
    domains: [],
    top_k: 10,
    use_rerank: true
});
const domainOptions = [
    { value: 'standard', label: '建设规范库' },
    { value: 'case', label: '项目案例库' },
    { value: 'enterprise', label: '企业知识库' }
];
const samples = ['基坑监测报警值', '混凝土养护时间', '脚手架连墙件设置', '防水混凝土抗渗等级', '楼板裂缝处理'];
async function doSearch() {
    if (!form.value.query.trim())
        return;
    loading.value = true;
    try {
        const res = await ragApi.search({ ...form.value });
        results.value = res.data || [];
        searched.value = true;
    }
    finally {
        loading.value = false;
    }
}
function useSample(s) {
    form.value.query = s;
    doSearch();
}
onMounted(async () => {
    const res = await kbApi.list();
    kbs.value = res.data || [];
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
    ...{ class: "tf-section-title" },
});
const __VLS_0 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.Search;
/** @type {[typeof __VLS_components.Search, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({}));
const __VLS_6 = __VLS_5({}, ...__VLS_functionalComponentArgsRest(__VLS_5));
var __VLS_3;
const __VLS_8 = {}.ElForm;
/** @type {[typeof __VLS_components.ElForm, typeof __VLS_components.elForm, typeof __VLS_components.ElForm, typeof __VLS_components.elForm, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    model: (__VLS_ctx.form),
    labelWidth: "88px",
}));
const __VLS_10 = __VLS_9({
    model: (__VLS_ctx.form),
    labelWidth: "88px",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
const __VLS_12 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    label: "检索语句",
}));
const __VLS_14 = __VLS_13({
    label: "检索语句",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
const __VLS_16 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.form.query),
    placeholder: "输入工程关键词或完整问题，例如：深基坑支护结构水平位移报警值",
    clearable: true,
}));
const __VLS_18 = __VLS_17({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.form.query),
    placeholder: "输入工程关键词或完整问题，例如：深基坑支护结构水平位移报警值",
    clearable: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onKeyup: (__VLS_ctx.doSearch)
};
__VLS_19.slots.default;
{
    const { append: __VLS_thisSlot } = __VLS_19.slots;
    const __VLS_24 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.loading),
        type: "primary",
    }));
    const __VLS_26 = __VLS_25({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.loading),
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    let __VLS_28;
    let __VLS_29;
    let __VLS_30;
    const __VLS_31 = {
        onClick: (__VLS_ctx.doSearch)
    };
    __VLS_27.slots.default;
    var __VLS_27;
}
var __VLS_19;
var __VLS_15;
const __VLS_32 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    label: "快捷示例",
}));
const __VLS_34 = __VLS_33({
    label: "快捷示例",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
for (const [s] of __VLS_getVForSourceType((__VLS_ctx.samples))) {
    const __VLS_36 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        ...{ 'onClick': {} },
        key: (s),
        ...{ style: {} },
        effect: "plain",
    }));
    const __VLS_38 = __VLS_37({
        ...{ 'onClick': {} },
        key: (s),
        ...{ style: {} },
        effect: "plain",
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    let __VLS_40;
    let __VLS_41;
    let __VLS_42;
    const __VLS_43 = {
        onClick: (...[$event]) => {
            __VLS_ctx.useSample(s);
        }
    };
    __VLS_39.slots.default;
    (s);
    var __VLS_39;
}
var __VLS_35;
const __VLS_44 = {}.ElRow;
/** @type {[typeof __VLS_components.ElRow, typeof __VLS_components.elRow, typeof __VLS_components.ElRow, typeof __VLS_components.elRow, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    gutter: (12),
}));
const __VLS_46 = __VLS_45({
    gutter: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
const __VLS_48 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    span: (8),
}));
const __VLS_50 = __VLS_49({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
const __VLS_52 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    label: "知识库",
}));
const __VLS_54 = __VLS_53({
    label: "知识库",
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
const __VLS_56 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    modelValue: (__VLS_ctx.form.kb_ids),
    multiple: true,
    collapseTags: true,
    clearable: true,
    placeholder: "全部",
    ...{ style: {} },
}));
const __VLS_58 = __VLS_57({
    modelValue: (__VLS_ctx.form.kb_ids),
    multiple: true,
    collapseTags: true,
    clearable: true,
    placeholder: "全部",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
for (const [k] of __VLS_getVForSourceType((__VLS_ctx.kbs))) {
    const __VLS_60 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
        key: (k.id),
        label: (k.name),
        value: (k.id),
    }));
    const __VLS_62 = __VLS_61({
        key: (k.id),
        label: (k.name),
        value: (k.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
}
var __VLS_59;
var __VLS_55;
var __VLS_51;
const __VLS_64 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    span: (8),
}));
const __VLS_66 = __VLS_65({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
const __VLS_68 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    label: "知识域",
}));
const __VLS_70 = __VLS_69({
    label: "知识域",
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
const __VLS_72 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    modelValue: (__VLS_ctx.form.domains),
    multiple: true,
    collapseTags: true,
    clearable: true,
    placeholder: "全部",
    ...{ style: {} },
}));
const __VLS_74 = __VLS_73({
    modelValue: (__VLS_ctx.form.domains),
    multiple: true,
    collapseTags: true,
    clearable: true,
    placeholder: "全部",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
__VLS_75.slots.default;
for (const [d] of __VLS_getVForSourceType((__VLS_ctx.domainOptions))) {
    const __VLS_76 = {}.ElOption;
    /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        key: (d.value),
        label: (d.label),
        value: (d.value),
    }));
    const __VLS_78 = __VLS_77({
        key: (d.value),
        label: (d.label),
        value: (d.value),
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
}
var __VLS_75;
var __VLS_71;
var __VLS_67;
const __VLS_80 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
    span: (4),
}));
const __VLS_82 = __VLS_81({
    span: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
__VLS_83.slots.default;
const __VLS_84 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    label: "Top-K",
}));
const __VLS_86 = __VLS_85({
    label: "Top-K",
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
const __VLS_88 = {}.ElInputNumber;
/** @type {[typeof __VLS_components.ElInputNumber, typeof __VLS_components.elInputNumber, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    modelValue: (__VLS_ctx.form.top_k),
    min: (1),
    max: (50),
    ...{ style: {} },
}));
const __VLS_90 = __VLS_89({
    modelValue: (__VLS_ctx.form.top_k),
    min: (1),
    max: (50),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
var __VLS_87;
var __VLS_83;
const __VLS_92 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    span: (4),
}));
const __VLS_94 = __VLS_93({
    span: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
__VLS_95.slots.default;
const __VLS_96 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    label: "重排序",
}));
const __VLS_98 = __VLS_97({
    label: "重排序",
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
__VLS_99.slots.default;
const __VLS_100 = {}.ElSwitch;
/** @type {[typeof __VLS_components.ElSwitch, typeof __VLS_components.elSwitch, ]} */ ;
// @ts-ignore
const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
    modelValue: (__VLS_ctx.form.use_rerank),
}));
const __VLS_102 = __VLS_101({
    modelValue: (__VLS_ctx.form.use_rerank),
}, ...__VLS_functionalComponentArgsRest(__VLS_101));
var __VLS_99;
var __VLS_95;
var __VLS_47;
var __VLS_11;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tf-card" },
    ...{ style: {} },
});
__VLS_asFunctionalDirective(__VLS_directives.vLoading)(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.loading) }, null, null);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tf-section-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "tf-muted" },
    ...{ style: {} },
});
(__VLS_ctx.results.length);
if (__VLS_ctx.searched && !__VLS_ctx.results.length) {
    const __VLS_104 = {}.ElEmpty;
    /** @type {[typeof __VLS_components.ElEmpty, typeof __VLS_components.elEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
        description: "未检索到相关知识，建议补充相应规范或案例资料",
    }));
    const __VLS_106 = __VLS_105({
        description: "未检索到相关知识，建议补充相应规范或案例资料",
    }, ...__VLS_functionalComponentArgsRest(__VLS_105));
}
else if (!__VLS_ctx.searched) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tf-muted" },
        ...{ style: {} },
    });
}
for (const [c, i] of __VLS_getVForSourceType((__VLS_ctx.results))) {
    /** @type {[typeof ChunkCard, ]} */ ;
    // @ts-ignore
    const __VLS_108 = __VLS_asFunctionalComponent(ChunkCard, new ChunkCard({
        key: (c.chunk_id),
        chunk: (c),
        rank: (i + 1),
    }));
    const __VLS_109 = __VLS_108({
        key: (c.chunk_id),
        chunk: (c),
        rank: (i + 1),
    }, ...__VLS_functionalComponentArgsRest(__VLS_108));
}
/** @type {__VLS_StyleScopedClasses['tf-card']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-card']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            ChunkCard: ChunkCard,
            kbs: kbs,
            results: results,
            loading: loading,
            searched: searched,
            form: form,
            domainOptions: domainOptions,
            samples: samples,
            doSearch: doSearch,
            useSample: useSample,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
