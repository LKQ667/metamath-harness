#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from uuid import uuid4

from deck_run_state import now_iso, read_json, resolve_inside, sha256_file, write_json

EDITABLE_PPT_METADATA_SCHEMA = "dsh.mathmodel.editable-ppt-image-metadata/v1"
METADATA_ALLOWED_KEYS = {
    "schema", "createdAt", "connectionId", "connectionName", "template", "model",
    "protocol", "operation", "promptSha256", "inputSha256", "size", "quality", "files",
}
FILE_ENTRY_ALLOWED_KEYS = {"file", "sha256", "mime"}
SECRET_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{8,}|Bearer\s|eyJ[A-Za-z0-9_-]{8,}\.|AIza[A-Za-z0-9_-]{15,}|://|api[_-]?key|access[_-]?token|credentialref|authorization)", re.IGNORECASE)


def _fail(reason: str) -> None:
    raise SystemExit(f"DSH metadata provenance rejected: {reason}")


def _deck_backend_above(start_dir: Path):
    directory = start_dir.resolve()
    visited = set()
    while True:
        candidate = directory / "deck_manifest.json"
        if candidate.is_file():
            try:
                deck = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                _fail(f"运行清单无法解析：{candidate}（{exc}）")
            backend = deck.get("image_backend") if isinstance(deck, dict) else None
            return backend if isinstance(backend, dict) else None
        key = str(directory)
        if key in visited:
            return None
        visited.add(key)
        parent = directory.parent
        if parent == directory:
            return None
        directory = parent


def validate_dsh_metadata(metadata_path: Path, dest: Path, backend: dict) -> dict:
    """§7.3 六项校验；任一失败即拒绝登记（抛出 SystemExit，不写 jobs）。"""
    if not metadata_path.is_file():
        _fail("--metadata-file 指向的 DSH 元数据文件不存在")
    try:
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _fail(f"元数据 JSON 无法解析：{exc}")
    if not isinstance(meta, dict):
        _fail("元数据必须是对象")
    # 5) 已知敏感字段拒绝（含未知键白名单，杜绝 Base URL/Key/Token/credentialRef 混入）
    unknown = set(meta.keys()) - METADATA_ALLOWED_KEYS
    if unknown:
        _fail(f"元数据包含未知/敏感字段：{sorted(unknown)}")
    serialized = json.dumps(meta, ensure_ascii=False)
    if SECRET_VALUE_RE.search(serialized):
        _fail("元数据包含疑似秘密值或 URL，禁止登记")
    # 1) schema 正确
    if meta.get("schema") != EDITABLE_PPT_METADATA_SCHEMA:
        _fail(f"元数据 schema 必须为 {EDITABLE_PPT_METADATA_SCHEMA}")
    # 2) 连接 ID 等于运行锁定 ID
    if meta.get("connectionId") != backend.get("connection_id"):
        _fail("元数据 connectionId 与运行锁定的 connection_id 不一致（provenance_mismatch）")
    # 4) protocol/model 与运行契约一致
    if meta.get("protocol") != backend.get("protocol") or meta.get("model") != backend.get("model"):
        _fail("元数据 protocol/model 与运行契约不一致（provenance_mismatch）")
    files = meta.get("files")
    if not isinstance(files, list) or len(files) != 1 or not isinstance(files[0], dict):
        _fail("元数据 files 必须恰好包含一个输出条目")
    entry = files[0]
    if set(entry.keys()) - FILE_ENTRY_ALLOWED_KEYS:
        _fail("元数据 files 条目包含未知字段")
    # 3) 元数据输出哈希等于实际文件哈希
    if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", ""))):
        _fail("元数据输出哈希不是 64 位十六进制")
    if entry["sha256"] != sha256_file(dest):
        _fail("元数据输出哈希与实际文件不一致")
    return meta


