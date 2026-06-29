import { useEffect, useState, useMemo } from 'react';
import { getChangeLogs, downloadVersionSource, type ChangeLogInfo } from '../api/contracts';

const PAGE_SIZE = 3;

const CHANGE_TYPE: Record<string, string> = {
  upload: '上传', diff: '版本比对', accept: '接受', reject: '拒绝',
  annotate: '批注', apply: '一键应用', return: '退回', finalize: '定稿',
  review: 'AI 初审', stance: '切换立场', export_revised: '导出修订稿',
  export_report: '导出报告',
};

function fmt(s: string) {
  if (!s) return '-';
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

export default function ChangeLogModal({
  contractId, contractName, contractNo, versionNo, onClose,
}: {
  contractId: number; contractName: string; contractNo: string;
  versionNo: number; onClose: () => void;
}) {
  const [logs, setLogs] = useState<ChangeLogInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [pages, setPages] = useState<Record<string, number>>({});

  useEffect(() => {
    let alive = true;
    getChangeLogs(contractId).then(list => {
      if (!alive) return;
      setLogs(list);
      // 默认展开最新版本
      const vers = [...new Set(list.map(l => l.version_no))];
      if (vers.length) {
        const top = vers[0];
        setExpanded({ [top]: true });
      }
    }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [contractId]);

  const grouped = useMemo(() => {
    const map = new Map<number, ChangeLogInfo[]>();
    for (const l of logs) {
      const arr = map.get(l.version_no) || [];
      arr.push(l);
      map.set(l.version_no, arr);
    }
    return Array.from(map.entries()).sort((a, b) => Number(b[0]) - Number(a[0]));
  }, [logs]);

  const setPage = (v: number, p: number) => setPages(s => ({ ...s, [v]: p }));
  const toggle = (v: number) => setExpanded(s => ({ ...s, [v]: !s[v] }));

  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal chlog-modal" onClick={e => e.stopPropagation()}>
        <h3>全部版本变更记录</h3>
        <p className="lead">
          编号 {contractNo || '—'}　·　当前 v{versionNo}　·　共 {grouped.length} 个版本
        </p>
        <div style={{ fontFamily: "'Noto Serif SC',serif", fontWeight: 600, color: 'var(--navy)', fontSize: 15 }}>
          {contractName}
        </div>
        <div className="chlog-scroll">
          {loading ? (
            <div className="empty" style={{ padding: '24px 0', textAlign: 'center', color: 'var(--ink-soft)' }}>
              <span className="spinner" /> 加载中…
            </div>
          ) : grouped.length === 0 ? (
            <div className="empty" style={{ padding: '24px 0', textAlign: 'center', color: 'var(--ink-soft)' }}>
              暂无变更记录
            </div>
          ) : grouped.map(([v, items]) => {
            const open = !!expanded[v];
            const totalPages = Math.ceil(items.length / PAGE_SIZE);
            const page = Math.min(pages[v] || 1, totalPages) || 1;
            const start = (page - 1) * PAGE_SIZE;
            const pageItems = items.slice(start, start + PAGE_SIZE);
            const from = (page - 1) * PAGE_SIZE + 1;
            const to = Math.min(page * PAGE_SIZE, items.length);
            return (
              <div key={v} className={`chlog-card ${open ? 'open' : ''}`}>
                <div className="chlog-card-head" onClick={() => toggle(v)}>
                  <span className="ver">v{v} <span className="cnt">（{items.length} 条）</span></span>
                  <div className="chlog-card-actions">
                    <a className="chlog-dl" href={downloadVersionSource(contractId, v)} download
                      onClick={e => e.stopPropagation()} title="下载该版本原始上传文件">⬇ 原文件</a>
                    <span className="caret">▾</span>
                  </div>
                </div>
                {open && (
                  <div className="chlog-card-body">
                    {pageItems.map(l => (
                      <div key={l.id} className="chlog-item">
                        <div className="chlog-time">{fmt(l.created_at)}</div>
                        <div className="chlog-body">
                          <span className={`chlog-tag ${l.event_type}`}>
                            {CHANGE_TYPE[l.event_type] || l.event_type}
                          </span>
                          <span className="chlog-user">{l.actor_post || '系统'}</span>
                          <div>{l.detail || '—'}</div>
                          {l.clause_code ? <div className="chlog-clause">条款 {l.clause_code}</div> : null}
                        </div>
                      </div>
                    ))}
                    {items.length > PAGE_SIZE && (
                      <div className="chlog-pager">
                        <button type="button" disabled={page <= 1} onClick={() => setPage(v, page - 1)}>上一页</button>
                        {Array.from({ length: totalPages }, (_, i) => i + 1).map(i => (
                          <button key={i} type="button" className={i === page ? 'active' : ''} onClick={() => setPage(v, i)}>{i}</button>
                        ))}
                        <span className="pg-info">{from}–{to} / {items.length}</span>
                        <button type="button" disabled={page >= totalPages} onClick={() => setPage(v, page + 1)}>下一页</button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <div className="modal-foot">
          <div></div>
          <button className="ca-btn" onClick={onClose}>关闭</button>
        </div>
      </div>
    </div>
  );
}
