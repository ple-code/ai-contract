import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getLegalArticles, type LegalArticleInfo } from '../api/legal';
import { getReviewRules, type ReviewRuleInfo } from '../api/rules';

const levelClass = (lv: string) => lv === '高' ? 'st-off' : lv === '中' ? 'st-mid' : 'st-on';

export default function LegalPage() {
  const [params] = useSearchParams();
  return params.get('tab') === 'rule' ? <RulePane /> : <LegalPane />;
}

// 适用标签 → 颜色映射（不同标签用不同色调，便于在条文列表里快速区分关注点）
const TAG_COLOR: Record<string, string> = {
  '合同效力': 'tag-c-blue',
  '保密': 'tag-c-purple',
  '违约金': 'tag-c-red',
  '价格': 'tag-c-gold',
  '交付': 'tag-c-green',
  '质保': 'tag-c-teal',
  '知识产权': 'tag-c-indigo',
  '解除终止': 'tag-c-orange',
  '争议解决': 'tag-c-cyan',
  '不可抗力': 'tag-c-slate',
  '数据安全': 'tag-c-rose',
  '付款': 'tag-c-amber',
};
const tagColorClass = (t: string) => TAG_COLOR[t] || 'tag-c-default';


function LegalPane() {
  const [articles, setArticles] = useState<LegalArticleInfo[]>([]);
  const [search, setSearch] = useState('');
  const [law, setLaw] = useState('');
  const [laws, setLaws] = useState<string[]>([]);
  // 按法律/法规折叠：记录哪些法律处于折叠态（默认全展开）
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const p: Record<string, string> = {};
    if (search) p.search = search;
    if (law) p.law = law;
    getLegalArticles(p).then(list => {
      setArticles(list);
      if (!laws.length) setLaws([...new Set(list.map(a => a.law))]);
    }).catch(() => {});
  }, [search, law]);

  const rows = articles.filter(a => {
    if (law && a.law !== law) return false;
    if (!search) return true;
    return (a.law + a.article_no + a.content + (a.tags || []).join('')).toLowerCase().includes(search.toLowerCase());
  });

  // 按法律名分组（保持库内出现顺序）
  const grouped: [string, LegalArticleInfo[]][] = [];
  const order: Record<string, number> = {};
  rows.forEach(a => {
    if (!(a.law in order)) {
      order[a.law] = grouped.length;
      grouped.push([a.law, []]);
    }
    grouped[order[a.law]][1].push(a);
  });

  const toggle = (lname: string) => setCollapsed(s => ({ ...s, [lname]: !s[lname] }));

  return (
    <div className="list-wrap">
      <div className="list-head">
        <div>
          <h1 className="serif">法律法规</h1>
          <div className="list-sub">AI 审查所依据的法律法规（静态导入，暂只读、不支持录入）　·　共 {rows.length} 条</div>
        </div>
        <div className="list-tools">
          <input className="search" placeholder="搜索法律 / 条号 / 关键词…" value={search} onChange={e => setSearch(e.target.value)} />
          <select className="filter" value={law} onChange={e => setLaw(e.target.value)}>
            <option value="">全部法律</option>
            {laws.map(l => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
      </div>
      <div className="legal-groups">
        {grouped.length === 0 ? (
          <div className="empty" style={{ padding: '24px 0', textAlign: 'center', color: 'var(--ink-soft)' }}>无匹配条文</div>
        ) : grouped.map(([lname, items]) => {
          const open = !collapsed[lname];
          return (
            <div key={lname} className={`legal-group${open ? ' open' : ''}`}>
              <div className="legal-group-head" onClick={() => toggle(lname)}>
                <span className="caret">{open ? '▾' : '▸'}</span>
                <b style={{ color: 'var(--navy)' }}>{lname}</b>
                <span className="cnt">（{items.length} 条）</span>
              </div>
              {open && (
                <table className="ctable">
                  <thead>
                    <tr>
                      <th style={{ width: 100 }}>条号</th>
                      <th>内容</th>
                      <th style={{ width: 220 }}>适用标签</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map(a => (
                      <tr key={a.id} id={`legal-row-${a.id}`}>
                        <td className="no">{a.article_no}</td>
                        <td style={{ lineHeight: 1.7 }}>{a.content}</td>
                        <td>{(a.tags || []).map(t => <span key={t} className={`tag ${tagColorClass(t)}`} style={{ marginRight: 4 }}>{t}</span>)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RulePane() {
  const [kw, setKw] = useState('');
  const [lv, setLv] = useState('');
  const [rules, setRules] = useState<ReviewRuleInfo[]>([]);
  const [loadErr, setLoadErr] = useState('');

  useEffect(() => {
    getReviewRules().then(setRules).catch(e => setLoadErr(e instanceof Error ? e.message : '加载失败'));
  }, []);

  const levelCn = (rlv: string) => rlv === 'high' ? '高' : rlv === 'medium' ? '中' : '低';

  const rows = rules.filter(r => {
    if (lv && r.risk_level !== lv) return false;
    if (!kw) return true;
    return (r.name + r.condition_desc + r.suggestion + r.match_keywords).toLowerCase().includes(kw.toLowerCase());
  });

  return (
    <div className="list-wrap">
      <div className="list-head">
        <div>
          <h1 className="serif">审查规则</h1>
          <div className="list-sub">确定性审查规则，AI 初审时按条款命中关键词注入 prompt 与模型互补防遗漏　·　共 {rules.length} 条</div>
        </div>
        <div className="list-tools">
          <input className="search" placeholder="搜索规则名 / 关键词…" value={kw} onChange={e => setKw(e.target.value)} />
          <select className="filter" value={lv} onChange={e => setLv(e.target.value)}>
            <option value="">全部风险等级</option>
            <option value="high">高风险</option>
            <option value="medium">中风险</option>
            <option value="low">低风险</option>
          </select>
        </div>
      </div>
      {loadErr && <div className="empty" style={{ padding: '16px 0', color: 'var(--risk-high)' }}>规则加载失败：{loadErr}</div>}
      <table className="ctable rule-table">
        <thead>
          <tr>
            <th className="col-name">规则名称</th>
            <th className="col-type">适用类型</th>
            <th className="col-cond">触发条件 / 命中关键词</th>
            <th className="col-risk">风险</th>
            <th className="col-sug">建议</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr><td colSpan={5} className="empty">无匹配规则</td></tr>
          ) : rows.map(r => (
            <tr key={r.id}>
              <td className="col-name"><b style={{ color: 'var(--navy)' }}>{r.name}</b></td>
              <td className="col-type">{r.rule_type}</td>
              <td className="col-cond no" style={{ lineHeight: 1.7 }}>
                {r.condition_desc}
                {r.match_keywords && <div className="rule-kws">命中关键词：{r.match_keywords}</div>}
              </td>
              <td className="col-risk"><span className={`st ${levelClass(levelCn(r.risk_level))}`}>{levelCn(r.risk_level)}风险</span></td>
              <td className="col-sug" style={{ lineHeight: 1.7 }}>{r.suggestion}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
