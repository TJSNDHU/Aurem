#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "transformers>=4.36.0",
#     "peft>=0.7.0",
#     "torch>=2.0.0",
#     "accelerate>=0.24.0",
#     "huggingface_hub>=0.20.0",
#     "sentencepiece>=0.1.99",
#     "protobuf>=3.20.0",
#     "numpy",
#     "gguf",
# ]
# ///

"""
GGUF Conversion Script - Production Ready

This script converts a LoRA fine-tuned model to GGUF format for use with:
- llama.cpp
- Ollama
- LM Studio
- Other GGUF-compatible tools

PREREQUISITES (install these FIRST):
- Ubuntu/Debian: sudo apt-get update && sudo apt-get install -y build-essential cmake
- RHEL/CentOS: sudo yum groupinstall -y "Development Tools" && sudo yum install -y cmake
- macOS: xcode-select --install && brew install cmake

Usage:
    Set environment variables:
    - ADAPTER_MODEL: Your fine-tuned model (e.g., "username/my-finetuned-model")
    - BASE_MODEL: Base model used for fine-tuning (e.g., "Qwen/Qwen2.5-0.5B")
    - OUTPUT_REPO: Where to upload GGUF files (e.g., "username/my-model-gguf")
    - HF_USERNAME: Your Hugging Face username (optional, for README)

Dependencies: All required packages are declared in PEP 723 header above.
"""

import os
import sys
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from huggingface_hub import HfApi
import subprocess


def check_system_dependencies():
    """Check if required system packages are available."""
    print("🔍 Checking system dependencies...")
    
    # Check for git
    if subprocess.run(["which", "git"], capture_output=True).returncode != 0:
        print("  ❌ git is not installed. Please install it:")
        print("     Ubuntu/Debian: sudo apt-get install git")
        print("     RHEL/CentOS: sudo yum install git")
        print("     macOS: brew install git")
        return False
    
    # Check for make or cmake
    has_make = subprocess.run