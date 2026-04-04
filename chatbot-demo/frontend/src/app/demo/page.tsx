'use client'

import { useState } from 'react'
import { TemplateSelector } from '@/components/message-parts/TemplateSelector'
import { ExampleSelector } from '@/components/message-parts/ExampleSelector'
import { DocumentPreview } from '@/components/message-parts/DocumentPreview'

// ─── 더미 데이터 ───

const DUMMY_TEMPLATES = [
  { id: 'tpl_001', title: '예산 집행 현황 보고서', category: '예산/회계', score: 0.95 },
  { id: 'tpl_002', title: '예산 변경 요청서', category: '예산/회계', score: 0.91 },
  { id: 'tpl_003', title: '월간 예산 결산 보고서', category: '예산/회계', score: 0.88 },
  { id: 'tpl_004', title: '사업 계획서', category: '사업/계획', score: 0.82 },
  { id: 'tpl_005', title: '예산 편성 계획서', category: '예산/회계', score: 0.79 },
  { id: 'tpl_006', title: '분기별 예산 보고서', category: '예산/회계', score: 0.68 },
  { id: 'tpl_007', title: '예산 초과 사유서', category: '예산/회계', score: 0.65 },
]

const DUMMY_EXAMPLES = [
  { id: 'ex_user_001', title: '우리부서 3월 보고서.hwpx', is_mine: true, preview: '2025년 3월 예산 집행 현황을 아래와 같이 보고합니다. 당월 집행률은 85%로 전월 대비 3%p 상승하였으며...' },
  { id: 'ex_user_002', title: '작년 결산 보고서.hwpx', is_mine: true, preview: '2024년 연간 예산 결산 결과를 보고합니다. 총 배정액 대비 집행률 92.3%를 달성하였고...' },
  { id: 'ex_pub_001', title: '예시 - 기획재정부 2025.03', is_mine: false, preview: '2025년 3월 기획재정부 예산 집행 현황 보고서입니다. 주요 사업별 집행 실적을 정리하였습니다...' },
  { id: 'ex_pub_002', title: '예시 - 행정안전부 2025.01', is_mine: false, preview: '행정안전부 2025년 1월 예산 집행 현황을 보고드립니다. 전체 예산 대비 집행률은 8.2%로...' },
  { id: 'ex_pub_003', title: '예시 - 환경부 2025.02', is_mine: false, preview: '환경부 2025년 2월 예산 집행 현황입니다. 환경 보전 분야 집행률이 전월 대비 상승하였습니다...' },
]

