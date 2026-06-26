"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { X, Play, Pause, ChevronLeft, ChevronRight, Loader2, AlertCircle, Volume2, VolumeX, Maximize, Minimize } from "lucide-react";
import { fetchFileContent, getFileViewUrl, type Task } from "@/lib/api";

const NAV_SCRIPT = `
/* Lock down: disable all manual interaction */
document.documentElement.style.overflow = 'hidden';
document.documentElement.style.scrollSnapType = 'none';
document.body.style.overflow = 'hidden';
document.body.style.pointerEvents = 'none';
document.addEventListener('keydown', function(e) { e.preventDefault(); e.stopPropagation(); }, true);
document.addEventListener('wheel', function(e) { e.preventDefault(); }, { passive: false, capture: true });
document.addEventListener('touchmove', function(e) { e.preventDefault(); }, { passive: false, capture: true });
document.addEventListener('touchstart', function(e) { e.preventDefault(); }, { passive: false, capture: true });

window.addEventListener('message', function(e) {
  if (e.data && e.data.type === 'navigate-slide') {
    var slides = document.querySelectorAll('.slide');
    slides.forEach(function(s, i) {
      s.classList.add('visible');
      s.style.display = (i === e.data.index) ? '' : 'none';
    });
  }
});
`;

interface SlideData {
  number: number;
  title: string;
  audioUrl: string;
  hasAudio: boolean;
}

interface PPTPlayerDialogProps {
  workspaceId: string;
  narrationTask: Task;
  pptTask: Task;
  onClose: () => void;
}

