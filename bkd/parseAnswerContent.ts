/* ── 타입 정의 ── */

export interface ReasoningStep {
  label: string;
  content: string;
}

/* ── Retrieval 관련 타입 (2단 구조) ── */

export interface RetrievalTimelineNode {
  title: string;
  status: "completed" | "active" | "pending";
  details: RetrievalDetail[];
}

export interface RetrievalDetail {
  label: string;
  value: string;
}

export interface RetrievalStep {
  num: number;
  title: string;
  status: "completed" | "active" | "pending";
  summary?: string;
  timeline: RetrievalTimelineNode[];
  chips?: Array<{ icon: string; label: string; value: string }>;
}

export interface RetrievalData {
  steps: RetrievalStep[];
}

/* ── Agent Progress 타입 (Claude 스타일 플랫 구조) ── */

export interface AgentPreviewItem {
  icon: string;
  text: string;
  sub?: string;
}

export interface AgentStep {
  title: string;
  status: "completed" | "active" | "pending";
  result_count?: string;
  preview?: AgentPreviewItem[];
}

export interface AgentData {
  steps: AgentStep[];
}

/* ── Excel 실시간 스트리밍 타입 ── */

export interface ExcelStreamSection {
  subtitle: string;
  rows: Record<string, string>[];
  columns: string[];
}

export interface ExcelStreamData {
  title: string;
  rows: Record<string, string>[];
  columns: string[];
  isComplete: boolean;
  downloadUrl?: string;
  fileName?: string;
  headerGroups?: Array<{ label: string; columns: string[] }>;
  formatRules?: Array<{ column: string; type: string; value?: number }>;
  sections?: ExcelStreamSection[];
  streamingSheetTitle?: string;
  streamingSheetIndex?: number;
  completedSheetCount?: number;
}

export interface ParsedContent {
  cot: string | null;
  reasoning: ReasoningStep[] | null;
  answer: string | null;
  retrieval: RetrievalData | null;
  retrievalSummary: RetrievalData | null;
  agent: AgentData | null;
  agentSummary: AgentData | null;
  excelData: ExcelStreamData[];
  raw: string;
  phase:
    | "starting"
    | "cot"
    | "reasoning"
    | "answering"
    | "complete"
    | "retrieving";
}

/* ── retrieval 태그 파싱 ── */

const parseRetrievalTag = (
  content: string,
  tagName: string
): RetrievalData | null => {
  const regex = new RegExp(`<${tagName}\\s+data='([^']*)'\\s*\\/>`, "i");
  const match = regex.exec(content);
  if (!match) return null;
  try {
    const parsed = JSON.parse(match[1]);
    // 하위 호환: 배열이면 기존 flat 구조 → 새 구조로 변환
    if (Array.isArray(parsed)) {
      return {
        steps: [
          {
            num: 1,
            title: "검색",
            status: parsed.some((s: any) => s.status === "active")
              ? "active"
              : "completed",
            timeline: parsed,
          },
        ],
      };
    }
    return parsed as RetrievalData;
  } catch {
    return null;
  }
};

/* ── agent 태그 파싱 (Claude 스타일 플랫 구조) ── */

const parseAgentTag = (
  content: string,
  tagName: string
): AgentData | null => {
  const regex = new RegExp(`<${tagName}\\s+data='([^']*)'\\s*\\/>`, "i");
  const match = regex.exec(content);
  if (!match) return null;
  try {
    return JSON.parse(match[1]) as AgentData;
  } catch {
    return null;
  }
};

/* ── sections 증분 파싱 (스트리밍 중 불완전한 JSON 처리) ── */

