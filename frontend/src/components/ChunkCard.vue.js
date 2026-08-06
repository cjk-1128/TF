/// <reference types="../../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
const __VLS_props = defineProps();
const domainLabel = {
    standard: '建设规范',
    case: '项目案例',
    enterprise: '企业知识'
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "chunk-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "head" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
if (__VLS_ctx.rank) {
    const __VLS_0 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        size: "small",
        type: "info",
        effect: "plain",
    }));
    const __VLS_2 = __VLS_1({
        size: "small",
        type: "info",
        effect: "plain",
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    __VLS_3.slots.default;
    (__VLS_ctx.rank);
    var __VLS_3;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({
    ...{ style: {} },
});
(__VLS_ctx.chunk.standard_code ? `《${__VLS_ctx.chunk.standard_code}》` : __VLS_ctx.chunk.doc_title);
if (__VLS_ctx.chunk.clause_no) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ style: {} },
    });
    (__VLS_ctx.chunk.clause_no);
}
if (__VLS_ctx.chunk.is_mandatory) {
    const __VLS_4 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
        size: "small",
        type: "danger",
        effect: "light",
        ...{ style: {} },
    }));
    const __VLS_6 = __VLS_5({
        size: "small",
        type: "danger",
        effect: "light",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_5));
    __VLS_7.slots.default;
    var __VLS_7;
}
const __VLS_8 = {}.ElTag;
/** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    size: "small",
    effect: "plain",
}));
const __VLS_10 = __VLS_9({
    size: "small",
    effect: "plain",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
(__VLS_ctx.domainLabel[__VLS_ctx.chunk.domain] || __VLS_ctx.chunk.domain);
var __VLS_11;
if (__VLS_ctx.chunk.section_path) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tf-muted" },
        ...{ style: {} },
    });
    (__VLS_ctx.chunk.section_path);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "content" },
});
(__VLS_ctx.chunk.content);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ style: {} },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "score-bar" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i)({
    ...{ style: ({ width: Math.min(100, __VLS_ctx.chunk.final_score * 100) + '%' }) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tf-muted" },
    ...{ style: {} },
});
(__VLS_ctx.chunk.final_score.toFixed(3));
(__VLS_ctx.chunk.vector_score.toFixed(3));
(__VLS_ctx.chunk.bm25_score.toFixed(3));
(__VLS_ctx.chunk.fusion_score.toFixed(3));
(__VLS_ctx.chunk.rerank_score.toFixed(3));
/** @type {__VLS_StyleScopedClasses['chunk-card']} */ ;
/** @type {__VLS_StyleScopedClasses['head']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['content']} */ ;
/** @type {__VLS_StyleScopedClasses['score-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            domainLabel: domainLabel,
        };
    },
    __typeProps: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
