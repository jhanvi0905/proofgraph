#!/usr/bin/env bash
# Default: clone FinDVer and check that ContractNLI was placed manually.
# --suite DATASET_DIR: copy the suite evidence listed in examples/suite/manifest.json
# from a local dataset folder into data/suite/ and verify every sha256. Downloads nothing.
# docs/05-datasets-and-eval.md. data/ is gitignored.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${1:-}" == "--suite" ]]; then
  src="${2:-}"
  manifest="${SUITE_MANIFEST:-${root}/examples/suite/manifest.json}"
  out="${SUITE_DEST:-${root}/data/suite}"
  if [[ -z "${src}" || ! -d "${src}" ]]; then
    echo "usage: $0 --suite DATASET_DIR (a local folder; nothing is downloaded)" >&2
    exit 2
  fi
  if [[ ! -f "${manifest}" ]]; then
    echo "missing manifest: ${manifest}" >&2
    exit 1
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    hash_of() { sha256sum "$1" | cut -d' ' -f1; }
  else
    hash_of() { shasum -a 256 "$1" | cut -d' ' -f1; }
  fi
  while IFS=$'\t' read -r case_id name rel want; do
    from="${src}/${rel}"
    to="${out}/${case_id}/${name}"
    if [[ ! -f "${from}" ]]; then
      echo "missing: ${from}" >&2
      exit 1
    fi
    mkdir -p "${out}/${case_id}"
    cp "${from}" "${to}"
    got="$(hash_of "${to}")"
    if [[ "${got}" != "${want}" ]]; then
      rm -f "${to}"
      echo "sha256 mismatch: ${case_id}/${name} expected ${want} got ${got}" >&2
      exit 1
    fi
  done < <(python3 -I - "${manifest}" <<'PY'
import json, sys
for case in json.load(open(sys.argv[1]))["cases"]:
    for f in case["files"]:
        print("\t".join([case["id"], f["name"], f["path"], f["sha256"]]))
PY
)
  echo "suite evidence verified in ${out}"
  exit 0
fi

dest="${root}/data/FinDVer"

mkdir -p "${root}/data"

if [[ ! -d "${dest}" ]]; then
  git clone --depth 1 https://github.com/yilunzhao/FinDVer "${dest}"
fi

if [[ ! -d "${root}/data/contract-nli" ]]; then
  echo "ContractNLI is missing. Download contract-nli.zip from https://stanfordnlp.github.io/contract-nli/ and unzip it to data/contract-nli/." >&2
  exit 1
fi
