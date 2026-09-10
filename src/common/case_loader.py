#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用例目录扫描与元数据加载模块
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any


def load_and_validate_case(
    case_dir: Path,
    logger: logging.Logger,
) -> Tuple[Dict[str, Any], List[Path], List[Path], Path]:
    """读取并验证用例元数据配置 meta.json 及多文件源列表"""
    meta_path = case_dir / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing metadata configuration file: {meta_path}")

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in {meta_path}: {e}")

    top_name = meta.get("design_name")
    if not top_name:
        raise ValueError(f"'design_name' must be specified in {meta_path}")

    src_orig_dir = case_dir / "src_orig"
    src_opt_dir = case_dir / "src_opt"
    tb_path = case_dir / "tb" / "tb_top.v"

    if not src_orig_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src_orig_dir}")
    if not src_opt_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src_opt_dir}")
    if not tb_path.exists():
        raise FileNotFoundError(f"Dedicated testbench not found: {tb_path}")

    def resolve_sources(src_dir: Path, source_list: Optional[List[str]]) -> List[Path]:
        if source_list and len(source_list) > 0:
            resolved = []
            for s in source_list:
                f = src_dir / s
                if not f.exists():
                    raise FileNotFoundError(f"Declared source file not found: {f}")
                resolved.append(f.resolve())
            return resolved
        all_sources = sorted(list(src_dir.glob("*.v")) + list(src_dir.glob("*.sv")))
        if not all_sources:
            raise FileNotFoundError(f"No .v or .sv files found in {src_dir}")
        return [p.resolve() for p in all_sources]

    sources_orig = resolve_sources(src_orig_dir, meta.get("sources_orig"))
    sources_opt = resolve_sources(src_opt_dir, meta.get("sources_opt"))

    logger.info(f"Loaded Benchmark Case: {case_dir.name}")
    logger.info(f"  Top Module:       {top_name}")
    logger.info(f"  Orig Sources ({len(sources_orig)}): {[f.name for f in sources_orig]}")
    logger.info(f"  Opt Sources  ({len(sources_opt)}): {[f.name for f in sources_opt]}")
    logger.info(f"  Testbench:        {tb_path}")

    return meta, sources_orig, sources_opt, tb_path.resolve()

