# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "datasets",
#     "flashinfer-python",
#     "huggingface-hub[hf_transfer]",
#     "hf-xet>= 1.1.7",
#     "torch",
#     "transformers",
#     "vllm>=0.8.5",
# ]
#
# ///
"""
Generate responses for prompts in a dataset using vLLM for efficient GPU inference.

This script loads a dataset from Hugging Face Hub containing chat-formatted messages,
applies the model's chat template, generates responses using vLLM, and saves the
results back to the Hub with a comprehensive dataset card.

Example usage:
    # Local execution with auto GPU detection
    uv run generate-responses.py \\
        username/input-dataset \\
        username/output-dataset \\
        --messages-column messages

    # With custom model and sampling parameters
    uv run generate-responses.py \\
        username/input-dataset \\
        username/output-dataset \\
        --model-id meta-llama/Llama-3.1-8B-Instruct \\
        --temperature 0.9 \\
        --top-p 0.95 \\
        --max-tokens 2048

    # HF Jobs execution (see script output for full command)
    hf jobs uv run --flavor a100x4 ...
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Optional

from datasets import load_dataset
from huggingface_hub import DatasetCard, get_token, login
from torch import cuda
from tqdm.auto import tqdm
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams

# Enable HF Transfer for faster downloads
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_gpu_availability() -> int:
    """Check if CUDA is available and return the number of GPUs."""
    if not cuda.is_available():
        logger.error("CUDA is not available. This script requires a GPU.")
        logger.error(
            "Please run on a machine with NVIDIA GPU or use HF Jobs with GPU flavor."
        )
        sys.exit(1)

    num_gpus = cuda.device_count()
    for i in range(num_gpus):
        gpu_name = cuda.get_device_name(i)
        gpu_memory = cuda.get_device_properties(i).total_memory / 1024**3
        logger.info(f"GPU {i}: {gpu_name} with {gpu_memory:.1f} GB memory")

    return num_gpus


def create_dataset_card(
    source_dataset: str,
    model_id: str,
    messages_column: str,
    prompt_column: Optional[str],
    sampling_params: SamplingParams,
    tensor_parallel_size: int,
    num_examples: int,
    generation_time: str,
    num_skipped: int = 0,
    max_model_len_used: Optional[int] = None,
) -> str:
    """Create a comprehensive dataset card documenting the generation process."""
    filtering_section = ""
    if num_skipped > 0:
        skip_percentage = (num_skipped / num_examples) * 100
        processed = num_examples - num_skipped
        filtering_section = f"""

### Filtering Statistics

- **Total Examples**: {num_examples:,}
- **Processed**: {processed:,} ({100 - skip_percentage:.1f}%)
- **Skipped (too long)**: {num_skipped:,} ({skip_percentage:.1f}%)
- **Max Model Length Used**: {max_model_len_used:,} tokens

Note: Prompts exceeding the maximum model length were skipped and have empty responses."""

    max_model_len_option = (
        f" \\\\\\n    --max-model-len {max_model_len_used}"
        if max_model_len_used
        else ""
    )

    return f"""---
tags:
- generated
- vllm
- uv-script
---

# Generated Responses Dataset

This dataset contains generated responses for prompts from [{source_dataset}](https://huggingface.co/datasets/{source_dataset}).

## Generation Details

- **Source Dataset**: [{source_dataset}](https://huggingface.co/datasets/{source_dataset})
- **Input Column**: `{prompt_column if prompt_column else messages_column}` ({"plain text prompts" if prompt_column else "chat messages"})
- **Model**: [{model_id}](https://huggingface.co/{model_id})
- **Number of Examples**: {num_examples:,}
- **Generation Date**: {generation_time}{filtering_section}

### Sampling Parameters

- **Temperature**: {sampling_params.temperature}
- **Top P**: {sampling_params.top_p}
- **Top K**: {sampling_params.top_k}
- **Min P**: {sampling_params.min_p}
- **Max Tokens**: {sampling_params.max_tokens}
- **Repetition Penalty**: {sampling_params.repetition_penalty}

### Hardware Configuration

- **Tensor Parallel Size**: {tensor_parallel_size}
- **GPU Configuration**: {tensor_parallel_size} GPU(s)

## Dataset Structure

The dataset contains all columns from the source dataset plus