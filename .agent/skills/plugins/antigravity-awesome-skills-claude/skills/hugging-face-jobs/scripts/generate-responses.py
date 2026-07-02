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

The dataset contains all columns from the source dataset plus:
- `response`: The generated response from the model

## Generation Script

Generated using the vLLM inference script from [uv-scripts/vllm](https://huggingface.co/datasets/uv-scripts/vllm).

To reproduce this generation:

```bash
uv run https://huggingface.co/datasets/uv-scripts/vllm/raw/main/generate-responses.py \\
    {source_dataset} \\
    <output-dataset> \\
    --model-id {model_id} \\
    {"--prompt-column " + prompt_column if prompt_column else "--messages-column " + messages_column} \\
    --temperature {sampling_params.temperature} \\
    --top-p {sampling_params.top_p} \\
    --top-k {sampling_params.top_k} \\
    --max-tokens {sampling_params.max_tokens}{f" \\\\\\n    --max-model-len {max_model_len_used}" if max_model_len_used else ""}
```
"""


def main(
    src_dataset_hub_id: str,
    output_dataset_hub_id: str,
    model_id: str = "Qwen/Qwen3-30B-A3B-Instruct-2507",
    messages_column: str = "messages",
    prompt_column: Optional[str] = None,
    output_column: str = "response",
    temperature: float = 0.7,
    top_p: float = 0.8,
    top_k: int = 20,
    min_p: float = 0.0,
    max_tokens: int = 16384,
    repetition_penalty: float = 1.0,
    gpu_memory_utilization: float = 0.90,
    max_model_len: Optional[int] = None,
    tensor_parallel_size: Optional[int] = None,
    skip_long_prompts: bool = True,
    max_samples: Optional[int] = None,
    hf_token: Optional[str] = None,
):
    """
    Main generation pipeline.

    Args:
        src_dataset_hub_id: Input dataset on Hugging Face Hub
        output_dataset_hub_id: Where to save results on Hugging Face Hub
        model_id: Hugging Face model ID for generation
        messages_column: Column name containing chat messages
        prompt_column: Column name containing plain text prompts (alternative to messages_column)
        output_column: Column name for generated responses
        temperature: Sampling temperature
        top_p: Top-p sampling parameter
        top_k: Top-k sampling parameter
        min_p: Minimum probability threshold
        max_tokens: Maximum tokens to generate
        repetition_penalty: Repetition penalty parameter
        gpu_memory_utilization: GPU memory utilization factor
        max_model_len: Maximum model context length (None uses model default)
        tensor_parallel_size: Number of GPUs to use (auto-detect if None)
        skip_long_prompts: Skip prompts exceeding max_model_len instead of failing
        max_samples: Maximum number of samples to process (None for all)
        hf_token: Hugging Face authentication token
    """
    generation_start_time = datetime.now().isoformat()

    # GPU check and configuration
    num_gpus = check_gpu_availability()
    if tensor_parallel_size is None:
        tensor_parallel_size = num_gpus
        logger.info(
            f"Auto-detected {num_gpus} GPU(s), using tensor_parallel_size={tensor_parallel_size}"
        )
    else:
        logger.info(f"Using specified tensor_parallel_size={tensor_parallel_size}")
        if tensor_parallel_size > num_gpus:
            logger.warning(
                f"Requested {tensor_parallel_size} GPUs but only {num_gpus} available"
            )

    # Authentication - try multiple methods
    HF_TOKEN = hf_token or os.environ.get("HF_TOKEN") or get_token()

    if not HF_TOKEN:
        logger.error("No HuggingFace token found. Please provide token via:")
        logger.error("  1. --hf-token argument")
        logger.error("  2. HF_TOKEN environment variable")
        logger.error("  3. Run 'hf auth login' or use login() in Python")
        sys.exit(1)

    logger.info("HuggingFace token found, authenticating...")
    login(token=HF_TOKEN)

    # Initialize vLLM
    logger.info(f"Loading model: {model_id}")
    vllm_kwargs = {
        "model": model_id,
        "tensor_parallel_size": tensor_parallel_size,
        "gpu_memory_utilization": gpu_memory_utilization,
    }
    if max_model_len is not None:
        vllm_kwargs["max_model_len"] = max_model_len
        logger.info(f"Using max_model_len={max_model_len}")

    llm = LLM(**vllm_kwargs)

    # Load tokenizer for chat template
    logger.info("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)

    # Create sampling parameters
    sampling_params = SamplingParams(
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        min_p=min_p,
        max_tokens=max_tokens,
        repetition_penalty=repetition_penalty,
    )

    # Load dataset
    logger.info(f"Loading dataset: {src_dataset_hub_id}")
    dataset = load_dataset(src_dataset_hub_id, split="train")

    # Apply max_samples if specified
    if max_samples is not None and max_samples < len(dataset):
        logger.info(f"Limiting dataset to {max_samples} samples")
        dataset = dataset.select(range(max_samples))

    total_examples = len(dataset)
    logger.info(f"Dataset loaded with {total_examples:,} examples")

    # Determine which column to use and validate
    if prompt_column:
        # Use prompt column mode
        if prompt_column not in dataset.column_names:
            logger.error(
                f"Column '{prompt_column}' not found. Available columns: {dataset.column_names}"
            )
            sys.exit(1)
        logger.info(f"Using prompt column mode with column: '{prompt_column}'")
        use_messages = False
    else:
        # Use messages column mode
        if messages_column not in dataset.column_names:
            logger.error(
                f"Column '{messages_column}' not found. Available columns: {dataset.column_names}"
            )
            sys.exit(1)
        logger.info(f"Using messages column mode with column: '{messages_column}'")
        use_messages = True

    # Get effective max length for filtering
    if max_model_len is not None:
        effective_max_len = max_model_len
    else:
        # Get model's default max length
        effective_max_len = llm.llm_engine.model_config.max_model_len
    logger.info(f"Using effective max model length: {effective_max_len}")

    # Process messages and apply chat template
    logger.info("Preparing prompts...")
    all_prompts = []
    valid_prompts = []
    valid_indices = []
    skipped_info = []

    for i, example in enumerate(tqdm(dataset, desc="Processing prompts")):
        if use_messages:
            # Messages mode: use existing chat messages
            messages = example[messages_column]
            # Apply chat template
            prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            # Prompt mode: convert plain text to messages format
            user_prompt = example[prompt_column]
            messages = [{"role": "user", "content": user_prompt}]
            # Apply chat template
            prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )

        all_prompts.append(prompt)

        # Count tokens if filtering is enabled
        if skip_long_prompts:
            tokens = tokenizer.encode(prompt)
            if len(tokens) <= effective_max_len:
                valid_prompts.append(prompt)
                valid_indices.append(i)
            else:
                skipped_info.append((i, len(tokens)))
        else:
            valid_prompts.append(prompt)
            valid_indices.append(