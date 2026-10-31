/**
 * User feedback: screen-reader announcements, toasts, copy to clipboard (with a fallback for sandboxed frames).
 */
import { SR, TOAST } from '../dom.js';

let srTO = 0;
export function announce(t) {
  clearTimeout(srTO);
  srTO = setTimeout(() => {
    SR.textContent = t;
  }, 120);
}
// clipboard with a fallback for sandboxed frames where the async API is blocked
export function copyText(t) {
  const done = () => toast(`Copied ${t}`);
  const fallback = () => {
    const ta = document.createElement('textarea');
    ta.value = t;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;opacity:0;top:0';
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand('copy') ? done() : toast('Copy isn’t allowed here. Select the title to copy it.');
    } catch (_) {
      toast('Copy isn’t allowed here. Select the title to copy it.');
    }
    ta.remove();
  };
  try {
    navigator.clipboard ? navigator.clipboard.writeText(t).then(done, fallback) : fallback();
  } catch (_) {
    fallback();
  }
}
let toastTO = 0;
export function toast(t) {
  TOAST.textContent = t;
  TOAST.classList.add('on');
  announce(t);
  clearTimeout(toastTO);
  toastTO = setTimeout(() => TOAST.classList.remove('on'), 2800);
}
