import React, { FC, memo, useRef, useState, useEffect } from "react";
import { Box, Collapse } from "@mui/material";
import type {
  RetrievalData,
  RetrievalStep,
  RetrievalTimelineNode,
  RetrievalDetail,
} from "@/utils/parseAnswerContent";

/* ── 키프레임 ── */
const KEYFRAMES = `
@keyframes rtrvSpin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
@keyframes rtrvFadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes completeBounce {
  0%   { transform: scale(1); }
  35%  { transform: scale(1.5); }
  65%  { transform: scale(0.88); }
  100% { transform: scale(1); }
}
@keyframes textFlash {
  0%   { color: #6B8BF5; }
  100% { color: #1e3a5f; }
}
`;

/* ── 타임라인 점 ── */
const TimelineDot: FC<{ status: string }> = ({ status }) => {
  if (status === "completed") {
    return (
      <Box
        sx={{
          width: 12,
          height: 12,
          borderRadius: "50%",
          background: "linear-gradient(135deg, #6B8BF5, #5070D6)",
          boxShadow: "0 0 6px rgba(107,139,245,0.35)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          fontSize: "8px",
          color: "#fff",
          fontWeight: 700,
        }}
      >
        ✓
      </Box>
    );
  }

  if (status === "active") {
    return (
      <Box
        sx={{
          width: 12,
          height: 12,
          borderRadius: "50%",
          border: "2px solid #6B8BF5",
          background: "transparent",
          position: "relative",
          flexShrink: 0,
          boxShadow: "0 0 6px rgba(107,139,245,0.25)",
          "&::after": {
            content: '""',
            position: "absolute",
            inset: "1px",
            borderRadius: "50%",
            border: "1.5px solid transparent",
            borderTop: "1.5px solid #9DB5FF",
            animation: "rtrvSpin 1s linear infinite",
          },
        }}
      />
    );
  }

  return (
    <Box
      sx={{
        width: 12,
        height: 12,
        borderRadius: "50%",
        border: "2px solid #d1d5db",
        background: "transparent",
        flexShrink: 0,
      }}
    />
  );
};

/* ── 인라인 스피너 ── */
const MiniSpinner: FC = () => (
  <Box
    component="span"
    sx={{
      display: "inline-block",
      width: 12,
      height: 12,
      border: "2px solid rgba(107,139,245,0.2)",
      borderTop: "2px solid #6B8BF5",
      borderRadius: "50%",
      animation: "rtrvSpin 0.8s linear infinite",
      ml: "6px",
      verticalAlign: "middle",
      flexShrink: 0,
    }}
  />
);

/* ── 디테일 카드 ── */
const DetailCard: FC<{ details: RetrievalDetail[]; status: string }> = ({
  details,
  status,
}) => {
  if (!details || details.length === 0) return null;

  return (
    <Box
      sx={{
        mt: "8px",
        background: "#ffffff",
        border: `1px solid ${
          status === "active" ? "rgba(107,139,245,0.25)" : "#e5e7eb"
        }`,
        borderRadius: "10px",
        padding: "10px 14px",
        maxWidth: "380px",
        boxShadow:
          status === "active"
            ? "0 2px 12px rgba(107,139,245,0.08)"
            : "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      {details.map((d, i) => (
        <Box
          key={i}
          sx={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            py: "4px",
            fontSize: "12.5px",
            borderTop: i > 0 ? "1px solid #f3f4f6" : "none",
          }}
        >
          <span style={{ color: "#374151", fontWeight: 600 }}>{d.label}</span>
          <span
            style={{
              color: "#6B8BF5",
              fontWeight: 700,
              fontSize: "12.5px",
              marginLeft: "auto",
            }}
          >
            {d.value}
          </span>
        </Box>
      ))}
    </Box>
  );
};

/* ── Chip 바 ── */
const ChipBar: FC<{
  chips: Array<{ icon: string; label: string; value: string }>;
}> = ({ chips }) => {
  if (!chips || chips.length === 0) return null;

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        flexWrap: "wrap",
        py: "6px",
        pl: "32px",
      }}
    >
      {chips.map((chip, i) => (
        <Box
          key={i}
          sx={{
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            background: "rgba(107, 139, 245, 0.06)",
            border: "1px solid rgba(107, 139, 245, 0.15)",
            borderRadius: "8px",
            padding: "3px 10px",
            fontSize: "12px",
            color: "#6b7280",
            animation: "rtrvFadeIn 0.3s ease-out both",
          }}
        >
          <span>{chip.icon}</span>
          <span>{chip.label}</span>
          <span style={{ color: "#6B8BF5", fontWeight: 700 }}>
            {chip.value}
          </span>
        </Box>
      ))}
    </Box>
  );
};

