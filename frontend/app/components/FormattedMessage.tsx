"use client";

import React from "react";

interface FormattedMessageProps {
  content: string;
}

export default function FormattedMessage({ content }: FormattedMessageProps) {
  // Pre-clean any accidental robotic text
  const cleaned = content
    .replace(/\[Grounded Answer\]/gi, "")
    .replace(/\[Grounded Response\]/gi, "")
    .replace(/According to [^,\n]+'s official dealership documentation:\s*/gi, "")
    .replace(/According to official dealership documentation:\s*/gi, "")
    .replace(/Based on the provided (context|documents|data):\s*/gi, "")
    .trim();

  // Split into lines/paragraphs
  const lines = cleaned.split("\n");

  return (
    <div className="space-y-2 text-xs leading-relaxed text-slate-800">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={idx} className="h-1" />;
        }

        // Bullet point detection (* or -)
        if (trimmed.startsWith("* ") || trimmed.startsWith("- ")) {
          const bulletText = trimmed.slice(2);
          return (
            <div key={idx} className="flex items-start gap-2 pl-1 my-0.5">
              <span className="h-1.5 w-1.5 rounded-full bg-blue-400 mt-1.5 flex-shrink-0" />
              <div className="flex-1">{renderFormattedInline(bulletText)}</div>
            </div>
          );
        }

        // Regular paragraph line
        return <p key={idx}>{renderFormattedInline(trimmed)}</p>;
      })}
    </div>
  );
}

function renderFormattedInline(text: string): React.ReactNode {
  // Parse **bold** and `code` tokens
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }

    const token = match[0];
    if (token.startsWith("**") && token.endsWith("**")) {
      parts.push(
        <strong key={match.index} className="font-semibold text-slate-900">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith("`") && token.endsWith("`")) {
      parts.push(
        <code
          key={match.index}
          className="rounded bg-white px-1 py-0.5 font-mono text-[11px] text-blue-700 border border-slate-200"
        >
          {token.slice(1, -1)}
        </code>
      );
    }

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  return parts;
}
