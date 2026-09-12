#!/usr/bin/env bash
# Build the Pilot Implementation's headless SysMLInteractive fat jar at a
# pinned commit, then compile adapters/pilot_glue/Main.java against it.
#
# Requires: JDK 21 specifically (a local clone of
# Systems-Modeling/SysML-v2-Pilot-Implementation, this is a Maven/Tycho
# reactor build -- the first run downloads a real amount of Eclipse p2
# metadata and can take a while).
#
# JDK 21, not "whatever JDK you have": confirmed on this machine that a
# JDK 26 (`brew install openjdk`) makes org.omg.sysml's Xtend compilation
# fail with ~150,000 "resource is empty: java:/Objects/..." /
# "resolution of uriFragment '|N' failed" errors -- Xtend/Xbase's JRE
# TypeReferences indexing doesn't handle that JDK's layout. This is a real,
# understood incompatibility, not a flaky build; retrying with the same
# JDK will not help. Point JAVA_HOME at a JDK 21 (e.g.
# `brew install openjdk@21`) before running this script.
#
# Usage:
#   PILOT_REPO=/path/to/SysML-v2-Pilot-Implementation \
#   PILOT_COMMIT=<sha> \
#   toolchain/get-pilot-jar.sh
#
# Prints, on success, the classpath to export as PILOT_GLUE_CLASSPATH and
# the jar's sha256 (record as the Version's svt:artifactDigest).

set -euo pipefail

: "${PILOT_REPO:?set PILOT_REPO to a local clone of Systems-Modeling/SysML-v2-Pilot-Implementation}"
: "${PILOT_COMMIT:?set PILOT_COMMIT to the exact commit to build}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/.cache/pilot/$PILOT_COMMIT"
mkdir -p "$OUT"

echo "== checking out $PILOT_COMMIT in $PILOT_REPO ==" >&2
git -C "$PILOT_REPO" checkout --quiet "$PILOT_COMMIT"

echo "== building org.omg.sysml.interactive (first run downloads p2 metadata; can take a while) ==" >&2
# `install`, not `package`: org.omg.sysml.model.bundle depends on
# org.omg.sysml.model as a plain jar artifact (not p2), which only lands in
# the local repo once its own reactor module has been installed.
( cd "$PILOT_REPO" && ./mvnw -q -pl org.omg.sysml.interactive -am -DskipTests clean install )

FAT_JAR=$(find "$PILOT_REPO/org.omg.sysml.interactive/target" -maxdepth 1 -name "org.omg.sysml.interactive-*-all.jar" | head -1)
if [ -z "$FAT_JAR" ]; then
	echo "error: fat jar not found under $PILOT_REPO/org.omg.sysml.interactive/target" >&2
	exit 1
fi
cp "$FAT_JAR" "$OUT/interactive-all.jar"

echo "== compiling adapters/pilot_glue/Main.java ==" >&2
javac -cp "$OUT/interactive-all.jar" -d "$OUT/classes" "$ROOT/adapters/pilot_glue/Main.java"

echo "== sha256 of the fat jar (record as the Version's svt:artifactDigest) ==" >&2
shasum -a 256 "$OUT/interactive-all.jar"

echo "export PILOT_GLUE_CLASSPATH=\"$OUT/interactive-all.jar:$OUT/classes\""
