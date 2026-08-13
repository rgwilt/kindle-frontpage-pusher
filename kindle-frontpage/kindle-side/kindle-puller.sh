#!/bin/sh
# kindle-puller.sh
#
# Runs ON THE KINDLE (not in the Docker container). Pulls the latest
# processed front page from the kindle-frontpage-pusher container and draws
# it full-screen with FBInk. Install this via KUAL's cron/extensions
# mechanism (or any other jailbreak cron facility) to run every 10-15
# minutes -- it's cheap (a single HTTP GET) and will simply redraw the same
# image if nothing changed since the last poll, so polling more often than
# the container updates is harmless.
#
# Requires: FBInk installed on the Kindle (standard on most jailbreaks,
# see https://github.com/NiLuJe/FBInk), and network access to the host
# running the Docker container.

# EDIT THIS: host:port of the machine running the kindle-frontpage container.
SERVER_URL="http://192.168.1.10:8080/current.png"

DEST_DIR="/mnt/us/frontpage"
DEST="$DEST_DIR/current.png"
TMP="$DEST.tmp"

mkdir -p "$DEST_DIR"

# -q quiet, -O write to file, short timeouts so a flaky Wi-Fi connection
# doesn't hang whatever cron facility is calling this script.
if wget -q -T 15 -O "$TMP" "$SERVER_URL"; then
    # Only redraw if the image actually changed, to avoid an unnecessary
    # full-screen flash every time this script runs.
    if ! cmp -s "$TMP" "$DEST" 2>/dev/null; then
        mv "$TMP" "$DEST"
        # -g file=...   draw the image full-screen, scaled to fit
        # -c            clear the screen first
        # -d            let FBInk dither it to the panel's native depth
        fbink -g file="$DEST" -c -d
    else
        rm -f "$TMP"
    fi
else
    rm -f "$TMP"
    echo "kindle-puller: failed to fetch $SERVER_URL" >&2
fi
