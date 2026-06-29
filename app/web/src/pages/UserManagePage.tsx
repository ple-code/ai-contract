import { useState, useEffect } from 'react';
import { getUsers, createUser, updateUser, type UserBrief } from '../api/admin';
import { useToast } from '../hooks/useToast';

const POST_OPTS = ['法务', '销售', '商务', '财务'];

export default function UserManagePage() {
  const { addToast } = useToast();
  const [users, setUsers] = useState<UserBrief[]>([]);
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ username: '', password: 'Init@123', display_name: '', post: '法务', role: '普通用户' });
  const [error, setError] = useState('');

  const load = () => getUsers().then(setUsers).catch(() => {});
  useEffect(() => { load(); }, []);

  const doCreate = async () => {
    setError('');
    if (!form.username || !form.display_name) { setError('请填写用户名与姓名'); return; }
    try {
      await createUser(form);
      setShowCreate(false);
      setForm({ username: '', password: 'Init@123', display_name: '', post: '法务', role: '普通用户' });
      load();
      addToast(`已开通账号：${form.display_name}`, 'success');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '创建失败');
    }
  };

  const toggleEnabled = async (u: UserBrief) => {
    await updateUser(u.id, { enabled: !u.enabled });
    load();
    addToast(`已${u.enabled ? '停用' : '启用'} ${u.display_name}`, 'success');
  };

  const filtered = users.filter(u =>
    !search || u.username.includes(search) || u.display_name.includes(search));

  return (
    <div className="list-wrap">
      <div className="list-head">
        <div>
          <h1 className="serif">用户管理</h1>
          <div className="list-sub">账号分配制：由管理员开通账号、分配岗位与角色</div>
        </div>
        <div className="list-tools">
          <input className="search" placeholder="搜索用户名 / 姓名…" value={search} onChange={e => setSearch(e.target.value)} />
          <button className="btn-export" onClick={() => setShowCreate(true)}>＋ 新增用户</button>
        </div>
      </div>

      <table className="ctable">
        <thead>
          <tr><th>用户名</th><th>姓名</th><th>岗位</th><th>角色</th><th>状态</th><th>创建时间</th><th>操作</th></tr>
        </thead>
        <tbody>
          {filtered.length === 0 ? (
            <tr><td colSpan={7} className="empty">无匹配用户</td></tr>
          ) : filtered.map(u => (
            <tr key={u.id}>
              <td className="no">{u.username}</td>
              <td>{u.display_name}</td>
              <td>{u.post}</td>
              <td>{u.role === '管理员' ? <b style={{ color: 'var(--gold)' }}>管理员</b> : u.role}</td>
              <td><span className={`st ${u.enabled ? 'st-on' : 'st-off'}`}>{u.enabled ? '启用' : '停用'}</span></td>
              <td className="no">{new Date(u.created_at).toLocaleString('zh-CN')}</td>
              <td>
                <span className="rowact" onClick={() => toggleEnabled(u)}>{u.enabled ? '停用' : '启用'}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showCreate && (
        <div className="modal-mask" onClick={() => setShowCreate(false)}>
          <div className="modal" style={{ width: 460 }} onClick={e => e.stopPropagation()}>
            <h3>新增用户</h3>
            <p className="lead">由管理员开通账号；用户首次登录后可修改密码。</p>
            <div className="field"><label>用户名（登录名）</label><input value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} placeholder="如 zhangming" /></div>
            <div className="field"><label>姓名</label><input value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })} placeholder="如 张明" /></div>
            <div className="field">
              <label>岗位</label>
              <select className="filter" style={{ width: '100%' }} value={form.post} onChange={e => setForm({ ...form, post: e.target.value })}>
                {POST_OPTS.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div className="field">
              <label>角色</label>
              <select className="filter" style={{ width: '100%' }} value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}>
                <option value="普通用户">普通用户</option>
                <option value="管理员">管理员</option>
              </select>
            </div>
            <div className="field"><label>初始密码</label><input value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} type="text" /></div>
            {error && <div style={{ color: 'var(--del)', fontSize: 13, marginTop: 8 }}>{error}</div>}
            <div className="modal-foot">
              <button className="ca-btn" onClick={() => setShowCreate(false)}>取消</button>
              <button className="confirm-btn" onClick={doCreate}>开通账号</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
