import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadContract, getContractOptions, type ContractOption, type UploadResult } from '../api/contracts';
import { useToast } from '../hooks/useToast';

type DupMatch = NonNullable<UploadResult['match']>;

export default function UploadPage() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const pickerRef = useRef<HTMLDivElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<'new' | 'version'>('new');
  const [baseId, setBaseId] = useState<number | null>(null);
  const [options, setOptions] = useState<ContractOption[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerKw, setPickerKw] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  // 重复合同识别命中的匹配对象（非空时弹确认框）
  const [dupMatch, setDupMatch] = useState<DupMatch | null>(null);
  // 命中原因文案（后端 message）+ 方法（编号撞号 / AI 相似度）
  const [dupMessage, setDupMessage] = useState('');
  const [dupMethod, setDupMethod] = useState<'contract_no' | 'ai_similarity' | ''>('');

  useEffect(() => {
    getContractOptions().then(list => {
      setOptions(list);
      if (list[0]) setBaseId(list[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) setPickerOpen(false);
    };
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, []);

  const handleFile = (f: File) => {
    if (!f.name.endsWith('.docx') && !f.name.endsWith('.pdf')) {
      setError('支持 .docx 和 .pdf 格式');
      return;
    }
    setFile(f);
    setError('');
  };

  // 参数化提交：支持重复确认后以不同 mode/contractId/confirm 重新提交
  const submit = async (opts?: { overrideMode?: 'new' | 'version'; overrideContractId?: number; confirmDuplicate?: boolean }) => {
    if (!file) return;
    const useMode = opts?.overrideMode ?? mode;
    const useBaseId = opts?.overrideContractId ?? baseId;
    if (useMode === 'version' && !useBaseId) {
      setError('请先在上方搜索并选择要关联的「已有合同」，否则无法作为新版本合并');
      return;
    }
    setUploading(true);
    setError('');
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('mode', useMode);
      if (useMode === 'version' && useBaseId) form.append('target_contract_id', String(useBaseId));
      if (useMode === 'new' && opts?.confirmDuplicate) form.append('confirm_duplicate', 'true');
      const res = await uploadContract(form);

      // 重复合同识别：命中后弹确认框，不跳转
      if (res.ok === false && res.error === 'duplicate_detected' && res.match) {
        setDupMatch(res.match);
        setDupMessage(res.message || '');
        setDupMethod(res.method || '');
        return;
      }
      addToast('已上传，AI 正在解析合同…', 'success');
      navigate(`/contract/${res.contract_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '上传失败');
    } finally {
      setUploading(false);
    }
  };

  // 重复确认：作为新版本关联到命中的合同
  const linkAsVersion = () => {
    if (!dupMatch) return;
    setDupMatch(null);
    setDupMessage('');
    setDupMethod('');
    setMode('version');
    setBaseId(dupMatch.id);
    submit({ overrideMode: 'version', overrideContractId: dupMatch.id });
  };
  // 重复确认：仍作为新合同（跳过检查）
  const forceNew = () => {
    setDupMatch(null);
    setDupMessage('');
    setDupMethod('');
    submit({ overrideMode: 'new', confirmDuplicate: true });
  };

  const picked = options.find(o => o.id === baseId);
  const pickerText = pickerOpen ? pickerKw : (picked ? `${picked.name}（${picked.no || '无编号'} · 当前 v${picked.current_version_no ?? '?'}）` : '');
  const filtered = options.filter(o => {
    if (!pickerKw) return true;
    const kw = pickerKw.toLowerCase();
    return (o.name + ' ' + (o.no || '')).toLowerCase().includes(kw);
  });

  return (
    <div className="upload-stage">
      <div
        className="dropzone"
        style={dragOver ? { borderColor: 'var(--gold)', background: '#fffcf5' } : undefined}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); }}
      >
        <div className="big serif">上传合同开始初审</div>
        <div className="small">支持 Word（.doc/.docx）与 PDF（.pdf）· MVP 先支持采购合同</div>

        <div className="upload-opts">
          <div className="opt-title">上传归属（决定版本比对基准）</div>
          <div className="upload-mode">
            <label><input type="radio" name="mode" checked={mode === 'new'} onChange={() => setMode('new')} /> 新合同</label>
            <label><input type="radio" name="mode" checked={mode === 'version'} onChange={() => setMode('version')} /> 已有合同的新版本</label>
          </div>
          {mode === 'version' && (
            <div className="upload-target">
              <div className="upload-picker" ref={pickerRef}>
                <input
                  type="text"
                  placeholder="搜索合同名称 / 编号…"
                  value={pickerText}
                  autoComplete="off"
                  onChange={e => { setPickerKw(e.target.value); setBaseId(null); }}
                  onFocus={() => { setPickerOpen(true); setPickerKw(''); }}
                />
                {pickerOpen && (
                  <div className="upload-picker-menu">
                    {filtered.length === 0 ? (
                      <div className="upload-picker-empty">无匹配合同，请换关键词（名称 / 编号）</div>
                    ) : filtered.map(o => (
                      <div key={o.id} className={`upload-picker-opt${o.id === baseId ? ' active' : ''}`}
                        onClick={() => { setBaseId(o.id); setPickerOpen(false); setPickerKw(''); }}>
                        <span className="opt-name">{o.name}</span>
                        <span className="opt-no">{o.no || '无编号'}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="hint">比对基准 = 所选合同的<strong>当前版本</strong>（上一版作 diff 参照）</div>
            </div>
          )}
        </div>

        <div className="mock-uploads" style={{ display: 'flex', gap: 14, justifyContent: 'center', flexWrap: 'wrap' }}>
          <button className="upload-btn" onClick={() => fileRef.current?.click()}>
            {file ? '重新选择文件' : '选择合同文件'}
          </button>
          {file && (
            <button className="confirm-btn" disabled={uploading} onClick={() => submit()}>
              {uploading ? '解析上传中…' : '上传并解析'}
            </button>
          )}
        </div>
        <input ref={fileRef} type="file" accept=".docx,.pdf" hidden onChange={e => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }} />

        {file && (
          <div style={{ marginTop: 16, fontSize: 13, color: 'var(--navy)' }}>
            已选择：<b>{file.name}</b> （{(file.size / 1024).toFixed(1)} KB）
          </div>
        )}
        <div className="fmt-hint">＊ 支持 .docx 与 .pdf（文字版），扫描版 PDF 暂不支持</div>
      </div>

      {error && <div className="unsupport"><h4>上传失败</h4><p>{error}</p></div>}

      {dupMatch && (
        <div className="modal-mask">
          <div className="modal" style={{ width: 520 }}>
            <h3>疑似为已有合同的新版本</h3>
            <p className="lead">
              {dupMethod === 'ai_similarity'
                ? 'AI 初审时判断，这份合同与库内已有合同高度相似，可能是同一交易的不同版本。'
                : '解析时检测到，这份合同的合同编号与库内已有合同一致。'}
              {dupMessage ? `（${dupMessage}）` : ''}
              是否将其关联为该合同的新版本，以便做版本比对？
            </p>
            <div className="dup-info">
              <div className="dup-row">
                <span className="dup-k">已存在合同</span>
                <span className="dup-v">{dupMatch.name}</span>
              </div>
              <div className="dup-row">
                <span className="dup-k">合同编号</span>
                <span className="dup-v">{dupMatch.no || '（无编号）'}</span>
              </div>
              <div className="dup-row">
                <span className="dup-k">当前版本</span>
                <span className="dup-v">v{dupMatch.current_version_no ?? '?'}</span>
              </div>
            </div>
            <div className="modal-foot">
              <button className="ca-btn" onClick={() => { setDupMatch(null); setDupMessage(''); setDupMethod(''); }}>取消</button>
              <button className="ca-btn" onClick={forceNew} disabled={uploading}>仍作为新合同</button>
              <button className="confirm-btn" onClick={linkAsVersion} disabled={uploading}>
                {uploading ? '关联中…' : '关联为新版本'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
