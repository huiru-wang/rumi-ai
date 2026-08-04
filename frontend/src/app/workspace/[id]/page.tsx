"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, FileText, Mic, Package } from "lucide-react";
import { getWorkspace, listPptStyles, listVoices, type Workspace, type Task, type PptStyleInfo, type VoiceInfo } from "@/lib/api";
import { ThreePanel } from "@/components/layout/three-panel";
import { ChatPanel } from "@/components/chat/chat-panel";
import { DocumentPanel } from "@/components/document/document-panel";
import { TaskPanel } from "@/components/task/task-panel";
import { ConfigPanel } from "@/components/config/config-panel";
import { PPTPlayerDialog } from "@/components/player/ppt-player-dialog";
import { PPTPreviewDialog } from "@/components/player/ppt-preview-dialog";
import { StyleExtractionDialog } from "@/components/config/style-extraction-dialog";
import { ThemeToggle } from "@/components/theme-toggle";
import { GithubLink } from "@/components/github-link";
import { BetaInfo } from "@/components/beta-info";
import type { ExternalCommand } from "@/components/chat/assistant";

export default function WorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.id as string;
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);
  const [rightDrawerOpen, setRightDrawerOpen] = useState(false);
  const [pptStyle, setPptStyle] = useState("sys-swiss-modern");
  const [voiceId, setVoiceId] = useState("Cherry");
  const [currentPptTaskId, setCurrentPptTaskId] = useState("");
  const [externalCommand, setExternalCommand] = useState<ExternalCommand | null>(null);
  const [playerData, setPlayerData] = useState<{ narrationTask: Task; pptTask: Task } | null>(null);
  const [previewTask, setPreviewTask] = useState<Task | null>(null);
  const [pptStyles, setPptStyles] = useState<PptStyleInfo[]>([]);
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [styleExtractionTaskId, setStyleExtractionTaskId] = useState<string | null>(null);

  useEffect(() => {
    getWorkspace(workspaceId)
      .then((ws) => {
        setWorkspace(ws);
        // Read config from ext_data
        const ext = ws.ext_data ?? {};
        if (ext.ppt_style) setPptStyle(ext.ppt_style as string);
        // voice_id is stored inside voice_info.id
        const voiceInfo = ext.voice_info as { id?: string } | undefined;
        if (voiceInfo?.id) setVoiceId(voiceInfo.id);
        // Fetch PPT styles for this user
        listPptStyles(ws.user_id).then(setPptStyles).catch(() => {});
        // Fetch available voices
        listVoices().then(setVoices).catch(() => {});
      })
      .catch(() => router.push("/"));
  }, [workspaceId, router]);

  const handleConfigChange = useCallback((key: string, value: string) => {
    if (key === "ppt_style") setPptStyle(value);
    if (key === "voice_id") setVoiceId(value);
  }, []);

  const handleNarrate = useCallback((taskId: string, title: string) => {
    setCurrentPptTaskId(taskId);
    setExternalCommand({
      command: "/narrate",
      label: "生成口播稿",
      icon: <Mic size={14} />,
      subtitle: title,
      metadata: { pptTaskId: taskId },
    });
  }, []);

  const handlePptTaskIdConsumed = useCallback(() => {
    setCurrentPptTaskId("");
  }, []);

  const handleExternalCommandConsumed = useCallback(() => {
    setExternalCommand(null);
  }, []);

  const handlePlayNarration = useCallback((narrationTask: Task, pptTask: Task) => {
    setPlayerData({ narrationTask, pptTask });
  }, []);

  const handlePreview = useCallback((task: Task) => {
    setPreviewTask(task);
  }, []);

  const handleViewStyleExtraction = useCallback((task: Task) => {
    setStyleExtractionTaskId(task.id);
  }, []);

  const refreshPptStyles = useCallback(() => {
    if (workspace) {
      listPptStyles(workspace.user_id).then(setPptStyles).catch(() => {});
    }
  }, [workspace]);

  // Mobile drawer: body scroll lock + ESC close
  useEffect(() => {
    const anyOpen = leftDrawerOpen || rightDrawerOpen;
    document.body.style.overflow = anyOpen ? "hidden" : "";
    if (!anyOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setLeftDrawerOpen(false); setRightDrawerOpen(false); }
    };
    document.addEventListener("keydown", handleKey);
    return () => { document.body.style.overflow = ""; document.removeEventListener("keydown", handleKey); };
  }, [leftDrawerOpen, rightDrawerOpen]);

  if (!workspace) {
    return (
      <div className="flex h-screen items-center justify-center text-muted-foreground">
        加载中...
      </div>
    );
  }

  const rightPanel = (
    <div className="flex h-full flex-col">
      <ConfigPanel
        workspaceId={workspaceId}
        userId={workspace.user_id}
        pptStyle={pptStyle}
        voiceId={voiceId}
        styles={pptStyles}
        voices={voices}
        onConfigChange={handleConfigChange}
        onStyleSaved={refreshPptStyles}
      />
      <div className="min-h-0 flex-1 overflow-hidden">
        <TaskPanel workspaceId={workspaceId} styles={pptStyles} voices={voices} onNarrate={handleNarrate} onPlayNarration={handlePlayNarration} onPreview={handlePreview} onViewStyleExtraction={handleViewStyleExtraction} />
      </div>
    </div>
  );

  return (
    <div className="flex h-screen flex-col">
      {/* Workspace Header */}
      <header className="flex h-[61px] shrink-0 items-center gap-3 border-b border-border px-8">
        <button
          onClick={() => router.push("/")}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft size={18} />
        </button>
        {/* Mobile: left drawer button */}
        <button
          onClick={() => { setRightDrawerOpen(false); setLeftDrawerOpen(true); }}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-foreground md:hidden"
          title="知识库"
        >
          <FileText size={16} />
        </button>
        <div className="flex min-w-0 items-center gap-2">
          <svg viewBox="0 0 120 120" className="h-7 w-7 shrink-0 text-logo-primary" aria-hidden="true">
            <path d="M60,22 C82,22 100,40 100,62 C100,84 82,102 60,102 C45,102 32,94 25,82" stroke="currentColor" strokeWidth="5" fill="none" strokeLinecap="round"/>
            <path d="M60,42 C71,42 80,51 80,62 C80,73 71,82 60,82 C52,82 46,78 43,72" stroke="#C75B3A" strokeWidth="4" fill="none" strokeLinecap="round"/>
            <circle cx="60" cy="62" r="4" fill="currentColor"/>
          </svg>
          <span className="truncate text-lg font-semibold text-foreground">
            {workspace.name}
          </span>
          <BetaInfo />
        </div>
        <div className="ml-auto flex items-center gap-1">
          {/* Mobile: right drawer button */}
          <button
            onClick={() => { setLeftDrawerOpen(false); setRightDrawerOpen(true); }}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-foreground md:hidden"
            title="配置与产出"
          >
            <Package size={16} />
          </button>
          <ThemeToggle />
          <GithubLink />
        </div>
      </header>

      {/* Desktop: Three-Panel Layout */}
      <div className="hidden flex-1 overflow-hidden md:block">
        <ThreePanel
          left={<DocumentPanel workspaceId={workspaceId} />}
          center={<ChatPanel workspaceId={workspaceId} pptStyle={pptStyle} voiceId={voiceId} currentPptTaskId={currentPptTaskId} onPptTaskIdConsumed={handlePptTaskIdConsumed} externalCommand={externalCommand} onExternalCommandConsumed={handleExternalCommandConsumed} />}
          right={rightPanel}
          rightCollapsed={rightCollapsed}
          onRightToggle={() => setRightCollapsed((v) => !v)}
        />
      </div>

      {/* Mobile: Chat only */}
      <div className="flex-1 overflow-hidden md:hidden">
        <ChatPanel workspaceId={workspaceId} pptStyle={pptStyle} voiceId={voiceId} currentPptTaskId={currentPptTaskId} onPptTaskIdConsumed={handlePptTaskIdConsumed} externalCommand={externalCommand} onExternalCommandConsumed={handleExternalCommandConsumed} />
      </div>

      {/* Mobile: Left drawer (knowledge base) */}
      {leftDrawerOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setLeftDrawerOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-[85vw] max-w-[360px] border-r border-border bg-background shadow-xl animate-[slide-in-left_0.25s_ease-out]">
            <DocumentPanel workspaceId={workspaceId} />
          </div>
        </div>
      )}

      {/* Mobile: Right drawer (config & output) */}
      {rightDrawerOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setRightDrawerOpen(false)} />
          <div className="absolute inset-y-0 right-0 w-[85vw] max-w-[360px] border-l border-border bg-background shadow-xl animate-[slide-in-right_0.25s_ease-out]">
            {rightPanel}
          </div>
        </div>
      )}

      {/* PPT Player Dialog */}
      {playerData && (
        <PPTPlayerDialog
          workspaceId={workspaceId}
          narrationTask={playerData.narrationTask}
          pptTask={playerData.pptTask}
          onClose={() => setPlayerData(null)}
        />
      )}

      {/* PPT Preview Dialog */}
      {previewTask && (
        <PPTPreviewDialog
          workspaceId={workspaceId}
          pptTask={previewTask}
          styles={pptStyles}
          onClose={() => setPreviewTask(null)}
        />
      )}

      {/* Style Extraction Dialog */}
      {styleExtractionTaskId && (
        <StyleExtractionDialog
          workspaceId={workspaceId}
          userId={workspace.user_id}
          taskId={styleExtractionTaskId}
          onClose={() => setStyleExtractionTaskId(null)}
          onSaved={refreshPptStyles}
        />
      )}
    </div>
  );
}
