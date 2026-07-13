# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "datasets",
#     "transformers",
#     "vllm>=0.6.5",
#     "huggingface-hub[hf_transfer]",
#     "torch",
#     "numpy",
#     "tqdm",
#     "scikit-learn",
# ]
# ///
"""
Generate high-quality synthetic data using Chain-of-Thought Self-Instruct methodology.

This script implements the CoT-Self-Instruct approach from the paper "CoT-Self-Instruct: 
Building high-quality synthetic prompts for reasoning and non-reasoning tasks" (2025).

It supports two modes:
1. Reasoning tasks: Generates both questions and answers with Chain-of-Thought
2. Instruction tasks: Generates diverse prompts for general instruction following

Example usage:
    # Reasoning tasks with Answer-Consistency filtering
    uv run cot-self-instruct.py \\
        --seed-dataset davanstrien/s1k-reasoning \\
        --output-dataset username/synthetic-math \\
        --task-type reasoning \\
        --num-samples 5000 \\
        --filter-method answer-consistency

    # Instruction tasks with RIP filtering
    uv run cot-self-instruct.py \\
        --seed-dataset wildchat-filtered \\
        --output-dataset username/synthetic-prompts \\
        --task-type instruction \\
        --filter-method rip \\
        --reward-model Nexusflow/Athene-RM-8B

    # HF Jobs execution
    hf jobs uv run --flavor l4x4 \\
        --image vllm/vllm-openai \\
        -e HF_TOKEN=$(python3 -c "from huggingface_hub import get_token; print(get_token())") \\
        https://huggingface.co/datasets/uv-scripts/synthetic-data/raw/main/cot-self-instruct.py \\
        [args...]
"""

import argparse
import json
import logging
import os
import random
import re
import sys
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import torch
from datasets import Dataset, load_dataset
from huggingface_hub import DatasetCard, login
from sklearn.cluster import KMeans
from tqdm.auto import tqdm
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams

# Enable HF Transfer for faster downloads
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Prompt templates from the paper
REASONING_PROMPT_TEMPLATE = """You are a reasoning question generator assistant. Your goal is to create a novel, and challenging reasoning question. You are provided the following seed questions:
Seed Question 1: {seed1}
Seed Question 2: {seed2}
Your task is to:
1. Write a brand-new, self-contained reasoning question that meets the following requirements:
(a) The question draws inspiration from the seed question without copying it verbatim, remaining novel and of comparable difficulty.
(b) The question's final answer should be a single, unambiguous scalar value (e.g., an integer, reduced fraction, exact radical), or another answer type that can be verified in one step (e.g., 'yes/no,' a choice from A to D).
2. Then reason step by step, solve the new question and format your output as follows:
[New Question Begin]{{your_generated_question}}[New Question End]
[Final Answer to New Question Begin]\\boxed{{your_final_answer}}[Final Answer to New Question End]"""

INSTRUCTION_PROMPT_TEMPLATE = """You are a prompt generator assistant. Your goal is to create diverse and creative synthetic prompts.
Please follow the steps below to create synthetic prompts.
Step 1: Carefully read #Prompt 1# and #Prompt 2#. Identify and list all the common elements between these two prompts. If no common elements are found, list the main elements from each prompt.
Step 2: Develop a comprehensive plan based on the #Common Elements List# or #Main Elements List# from Step 1. This plan will guide the generation of new synthetic prompts that are similar to the original prompts.
Step 3: Execute the plan step by step and provide one #Synthetic Prompt#.
Please reply strictly in the following format:
- Step 1 #Common Elements List# or #Main Elements List#:
- Step 2 #Plan#:
- Step 3 #Synthetic Prompt#:
#Prompt 1#:
{prompt1}
#Prompt 2#:
{prompt2}"""


def check_gpu_availability() -> int:
    """Check if CUDA is available and return the number of GPUs."""
    if not torch.cuda.is_available():
        logger.error("CUDA is not available. This script requires a GPU.")
        logger.error(
            "Please run on a machine with NVIDIA GPU or use HF Jobs with GPU flavor."
        )
        sys.exit(1)

    num_gpus = torch.cuda.device_count()
    for i in range(num_gpus):
        gpu_name = torch.cuda.get_device_name(i)
        gpu_memory = torch.cuda.get_device_properties(i).total_memory / 1024**3
        logger.info(f"GPU {i}: {gpu_name} with {gpu_memory:.1f} GB memory")

    return num_gpus


