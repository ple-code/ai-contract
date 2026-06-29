import { useState, useEffect, useRef, useCallback, type MouseEvent } from 'react';
import { useParams } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';
import { getContract, getAiStatus, getFieldSummary, getPostFocus, getPersonalFocus, type ContractDetail, type FieldChange } from '../api/contracts';
import { startReview, getReviewByVersion, type FindingInfo, type ReviewDetail } from '../api/reviews';
import { getReviewState, annotate, applySuggestion, revertApply, completeReview, type ClauseReviewStateInfo } from '../api/clauses';
import { useToast } from '../hooks/useToast';
import { useAuth } from '../contexts/AuthContext';

const STATUS_STEPS = ['AI初审中', '待人工复核', '复核完成'];
const ROLE_NAME: Record<string, string> = { buyer: '甲方（采购方）', seller: '乙方（供方）', neutral: '中立方' };

// 岗位 → 关注的条款类型标签（基于解析器的 type_tags 词汇）
// 对齐原型 FOCUS_AI 语义：销售关注商务条款、法务关注风险条款、财务关注资金、商务关注交付
const FOCUS_AI: Record<string, string[]> = {
  '销售': ['价格', '付款', '交付'],
  '法务': ['违约金', '合同效力', '解除终止', '保密', '知识产权', '争议解决', '数据安全'],
  '商务': ['交付', '质保', '价格'],
  '财务': ['付款', '违约金', '价格'],
};
const DEFAULT_FOCUS = FOCUS_AI['法务'];

// 三栏可拖动分隔（对齐原型 mh_wb_split，记忆到 localStorage）
const WB_SPLIT = { nav: 230, preview: 300, navMin: 160, navMax: 380, previewMin: 220, previewMax: 560 };
const clampSplit = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v));
function loadSplit(): { nav: number; preview: number } {
  try {
    const s = JSON.parse(localStorage.getItem('mh_wb_split') || '{}');
    return {
      nav: s.nav ? clampSplit(Number(s.nav), WB_SPLIT.navMin, WB_SPLIT.navMax) : WB_SPLIT.nav,
      preview: s.preview ? clampSplit(Number(s.preview), WB_SPLIT.previewMin, WB_SPLIT.previewMax) : WB_SPLIT.preview,
    };
  } catch { return { nav: WB_SPLIT.nav, preview: WB_SPLIT.preview }; }
}
// 把 markdown / 表格符号剥成纯文本，供 nav 浮窗预览
const stripMd = (t: string) => t.replace(/\|/g, ' ').replace(/[#*_`>]/g, '').replace(/\s+/g, ' ').trim();

// 关键字段在不同立场下的风险标签语义（与原型一致）
// [标签文本, CSS class]
const FIELD_TAG: Record<string, Record<string, [string, string]>> = {
  '合同总价': { buyer: ['需核价', 'tag-high'], seller: ['对方上调', 'tag-mid'], neutral: ['金额变动', 'tag-mid'] },
  '付款账期': { buyer: ['利于我方', 'tag-low'], seller: ['账期延长·不利', 'tag-high'], neutral: ['账期放宽', 'tag-mid'] },
  '违约金比例': { buyer: ['约束减弱·不利', 'tag-high'], seller: ['利于我方', 'tag-low'], neutral: ['约束减弱', 'tag-mid'] },
  '交货期': { buyer: ['交期放宽·留意', 'tag-mid'], seller: ['利于我方', 'tag-low'], neutral: ['交期放宽', 'tag-mid'] },
};

function riskDot(level: string) {
  if (level === 'high') return 'dot-high';
  if (level === 'medium') return 'dot-mid';
  return 'dot-low';
}

function maxRisk(findings: FindingInfo[]): string {
  if (findings.some(f => f.risk_level === 'high')) return 'high';
  if (findings.some(f => f.risk_level === 'medium')) return 'medium';
  return findings.length ? 'low' : '';
}

function riskTagCls(level: string) {
  if (level === 'high') return 'tag-high';
  if (level === 'medium') return 'tag-mid';
  return 'tag-low';
}

function riskLabel(level: string) {
  if (level === 'high') return '高风险';
  if (level === 'medium') return '中风险';
  return '低风险';
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string));
}

