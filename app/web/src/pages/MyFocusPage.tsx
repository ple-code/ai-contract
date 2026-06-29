import { useState, useEffect } from 'react';
import { getPostFocus, getPersonalFocus, updatePersonalFocus } from '../api/contracts';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../hooks/useToast';

const ALL_TAGS = ['价格', '付款', '违约金', '交付', '质保', '保密', '知识产权', '合同效力', '解除终止', '争议解决', '不可抗力', '数据安全'];
const DEFAULT_FOCUS: Record<string, string[]> = {
  '法务': ['违约金', '争议解决', '合同效力', '保密', '知识产权', '解除终止'],
  '销售': ['价格', '付款', '交付', '违约金'],
  '商务': ['交付', '质保', '价格', '付款'],
  '财务': ['付款', '价格', '违约金'],
};

export default function MyFocusPage() {
  const { user } = useAuth();
  const { addToast } = useToast();
  const post = user?.post || '法务';
  const [tags, setTags] = useState<string[]>([]);
  const [defaults, setDefaults] = useState<string[]>(DEFAULT_FOCUS[post] || []);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const pf = await getPostFocus();
        const adminFocus = (pf.post_focus && pf.post_focus[post]) || DEFAULT_FOCUS[post] || [];
        setDefaults(adminFocus);
        const me = await getPersonalFocus();
        setTags(me.personal_focus && me.personal_focus.length > 0 ? me.personal_focus : adminFocus);
      } catch { /* ignore */ } finally { setLoading(false); }
    })();
  }, [post]);

  const toggle = (t: string) => {
    setTags(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]);
  };
  const reset = () => { setTags(defaults); addToast('已恢复为岗位默认关注点', 'info'); };
  const save = async () => {
    setSaving(true);
    try {
      await updatePersonalFocus(tags);
      addToast('我的关注点已保存', 'success');
    } catch (err: unknown) {
      addToast(err instanceof Error ? err.message : '保存失败', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="admin-page">
      <div className="list-head">
        <div>
          <h1 className="serif">我的关注点</h1>
          <div className="list-sub">在你所在岗位（{post}）的默认关注点基础上，按个人习惯增减；只影响你自己的定位/高亮。</div>
        </div>
      </div>
      <div className="sys-page" style={{ maxWidth: 680 }}>
        <div style={{ padding: '22px 24px' }}>
          <p className="hint" style={{ margin: '0 0 16px' }}>勾选 = 你关注（进入合同自动定位）。带「默认」标记的来自岗位配置；你可以取消或额外勾选其它类型。</p>
          {loading ? (
            <div className="empty"><span className="spinner" />加载中...</div>
          ) : (
            <div className="my-focus-list">
              {ALL_TAGS.map(t => {
                const on = tags.includes(t);
                const isDefault = defaults.includes(t);
                return (
                  <label key={t} className={`my-focus-item${on ? ' on' : ''}`}>
                    <input type="checkbox" checked={on} onChange={() => toggle(t)} />
                    <span className="mf-label">{t}</span>
                    {isDefault && <span className="mf-default">默认</span>}
                  </label>
                );
              })}
            </div>
          )}
          <div className="modal-foot" style={{ marginTop: 20 }}>
            <button className="ca-btn" onClick={reset}>恢复岗位默认</button>
            <button className="confirm-btn" disabled={saving || loading} onClick={save}>{saving ? '保存中…' : '保存'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
