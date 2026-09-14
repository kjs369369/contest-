#!/usr/bin/env bash
# 전시회 영상 편집 도구 설치 스크립트 (프로젝트 본체와 의존성 분리)
set -euo pipefail
cd "$(dirname "$0")"

echo "▶ 1/3 파이썬 가상환경 준비 (.venv)"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "▶ 2/3 ffmpeg 확인"
python3 - <<'PY'
import sys
sys.path.insert(0, ".")
from lib.env import find_ffmpeg, available_korean_font
print("   ffmpeg :", find_ffmpeg())
print("   한글폰트:", available_korean_font())
PY

echo "▶ 3/3 한글 폰트 안내"
if ! fc-list :lang=ko 2>/dev/null | grep -qiE "nanum|noto"; then
  echo "   ! 한글 폰트가 없습니다. 자막이 깨질 수 있습니다."
  echo "     Ubuntu/Debian : sudo apt-get install -y fonts-nanum fonts-noto-cjk"
  echo "     macOS         : 기본 AppleSDGothicNeo 사용 (추가 설치 불필요)"
  echo "     Windows       : 기본 맑은 고딕 사용 (추가 설치 불필요)"
else
  echo "   한글 폰트 확인 완료"
fi

echo
echo "설치 완료. 다음 순서로 사용하세요:"
echo "  1) media/photos, media/videos 에 사진·영상을 넣습니다"
echo "  2) captions.csv 에 작품명·설명을 적습니다 (선택)"
echo "  3) source .venv/bin/activate && python3 build_video.py --preview   # 시험 렌더"
echo "  4) python3 build_video.py                                          # 최종 렌더"
