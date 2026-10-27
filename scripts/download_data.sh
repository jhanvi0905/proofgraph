#!/usr/bin/env bash
# Clone FinDVer and check that ContractNLI was placed manually.
# docs/05-datasets-and-eval.md. data/ is gitignored.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest="${root}/data/FinDVer"

mkdir -p "${root}/data"

if [[ ! -d "${dest}" ]]; then
  git clone --depth 1 https://github.com/yilunzhao/FinDVer "${dest}"
fi

if [[ ! -d "${root}/data/contract-nli" ]]; then
  echo "ContractNLI is missing. Download contract-nli.zip from https://stanfordnlp.github.io/contract-nli/ and unzip it to data/contract-nli/." >&2
  exit 1
fi
