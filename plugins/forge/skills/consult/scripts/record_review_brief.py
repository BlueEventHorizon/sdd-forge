#!/usr/bin/env python3
"""consult brief の要旨と推奨案を、consult topic ごとの独立した記録として書く。

review から委譲された consult が、1 つの consult topic の consult brief を作り終えたときに呼ぶ。
置き場は評価 JSON のパスの親ディレクトリである。評価 JSON の中身は読まず、パスは置き場の基準に
だけ使う。記録のファイル名は ``consult_brief_{通し番号}.json`` で、通し番号は置き場にある既存の
記録の最大の番号に 1 を足した値（無ければ ``1``）を、本 script が採る。

記録は ``review_id``・``round_number``・``sequence``（通し番号）・``finding_ids``（昇順・重複なし）・
``summary``・``recommendation`` を持つ。``summary`` と ``recommendation`` は、渡された本文のファイルを
UTF-8 で読んだ内容を、生成・要約・改変せずに入れる。

一時ファイルへ書いてから、記録のファイル名へハードリンクして公開する。ハードリンクは同じ名前が
既にあると失敗するので、先に作られた記録を上書きしない。採番から公開までの間に同じ名前が作られた
ときは、通し番号を 1 進めて公開をやり直す。成功したときだけ、受け渡し本文の 2 つのファイルを削除する。
失敗したときは、記録も一時ファイルも残さず、受け渡し本文も変えない。

本 script は REQ-017 の FNC-014・NFR-002・NFR-005 の実装（DES-078 §5.2 M-07、§6.2〜§6.5）である。

## 終了コード

| code | 意味                                                                          |
| ---- | ----------------------------------------------------------------------------- |
| 0    | 記録した（標準出力に ``{"path": "<記録の絶対パス>"}``）                       |
| 1    | 区別のないエラー（標準出力の ``errors`` に理由。記録も一時ファイルも残さない） |
| 2    | 引数を受理できない（``argparse``）                                            |

Usage:
    python3 record_review_brief.py EVALUATION_JSON_PATH REVIEW_ID ROUND_NUMBER \\
        --finding-ids ID [ID ...] --summary-file PATH --recommendation-file PATH
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

_RECORD_NAME = re.compile(r"consult_brief_([0-9]+)\.json")


def emit(payload):
    """結果を、JSON object 1 つとして標準出力へ出す。"""
    json.dump(payload, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")


def fail(*messages):
    """失敗を、終了コード 1 と標準出力の ``errors`` で返す。戻り値を終了コードとして返すこと。"""
    emit({"errors": list(messages)})
    return 1


def parse_positive_int(text):
    """``1`` 以上の整数を表す文字列なら整数を返す。そうでなければ ``None``。"""
    if not re.fullmatch(r"[0-9]+", text):
        return None
    value = int(text)
    return value if value >= 1 else None


def argument_errors(args):
    """引数だけから分かる誤りを、理由の一覧で返す。無ければ空配列。"""
    errors = []
    for label, value in (
        ("評価JSON のパス", args.evaluation_path),
        ("--summary-file", args.summary_file),
        ("--recommendation-file", args.recommendation_file),
    ):
        if not Path(value).is_absolute():
            errors.append(f"{label} は絶対パスで渡してください: {value}")
        elif not Path(value).exists():
            errors.append(f"{label} が実在しません: {value}")
    if parse_positive_int(args.round_number) is None:
        errors.append(
            f"round_number は 1 以上の整数で渡してください: {args.round_number}"
        )
    bad = [v for v in args.finding_ids if parse_positive_int(v) is None]
    if bad:
        errors.append(f"--finding-ids は正の整数で渡してください: {', '.join(bad)}")
    return errors


def next_sequence(directory):
    """置き場にある既存の記録の最大の通し番号に 1 を足した値を返す。記録が無ければ 1。"""
    highest = 0
    for entry in directory.iterdir():
        match = _RECORD_NAME.fullmatch(entry.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def read_text(path, label):
    """本文のファイルを、加工せずに UTF-8 の文字列として読む。``(text, error)`` を返す。"""
    try:
        return Path(path).read_bytes().decode("utf-8"), None
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"{label} を UTF-8 として読めません: {path} ({exc})"


def publish(directory, sequence, build_record):
    """一時ファイルへ書き、記録のファイル名へハードリンクして公開する。``(記録のパス, 通し番号)`` を返す。

    同じ名前が既にあれば、通し番号を 1 進めてやり直す。``build_record`` は通し番号から記録の内容を作る。
    一時ファイルは、成功しても失敗しても残さない。
    """
    fd, tmp = tempfile.mkstemp(
        dir=str(directory), prefix=".consult_brief.", suffix=".tmp"
    )
    tmp_path = Path(tmp)
    try:
        os.close(fd)
        while True:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(build_record(sequence), fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            target = directory / f"consult_brief_{sequence}.json"
            try:
                os.link(tmp_path, target)
            except FileExistsError:
                sequence += 1
                continue
            return target, sequence
    finally:
        tmp_path.unlink(missing_ok=True)


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("evaluation_path")
    parser.add_argument("review_id")
    parser.add_argument("round_number")
    parser.add_argument("--finding-ids", dest="finding_ids", nargs="+", required=True)
    parser.add_argument("--summary-file", dest="summary_file", required=True)
    parser.add_argument(
        "--recommendation-file", dest="recommendation_file", required=True
    )
    return parser


def run_cli(argv=None):
    args = build_parser().parse_args(argv)

    errors = argument_errors(args)
    if errors:
        return fail(*errors)

    directory = Path(args.evaluation_path).parent
    if not directory.is_dir():
        return fail(
            f"置き場（評価JSON のパスの親ディレクトリ）がありません: {directory}"
        )

    finding_ids = sorted({int(v) for v in args.finding_ids})
    summary, problem = read_text(args.summary_file, "--summary-file")
    if problem:
        return fail(problem)
    recommendation, problem = read_text(
        args.recommendation_file, "--recommendation-file"
    )
    if problem:
        return fail(problem)

    def build_record(sequence):
        return {
            "review_id": args.review_id,
            "round_number": int(args.round_number),
            "sequence": sequence,
            "finding_ids": finding_ids,
            "summary": summary,
            "recommendation": recommendation,
        }

    try:
        target, _ = publish(directory, next_sequence(directory), build_record)
    except OSError as exc:
        return fail(f"記録を公開できません: {exc}")

    # 公開済みの記録は取り消さない。残った本文は、次の consult topic が上書きしてよい（DES-078 §6.2）
    for path in (args.summary_file, args.recommendation_file):
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass
    emit({"path": str(target)})
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
