/// <reference types="../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { kbApi } from '@/api';
const route = useRoute();
const router = useRouter();
const collapsed = ref(false);
const backendOk = ref(null);
const stats = ref({});
const menus = [
    { path: '/chat', title: '工程智能问答', icon: 'ChatDotRound' },
    { path: '/search', title: '知识片段检索', icon: 'Search' },
    { path: '/knowledge', title: '知识库管理', icon: 'Collection' },
    { path: '/documents', title: '文档与切片', icon: 'Document' },
    { path: '/governance', title: '知识治理闭环', icon: 'DataAnalysis' }
];
const currentTitle = computed(() => route.meta?.title || 'TerraForge');
const subTitle = computed(() => {
    const map = {
        '/chat': 'Stage0-Stage7 全链路 RAG · 答案均来自知识库并标注出处',
        '/search': '混合检索（向量 + BM25 + RRF）与重排序结果透视',
        '/knowledge': '建设规范库 / 项目案例库 / 企业知识库三域管理',
        '/documents': '文档解析入库、工程元数据维护与切片查看',
        '/governance': '知识健康度、治理事项、知识盲区与运营报告'
    };
    return map[route.path] || '';
});
async function loadStats() {
    try {
        const res = await kbApi.stats();
        stats.value = res.data || {};
    }
    catch {
        /* 已由拦截器提示 */
    }
}
onMounted(async () => {
    try {
        const r = await fetch('/health');
        backendOk.value = r.ok;
    }
    catch {
        backendOk.value = false;
    }
    loadStats();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
const __VLS_0 = {}.ElContainer;
/** @type {[typeof __VLS_components.ElContainer, typeof __VLS_components.elContainer, typeof __VLS_components.ElContainer, typeof __VLS_components.elContainer, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "tf-layout" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "tf-layout" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_4 = {};
__VLS_3.slots.default;
const __VLS_5 = {}.ElAside;
/** @type {[typeof __VLS_components.ElAside, typeof __VLS_components.elAside, typeof __VLS_components.ElAside, typeof __VLS_components.elAside, ]} */ ;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent(__VLS_5, new __VLS_5({
    ...{ class: "tf-aside" },
    width: (__VLS_ctx.collapsed ? '64px' : '218px'),
}));
const __VLS_7 = __VLS_6({
    ...{ class: "tf-aside" },
    width: (__VLS_ctx.collapsed ? '64px' : '218px'),
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
__VLS_8.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tf-logo" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tf-logo-mark" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tf-logo-text" },
});
__VLS_asFunctionalDirective(__VLS_directives.vShow)(null, { ...__VLS_directiveBindingRestFields, value: (!__VLS_ctx.collapsed) }, null, null);
__VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
const __VLS_9 = {}.ElMenu;
/** @type {[typeof __VLS_components.ElMenu, typeof __VLS_components.elMenu, typeof __VLS_components.ElMenu, typeof __VLS_components.elMenu, ]} */ ;
// @ts-ignore
const __VLS_10 = __VLS_asFunctionalComponent(__VLS_9, new __VLS_9({
    ...{ 'onSelect': {} },
    ...{ class: "tf-menu" },
    defaultActive: (__VLS_ctx.route.path),
    collapse: (__VLS_ctx.collapsed),
    backgroundColor: "transparent",
    textColor: "#c3d0e2",
    activeTextColor: "#ffffff",
}));
const __VLS_11 = __VLS_10({
    ...{ 'onSelect': {} },
    ...{ class: "tf-menu" },
    defaultActive: (__VLS_ctx.route.path),
    collapse: (__VLS_ctx.collapsed),
    backgroundColor: "transparent",
    textColor: "#c3d0e2",
    activeTextColor: "#ffffff",
}, ...__VLS_functionalComponentArgsRest(__VLS_10));
let __VLS_13;
let __VLS_14;
let __VLS_15;
const __VLS_16 = {
    onSelect: ((i) => __VLS_ctx.router.push(i))
};
__VLS_12.slots.default;
for (const [m] of __VLS_getVForSourceType((__VLS_ctx.menus))) {
    const __VLS_17 = {}.ElMenuItem;
    /** @type {[typeof __VLS_components.ElMenuItem, typeof __VLS_components.elMenuItem, typeof __VLS_components.ElMenuItem, typeof __VLS_components.elMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_18 = __VLS_asFunctionalComponent(__VLS_17, new __VLS_17({
        key: (m.path),
        index: (m.path),
    }));
    const __VLS_19 = __VLS_18({
        key: (m.path),
        index: (m.path),
    }, ...__VLS_functionalComponentArgsRest(__VLS_18));
    __VLS_20.slots.default;
    const __VLS_21 = {}.ElIcon;
    /** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
    // @ts-ignore
    const __VLS_22 = __VLS_asFunctionalComponent(__VLS_21, new __VLS_21({}));
    const __VLS_23 = __VLS_22({}, ...__VLS_functionalComponentArgsRest(__VLS_22));
    __VLS_24.slots.default;
    const __VLS_25 = ((m.icon));
    // @ts-ignore
    const __VLS_26 = __VLS_asFunctionalComponent(__VLS_25, new __VLS_25({}));
    const __VLS_27 = __VLS_26({}, ...__VLS_functionalComponentArgsRest(__VLS_26));
    var __VLS_24;
    {
        const { title: __VLS_thisSlot } = __VLS_20.slots;
        (m.title);
    }
    var __VLS_20;
}
var __VLS_12;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tf-aside-footer" },
});
__VLS_asFunctionalDirective(__VLS_directives.vShow)(null, { ...__VLS_directiveBindingRestFields, value: (!__VLS_ctx.collapsed) }, null, null);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
(__VLS_ctx.stats.kb_count ?? '-');
(__VLS_ctx.stats.doc_count ?? '-');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
(__VLS_ctx.stats.chunk_count ?? '-');
var __VLS_8;
const __VLS_29 = {}.ElContainer;
/** @type {[typeof __VLS_components.ElContainer, typeof __VLS_components.elContainer, typeof __VLS_components.ElContainer, typeof __VLS_components.elContainer, ]} */ ;
// @ts-ignore
const __VLS_30 = __VLS_asFunctionalComponent(__VLS_29, new __VLS_29({}));
const __VLS_31 = __VLS_30({}, ...__VLS_functionalComponentArgsRest(__VLS_30));
__VLS_32.slots.default;
const __VLS_33 = {}.ElHeader;
/** @type {[typeof __VLS_components.ElHeader, typeof __VLS_components.elHeader, typeof __VLS_components.ElHeader, typeof __VLS_components.elHeader, ]} */ ;
// @ts-ignore
const __VLS_34 = __VLS_asFunctionalComponent(__VLS_33, new __VLS_33({
    ...{ class: "tf-header" },
}));
const __VLS_35 = __VLS_34({
    ...{ class: "tf-header" },
}, ...__VLS_functionalComponentArgsRest(__VLS_34));
__VLS_36.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ style: {} },
});
const __VLS_37 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_38 = __VLS_asFunctionalComponent(__VLS_37, new __VLS_37({
    ...{ 'onClick': {} },
    ...{ style: {} },
}));
const __VLS_39 = __VLS_38({
    ...{ 'onClick': {} },
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_38));
let __VLS_41;
let __VLS_42;
let __VLS_43;
const __VLS_44 = {
    onClick: (...[$event]) => {
        __VLS_ctx.collapsed = !__VLS_ctx.collapsed;
    }
};
__VLS_40.slots.default;
const __VLS_45 = ((__VLS_ctx.collapsed ? 'Expand' : 'Fold'));
// @ts-ignore
const __VLS_46 = __VLS_asFunctionalComponent(__VLS_45, new __VLS_45({}));
const __VLS_47 = __VLS_46({}, ...__VLS_functionalComponentArgsRest(__VLS_46));
var __VLS_40;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tf-header-title" },
});
(__VLS_ctx.currentTitle);
__VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
(__VLS_ctx.subTitle);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ style: {} },
});
if (__VLS_ctx.backendOk === true) {
    const __VLS_49 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_50 = __VLS_asFunctionalComponent(__VLS_49, new __VLS_49({
        type: "success",
        effect: "light",
        size: "small",
    }));
    const __VLS_51 = __VLS_50({
        type: "success",
        effect: "light",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_50));
    __VLS_52.slots.default;
    var __VLS_52;
}
else if (__VLS_ctx.backendOk === false) {
    const __VLS_53 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_54 = __VLS_asFunctionalComponent(__VLS_53, new __VLS_53({
        type: "danger",
        effect: "light",
        size: "small",
    }));
    const __VLS_55 = __VLS_54({
        type: "danger",
        effect: "light",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_54));
    __VLS_56.slots.default;
    var __VLS_56;
}
const __VLS_57 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_58 = __VLS_asFunctionalComponent(__VLS_57, new __VLS_57({
    ...{ 'onClick': {} },
    size: "small",
    text: true,
}));
const __VLS_59 = __VLS_58({
    ...{ 'onClick': {} },
    size: "small",
    text: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_58));