// 把 markdown 表格（连续 | ... | 行）转成 <table>，保留原文件里的表格结构
function markdownTableToHtml(html: string): string {
  // 预处理：合并表格行内被 \n 切断的片段（docx 单元格多段落会带 \n，导致 "|...|单价\n（\n元）|..." 被切成多行）
  const rawLines = html.split('\n');
  const merged: string[] = [];
  for (let i = 0; i < rawLines.length; i++) {
    let line = rawLines[i];
    // 当前行以 | 开头但不以 | 结尾 → 单元格内被 \n 切断，往下合并直到行尾是 |
    while (/^\s*\|/.test(line) && !/\|\s*$/.test(line) && i + 1 < rawLines.length) {
      i++;
      line += ' ' + rawLines[i].trim();
    }
    merged.push(line);
  }
  const text = merged.join('\n');
  return text.replace(/((?:^[ \t]*\|.*\|[ \t]*\n?)+)/gm, (block) => {
    const lines = block.trim().split('\n').map(l => l.trim()).filter(Boolean);
    if (lines.length < 2) return block;
    // 第二行须为分隔行 | --- | --- |
    if (!/^\|[\s\-:|]+\|$/.test(lines[1])) return block;
    const parseRow = (line: string) =>
      line.replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
    const header = parseRow(lines[0]);
    if (header.length === 0) return block;
    const rows = lines.slice(2).map(parseRow);
    let out = '<table class="md-table"><thead><tr>';
    header.forEach(h => { out += `<th>${h}</th>`; });
    out += '</tr></thead><tbody>';
    rows.forEach(r => {
      const cells = r.length >= header.length
        ? r.slice(0, header.length)
        : [...r, ...Array(header.length - r.length).fill('')];
      // 合并单元格启发式：仅第一格有内容（长度≥3，排除序号"1/2"）且其余全空
      // → 原文为 docx 横向合并（gridSpan），markdown 无法表达 colspan，这里还原为 <td colspan>
      const isMergeRow = cells.length >= 2
        && cells[0].trim().length >= 3
        && cells.slice(1).every(c => c.trim() === '');
      if (isMergeRow) {
        out += `<tr><td colspan="${cells.length}">${cells[0]}</td></tr>`;
      } else {
        out += '<tr>';
        cells.forEach(c => { out += `<td>${c}</td>`; });
        out += '</tr>';
      }
    });
    out += '</tbody></table>';
    return out;
  });
}

// 将纯文本转为含 del/ins 标记的 HTML（识别 "旧→新" 模式做简单高亮）；markdown 表格渲染为 <table>
function renderClauseText(raw: string) {
  if (!raw) return '';
  // 若后端已返回 HTML（含 <del/ins>），直接使用；否则转义
  if (/<(?:del|ins)[\s>]/i.test(raw)) return raw;
  // 先转义 + 识别「X→Y」高亮（在纯文本上处理，避免碰到表格 HTML 标签）
  let html = escapeHtml(raw).replace(/([^→\n]*?)\s*[→]\s*([^→\n]*)/g, (_m, a, b) =>
    `<del class="d">${String(a).trim()}</del> <ins class="i">${String(b).trim()}</ins>`);
  // 再把 markdown 表格段渲染成 <table>
  html = markdownTableToHtml(html);
  // 保留段落换行（HTML 默认会把 \n 折叠成空格，导致与原上传文档格式不符）
  html = html.replace(/\n/g, '<br>');
  return html;
}

