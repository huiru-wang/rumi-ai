"use client";

import { useState, useCallback, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";
import { CITE_HREF_PREFIX, replaceCitationMarkers } from "./citations";

// ============================================================
// CitationBadge
// ============================================================

function CitationBadge({
  index,
  docName,
  detail,
}: {
  index: number;
  docName: string;
  detail: string;
}) {
  const [show, setShow] = useState(false);
  const badgeRef = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  const onEnter = useCallback(() => {
    if (badgeRef.current) {
      const r = badgeRef.current.getBoundingClientRect();
      setPos({ top: r.top - 8, left: r.left + r.width / 2 });
    }
    setShow(true);
  }, []);

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={onEnter}
      onMouseLeave={() => setShow(false)}
    >
      <span
        ref={badgeRef}
        className="ml-0.5 inline-flex h-[18px] min-w-[18px] cursor-default items-center justify-center rounded-full bg-emerald-500/20 px-1 text-[10px] font-semibold text-emerald-400 align-super leading-none"
      >
        {index}
      </span>
      {show && (
        <span
          className="fixed z-[9999] w-max max-w-xs -translate-x-1/2 -translate-y-full rounded-lg border border-border bg-muted px-3 py-2 text-xs text-foreground shadow-xl"
          style={{ top: pos.top, left: pos.left }}
        >
          <span className="font-medium text-emerald-400">📄 {docName}</span>
          <br />
          <span className="text-muted-foreground">{detail}</span>
        </span>
      )}
    </span>
  );
}

// ============================================================
// MarkdownWithCitations
// ============================================================

export function MarkdownWithCitations({ text }: { text: string }) {
  const { text: sanitized, citations } = replaceCitationMarkers(text);

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children, ...rest }) => {
          if (href?.startsWith(CITE_HREF_PREFIX)) {
            const idx = parseInt(href.slice(CITE_HREF_PREFIX.length), 10);
            const entry = citations[idx - 1];
            if (entry)
              return (
                <CitationBadge
                  index={idx}
                  docName={entry.docName}
                  detail={entry.detail}
                />
              );
          }
          return (
            <a href={href} {...rest}>
              {children}
            </a>
          );
        },
        table: ({ children, ...rest }) => (
          <div className="overflow-x-auto">
            <table className="w-max min-w-full" {...rest}>
              {children}
            </table>
          </div>
        ),
        code: ({ className, children, ...rest }) => {
          const match = /language-(\w+)/.exec(className || "");
          const codeString = String(children).replace(/\n$/, "");
          if (match) {
            return (
              <SyntaxHighlighter
                style={oneDark}
                language={match[1]}
                PreTag="div"
                customStyle={{
                  margin: 0,
                  borderRadius: "0.5rem",
                  fontSize: "0.85em",
                }}
              >
                {codeString}
              </SyntaxHighlighter>
            );
          }
          return (
            <code className={className} {...rest}>
              {children}
            </code>
          );
        },
      }}
    >
      {sanitized}
    </ReactMarkdown>
  );
}
