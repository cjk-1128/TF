/// <reference types="../../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
import { computed, nextTick, onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import MarkdownIt from 'markdown-it';
import { kbApi, ragApi } from '@/api';
import CitationList from '@/components/CitationList.vue';
import ConfidenceTag from '@/components/ConfidenceTag.vue';
import StageTimeline from '@/components/StageTimeline.vue';
import ChunkCard from '@/components/ChunkCard.vue';
export default await (async () => {
    const md = new MarkdownIt({ html: false, breaks: true, linkify: true });
    const kbs = ref([]);
    const conversations = ref([]);
    const conversationId = ref('');
    const messages = ref([]);
    const query = ref('');
    const sending = ref(false);
    const bodyRef = ref(null);
    const rightTab = ref('trace');
    const selectedKbs = ref([]);
    const selectedDomains = ref([]);
    const ctx = ref({ project_name: '', project_type: '', discipline: 'general', region: '' });
    const previewVisible = ref(false);
    const previewCitation = ref(null);
    const lastAssistant = computed(() => {
        for (let i = messages.value.length - 1; i >= 0; i--) {
            if (messages.value[i].role === 'assistant' && !messages.value[i].loading)
                return messages.value[i];
        }
        return null;
    });
    const domainOptions = [
        { value: 'standard', label: '建设规范库' },
        { value: 'case', label: '项目案例库' },
        { value: 'enterprise', label: '企业知识库' }
    ];
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
    const scenes = [
        {
            title: '工程规范智能查询',
            q: 'C60 混凝土冬期施工的养护时间和温度要求是什么？'
        },
        {
            title: '施工质量问题分析',
            q: '现浇楼板出现宽度 0.4mm 的裂缝，可能原因和处理措施有哪些？'
        },
        {
            title: '施工方案智能生成',
            q: '请生成一份深度 8m 的基坑支护监测方案要点，包含监测项目和报警值。'
        },
        {
            title: '工程案例经验检索',
            q: '有哪些类似的地铁车站深基坑变形超限处置案例可以参考？'
        }
    ];
    function renderAnswer(text) {
        const html = md.render(text || '');
        // 将 [1] [2] 形式的引用标记高亮
        return html.replace(/\[(\d{1,2})\]/g, '<span class="cite-ref">$1</span>');
    }
    async function scrollBottom() {
        await nextTick();
        if (bodyRef.value)
            bodyRef.value.scrollTop = bodyRef.value.scrollHeight;
    }
    async function loadKbs() {
        const res = await kbApi.list();
        kbs.value = res.data || [];
    }
    async function loadConversations() {
        const res = await ragApi.conversations({ page: 1, page_size: 30 });
        conversations.value = res.data?.items || [];
    }
    async function openConversation(id) {
        conversationId.value = id;
        const res = await ragApi.messages(id);
        messages.value = (res.data || []).map((m) => ({
            role: m.role,
            content: m.content,
            messageId: m.id,
            citations: m.citations || [],
            confidence: m.confidence,
            confidenceLevel: m.confidence_level,
            needReview: !!m.need_human_review,
            latencyMs: m.latency_ms
        }));
        scrollBottom();
    }
    function newConversation() {
        conversationId.value = '';
        messages.value = [];
    }
    async function removeConversation(id) {
        await ElMessageBox.confirm('确认删除该会话及其全部消息？', '提示', { type: 'warning' });
        await ragApi.removeConversation(id);
        if (conversationId.value === id)
            newConversation();
        loadConversations();
        ElMessage.success('已删除');
    }
    async function send(text) {
        const q = (text ?? query.value).trim();
        if (!q)
            return;
        if (sending.value)
            return;
        messages.value.push({ role: 'user', content: q });
        messages.value.push({ role: 'assistant', content: '', loading: true });
        query.value = '';
        sending.value = true;
        scrollBottom();
        try {
            const res = await ragApi.chat({
                query: q,
                conversation_id: conversationId.value || null,
                kb_ids: selectedKbs.value,
                domains: selectedDomains.value,
                context: ctx.value
            });
            const d = res.data;
            conversationId.value = d.conversation_id;
            messages.value.pop();
            messages.value.push({
                role: 'assistant',
                content: d.answer,
                messageId: d.message_id,
                citations: d.citations,
                intentLabel: d.intent_label,
                confidence: d.confidence,
                confidenceLevel: d.confidence_level,
                needReview: d.need_human_review,
                reviewHint: d.review_hint,
                latencyMs: d.latency_ms,
                traces: d.stage_traces,
                retrieved: d.retrieved
            });
            loadConversations();
        }
        catch (e) {
            messages.value.pop();
            messages.value.push({ role: 'assistant', content: '请求失败，请检查后端服务是否已启动。' });
        }
        finally {
            sending.value = false;
            scrollBottom();
        }
    }
    async function feedback(m, rating) {
        if (!m.messageId) {
            ElMessage.warning('该消息暂不支持反馈');
            return;
        }
        let reason = '';
        if (rating < 0) {
            try {
                const r = await ElMessageBox.prompt('请简述问题（如：引用条文过期、答非所问、缺少依据）', '需改进', {
                    inputPlaceholder: '选填'
                });
                reason = r.value || '';
            }
            catch {
                return;
            }
        }
        await ragApi.feedback({ message_id: m.messageId, rating, reason });
        m.rated = rating;
        ElMessage.success(rating > 0 ? '感谢反馈，已记录为有帮助' : '已记录，该问题将进入知识盲区分析');
    }
    function preview(c) {
        previewCitation.value = c;
        previewVisible.value = true;
    }
    function onKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) {
            e.preventDefault();
            send();
        }
    }
    onMounted(() => {
        loadKbs();
        loadConversations();
    });
    debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
    const __VLS_ctx = {};
    let __VLS_components;
    let __VLS_directives;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chat-wrap" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chat-left tf-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ style: {} },
    });
    const __VLS_0 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        ...{ 'onClick': {} },
        type: "primary",
        ...{ style: {} },
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onClick': {} },
        type: "primary",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_4;
    let __VLS_5;
    let __VLS_6;
    const __VLS_7 = {
        onClick: (__VLS_ctx.newConversation)
    };
    __VLS_3.slots.default;
    const __VLS_8 = {}.ElIcon;
    /** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({}));
    const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
    __VLS_11.slots.default;
    const __VLS_12 = {}.Plus;
    /** @type {[typeof __VLS_components.Plus, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
    const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
    var __VLS_11;
    var __VLS_3;
    const __VLS_16 = {}.ElScrollbar;
    /** @type {[typeof __VLS_components.ElScrollbar, typeof __VLS_components.elScrollbar, typeof __VLS_components.ElScrollbar, typeof __VLS_components.elScrollbar, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        ...{ style: {} },
    }));
    const __VLS_18 = __VLS_17({
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    __VLS_19.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ style: {} },
    });
    if (!__VLS_ctx.conversations.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "tf-muted" },
            ...{ style: {} },
        });
    }
    for (const [c] of __VLS_getVForSourceType((__VLS_ctx.conversations))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    __VLS_ctx.openConversation(c.id);
                } },
            key: (c.id),
            ...{ class: "conv-item" },
            ...{ class: ({ active: c.id === __VLS_ctx.conversationId }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "txt" },
        });
        (c.title);
        const __VLS_20 = {}.ElIcon;
        /** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
        // @ts-ignore
        const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
            ...{ 'onClick': {} },
            ...{ style: {} },
        }));
        const __VLS_22 = __VLS_21({
            ...{ 'onClick': {} },
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_21));
        let __VLS_24;
        let __VLS_25;
        let __VLS_26;
        const __VLS_27 = {
            onClick: (...[$event]) => {
                __VLS_ctx.removeConversation(c.id);
            }
        };
        __VLS_23.slots.default;
        const __VLS_28 = {}.Delete;
        /** @type {[typeof __VLS_components.Delete, ]} */ ;
        // @ts-ignore
        const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({}));
        const __VLS_30 = __VLS_29({}, ...__VLS_functionalComponentArgsRest(__VLS_29));
        var __VLS_23;
    }
    var __VLS_19;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tf-muted" },
        ...{ style: {} },
    });
    const __VLS_32 = {}.ElInput;
    /** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        modelValue: (__VLS_ctx.ctx.project_name),
        size: "small",
        placeholder: "项目名称",
        ...{ style: {} },
    }));
    const __VLS_34 = __VLS_33({
        modelValue: (__VLS_ctx.ctx.project_name),
        size: "small",
        placeholder: "项目名称",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    const __VLS_36 = {}.ElInput;
    /** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        modelValue: (__VLS_ctx.ctx.project_type),
        size: "small",
        placeholder: "项目类型，如地铁车站",
        ...{ style: {} },
    }));
    const __VLS_38 = __VLS_37({
        modelValue: (__VLS_ctx.ctx.project_type),
        size: "small",
        placeholder: "项目类型，如地铁车站",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    const __VLS_40 = {}.ElSelect;
    /** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        modelValue: (__VLS_ctx.ctx.discipline),
        size: "small",
        ...{ style: {} },
    }));
    const __VLS_42 = __VLS_41({
        modelValue: (__VLS_ctx.ctx.discipline),
        size: "small",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    __VLS_43.slots.default;
    for (const [d] of __VLS_getVForSourceType((__VLS_ctx.disciplineOptions))) {
        const __VLS_44 = {}.ElOption;
        /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
        // @ts-ignore
        const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
            key: (d.value),
            label: (d.label),
            value: (d.value),
        }));
        const __VLS_46 = __VLS_45({
            key: (d.value),
            label: (d.label),
            value: (d.value),
        }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    }
    var __VLS_43;
    const __VLS_48 = {}.ElInput;
    /** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        modelValue: (__VLS_ctx.ctx.region),
        size: "small",
        placeholder: "所在地区",
    }));
    const __VLS_50 = __VLS_49({
        modelValue: (__VLS_ctx.ctx.region),
        size: "small",
        placeholder: "所在地区",
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chat-center tf-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ref: "bodyRef",
        ...{ class: "chat-body" },
    });
    /** @type {typeof __VLS_ctx.bodyRef} */ ;
    if (!__VLS_ctx.messages.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "chat-empty" },
        });
        const __VLS_52 = {}.ElIcon;
        /** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
        // @ts-ignore
        const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
            ...{ style: {} },
        }));
        const __VLS_54 = __VLS_53({
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_53));
        __VLS_55.slots.default;
        const __VLS_56 = {}.ChatDotRound;
        /** @type {[typeof __VLS_components.ChatDotRound, ]} */ ;
        // @ts-ignore
        const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({}));
        const __VLS_58 = __VLS_57({}, ...__VLS_functionalComponentArgsRest(__VLS_57));
        var __VLS_55;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ style: {} },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "scene-cards" },
        });
        for (const [s] of __VLS_getVForSourceType((__VLS_ctx.scenes))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ onClick: (...[$event]) => {
                        if (!(!__VLS_ctx.messages.length))
                            return;
                        __VLS_ctx.send(s.q);
                    } },
                key: (s.title),
                ...{ class: "scene-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            (s.title);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "tf-muted" },
            });
            (s.q);
        }
    }
    for (const [m, i] of __VLS_getVForSourceType((__VLS_ctx.messages))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (i),
            ...{ class: "msg-row" },
            ...{ class: (m.role) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "msg-avatar" },
            ...{ class: (m.role === 'user' ? 'user' : 'bot') },
        });
        const __VLS_60 = {}.ElIcon;
        /** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
        // @ts-ignore
        const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({}));
        const __VLS_62 = __VLS_61({}, ...__VLS_functionalComponentArgsRest(__VLS_61));
        __VLS_63.slots.default;
        const __VLS_64 = ((m.role === 'user' ? 'User' : 'Cpu'));
        // @ts-ignore
        const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({}));
        const __VLS_66 = __VLS_65({}, ...__VLS_functionalComponentArgsRest(__VLS_65));
        var __VLS_63;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "msg-bubble" },
        });
        if (m.loading) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "tf-muted" },
            });
            const __VLS_68 = {}.ElProgress;
            /** @type {[typeof __VLS_components.ElProgress, typeof __VLS_components.elProgress, ]} */ ;
            // @ts-ignore
            const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
                percentage: (100),
                indeterminate: (true),
                showText: (false),
                ...{ style: {} },
            }));
            const __VLS_70 = __VLS_69({
                percentage: (100),
                indeterminate: (true),
                showText: (false),
                ...{ style: {} },
            }, ...__VLS_functionalComponentArgsRest(__VLS_69));
        }
        else if (m.role === 'user') {
            (m.content);
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "msg-meta" },
            });
            if (m.intentLabel) {
                const __VLS_72 = {}.ElTag;
                /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
                // @ts-ignore
                const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
                    size: "small",
                    effect: "plain",
                }));
                const __VLS_74 = __VLS_73({
                    size: "small",
                    effect: "plain",
                }, ...__VLS_functionalComponentArgsRest(__VLS_73));
                __VLS_75.slots.default;
                (m.intentLabel);
                var __VLS_75;
            }
            if (m.confidence !== undefined) {
                /** @type {[typeof ConfidenceTag, ]} */ ;
                // @ts-ignore
                const __VLS_76 = __VLS_asFunctionalComponent(ConfidenceTag, new ConfidenceTag({
                    value: (m.confidence),
                    level: (m.confidenceLevel),
                }));
                const __VLS_77 = __VLS_76({
                    value: (m.confidence),
                    level: (m.confidenceLevel),
                }, ...__VLS_functionalComponentArgsRest(__VLS_76));
            }
            if (m.latencyMs) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "tf-muted" },
                    ...{ style: {} },
                });
                (m.latencyMs);
            }
            if (m.needReview) {
                const __VLS_79 = {}.ElAlert;
                /** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
                // @ts-ignore
                const __VLS_80 = __VLS_asFunctionalComponent(__VLS_79, new __VLS_79({
                    type: "warning",
                    closable: (false),
                    showIcon: true,
                    title: (m.reviewHint || '本回答置信度较低，请由专业工程师复核后使用'),
                    ...{ style: {} },
                }));
                const __VLS_81 = __VLS_80({
                    type: "warning",
                    closable: (false),
                    showIcon: true,
                    title: (m.reviewHint || '本回答置信度较低，请由专业工程师复核后使用'),
                    ...{ style: {} },
                }, ...__VLS_functionalComponentArgsRest(__VLS_80));
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div)({
                ...{ class: "answer-md" },
            });
            __VLS_asFunctionalDirective(__VLS_directives.vHtml)(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.renderAnswer(m.content)) }, null, null);
            /** @type {[typeof CitationList, ]} */ ;
            // @ts-ignore
            const __VLS_83 = __VLS_asFunctionalComponent(CitationList, new CitationList({
                ...{ 'onPreview': {} },
                citations: (m.citations || []),
            }));
            const __VLS_84 = __VLS_83({
                ...{ 'onPreview': {} },
                citations: (m.citations || []),
            }, ...__VLS_functionalComponentArgsRest(__VLS_83));
            let __VLS_86;
            let __VLS_87;
            let __VLS_88;
            const __VLS_89 = {
                onPreview: (__VLS_ctx.preview)
            };
            var __VLS_85;
            if (m.messageId) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ style: {} },
                });
                const __VLS_90 = {}.ElButton;
                /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
                // @ts-ignore
                const __VLS_91 = __VLS_asFunctionalComponent(__VLS_90, new __VLS_90({
                    ...{ 'onClick': {} },
                    size: "small",
                    text: true,
                    type: (m.rated === 1 ? 'primary' : ''),
                }));
                const __VLS_92 = __VLS_91({
                    ...{ 'onClick': {} },
                    size: "small",
                    text: true,
                    type: (m.rated === 1 ? 'primary' : ''),
                }, ...__VLS_functionalComponentArgsRest(__VLS_91));
                let __VLS_94;
                let __VLS_95;
                let __VLS_96;
                const __VLS_97 = {
                    onClick: (...[$event]) => {
                        if (!!(m.loading))
                            return;
                        if (!!(m.role === 'user'))
                            return;
                        if (!(m.messageId))
                            return;
                        __VLS_ctx.feedback(m, 1);
                    }
                };
                __VLS_93.slots.default;
                const __VLS_98 = {}.ElIcon;
                /** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
                // @ts-ignore
                const __VLS_99 = __VLS_asFunctionalComponent(__VLS_98, new __VLS_98({}));
                const __VLS_100 = __VLS_99({}, ...__VLS_functionalComponentArgsRest(__VLS_99));
                __VLS_101.slots.default;
                const __VLS_102 = {}.Select;
                /** @type {[typeof __VLS_components.Select, ]} */ ;
                // @ts-ignore
                const __VLS_103 = __VLS_asFunctionalComponent(__VLS_102, new __VLS_102({}));
                const __VLS_104 = __VLS_103({}, ...__VLS_functionalComponentArgsRest(__VLS_103));
                var __VLS_101;
                var __VLS_93;
                const __VLS_106 = {}.ElButton;
                /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
                // @ts-ignore
                const __VLS_107 = __VLS_asFunctionalComponent(__VLS_106, new __VLS_106({
                    ...{ 'onClick': {} },
                    size: "small",
                    text: true,
                    type: (m.rated === -1 ? 'danger' : ''),
                }));
                const __VLS_108 = __VLS_107({
                    ...{ 'onClick': {} },
                    size: "small",
                    text: true,
                    type: (m.rated === -1 ? 'danger' : ''),
                }, ...__VLS_functionalComponentArgsRest(__VLS_107));
                let __VLS_110;
                let __VLS_111;
                let __VLS_112;
                const __VLS_113 = {
                    onClick: (...[$event]) => {
                        if (!!(m.loading))
                            return;
                        if (!!(m.role === 'user'))
                            return;
                        if (!(m.messageId))
                            return;
                        __VLS_ctx.feedback(m, -1);
                    }
                };
                __VLS_109.slots.default;
                const __VLS_114 = {}.ElIcon;
                /** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
                // @ts-ignore
                const __VLS_115 = __VLS_asFunctionalComponent(__VLS_114, new __VLS_114({}));
                const __VLS_116 = __VLS_115({}, ...__VLS_functionalComponentArgsRest(__VLS_115));
                __VLS_117.slots.default;
                const __VLS_118 = {}.CloseBold;
                /** @type {[typeof __VLS_components.CloseBold, ]} */ ;
                // @ts-ignore
                const __VLS_119 = __VLS_asFunctionalComponent(__VLS_118, new __VLS_118({}));
                const __VLS_120 = __VLS_119({}, ...__VLS_functionalComponentArgsRest(__VLS_119));
                var __VLS_117;
                var __VLS_109;
            }
        }
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chat-input" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chat-input-tools" },
    });
    const __VLS_122 = {}.ElSelect;
    /** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
    // @ts-ignore
    const __VLS_123 = __VLS_asFunctionalComponent(__VLS_122, new __VLS_122({
        modelValue: (__VLS_ctx.selectedKbs),
        multiple: true,
        collapseTags: true,
        collapseTagsTooltip: true,
        clearable: true,
        size: "small",
        placeholder: "全部知识库",
        ...{ style: {} },
    }));
    const __VLS_124 = __VLS_123({
        modelValue: (__VLS_ctx.selectedKbs),
        multiple: true,
        collapseTags: true,
        collapseTagsTooltip: true,
        clearable: true,
        size: "small",
        placeholder: "全部知识库",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_123));
    __VLS_125.slots.default;
    for (const [k] of __VLS_getVForSourceType((__VLS_ctx.kbs))) {
        const __VLS_126 = {}.ElOption;
        /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
        // @ts-ignore
        const __VLS_127 = __VLS_asFunctionalComponent(__VLS_126, new __VLS_126({
            key: (k.id),
            label: (k.name),
            value: (k.id),
        }));
        const __VLS_128 = __VLS_127({
            key: (k.id),
            label: (k.name),
            value: (k.id),
        }, ...__VLS_functionalComponentArgsRest(__VLS_127));
    }
    var __VLS_125;
    const __VLS_130 = {}.ElSelect;
    /** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
    // @ts-ignore
    const __VLS_131 = __VLS_asFunctionalComponent(__VLS_130, new __VLS_130({
        modelValue: (__VLS_ctx.selectedDomains),
        multiple: true,
        collapseTags: true,
        clearable: true,
        size: "small",
        placeholder: "全部知识域",
        ...{ style: {} },
    }));
    const __VLS_132 = __VLS_131({
        modelValue: (__VLS_ctx.selectedDomains),
        multiple: true,
        collapseTags: true,
        clearable: true,
        size: "small",
        placeholder: "全部知识域",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_131));
    __VLS_133.slots.default;
    for (const [d] of __VLS_getVForSourceType((__VLS_ctx.domainOptions))) {
        const __VLS_134 = {}.ElOption;
        /** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
        // @ts-ignore
        const __VLS_135 = __VLS_asFunctionalComponent(__VLS_134, new __VLS_134({
            key: (d.value),
            label: (d.label),
            value: (d.value),
        }));
        const __VLS_136 = __VLS_135({
            key: (d.value),
            label: (d.label),
            value: (d.value),
        }, ...__VLS_functionalComponentArgsRest(__VLS_135));
    }
    var __VLS_133;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "tf-muted" },
        ...{ style: {} },
    });
    const __VLS_138 = {}.ElInput;
    /** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
    // @ts-ignore
    const __VLS_139 = __VLS_asFunctionalComponent(__VLS_138, new __VLS_138({
        ...{ 'onKeydown': {} },
        modelValue: (__VLS_ctx.query),
        type: "textarea",
        rows: (3),
        resize: "none",
        placeholder: "请输入工程问题，例如：地下室外墙防水混凝土的抗渗等级如何确定？",
    }));
    const __VLS_140 = __VLS_139({
        ...{ 'onKeydown': {} },
        modelValue: (__VLS_ctx.query),
        type: "textarea",
        rows: (3),
        resize: "none",
        placeholder: "请输入工程问题，例如：地下室外墙防水混凝土的抗渗等级如何确定？",
    }, ...__VLS_functionalComponentArgsRest(__VLS_139));
    let __VLS_142;
    let __VLS_143;
    let __VLS_144;
    const __VLS_145 = {
        onKeydown: (__VLS_ctx.onKeydown)
    };
    var __VLS_141;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chat-input-actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "tf-muted" },
        ...{ style: {} },
    });
    const __VLS_146 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_147 = __VLS_asFunctionalComponent(__VLS_146, new __VLS_146({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.sending),
    }));
    const __VLS_148 = __VLS_147({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.sending),
    }, ...__VLS_functionalComponentArgsRest(__VLS_147));
    let __VLS_150;
    let __VLS_151;
    let __VLS_152;
    const __VLS_153 = {
        onClick: (...[$event]) => {
            __VLS_ctx.send();
        }
    };
    __VLS_149.slots.default;
    const __VLS_154 = {}.ElIcon;
    /** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
    // @ts-ignore
    const __VLS_155 = __VLS_asFunctionalComponent(__VLS_154, new __VLS_154({
        ...{ class: "el-icon--right" },
    }));
    const __VLS_156 = __VLS_155({
        ...{ class: "el-icon--right" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_155));
    __VLS_157.slots.default;
    const __VLS_158 = {}.Promotion;
    /** @type {[typeof __VLS_components.Promotion, ]} */ ;
    // @ts-ignore
    const __VLS_159 = __VLS_asFunctionalComponent(__VLS_158, new __VLS_158({}));
    const __VLS_160 = __VLS_159({}, ...__VLS_functionalComponentArgsRest(__VLS_159));
    var __VLS_157;
    var __VLS_149;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chat-right tf-card" },
        ...{ style: {} },
    });
    const __VLS_162 = {}.ElTabs;
    /** @type {[typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, typeof __VLS_components.ElTabs, typeof __VLS_components.elTabs, ]} */ ;
    // @ts-ignore
    const __VLS_163 = __VLS_asFunctionalComponent(__VLS_162, new __VLS_162({
        modelValue: (__VLS_ctx.rightTab),
    }));
    const __VLS_164 = __VLS_163({
        modelValue: (__VLS_ctx.rightTab),
    }, ...__VLS_functionalComponentArgsRest(__VLS_163));
    __VLS_165.slots.default;
    const __VLS_166 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_167 = __VLS_asFunctionalComponent(__VLS_166, new __VLS_166({
        label: "执行链路",
        name: "trace",
    }));
    const __VLS_168 = __VLS_167({
        label: "执行链路",
        name: "trace",
    }, ...__VLS_functionalComponentArgsRest(__VLS_167));
    __VLS_169.slots.default;
    /** @type {[typeof StageTimeline, ]} */ ;
    // @ts-ignore
    const __VLS_170 = __VLS_asFunctionalComponent(StageTimeline, new StageTimeline({
        traces: (__VLS_ctx.lastAssistant?.traces || []),
    }));
    const __VLS_171 = __VLS_170({
        traces: (__VLS_ctx.lastAssistant?.traces || []),
    }, ...__VLS_functionalComponentArgsRest(__VLS_170));
    var __VLS_169;
    const __VLS_173 = {}.ElTabPane;
    /** @type {[typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, typeof __VLS_components.ElTabPane, typeof __VLS_components.elTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_174 = __VLS_asFunctionalComponent(__VLS_173, new __VLS_173({
        label: (`召回片段 (${__VLS_ctx.lastAssistant?.retrieved?.length || 0})`),
        name: "chunks",
    }));
    const __VLS_175 = __VLS_174({
        label: (`召回片段 (${__VLS_ctx.lastAssistant?.retrieved?.length || 0})`),
        name: "chunks",
    }, ...__VLS_functionalComponentArgsRest(__VLS_174));
    __VLS_176.slots.default;
    if (!__VLS_ctx.lastAssistant?.retrieved?.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "tf-muted" },
            ...{ style: {} },
        });
    }
    for (const [c, i] of __VLS_getVForSourceType((__VLS_ctx.lastAssistant?.retrieved || []))) {
        /** @type {[typeof ChunkCard, ]} */ ;
        // @ts-ignore
        const __VLS_177 = __VLS_asFunctionalComponent(ChunkCard, new ChunkCard({
            key: (c.chunk_id),
            chunk: (c),
            rank: (i + 1),
        }));
        const __VLS_178 = __VLS_177({
            key: (c.chunk_id),
            chunk: (c),
            rank: (i + 1),
        }, ...__VLS_functionalComponentArgsRest(__VLS_177));
    }
    var __VLS_176;
    var __VLS_165;
    const __VLS_180 = {}.ElDrawer;
    /** @type {[typeof __VLS_components.ElDrawer, typeof __VLS_components.elDrawer, typeof __VLS_components.ElDrawer, typeof __VLS_components.elDrawer, ]} */ ;
    // @ts-ignore
    const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
        modelValue: (__VLS_ctx.previewVisible),
        title: "引用原文",
        size: "520px",
    }));
    const __VLS_182 = __VLS_181({
        modelValue: (__VLS_ctx.previewVisible),
        title: "引用原文",
        size: "520px",
    }, ...__VLS_functionalComponentArgsRest(__VLS_181));
    __VLS_183.slots.default;
    if (__VLS_ctx.previewCitation) {
        const __VLS_184 = {}.ElDescriptions;
        /** @type {[typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, ]} */ ;
        // @ts-ignore
        const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
            column: (1),
            border: true,
            size: "small",
        }));
        const __VLS_186 = __VLS_185({
            column: (1),
            border: true,
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_185));
        __VLS_187.slots.default;
        const __VLS_188 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
            label: "文档",
        }));
        const __VLS_190 = __VLS_189({
            label: "文档",
        }, ...__VLS_functionalComponentArgsRest(__VLS_189));
        __VLS_191.slots.default;
        (__VLS_ctx.previewCitation.doc_title);
        var __VLS_191;
        if (__VLS_ctx.previewCitation.standard_code) {
            const __VLS_192 = {}.ElDescriptionsItem;
            /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
            // @ts-ignore
            const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
                label: "标准编号",
            }));
            const __VLS_194 = __VLS_193({
                label: "标准编号",
            }, ...__VLS_functionalComponentArgsRest(__VLS_193));
            __VLS_195.slots.default;
            (__VLS_ctx.previewCitation.standard_code);
            var __VLS_195;
        }
        if (__VLS_ctx.previewCitation.clause_no) {
            const __VLS_196 = {}.ElDescriptionsItem;
            /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
            // @ts-ignore
            const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
                label: "条文号",
            }));
            const __VLS_198 = __VLS_197({
                label: "条文号",
            }, ...__VLS_functionalComponentArgsRest(__VLS_197));
            __VLS_199.slots.default;
            (__VLS_ctx.previewCitation.clause_no);
            var __VLS_199;
        }
        if (__VLS_ctx.previewCitation.section_path) {
            const __VLS_200 = {}.ElDescriptionsItem;
            /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
            // @ts-ignore
            const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
                label: "章节路径",
            }));
            const __VLS_202 = __VLS_201({
                label: "章节路径",
            }, ...__VLS_functionalComponentArgsRest(__VLS_201));
            __VLS_203.slots.default;
            (__VLS_ctx.previewCitation.section_path);
            var __VLS_203;
        }
        const __VLS_204 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
            label: "相关度",
        }));
        const __VLS_206 = __VLS_205({
            label: "相关度",
        }, ...__VLS_functionalComponentArgsRest(__VLS_205));
        __VLS_207.slots.default;
        ((__VLS_ctx.previewCitation.score * 100).toFixed(1));
        var __VLS_207;
        var __VLS_187;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "chunk-card" },
            ...{ style: {} },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "content" },
        });
        (__VLS_ctx.previewCitation.snippet);
    }
    var __VLS_183;
    /** @type {__VLS_StyleScopedClasses['chat-wrap']} */ ;
    /** @type {__VLS_StyleScopedClasses['chat-left']} */ ;
    /** @type {__VLS_StyleScopedClasses['tf-card']} */ ;
    /** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
    /** @type {__VLS_StyleScopedClasses['conv-item']} */ ;
    /** @type {__VLS_StyleScopedClasses['txt']} */ ;
    /** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
    /** @type {__VLS_StyleScopedClasses['chat-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['tf-card']} */ ;
    /** @type {__VLS_StyleScopedClasses['chat-body']} */ ;
    /** @type {__VLS_StyleScopedClasses['chat-empty']} */ ;
    /** @type {__VLS_StyleScopedClasses['scene-cards']} */ ;
    /** @type {__VLS_StyleScopedClasses['scene-card']} */ ;
    /** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
    /** @type {__VLS_StyleScopedClasses['msg-row']} */ ;
    /** @type {__VLS_StyleScopedClasses['msg-avatar']} */ ;
    /** @type {__VLS_StyleScopedClasses['msg-bubble']} */ ;
    /** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
    /** @type {__VLS_StyleScopedClasses['msg-meta']} */ ;
    /** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
    /** @type {__VLS_StyleScopedClasses['answer-md']} */ ;
    /** @type {__VLS_StyleScopedClasses['chat-input']} */ ;
    /** @type {__VLS_StyleScopedClasses['chat-input-tools']} */ ;
    /** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
    /** @type {__VLS_StyleScopedClasses['chat-input-actions']} */ ;
    /** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
    /** @type {__VLS_StyleScopedClasses['el-icon--right']} */ ;
    /** @type {__VLS_StyleScopedClasses['chat-right']} */ ;
    /** @type {__VLS_StyleScopedClasses['tf-card']} */ ;
    /** @type {__VLS_StyleScopedClasses['tf-muted']} */ ;
    /** @type {__VLS_StyleScopedClasses['chunk-card']} */ ;
    /** @type {__VLS_StyleScopedClasses['content']} */ ;
    var __VLS_dollars;
    const __VLS_self = (await import('vue')).defineComponent({
        setup() {
            return {
                CitationList: CitationList,
                ConfidenceTag: ConfidenceTag,
                StageTimeline: StageTimeline,
                ChunkCard: ChunkCard,
                kbs: kbs,
                conversations: conversations,
                conversationId: conversationId,
                messages: messages,
                query: query,
                sending: sending,
                bodyRef: bodyRef,
                rightTab: rightTab,
                selectedKbs: selectedKbs,
                selectedDomains: selectedDomains,
                ctx: ctx,
                previewVisible: previewVisible,
                previewCitation: previewCitation,
                lastAssistant: lastAssistant,
                domainOptions: domainOptions,
                disciplineOptions: disciplineOptions,
                scenes: scenes,
                renderAnswer: renderAnswer,
                openConversation: openConversation,
                newConversation: newConversation,
                removeConversation: removeConversation,
                send: send,
                feedback: feedback,
                preview: preview,
                onKeydown: onKeydown,
            };
        },
        name: 'ChatView'
    });
    return (await import('vue')).defineComponent({
        setup() {
            return {};
        },
        name: 'ChatView'
    });
})(); /* PartiallyEnd: #4569/main.vue */