const DUMMY_DOCUMENT = {
  docId: 'doc_abc123',
  title: '2025년 3월 예산 집행 현황 보고서',
  docType: '예산/회계',
  reviewScore: 0.95,
  files: { hwpx: '/api/documents/doc_abc123/download?format=hwpx', pptx: '/api/documents/doc_abc123/download?format=pptx' },
  sections: [
    {
      section_index: 0,
      section_title: '제목 및 개요',
      content: '<h3>2025년 3월 예산 집행 현황 보고</h3><p>아래와 같이 2025년 3월 예산 집행 현황을 보고합니다.</p><p><strong>보고 기간:</strong> 2025.03.01 ~ 2025.03.31</p><p><strong>작성 부서:</strong> 기획예산과</p>',
      version: 1,
    },
    {
      section_index: 1,
      section_title: '현황 분석',
      content: '<h3>1. 집행 현황 분석</h3><p>당월 집행률은 <strong>85%</strong>로 전월 대비 3%p 상승하였습니다.</p><table style="width:100%;border-collapse:collapse;margin:8px 0"><tr style="background:#2F5496;color:#fff"><th style="padding:8px;border:1px solid #ddd">항목</th><th style="padding:8px;border:1px solid #ddd">배정액(천원)</th><th style="padding:8px;border:1px solid #ddd">집행액(천원)</th><th style="padding:8px;border:1px solid #ddd">집행률</th></tr><tr><td style="padding:8px;border:1px solid #ddd">인건비</td><td style="padding:8px;border:1px solid #ddd;text-align:right">50,000</td><td style="padding:8px;border:1px solid #ddd;text-align:right">45,000</td><td style="padding:8px;border:1px solid #ddd;text-align:center">90%</td></tr><tr style="background:#f8fafc"><td style="padding:8px;border:1px solid #ddd">운영비</td><td style="padding:8px;border:1px solid #ddd;text-align:right">30,000</td><td style="padding:8px;border:1px solid #ddd;text-align:right">25,500</td><td style="padding:8px;border:1px solid #ddd;text-align:center">85%</td></tr><tr><td style="padding:8px;border:1px solid #ddd">사업비</td><td style="padding:8px;border:1px solid #ddd;text-align:right">70,000</td><td style="padding:8px;border:1px solid #ddd;text-align:right">56,000</td><td style="padding:8px;border:1px solid #ddd;text-align:center">80%</td></tr><tr style="background:#e2e8f0;font-weight:bold"><td style="padding:8px;border:1px solid #ddd">합계</td><td style="padding:8px;border:1px solid #ddd;text-align:right">150,000</td><td style="padding:8px;border:1px solid #ddd;text-align:right">126,500</td><td style="padding:8px;border:1px solid #ddd;text-align:center">85%</td></tr></table>',
      version: 1,
    },
    {
      section_index: 2,
      section_title: '주요 사항 및 건의',
      content: '<h3>2. 주요 사항</h3><ul><li>인건비 집행률 90%로 정상 범위 내 집행 중</li><li>운영비 중 여비 항목 집행 지연 (출장 일정 변경)</li><li>사업비 중 시설 보수 공사 4월 착수 예정</li></ul><h3>3. 건의 사항</h3><p>운영비 여비 항목의 <strong>이월 처리</strong>를 건의드립니다. 출장 일정이 4월로 연기됨에 따라 해당 예산의 이월이 필요합니다.</p>',
      version: 1,
    },
  ],
}

// ─── 컴포넌트별 데모 섹션 ───

type DemoStep = 'template' | 'example' | 'preview'

export default function DemoPage() {
  const [activeStep, setActiveStep] = useState<DemoStep>('template')

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      {/* 헤더 */}
      <div className="border-b border-gray-200 bg-white px-6 py-4 dark:border-gray-800 dark:bg-gray-900">
        <h1 className="text-xl font-bold text-gray-900 dark:text-white">
          Agentic AI 문서 생성 — UI 데모
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          백엔드 없이 컴포넌트 렌더링을 확인하는 데모 페이지
        </p>
      </div>

      {/* 탭 네비게이션 */}
      <div className="flex gap-1 border-b border-gray-200 bg-white px-6 dark:border-gray-800 dark:bg-gray-900">
        {([
          { key: 'template', label: '1. 양식 선택' },
          { key: 'example', label: '2. 예시 선택' },
          { key: 'preview', label: '3. 문서 미리보기' },
        ] as const).map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveStep(tab.key)}
            className={`px-4 py-3 text-sm font-medium transition-colors ${
              activeStep === tab.key
                ? 'border-b-2 border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 컨텐츠 */}
      <div className="mx-auto max-w-3xl px-6 py-8">
        {activeStep === 'template' && (
          <div className="space-y-4">
            <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
              <TemplateSelector candidates={DUMMY_TEMPLATES} />
            </div>
          </div>
        )}

        {activeStep === 'example' && (
          <div className="space-y-4">
            <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
              <ExampleSelector
                templateTitle="예산 집행 현황 보고서"
                examples={DUMMY_EXAMPLES}
              />
            </div>
          </div>
        )}

        {activeStep === 'preview' && (
          <div className="space-y-4">
            <DocumentPreview {...DUMMY_DOCUMENT} />
          </div>
        )}
      </div>
    </div>
  )
}
