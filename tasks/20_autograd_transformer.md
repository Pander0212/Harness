---
topic: ml
legacy_title: Autograd-Engine, neuronale Netze und ein kleiner Transformer von Grund auf
---
# Autograd Engine, Neural Networks and a Small Transformer from Scratch

## Goal
Implement, in pure Python 3 (standard library only; no NumPy), a tensor library with
automatic differentiation, and on top of it neural network layers, optimizers, a BPE
tokenizer and a small decoder-only transformer trained on a text corpus. Efficiency in
pure Python is part of the task. Scope: at least 8 hours of focused work.

## Functional Requirements
1. **Tensors**: n-dimensional arrays (flat list + shape + strides), broadcasting,
   indexing and slicing, reshape/transpose/permute as views, reductions along axes,
   matmul (batched), concatenation, float dtype.
2. **Autograd**: dynamic computation graph, topological sort, backward pass for all
   operations including broadcast reduction of gradients, `no_grad` context, gradient
   accumulation, `detach`.
3. **Gradient check**: numerical gradients (central differences) for every operation.
4. **Layers**: Linear, Embedding, LayerNorm, Dropout, activations (ReLU, GELU, Tanh,
   softmax in a numerically stable form), cross-entropy (stable, with label smoothing),
   Conv1D, residual blocks; parameter management, `state_dict`, saving and loading.
5. **Optimizers**: SGD with momentum/Nesterov, Adam, AdamW, learning rate schedulers
   (warmup + cosine), gradient clipping.
6. **BPE tokenizer**: training on a corpus, merges, encoding/decoding (lossless, byte
   fallback), special tokens, saving/loading.
7. **Transformer**: multi-head self-attention with a causal mask, positional embeddings
   (learned and rotary/RoPE), feed-forward, pre-LN blocks; training on a small corpus (e.g.
   self-written texts or public-domain material included in the project), sampling with
   temperature, top-k and top-p; KV cache for fast generation.
8. **Classic tasks**: MLP on a synthetic spiral dataset, classification of procedurally
   generated 8×8 digits; learning curves as CSV.

## Test Strategy (pytest)
- Gradient check for every operation and layer (at least 80 cases, different shapes and
  broadcasting configurations).
- Tensor semantics against a naive reference (nested lists) for 300 random operations.
- Optimizers against hand-computed steps; tokenizer round trip over Unicode.
- Learning ability: spiral dataset > 95 % accuracy; the transformer overfits a small text
  (loss falls below a threshold); the KV cache yields identical logits.
- At least 250 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; training results and run times in DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