const parseIncrementalSections = (
  jsonStr: string,
  hasClose: boolean
): ExcelStreamSection[] => {
  const sections: ExcelStreamSection[] = [];
  const sectionsIdx = jsonStr.indexOf('"sections"');
  if (sectionsIdx === -1) return sections;

  const arrStart = jsonStr.indexOf("[", sectionsIdx);
  if (arrStart === -1) return sections;

  // 완성된 섹션 객체 추출 (depth 0→1: 섹션 시작, 1→0: 섹션 끝)
  let depth = 0;
  let objStart = -1;
  for (let j = arrStart + 1; j < jsonStr.length; j++) {
    if (jsonStr[j] === "{") {
      if (depth === 0) objStart = j;
      depth++;
    } else if (jsonStr[j] === "}") {
      depth--;
      if (depth === 0 && objStart !== -1) {
        try {
          const sec = JSON.parse(jsonStr.slice(objStart, j + 1));
          if (Array.isArray(sec.data) && sec.data.length > 0) {
            sections.push({
              subtitle: sec.subtitle || "",
              rows: sec.data,
              columns: Object.keys(sec.data[0]),
            });
          }
        } catch { /* skip malformed */ }
        objStart = -1;
      }
    }
  }

  // 미완성 마지막 섹션에서 부분 행 추출 (스트리밍 중)
  if (objStart !== -1 && !hasClose) {
    const partial = jsonStr.slice(objStart);
    const subMatch = partial.match(/"subtitle"\s*:\s*"([^"]*)"/);
    const subtitle = subMatch ? subMatch[1] : "";

    const dIdx = partial.indexOf('"data"');
    if (dIdx !== -1) {
      const dArrStart = partial.indexOf("[", dIdx);
      if (dArrStart !== -1) {
        const partialRows: Record<string, string>[] = [];
        let d = 0, os = -1;
        for (let k = dArrStart + 1; k < partial.length; k++) {
          if (partial[k] === "{") { if (d === 0) os = k; d++; }
          else if (partial[k] === "}") {
            d--;
            if (d === 0 && os !== -1) {
              try { partialRows.push(JSON.parse(partial.slice(os, k + 1))); } catch { /* skip */ }
              os = -1;
            }
          }
        }
        if (partialRows.length > 0) {
          sections.push({ subtitle, rows: partialRows, columns: Object.keys(partialRows[0]) });
        }
      }
    }
  }

  return sections;
};

/* ── sheets 증분 파싱 (단일 <excel-data> 블록 내 "sheets" 배열) ── */

const parseIncrementalSheets = (
  jsonStr: string,
  hasClose: boolean,
): {
  sections: ExcelStreamSection[];
  streamingSheetTitle?: string;
  streamingSheetIndex?: number;
  completedSheetCount?: number;
} => {
  const sections: ExcelStreamSection[] = [];
  const sheetsIdx = jsonStr.indexOf('"sheets"');
  if (sheetsIdx === -1) return { sections };

  const arrStart = jsonStr.indexOf("[", sheetsIdx);
  if (arrStart === -1) return { sections };

  // 완성된 시트 객체 추출 (depth 0→1: 시트 시작, 1→0: 시트 끝)
  let depth = 0;
  let objStart = -1;
  for (let j = arrStart + 1; j < jsonStr.length; j++) {
    if (jsonStr[j] === "{") {
      if (depth === 0) objStart = j;
      depth++;
    } else if (jsonStr[j] === "}") {
      depth--;
      if (depth === 0 && objStart !== -1) {
        try {
          const sheet = JSON.parse(jsonStr.slice(objStart, j + 1));
          if (Array.isArray(sheet.data) && sheet.data.length > 0) {
            sections.push({
              subtitle: sheet.title || "",
              rows: sheet.data,
              columns: Object.keys(sheet.data[0]),
            });
          }
        } catch { /* skip malformed */ }
        objStart = -1;
      }
    }
  }

  const completedSheetCount = sections.length;
  let streamingSheetTitle: string | undefined;
  let streamingSheetIndex: number | undefined;

  // 미완성 마지막 시트에서 부분 행 + title 추출 (스트리밍 중)
  if (objStart !== -1 && !hasClose) {
    const partial = jsonStr.slice(objStart);
    const titleMatch = partial.match(/"title"\s*:\s*"([^"]*)"/);
    streamingSheetTitle = titleMatch ? titleMatch[1] : undefined;
    streamingSheetIndex = sections.length;

    const dIdx = partial.indexOf('"data"');
    if (dIdx !== -1) {
      const dArrStart = partial.indexOf("[", dIdx);
      if (dArrStart !== -1) {
        const partialRows: Record<string, string>[] = [];
        let d = 0, os = -1;
        for (let k = dArrStart + 1; k < partial.length; k++) {
          if (partial[k] === "{") { if (d === 0) os = k; d++; }
          else if (partial[k] === "}") {
            d--;
            if (d === 0 && os !== -1) {
              try { partialRows.push(JSON.parse(partial.slice(os, k + 1))); } catch { /* skip */ }
              os = -1;
            }
          }
        }
        if (partialRows.length > 0) {
          sections.push({ subtitle: streamingSheetTitle || "", rows: partialRows, columns: Object.keys(partialRows[0]) });
        }
      }
    }
  }

  return { sections, streamingSheetTitle, streamingSheetIndex, completedSheetCount };
};

