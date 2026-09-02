#!/usr/bin/env python3
import argparse
import json
import re

from deck_run_state import load_deck, load_jobs, read_json, run_dir_from_target, save_deck, write_json

BACKEND_CHOICES = ["editppt-image-cli", "openai-compatible-api", "dsh-current"]

CONNECTION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{7,63}$")
# 疑似秘密样式：API Key 形态、Bearer/JWT、URL、显式凭据词。dsh-current 契约一律拒绝。
SECRET_LIKE_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|Bearer\s|eyJ[A-Za-z0-9_-]{8,}\.|api[_-]?key|access[_-]?token|"
    r"credentialref|password|secret|://)",
    re.IGNORECASE,
)


def _safe_scalar(value, label, max_length):
    if value is None or str(value).strip() == "":
        raise SystemExit(f"dsh-current 契约缺少必填项：--{label}")
    text = str(value).strip()
    if len(text) > max_length:
        raise SystemExit(f"dsh-current 契约字段过长（≤{max_length}）：--{label}")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in text):
        raise SystemExit(f"dsh-current 契约字段包含控制字符：--{label}")
    if SECRET_LIKE_RE.search(text):
        raise SystemExit(f"dsh-current 契约字段疑似秘密值（禁止 Key/Token/Base URL 进入契约）：--{label}")
    return text


def dsh_backend_contract(args):
    connection_id = _safe_scalar(args.connection_id, "connection-id", 64)
    if not CONNECTION_ID_RE.match(connection_id):
        raise SystemExit("dsh-current 契约的 --connection-id 不是合法 DSH 连接 ID")
    connection_name = _safe_scalar(args.connection_name, "connection-name", 64)
    model = _safe_scalar(args.model, "model", 160)
    protocol = _safe_scalar(args.image_protocol, "image-protocol", 64)
    return {
        "backend_id": "dsh-current",
        "tool_name": "editable_ppt_image",
        "connection_binding": "run-start-pinned",
        "connection_id": connection_id,
        "connection_name": connection_name,
        "model": model,
        "protocol": protocol,
        "requires_openai_api_key": False,
        "allow_codex": False,
        "fallback_policy": "none",
        "mode_policy": "generate-or-edit-per-asset",
        "save_path_policy": "write one output directly inside the owning page directory",
        "handoff_rule": "call editable_ppt_image serially with the pinned connectionId; never call editppt image generate/edit",
    }


def backend_contract(args):
    if args.backend_id == "dsh-current":
        return dsh_backend_contract(args)
    requires_api_key = args.backend_id == "openai-compatible-api"
    return {
        "backend_id": args.backend_id,
        "tool_name": args.tool_name,
        "tool_call": args.tool_call,
        "fallback_command": args.fallback_command,
        "runtime_home": args.runtime_home,
        "model": args.model,
        "requires_openai_api_key": requires_api_key,
        "mode_policy": "generate-or-edit-per-asset",
        "chroma_key_helper": "editppt image process-sheet",
        "input_context_policy": args.input_context_policy,
        "save_path_policy": "write outputs directly to page dir or copy selected outputs before manifest references them",
        "handoff_rule": args.handoff_rule,
    }


def main():
    parser = argparse.ArgumentParser(description="Record the run-level image backend contract.")
    parser.add_argument("run")
    parser.add_argument("--backend-id", default="editppt-image-cli", choices=BACKEND_CHOICES)
    parser.add_argument("--tool-name")
    parser.add_argument("--tool-call")
    parser.add_argument("--model", default=None)
    parser.add_argument("--fallback-command")
    parser.add_argument("--runtime-home", default="~/.editppt")
    parser.add_argument("--input-context-policy", default="pass edit targets and strict visual references via editppt image edit --image")
    parser.add_argument("--connection-id", help="dsh-current：任务开始时锁定的 DSH 生图连接 ID")
    parser.add_argument("--connection-name", help="dsh-current：连接显示名（非敏感）")
    parser.add_argument("--image-protocol", help="dsh-current：已验证的生图协议，例如 openai-images")
    parser.add_argument(
        "--handoff-rule",
        help="Override the handoff rule note for non-dsh backends. Defaults to the legacy Codex-first editppt image CLI wording.",
    )
    args = parser.parse_args()

    if args.backend_id == "dsh-current":
        # dsh-current 没有 Codex/API 回退；不得被写回旧 handoff 文案。
        # 模型必须显式来自 status 返回，不允许落入默认值掩盖缺参。
        if args.model is None:
            raise SystemExit("dsh-current 契约缺少必填项：--model（必须显式携带锁定连接的模型名）")
        args.tool_name = "editable_ppt_image"
        args.tool_call = None
        args.fallback_command = None
    else:
        if args.model is None:
            args.model = "gpt-image-2"
        if args.handoff_rule is None:
            args.handoff_rule = "call editppt image generate/edit serially; the CLI selects Codex OAuth first and OpenAI-compatible API fallback second"
        if args.tool_name is None:
            args.tool_name = "editppt image"
        if args.tool_call is None:
            args.tool_call = "editppt image generate/edit"
        if args.fallback_command is None:
            args.fallback_command = "editppt image"

    run_dir = run_dir_from_target(args.run)
    deck = load_deck(run_dir)
    contract = backend_contract(args)
    deck["image_backend"] = contract
    save_deck(run_dir, deck)

    jobs = load_jobs(run_dir)
    for page in jobs.get("pages", []):
        request_path = run_dir / page["page_request"]
        request = read_json(request_path)
        request["image_backend"] = contract
        write_json(request_path, request)
    print(json.dumps({"image_backend": contract}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
