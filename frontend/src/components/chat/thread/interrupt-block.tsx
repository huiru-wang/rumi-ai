"use client";

import { useState, useEffect, useRef } from "react";
import { useStreamContext, useResume } from "../assistant";
import { ClarifyForm } from "../clarify-form";
import { stableStringify } from "./helpers";

// ============================================================
// Helpers
// ============================================================

function normalizeFieldOptions(options: unknown): string[] | undefined {
  if (Array.isArray(options)) {
    const normalized = options
      .map((option) => {
        if (typeof option === "string") return option;
        if (typeof option === "number" || typeof option === "boolean") {
          return String(option);
        }
        if (typeof option === "object" && option !== null) {
          const record = option as Record<string, unknown>;
          const value = record.label ?? record.value ?? record.name ?? record.text;
          if (typeof value === "string") return value;
          if (typeof value === "number" || typeof value === "boolean") {
            return String(value);
          }
        }
        return "";
      })
      .map((option) => option.trim())
      .filter(Boolean);
    return normalized.length > 0 ? normalized : undefined;
  }

  if (typeof options === "string") {
    const normalized = options
      .split(/[\n,，、]/)
      .map((option) => option.trim())
      .filter(Boolean);
    return normalized.length > 0 ? normalized : undefined;
  }

  return undefined;
}

// ============================================================
// InterruptBlock
// ============================================================

export function InterruptBlock() {
  const { interrupt, isLoading } = useStreamContext();
  const onResume = useResume();
  // 本地已提交标记：resume 发出后立即隐藏表单，不等 stream 消息更新。
  // 防止重启后重复点击提交触发 "no pending protocol interrupt" 错误。
  const [localSubmitted, setLocalSubmitted] = useState(false);

  // 记录已处理（提交/取消）的 interrupt 值的序列化字符串。
  // 用于防止 SDK 在 stream 结束后从 stale threadHead.tasks[].interrupts
  // 重新暴露相同 interrupt 值导致表单重复出现（取消后 BUG）。
  const handledValueRef = useRef<string | null>(null);

  useEffect(() => {
    // 当 interrupt 完全消失且 stream 空闲时，清除已处理记录，
    // 为下一次全新 interrupt 做准备。
    if ((!interrupt || interrupt.value === undefined) && !isLoading) {
      handledValueRef.current = null;
      return;
    }

    if (!interrupt || interrupt.value === undefined) return;

    const currStringified = stableStringify(interrupt.value);

    // 如果当前 interrupt 值与已处理的值相同，说明是 SDK 从 stale state
    // 重新暴露的旧值，跳过重置，保持表单隐藏。
    if (handledValueRef.current === currStringified) {
      return;
    }

    // 真正的新 interrupt 到达，重置提交状态以显示表单。
    setLocalSubmitted(false);
  }, [interrupt, isLoading]);

  if (!interrupt || interrupt.value === undefined) return null;
  if (localSubmitted) return null;

  const interruptValue = interrupt.value as Record<string, unknown>;

  const handleSubmit = async (values: Record<string, string | string[]>) => {
    setLocalSubmitted(true);
    handledValueRef.current = stableStringify(interrupt.value);
    try {
      await onResume(values);
    } catch (err) {
      console.error("[InterruptBlock] resume failed:", err);
      setLocalSubmitted(false);
      handledValueRef.current = null;
    }
  };

  if (interruptValue.fields && Array.isArray(interruptValue.fields)) {
    const fields = (
      interruptValue.fields as Array<Record<string, unknown>>
    ).map((field) => ({
      name: (field.name as string) || "",
      label: (field.label as string) || "",
      type: (field.type as "text" | "select" | "multiselect") || "select",
      options: normalizeFieldOptions(field.options),
      recommended: Array.isArray(field.recommended) ? field.recommended as string[] : undefined,
      allow_custom: field.allow_custom === true,
      required: field.required !== false,
    }));

    return (
      <div>
        <div className="min-w-0">
          <ClarifyForm
            title={(interruptValue.title as string) || "请填写信息"}
            description={(interruptValue.description as string) || ""}
            fields={fields}
            onSubmit={handleSubmit}
          />
        </div>
      </div>
    );
  }

  return null;
}