/* ── excel-data 증분 파싱 (다중 블록 지원 + 단일 sheets 블록) ── */

const parseExcelData = (
  content: string,
  isStreaming: boolean
): ExcelStreamData[] => {
  if (!/<excel-data>/i.test(content)) return [];

  const results: ExcelStreamData[] = [];
  const parts = content.split(/<excel-data>/i);

  for (let p = 1; p < parts.length; p++) {
    const part = parts[p];
    const closeIdx = part.search(/<\/excel-data>/i);
    const hasClose = closeIdx !== -1;

    let jsonStr: string;
    if (hasClose) {
      jsonStr = part.slice(0, closeIdx).trim();
    } else if (isStreaming) {
      jsonStr = part.trim();
    } else {
      continue;
    }

    // download URL + filename 추출 (</excel-data> 이후의 <excel-download> 태그)
    let downloadUrl: string | undefined;
    let dlFileName: string | undefined;
    if (hasClose) {
      const afterClose = part.slice(closeIdx);
      const dlMatch = afterClose.match(/<excel-download\s[^>]*url="([^"]*)"/i);
      if (dlMatch) downloadUrl = dlMatch[1];
      const fnMatch = afterClose.match(/<excel-download\s[^>]*filename="([^"]*)"/i);
      if (fnMatch && fnMatch[1]) dlFileName = fnMatch[1];
    }

    // 1) 전체 JSON 파싱 시도
    try {
      const parsed = JSON.parse(jsonStr);
      // NEW: unified sheets 포맷 (멀티시트 → sections 변환)
      if (Array.isArray(parsed.sheets)) {
        const sections: ExcelStreamSection[] = parsed.sheets
          .filter((s: any) => Array.isArray(s.data) && s.data.length > 0)
          .map((s: any) => ({
            subtitle: s.title || "",
            rows: s.data,
            columns: s.data.length > 0 ? Object.keys(s.data[0]) : [],
          }));
        results.push({
          title: parsed.file_name || parsed.sheets[0]?.title || "",
          rows: [],
          columns: [],
          isComplete: hasClose,
          downloadUrl,
          fileName: dlFileName || parsed.file_name,
          sections,
          completedSheetCount: sections.length,
        });
        continue;
      }
      // sections 모드: 다른 컬럼 구조를 하나의 시트에 합침
      if (Array.isArray(parsed.sections)) {
        const rawCount = parsed.sections.length;
        const sections: ExcelStreamSection[] = parsed.sections
          .filter((s: any) => Array.isArray(s.data) && s.data.length > 0)
          .map((s: any) => ({
            subtitle: s.subtitle || "",
            rows: s.data,
            columns: s.data.length > 0 ? Object.keys(s.data[0]) : [],
          }));
        if (sections.length !== rawCount) {
          console.warn(
            `[parseExcelData] sections 필터링: ${rawCount} → ${sections.length}`,
            `(isStreaming=${isStreaming}, hasClose=${hasClose})`,
            parsed.sections.map((s: any) => ({
              subtitle: s.subtitle,
              dataIsArray: Array.isArray(s.data),
              dataLen: Array.isArray(s.data) ? s.data.length : 0,
            })),
          );
        }
        results.push({
          title: parsed.title || "",
          rows: [],
          columns: [],
          isComplete: hasClose,
          downloadUrl,
          fileName: dlFileName,
          sections,
        });
        continue;
      }
      // 기존 flat data 모드
      const data = Array.isArray(parsed.data) ? parsed.data : [];
      const columns = data.length > 0 ? Object.keys(data[0]) : [];
      results.push({
        title: parsed.title || "",
        rows: data,
        columns,
        isComplete: hasClose,
        downloadUrl,
        fileName: dlFileName || parsed.file_name,
        headerGroups: parsed.header_groups,
        formatRules: parsed.format_rules,
      });
      continue;
    } catch {
      /* 증분 파싱으로 fallback */
    }

    // 2) title / file_name 추출
    const titleMatch = jsonStr.match(/"title"\s*:\s*"([^"]*)"/);
    const title = titleMatch ? titleMatch[1] : "";
    const fnMatch = jsonStr.match(/"file_name"\s*:\s*"([^"]*)"/);
    const parsedFileName = fnMatch ? fnMatch[1] : undefined;

    // 3-A) sheets 증분 파싱 (신규 통합 포맷)
    if (jsonStr.includes('"sheets"')) {
      const { sections, streamingSheetTitle, streamingSheetIndex, completedSheetCount } =
        parseIncrementalSheets(jsonStr, hasClose);
      results.push({
        title: parsedFileName || streamingSheetTitle || title || "",
        rows: [], columns: [],
        isComplete: hasClose,
        downloadUrl, fileName: dlFileName || parsedFileName,
        sections: sections.length > 0 ? sections : undefined,
        streamingSheetTitle, streamingSheetIndex, completedSheetCount,
      });
      continue;
    }

    // 3-B) sections 증분 파싱
    if (jsonStr.includes('"sections"')) {
      const sections = parseIncrementalSections(jsonStr, hasClose);
      results.push({ title, rows: [], columns: [], isComplete: hasClose, downloadUrl, fileName: dlFileName, sections: sections.length > 0 ? sections : undefined });
      continue;
    }

    // 3-C) 기존 flat data 증분 파싱 (brace depth tracking)
    const rows: Record<string, string>[] = [];
    const dataIdx = jsonStr.indexOf('"data"');
    if (dataIdx === -1) { results.push({ title, rows: [], columns: [], isComplete: hasClose, downloadUrl, fileName: dlFileName || parsedFileName }); continue; }

    const arrStart = jsonStr.indexOf("[", dataIdx);
    if (arrStart === -1) { results.push({ title, rows: [], columns: [], isComplete: hasClose, downloadUrl, fileName: dlFileName || parsedFileName }); continue; }

    let depth = 0;
    let objStart = -1;
    for (let j = arrStart + 1; j < jsonStr.length; j++) {
      if (jsonStr[j] === "{") {
        if (depth === 0) objStart = j;
        depth++;
      } else if (jsonStr[j] === "}") {
        depth--;
        if (depth === 0 && objStart !== -1) {
          try { rows.push(JSON.parse(jsonStr.slice(objStart, j + 1))); } catch { /* skip */ }
          objStart = -1;
        }
      }
    }

    const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
    results.push({ title, rows, columns, isComplete: hasClose, downloadUrl, fileName: dlFileName || parsedFileName });
  }

  // 다중 flat-data 블록 → 하나의 sections 모드로 자동 결합
  if (results.length > 1 && results.every((r) => !r.sections)) {
    const downloadUrl = results.reduce<string | undefined>(
      (u, r) => r.downloadUrl ?? u,
      undefined,
    );
    const fileName = results.reduce<string | undefined>(
      (u, r) => r.fileName ?? u,
      undefined,
    );
    return [
      {
        title: results[0].title,
        rows: [],
        columns: [],
        isComplete: results.every((r) => r.isComplete),
        downloadUrl,
        fileName,
        sections: results.map((r) => ({
          subtitle: r.title,
          rows: r.rows,
          columns: r.columns,
        })),
      },
    ];
  }

  return results;
};

