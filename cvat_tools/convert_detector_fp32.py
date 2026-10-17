"""Promote FP16 ONNX operations to FP32 to match the verified CPU execution path."""
import hashlib
import json
from pathlib import Path
import numpy as np
import onnx
from onnx import TensorProto, numpy_helper

ROOT = Path(__file__).resolve().parent / 'models' / 'grounding-dino-tiny' / 'onnx'


def promote_tensor(tensor):
    if tensor.data_type == TensorProto.FLOAT16:
        tensor.CopyFrom(numpy_helper.from_array(numpy_helper.to_array(tensor).astype(np.float32), name=tensor.name))


def promote_graph(graph):
    for tensor in graph.initializer:
        promote_tensor(tensor)
    for value in list(graph.input) + list(graph.output) + list(graph.value_info):
        if value.type.tensor_type.elem_type == TensorProto.FLOAT16:
            value.type.tensor_type.elem_type = TensorProto.FLOAT
    for node in graph.node:
        for attr in node.attribute:
            if node.op_type == 'Cast' and attr.name == 'to' and attr.i == TensorProto.FLOAT16:
                attr.i = TensorProto.FLOAT
            if attr.type == onnx.AttributeProto.TENSOR:
                promote_tensor(attr.t)
            elif attr.type == onnx.AttributeProto.TENSORS:
                for tensor in attr.tensors:
                    promote_tensor(tensor)
            elif attr.type == onnx.AttributeProto.GRAPH:
                promote_graph(attr.g)
            elif attr.type == onnx.AttributeProto.GRAPHS:
                for subgraph in attr.graphs:
                    promote_graph(subgraph)


if __name__ == '__main__':
    source = ROOT / 'model_fp16.onnx'
    target = ROOT / 'model_promoted_fp32.onnx'
    model = onnx.load(source)
    promote_graph(model.graph)
    onnx.checker.check_model(model)
    onnx.save(model, target)
    report = {'source': source.name, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'target': target.name, 'target_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
              'method': 'Promote FLOAT16 tensors, value information and Cast destinations to FLOAT; retain rounded original weights.'}
    target.with_suffix('.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)
