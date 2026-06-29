import { useState, useEffect } from 'react';
import { getAuditLogs, type AuditLogInfo } from '../api/admin';

const ACTION_LABEL: Record<string, string> = {
  login: '登录', logout: '登出', upload: '上传合同',
  review: 'AI 初审', stance_change: '切换立场',
  decision: '复审决定', accept: '接受条款', reject: '拒绝条款',
  undo_decision: '撤销决定', annotate: '添加批注',
  apply: '应用建议', revert_apply: '撤销应用',
  finalize: '完成复核', complete: '完成复核',
  export_report: '导出审查报告', export_revised: '导出修订稿',
  user_change: '切换岗位', model_config: '更新模型配置',
  config_change: '系统配置变更',
  user_create: '新建用户', user_update: '更新用户',
};

const ACTION_OPTS: { value: string; label: string }[] = [
  { value: 'login', label: '登录' },
  { value: 'upload', label: '上传合同' },
  { value: 'review', label: 'AI 初审' },
  { value: 'decision', label: '复审决定' },
  { value: 'annotate', label: '添加批注' },
  { value: 'finalize', label: '完成复核' },
  { value: 'export_revised', label: '导出修订稿' },
  { value: 'user_change', label: '切换岗位' },
];

export default function AuditLogPage() {
  const [items, setItems] = useState<AuditLogInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [action, setAction] = useState('');

  useEffect(() => {
    const params: Record<string, string> = { page: String(page), size: '30' };
    if (action) params.action = action;
    getAuditLogs(params).then(res => { setItems(res.items); setTotal(res.total); }).catch(() => {});
  }, [page, action]);

  return (
    <div className="admin-page">
      <h1>审计日志</h1>
      <div className="list-tools" style={{ marginBottom: 16 }}>
        <select className="filter" value={action} onChange={e => { setAction(e.target.value); setPage(1); }}>
          <option value="">全部操作</option>
          {ACTION_OPTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <span style={{ fontSize: 12, color: 'var(--ink-soft)' }}>共 {total} 条记录</span>
      </div>
      <table className="ctable">
        <thead>
          <tr><th>时间</th><th>用户</th><th>岗位</th><th>操作</th><th>对象</th><th>IP</th></tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr><td colSpan={6} className="empty">暂无记录</td></tr>
          ) : items.map(a => (
            <tr key={a.id}>
              <td style={{ whiteSpace: 'nowrap' }}>{new Date(a.created_at).toLocaleString('zh-CN')}</td>
              <td>{a.username || a.user_post || '-'}</td>
              <td>{a.user_post || '-'}</td>
              <td><span className="type-badge">{ACTION_LABEL[a.action] || a.action}</span></td>
              <td>{a.target_label || '-'}</td>
              <td style={{ fontVariantNumeric: 'tabular-nums' }}>{a.ip || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {total > 30 && (
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 16 }}>
          <button className="ca-btn" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</button>
          <span style={{ padding: '8px 12px', fontSize: 13 }}>第 {page} 页</span>
          <button className="ca-btn" disabled={page * 30 >= total} onClick={() => setPage(p => p + 1)}>下一页</button>
        </div>
      )}
    </div>
  );
}