/* ── reasoning 텍스트 파싱 ── */

const parseReasoningText = (text: string): ReasoningStep[] => {
  const steps: ReasoningStep[] = [];

  // 방식 1: [라벨] 패턴
  const bracketRegex = /\[([^\]]+)\]\s*/g;
  const bracketLabels: { label: string; startIndex: number }[] = [];

  let match: RegExpExecArray | null;
  while ((match = bracketRegex.exec(text)) !== null) {
    bracketLabels.push({
      label: match[1],
      startIndex: match.index + match[0].length,
    });
  }

  if (bracketLabels.length >= 2) {
    for (let i = 0; i < bracketLabels.length; i++) {
      const endIndex =
        i + 1 < bracketLabels.length
          ? text.lastIndexOf(
              `[${bracketLabels[i + 1].label}]`,
              bracketLabels[i + 1].startIndex
            )
          : text.length;
      const content = text.slice(bracketLabels[i].startIndex, endIndex).trim();
      if (content) {
        steps.push({ label: bracketLabels[i].label, content });
      }
    }
    return steps;
  }

  // 방식 2: <li><b>라벨:</b> 패턴
  const htmlRegex = /<li>\s*<b>([^<]+?)[:：]?\s*<\/b>\s*/gi;
  const htmlLabels: { label: string; matchEnd: number }[] = [];

  while ((match = htmlRegex.exec(text)) !== null) {
    htmlLabels.push({
      label: match[1].trim(),
      matchEnd: match.index + match[0].length,
    });
  }

  if (htmlLabels.length > 0) {
    for (let i = 0; i < htmlLabels.length; i++) {
      const startIdx = htmlLabels[i].matchEnd;
      const endIdx =
        i + 1 < htmlLabels.length
          ? text.indexOf("<li>", htmlLabels[i].matchEnd)
          : text.length;
      const rawSlice = text.slice(
        startIdx,
        endIdx !== -1 ? endIdx : text.length
      );

      let content = rawSlice
        .replace(/<\/li>/gi, "")
        .replace(/<\/?(?:ol|ul|br|p|div)[^>]*>/gi, "\n")
        .replace(/<li>/gi, "\n- ")
        .replace(/<\/?[^>]+>/gi, "")
        .replace(/\n{3,}/g, "\n\n")
        .trim();

      if (content) {
        steps.push({ label: htmlLabels[i].label, content });
      }
    }
    return steps;
  }

  // 방식 3: 패턴 없음
  if (text.trim()) {
    let cleaned = text.replace(/<[^>]+>/g, "").trim();
    if (cleaned) {
      steps.push({ label: "분석 내용", content: cleaned });
    }
  }

  return steps;
};

