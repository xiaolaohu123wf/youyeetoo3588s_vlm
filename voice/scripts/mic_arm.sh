#!/bin/bash
# Lock mic routing; fight ES8388 jack handler when headphone playback is active.
set -euo pipefail
CARD="${1:-0}"
TRIES="${MIC_ARM_TRIES:-10}"
INTER="${MIC_ARM_INTERVAL:-0.06}"
TRIES="${TRIES//$'\r'/}"
INTER="${INTER//$'\r'/}"

source /userdata/voice/scripts/voice_env.sh 2>/dev/null || true
ROUTE="${MIC_ROUTE:-main_board}"
ROUTE="${ROUTE//$'\r'/}"

for _ in $(seq 1 "${TRIES}"); do
  bash /userdata/voice/scripts/mic_setup.sh "${CARD}" >/dev/null 2>&1 || true
  case "${ROUTE}" in
    main_board|main)
      amixer -c "${CARD}" cset numid=31 0 >/dev/null 2>&1 || true
      amixer -c "${CARD}" cset numid=30 1 >/dev/null 2>&1 || true
      ;;
  esac
  sleep "${INTER}"
done

read_mixer() {
  amixer -c "${CARD}" cget "numid=$1" 2>/dev/null | sed -n 's/^  : values=//p' | head -1
}

LMUX=$(read_mixer 36)
RMUX=$(read_mixer 37)
ALC=$(read_mixer 12)
NG=$(read_mixer 13)
MAIN=$(read_mixer 30)
HSET=$(read_mixer 31)

echo "[MIC-ARM] route=${ROUTE} LineMux=${LMUX:-?}/${RMUX:-?} ALC=${ALC:-?} NG=${NG:-?} Main=${MAIN:-?} Headset=${HSET:-?}" >&2

ok=1
if [ "${ALC}" != "0" ] || [ "${NG}" != "off" ]; then
  ok=0
fi

case "${ROUTE}" in
  main_board|main)
    [ "${LMUX}" = "3" ] && [ "${RMUX}" = "3" ] && [ "${MAIN}" = "on" ] || ok=0
    if [ "${HSET}" != "off" ]; then
      echo "[MIC-ARM] 警告: Headset=${HSET}（播放路由可能拉回），已强制关 Headset Mic" >&2
      amixer -c "${CARD}" cset numid=31 0 >/dev/null 2>&1 || true
      HSET=$(read_mixer 31)
    fi
    # LineMux + MainMic 正确即可继续（Headset 偶发读 on 但已强制关）
    ;;
  headset_line2)
    [ "${LMUX}" = "1" ] && [ "${RMUX}" = "1" ] && [ "${MAIN}" = "off" ] && [ "${HSET}" = "on" ] || ok=0
    ;;
  headset_line1)
    [ "${LMUX}" = "0" ] && [ "${RMUX}" = "0" ] && [ "${MAIN}" = "off" ] && [ "${HSET}" = "on" ] || ok=0
    ;;
  headset_miclr|*)
    [ "${LMUX}" = "3" ] && [ "${RMUX}" = "3" ] && [ "${MAIN}" = "off" ] && [ "${HSET}" = "on" ] || ok=0
    ;;
esac

if [ "${ok}" -eq 0 ]; then
  echo "[MIC-ARM] 路由未锁定，请检查 MIC_ROUTE=${ROUTE}" >&2
  exit 1
fi
