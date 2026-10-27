#!/bin/sh
set -e
pulseaudio -D --exit-idle-time=-1 2>/dev/null || true
exec xvfb-run -a -s "-screen 0 1280x800x24" python -m agent_compte_rendu.zoom "$@"
