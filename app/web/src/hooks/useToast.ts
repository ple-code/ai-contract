import { useSyncExternalStore } from 'react';

// 全局 toast store：任何组件 addToast → 全局 <Toast/> 容器统一渲染。
// 这样跨页面/跨组件的提示都能显示（之前 useToast 是组件内本地状态，
//   且无人渲染 <Toast/>，导致 addToast 实际不可见）。
let toastId = 0;
interface Toast { id: number; message: string; type: 'info' | 'error' | 'success' }

let store: Toast[] = [];
const listeners = new Set<() => void>();
function emit() { listeners.forEach(l => l()); }

export function addToast(message: string, type: Toast['type'] = 'info') {
  const id = ++toastId;
  store = [...store, { id, message, type }];
  emit();
  setTimeout(() => {
    store = store.filter(t => t.id !== id);
    emit();
  }, 3500);
}

// 供全局 toast 容器订阅
export function useToasts() {
  return useSyncExternalStore(
    (l) => { listeners.add(l); return () => { listeners.delete(l); }; },
    () => store,
  );
}

// 兼容旧用法：const { addToast } = useToast();
export function useToast() {
  return { toasts: useToasts(), addToast };
}
