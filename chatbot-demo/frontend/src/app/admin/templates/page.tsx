'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Upload,
  Search,
  Trash2,
  FileText,
  Plus,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Loader2,
  X,
  Eye,
  EyeOff,
} from 'lucide-react'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || ''

/** 페이지당 표시 개수 */
const PAGE_LIMIT = 10

/** 카테고리 프리셋 */
const CATEGORY_PRESETS = [
  '행정/일반',
  '예산/회계',
  '사업/기획',
  '인사/복무',
  '감사/법무',
  '자산관리',
  '채권관리',
  '기타',
]

// ─── 타입 정의 ───

interface TemplateItem {
  id: string
  title: string
  category: string
  sub_category?: string
  example_count: number
  created_at: string
}

interface TemplateDetail {
  id: string
  title: string
  category: string
  sub_category?: string
  sections: Array<{ section_index: number; section_title: string; content: string }>
  examples: Array<{ id: string; title: string; is_public: boolean }>
  created_at?: string
}

// ─── 메인 페이지 컴포넌트 ───

export default function TemplatesAdminPage() {
  // 목록 상태
  const [templates, setTemplates] = useState<TemplateItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 필터/검색 상태
  const [categories, setCategories] = useState<string[]>([])
  const [selectedCategory, setSelectedCategory] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchInput, setSearchInput] = useState('')

  // 모달 상태
  const [showTemplateUpload, setShowTemplateUpload] = useState(false)
  const [showExampleUpload, setShowExampleUpload] = useState(false)

  // 상세 보기 상태
  const [detailId, setDetailId] = useState<string | null>(null)
  const [detail, setDetail] = useState<TemplateDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_LIMIT))

  /** 카테고리 목록 로드 */
  const fetchCategories = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/templates/categories/list`)
      if (!res.ok) throw new Error('카테고리 로드 실패')
      const data = await res.json()
      setCategories(data.categories || [])
    } catch {
      // 카테고리 로드 실패 시 프리셋 사용
      setCategories(CATEGORY_PRESETS)
    }
  }, [])

  /** 양식 목록 로드 */
  const fetchTemplates = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (selectedCategory) params.set('category', selectedCategory)
      if (searchQuery) params.set('query', searchQuery)
      params.set('limit', String(PAGE_LIMIT))
      params.set('offset', String((page - 1) * PAGE_LIMIT))

      const res = await fetch(
        `${API_BASE_URL}/api/templates/list?${params.toString()}`
      )
      if (!res.ok) throw new Error(`목록 로드 오류 (${res.status})`)
      const data = await res.json()
      setTemplates(data.templates || [])
      setTotal(data.total ?? 0)
    } catch (err) {
      const message =
        err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다'
      setError(`오류: ${message}`)
    } finally {
      setIsLoading(false)
    }
  }, [selectedCategory, searchQuery, page])

  /** 양식 상세 로드 */
  const fetchDetail = useCallback(async (templateId: string) => {
    setDetailLoading(true)
    try {
      const res = await fetch(`${API_BASE_URL}/api/templates/${templateId}`)
      if (!res.ok) throw new Error('상세 정보 로드 실패')
      const data = await res.json()
      setDetail(data)
    } catch {
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  /** 양식 삭제 */
  const handleDeleteTemplate = useCallback(
    async (templateId: string) => {
      if (!window.confirm('정말 삭제하시겠습니까?')) return
      try {
        await fetch(`${API_BASE_URL}/api/templates/${templateId}`, {
          method: 'DELETE',
        })
        // 목록 새로고침
        fetchTemplates()
      } catch {
        setError('삭제 중 오류가 발생했습니다')
      }
    },
    [fetchTemplates]
  )

  /** 예시 삭제 */
  const handleDeleteExample = useCallback(
    async (exampleId: string) => {
      if (!window.confirm('정말 삭제하시겠습니까?')) return
      try {
        await fetch(`${API_BASE_URL}/api/templates/examples/${exampleId}`, {
          method: 'DELETE',
        })
        // 상세 새로고침
        if (detailId) fetchDetail(detailId)
      } catch {
        setError('예시 삭제 중 오류가 발생했습니다')
      }
    },
    [detailId, fetchDetail]
  )

  /** 검색 실행 */
  const handleSearch = () => {
    setSearchQuery(searchInput)
    setPage(1)
  }

  /** 카테고리 변경 */
  const handleCategoryChange = (value: string) => {
    setSelectedCategory(value)
    setPage(1)
  }

  /** 양식 카드 클릭 → 상세 보기 */
  const handleCardClick = (templateId: string) => {
    if (detailId === templateId) {
      setDetailId(null)
      setDetail(null)
    } else {
      setDetailId(templateId)
      fetchDetail(templateId)
    }
  }

  // 초기 데이터 로드
  useEffect(() => {
    fetchCategories()
  }, [fetchCategories])

  useEffect(() => {
    fetchTemplates()
  }, [fetchTemplates])

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      {/* 헤더 */}
      <div className="border-b border-gray-200 bg-white px-6 py-4 dark:border-gray-800 dark:bg-gray-900">
        <div className="mx-auto max-w-4xl">
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">
            양식 관리
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            양식과 예시 문서를 업로드하고 관리합니다
          </p>
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-6 py-6">
        {/* 상단 액션 버튼 */}
        <div className="mb-6 flex flex-wrap gap-3">
          <button
            onClick={() => setShowTemplateUpload(true)}
            className="flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700 dark:bg-primary-500 dark:hover:bg-primary-600"
          >
            <Upload size={16} />
            양식 업로드
          </button>
          <button
            onClick={() => setShowExampleUpload(true)}
            className="flex items-center gap-1.5 rounded-lg border border-primary-300 bg-white px-4 py-2 text-sm font-medium text-primary-600 transition-colors hover:bg-primary-50 dark:border-primary-600 dark:bg-gray-800 dark:text-primary-400 dark:hover:bg-gray-700"
          >
            <Plus size={16} />
            예시 업로드
          </button>
        </div>

        {/* 필터 / 검색 바 */}
        <div className="mb-6 flex flex-wrap items-center gap-3">
          {/* 카테고리 드롭다운 */}
          <div className="flex items-center gap-2">
            <label
              htmlFor="category-filter"
              className="text-sm text-gray-600 dark:text-gray-400"
            >
              카테고리:
            </label>
            <select
              id="category-filter"
              value={selectedCategory}
              onChange={(e) => handleCategoryChange(e.target.value)}
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300"
            >
              <option value="">전체</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          {/* 검색 */}
          <div className="flex flex-1 items-center gap-2">
            <label htmlFor="search-input" className="sr-only">
              검색
            </label>
            <input
              id="search-input"
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="양식 이름 검색..."
              className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 placeholder-gray-400 outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300 dark:placeholder-gray-500"
            />
            <button
              onClick={handleSearch}
              className="flex items-center gap-1.5 rounded-lg bg-gray-100 px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
            >
              <Search size={16} />
              검색
            </button>
          </div>
        </div>

        {/* 로딩 상태 */}
        {isLoading && (
          <div
            className="flex items-center justify-center py-12"
            data-testid="loading-spinner"
          >
            <Loader2 size={24} className="animate-spin text-primary-500" />
            <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">
              불러오는 중...
            </span>
          </div>
        )}

        {/* 에러 상태 */}
        {error && !isLoading && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}

        {/* 빈 상태 */}
        {!isLoading && !error && templates.length === 0 && (
          <div className="flex flex-col items-center justify-center rounded-lg border border-gray-200 bg-white py-12 dark:border-gray-700 dark:bg-gray-900">
            <FileText
              size={40}
              className="mb-3 text-gray-300 dark:text-gray-600"
            />
            <p className="text-sm text-gray-500 dark:text-gray-400">
              등록된 양식이 없습니다
            </p>
            <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
              양식 업로드 버튼을 눌러 새 양식을 등록하세요
            </p>
          </div>
        )}

        {/* 양식 목록 */}
        {!isLoading && !error && templates.length > 0 && (
          <div className="space-y-2">
            {templates.map((tpl) => (
              <div key={tpl.id}>
                {/* 양식 카드 */}
                <div
                  className={`flex items-center justify-between rounded-lg border bg-white px-4 py-3 transition-all dark:bg-gray-900 ${
                    detailId === tpl.id
                      ? 'border-primary-300 shadow-sm dark:border-primary-600'
                      : 'border-gray-200 hover:border-gray-300 dark:border-gray-700 dark:hover:border-gray-600'
                  }`}
                >
                  {/* 왼쪽: 제목 + 카테고리 */}
                  <button
                    onClick={() => handleCardClick(tpl.id)}
                    className="flex flex-1 items-center gap-3 text-left"
                  >
                    <FileText
                      size={18}
                      className="shrink-0 text-primary-500"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
                        {tpl.title}
                      </p>
                      <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">
                        등록일: {tpl.created_at}
                      </p>
                    </div>
                  </button>

                  {/* 오른쪽: 카테고리 뱃지 + 예시 수 + 삭제 */}
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                      {tpl.category}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {tpl.example_count}개 예시
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteTemplate(tpl.id)
                      }}
                      aria-label="삭제"
                      className="rounded-md p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-900/20 dark:hover:text-red-400"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                {/* 상세 보기 (확장) */}
                {detailId === tpl.id && (
                  <div className="mx-2 rounded-b-lg border border-t-0 border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/50">
                    {detailLoading ? (
                      <div className="flex items-center gap-2 py-4">
                        <Loader2
                          size={16}
                          className="animate-spin text-primary-500"
                        />
                        <span className="text-xs text-gray-500">
                          불러오는 중...
                        </span>
                      </div>
                    ) : detail ? (
                      <div className="space-y-3">
                        {/* 섹션 목록 */}
                        {detail.sections.length > 0 && (
                          <div>
                            <h4 className="mb-1.5 text-xs font-semibold text-gray-500 dark:text-gray-400">
                              섹션
                            </h4>
                            <div className="space-y-1">
                              {detail.sections.map((sec) => (
                                <div
                                  key={sec.section_index}
                                  className="rounded-md bg-white px-3 py-2 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                                >
                                  {sec.section_index + 1}.{' '}
                                  {sec.section_title}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* 연결된 예시 */}
                        {detail.examples.length > 0 && (
                          <div>
                            <h4 className="mb-1.5 text-xs font-semibold text-gray-500 dark:text-gray-400">
                              연결된 예시
                            </h4>
                            <div className="space-y-1">
                              {detail.examples.map((ex) => (
                                <div
                                  key={ex.id}
                                  className="flex items-center justify-between rounded-md bg-white px-3 py-2 dark:bg-gray-800"
                                >
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs text-gray-700 dark:text-gray-300">
                                      {ex.title}
                                    </span>
                                    {ex.is_public ? (
                                      <Eye
                                        size={12}
                                        className="text-green-500"
                                      />
                                    ) : (
                                      <EyeOff
                                        size={12}
                                        className="text-gray-400"
                                      />
                                    )}
                                  </div>
                                  <button
                                    onClick={() => handleDeleteExample(ex.id)}
                                    aria-label="예시 삭제"
                                    className="rounded-md p-1 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-900/20"
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {detail.sections.length === 0 &&
                          detail.examples.length === 0 && (
                            <p className="text-xs text-gray-400">
                              섹션과 예시가 없습니다
                            </p>
                          )}
                      </div>
                    ) : (
                      <p className="text-xs text-red-500">
                        상세 정보를 불러올 수 없습니다
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* 페이지네이션 */}
        {!isLoading && total > PAGE_LIMIT && (
          <div className="mt-6 flex items-center justify-center gap-4">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              aria-label="이전"
              className="flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-40 dark:border-gray-600 dark:text-gray-400 dark:hover:bg-gray-700"
            >
              <ChevronLeft size={16} />
              이전
            </button>
            <span className="text-sm text-gray-600 dark:text-gray-400">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              aria-label="다음"
              className="flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-600 transition-colors hover:bg-gray-100 disabled:opacity-40 dark:border-gray-600 dark:text-gray-400 dark:hover:bg-gray-700"
            >
              다음
              <ChevronRight size={16} />
            </button>
          </div>
        )}
      </div>

      {/* ─── 양식 업로드 모달 ─── */}
      {showTemplateUpload && (
        <TemplateUploadModal
          categories={categories}
          onClose={() => setShowTemplateUpload(false)}
          onUploaded={() => {
            setShowTemplateUpload(false)
            fetchTemplates()
          }}
        />
      )}

      {/* ─── 예시 업로드 모달 ─── */}
      {showExampleUpload && (
        <ExampleUploadModal
          categories={categories}
          onClose={() => setShowExampleUpload(false)}
          onUploaded={() => {
            setShowExampleUpload(false)
            fetchTemplates()
          }}
        />
      )}
    </div>
  )
}

// ─── 양식 업로드 모달 ───

interface TemplateUploadModalProps {
  categories: string[]
  onClose: () => void
  onUploaded: () => void
}

function TemplateUploadModal({
  categories,
  onClose,
  onUploaded,
}: TemplateUploadModalProps) {
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('')
  const [customCategory, setCustomCategory] = useState('')
  const [subCategory, setSubCategory] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [textContent, setTextContent] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const effectiveCategory = category === '__custom__' ? customCategory : category

  /** 파일 드래그앤드롭 */
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) setFile(dropped)
  }

  /** 업로드 실행 */
  const handleSubmit = async () => {
    if (!title.trim() || !effectiveCategory.trim()) return
    if (!file && !textContent.trim()) return

    setIsUploading(true)
    setUploadError(null)

    try {
      const formData = new FormData()
      formData.append('title', title.trim())
      formData.append('category', effectiveCategory.trim())
      if (subCategory.trim()) formData.append('sub_category', subCategory.trim())
      if (file) {
        formData.append('file', file)
      } else {
        formData.append('text_content', textContent.trim())
      }

      const res = await fetch(`${API_BASE_URL}/api/templates/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) throw new Error(`업로드 실패 (${res.status})`)
      onUploaded()
    } catch (err) {
      const message =
        err instanceof Error ? err.message : '업로드 중 오류가 발생했습니다'
      setUploadError(message)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 백드롭 */}
      <div
        data-testid="modal-backdrop"
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 모달 본체 */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="양식 업로드"
        className="relative z-10 mx-4 w-full max-w-lg rounded-xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-800"
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3.5 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <Upload size={16} className="text-primary-500" />
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              양식 업로드
            </h3>
          </div>
          <button
            onClick={onClose}
            aria-label="닫기"
            className="rounded-md p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300"
          >
            <X size={18} />
          </button>
        </div>

        {/* 본문 */}
        <div className="space-y-4 px-5 py-4">
          {/* 제목 */}
          <div>
            <label
              htmlFor="tpl-title"
              className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400"
            >
              제목 <span className="text-red-500">*</span>
            </label>
            <input
              id="tpl-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="양식 제목을 입력하세요"
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 placeholder-gray-400 outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300 dark:placeholder-gray-500"
            />
          </div>

          {/* 카테고리 */}
          <div>
            <label
              htmlFor="tpl-category"
              className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400"
            >
              카테고리 <span className="text-red-500">*</span>
            </label>
            <select
              id="tpl-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300"
            >
              <option value="">선택하세요</option>
              {(categories.length > 0 ? categories : CATEGORY_PRESETS).map(
                (cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                )
              )}
              <option value="__custom__">직접 입력</option>
            </select>
            {category === '__custom__' && (
              <input
                type="text"
                value={customCategory}
                onChange={(e) => setCustomCategory(e.target.value)}
                placeholder="카테고리를 직접 입력하세요"
                className="mt-2 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 placeholder-gray-400 outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300 dark:placeholder-gray-500"
              />
            )}
          </div>

          {/* 하위 카테고리 */}
          <div>
            <label
              htmlFor="tpl-sub-category"
              className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400"
            >
              하위 카테고리
            </label>
            <input
              id="tpl-sub-category"
              type="text"
              value={subCategory}
              onChange={(e) => setSubCategory(e.target.value)}
              placeholder="(선택) 하위 카테고리"
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 placeholder-gray-400 outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300 dark:placeholder-gray-500"
            />
          </div>

          {/* 파일 업로드 또는 텍스트 입력 */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400">
              파일 업로드 또는 텍스트 입력
            </label>

            {/* 파일 드래그앤드롭 영역 */}
            <div
              onDragOver={(e) => {
                e.preventDefault()
                setDragOver(true)
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              className={`rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
                dragOver
                  ? 'border-primary-400 bg-primary-50 dark:border-primary-500 dark:bg-primary-900/20'
                  : 'border-gray-200 bg-gray-50 dark:border-gray-600 dark:bg-gray-800'
              }`}
            >
              {file ? (
                <div className="flex items-center justify-center gap-2">
                  <FileText size={16} className="text-primary-500" />
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    {file.name}
                  </span>
                  <button
                    onClick={() => setFile(null)}
                    className="ml-1 rounded p-0.5 text-gray-400 hover:text-red-500"
                  >
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <>
                  <Upload
                    size={20}
                    className="mx-auto mb-2 text-gray-400"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    .hwpx 파일을 드래그하거나{' '}
                    <label className="cursor-pointer text-primary-500 hover:underline">
                      파일 선택
                      <input
                        type="file"
                        accept=".hwpx"
                        className="hidden"
                        onChange={(e) =>
                          setFile(e.target.files?.[0] ?? null)
                        }
                      />
                    </label>
                  </p>
                </>
              )}
            </div>

            {/* 텍스트 직접 입력 */}
            {!file && (
              <div className="mt-3">
                <p className="mb-1 text-xs text-gray-400 dark:text-gray-500">
                  또는 텍스트로 직접 입력:
                </p>
                <textarea
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  placeholder="양식 내용을 직접 입력하세요..."
                  rows={4}
                  className="w-full resize-none rounded-lg border border-gray-200 bg-white p-3 text-sm text-gray-700 placeholder-gray-400 outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300 dark:placeholder-gray-500"
                />
              </div>
            )}
          </div>

          {/* 업로드 에러 */}
          {uploadError && (
            <p className="text-sm text-red-600 dark:text-red-400">
              {uploadError}
            </p>
          )}
        </div>

        {/* 푸터 */}
        <div className="flex items-center justify-end gap-2 border-t border-gray-100 px-5 py-3 dark:border-gray-700">
          {isUploading && (
            <span className="flex items-center gap-1.5 text-xs text-gray-500">
              <Loader2 size={14} className="animate-spin" />
              업로드 중...
            </span>
          )}
          <button
            onClick={handleSubmit}
            disabled={
              !title.trim() ||
              !effectiveCategory.trim() ||
              (!file && !textContent.trim()) ||
              isUploading
            }
            className="flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-primary-500 dark:hover:bg-primary-600"
          >
            <Upload size={14} />
            업로드
          </button>
          <button
            onClick={onClose}
            disabled={isUploading}
            className="rounded-lg border border-gray-200 px-4 py-1.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:text-gray-400 dark:hover:bg-gray-700"
          >
            취소
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── 예시 업로드 모달 ───

interface ExampleUploadModalProps {
  categories: string[]
  onClose: () => void
  onUploaded: () => void
}

function ExampleUploadModal({
  categories,
  onClose,
  onUploaded,
}: ExampleUploadModalProps) {
  const [title, setTitle] = useState('')
  const [templateSearch, setTemplateSearch] = useState('')
  const [templateId, setTemplateId] = useState('')
  const [templateResults, setTemplateResults] = useState<
    Array<{ id: string; title: string }>
  >([])
  const [category, setCategory] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [textContent, setTextContent] = useState('')
  const [isPublic, setIsPublic] = useState(true)
  const [userId, setUserId] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [showTemplateDropdown, setShowTemplateDropdown] = useState(false)

  /** 양식 검색 (드롭다운용) */
  const searchTemplates = useCallback(async (query: string) => {
    if (!query.trim()) {
      setTemplateResults([])
      return
    }
    try {
      const params = new URLSearchParams({ query, limit: '5' })
      const res = await fetch(
        `${API_BASE_URL}/api/templates/list?${params.toString()}`
      )
      if (res.ok) {
        const data = await res.json()
        setTemplateResults(
          (data.templates || []).map((t: TemplateItem) => ({
            id: t.id,
            title: t.title,
          }))
        )
        setShowTemplateDropdown(true)
      }
    } catch {
      setTemplateResults([])
    }
  }, [])

  /** 파일 드래그앤드롭 */
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) setFile(dropped)
  }

  /** 업로드 실행 */
  const handleSubmit = async () => {
    if (!title.trim()) return
    if (!file && !textContent.trim()) return

    setIsUploading(true)
    setUploadError(null)

    try {
      const formData = new FormData()
      formData.append('title', title.trim())
      if (templateId) formData.append('template_id', templateId)
      if (category) formData.append('category', category)
      formData.append('is_public', String(isPublic))
      if (!isPublic && userId.trim()) {
        formData.append('user_id', userId.trim())
      }
      if (file) {
        formData.append('file', file)
      } else {
        formData.append('text_content', textContent.trim())
      }

      const res = await fetch(
        `${API_BASE_URL}/api/templates/examples/upload`,
        {
          method: 'POST',
          body: formData,
        }
      )

      if (!res.ok) throw new Error(`업로드 실패 (${res.status})`)
      onUploaded()
    } catch (err) {
      const message =
        err instanceof Error ? err.message : '업로드 중 오류가 발생했습니다'
      setUploadError(message)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 백드롭 */}
      <div
        data-testid="modal-backdrop"
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 모달 본체 */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="예시 업로드"
        className="relative z-10 mx-4 w-full max-w-lg rounded-xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-800"
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3.5 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <Plus size={16} className="text-primary-500" />
            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              예시 업로드
            </h3>
          </div>
          <button
            onClick={onClose}
            aria-label="닫기"
            className="rounded-md p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300"
          >
            <X size={18} />
          </button>
        </div>

        {/* 본문 */}
        <div className="max-h-[70vh] space-y-4 overflow-y-auto px-5 py-4">
          {/* 제목 */}
          <div>
            <label
              htmlFor="ex-title"
              className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400"
            >
              제목 <span className="text-red-500">*</span>
            </label>
            <input
              id="ex-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="예시 제목을 입력하세요"
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 placeholder-gray-400 outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300 dark:placeholder-gray-500"
            />
          </div>

          {/* 연결할 양식 (드롭다운 검색) */}
          <div className="relative">
            <label
              htmlFor="ex-template"
              className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400"
            >
              연결할 양식
            </label>
            <input
              id="ex-template"
              type="text"
              value={templateSearch}
              onChange={(e) => {
                setTemplateSearch(e.target.value)
                searchTemplates(e.target.value)
              }}
              onFocus={() =>
                templateResults.length > 0 && setShowTemplateDropdown(true)
              }
              placeholder="양식 이름으로 검색..."
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 placeholder-gray-400 outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300 dark:placeholder-gray-500"
            />
            {showTemplateDropdown && templateResults.length > 0 && (
              <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-40 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-600 dark:bg-gray-800">
                {templateResults.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => {
                      setTemplateId(t.id)
                      setTemplateSearch(t.title)
                      setShowTemplateDropdown(false)
                    }}
                    className="block w-full px-3 py-2 text-left text-xs text-gray-700 transition-colors hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700"
                  >
                    {t.title}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 카테고리 */}
          <div>
            <label
              htmlFor="ex-category"
              className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400"
            >
              카테고리
            </label>
            <select
              id="ex-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300"
            >
              <option value="">선택하세요</option>
              {(categories.length > 0 ? categories : CATEGORY_PRESETS).map(
                (cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                )
              )}
            </select>
          </div>

          {/* 공개/비공개 */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400">
              공개 설정
            </label>
            <div className="flex gap-4">
              <label className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="radio"
                  name="visibility"
                  checked={isPublic}
                  onChange={() => setIsPublic(true)}
                  className="text-primary-500"
                />
                공개
              </label>
              <label className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="radio"
                  name="visibility"
                  checked={!isPublic}
                  onChange={() => setIsPublic(false)}
                  className="text-primary-500"
                />
                비공개
              </label>
            </div>
            {!isPublic && (
              <input
                type="text"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="사용자 ID를 입력하세요"
                className="mt-2 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 placeholder-gray-400 outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300 dark:placeholder-gray-500"
              />
            )}
          </div>

          {/* 파일 업로드 또는 텍스트 입력 */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-gray-500 dark:text-gray-400">
              파일 업로드 또는 텍스트 입력
            </label>

            <div
              onDragOver={(e) => {
                e.preventDefault()
                setDragOver(true)
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              className={`rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
                dragOver
                  ? 'border-primary-400 bg-primary-50 dark:border-primary-500 dark:bg-primary-900/20'
                  : 'border-gray-200 bg-gray-50 dark:border-gray-600 dark:bg-gray-800'
              }`}
            >
              {file ? (
                <div className="flex items-center justify-center gap-2">
                  <FileText size={16} className="text-primary-500" />
                  <span className="text-sm text-gray-700 dark:text-gray-300">
                    {file.name}
                  </span>
                  <button
                    onClick={() => setFile(null)}
                    className="ml-1 rounded p-0.5 text-gray-400 hover:text-red-500"
                  >
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <>
                  <Upload
                    size={20}
                    className="mx-auto mb-2 text-gray-400"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    .hwpx 파일을 드래그하거나{' '}
                    <label className="cursor-pointer text-primary-500 hover:underline">
                      파일 선택
                      <input
                        type="file"
                        accept=".hwpx"
                        className="hidden"
                        onChange={(e) =>
                          setFile(e.target.files?.[0] ?? null)
                        }
                      />
                    </label>
                  </p>
                </>
              )}
            </div>

            {!file && (
              <div className="mt-3">
                <p className="mb-1 text-xs text-gray-400 dark:text-gray-500">
                  또는 텍스트로 직접 입력:
                </p>
                <textarea
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  placeholder="예시 내용을 직접 입력하세요..."
                  rows={4}
                  className="w-full resize-none rounded-lg border border-gray-200 bg-white p-3 text-sm text-gray-700 placeholder-gray-400 outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300 dark:placeholder-gray-500"
                />
              </div>
            )}
          </div>

          {/* 업로드 에러 */}
          {uploadError && (
            <p className="text-sm text-red-600 dark:text-red-400">
              {uploadError}
            </p>
          )}
        </div>

        {/* 푸터 */}
        <div className="flex items-center justify-end gap-2 border-t border-gray-100 px-5 py-3 dark:border-gray-700">
          {isUploading && (
            <span className="flex items-center gap-1.5 text-xs text-gray-500">
              <Loader2 size={14} className="animate-spin" />
              업로드 중...
            </span>
          )}
          <button
            onClick={handleSubmit}
            disabled={
              !title.trim() || (!file && !textContent.trim()) || isUploading
            }
            className="flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-primary-500 dark:hover:bg-primary-600"
          >
            <Upload size={14} />
            업로드
          </button>
          <button
            onClick={onClose}
            disabled={isUploading}
            className="rounded-lg border border-gray-200 px-4 py-1.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:text-gray-400 dark:hover:bg-gray-700"
          >
            취소
          </button>
        </div>
      </div>
    </div>
  )
}
