import { useCallback, useState } from "react";
import Button from "./Button";

export interface CodeBlockProps {
  /** Raw code/text. Rendered as a text node (never innerHTML) — XSS-safe. */
  code: string;
  /** Informational language label (e.g. "json", "yaml"). Not highlighted. */
  language?: string;
  /** Show a copy-to-clipboard button. */
  copyable?: boolean;
  /** When set, show a download button producing a blob with this filename. */
  downloadName?: string;
  /** Optional caption above the block. */
  label?: string;
  className?: string;
  maxHeight?: string;
}

/**
 * Dark-chrome code panel (Evidentia pre.block). The content is bound via React
 * children → textContent, so untrusted JSON/SARIF/OSCAL payloads cannot inject
 * markup. Copy + download act on the in-memory string only.
 */
export function CodeBlock({
  code,
  language,
  copyable = false,
  downloadName,
  label,
  className,
  maxHeight,
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const onCopy = useCallback(() => {
    void navigator.clipboard?.writeText(code).then(
      () => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1400);
      },
      () => setCopied(false),
    );
  }, [code]);

  const onDownload = useCallback(() => {
    const blob = new Blob([code], { type: "application/octet-stream" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = downloadName ?? "download.txt";
    document.body.appendChild(a);
    a.click();
    a.remove();
    // Revoke on the next tick so the navigation has fired.
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }, [code, downloadName]);

  const hasActions = copyable || !!downloadName;

  return (
    <div className={className ? `stack-2 ${className}` : "stack-2"}>
      {(label || hasActions) && (
        <div className="row-between">
          <span className="muted" style={{ fontSize: "0.78rem" }}>
            {label ?? (language ? language.toUpperCase() : "")}
          </span>
          {hasActions && (
            <div className="row gap-2">
              {copyable && (
                <Button variant="ghost" size="sm" onClick={onCopy}>
                  {copied ? "Copied" : "Copy"}
                </Button>
              )}
              {downloadName && (
                <Button variant="outline" size="sm" onClick={onDownload}>
                  Download
                </Button>
              )}
            </div>
          )}
        </div>
      )}
      <pre className="block" style={maxHeight ? { maxHeight } : undefined}>
        <code>{code}</code>
      </pre>
    </div>
  );
}

export default CodeBlock;