export function PPTPlayerDialog({ workspaceId, narrationTask, pptTask, onClose }: PPTPlayerDialogProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pptHtml, setPptHtml] = useState("");
  const [slides, setSlides] = useState<SlideData[]>([]);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [durations, setDurations] = useState<number[]>([]);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);

  const audioRefs = useRef<(HTMLAudioElement | null)[]>([]);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);
  const isPlayingRef = useRef(false);
  const currentSlideRef = useRef(0);

  // Keep refs in sync with state
  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);
  useEffect(() => { currentSlideRef.current = currentSlide; }, [currentSlide]);

  // Initialize: load PPT HTML and narration slide data
  useEffect(() => {
    let cancelled = false;

    const init = async () => {
      try {
        const pptResult = JSON.parse(pptTask.result_data || "{}");
        const narrResult = JSON.parse(narrationTask.result_data || "{}");

        if (!pptResult.file_path) {
          throw new Error("PPT 文件路径缺失");
        }

        const pptFileUrl = getFileViewUrl(pptResult.file_path);
        const html = await fetchFileContent(pptFileUrl);
        if (cancelled) return;

        const injectedHtml = html.replace("</body>", `<script>${NAV_SCRIPT}</script></body>`);
        setPptHtml(injectedHtml);

        const narrSlides: SlideData[] = (narrResult.slides || []).map((s: { number?: number; title?: string; audio_path?: string | null }) => ({
          number: s.number || 0,
          title: s.title || "",
          audioUrl: s.audio_path ? getFileViewUrl(s.audio_path) : "",
          hasAudio: !!s.audio_path,
        }));
        setSlides(narrSlides);
        setDurations(new Array(narrSlides.length).fill(0));
        setIsLoading(false);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "加载失败");
          setIsLoading(false);
        }
      }
    };

    init();
    return () => { cancelled = true; };
  }, [pptTask, narrationTask]);

  // ESC: exit fullscreen first if active, otherwise close dialog; space: toggle play/pause
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (document.fullscreenElement) return; // browser exits fullscreen
        onClose();
      }
      if (e.key === " ") {
        e.preventDefault();
        if (isPlayingRef.current) pause(); else play();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onClose]);

  // Sync isFullscreen with browser fullscreen state
  useEffect(() => {
    const handleChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", handleChange);
    return () => document.removeEventListener("fullscreenchange", handleChange);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cancelAnimationFrame(rafRef.current);
      audioRefs.current.forEach((a) => { try { a?.pause(); } catch { /* ignore */ } });
    };
  }, []);

  // --- Playback helpers ---

  const stopProgressLoop = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
  }, []);

  const startProgressLoop = useCallback(() => {
    const tick = () => {
      const audio = audioRefs.current[currentSlideRef.current];
      if (audio && audio.duration && isFinite(audio.duration)) {
        setCurrentProgress(audio.currentTime / audio.duration);
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  }, []);

  const play = useCallback(() => {
    const audio = audioRefs.current[currentSlideRef.current];
    if (audio?.src) {
      audio.play().catch(() => { /* autoplay may be blocked */ });
    }
    setIsPlaying(true);
    startProgressLoop();
  }, [startProgressLoop]);

  const pause = useCallback(() => {
    const audio = audioRefs.current[currentSlideRef.current];
    try { audio?.pause(); } catch { /* ignore */ }
    setIsPlaying(false);
    stopProgressLoop();
  }, [stopProgressLoop]);

  const navigateToSlide = useCallback((index: number) => {
    const prevAudio = audioRefs.current[currentSlideRef.current];
    try { prevAudio?.pause(); } catch { /* ignore */ }
    stopProgressLoop();

    currentSlideRef.current = index;
    setCurrentSlide(index);
    setCurrentProgress(0);

    iframeRef.current?.contentWindow?.postMessage({ type: "navigate-slide", index }, "*");
  }, [stopProgressLoop]);

  const handleEnded = useCallback((slideIndex: number) => {
    stopProgressLoop();
    if (slideIndex < slides.length - 1) {
      const next = slideIndex + 1;
      navigateToSlide(next);
      if (isPlayingRef.current) {
        const audio = audioRefs.current[next];
        if (audio?.src) {
          audio.play().catch(() => { /* ignore */ });
        }
        startProgressLoop();
      }
    } else {
      isPlayingRef.current = false;
      setIsPlaying(false);
      setCurrentProgress(0);
    }
  }, [slides.length, navigateToSlide, startProgressLoop, stopProgressLoop]);

  const handleLoadedMetadata = useCallback((index: number, duration: number) => {
    setDurations((prev) => {
      const next = [...prev];
      next[index] = duration;
      return next;
    });
  }, []);

  const goPrev = useCallback(() => {
    if (currentSlideRef.current > 0) {
      const wasPlaying = isPlayingRef.current;
      navigateToSlide(currentSlideRef.current - 1);
      if (wasPlaying) {
        const audio = audioRefs.current[currentSlideRef.current];
        if (audio?.src) {
          audio.play().catch(() => { /* ignore */ });
        }
        startProgressLoop();
      }
    }
  }, [navigateToSlide, startProgressLoop]);

  const goNext = useCallback(() => {
    if (currentSlideRef.current < slides.length - 1) {
      const wasPlaying = isPlayingRef.current;
      navigateToSlide(currentSlideRef.current + 1);
      if (wasPlaying) {
        const audio = audioRefs.current[currentSlideRef.current];
        if (audio?.src) {
          audio.play().catch(() => { /* ignore */ });
        }
        startProgressLoop();
      }
    }
  }, [slides.length, navigateToSlide, startProgressLoop]);

  const toggleFullscreen = useCallback(() => {
    if (!dialogRef.current) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      dialogRef.current.requestFullscreen();
    }
  }, []);

  const handleVolumeChange = useCallback((val: number) => {
    setVolume(val);
    setIsMuted(val === 0);
    audioRefs.current.forEach((a) => { if (a) a.volume = val; });
  }, []);

  const toggleMute = useCallback(() => {
    const next = !isMuted;
    setIsMuted(next);
    audioRefs.current.forEach((a) => { if (a) a.volume = next ? 0 : volume; });
  }, [isMuted, volume]);

  // --- Derived values ---

  const totalDuration = durations.reduce((a, b) => a + b, 0);
  const hasSlides = slides.length > 0;

  // --- Render ---

  if (error) {
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
        onClick={onClose}
      >
        <div
          className="mx-4 w-full max-w-md rounded-2xl border border-border bg-background p-6 text-center"
          onClick={(e) => e.stopPropagation()}
        >
          <AlertCircle size={32} className="mx-auto text-red-400" />
          <p className="mt-3 text-sm text-foreground">加载失败</p>
          <p className="mt-1 text-xs text-muted-foreground">{error}</p>
          <button
            onClick={onClose}
            className="mt-4 rounded-lg bg-accent/20 px-4 py-1.5 text-xs text-accent hover:bg-accent/30"
          >
            关闭
          </button>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <Loader2 size={28} className="animate-spin" />
          <p className="text-xs">加载 PPT 和音频数据...</p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={dialogRef}
      className={`flex flex-col bg-background ${
        isFullscreen
          ? "h-screen w-screen"
          : "fixed inset-0 z-50 items-center justify-center bg-black/80"
      }`}
      onClick={isFullscreen ? undefined : onClose}
    >
      <div
        className={`flex flex-col overflow-hidden ${
          isFullscreen
            ? "h-full w-full"
            : "max-h-[90vh] w-full max-w-5xl rounded-2xl border border-border shadow-2xl"
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 bg-black/40 px-4 py-2.5 backdrop-blur-md">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-foreground">
              {pptTask.title || "PPT 播放"}
            </p>
            <p className="text-[10px] text-muted-foreground">
              第 {currentSlide + 1} / {slides.length} 页
            </p>
          </div>
          <button
            onClick={onClose}
            className="ml-3 flex-shrink-0 rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground"
            title="关闭 (ESC)"
          >
            <X size={16} />
          </button>
        </div>

        {/* PPT Area — 16:9 normally, flex-1 in fullscreen */}
        <div className={`relative w-full bg-black ${isFullscreen ? "min-h-0 flex-1" : "aspect-video"}`}>
          {pptHtml && (
            <iframe
              ref={iframeRef}
              srcDoc={pptHtml}
              className="absolute inset-0 h-full w-full border-0"
              title="PPT Presentation"
              sandbox="allow-scripts"
            />
          )}
        </div>

        {/* Controls */}
        <div className="border-t border-white/10 bg-black/40 px-4 py-2.5 backdrop-blur-md">
          {/* Playback buttons + volume + fullscreen */}
          <div className="flex items-center justify-between">
            {/* Left spacer (balances right side) */}
            <div className="flex items-center gap-1 min-w-[100px]" />

            {/* Center: prev / play-pause / next */}
            <div className="flex items-center gap-3">
              <button
                onClick={goPrev}
                disabled={currentSlide <= 0}
                className="rounded-lg p-2 text-muted-foreground transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-30"
                title="上一页"
              >
                <ChevronLeft size={18} />
              </button>
              <button
                onClick={isPlaying ? pause : play}
                disabled={!hasSlides}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-accent/20 text-accent transition-colors hover:bg-accent/30 disabled:opacity-30"
                title={isPlaying ? "暂停 (空格)" : "播放 (空格)"}
              >
                {isPlaying ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
              </button>
              <button
                onClick={goNext}
                disabled={currentSlide >= slides.length - 1}
                className="rounded-lg p-2 text-muted-foreground transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-30"
                title="下一页"
              >
                <ChevronRight size={18} />
              </button>
            </div>

            {/* Right: volume + fullscreen */}
            <div className="flex items-center gap-1 min-w-[100px] justify-end">
              {/* Mute toggle */}
              <button
                onClick={toggleMute}
                className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground"
                title={isMuted ? "取消静音" : "静音"}
              >
                {isMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
              </button>
              {/* Volume slider */}
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={isMuted ? 0 : volume}
                onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                className="h-1 w-16 cursor-pointer accent-accent"
                title={`音量 ${Math.round((isMuted ? 0 : volume) * 100)}%`}
              />
              {/* Fullscreen toggle */}
              <button
                onClick={toggleFullscreen}
                className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground"
                title={isFullscreen ? "退出全屏" : "全屏"}
              >
                {isFullscreen ? <Minimize size={16} /> : <Maximize size={16} />}
              </button>
            </div>
          </div>

          {/* Segmented progress bar */}
          {hasSlides && (
            <div className="mt-3 flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full">
              {durations.map((dur, i) => {
                const widthPct = totalDuration > 0 ? (dur / totalDuration) * 100 : 100 / slides.length;
                const isActive = i === currentSlide;
                const isDone = i < currentSlide;
                return (
                  <div
                    key={i}
                    className="relative h-full cursor-pointer transition-opacity hover:opacity-80"
                    style={{ width: `${widthPct}%`, minWidth: "3px" }}
                    onClick={() => {
                      const wasPlaying = isPlayingRef.current;
                      navigateToSlide(i);
                      if (wasPlaying) {
                        const audio = audioRefs.current[i];
                        if (audio?.src) {
                          audio.play().catch(() => { /* ignore */ });
                        }
                        startProgressLoop();
                      }
                    }}
                    title={`第 ${i + 1} 页${dur > 0 ? ` (${dur.toFixed(1)}s)` : ""}`}
                  >
                    {/* Background */}
                    <div className={`absolute inset-0 rounded-sm ${isDone ? "bg-accent" : "bg-muted/60"}`} />
                    {/* Current progress fill */}
                    {isActive && (
                      <div
                        className="absolute inset-y-0 left-0 rounded-sm bg-accent/70 transition-none"
                        style={{ width: `${Math.min(currentProgress * 100, 100)}%` }}
                      />
                    )}
                    {/* Hover highlight */}
                    <div className="absolute inset-0 rounded-sm bg-white/0 transition-colors hover:bg-white/10" />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Hidden audio elements */}
      {slides.map((slide, i) => (
        <audio
          key={i}
          ref={(el) => { audioRefs.current[i] = el; }}
          src={slide.hasAudio ? slide.audioUrl : undefined}
          onEnded={() => handleEnded(i)}
          onLoadedMetadata={(e) => {
            const dur = e.currentTarget.duration;
            if (isFinite(dur)) handleLoadedMetadata(i, dur);
          }}
          preload="metadata"
        />
      ))}
    </div>
  );
}
