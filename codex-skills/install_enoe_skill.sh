#!/usr/bin/env bash
set -euo pipefail

force=0
if [[ "${1:-}" == "--force" ]]; then
  force=1
elif [[ "${1:-}" != "" ]]; then
  echo "Usage: bash codex-skills/install_enoe_skill.sh [--force]" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
skill_dir="${script_dir}/enoe-quarterly-agent"
codex_home="${CODEX_HOME:-${HOME}/.codex}"
skills_dir="${codex_home}/skills"
target_link="${skills_dir}/enoe-quarterly-agent"
validator="${skills_dir}/.system/skill-creator/scripts/quick_validate.py"

if [[ ! -f "${validator}" ]]; then
  echo "Skill validator not found: ${validator}" >&2
  exit 2
fi

python3 "${validator}" "${skill_dir}"
mkdir -p "${skills_dir}"

if [[ -L "${target_link}" ]]; then
  rm "${target_link}"
elif [[ -e "${target_link}" ]]; then
  if [[ "${force}" -ne 1 ]]; then
    echo "Refusing to overwrite non-symlink target: ${target_link}" >&2
    echo "Re-run with --force to replace it." >&2
    exit 2
  fi
  rm -rf "${target_link}"
fi

ln -s "${skill_dir}" "${target_link}"
echo "Installed enoe-quarterly-agent -> ${target_link}"