let __VLS_61;
let __VLS_62;
let __VLS_63;
const __VLS_64 = {
    onClick: (__VLS_ctx.loadStats)
};
__VLS_60.slots.default;
const __VLS_65 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_66 = __VLS_asFunctionalComponent(__VLS_65, new __VLS_65({}));
const __VLS_67 = __VLS_66({}, ...__VLS_functionalComponentArgsRest(__VLS_66));
__VLS_68.slots.default;
const __VLS_69 = {}.Refresh;
/** @type {[typeof __VLS_components.Refresh, ]} */ ;
// @ts-ignore
const __VLS_70 = __VLS_asFunctionalComponent(__VLS_69, new __VLS_69({}));
const __VLS_71 = __VLS_70({}, ...__VLS_functionalComponentArgsRest(__VLS_70));
var __VLS_68;
var __VLS_60;
const __VLS_73 = {}.ElLink;
/** @type {[typeof __VLS_components.ElLink, typeof __VLS_components.elLink, typeof __VLS_components.ElLink, typeof __VLS_components.elLink, ]} */ ;
// @ts-ignore
const __VLS_74 = __VLS_asFunctionalComponent(__VLS_73, new __VLS_73({
    href: "/docs",
    target: "_blank",
    type: "primary",
    underline: (false),
}));
const __VLS_75 = __VLS_74({
    href: "/docs",
    target: "_blank",
    type: "primary",
    underline: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_74));
