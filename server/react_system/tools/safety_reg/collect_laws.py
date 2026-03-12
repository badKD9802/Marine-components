#!/usr/bin/env python3
"""안전법령 수집 스크립트.

사용법:
    # 1. 인증키 설정 (둘 중 하나)
    export LAW_API_OC="발급받은인증키"
    # 또는 아래 스크립트 실행 시 --oc 옵션

    # 2. 수집 실행
    cd /home/coder/chatsam-app-src
    python -m app.tasks.node_agent.aiassistant.function_calling.react_system.tools.safety_reg.collect_laws

    # 옵션:
    python -m ...collect_laws --oc YOUR_KEY          # 인증키 직접 전달
    python -m ...collect_laws --only 산업안전보건법    # 특정 법령만 수집
    python -m ...collect_laws --dry-run              # 검색만 (본문 미수집)
    python -m ...collect_laws --verify               # 기존 JSON 검증

결과:
    react_system/tools/safety_reg/data/laws/*.json  (법령별 JSON 파일)
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parents[4]  # safety_reg → tools → react_system → server
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from react_system.tools.safety_reg.law_api_client import LawApiClient
from react_system.tools.safety_reg.constants import LAW_LIST

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data" / "laws"


async def collect(oc: str, only: str = None, dry_run: bool = False):
    """법령 수집 메인 로직."""
    client = LawApiClient(oc=oc)

    # 수집 대상 필터링
    targets = LAW_LIST
    if only:
        targets = [(q, t, d) for q, t, d in LAW_LIST if only in q]
        if not targets:
            logger.error(f"'{only}'에 해당하는 법령이 목록에 없습니다.")
            logger.info("수집 가능한 법령:")
            for q, t, d in LAW_LIST:
                logger.info(f"  - {q} ({d})")
            return

    logger.info("=" * 60)
    logger.info(f"안전법령 수집 시작 — 대상 {len(targets)}건")
    logger.info(f"인증키: {oc[:4]}...{oc[-4:]}" if len(oc) > 8 else f"인증키: {oc}")
    logger.info(f"저장 경로: {DATA_DIR}")
    logger.info("=" * 60)

    success = 0
    failed = []

    for i, (query, target, doc_type) in enumerate(targets, 1):
        logger.info(f"\n[{i}/{len(targets)}] {query} (target={target}, type={doc_type})")

        # Step 1: 검색
        results = await client.search_law(query, target)
        if not results:
            logger.warning("  ❌ 검색 결과 없음")
            failed.append(query)
            await asyncio.sleep(0.5)
            continue

        mst = results[0].get("mst", "")
        name = results[0].get("법령명한글", query)
        logger.info(f"  ✅ 검색 성공: MST={mst}, 법령명={name}")

        if dry_run:
            logger.info("  ⏭️  dry-run: 본문 수집 건너뜀")
            success += 1
            await asyncio.sleep(0.5)
            continue

        await asyncio.sleep(0.5)

        # Step 2: 본문 조회
        doc = await client.get_law_full(mst, query, doc_type)
        if not doc:
            logger.warning("  ❌ 본문 조회 실패")
            failed.append(query)
            await asyncio.sleep(0.5)
            continue

        logger.info(f"  ✅ 본문 수집: 조문 {len(doc.articles)}건, 시행일 {doc.effective_date}")

        # JSON 저장
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        client._save_to_json(doc)
        json_path = DATA_DIR / f"{_safe_filename(doc.doc_name)}.json"
        if json_path.exists():
            logger.info(f"  📄 JSON 저장 완료: {json_path.name}")
        else:
            logger.warning("  ⚠️  JSON 파일 미생성 — 수동 확인 필요")

        success += 1
        await asyncio.sleep(0.5)

    # 결과 요약
    logger.info(f"\n{'=' * 60}")
    logger.info(f"수집 완료: {success}/{len(targets)}건 성공")
    if failed:
        logger.warning("실패 목록:")
        for q in failed:
            logger.warning(f"  - {q}")
    logger.info(f"JSON 저장 경로: {DATA_DIR}")

    # 저장된 파일 목록
    if DATA_DIR.exists():
        json_files = sorted(DATA_DIR.glob("*.json"))
        logger.info(f"\n저장된 JSON 파일 ({len(json_files)}건):")
        total_articles = 0
        for f in json_files:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                n_articles = len(data.get("articles", []))
                total_articles += n_articles
                logger.info(f"  📄 {f.name} — 조문 {n_articles}건")
        logger.info(f"\n전체 조문 수: {total_articles}건")

    logger.info(f"{'=' * 60}")


async def verify():
    """기존 JSON 파일 검증."""
    client = LawApiClient()
    documents = client.load_from_json()

    if not documents:
        logger.warning("JSON 파일이 없습니다. 먼저 수집을 실행하세요.")
        return

    logger.info(f"JSON 검증 — {len(documents)}건")
    logger.info("-" * 40)

    total_articles = 0
    for doc in documents:
        n = len(doc.articles)
        total_articles += n
        status = "✅" if n > 0 else "⚠️ 조문 없음"
        logger.info(f"  {status} {doc.doc_name} — 조문 {n}건, 시행일 {doc.effective_date}")

    logger.info("-" * 40)
    logger.info(f"전체: {len(documents)}문서, {total_articles}조문")

    # LAW_LIST 대비 누락 확인
    collected_names = {doc.doc_name for doc in documents}
    missing = [q for q, _, _ in LAW_LIST if not any(q in name or name in q for name in collected_names)]
    if missing:
        logger.warning(f"\n누락된 법령 ({len(missing)}건):")
        for q in missing:
            logger.warning(f"  - {q}")
    else:
        logger.info(f"\n✅ 전체 {len(LAW_LIST)}건 수집 완료!")


def _safe_filename(name: str) -> str:
    """파일명에 사용 불가한 문자 제거."""
    import re
    return re.sub(r'[^\w가-힣]', '_', name)


def main():
    parser = argparse.ArgumentParser(description="안전법령 수집 스크립트")
    parser.add_argument("--oc", type=str, default=None, help="법령 API 인증키 (OC)")
    parser.add_argument("--only", type=str, default=None, help="특정 법령만 수집 (부분 매칭)")
    parser.add_argument("--dry-run", action="store_true", help="검색만 수행 (본문 미수집)")
    parser.add_argument("--verify", action="store_true", help="기존 JSON 파일 검증")
    args = parser.parse_args()

    if args.verify:
        asyncio.run(verify())
        return

    # 인증키 확인
    import os
    oc = args.oc or os.getenv("LAW_API_OC", "")
    if not oc:
        logger.error("인증키가 필요합니다.")
        logger.error("  export LAW_API_OC='인증키'")
        logger.error("  또는 --oc 인증키")
        sys.exit(1)

    asyncio.run(collect(oc=oc, only=args.only, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
