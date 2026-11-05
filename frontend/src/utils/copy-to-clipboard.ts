/**
 * Copy `text` to the clipboard, returning whether it worked.
 *
 * `navigator.clipboard` only exists in a secure context (HTTPS or localhost).
 * TargetMind is commonly reached over plain HTTP on a LAN address, where the
 * API is simply `undefined` and every copy button silently did nothing — hence
 * the `execCommand("copy")` fallback via an off-screen textarea.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Permission denied or a transient failure — fall through to the legacy path.
    }
  }

  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    // Keep it out of view and out of the tab order, but still selectable.
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.top = "-1000px";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    textarea.setSelectionRange(0, text.length);
    const ok = document.execCommand("copy");
    textarea.remove();
    return ok;
  } catch {
    return false;
  }
}
