"use client";

import { useState } from "react";
import { Palette, Mic, Wand2 } from "lucide-react";
import { updateWorkspaceConfig, type PptStyleInfo, type Task, type VoiceInfo } from "@/lib/api";
import { StylePickerDialog } from "./style-picker-dialog";
import { VoicePickerDialog } from "./voice-picker-dialog";
import { StyleExtractionUploadDialog } from "./style-extraction-upload-dialog";
import { StyleExtractionDialog } from "./style-extraction-dialog";

interface ConfigPanelProps {
  workspaceId: string;
  userId: string;
  pptStyle: string;
  voiceId: string;
  styles: PptStyleInfo[];
  voices: VoiceInfo[];
  onConfigChange: (key: string, value: string) => void;
  onStyleSaved?: () => void;
}

export function ConfigPanel({
  workspaceId,
  userId,
  pptStyle,
  voiceId,
  styles,
  voices,
  onConfigChange,
  onStyleSaved,
}: ConfigPanelProps) {
  const [showStylePicker, setShowStylePicker] = useState(false);
  const [showVoicePicker, setShowVoicePicker] = useState(false);
  const [showExtractionUpload, setShowExtractionUpload] = useState(false);
  const [extractionTaskId, setExtractionTaskId] = useState<string | null>(null);

  const selectedStyle = styles.find((s) => s.id === pptStyle);
  const selectedVoice = voices.find((v) => v.id === voiceId);

  const handleStyleSelect = async (styleId: string) => {
    onConfigChange("ppt_style", styleId);
    try {
      await updateWorkspaceConfig(workspaceId, "ppt_style", styleId);
    } catch {
      console.error("Failed to update ppt_style config");
    }
  };

  const handleVoiceSelect = async (selectedVoiceId: string) => {
    const voice = voices.find((v) => v.id === selectedVoiceId);
    onConfigChange("voice_id", selectedVoiceId);
    try {
      if (voice) {
        await updateWorkspaceConfig(workspaceId, "voice_info", {
          id: voice.id,
          name: voice.name,
          trait: voice.trait,
          gender: voice.gender,
        });
      }
    } catch {
      console.error("Failed to update voice config");
    }
  };

  const handleStyleDelete = async () => {
    onStyleSaved?.();
  };

  return (
    <>
      <div className="shrink-0 border-b border-border px-4 py-3">
        <h3 className="mb-2.5 text-sm font-medium text-foreground">⚙️ 配置</h3>

        <div className="flex flex-col gap-2">
          {/* PPT Style */}
          <button
            onClick={() => setShowStylePicker(true)}
            className="flex items-center gap-2.5 rounded-lg border border-border px-3 py-2 text-left transition-colors hover:border-accent/50 hover:bg-muted/50"
          >
            <Palette size={14} className="shrink-0 text-accent/70" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-foreground">
                PPT视觉风格
              </p>
              <p className="truncate text-[10px] text-muted-foreground">
                {selectedStyle ? `${selectedStyle.name}` : pptStyle}
              </p>
            </div>
          </button>

          {/* Style Extraction */}
          <button
            onClick={() => setShowExtractionUpload(true)}
            className="flex items-center gap-2.5 rounded-lg border border-border px-3 py-2 text-left transition-colors hover:border-accent/50 hover:bg-muted/50"
          >
            <Wand2 size={14} className="shrink-0 text-accent/70" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-foreground">
                视觉风格提取
              </p>
              <p className="truncate text-[10px] text-muted-foreground">
                提供PPTX文件提取风格布局，制作专属模版
              </p>
            </div>
          </button>

          {/* Voice */}
          <button
            onClick={() => setShowVoicePicker(true)}
            className="flex items-center gap-2.5 rounded-lg border border-border px-3 py-2 text-left transition-colors hover:border-accent/50 hover:bg-muted/50"
          >
            <Mic size={14} className="shrink-0 text-accent/70" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-foreground">
                口播稿语音音色
              </p>
              <p className="truncate text-[10px] text-muted-foreground">
                {selectedVoice?.name ?? voiceId}
              </p>
            </div>
          </button>
        </div>
      </div>

      {showStylePicker && (
        <StylePickerDialog
          selectedId={pptStyle}
          styles={styles}
          onSelect={handleStyleSelect}
          onClose={() => setShowStylePicker(false)}
          onDelete={handleStyleDelete}
        />
      )}

      {showVoicePicker && (
        <VoicePickerDialog
          selectedId={voiceId}
          voices={voices}
          onSelect={handleVoiceSelect}
          onClose={() => setShowVoicePicker(false)}
        />
      )}

      {showExtractionUpload && (
        <StyleExtractionUploadDialog
          workspaceId={workspaceId}
          onClose={() => setShowExtractionUpload(false)}
          onSubmitted={(task: Task) => {
            setShowExtractionUpload(false);
            setExtractionTaskId(task.id);
          }}
        />
      )}

      {extractionTaskId && (
        <StyleExtractionDialog
          workspaceId={workspaceId}
          userId={userId}
          taskId={extractionTaskId}
          onClose={() => setExtractionTaskId(null)}
          onSaved={onStyleSaved}
        />
      )}
    </>
  );
}
