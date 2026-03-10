#!/bin/bash
# ==========================================================
# 파일명: copy_resource.sh
# 설명  : _resource 폴더를 현재 디렉토리로 복사합니다.
# 경로  : /home/chatsam-app/app/tasks/_resource/
# 사용법: bash copy_resource.sh
# ==========================================================

# 오류 발생 시 즉시 중단
set -e

# 복사할 원본 경로
SRC_PATH="/home/chatsam-app/app/tasks/_resource"

# 대상 경로
DEST_PATH="/home/upload/pdf/_resource"

# 기존 폴더가 있으면 삭제
if [ -d "$DEST_PATH" ]; then
    echo " 기존 폴더가 존재합니다: $DEST_PATH"
    echo " 기존 폴더를 삭제합니다..."
    rm -rf "$DEST_PATH"
fi

# 복사 실행
echo ""
echo " 복사 중: ${SRC_PATH} → ${DEST_PATH}"
cp -r "${SRC_PATH}" "${DEST_PATH}"

echo " 복사 완료: ${DEST_PATH}"
echo ""
