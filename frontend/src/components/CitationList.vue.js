/// <reference types="../../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
const __VLS_props = defineProps();
const emit = defineEmits();
const domainLabel = {
    standard: '建设规范',
    case: '项目案例',
    enterprise: '企业知识'
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
if (__VLS_ctx.citations && __VLS_ctx.citations.length) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "cite-list" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tf-muted" },
        ...{ style: {} },
    });
    (__VLS_ctx.citations.length);
    for (const [c] of __VLS_getVForSourceType((__VLS_ctx.citations))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.citations && __VLS_ctx.citations.length))
                        return;
                    __VLS_ctx.emit('preview', c);
                } },
            key: (c.index_no + c.chunk_id),
            ...{ class: "cite-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "cite-no" },
        });
        (c.index_no);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ style: {} },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "cite-title" },
        });
        (c.standard_code ? `《${c.standard_code}》 ` : '');
        (c.doc_title);
        const __VLS_0 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
            size: "small",
            effect: "plain",
            ...{ style: {} },
        }));
        const __VLS_2 = __VLS_1({
            size: "small",
            effect: "plain",
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_1));
        __VLS_3.slots.default;
        (__VLS_ctx.domainLabel[c.domain] || c.domain);
        var __VLS_3;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "cite-path" },
        });
        if (c.clause_no) {
            (c.clause_no);
        }
        if (c.section_path) {
            (c.section_path);
        }
        if (c.page_no) {
            (c.page_no);
        }
        ((c.score * 100).toFixed(0));
    }
}
/** @type {__VLS_StyleScopedClasses['cite-list']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['cite-item']} */ ;
/** @type {__VLS_StyleScopedClasses['cite-no']} */ ;
/** @type {__VLS_StyleScopedClasses['cite-title']} */ ;
/** @type {__VLS_StyleScopedClasses['cite-path']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            emit: emit,
            domainLabel: domainLabel,
        };
    },
    __typeEmits: {},
    __typeProps: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