def atomic_copy(source: Path, dest: Path) -> None:
    """先完整复制到同目录临时文件，再原子替换目标；失败不留下半文件。"""
    temp = dest.with_name(f".{dest.name}.{uuid4().hex}.tmp")
    try:
        shutil.copy2(source, temp)
        temp.replace(dest)
    finally:
        temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(
        prog="editppt image import",
        description="Copy a selected generated image into a page directory and record provenance.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  editppt image import <page_dir> --job-id clean-base-1 --source-image /tmp/generated.png --dest assets/clean_base.png --role clean_base
  editppt image import <page_dir> --job-id icon-sheet-1 --source-image sheet.png --dest assets/sheet.png --role asset_sheet --prompt-file prompts/icon-sheet.md
  editppt image import <page_dir> --job-id base-1 --source-image <dsh result file> --dest assets/base.png --role clean_base --prompt-file prompts/base.md --metadata-file <dsh metadataFile>
""",
    )
    parser.add_argument("page_dir", help="Page directory that owns imagegen-jobs.json and receives the copied asset.")
    parser.add_argument("--job-id", required=True, help="Stable job id to create or update inside imagegen-jobs.json.")
    parser.add_argument("--source-image", required=True, help="Generated image selected by the agent, usually from editppt image output or another approved image backend output.")
    parser.add_argument("--dest", required=True, help="Destination path relative to page_dir; absolute paths are rejected.")
    parser.add_argument("--role", default="asset", help="Asset role recorded in the job, for example clean_base, asset_sheet, or asset.")
    parser.add_argument("--prompt-file", help="Optional prompt file path used to create the selected image.")
    parser.add_argument("--metadata-file", help="DSH editable_ppt_image metadata JSON. Required in dsh-current runs; optional provenance note otherwise.")
    parser.add_argument("--note", help="Short provenance or approval note recorded with the job.")
    args = parser.parse_args()

    page_dir = Path(args.page_dir).resolve()
    if not page_dir.exists():
        raise SystemExit(f"Page dir does not exist: {page_dir}")
    source = Path(args.source_image).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Generated image does not exist: {source}")
    dest = resolve_inside(page_dir, args.dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    backend = _deck_backend_above(page_dir)
    dsh_run = isinstance(backend, dict) and backend.get("backend_id") == "dsh-current"
    metadata_path = Path(args.metadata_file).expanduser().resolve() if args.metadata_file else None
    meta = None
    recorded_metadata_path = None
    if dsh_run:
        if metadata_path is None:
            raise SystemExit("DSH metadata provenance rejected: dsh-current 运行的 import 必须携带 --metadata-file")
        # 在任何资产复制前，以来源文件完成 provenance 校验；失败不得污染页面目录。
        meta = validate_dsh_metadata(metadata_path, source, backend)

    if source != dest:
        atomic_copy(source, dest)

    if dsh_run:
        # 元数据必须与资产同页保存：不在页内时复制进 dest 旁边。
        try:
            recorded_metadata_path = metadata_path.relative_to(page_dir)
        except ValueError:
            sidecar = dest.parent / f"{dest.stem}.dsh-image.json"
            if metadata_path != sidecar:
                atomic_copy(metadata_path, sidecar)
            recorded_metadata_path = sidecar.relative_to(page_dir)

    jobs_path = page_dir / "imagegen-jobs.json"
    jobs = read_json(jobs_path, default={"schema_version": 1, "jobs": []})
    existing = None
    for item in jobs.get("jobs", []):
        if item.get("job_id") == args.job_id:
            existing = item
            break
    if existing is None:
        existing = {"job_id": args.job_id}
        jobs.setdefault("jobs", []).append(existing)
    record = {
        "role": args.role,
        "status": "recorded",
        "source_image": str(source),
        "output": dest.relative_to(page_dir).as_posix(),
        "output_sha256": sha256_file(dest),
        "prompt_file": args.prompt_file,
        "note": args.note,
        "recorded_at": now_iso(),
    }
    if dsh_run:
        record.update(
            {
                "metadata_file": Path(recorded_metadata_path).as_posix(),
                "metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
                "connection_id": meta.get("connectionId"),
                "model": meta.get("model"),
                "protocol": meta.get("protocol"),
            }
        )
    elif metadata_path is not None:
        record["metadata_file"] = str(metadata_path)
    existing.update(record)
    jobs["updated_at"] = now_iso()
    write_json(jobs_path, jobs)
    print(dest)


if __name__ == "__main__":
    main()
