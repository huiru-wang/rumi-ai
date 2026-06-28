"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { AlertCircle, ChevronLeft, ChevronRight, Loader2, Pause, Play, Volume2, VolumeX } from "lucide-react";
import { fetchFileContent, getShareDetail, type ShareDetail, type ShareSlide } from "@/lib/api";

const NAV_SCRIPT = `
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

export default function SharePage() {
  const params = useParams();
  const token = params.token as string;
  const [detail, setDetail] = useState<ShareDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await getShareDetail(token);
        if (!cancelled) setDetail(data);
      } catch {
        if (!cancelled) setError("分享链接不存在或已失效");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [token]);

  useEffect(() => {
    if (detail?.ppt.title) {
      document.title = detail.ppt.title;
    }
  }, [detail?.ppt.title]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        <div className="flex items-center gap-2 text-sm">
          <Loader2 size={18} className="animate-spin" />
          加载分享内容...
        </div>
      </main>
    );
  }

  if (error || !detail) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-sm rounded-xl border border-border bg-muted/30 p-6 text-center">
          <AlertCircle size={28} className="mx-auto text-red-400" />
          <h1 className="mt-3 text-sm font-semibold text-foreground">分享不可用</h1>
          <p className="mt-2 text-xs text-muted-foreground">分享链接不存在或已失效。</p>
        </div>
      </main>
    );
  }

  if (detail.type === "narration" && detail.narration) {
    return <SharedNarrationPlayer detail={detail} />;
  }

  return <SharedPPTViewer detail={detail} />;
}

function SharedPPTViewer({ detail }: { detail: ShareDetail }) {
  return (
    <main className="flex h-screen flex-col bg-background">
      <header className="flex items-center border-b border-border px-4 py-2.5">
        <div className="min-w-0">
          <h1 className="truncate text-sm font-medium text-foreground">{detail.ppt.title}</h1>
          <p className="text-[10px] text-muted-foreground">只读分享</p>
        </div>
      </header>
      <div className="min-h-0 flex-1 bg-black">
        <iframe
          src={detail.ppt.html_url}
          sandbox="allow-scripts"
          className="h-full w-full border-0"
          title={detail.ppt.title}
        />
      </div>
    </main>
  );
}

function SharedNarrationPlayer({ detail }: { detail: ShareDetail }) {
  const [pptHtml, setPptHtml] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isFrameReady, setIsFrameReady] = useState(false);
  const [error, setError] = useState("");
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [durations, setDurations] = useState<number[]>([]);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);

  const iframeRef = useRef<HTMLIFrameElement>(null);
  const audioRefs = useRef<(HTMLAudioElement | null)[]>([]);
  const rafRef = useRef<number>(0);
  const currentSlideRef = useRef(0);
  const isPlayingRef = useRef(false);
  const slides = detail.narration?.slides ?? [];

  useEffect(() => { currentSlideRef.current = currentSlide; }, [currentSlide]);
  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const html = await fetchFileContent(detail.ppt.html_url);
        if (cancelled) return;
        setIsFrameReady(false);
        setPptHtml(html.replace("</body>", `<script>${NAV_SCRIPT}</script></body>`));
        setDurations(new Array(slides.length).fill(0));
      } catch {
        if (!cancelled) setError("加载播放内容失败");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
      cancelAnimationFrame(rafRef.current);
      audioRefs.current.forEach((audio) => audio?.pause());
    };
  }, [detail.ppt.html_url, slides.length]);

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

  const playAudioAt = useCallback((index: number) => {
    if (!isFrameReady) {
      isPlayingRef.current = false;
      setIsPlaying(false);
      return;
    }
    const audio = audioRefs.current[index];
    stopProgressLoop();
    if (!audio?.src) {
      isPlayingRef.current = false;
      setIsPlaying(false);
      setCurrentProgress(0);
      return;
    }
    audio.play()
      .then(() => {
        isPlayingRef.current = true;
        setIsPlaying(true);
        startProgressLoop();
      })
      .catch(() => {
        isPlayingRef.current = false;
        setIsPlaying(false);
        stopProgressLoop();
      });
  }, [isFrameReady, startProgressLoop, stopProgressLoop]);

  const navigateToSlide = useCallback((index: number) => {
    audioRefs.current[currentSlideRef.current]?.pause();
    stopProgressLoop();
    currentSlideRef.current = index;
    setCurrentSlide(index);
    setCurrentProgress(0);
    iframeRef.current?.contentWindow?.postMessage({ type: "navigate-slide", index }, "*");
  }, [stopProgressLoop]);

  const play = useCallback(() => {
    playAudioAt(currentSlideRef.current);
  }, [playAudioAt]);

  const pause = useCallback(() => {
    audioRefs.current[currentSlideRef.current]?.pause();
    isPlayingRef.current = false;
    setIsPlaying(false);
    stopProgressLoop();
  }, [stopProgressLoop]);

  const goPrev = useCallback(() => {
    if (currentSlideRef.current > 0) {
      const wasPlaying = isPlayingRef.current;
      const next = currentSlideRef.current - 1;
      navigateToSlide(next);
      if (wasPlaying) playAudioAt(next);
    }
  }, [navigateToSlide, playAudioAt]);

  const goNext = useCallback(() => {
    if (currentSlideRef.current < slides.length - 1) {
      const wasPlaying = isPlayingRef.current;
      const next = currentSlideRef.current + 1;
      navigateToSlide(next);
      if (wasPlaying) playAudioAt(next);
    }
  }, [navigateToSlide, playAudioAt, slides.length]);

  const jumpToSlide = useCallback((index: number) => {
    if (!isFrameReady) return;
    const wasPlaying = isPlayingRef.current;
    navigateToSlide(index);
    if (wasPlaying) {
      playAudioAt(index);
    }
  }, [isFrameReady, navigateToSlide, playAudioAt]);

  const handleEnded = useCallback((index: number) => {
    stopProgressLoop();
    if (index < slides.length - 1) {
      const next = index + 1;
      navigateToSlide(next);
      if (isPlayingRef.current) {
        playAudioAt(next);
      }
    } else {
      isPlayingRef.current = false;
      setIsPlaying(false);
      setCurrentProgress(0);
    }
  }, [navigateToSlide, playAudioAt, slides.length, stopProgressLoop]);

  const totalDuration = durations.reduce((sum, item) => sum + item, 0);
  const isPlaybackReady = isFrameReady && !!pptHtml && slides.length > 0;

  if (isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        <div className="flex items-center gap-2 text-sm">
          <Loader2 size={18} className="animate-spin" />
          加载播放内容...
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-sm rounded-xl border border-border bg-muted/30 p-6 text-center">
          <AlertCircle size={28} className="mx-auto text-red-400" />
          <p className="mt-3 text-sm text-foreground">{error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex h-screen flex-col bg-background">
      <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="min-w-0">
          <h1 className="truncate text-sm font-medium text-foreground">{detail.ppt.title}</h1>
          <p className="text-[10px] text-muted-foreground">
            第 {currentSlide + 1} / {slides.length} 页 · {detail.narration?.voice_name || "分享播放"}
          </p>
        </div>
      </header>

      <div className="relative min-h-0 flex-1 bg-black">
        {pptHtml && (
          <iframe
            ref={iframeRef}
            srcDoc={pptHtml}
            sandbox="allow-scripts"
            className="absolute inset-0 h-full w-full border-0"
            title={detail.ppt.title}
            onLoad={() => {
              setIsFrameReady(true);
              iframeRef.current?.contentWindow?.postMessage({ type: "navigate-slide", index: currentSlideRef.current }, "*");
            }}
          />
        )}
        {!isFrameReady && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/70 text-muted-foreground">
            <div className="flex items-center gap-2 text-sm">
              <Loader2 size={18} className="animate-spin" />
              加载播放画面...
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-border bg-background px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="min-w-[96px]" />
          <div className="flex items-center gap-3">
            <button
              onClick={goPrev}
              disabled={!isPlaybackReady || currentSlide <= 0}
              className="rounded-lg p-2 text-muted-foreground hover:text-foreground disabled:opacity-30"
              title="上一页"
            >
              <ChevronLeft size={18} />
            </button>
            <button
              onClick={isPlaying ? pause : play}
              disabled={!isPlaybackReady}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-accent/20 text-accent hover:bg-accent/30 disabled:opacity-30"
              title={isPlaying ? "暂停" : "播放"}
            >
              {isPlaying ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
            </button>
            <button
              onClick={goNext}
              disabled={!isPlaybackReady || currentSlide >= slides.length - 1}
              className="rounded-lg p-2 text-muted-foreground hover:text-foreground disabled:opacity-30"
              title="下一页"
            >
              <ChevronRight size={18} />
            </button>
          </div>
          <div className="flex min-w-[96px] items-center justify-end gap-1">
            <button
              onClick={() => {
                const next = !isMuted;
                setIsMuted(next);
                audioRefs.current.forEach((audio) => { if (audio) audio.volume = next ? 0 : volume; });
              }}
              className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground"
              title={isMuted ? "取消静音" : "静音"}
            >
              {isMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={isMuted ? 0 : volume}
              onChange={(event) => {
                const next = parseFloat(event.target.value);
                setVolume(next);
                setIsMuted(next === 0);
                audioRefs.current.forEach((audio) => { if (audio) audio.volume = next; });
              }}
              className="h-1 w-16 cursor-pointer accent-accent"
              title="音量"
            />
          </div>
        </div>

        {slides.length > 0 && (
          <div className="mt-3 flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full">
            {slides.map((slide: ShareSlide, index) => {
              const widthPct = totalDuration > 0 ? ((durations[index] || 0) / totalDuration) * 100 : 100 / slides.length;
              const isActive = index === currentSlide;
              const isDone = index < currentSlide;
              return (
                <div
                  key={`${slide.number}-${index}`}
                  className={`relative h-full transition-opacity ${
                    isPlaybackReady ? "cursor-pointer hover:opacity-80" : "cursor-not-allowed opacity-60"
                  }`}
                  style={{ width: `${widthPct}%`, minWidth: "3px" }}
                  onClick={() => jumpToSlide(index)}
                  aria-label={`第 ${index + 1} 页进度`}
                  title={`第 ${index + 1} 页${durations[index] > 0 ? ` (${durations[index].toFixed(1)}s)` : ""}`}
                >
                  <span className={`absolute inset-0 rounded-sm ${isDone ? "bg-accent" : "bg-muted/60"}`} />
                  {isActive && (
                    <span
                      className="absolute inset-y-0 left-0 rounded-sm bg-accent/70"
                      style={{ width: `${Math.min(currentProgress * 100, 100)}%` }}
                    />
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {slides.map((slide, index) => (
        <audio
          key={`${slide.number}-${index}-audio`}
          ref={(el) => { audioRefs.current[index] = el; }}
          src={slide.has_audio ? slide.audio_url : undefined}
          preload="metadata"
          onEnded={() => handleEnded(index)}
          onLoadedMetadata={(event) => {
            const duration = event.currentTarget.duration;
            if (!isFinite(duration)) return;
            setDurations((prev) => {
              const next = [...prev];
              next[index] = duration;
              return next;
            });
          }}
        />
      ))}
    </main>
  );
}