/* ── 타임라인 본문 ── */
const TimelineBody: FC<{ nodes: RetrievalTimelineNode[] }> = ({ nodes }) => (
  <Box sx={{ position: "relative", ml: "4px" }}>
    {/* 세로선 */}
    <Box
      sx={{
        position: "absolute",
        left: "5px",
        top: "10px",
        bottom: "8px",
        width: "2px",
        background:
          "linear-gradient(to bottom, #6B8BF5 0%, rgba(107,139,245,0.12) 100%)",
        borderRadius: "1px",
      }}
    />
    {nodes.map((node, i) => (
      <Box
        key={i}
        sx={{
          display: "flex",
          alignItems: "flex-start",
          gap: "12px",
          py: "8px",
          animation: "rtrvFadeIn 0.3s ease-out both",
          animationDelay: `${i * 0.05}s`,
          "&:last-child": { pb: 0 },
        }}
      >
        <Box sx={{ flexShrink: 0, pt: "2px" }}>
          <TimelineDot status={node.status} />
        </Box>

        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box
            sx={{
              fontSize: "13px",
              fontWeight: 600,
              color: node.status === "active" ? "#6B8BF5" : "#374151",
              display: "flex",
              alignItems: "center",
            }}
          >
            {node.title}
            {node.status === "active" && <MiniSpinner />}
          </Box>
          <DetailCard details={node.details} status={node.status} />
        </Box>
      </Box>
    ))}
  </Box>
);

/* ── Step 컴포넌트 (numbered, 접기/펼치기) ── */
const StepBlock: FC<{
  step: RetrievalStep;
  defaultOpen?: boolean;
}> = ({ step, defaultOpen = false }) => {
  const isActive = step.status === "active";
  const isCompleted = step.status === "completed";
  const hasTimeline = step.timeline && step.timeline.length > 0;
  const hasChips = !!(step.chips && step.chips.length > 0);
  const hasContent = hasTimeline || hasChips;

  const [isOpen, setIsOpen] = useState(defaultOpen || isActive);
  const [justCompleted, setJustCompleted] = useState(false);
  const prevStatusRef = useRef(step.status);

  useEffect(() => {
    if (isActive) setIsOpen(true);
  }, [isActive]);

  useEffect(() => {
    if (prevStatusRef.current === "active" && step.status === "completed") {
      setJustCompleted(true);
      setTimeout(() => setJustCompleted(false), 700);
    }
    prevStatusRef.current = step.status;
  }, [step.status]);

  return (
    <Box
      sx={{
        animation: "rtrvFadeIn 0.3s ease-out both",
      }}
    >
      {/* ── Step 헤더 ── */}
      <Box
        onClick={() => hasContent && setIsOpen(!isOpen)}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          py: "6px",
          cursor: hasContent ? "pointer" : "default",
          userSelect: "none",
          "&:hover": hasContent
            ? { "& .step-title": { color: "#6B8BF5" } }
            : {},
        }}
      >
        {/* 숫자 뱃지 */}
        <Box
          sx={{
            minWidth: "22px",
            height: "22px",
            borderRadius: "50%",
            backgroundColor: isActive
              ? "rgba(107, 139, 245, 0.15)"
              : isCompleted
              ? "rgba(107, 139, 245, 0.18)"
              : "rgba(0,0,0,0.05)",
            color: isActive || isCompleted ? "#6B8BF5" : "#9ca3af",
            fontSize: "11px",
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            animation: justCompleted ? "completeBounce 0.55s ease-out" : "none",
          }}
        >
          {step.num}
        </Box>

        {/* 제목 */}
        <Box
          className="step-title"
          sx={{
            fontSize: "13.5px",
            fontWeight: 700,
            color: isActive ? "#6B8BF5" : isCompleted ? "#1e3a5f" : "#9ca3af",
            animation: justCompleted ? "textFlash 0.5s ease-out forwards" : "none",
          }}
        >
          {step.title}
        </Box>

        {/* summary (접혀있을 때) */}
        {!isOpen && step.summary && (
          <Box
            component="span"
            sx={{
              fontSize: "12px",
              color: "#6b7280",
              fontWeight: 400,
              maxWidth: "280px",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            — {step.summary}
          </Box>
        )}

        {/* 스피너 (active) */}
        {isActive && <MiniSpinner />}

        {/* 화살표 */}
        {hasContent && (
          <Box
            component="span"
            sx={{
              fontSize: "10px",
              color: "#8DA0BE",
              transition: "transform 0.2s",
              transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
              ml: "auto",
            }}
          >
            ▾
          </Box>
        )}
      </Box>

      {/* ── Chips ── */}
      {hasChips && (
        <Collapse in={isOpen}>
          <ChipBar chips={step.chips!} />
        </Collapse>
      )}

      {/* ── Step 본문 (타임라인) ── */}
      {hasTimeline && (
        <Collapse in={isOpen}>
          <Box sx={{ pl: "32px", pb: "4px" }}>
            <TimelineBody nodes={step.timeline} />
          </Box>
        </Collapse>
      )}
    </Box>
  );
};

/* ═══════════════════════════════════════ */
/* ── 메인 컴포넌트                       */
/* ═══════════════════════════════════════ */

interface RetrievalProgressProps {
  data: RetrievalData;
  collapsed?: boolean;
}

const RetrievalProgress: FC<RetrievalProgressProps> = ({
  data,
  collapsed = false,
}) => {
  if (!data || !data.steps || data.steps.length === 0) return null;

  return (
    <Box sx={{ mb: "4px" }}>
      <style>{KEYFRAMES}</style>
      {data.steps.map((step) => (
        <StepBlock
          key={step.num}
          step={step}
          defaultOpen={collapsed ? false : undefined}
        />
      ))}
    </Box>
  );
};

export default memo(RetrievalProgress);
