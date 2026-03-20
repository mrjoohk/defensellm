import sys
sys.path.insert(0, '/home/rtv-24n10/defenseLLM_claude/src')
from defense_llm.serving.qwen_adapter import Qwen25Adapter

adapter = Qwen25Adapter(preload=True)
import torch
print(f"Model device: {adapter._model.device}")
print(f"CUDA memory: {torch.cuda.memory_allocated()} bytes")
