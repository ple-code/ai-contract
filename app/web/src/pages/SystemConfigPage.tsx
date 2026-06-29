import { useState, useEffect } from 'react';
import { getModelConfig, updateModelConfig, testModelConfig, type ModelConfigInfo } from '../api/admin';
import { useToast } from '../hooks/useToast';
import PasswordInput from '../components/PasswordInput';

const POSTS = ['法务', '销售', '商务', '财务'];
const ALL_TAGS = ['价格', '付款', '违约金', '交付', '质保', '保密', '知识产权', '合同效力', '解除终止', '争议解决', '不可抗力', '数据安全'];
// 默认关注点（与 WorkbenchPage FOCUS_AI 对齐；后端未配置时用此默认）
const DEFAULT_POST_FOCUS: Record<string, string[]> = {
  '法务': ['违约金', '争议解决', '合同效力', '保密', '知识产权', '解除终止'],
  '销售': ['价格', '付款', '交付', '违约金'],
  '商务': ['交付', '质保', '价格', '付款'],
  '财务': ['付款', '价格', '违约金'],
};

type Tab = 'model' | 'focus' | 'security' | 'retention' | 'about';

export default function SystemConfigPage() {
  const { addToast } = useToast();
  const [tab, setTab] = useState<Tab>('model');
  const [config, setConfig] = useState<ModelConfigInfo | null>(null);
  const [form, setForm] = useState({ gateway_base_url: '', default_model: '', sensitive_model: '', gateway_token: '' });
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [postFocus, setPostFocus] = useState<Record<string, string[]>>({ ...DEFAULT_POST_FOCUS });
  const [focusSaving, setFocusSaving] = useState(false);

  useEffect(() => {
    getModelConfig().then(c => {
      setConfig(c);
      setForm({ gateway_base_url: c.gateway_base_url, default_model: c.default_model, sensitive_model: c.sensitive_model, gateway_token: '' });
      if (c.post_focus && Object.keys(c.post_focus).length > 0) {
        setPostFocus({ ...DEFAULT_POST_FOCUS, ...c.post_focus });
      }
    }).catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const data: Record<string, unknown> = { ...form };
      if (!data.gateway_token) delete data.gateway_token;
      const c = await updateModelConfig(data);
      setConfig(c);
      addToast('模型配置已保存', 'success');
    } catch (err: unknown) {
      addToast(err instanceof Error ? err.message : '保存失败', 'error');
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      const res = await testModelConfig();
      addToast(res.ok ? '连通测试成功' : `测试失败: ${res.message}`, res.ok ? 'success' : 'error');
    } catch (err: unknown) {
      addToast(err instanceof Error ? err.message : '测试失败', 'error');
    } finally {
      setTesting(false);
    }
  };

  const toggleTag = (post: string, tag: string) => {
    setPostFocus(prev => {
      const cur = prev[post] || [];
      return { ...prev, [post]: cur.includes(tag) ? cur.filter(t => t !== tag) : [...cur, tag] };
    });
  };

  const saveFocus = async () => {
    setFocusSaving(true);
    try {
      await updateModelConfig({ post_focus: postFocus });
      addToast('岗位关注点已保存', 'success');
    } catch (err: unknown) {
      addToast(err instanceof Error ? err.message : '保存失败', 'error');
    } finally {
      setFocusSaving(false);
    }
  };

  const TABS: [Tab, string][] = [
    ['model', '模型配置'], ['focus', '岗位关注点'], ['security', '安全与存储'],
    ['retention', '数据留存'], ['about', '关于'],
  ];

  return (
    <div className="admin-page sys-page">
      <div className="list-head">
        <div>
          <h1 className="serif">系统配置</h1>
          <div className="list-sub">模型、安全存储、数据留存等系统级配置</div>
        </div>
      </div>
      <div className="sys-wrap">
        <div className="sys-nav">
          {TABS.map(([k, label]) => (
            <div key={k} className={`sys-tab${tab === k ? ' active' : ''}`} onClick={() => setTab(k)}>{label}</div>
          ))}
        </div>
        <div className="sys-body">
          {tab === 'model' && (
            <div className="sys-pane">
              <h3>模型配置</h3>
              <p className="lead">配置模型网关与默认模型。生产默认走内网本地推理（数据不出网）；敏感合同固定使用本地模型。</p>
              <div className="field">
                <label>网关地址（Base URL，OpenAI 兼容）</label>
                <input value={form.gateway_base_url} onChange={e => setForm({ ...form, gateway_base_url: e.target.value })} placeholder="https://api.example.com" />
              </div>
              <div className="field">
                <label>API Token（留空不修改）</label>
                <PasswordInput value={form.gateway_token} onChange={e => setForm({ ...form, gateway_token: e.target.value })} placeholder={config?.has_token ? '••••••（已配置）' : '未配置'} />
              </div>
              <div className="field">
                <label>默认模型</label>
                <input value={form.default_model} onChange={e => setForm({ ...form, default_model: e.target.value })} placeholder="glm-4.5-air" />
              </div>
              <div className="field">
                <label>敏感模型（涉密条款）</label>
                <input value={form.sensitive_model} onChange={e => setForm({ ...form, sensitive_model: e.target.value })} placeholder="同默认模型" />
              </div>
              <div className="modal-foot">
                <button className="ca-btn" disabled={testing} onClick={test}>{testing ? '测试中…' : '连通测试'}</button>
                <button className="confirm-btn" disabled={saving} onClick={save}>{saving ? '保存中…' : '保存'}</button>
              </div>
            </div>
          )}
          {tab === 'focus' && (
            <div className="sys-pane">
              <h3>岗位关注点</h3>
              <p className="lead">按"条款类型标签"配置每个岗位默认关注哪类条款（跨合同通用，不绑定具体条款号）。进入合同后据此自动定位/高亮。</p>
              <div className="focus-bar">
                <span className="hint">未勾选的岗位将由 AI 按合同类型自动推荐默认关注点。</span>
              </div>
              <div className="focus-matrix-wrap">
                <table className="focus-matrix">
                  <thead>
                    <tr>
                      <th>岗位 \ 关注标签</th>
                      {ALL_TAGS.map(t => <th key={t}>{t}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {POSTS.map(p => (
                      <tr key={p}>
                        <td className="post-name">{p}</td>
                        {ALL_TAGS.map(t => {
                          const on = (postFocus[p] || []).includes(t);
                          return (
                            <td key={t} className="cell" style={{ textAlign: 'center' }}>
                              <input type="checkbox" checked={on} onChange={() => toggleTag(p, t)} />
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="modal-foot"><div></div><button className="confirm-btn" disabled={focusSaving} onClick={saveFocus}>{focusSaving ? '保存中…' : '保存'}</button></div>
            </div>
          )}
          {tab === 'security' && (
            <div className="sys-pane">
              <h3>安全与存储</h3>
              <p className="lead">合同属机密、可能含个人信息，默认按"最小权限 + 加密 + 留痕"落地（涉数据安全法 / 个人信息保护法）。</p>
              <div className="kv"><span>传输加密</span><b className="on">TLS 全链路（含内网）</b></div>
              <div className="kv"><span>静态加密</span><b className="on">磁盘/卷加密 + 文件存储 SSE</b></div>
              <div className="kv"><span>敏感合同外发</span><b className="on">禁止（强制本地推理）</b></div>
              <div className="kv"><span>访问控制</span><b className="on">账号分配制 + RBAC 最小权限</b></div>
              <div className="kv"><span>操作审计</span><b className="on">全量留痕（见「审计日志」）</b></div>
              <div className="kv"><span>下载水印 / 防外传</span><b className="off">按需开启（P1）</b></div>
              <p className="hint">以上为默认安全基线，具体强度（字段级加密、水印等）随公司安全/合规要求确定。</p>
            </div>
          )}
          {tab === 'retention' && (
            <div className="sys-pane">
              <h3>数据留存</h3>
              <p className="lead">合同与审计记录的留存与销毁周期（合规留存）。</p>
              <div className="field"><label>合同留存期限</label><select className="filter"><option>长期保存（默认）</option><option>5 年</option><option>3 年</option></select></div>
              <div className="field"><label>审计日志留存期限</label><select className="filter"><option>≥ 6 个月（默认）</option><option>1 年</option><option>3 年</option></select></div>
              <div className="field"><label>备份加密</label><select className="filter"><option>开启（默认）</option><option>关闭</option></select></div>
              <p className="hint">MVP 阶段以上策略为系统默认值，后续按合规要求可配置化。</p>
            </div>
          )}
          {tab === 'about' && (
            <div className="sys-pane">
              <h3>关于</h3>
              <p className="lead">明衡 · AI 合同审阅系统</p>
              <div className="kv"><span>版本</span><b>MVP v1</b></div>
              <div className="kv"><span>部署形态</span><b>办公网内网（不暴露公网）</b></div>
              <div className="kv"><span>默认推理</span><b>本地/网关模型（自主可控）</b></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
