/// <reference types="../../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
import { computed } from 'vue';
const props = defineProps();
const type = computed(() => {
    if (props.value >= 0.75)
        return 'success';
    if (props.value >= 0.45)
        return 'warning';
    return 'danger';
});
const label = computed(() => {
    if (props.level === 'high' || props.value >= 0.75)
        return '高置信';
    if (props.level === 'medium' || props.value >= 0.45)
        return '中置信';
    return '低置信';
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
const __VLS_0 = {}.ElTooltip;
/** @type {[typeof __VLS_components.ElTooltip, typeof __VLS_components.elTooltip, typeof __VLS_components.ElTooltip, typeof __VLS_components.elTooltip, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    placement: "top",
    content: (`置信度综合了检索相关性、引用覆盖、来源权威性与一致性等信号；低于 0.45 时建议人工复核`),
}));
const __VLS_2 = __VLS_1({
    placement: "top",
    content: (`置信度综合了检索相关性、引用覆盖、来源权威性与一致性等信号；低于 0.45 时建议人工复核`),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_4 = {};
__VLS_3.slots.default;
const __VLS_5 = {}.ElTag;
/** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent(__VLS_5, new __VLS_5({
    type: (__VLS_ctx.type),
    size: "small",
    effect: "light",
}));
const __VLS_7 = __VLS_6({
    type: (__VLS_ctx.type),
    size: "small",
    effect: "light",
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
__VLS_8.slots.default;
(__VLS_ctx.label);
((__VLS_ctx.value * 100).toFixed(0));
var __VLS_8;
var __VLS_3;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            type: type,
            label: label,
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