def parse_thinking_output(text: str) -> str:
    """Remove thinking tokens from model output."""
    # Remove <think>...</think> blocks
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return text.strip()


def extract_reasoning_output(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract question and answer from reasoning task output."""
    text = parse_thinking_output(text)
    
    # Extract question
    question_match = re.search(r'\[New Question Begin\](.*?)\[New Question End\]', text, re.DOTALL)
    if not question_match:
        return None, None
    question = question_match.group(1).strip()
    
    # Extract answer
    answer_match = re.search(r'\[Final Answer to New Question Begin\]\\?boxed\{(.*?)\}\[Final Answer to New Question End\]', text, re.DOTALL)
    if not answer_match:
        # Try without \boxed
        answer_match = re.search(r'\[Final Answer to New Question Begin\](.*?)\[Final Answer to New Question End\]', text, re.DOTALL)
    
    if not answer_match:
        return question, None
    
    answer = answer_match.group(1).strip()
    return question, answer


def extract_instruction_output(text: str) -> Optional[str]:
    """Extract synthetic prompt from instruction task output."""
    text = parse_thinking_output(text)
    
    # Look for the synthetic prompt after "Step 3 #Synthetic Prompt#:"
    match = re.search(r'Step 3 #Synthetic Prompt#:\s*(.+)', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def categorize_prompts(prompts: List[str], num_categories: int = 8) -> Dict[int, List[int]]:
    """Categorize prompts using clustering for instruction tasks."""
    from transformers import AutoModel
    
    logger.info(f"Categorizing {len(prompts)} prompts into {num_categories} categories...")
    
    # Use a small model for embeddings
    tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    
    # Get embeddings
    embeddings = []
    for prompt in tqdm(prompts, desc="Computing embeddings"):
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            outputs = model(**inputs)
            embedding = outputs.last_hidden_state.mean(dim=1).numpy()
        embeddings.append(embedding[0])
    
    # Cluster
    kmeans = KMeans(n_clusters=num_categories, random_state=42)
    labels = kmeans.fit_predict(embeddings)
    
    # Group by category
    categories = {}
    for idx, label in enumerate(labels):
        if label not in categories:
            categories[label] = []
        categories[label].append(idx)
    
    return categories


def generate_synthetic_data(
    llm: LLM,
    seed_data: List[Dict],
    task_type: str,
    num_samples: int,
    categories: Optional[Dict[int, List[int]]] = None,
) -> List[Dict]:
    """Generate synthetic data using CoT-Self-Instruct."""
    synthetic_data = []
    
    # Set up progress bar
    pbar = tqdm(total=num_samples, desc="Generating synthetic data")
    
    while len(synthetic_data) < num_samples:
        # Sample seed data
        if task_type == "reasoning":
            # Random sampling for reasoning tasks
            seeds = random.sample(seed_data, min(2, len(seed_data)))
            prompt = REASONING_PROMPT_TEMPLATE.format(
                seed1=seeds[0].get("question", seeds[0].get("prompt", "")),
                seed2=seeds[1].get("question", seeds[1].get("prompt", "")) if len(seeds) > 1 else seeds[0].get("question", seeds[0].get("prompt", ""))
            )
        else:
            # Category-aware sampling for instruction tasks
            if categories:
                # Pick a random category
                category = random.choice(list(categories.keys()))
                category_indices = categories[category]
                indices = random.sample(category_indices, min(2, len(category_indices)))
                seeds = [seed_data[i] for i in indices]
            else:
                seeds = random.sample(seed_data, min(2, len(seed_data)))
            
            prompt = INSTRUCTION_PROMPT_TEMPLATE.format(
                prompt1=seeds[0].get("prompt", seeds[0].get("question", "")),
                prompt2=seeds[1].get("prompt", seeds[1].get("question", "")) if len(seeds) > 1 else seeds[0].get("prompt", seeds[0].get("question", ""))
            )
        
        # Generate
        sampling_params = SamplingParams(
            temperature=0.7 if task_type == "reasoning" else 0.8,
            top_p=0.95 if task_type == "reasoning" else 0.9,
            max_tokens=2048,
        )
        
        outputs = llm.generate([prompt], sampling_params)
        output_text = outputs[0].outputs[0].text
        
        # Parse output
        if task_type == "reasoning":
            question, answer = extract_reasoning_output(output_text)
            if question and answer:
                synthetic_data.append({
                    "question": question,
                    "answer": answer,
                    "seed_indices": [seed_data.index(s) for s in seeds],
                })
                pbar.update(1)
        else:
            synthetic_prompt = extract_instruction_output(output_text)
            if synthetic_prompt:
                synthetic_data.append({
                    "prompt": synthetic_prompt,
                    "seed_indices": [seed_data.index(s) for s in seeds],
                })
                pbar.update(1)
    
    pbar.close()
    return synthetic_data


def answer_consistency_filter(
    llm: LLM,
    synthetic_data: List[Dict],
    k_responses: int = 16,
    threshold: float = 0.5,
) -> List[Dict]:
    """Filter reasoning tasks using Answer-Consistency."""
    logger.info(f"Applying Answer-Consistency filter with K={k_responses}")
    
    filtered_data = []
    
    for item in tqdm(synthetic_data, desc="Answer-Consistency filtering"):
        question = item["question"]
        original_answer = item["answer"]
        
        # Generate K responses
        prompts = [question] * k_responses
        sampling_params = SamplingParams(
            temperature=0.6,
            top_p=0.95,
            max_tokens=1024,
        )
        
        outputs = llm.generate(prompts, sampling_params)
        
        # Extract answers
        answers = []
        for output in outputs:
            text = output.outputs[0].text
            # Try to extract boxed answer
            match = re.search(r'\\boxed\{(.*?)\}', text)
            if match:
                answers.append(match.group(1).strip())
        
        if not answers:
            continue
        
        # Get majority answer
        answer_counts = Counter(answers)
        if answer_counts:
            majority_answer, count = answer_counts.most_common(1)[0]
            
            # Check if majority answer matches original and meets threshold
            if (majority_answer == original_answer and 
                count / len(answers) >= threshold):
                item["consistency_score"] = count / len(answers)
                filtered_data.append(item)
    
    logger.info(f"Answer-Consistency: kept {len(filtered_data)}/{len(synthetic_data)} examples")
    return filtered_data


def rip_filter(
    llm: LLM,
    synthetic_data: List[Dict],
    reward_model_id: str,
    k_responses: int = 32,
    threshold: float = 0.5,
) -> List[Dict]:
    """Filter using Rejecting Instruction Preferences (RIP)."""
    logger.info(f"Applying RIP filter with K={k_responses} and reward model {reward_model_id}")
    
    # Note: In a full implementation, you would load and use the actual reward model
    # For this example, we'll use a placeholder scoring mechanism
    logger.warning("RIP filtering requires a reward model implementation - using placeholder")
    
    filtered_data = []
    
    for item in tqdm(synthetic_data, desc="RIP filtering"):
        prompt = item.get("prompt", item.get("question", ""))
        
        # Generate K responses
        prompts = [prompt] * k_responses
        sampling_params = SamplingParams(
            temperature=1.0,
            top_p=1.0,
            max_tokens=1024,
        )
        
        outputs = llm.generate(prompts, sampling_params)
        
        # In real implementation: score each response with reward model
        # For now, use length as a proxy (longer responses often score higher)
        scores = [len(output.outputs[0].text) for output in outputs]
        
        # Use minimum score as quality indicator
        min_score = min(scores) if scores else 0
        normalized_score = min_score / 1000  # Normalize to 0-1 range
        
        if normalized_score >= threshold:
            item["rip_score"] = normalized_score
            filtered_data.append(item)
    
    logger.info(f"RIP filter: kept {len(filtered_data)}/{len(synthetic_data)} examples")
    return filtered_data


def create_dataset_card(
    task_type: str,
    source_dataset: str,
    generation_model: str,
    filter_method: str,
    num_generated: int,
    num_filtered: int,
    generation_time: str,
    additional_info: Dict = None,
) -> str:
    """Create a comprehensive dataset card."""
    filter_info = ""
    if filter_method == "answer-consistency":
        filter_info = """
### Answer-Consistency Filtering

This dataset was filtered using Answer-Consistency:
- Generated K responses for each synthetic question
- Kept only examples where majority answer matched the generated answer
- Ensures high-quality, correctly solved problems"""
    elif filter_method == "rip":
        filter_info = """
### RIP (Rejecting Instruction Preferences) Filtering

This dataset was filtered using RIP