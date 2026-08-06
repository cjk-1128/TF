/// <reference types="../../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
const __VLS_props = defineProps();
function fmt(detail) {
    if (!detail)
        return '';
    return Object.entries(detail)
        .map(([k, v]) => {
        let val;
        if (Array.isArray(v))
            val = v.slice(0, 4).join('、') || '-';
        else if (typeof v === 'object' && v !== null)
            val = JSON.stringify(v);
        else
            val = String(v);
        if (val.length > 90)
            val = val.slice(0, 90) + '…';
        return `${k}: ${val}`;
    })
        .join('　|　');
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
if (!__VLS_ctx.traces || !__VLS_ctx.traces.length) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tf-muted" },
        ...{ style: {} },
    });
}
for (const [t] of __VLS_getVForSourceType((__VLS_ctx.traces))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (t.stage),
        ...{ class: "stage-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stage-head" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (t.stage.toUpperCase());
    (t.name);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "tf-muted" },
        ...{ style: {} },
    });
    (t.elapsed_ms);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stage-detail" },
    });
    (__VLS_ctx.fmt(t.detail));
}
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['stage-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stage-head']} */ ;
/** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['stage-detail']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            fmt: fmt,
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
