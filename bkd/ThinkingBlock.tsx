import React, { useState, useEffect, useRef, useMemo } from "react";
import { Box, Collapse } from "@mui/material";
import type { ReasoningStep, RetrievalData, AgentData } from "@/utils/parseAnswerContent";
import RetrievalProgress from "./RetrievalProgress";
import AgentProgress from "./AgentProgress";

interface ThinkingBlockProps {
  cotText?: string | null;
  steps?: ReasoningStep[] | null;
  retrieval?: RetrievalData | null;
  retrievalSummary?: RetrievalData | null;
  agent?: AgentData | null;
  agentSummary?: AgentData | null;
  isStreaming?: boolean;
  isThinkingPhase?: boolean;
  label?: string;
  streamingLabel?: string;
}

const ThinkingBlock: React.FC<ThinkingBlockProps> = ({
  cotText,
  steps,
  retrieval,
  retrievalSummary,
  agent,
  agentSummary,
  isThinkingPhase = false,
  label = "생각 완료",
  streamingLabel = "생각중...",
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const [hadContent, setHadContent] = useState(false);

  const hasRetrieval = !!(retrieval && retrieval.steps && retrieval.steps.length > 0);
  const hasRetrievalSummary = !!(
    retrievalSummary &&
    retrievalSummary.steps &&
    retrievalSummary.steps.length > 0
  );
  const hasAgent = !!(agent && agent.steps && agent.steps.length > 0);
  const hasAgentSummary = !!(agentSummary && agentSummary.steps && agentSummary.steps.length > 0);
  const hasSteps = !!(steps && steps.length > 0);
  const hasCot = !!(cotText && cotText.trim());
  const hasContent = hasSteps || hasCot || hasRetrieval || hasRetrievalSummary || hasAgent || hasAgentSummary;

  const isRetrievalActive = useMemo(() => {
    if (!retrieval || !retrieval.steps) return false;
    return retrieval.steps.some((s) => s.status === "active");
  }, [retrieval]);

  const isAgentActive = useMemo(() => {
    if (!agent || !agent.steps) return false;
    return agent.steps.some((s) => s.status === "active");
  }, [agent]);

  const isThinking = isThinkingPhase || isRetrievalActive || isAgentActive;

  useEffect(() => {
    if (hasContent) setHadContent(true);
  }, [hasContent]);

  useEffect(() => {
    if (isThinking) setIsOpen(true);
  }, [isThinking]);

  useEffect(() => {
    if (!isThinking && hadContent) setIsOpen(false);
  }, [isThinking, hadContent]);

  useEffect(() => {
    if (isThinking && contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [isThinking, steps, cotText, retrieval]);

  if (!hasContent && !hadContent && !isThinking) return null;

  const isExpanded = isOpen;

  const headerLabel = isAgentActive
    ? "작업 수행 중..."
    : (hasAgent || hasAgentSummary) && !isAgentActive
    ? "작업 완료"
    : isRetrievalActive
    ? "검색 중..."
    : isThinking
    ? streamingLabel
    : label;

  return (
    <Box sx={{ mb: "12px", ml: "8px" }}>
      {/* ── 토글 헤더 ── */}
      <Box
        onClick={() => setIsOpen((prev) => !prev)}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: "4px 0",
          cursor: "pointer",
          userSelect: "none",
          width: "fit-content",
        }}
      >
        <Box
          sx={{
            fontSize: "16px",
            fontWeight: "bold",
            whiteSpace: "nowrap",
            fontFamily:
              "system-ui, -apple-system, Roboto, 'Noto Sans KR', sans-serif",
            ...(isThinking
              ? {
                  background:
                    "linear-gradient(90deg, #6B8BF5 0%, #9DB5FF 50%, #6B8BF5 100%)",
                  backgroundSize: "200% 100%",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  animation: "shimmerText 2s ease-in-out infinite",
                  "@keyframes shimmerText": {
                    "0%": { backgroundPosition: "100% 0" },
                    "100%": { backgroundPosition: "-100% 0" },
                  },
                }
              : {
                  color: "#6B8BF5",
                }),
          }}
        >
          {headerLabel}
        </Box>

        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "24px",
            height: "24px",
            ml: "-4px",
            flexShrink: 0,
            transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
            transformOrigin: "center center",
            transition: "transform 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 20 20"
            fill="#8DA0BE"
            style={{
              display: "block",
              strokeWidth: "0.5px",
              stroke: "#8DA0BE",
            }}
          >
            <path
              fillRule="evenodd"
              d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
              clipRule="evenodd"
            />
          </svg>
        </Box>
      </Box>

      {/* ── 내용 ── */}
      <Collapse in={isExpanded}>
        <Box
          sx={{
            mt: "2px",
            ml: "2px",
            border: "1px solid #e0e7f1",
            borderLeft: "4px solid #6B8BF5",
            borderRadius: "12px",
            overflow: "hidden",
          }}
        >
          <Box
            ref={contentRef}
            sx={{
              pl: "12px",
              pr: "8px",
              py: "8px",
              overflowY: "auto",
              fontSize: "14px",
              scrollbarGutter: "stable",
              color: "#374151",
              lineHeight: 1.6,
              "&::-webkit-scrollbar": { width: "4px" },
              "&::-webkit-scrollbar-track": { background: "transparent" },
              "&::-webkit-scrollbar-thumb": {
                background: "rgba(0,0,0,0.1)",
                borderRadius: "4px",
              },
            }}
          >
            {/* ── 1. Retrieval (스트리밍 중) ── */}
            {hasRetrieval && (
              <Box sx={{ mb: hasSteps || hasCot ? "12px" : 0 }}>
                <RetrievalProgress data={retrieval!} />
              </Box>
            )}

            {/* ── 1-b. Retrieval Summary (DB 로드) ── */}
            {hasRetrievalSummary && !hasRetrieval && (
              <Box sx={{ mb: hasSteps || hasCot ? "12px" : 0 }}>
                <RetrievalProgress data={retrievalSummary!} collapsed />
              </Box>
            )}

            {/* ── 1-c. Agent Progress (스트리밍 중, Claude 스타일) ── */}
            {hasAgent && (
              <Box sx={{ mb: hasSteps || hasCot ? "12px" : 0 }}>
                <AgentProgress data={agent!} />
              </Box>
            )}

            {/* ── 1-d. Agent Summary (DB 로드, Claude 스타일) ── */}
            {hasAgentSummary && !hasAgent && (
              <Box sx={{ mb: hasSteps || hasCot ? "12px" : 0 }}>
                <AgentProgress data={agentSummary!} />
              </Box>
            )}

            {/* ── 구분선 ── */}
            {(hasRetrieval || hasRetrievalSummary || hasAgent || hasAgentSummary) && (hasSteps || hasCot) && (
              <Box
                sx={{
                  height: "1px",
                  background:
                    "linear-gradient(to right, rgba(107, 139, 245, 0.25), transparent)",
                  mb: "12px",
                }}
              />
            )}

            {/* ── 2. CoT ── */}
            {hasCot && !hasSteps && (
              <Box sx={{ whiteSpace: "pre-wrap", color: "#4b5563" }}>
                {cotText}
              </Box>
            )}

            {/* ── 3. Reasoning Steps ── */}
            {hasSteps && (
              <Box sx={{ display: "flex", flexDirection: "column" }}>
                {steps!.map((step, i) => (
                  <Box
                    key={i}
                    sx={{
                      display: "flex",
                      flexDirection: "row",
                      gap: "10px",
                      animation: isThinking
                        ? "stepSlideIn 0.25s ease-out"
                        : "none",
                      "@keyframes stepSlideIn": {
                        from: { opacity: 0, transform: "translateY(3px)" },
                        to: { opacity: 1, transform: "translateY(0)" },
                      },
                    }}
                  >
                    <Box
                      sx={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        flexShrink: 0,
                      }}
                    >
                      <Box
                        sx={{
                          minWidth: "22px",
                          height: "22px",
                          borderRadius: "50%",
                          backgroundColor: "rgba(107, 139, 245, 0.1)",
                          color: "#6B8BF5",
                          fontSize: "11px",
                          fontWeight: 700,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        {i + 1}
                      </Box>
                    </Box>

                    <Box
                      sx={{
                        flex: 1,
                        minWidth: 0,
                        pb: i < steps!.length - 1 ? "12px" : 0,
                      }}
                    >
                      <span
                        style={{
                          fontWeight: 700,
                          color: "#1e3a5f",
                          fontSize: "13.5px",
                          lineHeight: "22px",
                        }}
                      >
                        {step.label}
                      </span>
                      <Box
                        sx={{ color: "#4b5563", fontSize: "12.5px", mt: "2px" }}
                      >
                        {(() => {
                          const lines = step.content.split("\n");
                          const firstNonEmpty = lines.find((l) => l.trim());
                          const baseIndent = firstNonEmpty ? firstNonEmpty.search(/\S/) : 0;
                          return lines.map((line, li) => {
                          const trimmed = line.trim();
                          if (!trimmed) return null;
                          const text = trimmed.startsWith("- ")
                            ? trimmed.slice(2)
                            : trimmed;
                          const indent = line.search(/\S|$/);
                          const isSubItem = indent > baseIndent;
                          return (
                            <Box
                              key={li}
                              sx={{
                                display: "flex",
                                alignItems: "flex-start",
                                gap: "6px",
                                mt: li === 0 ? 0 : "3px",
                                pl: isSubItem ? "8px" : 0,
                              }}
                            >
                              <span
                                style={{
                                  color: isSubItem ? "#9DB5FF" : "#6B8BF5",
                                  fontSize: isSubItem ? "12px" : "6px",
                                  marginTop: isSubItem ? "2px" : "7px",
                                  flexShrink: 0,
                                }}
                              >
                                {isSubItem ? "▸" : "●"}
                              </span>
                              <span
                                style={{
                                  color: isSubItem ? "#6b7280" : "#4b5563",
                                  fontSize: isSubItem ? "12px" : "13px",
                                }}
                              >
                                {text}
                              </span>
                            </Box>
                          );
                        });
                        })()}
                      </Box>
                    </Box>
                  </Box>
                ))}
              </Box>
            )}

            {/* ── 4. 빈 상태 ── */}
            {!hasCot &&
              !hasSteps &&
              !hasRetrieval &&
              !hasRetrievalSummary &&
              !hasAgent &&
              !hasAgentSummary &&
              isThinking && (
                <Box
                  sx={{
                    color: "#9ca3af",
                    fontSize: "14px",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <Box
                    sx={{
                      width: "12px",
                      height: "12px",
                      borderRadius: "50%",
                      border: "2px solid rgba(107,139,245,0.2)",
                      borderTopColor: "#6B8BF5",
                      animation: "thinkSpin 0.7s linear infinite",
                      "@keyframes thinkSpin": {
                        to: { transform: "rotate(360deg)" },
                      },
                    }}
                  />
                  분석을 시작하고 있어요...
                </Box>
              )}
          </Box>
        </Box>
      </Collapse>
    </Box>
  );
};

export default React.memo(ThinkingBlock);
