import { FC, memo, useState, useEffect, useRef } from "react";
import { Box, Collapse } from "@mui/material";
import type {
  AgentData,
  AgentStep,
  AgentPreviewItem,
} from "@/utils/parseAnswerContent";

/* ── 키프레임 ── */
const KEYFRAMES = `
@keyframes agentSpin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
@keyframes agentFadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes agentCheckIn {
  0%   { transform: scale(0.5); opacity: 0; }
  60%  { transform: scale(1.15); }
  100% { transform: scale(1); opacity: 1; }
}
`;

/* ── 스피너 (active 상태) ── */
const Spinner: FC = () => (
  <Box
    component="span"
    sx={{
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: 18,
      height: 18,
      flexShrink: 0,
    }}
  >
    <Box
      component="span"
      sx={{
        width: 14,
        height: 14,
        border: "2px solid rgba(107,139,245,0.15)",
        borderTop: "2px solid #6B8BF5",
        borderRadius: "50%",
        animation: "agentSpin 0.8s linear infinite",
      }}
    />
  </Box>
);

/* ── 체크 아이콘 (completed 상태) ── */
const CheckIcon: FC = () => (
  <Box
    component="span"
    sx={{
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: 18,
      height: 18,
      borderRadius: "50%",
      background: "linear-gradient(135deg, #6B8BF5, #5070D6)",
      boxShadow: "0 1px 4px rgba(107,139,245,0.3)",
      color: "#fff",
      fontSize: "10px",
      fontWeight: 700,
      flexShrink: 0,
      animation: "agentCheckIn 0.35s ease-out",
    }}
  >
    ✓
  </Box>
);

/* ── Preview 리스트 (접었다 펼치는 상세 항목) ── */
const PreviewList: FC<{ items: AgentPreviewItem[] }> = ({ items }) => {
  if (!items || items.length === 0) return null;

  return (
    <Box
      sx={{
        mt: "4px",
        ml: "28px",
        maxHeight: items.length > 4 ? "108px" : "none",
        overflowY: items.length > 4 ? "auto" : "visible",
        "&::-webkit-scrollbar": { width: "3px" },
        "&::-webkit-scrollbar-track": { background: "transparent" },
        "&::-webkit-scrollbar-thumb": {
          background: "rgba(0,0,0,0.08)",
          borderRadius: "3px",
        },
      }}
    >
      {items.map((item, i) => (
        <Box
          key={i}
          sx={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            py: "3px",
            fontSize: "12.5px",
            animation: "agentFadeIn 0.2s ease-out both",
            animationDelay: `${i * 0.04}s`,
          }}
        >
          <span style={{ fontSize: "13px", flexShrink: 0 }}>{item.icon}</span>
          <span
            style={{
              color: "#374151",
              fontWeight: 500,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {item.text}
          </span>
          {item.sub && (
            <span
              style={{
                color: "#9ca3af",
                marginLeft: "auto",
                fontSize: "12px",
                flexShrink: 0,
                whiteSpace: "nowrap",
              }}
            >
              {item.sub}
            </span>
          )}
        </Box>
      ))}
    </Box>
  );
};

/* ── 스텝 행 (도구 하나) ── */
const StepRow: FC<{ step: AgentStep; isLast?: boolean }> = ({
  step,
  isLast = false,
}) => {
  const isActive = step.status === "active";
  const hasPreview = !!(step.preview && step.preview.length > 0);
  const [isOpen, setIsOpen] = useState(false);
  const prevStatusRef = useRef(step.status);

  // active → completed 전환 시 접기
  useEffect(() => {
    if (prevStatusRef.current === "active" && step.status === "completed") {
      setIsOpen(false);
    }
    prevStatusRef.current = step.status;
  }, [step.status]);

  return (
    <Box
      sx={{
        animation: "agentFadeIn 0.25s ease-out both",
        pb: isLast ? 0 : "2px",
      }}
    >
      {/* ── 스텝 헤더 ── */}
      <Box
        onClick={() => hasPreview && setIsOpen(!isOpen)}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          py: "4px",
          cursor: hasPreview ? "pointer" : "default",
          userSelect: "none",
          borderRadius: "6px",
          "&:hover": hasPreview
            ? { backgroundColor: "rgba(107,139,245,0.04)" }
            : {},
        }}
      >
        {/* 상태 아이콘 */}
        {isActive ? <Spinner /> : <CheckIcon />}

        {/* 제목 */}
        <Box
          sx={{
            fontSize: "13.5px",
            fontWeight: 600,
            color: isActive ? "#6B8BF5" : "#374151",
            flex: 1,
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {step.title}
        </Box>

        {/* 결과 수 (오른쪽) */}
        {step.result_count && (
          <Box
            sx={{
              fontSize: "12px",
              color: "#9ca3af",
              fontWeight: 500,
              flexShrink: 0,
              whiteSpace: "nowrap",
            }}
          >
            {step.result_count}
          </Box>
        )}

        {/* 펼침 화살표 */}
        {hasPreview && (
          <Box
            component="span"
            sx={{
              fontSize: "10px",
              color: "#8DA0BE",
              transition: "transform 0.2s ease",
              transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
              flexShrink: 0,
              ml: "-2px",
            }}
          >
            ▶
          </Box>
        )}
      </Box>

      {/* ── Preview 상세 ── */}
      {hasPreview && (
        <Collapse in={isOpen}>
          <PreviewList items={step.preview!} />
        </Collapse>
      )}
    </Box>
  );
};

/* ═══════════════════════════════════════ */
/* ── 메인 컴포넌트                       */
/* ═══════════════════════════════════════ */

interface AgentProgressProps {
  data: AgentData;
}

const AgentProgress: FC<AgentProgressProps> = ({ data }) => {
  if (!data || !data.steps || data.steps.length === 0) return null;

  return (
    <Box sx={{ mb: "4px" }}>
      <style>{KEYFRAMES}</style>
      {data.steps.map((step, i) => (
        <StepRow
          key={`${step.title}-${i}`}
          step={step}
          isLast={i === data.steps.length - 1}
        />
      ))}
    </Box>
  );
};

export default memo(AgentProgress);
