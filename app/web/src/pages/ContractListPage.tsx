import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { getContracts, type ContractBrief } from '../api/contracts';
import { useToast } from '../hooks/useToast';
import ChangeLogModal from '../components/ChangeLogModal';

const STATUS_OPTS = ['AI初审中', '待人工复核', '复核完成'];
const STATUS_CLS: Record<string, string> = {
  'AI初审中': 'stt-ai',
  '待人工复核': 'stt-doing',
  '复核完成': 'stt-done',
};

function fmtTime(s: string) {
  if (!s) return '-';
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export default function ContractListPage() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [items, setItems] = useState<ContractBrief[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('');  // 单选筛选：''=全部
  const [loading, setLoading] = useState(true);
  const [statusOpen, setStatusOpen] = useState(false);
  // 缺失编号 "?" 的悬浮提示（自定义 popover，替代原生 title 的 ~1s 延迟）
  const [missTip, setMissTip] = useState<{ x: number; y: number } | null>(null);
  const [openMenu, setOpenMenu] = useState<number | null>(null);
  const [chlog, setChlog] = useState<ContractBrief | null>(null);
  const statusRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const load = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (search) params.search = search;
      if (status) params.status = status;
      const res = await getContracts(params);
      setItems(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [search, status]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (statusRef.current && !statusRef.current.contains(e.target as Node)) setStatusOpen(false);
      if (openMenu !== null && menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenu(null);
      }
    };
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [openMenu]);

  const statusLabel = status || '全部状态';

  const doExport = (c: ContractBrief, fmt: 'docx' | 'pdf') => {
    setOpenMenu(null);
    if (!c.current_version_id) {
      addToast('当前合同没有可导出的版本', 'error');
      return;
    }
    const vid = c.current_version_id;
    const label = fmt === 'docx' ? 'Word' : 'PDF';
    const url = fmt === 'pdf'
      ? `/api/versions/${vid}/export/revised?format=pdf`
      : `/api/versions/${vid}/export/revised`;
    window.open(url, '_blank');
    addToast(`正在导出「${c.name}」v${c.current_version_no} · ${label}`, 'success');
  };

  // 下载用户最初上传的原文件（非修订版导出）
  const doDownload = (c: ContractBrief) => {
    setOpenMenu(null);
    if (!c.current_version_id) {
      addToast('当前合同没有可下载的原文件', 'error');
      return;
    }
    window.open(`/api/contracts/${c.id}/download`, '_blank');
    addToast(`正在下载「${c.name}」原文件`, 'success');
  };

  return (
    <div className="list-wrap">
      <div className="list-head">
        <div>
          <h1 className="serif">全部合同</h1>
          <div className="list-sub">已上传合同的留存与再进入　·　共 {total} 份</div>
        </div>
        <div className="list-tools">
          <input className="search" placeholder="搜索合同名称 / 编号…" value={search} onChange={e => setSearch(e.target.value)} />
          <div className="ms-filter" ref={statusRef}>
            <button type="button" className="ms-btn" onClick={e => { e.stopPropagation(); setStatusOpen(v => !v); }}>
              <span>{statusLabel}</span> ▾
            </button>
            {statusOpen && (
              <div className="ms-menu" onClick={e => e.stopPropagation()}>
                <label className="ms-opt">
                  <input type="radio" checked={status === ''} onChange={() => setStatus('')} /> 全部状态
                </label>
                {STATUS_OPTS.map(s => (
                  <label key={s} className="ms-opt">
                    <input type="radio" checked={status === s} onChange={() => setStatus(s)} /> {s}
                  </label>
                ))}
              </div>
            )}
          </div>
          <button className="upload-btn" onClick={() => navigate('/upload')}>＋ 上传合同</button>
        </div>
      </div>

      <table className="ctable">
        <thead>
          <tr>
            <th>合同名称</th>
            <th>编号</th>
            <th>类型</th>
            <th>状态</th>
            <th>版本</th>
            <th>更新时间</th>
            <th>上传人</th>
            <th style={{ width: 72 }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr><td colSpan={8} className="empty"><span className="spinner" />加载中...</td></tr>
          ) : items.length === 0 ? (
            <tr><td colSpan={8} className="empty">没有符合条件的合同</td></tr>
          ) : items.map(c => (
            <tr key={c.id} onClick={() => navigate(`/contract/${c.id}`)}>
              <td className="cname">{c.name}</td>
              <td className="no">
                {c.no ? c.no : (
                  <span className="no-missing"
                    onMouseEnter={e => setMissTip({ x: e.clientX, y: e.clientY })}
                    onMouseMove={e => setMissTip({ x: e.clientX, y: e.clientY })}
                    onMouseLeave={() => setMissTip(null)}
                  >?</span>
                )}
              </td>
              <td>{c.type_name}</td>
              <td><span className={`stt ${STATUS_CLS[c.status] || ''}`}>{c.status}</span></td>
              <td className="no">v{c.current_version_no}</td>
              <td className="no">{fmtTime(c.updated_at)}</td>
              <td>{c.uploader_name}</td>
              <td className="col-actions" onClick={e => e.stopPropagation()}>
                <div className="row-menu" ref={openMenu === c.id ? menuRef : undefined}>
                  <button type="button" className="row-menu-btn" onClick={e => { e.stopPropagation(); setOpenMenu(openMenu === c.id ? null : c.id); }}>操作 ▾</button>
                  {openMenu === c.id && (
                    <div className="export-menu" style={{ display: 'block' }} onClick={e => e.stopPropagation()}>
                      <div className="export-mi" onClick={() => { setChlog(c); setOpenMenu(null); }}>变更记录</div>
                      <div className="export-mi has-sub">
                        <span>导出</span><span className="sub-arr">›</span>
                        <div className="export-sub">
                          <div className="export-mi" onClick={() => doDownload(c)}>下载原文件</div>
                          <div className="export-mi" onClick={() => doExport(c, 'docx')}>Word <small>(.docx)</small></div>
                          <div className="export-mi" onClick={() => doExport(c, 'pdf')}>PDF <small>(.pdf)</small></div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {chlog && (
        <ChangeLogModal
          contractId={chlog.id}
          contractName={chlog.name}
          contractNo={chlog.no}
          versionNo={chlog.current_version_no}
          onClose={() => setChlog(null)}
        />
      )}

      {missTip && (
        <div className="legal-tip" style={{ left: missTip.x, top: missTip.y }}>
          <div className="lt-body">原始文件中没有合同编号</div>
        </div>
      )}
    </div>
  );
}
