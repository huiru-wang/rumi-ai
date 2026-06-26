"use client";

import { useEffect, useRef, useState } from "react";
import { X, Play, Pause } from "lucide-react";
import type { VoiceInfo } from "@/lib/api";

interface VoicePickerDialogProps {
  selectedId: string;
  voices: VoiceInfo[];
  onSelect: (voiceId: string) => void;
  onClose: () => void;
}

export function VoicePickerDialog({
  selectedId,
  voices,
  onSelect,
  onClose,
}: VoicePickerDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Close on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  // Close on Escape
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      audioRef.current?.pause();
    };
  }, []);

  const togglePlay = (voice: VoiceInfo) => {
    if (playingId === voice.id) {
      audioRef.current?.pause();
      setPlayingId(null);
    } else {
      audioRef.current?.pause();
      const audio = new Audio(voice.audio_url);
      audio.onended = () => setPlayingId(null);
      audio.onerror = () => setPlayingId(null);
      audio.play();
      audioRef.current = audio;
      setPlayingId(voice.id);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        ref={dialogRef}
        className="relative mx-4 flex max-h-[85vh] w-full max-w-md flex-col rounded-2xl border border-border bg-background shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-sm font-semibold text-foreground">语音音色</h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground"
          >
            <X size={16} />
          </button>
        </div>

        {/* Voice list */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="flex flex-col gap-3">
            {voices.map((voice) => {
              const isSelected = voice.id === selectedId;
              const isPlaying = playingId === voice.id;
              return (
                <div
                  key={voice.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelect(voice.id)}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onSelect(voice.id); }}
                  className={`cursor-pointer rounded-xl border p-4 transition-all ${
                    isSelected
                      ? "border-accent ring-1 ring-accent"
                      : "border-border hover:border-accent/50"
                  }`}
                >
                  {/* Single row: name + trait left, play button right */}
                  <div className="flex items-center">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground">
                        {voice.name}
                        <span className="ml-1 text-xs font-normal text-muted-foreground">
                          （{voice.gender === "female" ? "女性" : "男性"}）
                        </span>
                      </span>
                      <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                        {voice.trait}
                      </span>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); togglePlay(voice); }}
                      className="ml-auto flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    >
                      {isPlaying ? (
                        <Pause size={12} />
                      ) : (
                        <Play size={12} />
                      )}
                      {isPlaying ? "暂停" : "试听"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
