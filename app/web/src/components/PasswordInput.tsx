import { useState, type InputHTMLAttributes } from 'react';

/**
 * 密码输入框：带「眼睛」按钮切换明文/密文。
 * 透传所有原生 input 属性（value/onChange/placeholder/autoFocus 等），
 * 通过内联 paddingRight 覆盖外层 .field input 的 padding，给眼睛按钮留位。
 */
export default function PasswordInput({ className = '', style, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  const [show, setShow] = useState(false);
  return (
    <div className="pwd-wrap">
      <input
        {...props}
        type={show ? 'text' : 'password'}
        className={`pwd-input ${className}`}
        style={{ paddingRight: 40, ...style }}
      />
      <button
        type="button"
        className={`pwd-eye${show ? ' on' : ''}`}
        onClick={() => setShow(v => !v)}
        tabIndex={-1}
        aria-label={show ? '隐藏密码' : '显示密码'}
      >
        {show ? (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-10-8-10-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 10 8 10 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
            <line x1="1" y1="1" x2="23" y2="23" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        )}
      </button>
    </div>
  );
}
