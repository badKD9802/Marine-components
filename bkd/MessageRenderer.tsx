import React, { useRef } from "react";
import { Box } from "@mui/material";
import { parseMessageContent } from "@/utils/parseAnswerContent";
import ThinkingBlock from "./ThinkingBlock";
import ExcelStreamTable from "./ExcelStreamTable";
import MarkdownViewer from "../MarkdownViewer/MarkdownViewer";
import Lottie from "lottie-react";
import typing from "@/assets/lotties/typing.json";

const decodeHtmlEntities = (text: string): string => {
  const textarea = document.createElement("textarea");
  textarea.innerHTML = text;
  return textarea.value;
};

const cursorStyle = {
  "&::after": {
    content: '""',
    display: "inline-block",
    width: "2px",
    height: "1em",
    backgroundColor: "var(--primary-500, #6366f1)",
    marginLeft: "2px",
    verticalAlign: "text-bottom",
    animation: "blink 1s step-end infinite",
  },
  "@keyframes blink": {
    "0%, 100%": { opacity: 1 },
    "50%": { opacity: 0 },
  },
} as const;

interface MessageRendererProps {
  content: string;
  isStreaming?: boolean;
  showRawToggle?: boolean;
}

const MessageRenderer: React.FC<MessageRendererProps> = ({
  content,
  isStreaming = false,
  showRawToggle = false,
}) => {
  const [showRaw, setShowRaw] = React.useState(false);
  const parsed = parseMessageContent(content, isStreaming);
  const lastLegacyRef = useRef<string | null>(null);

  const isLegacyOrStatusHtml =
    content.includes("animated-details") ||
    content.includes("<details") ||
    content.includes("status-box") ||
    content.includes("spinner");

  const hasCustomTags =
    /<(cot|reasoning|answer|retrieval-progress|retrieval-summary|agent-progress|agent-summary)/i.test(
      content
    );

  // ✅ content가 비어있으면 이전 레거시 캐시 초기화
  if (!content) {
    lastLegacyRef.current = null;
  }

  if (isLegacyOrStatusHtml && !hasCustomTags) {
    lastLegacyRef.current = content;
  }

  const hasRenderable =
    (parsed.cot && parsed.phase === "cot") ||
    (parsed.reasoning && parsed.reasoning.length > 0) ||
    !!parsed.retrieval ||
    !!parsed.retrievalSummary ||
    !!parsed.agent ||
    !!parsed.agentSummary ||
    parsed.phase === "answering" ||
    parsed.phase === "retrieving" ||
    (!parsed.reasoning &&
      !parsed.answer &&
      !parsed.cot &&
      parsed.phase === "complete" &&
      !!content);

  // Raw view
  if (showRaw) {
    return (
      <Box>
        <Box
          onClick={() => setShowRaw(false)}
          sx={{
            fontSize: "11px",
            color: "var(--primary-500)",
            cursor: "pointer",
            textAlign: "right",
            mb: 0.5,
          }}
        >
          렌더 보기
        </Box>
        <Box
          component="pre"
          sx={{
            fontSize: "12px",
            backgroundColor: "var(--basic-50)",
            padding: "12px",
            borderRadius: "8px",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            border: "1px solid var(--basic-200)",
          }}
        >
          {content}
        </Box>
      </Box>
    );
  }

  // 레거시 HTML
  if (isLegacyOrStatusHtml && !hasCustomTags) {
    return <MarkdownViewer content={content} />;
  }

  // 전환 구간
  if (
    isStreaming &&
    !hasRenderable &&
    !hasCustomTags &&
    lastLegacyRef.current
  ) {
    return <MarkdownViewer content={lastLegacyRef.current} />;
  }

  /* ──────────────────────────────────────────
   * 핵심 변경: isThinkingPhase 판단
   * thinking 단계(검색, CoT, reasoning)가 진행 중인지 판단.
   * 답변(answer)이 생성되기 시작하면 false → "생각 완료"로 전환.
   * ────────────────────────────────────────── */
  const isThinkingPhase =
    isStreaming &&
    (parsed.phase === "retrieving" ||
      parsed.phase === "cot" ||
      parsed.phase === "reasoning" ||
      // 아직 아무 것도 안 왔을 때 (시작 직후)
      (parsed.phase === "answering" && !parsed.answer));

  // ThinkingBlock 표시 여부
  const showThinkingBlock =
    isThinkingPhase ||
    !!parsed.cot ||
    (parsed.reasoning && parsed.reasoning.length > 0) ||
    !!parsed.retrieval ||
    !!parsed.retrievalSummary ||
    !!parsed.agent ||
    !!parsed.agentSummary;

  return (
    <Box>
      {showRawToggle && (
        <Box
          onClick={() => setShowRaw(true)}
          sx={{
            fontSize: "11px",
            color: "var(--basic-400)",
            cursor: "pointer",
            textAlign: "right",
            mb: 0.5,
            "&:hover": { color: "var(--primary-500)" },
          }}
        >
          원본 보기
        </Box>
      )}

      {/* ── 통합 ThinkingBlock ── */}
      {showThinkingBlock && (
        <ThinkingBlock
          retrieval={parsed.retrieval}
          retrievalSummary={parsed.retrievalSummary}
          agent={parsed.agent}
          agentSummary={parsed.agentSummary}
          cotText={parsed.cot}
          steps={parsed.reasoning}
          isStreaming={isStreaming}
          isThinkingPhase={isThinkingPhase}
          label="생각 완료"
          streamingLabel="생각중..."
        />
      )}

      {/* ── Answer ── */}
      {parsed.answer ? (
        <Box>
          <MarkdownViewer content={decodeHtmlEntities(parsed.answer)} />
        </Box>
      ) : isStreaming && !parsed.answer && !showThinkingBlock ? (
        <Lottie
          animationData={typing}
          loop={true}
          style={{ width: 70, height: 30, marginTop: "8px", marginLeft: "-10px" }}
        />
      ) : null}

      {/* ── Excel 실시간 테이블 ── */}
      {parsed.excelData.length > 0 && parsed.excelData.map((data, idx) => (
        <ExcelStreamTable key={idx} excelData={data} />
      ))}

      {/* ── 태그 없는 일반 응답 ── */}
      {!parsed.reasoning &&
        !parsed.answer &&
        !parsed.cot &&
        !parsed.retrieval &&
        !parsed.retrievalSummary &&
        !parsed.agent &&
        !parsed.agentSummary &&
        parsed.phase === "complete" &&
        content && <MarkdownViewer content={content} />}
    </Box>
  );
};

export default React.memo(MessageRenderer);