__VLS_76.slots.default;
var __VLS_76;
var __VLS_36;
const __VLS_77 = {}.ElMain;
/** @type {[typeof __VLS_components.ElMain, typeof __VLS_components.elMain, typeof __VLS_components.ElMain, typeof __VLS_components.elMain, ]} */ ;
// @ts-ignore
const __VLS_78 = __VLS_asFunctionalComponent(__VLS_77, new __VLS_77({
    ...{ class: "tf-main" },
}));
const __VLS_79 = __VLS_78({
    ...{ class: "tf-main" },
}, ...__VLS_functionalComponentArgsRest(__VLS_78));
__VLS_80.slots.default;
const __VLS_81 = {}.RouterView;
/** @type {[typeof __VLS_components.RouterView, typeof __VLS_components.routerView, typeof __VLS_components.RouterView, typeof __VLS_components.routerView, ]} */ ;
// @ts-ignore
const __VLS_82 = __VLS_asFunctionalComponent(__VLS_81, new __VLS_81({}));
const __VLS_83 = __VLS_82({}, ...__VLS_functionalComponentArgsRest(__VLS_82));
{
    const { default: __VLS_thisSlot } = __VLS_84.slots;
    const [{ Component }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_85 = {}.KeepAlive;
    /** @type {[typeof __VLS_components.KeepAlive, typeof __VLS_components.keepAlive, typeof __VLS_components.KeepAlive, typeof __VLS_components.keepAlive, ]} */ ;
    // @ts-ignore
    const __VLS_86 = __VLS_asFunctionalComponent(__VLS_85, new __VLS_85({
        include: (['ChatView']),
    }));
    const __VLS_87 = __VLS_86({
        include: (['ChatView']),
    }, ...__VLS_functionalComponentArgsRest(__VLS_86));
    __VLS_88.slots.default;
    const __VLS_89 = ((Component));
    // @ts-ignore
    const __VLS_90 = __VLS_asFunctionalComponent(__VLS_89, new __VLS_89({}));
    const __VLS_91 = __VLS_90({}, ...__VLS_functionalComponentArgsRest(__VLS_90));
    var __VLS_88;
    __VLS_84.slots['' /* empty slot name completion */];
}
var __VLS_84;
var __VLS_80;
var __VLS_32;
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['tf-layout']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-aside']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-logo']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-logo-mark']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-logo-text']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-menu']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-aside-footer']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-header']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-header-title']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-main']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            route: route,
            router: router,
            collapsed: collapsed,
            backendOk: backendOk,
            stats: stats,
            menus: menus,
            currentTitle: currentTitle,
            subTitle: subTitle,
            loadStats: loadStats,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
