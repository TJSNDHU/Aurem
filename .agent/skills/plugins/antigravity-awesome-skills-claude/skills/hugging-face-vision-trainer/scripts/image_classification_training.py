# /// script
# dependencies = [
#     "transformers>=5.2.0",
#     "accelerate>=1.1.0",
#     "timm",
#     "datasets>=4.0",
#     "evaluate",
#     "scikit-learn",
#     "torchvision",
#     "trackio",
#     "huggingface_hub",
# ]
# ///

"""Fine-tuning any Transformers or timm model supported by AutoModelForImageClassification using the Trainer API."""

import logging
import os
import sys
from dataclasses import dataclass, field
from functools import partial
from typing import Any

import evaluate
import numpy as np
import torch
from datasets import load_dataset
from torchvision.transforms import (
    CenterCrop,
    Compose,
    Normalize,
    RandomHorizontalFlip,
    RandomResizedCrop,
    Resize,
    ToTensor,
)

import trackio

import transformers
from transformers import (
    AutoConfig,
    AutoImageProcessor,
    AutoModelForImageClassification,
    DefaultDataCollator,
    HfArgumentParser,
    Trainer,
    TrainingArguments,
)
from transformers.trainer import EvalPrediction
from transformers.utils import check_min_version
from transformers.utils.versions import require_version


logger = logging.getLogger(__name__)

check_min_version("4.57.0.dev0")
require_version("datasets>=2.0.0")


@dataclass
class DataTrainingArguments:
    dataset_name: str = field(
        default="ethz/food101",
        metadata={"help": "Name of a dataset from the Hub."},
    )
    dataset_config_name: str | None = field(
        default=None,
        metadata={"help": "The configuration name of the dataset to use (via the datasets library)."},
    )
    train_val_split: float | None = field(
        default=0.15,
        metadata={"help": "Fraction to split off of train for validation (used only when no validation split exists)."},
    )
    max_train_samples: int | None = field(
        default=None,
        metadata={"help": "Truncate training set to this many samples (for debugging / quick tests)."},
    )
    max_eval_samples: int | None = field(
        default=None,
        metadata={"help": "Truncate evaluation set to this many samples."},
    )
    image_column_name: str = field(
        default="image",
        metadata={"help": "The column name for images in the dataset."},
    )
    label_column_name: str = field(
        default="label",
        metadata={"help": "The column name for labels in the dataset."},
    )


@dataclass
class ModelArguments:
    model_name_or_path: str = field(
        default="timm/mobilenetv3_small_100.lamb_in1k",
        metadata={"help": "Path to pretrained model or model identifier from huggingface.co/models."},
    )
    config_name: str | None = field(
        default=None,
        metadata={"help": "Pretrained config name or path if not the same as model_name."},
    )
    cache_dir: str | None = field(
        default=None,
        metadata={"help": "Where to store pretrained models downloaded from the Hub."},
    )
    model_revision: str = field(
        default="main",
        metadata={"help": "The specific model version to use (branch, tag, or commit id)."},
    )
    image_processor_name: str | None = field(
        default=None,
        metadata={"help": "Name or path of image processor config."},
    )
    ignore_mismatched_sizes: bool = field(
        default=True,
        metadata={"help": "Allow loading weights when num_labels differs from pretrained checkpoint."},
    )
    token: str | None = field(
        default=None,
        metadata={"help": "Auth token for private models / datasets."},
    )
    trust_remote_code: bool = field(
        default=False,
        metadata={"help": "Whether to trust remote code from Hub repos."},
    )


def build_transforms(image_processor, is_training: bool):
    """Build torchvision transforms from the image processor's config."""
    if hasattr(image_processor, "size"):
        size = image_processor.size
        if "shortest_edge" in size:
            img_size = size["shortest_edge"]
        elif "height" in size and "width" in size:
            img_size = (size["height"], size["width"])
        else:
            img_size = 224
    else:
        img_size = 224

    if hasattr(image_processor, "image_mean") and image_processor.image_mean:
        normalize = Normalize(mean=image_processor.image_mean, std=image_processor.image_std)
    else:
        normalize = Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])

    if is_training:
        return Compose([
            RandomResizedCrop(img_size),
            RandomHorizontalFlip(),
            ToTensor(),
            normalize,
        ])
    else:
        if isinstance(img_size, int):
            resize_size = int(img_size / 0.875)  # standard 87.5% center crop ratio
        else:
            resize_size = tuple(int(s / 0.875) for s in img_size)
        return Compose([
            Resize(resize_size),
            CenterCrop(img_size),
            ToTensor(),
            normalize,
        ])


