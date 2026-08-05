#!/usr/bin/env python3
"""One-time (re-)export of the embedding model to quantized ONNX.

Only needed if `EMBEDDING_MODEL_NAME` is ever changed — the checked-in
`assistant/models/ruri-v3-30m-onnx/` is what `assistant/embedding.py`
actually loads at runtime, on both local dev and Render. This script
itself needs the heavy PyTorch/transformers/onnx toolchain, but that's a
one-off local cost, not a runtime dependency:

    pip install torch transformers onnx onnxruntime

Usage:
    python scripts/export_embedding_model.py cl-nagoya/ruri-v3-30m assistant/models/ruri-v3-30m-onnx
"""
from __future__ import annotations

import sys
from pathlib import Path


def export(model_name: str, out_dir: Path) -> None:
    import torch
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from transformers import AutoModel, AutoTokenizer

    out_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()

    sample = tokenizer(["サンプルテキスト"], return_tensors="pt", padding=True, truncation=True, max_length=16)

    fp32_path = out_dir / "model_fp32_tmp.onnx"
    torch.onnx.export(
        model,
        (sample["input_ids"], sample["attention_mask"]),
        str(fp32_path),
        input_names=["input_ids", "attention_mask"],
        output_names=["last_hidden_state"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "sequence"},
            "attention_mask": {0: "batch", 1: "sequence"},
            "last_hidden_state": {0: "batch", 1: "sequence"},
        },
        opset_version=17,
        dynamo=False,
    )

    # Quantizing to int8 both shrinks the file (fp32 ~150MB -> int8 ~35MB,
    # comfortably under GitHub's 100MB single-file push limit) and cuts
    # runtime memory further — verified to preserve embedding similarity
    # within ~0.997 cosine of the original fp32 output.
    quantize_dynamic(str(fp32_path), str(out_dir / "model_int8.onnx"), weight_type=QuantType.QUInt8)
    fp32_path.unlink()

    tokenizer.save_pretrained(out_dir)
    print(f"Exported quantized ONNX model + tokenizer to {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    export(sys.argv[1], Path(sys.argv[2]))
