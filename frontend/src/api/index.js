import axios from 'axios';
import { ElMessage } from 'element-plus';
const http = axios.create({ baseURL: '/api/v1', timeout: 120000 });
http.interceptors.response.use((res) => res.data, (err) => {
    const msg = err.response?.data?.message || err.message || '请求失败';
    ElMessage.error(msg);
    return Promise.reject(err);
});
// ---------------- 知识库 ----------------
export const kbApi = {
    list: (params) => http.get('/knowledge/kb', { params }),
    create: (data) => http.post('/knowledge/kb', data),
    update: (id, data) => http.put(`/knowledge/kb/${id}`, data),
    remove: (id) => http.delete(`/knowledge/kb/${id}`),
    stats: () => http.get('/knowledge/stats')
};
// ---------------- 文档 ----------------
export const docApi = {
    list: (params) => http.get('/knowledge/documents', { params }),
    upload: (kbId, files, meta = {}) => {
        const fd = new FormData();
        fd.append('kb_id', kbId);
        fd.append('meta', JSON.stringify(meta));
        files.forEach((f) => fd.append('files', f));
        return http.post('/knowledge/documents/upload', fd, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
    },
    ingestText: (data) => http.post('/knowledge/documents/text', data),
    update: (id, data) => http.put(`/knowledge/documents/${id}`, data),
    remove: (id) => http.delete(`/knowledge/documents/${id}`),
    reindex: (id) => http.post(`/knowledge/documents/${id}/reindex`),
    chunks: (id, params) => http.get(`/knowledge/documents/${id}/chunks`, { params })
};
// ---------------- 问答 ----------------
export const ragApi = {
    chat: (data) => http.post('/rag/chat', data),
    search: (data) => http.post('/rag/search', data),
    conversations: (params) => http.get('/rag/conversations', { params }),
    messages: (id) => http.get(`/rag/conversations/${id}/messages`),
    removeConversation: (id) => http.delete(`/rag/conversations/${id}`),
    feedback: (data) => http.post('/rag/feedback', data),
    explain: (data) => http.post('/rag/explain', data),
    diagnose: (data) => http.post('/rag/diagnose', data)
};
// ---------------- 治理 ----------------
export const govApi = {
    healthReport: (kbId) => http.get('/governance/health-report', { params: { kb_id: kbId } }),
    tasks: (params) => http.get('/governance/tasks', { params }),
    createTask: (data) => http.post('/governance/tasks', data),
    autoGenerate: (kbId, assignee = '') => http.post('/governance/tasks/auto-generate', null, {
        params: { kb_id: kbId, assignee }
    }),
    updateTask: (id, data) => http.put(`/governance/tasks/${id}`, data),
    gaps: (days = 30) => http.get('/governance/knowledge-gaps', { params: { days } }),
    operationReport: (days = 7) => http.get('/governance/operation-report', { params: { days } })
};
// ---------------- 评测 ----------------
export const evalApi = {
    run: (apiKey, data) => http.post('/eval/run', data || {}, { headers: { 'X-API-Key': apiKey } }),
    golden: (apiKey) => http.get('/eval/golden', { headers: { 'X-API-Key': apiKey } }),
    addGolden: (apiKey, data) => http.post('/eval/golden', data, { headers: { 'X-API-Key': apiKey } }),
    deleteGolden: (apiKey, id) => http.delete(`/eval/golden/${id}`, { headers: { 'X-API-Key': apiKey } }),
    runs: (apiKey, params) => http.get('/eval/runs', { params, headers: { 'X-API-Key': apiKey } }),
    runDetail: (apiKey, id) => http.get(`/eval/runs/${id}`, { headers: { 'X-API-Key': apiKey } }),
    deleteRun: (apiKey, id) => http.delete(`/eval/runs/${id}`, { headers: { 'X-API-Key': apiKey } }),
    trend: (apiKey, params) => http.get('/eval/trend', { params, headers: { 'X-API-Key': apiKey } })
};
// ---------------- 质量巡检 ----------------
export const qualityApi = {
    inspect: (apiKey, data) => http.post('/quality/inspect', data, { headers: { 'X-API-Key': apiKey } }),
    reports: (apiKey, params) => http.get('/quality/reports', { params, headers: { 'X-API-Key': apiKey } }),
    report: (apiKey, id) => http.get(`/quality/reports/${id}`, { headers: { 'X-API-Key': apiKey } }),
    convert: (apiKey, data) => http.post('/quality/issues/convert', data, { headers: { 'X-API-Key': apiKey } }),
    triggerSchedule: (apiKey, data) => http.post('/quality/schedule/trigger', data || {}, { headers: { 'X-API-Key': apiKey } }),
    alerts: (apiKey, params) => http.get('/quality/alerts', { params, headers: { 'X-API-Key': apiKey } }),
    alertDetail: (apiKey, id) => http.get(`/quality/alerts/${id}`, { headers: { 'X-API-Key': apiKey } }),
    resolveAlert: (apiKey, id, note) => http.post(`/quality/alerts/${id}/resolve`, { note: note || '' }, { headers: { 'X-API-Key': apiKey } }),
    deleteAlert: (apiKey, id) => http.delete(`/quality/alerts/${id}`, { headers: { 'X-API-Key': apiKey } }),
    scoreTrend: (apiKey, params) => http.get('/quality/score-trend', { params, headers: { 'X-API-Key': apiKey } })
};
export default http;