/* ── 메인 파서 ── */

export const parseMessageContent = (
  content: string,
  isStreaming: boolean = false
): ParsedContent => {
  if (!content) {
    return {
      cot: null,
      reasoning: null,
      answer: null,
      retrieval: null,
      retrievalSummary: null,
      agent: null,
      agentSummary: null,
      excelData: [],
      raw: "",
      phase: "starting",
    };
  }

  const retrieval = parseRetrievalTag(content, "retrieval-progress");
  const retrievalSummary = parseRetrievalTag(content, "retrieval-summary");
  const agent = parseAgentTag(content, "agent-progress");
  const agentSummary = parseAgentTag(content, "agent-summary");

  const hasCotOpen = /<cot>/i.test(content);
  const hasCotClose = /<\/cot>/i.test(content);
  const hasReasoningOpen = /<reasoning>/i.test(content);
  const hasReasoningClose = /<\/reasoning>/i.test(content);
  const hasAnswerOpen = /<answer>/i.test(content);
  const hasAnswerClose = /<\/answer>/i.test(content);
  const hasRetrievalProgress = /<retrieval-progress\s/i.test(content);
  const hasAgentProgress = /<agent-progress\s/i.test(content);

  // Phase 결정
  let phase: ParsedContent["phase"];
  if (!isStreaming) {
    phase = "complete";
  } else if (hasAnswerOpen && !hasAnswerClose) {
    phase = "answering";
  } else if (hasReasoningOpen && !hasReasoningClose) {
    phase = "reasoning";
  } else if (hasCotOpen && !hasCotClose) {
    phase = "cot";
  } else if (hasCotClose && !hasReasoningOpen && !hasAnswerOpen) {
    phase = "starting";
  } else if (
    (hasRetrievalProgress || hasAgentProgress) &&
    !hasReasoningOpen &&
    !hasAnswerOpen
  ) {
    phase = "retrieving";
  } else if (
    !hasCotOpen &&
    !hasReasoningOpen &&
    !hasAnswerOpen &&
    content.length > 0
  ) {
    phase = "answering";
  } else {
    phase = "starting";
  }

  // CoT 추출
  let cot: string | null = null;
  if (hasCotOpen) {
    if (hasCotClose) {
      const m = content.match(/<cot>([\s\S]*?)<\/cot>/i);
      cot = m ? m[1].trim() : null;
    } else if (isStreaming) {
      const startIdx = content.indexOf("<cot>") + "<cot>".length;
      cot = content.slice(startIdx).trim();
    }
  }

  // Reasoning 추출
  let reasoningRaw: string | null = null;
  if (hasReasoningOpen) {
    if (hasReasoningClose) {
      const m = content.match(/<reasoning>([\s\S]*?)<\/reasoning>/i);
      reasoningRaw = m ? m[1].trim() : null;
    } else if (isStreaming) {
      const startIdx =
        content.indexOf("<reasoning>") + "<reasoning>".length;
      reasoningRaw = content.slice(startIdx).trim();
      reasoningRaw = reasoningRaw.replace(/<\/?[a-zA-Z][^>]*$/g, "");
    }
  }

  const reasoning = reasoningRaw ? parseReasoningText(reasoningRaw) : null;

  // Answer 추출
  let answer: string | null = null;
  if (hasAnswerOpen) {
    if (hasAnswerClose) {
      const m = content.match(/<answer>([\s\S]*?)<\/answer>/i);
      answer = m ? m[1].trim() : null;
    } else if (isStreaming) {
      const startIdx = content.indexOf("<answer>") + "<answer>".length;
      answer = content.slice(startIdx).trim();
      answer = answer.replace(/<\/?[a-zA-Z][^>]*$/g, "");
    }
  }
  // <excel-data>, <excel-download> 태그 제거 (답변 텍스트에서 분리)
  if (answer) {
    answer = answer.replace(/<excel-data>[\s\S]*?<\/excel-data>/gi, "");
    answer = answer.replace(/<excel-download\s+[^/]*\/>/gi, "");
    // 스트리밍 중 아직 닫히지 않은 <excel-data> 제거 (답변 멈춤 방지)
    answer = answer.replace(/<excel-data>[\s\S]*$/gi, "");
    answer = answer.trim();
  }

  // complete인데 태그 없는 경우
  if (phase === "complete" && !reasoning && !answer && !cot) {
    const cleanContent = content
      .replace(/<\/?cot>/gi, "")
      .replace(/<\/?reasoning>/gi, "")
      .replace(/<\/?answer>/gi, "")
      .replace(/<end>/gi, "")
      .replace(/<retrieval-summary\s+data='[^']*'\s*\/>/gi, "")
      .replace(/<agent-summary\s+data='[^']*'\s*\/>/gi, "")
      .replace(/<excel-data>[\s\S]*?<\/excel-data>/gi, "")
      .replace(/<excel-download\s+[^/]*\/>/gi, "")
      .trim();
    if (cleanContent) {
      answer = cleanContent;
    }
  }

  if (
    phase === "answering" &&
    !hasAnswerOpen &&
    !reasoning &&
    !cot &&
    !answer
  ) {
    const cleanContent = content
      .replace(/<end>/gi, "")
      .replace(/<retrieval-progress\s+data='[^']*'\s*\/>/gi, "")
      .replace(/<agent-progress\s+data='[^']*'\s*\/>/gi, "")
      .trim();
    if (cleanContent) {
      answer = cleanContent;
    }
  }

  // Excel 데이터 증분 파싱 (raw content에서 추출)
  const excelData = parseExcelData(content, isStreaming);

  return {
    cot,
    reasoning,
    answer,
    retrieval,
    retrievalSummary,
    agent,
    agentSummary,
    excelData,
    raw: content,
    phase,
  };
};