def parse_arguments():
    """Parse command-line or JSON file arguments."""
    parser = HfArgumentParser((ModelArguments, DataTrainingArguments, TrainingArguments))
    if len(sys.argv) == 2 and sys.argv[1].endswith(".json"):
        model_args, data_args, training_args = parser.parse_json_file(json_file=os.path.abspath(sys.argv[1]))
    else:
        model_args, data_args, training_args = parser.parse_args_into_dataclasses()
    return model_args, data_args, training_args


def setup_hub_auth(training_args):
    """Authenticate with the Hugging Face Hub if a token is available."""
    from huggingface_hub import login
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("hfjob")
    if hf_token:
        login(token=hf_token)
        training_args.hub_token = hf_token
        logger.info("Logged in to Hugging Face Hub")
    elif training_args.push_to_hub:
        logger.warning("HF_TOKEN not found in environment. Hub push will likely fail.")


def setup_logging(training_args):
    """Configure logging verbosity and format."""
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    if training_args.should_log:
        transformers.utils.logging.set_verbosity_info()

    log_level = training_args.get_process_log_level()
    logger.setLevel(log_level)
    transformers.utils.logging.set_verbosity(log_level)
    transformers.utils.logging.enable_default_handler()
    transformers.utils.logging.enable_explicit_format()

    logger.warning(
        f"Process rank: {training_args.local_process_index}, device: {training_args.device}, "
        f"n_gpu: {training_args.n_gpu}, distributed training: "
        f"{training_args.parallel_mode.value == 'distributed'}, 16-bits training: {training_args.fp16}"
    )
    logger.info(f"Training/evaluation parameters {training_args}")


def load_and_prepare_dataset(data_args, model_args, training_args):
    """Load dataset, resolve labels, remap strings, split, and truncate."""
    # --- Load dataset ---
    dataset = load_dataset(
        data_args.dataset_name,
        data_args.dataset_config_name,
        cache_dir=model_args.cache_dir,
        trust_remote_code=model_args.trust_remote_code,
    )

    # --- Resolve label column ---
    label_col = data_args.label_column_name
    if label_col not in dataset["train"].column_names:
        candidates = [c for c in dataset["train"].column_names if c in ("label", "labels", "class", "fine_label")]
        if candidates:
            label_col = candidates[0]
            logger.info(f"Label column '{data_args.label_column_name}' not found, using '{label_col}'")
        else:
            raise ValueError(
                f"Label column '{data_args.label_column_name}' not found. "
                f"Available columns: {dataset['train'].column_names}"
            )

    # --- Discover labels ---
    label_feature = dataset["train"].features[label_col]
    if hasattr(label_feature, "names"):
        label_names = label_feature.names
    else:
        unique_labels = sorted(set(dataset["train"][label_col]))
        if all(isinstance(l, str) for l in unique_labels):
            label_names = unique_labels
        else:
            label_names = [str(l) for l in unique_labels]

    num_labels = len(label_names)
    id2label = dict(enumerate(label_names))
    label2id = {v: k for k, v in id2label.items()}
    logger.info(f"Number of classes: {num_labels}")

    # --- Remap string labels to int if needed ---
    sample_label = dataset["train"][0][label_col]
    if isinstance(sample_label, str):
        logger.info("Remapping string labels to integer IDs")
        for split_name in list(dataset.keys()):
            dataset[split_name] = dataset[split_name].map(
                lambda ex: {label_col: label2id[ex[label_col]]},
            )

    # --- Shuffle + Train/val split ---
    dataset["train"] = dataset["train"].shuffle(seed=training_args.seed)

    data_args.train_val_split = None if "validation" in dataset else data_args.train_val_split
    if isinstance(data_args.train_val_split, float) and data_args.train_val_split > 0.0:
        split = dataset["train"].train_test_split(data_args.train_val_split, seed=training_args.seed)
        dataset["train"] = split["train"]
        dataset["validation"] = split["test"]

    # --- Truncate ---
    if data_args.max_train_samples is not None:
        max_train = min(data_args.max_train_samples, len(dataset["train"]))
        dataset["train"] = dataset["train"].select(range(max_train))
        logger.info(f"Truncated training set to {max_train} samples")
    if data_args.max_eval_samples is not None and "validation" in dataset:
        max_eval = min(data_args.max_eval_samples, len(dataset["validation"]))
        dataset["validation"] = dataset["validation"].select(range(max_eval))
        logger.info(f"Truncated validation set to {max_eval} samples")

    return dataset, label_col, num_labels, label2id, id2label


def load_model_and_processor(model_args, num_labels, label2id, id2label):
    """Load model config, model, and image processor from the Hub."""
    common_pretrained_args = {
        "cache_dir": model_args.cache_dir,
        "revision": model_args.model_revision,