export default function WorkbenchPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const { user } = useAuth();

  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [review, setReview] = useState<ReviewDetail | null>(null);
  const [findings, setFindings] = useState<FindingInfo[]>([]);
  const [states, setStates] = useState<ClauseReviewStateInfo[]>([]);
  const [activeClause, setActiveClause] = useState<string>('');
  const [stance, setStance] = useState('neutral');
  const stanceRef = useRef(stance);
  stanceRef.current = stance;
  const [stanceBusy, setStanceBusy] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [doneOpen, setDoneOpen] = useState(false);  // F3 复核完成确认弹窗
  const [postFocusCfg, setPostFocusCfg] = useState<Record<string, string[]> | null>(null);  // 管理员配置的岗位关注点
  const [personalFocus, setPersonalFocus] = useState<string[] | null>(null);  // 个人微调的关注点（优先级最高）
  const [reviewProgress, setReviewProgress] = useState<string[]>([]);
  const [annotateTarget, setAnnotateTarget] = useState<string | null>(null);
  const [annotateText, setAnnotateText] = useState('');
  const [showExport, setShowExport] = useState(false);
  const [fieldChanges, setFieldChanges] = useState<FieldChange[]>([]);
  const [loading, setLoading] = useState(true);
  // nav hover 浮窗（fixed 定位，立即显示，不被 sidenav overflow 裁剪）
  const [navPopup, setNavPopup] = useState<{ code: string; title: string; text: string; x: number; y: number } | null>(null);
  // 法条引用 hover 浮窗（替代原生 <a title>，避免浏览器 ~1s 延迟，期望更快）
  const [legalTip, setLegalTip] = useState<{ x: number; y: number; law: string; article: string; snippet: string } | null>(null);
  // 初审中进入详情：弹提示，确认后只显示左栏解析内容（隐藏右栏预览）
  const [reviewingEntry, setReviewingEntry] = useState<{ open: boolean; accepted: boolean }>({ open: false, accepted: false });

  const mainRef = useRef<HTMLDivElement>(null);
  const clauseRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const previewRefs = useRef<Record<string, HTMLDivElement | null>>({});

  // 三栏可拖动分隔：nav 宽 / preview 宽，拖动结束后写入 localStorage
  const [split, setSplit] = useState(loadSplit);
  const splitRef = useRef(split);
  splitRef.current = split;
  const dragState = useRef<{ which: 'nav' | 'preview' | null; lastX: number }>({ which: null, lastX: 0 });
  const onSplitDown = (which: 'nav' | 'preview') => (e: MouseEvent) => {
    e.preventDefault();
    dragState.current = { which, lastX: e.clientX };
    (e.currentTarget as HTMLElement).classList.add('dragging');
    document.body.classList.add('col-resizing');
  };
  useEffect(() => {
    const onMove = (ev: globalThis.MouseEvent) => {
      const ds = dragState.current;
      if (!ds.which) return;
      const dx = ev.clientX - ds.lastX;
      ds.lastX = ev.clientX;
      if (!dx) return;
      setSplit(prev => ds.which === 'nav'
        ? { ...prev, nav: clampSplit(prev.nav + dx, WB_SPLIT.navMin, WB_SPLIT.navMax) }
        : { ...prev, preview: clampSplit(prev.preview - dx, WB_SPLIT.previewMin, WB_SPLIT.previewMax) });
    };
    const onUp = () => {
      const ds = dragState.current;
      if (ds.which) {
        ds.which = null;
        document.body.classList.remove('col-resizing');
        document.querySelectorAll('.layout-split.dragging').forEach(el => el.classList.remove('dragging'));
        localStorage.setItem('mh_wb_split', JSON.stringify(splitRef.current));
      }
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    return () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
  }, []);

  const contractId = Number(id);

  const loadData = useCallback(async () => {
    try {
      const c = await getContract(contractId);
      setContract(c);

      // 并行拉取（互不依赖，减少本机↔云端 DB 的串行往返延迟）
      await Promise.allSettled([
        getReviewState(c.current_version_id)
          .then(rs => setStates(rs.states || []))
          .catch(() => {}),
        getPostFocus()
          .then(pf => { if (pf.post_focus && Object.keys(pf.post_focus).length > 0) setPostFocusCfg(pf.post_focus); })
          .catch(() => {}),
        getPersonalFocus()
          .then(me => { if (me.personal_focus && me.personal_focus.length > 0) setPersonalFocus(me.personal_focus); })
          .catch(() => {}),
        (c.baseline_kind
          ? getFieldSummary(contractId).then(fc => setFieldChanges(fc || [])).catch(() => setFieldChanges([]))
          : Promise.resolve(setFieldChanges([]))),
      ]);
    } finally {
      setLoading(false);
    }
  }, [contractId]);

  useEffect(() => { loadData(); }, [loadData]);

  // 进入/换合同时，默认选中第一个条款（与 nav 点击解耦，避免 loadData 全量 reload）
  useEffect(() => {
    if (contract?.clauses?.length) setActiveClause(contract.clauses[0].code);
  }, [contract?.id]);

  // review 查询独立：stance 切换或版本变化时拉取对应立场结果。
  // 与 nav 点击（activeClause）解耦，避免 loadData 重跑时重置 stance 导致按钮高亮错乱。
  useEffect(() => {
    const vid = contract?.current_version_id;
    if (!vid) return;
    setStanceBusy(true);
    getReviewByVersion(vid, stance)
      .then(r => { setReview(r); setFindings(r.findings || []); })
      .catch(() => { /* 该立场尚未初审 */ })
      .finally(() => setStanceBusy(false));
  }, [contract?.current_version_id, stance]);

  useEffect(() => {
    const close = () => setShowExport(false);
    if (showExport) {
      document.addEventListener('click', close);
      return () => document.removeEventListener('click', close);
    }
  }, [showExport]);

  // 立场锁定：一旦「应用建议」或「批注」，切换立场会让既有结果与新立场不一致，故锁定
  const stanceLocked = states.some(s => s.applied || !!s.note);
  const clauses = contract?.clauses || [];
  // 是否存在比对基准（首次上传时为 false，隐藏比对/接受/拒绝，保留批注）
  const hasBaseline = !!contract?.baseline_kind;

  // ===== 岗位关注条款定位（F14）=====
  // 当前用户岗位关注的 type_tags 集合
  const userPost = user?.post || '法务';
  // 优先级：个人微调 > 管理员岗位配置 > 前端默认 FOCUS_AI
  const focusTags = new Set(
    personalFocus || (postFocusCfg && postFocusCfg[userPost]) || FOCUS_AI[userPost] || DEFAULT_FOCUS
  );
  // 命中关注标签的条款 code（用于左侧 nav 高亮 ★ + 进入时自动定位）
  const focusedCodes = new Set(
    clauses
      .filter(c => (c.type_tags || []).some(t => focusTags.has(t)))
      .map(c => c.code)
  );

  // 进入合同后，按岗位自动定位到关注的第一条条款；
  // 换岗位也会重定位（对齐原型 confirmPost → locateForPost）。每个「合同+岗位」组合只触发一次。
  const locatedKeyRef = useRef<string | null>(null);
  const locateKey = `${contractId}:${userPost}`;
  useEffect(() => {
    // 等 user 加载完（避免深链直进时 userPost 回落到默认值）
    if (!user || loading || clauses.length === 0) return;
    if (locatedKeyRef.current === locateKey) return;
    locatedKeyRef.current = locateKey;
    const first = clauses.find(c => focusedCodes.has(c.code));
    if (!first) return;
    // 等 DOM 完成渲染再滚动，确保 clauseRefs 已挂载
    const timer = setTimeout(() => {
      setActiveClause(first.code);
      clauseRefs.current[first.code]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      previewRefs.current[first.code]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      addToast(`已按【${userPost}】岗位定位到关注的条款`, 'info');
    }, 220);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clauses, loading, locateKey, user]);

  const doReview = async () => {
    if (!contract) return;
    try {
      const status = await getAiStatus();
      if (!status.ready) {
        addToast('尚未配置 AI 模型，请前往「系统管理 → 系统配置」完成模型网关配置', 'error');
        navigate('/admin/config');
        return;
      }
    } catch {
      addToast('无法检查 AI 配置状态，请前往「系统管理 → 系统配置」检查', 'error');
      navigate('/admin/config');
      return;
    }
    setReviewing(true);
    setReviewProgress([]);
    setFindings([]);

    startReview(
      { version_id: contract.current_version_id, stance },
      (e) => {
        // 后端 SSE 只发 data: 行（无 event:），e.event 恒为 'message'；
        // 这里从 JSON.type 分发，并按 stance 过滤，流式展示当前立场的 finding
        let parsed: { type?: string; stance?: string; data?: FindingInfo; completed?: number; total?: number; message?: string };
        try { parsed = JSON.parse(e.data); } catch { return; }
        const evt = parsed.type || e.event;
        if (evt === 'finding' && parsed.data) {
          if (parsed.stance && parsed.stance !== stanceRef.current) return;
          setFindings(prev => [...prev, parsed.data as FindingInfo]);
        } else if (evt === 'progress') {
          setReviewProgress(prev => [...prev, `审查进度：${parsed.completed || 0} / ${parsed.total || 0}`]);
        } else if (evt === 'error') {
          setReviewProgress(prev => [...prev, `条款 ${parsed.message || '处理出错'}`]);
        } else if (evt === 'field_summary') {
          setReviewProgress(prev => [...prev, '已识别关键字段，正在逐条审查…']);
        }
      },
      () => {
        setReviewing(false);
        loadData();
        addToast('AI 初审完成，当前版本：待人工复核', 'success');
      },
      (err) => {
        setReviewing(false);
        setReviewProgress(prev => [...prev, `错误: ${err.message}`]);
        addToast(err.message || '审查失败', 'error');
      }
    );
  };

  // F1/F2：上传后进入工作台，若版本仍处于「AI初审中」且无初审结果，自动触发 AI 初审。
  // 用 Set 记录已自动触发过的合同 id 避免重复；AI 未配置时静默跳过（留给用户手动点）。
  const autoStartedRef = useRef<Set<number>>(new Set());
  useEffect(() => {
    if (!contract) return;
    if (autoStartedRef.current.has(contract.id)) return;
    autoStartedRef.current.add(contract.id);
    if (reviewing || review || findings.length > 0) return;
    if (contract.status !== 'AI初审中') return;
    getAiStatus().then(st => { if (st.ready) doReview(); }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contract]);

  // 初审进行中进入详情：弹提示"只能看解析内容"，确认后隐藏右栏预览聚焦条款原文
  useEffect(() => {
    if (contract && contract.status === 'AI初审中' && !reviewingEntry.accepted && !reviewingEntry.open) {
      setReviewingEntry({ open: true, accepted: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contract]);

  const switchStance = (r: string) => {
    if (r === stance) return;
    if (stanceLocked) {
      addToast('本版本已有复审留痕，立场已锁定（避免建议与已应用正文不一致）', 'error');
      return;
    }
    setStance(r);  // 触发上方 useEffect 拉取目标立场结果
    addToast('已切换为【' + ROLE_NAME[r] + '】立场', 'success');
  };

  const doAnnotate = async () => {
    if (!contract || !annotateTarget) return;
    try {
      await annotate(contract.current_version_id, annotateTarget, annotateText);
      const rs = await getReviewState(contract.current_version_id);
      setStates(rs.states);
      setAnnotateTarget(null);
      setAnnotateText('');
      addToast('批注已保存', 'success');
    } catch (err: unknown) {
      addToast(err instanceof Error ? err.message : '批注失败', 'error');
    }
  };

  const doApply = async (code: string, text: string) => {
    if (!contract) return;
    try {
      await applySuggestion(contract.current_version_id, code, text);
      const rs = await getReviewState(contract.current_version_id);
      setStates(rs.states);
      addToast('已应用建议修改', 'success');
    } catch (err: unknown) {
      addToast(err instanceof Error ? err.message : '应用失败', 'error');
    }
  };

  const doRevert = async (code: string) => {
    if (!contract) return;
    try {
      await revertApply(contract.current_version_id, code);
      const rs = await getReviewState(contract.current_version_id);
      setStates(rs.states);
      addToast('已撤销应用', 'success');
    } catch (err: unknown) {
      addToast(err instanceof Error ? err.message : '撤销失败', 'error');
    }
  };

  // F3：打开「复核完成」确认弹窗（用美化 modal 代替浏览器原生 confirm，对齐原型）
  const openDoneModal = () => setDoneOpen(true);
  const confirmDone = async () => {
    if (!contract) return;
    setDoneOpen(false);
    try {
      await completeReview(contract.current_version_id);
      addToast('当前版本已标记为「复核完成」', 'success');
      loadData();
    } catch (err: unknown) {
      addToast(err instanceof Error ? err.message : '操作失败', 'error');
    }
  };

  const scrollToClause = (code: string) => {
    setActiveClause(code);
    clauseRefs.current[code]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    previewRefs.current[code]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  // map status to 3-step index
  const statusLabel = !contract ? 'AI初审中' :
    contract.status === '复核完成' ? '复核完成' :
    review || findings.length ? '待人工复核' : 'AI初审中';
  const stepIndex = STATUS_STEPS.indexOf(statusLabel);

  const findingMap = new Map<string, FindingInfo[]>();
  findings.forEach(f => {
    if (!findingMap.has(f.clause_code)) findingMap.set(f.clause_code, []);
    findingMap.get(f.clause_code)!.push(f);
  });

  const stateMap = new Map<string, ClauseReviewStateInfo>();
  states.forEach(s => stateMap.set(s.clause_code, s));

  // 统计
  const stats = {
    high: findings.filter(f => f.risk_level === 'high').length,
    mid: findings.filter(f => f.risk_level === 'medium').length,
    low: findings.filter(f => f.risk_level === 'low').length,
    applied: states.filter(s => s.applied).length,
  };

  if (loading) return <div className="loading"><span className="spinner" />加载中...</div>;
  if (!contract) return <div className="loading">合同未找到</div>;

  const baseLabel = hasBaseline
    ? (contract.baseline_label || `v${Math.max(1, (contract.current_version_no || 1) - 1)}（上一版本 · 比对基准）`)
    : '首次上传 · 无比对基准';

  // 初审中（用户已确认提示）：隐藏右栏预览，聚焦左栏条款列表 + 中间条款原文
  const onlyParsed = reviewingEntry.accepted && (contract.status === 'AI初审中' || reviewing);
  const layoutCols = onlyParsed
    ? `${split.nav}px 6px 1fr`
    : `${split.nav}px 6px minmax(180px,1fr) 6px ${split.preview}px`;

  return (
    <>
      {/* Docbar */}
      <div className="docbar">
        <div className="docbar-left">
          <h1>{contract.name}</h1>
          <div className="docbar-sub">
            <div className="docbar-tags">
              <span className="type-badge">已识别：{contract.type_name}</span>
              <span className="enc-badge" title="数据静态加密存储">🔒 已加密存储</span>
            </div>
            <div className="meta">
              <span className="meta-item"><span className="meta-k">编号</span><span className="meta-val">{contract.no || '-'}</span></span>
              <span className="meta-item"><span className="meta-k">版本</span><span className="meta-val">v{contract.current_version_no}</span></span>
              <span className="meta-item"><span className="meta-k">状态</span><span className="meta-val status">{contract.status}</span></span>
              <span className="meta-item"><span className="meta-k">上传</span><span className="meta-val">{contract.uploader_name}</span></span>
              <span className="meta-item"><span className="meta-k">基准</span><span className="meta-val">{baseLabel}</span></span>
            </div>
          </div>
        </div>
        <div className="docbar-actions">
          <div className={`stance-switch${stanceLocked ? ' locked' : ''}`}>
            <div className="stance-row">
              <span className="lbl">审阅立场</span>
              <div className="seg">
                {(['buyer', 'seller', 'neutral'] as const).map(s => (
                  <button key={s} type="button" className={stance === s ? 'on' : ''}
                    disabled={stanceLocked || stanceBusy}
                    onClick={() => switchStance(s)}>
                    {s === 'buyer' ? '甲方' : s === 'seller' ? '乙方' : '中立'}
                  </button>
                ))}
              </div>
            </div>
            {stanceLocked && <div className="stance-lock-hint">已应用建议或批注，立场已锁定</div>}
          </div>
          <div className="docbar-divider" />
          <div className="versions">
            {hasBaseline && (
              <>
                <span className="vbadge">{baseLabel}</span>
                <span className="ver-arrow">→</span>
              </>
            )}
            <span className="vbadge new">v{contract.current_version_no} 当前</span>
            <div className="export-group">
              <button className="btn-export" type="button" onClick={e => { e.stopPropagation(); setShowExport(v => !v); }}>导出 ▾</button>
              {showExport && (
                <div className="export-menu" onClick={e => e.stopPropagation()}>
                  <div className="export-mi" onClick={() => { setShowExport(false); window.open(`/api/versions/${contract.current_version_id}/export/revised`, '_blank'); }}>导出 Word <small>(.docx)</small></div>
                  <div className="export-mi" onClick={() => { setShowExport(false); window.open(`/api/versions/${contract.current_version_id}/export/revised?format=pdf`, '_blank'); }}>导出 PDF <small>(.pdf)</small></div>
                  <div className="export-mi" onClick={() => { setShowExport(false); window.open(`/api/versions/${contract.current_version_id}/export/report`, '_blank'); }}>导出变更报告</div>
                </div>
              )}
            </div>
          </div>
          {!reviewing && !review && findings.length === 0 && (
            <button className="btn-export" onClick={doReview}>开始 AI 初审</button>
          )}
          {reviewing && <button className="btn-export" disabled>审查中…</button>}
          {review && contract.status === '待人工复核' && (
            <button className="btn-export" onClick={openDoneModal}>完成复核</button>
          )}
        </div>
      </div>

      {/* Steps */}
      <div className="status-steps">
        {STATUS_STEPS.map((s, i) => (
          <span key={s} style={{ display: 'inline-flex', alignItems: 'center' }}>
            {i > 0 && <span className={`step-line${i <= stepIndex ? ' done' : ''}`} />}
            <span className={`step ${i < stepIndex ? 'done' : i === stepIndex ? 'current' : ''}`}>
              <span className="dot">{i < stepIndex ? '✓' : i + 1}</span>
              <span className="lbl">{s}</span>
            </span>
          </span>
        ))}
      </div>

      {/* Three-panel */}
      <div className="layout" style={{ gridTemplateColumns: layoutCols }}>
        {/* Left: clause nav */}
        <nav className="sidenav">
          <h2>
            {hasBaseline ? '本轮变更' : '条款列表'}
            {focusedCodes.size > 0 && (
              <span className="nav-focus-tag">★ {userPost}关注</span>
            )}
          </h2>
          {clauses.map(c => {
            const cFindings = findingMap.get(c.code) || [];
            const risk = maxRisk(cFindings);
            const st = stateMap.get(c.code);
            const isFocused = focusedCodes.has(c.code);
            return (
              <div key={c.code} className={`nav-item${activeClause === c.code ? ' active' : ''}${isFocused ? ' focus' : ''}`}
                onClick={() => scrollToClause(c.code)}
                onMouseEnter={(e) => {
                  const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
                  const w = 340;
                  const x = r.right + 8 + w > window.innerWidth ? r.left - w - 8 : r.right + 8;
                  setNavPopup({ code: c.code, title: c.title, text: c.text, x, y: r.top });
                }}
                onMouseLeave={() => setNavPopup(null)}>
                {risk && <span className={`nav-dot ${riskDot(risk)}`} />}
                <span className="nav-clause">{c.code}</span>
                <span className="nav-title">{c.title}</span>
                {isFocused && <span className="focus-star">★</span>}
                {st?.applied && <span className="st st-acc">已应用</span>}
              </div>
            );
          })}
          {clauses.length === 0 && <div style={{ padding: '0 18px', fontSize: 12, color: 'var(--ink-soft)' }}>暂无条款</div>}
        </nav>
        <div className="layout-split" onMouseDown={onSplitDown('nav')} title="拖动调整左侧宽度" />

        {/* Center: clause cards */}
        <main className="main" ref={mainRef}>
          <section className="risk-summary">
            {hasBaseline && fieldChanges.length > 0 ? (
              <>
                <h2>关键字段变更摘要</h2>
                <p className="lead">
                  立场 <b style={{ color: 'var(--navy)' }}>{ROLE_NAME[stance] || '中立方'}</b>
                  <span style={{ color: '#d5d8d2', margin: '0 8px' }}>|</span>
                  {contract?.baseline_label || '基准'} → v{contract?.current_version_no} 核心字段变更
                </p>
                <div className="risk-grid">
                  {fieldChanges.map(fc => {
                    const tagDef = (FIELD_TAG[fc.field] || {})[stance] || ['变动', 'tag-mid'];
                    const isAdd = fc.change_type === 'add';
                    const isDel = fc.change_type === 'del';
                    return (
                      <div className="risk-cell" key={fc.field}>
                        <div className="field-name">{fc.field}</div>
                        <div className="change">
                          {isAdd ? (
                            <span className="to">{fc.to_value || '—'}</span>
                          ) : isDel ? (
                            <>
                              <span className="from">{fc.from_value || '—'}</span>
                              <span className="arr">→</span>
                              <span className="to" style={{ color: 'var(--del)' }}>已删除</span>
                            </>
                          ) : (
                            <>
                              <span className="from">{fc.from_value || '—'}</span>
                              <span className="arr">→</span>
                              <span className="to">{fc.to_value || '—'}</span>
                            </>
                          )}
                        </div>
                        <span className={`tag ${tagDef[1]}`}>{tagDef[0]}</span>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <>
                <h2>本轮审阅摘要</h2>
                <p className="lead">
                  共 {clauses.length} 个条款 · 发现 {findings.length} 处风险（高 {stats.high} · 中 {stats.mid} · 低 {stats.low}）
                  {stats.applied > 0 && ` · 已应用建议 ${stats.applied} 条`}
                </p>
                <div className="risk-grid">
                  <div className="risk-cell">
                    <div className="field-name">高风险条款</div>
                    <div className="change"><span className="to">{stats.high}</span><span className="tag tag-high">需关注</span></div>
                  </div>
                  <div className="risk-cell">
                    <div className="field-name">中风险条款</div>
                    <div className="change"><span className="to">{stats.mid}</span><span className="tag tag-mid">建议复核</span></div>
                  </div>
                  <div className="risk-cell">
                    <div className="field-name">低风险条款</div>
                    <div className="change"><span className="to">{stats.low}</span><span className="tag tag-low">可接受</span></div>
                  </div>
                  <div className="risk-cell">
                    <div className="field-name">无风险条款</div>
                    <div className="change"><span className="to">{Math.max(0, clauses.length - new Set(findings.map(f => f.clause_code)).size)}</span><span className="tag tag-low">通过</span></div>
                  </div>
                </div>
              </>
            )}
          </section>

          {reviewing && (
            <div className="reviewing">
              <span className="spin" />
              <span>{reviewProgress[reviewProgress.length - 1] || (review ? 'AI 正在按当前立场重新初审…' : 'AI 正在解析合同并初审…')}</span>
            </div>
          )}

          <div className="clause-list">
            {clauses.map(clause => {
              const cFindings = findingMap.get(clause.code) || [];
              const st = stateMap.get(clause.code);
              const clauseRisk = maxRisk(cFindings);
              return (
                <div key={clause.code} id={`clause-${clause.code}`}
                  className={`clause${st?.applied ? ' accepted' : ''}`}
                  ref={el => { clauseRefs.current[clause.code] = el; }}>
                  <div className="clause-head">
                    <div className="clause-title">
                      <span>{clause.code}　{clause.title}</span>
                      {clauseRisk && <span className={`clause-flag ${clauseRisk === 'high' ? 'flag-del' : 'flag-mod'}`}>{riskLabel(clauseRisk)}</span>}
                    </div>
                    <div className="clause-actions">
                      <button type="button" className="ca-btn"
                        onClick={() => { setAnnotateTarget(clause.code); setAnnotateText(st?.note || ''); }}>批注</button>
                    </div>
                  </div>
                  <div className="clause-body">
                    <div className="col old">
                      <div className="col-label">条款内容</div>
                      <div className="clause-text" dangerouslySetInnerHTML={{ __html: renderClauseText(st?.applied ? (st.applied_text_snapshot || clause.text) : clause.text) }} />
                    </div>
                    <div className="col">
                      <div className="col-label">AI 解读 / 风险</div>
                      {cFindings.length === 0 ? (
                        <div className="clause-text" style={{ color: 'var(--ink-soft)', fontStyle: 'italic' }}>未检测到风险（或尚未初审）</div>
                      ) : cFindings.map((f, fi) => (
                        <div key={fi} style={fi > 0 ? { marginTop: 14, paddingTop: 14, borderTop: '1px dashed var(--line)' } : undefined}>
                          <div style={{ marginBottom: 6 }}>
                            <span className={`tag ${riskTagCls(f.risk_level)}`}>{riskLabel(f.risk_level)}</span>
                          </div>
                          <div className="interpret" style={{ background: 'transparent', border: 'none', padding: 0 }}>
                            <span className="ai-mark">AI</span>
                            <div className="ai-text" dangerouslySetInnerHTML={{ __html: escapeHtml(f.finding) }} />
                          </div>
                          {f.stance_note && (
                            <div className="suggest" style={{ background: 'transparent', padding: '8px 0 0' }}>
                              <div className="suggest-head">
                                <span className="suggest-label">立场 · {ROLE_NAME[stance] || stance}</span>
                              </div>
                              <p className="suggest-text">{f.stance_note}</p>
                            </div>
                          )}
                          {f.suggestion && (
                            <div className="suggest" style={{ background: 'transparent', padding: '8px 0 0' }}>
                              <div className="suggest-head">
                                <span className="suggest-label">修改建议</span>
                                {st?.applied ? (
                                  <button className="apply-btn outline" type="button" onClick={() => doRevert(clause.code)}>撤销应用</button>
                                ) : (
                                  <button className="apply-btn" type="button" onClick={() => doApply(clause.code, f.suggestion)}>应用建议</button>
                                )}
                              </div>
                              <p className="suggest-text">{f.suggestion}</p>
                            </div>
                          )}
                          {f.legal_basis && f.legal_basis.length > 0 && (
                            <div className="legal-ref" style={{ background: 'transparent', border: 'none', padding: '8px 0 0' }}>
                              <span className="ai-mark">法</span>
                              <div>
                                {f.legal_basis.map((lb, li) => {
                                  const law = lb.law || '';
                                  const article = lb.article_no || lb.article || '';
                                  const snippet = lb.snippet || lb.point || '';
                                  return (
                                    <span key={li}>
                                      {li > 0 && '、'}
                                      <a
                                        className="legal-cite"
                                        onMouseEnter={e => setLegalTip({ x: e.clientX, y: e.clientY, law, article, snippet })}
                                        onMouseMove={e => setLegalTip({ x: e.clientX, y: e.clientY, law, article, snippet })}
                                        onMouseLeave={() => setLegalTip(null)}
                                      >{law} {article}{!article && snippet ? `（${snippet.slice(0, 20)}…）` : ''}</a>
                                    </span>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>

                    {st?.note && (
                      <div className="annotation">
                        <b>人工批注 · {clause.code}</b>：{st.note}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </main>
        {!onlyParsed && (<>
        <div className="layout-split" onMouseDown={onSplitDown('preview')} title="拖动调整右侧预览宽度" />

        {/* Right: doc preview */}
        <aside className="doc-preview">
          <div className="doc-preview-head">
            <h3>全文预览 <span className="doc-preview-tag">v{contract.current_version_no} · 当前版本</span></h3>
          </div>
          <p className="doc-preview-note">在线查看 · 标黄为 AI 识别风险 · 点击左侧变更项可定位</p>
          <div className="doc-preview-body">
            <div className="doc-block">
              <p className="doc-title">{contract.name}</p>
              <p className="doc-meta">
                合同编号：{contract.no || '-'}<br />
                合同类型：{contract.type_name}<br />
                当前版本：v{contract.current_version_no}
              </p>
            </div>
            {clauses.map(c => {
              const cFindings = findingMap.get(c.code) || [];
              const risk = maxRisk(cFindings);
              const st = stateMap.get(c.code);
              const cls = ['doc-block'];
              if (risk) {
                cls.push('doc-changed');
                if (risk === 'high') cls.push('risk-high');
                else if (risk === 'medium') cls.push('risk-mid');
              }
              if (activeClause === c.code) cls.push('doc-active');
              return (
                <div key={c.code} className={cls.join(' ')}
                  ref={el => { previewRefs.current[c.code] = el; }}
                  onClick={() => scrollToClause(c.code)}>
                  <h4>{c.code}　{c.title}</h4>
                  <div className="clause-text" dangerouslySetInnerHTML={{ __html: renderClauseText(st?.applied ? (st.applied_text_snapshot || c.text) : c.text) }} />
                </div>
              );
            })}
          </div>
        </aside>
        </>)}
      </div>

      {/* nav hover 浮窗（fixed 定位，立即显示条款内容预览） */}
      {navPopup && (
        <div className="nav-popup" style={{ left: navPopup.x, top: navPopup.y }}>
          <div className="np-title">{navPopup.code}　{navPopup.title}</div>
          {(() => {
            const t = stripMd(navPopup.text);
            return t ? <div>{t.length > 140 ? t.slice(0, 140) + '…' : t}</div> : <div className="np-empty">（无正文）</div>;
          })()}
        </div>
      )}

      {/* 法条引用 hover 浮窗（立即显示，无原生 title 延迟） */}
      {legalTip && (
        <div className="legal-tip" style={{ left: legalTip.x, top: legalTip.y }}>
          <div className="lt-head"><b>{legalTip.law}</b>{legalTip.article ? ` ${legalTip.article}` : ''}</div>
          {legalTip.snippet && <div className="lt-body">{legalTip.snippet}</div>}
        </div>
      )}

      {/* Annotate modal */}
      {annotateTarget && (
        <div className="modal-mask" onClick={() => setAnnotateTarget(null)}>
          <div className="modal" style={{ width: 480 }} onClick={e => e.stopPropagation()}>
            <h3>添加批注</h3>
            <p className="lead">批注将写入变更留痕，团队成员均可追溯查看。</p>
            <div className="annotate-clause" style={{ fontFamily: "'Noto Serif SC', serif", fontSize: 14, color: 'var(--navy)', background: 'var(--paper-dim)', border: '1px solid var(--line)', borderLeft: '3px solid var(--gold)', padding: '10px 14px', marginBottom: 16, borderRadius: '0 3px 3px 0', lineHeight: 1.5 }}>
              <div>{annotateTarget}　{clauses.find(c => c.code === annotateTarget)?.title}</div>
              <div style={{ fontSize: 11.5, color: 'var(--ink-soft)', marginTop: 4 }}>留痕对象 · 当前审阅版本</div>
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label htmlFor="annotateInput">批注内容</label>
              <textarea id="annotateInput" rows={4} value={annotateText}
                onChange={e => setAnnotateText(e.target.value)}
                placeholder="例：账期偏长，建议与对方协商缩短；或说明不接受该修改的理由…" />
            </div>
            <div className="modal-foot right" style={{ marginTop: 20 }}>
              <button type="button" className="ca-btn" onClick={() => setAnnotateTarget(null)}>取消</button>
              <button type="button" className="confirm-btn" onClick={doAnnotate}>保存批注</button>
            </div>
          </div>
        </div>
      )}

      {/* F3：复核完成确认弹窗（对齐原型） */}
      {doneOpen && (
        <div className="modal-mask" onClick={() => setDoneOpen(false)}>
          <div className="modal" style={{ width: 440 }} onClick={e => e.stopPropagation()}>
            <h3>是否完成复核？</h3>
            <p className="lead">是否将当前版本标记为「复核完成」？完成后该版本状态将更新，便于团队同步复核进度。</p>
            <div className="modal-foot right">
              <button type="button" className="ca-btn" onClick={() => setDoneOpen(false)}>尚未完成</button>
              <button type="button" className="confirm-btn" onClick={confirmDone}>复核完成</button>
            </div>
          </div>
        </div>
      )}

      {/* 初审中进入详情：提示只能看解析内容 */}
      {reviewingEntry.open && (
        <div className="modal-mask">
          <div className="modal" style={{ width: 440 }} onClick={e => e.stopPropagation()}>
            <h3>AI 初审进行中</h3>
            <p className="lead">当前合同正在 AI 初审，暂时只能查看合同解析内容（条款原文）。初审完成后将自动展示风险解读与修改建议。</p>
            <div className="modal-foot right">
              <button type="button" className="ca-btn" onClick={() => navigate('/')}>返回列表</button>
              <button type="button" className="confirm-btn" onClick={() => setReviewingEntry({ open: false, accepted: true })}>继续查看</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
