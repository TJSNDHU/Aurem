# /// script
# dependencies = [
#     "transformers>=5.2.0",
#     "accelerate>=1.1.0",
#     "albumentations >= 1.4.16",
#     "timm",
#     "datasets>=4.0",
#     "torchmetrics",
#     "pycocotools",
#     "trackio",
#     "huggingface_hub",
# ]
# ///

"""Finetuning any 🤗 Transformers model supported by AutoModelForObjectDetection for object detection leveraging the Trainer API."""

import logging
import math
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import partial
from typing import Any

import albumentations as A
import numpy as np
import torch
from datasets import load_dataset
from torchmetrics.detection.mean_ap import MeanAveragePrecision

import trackio

import transformers
from transformers import (
    AutoConfig,
    AutoImageProcessor,
    AutoModelForObjectDetection,
    HfArgumentParser,
    Trainer,
    TrainingArguments,
)
from transformers.image_processing_utils import BatchFeature
from transformers.image_transforms import center_to_corners_format
from transformers.trainer import EvalPrediction
from transformers.utils import check_min_version
from transformers.utils.versions import require_version


logger = logging.getLogger(__name__)

# Will error if the minimal version of Transformers is not installed. Remove at your own risks.
check_min_version("4.57.0.dev0")

require_version("datasets>=2.0.0", "To fix: pip install -r examples/pytorch/object-detection/requirements.txt")


@dataclass
class ModelOutput:
    logits: torch.Tensor
    pred_boxes: torch.Tensor


def format_image_annotations_as_coco(
    image_id: str, categories: list[int], areas: list[float], bboxes: list[tuple[float]]
) -> dict:
    """Format one set of image annotations to the COCO format

    Args:
        image_id (str): image id. e.g. "0001"
        categories (list[int]): list of categories/class labels corresponding to provided bounding boxes
        areas (list[float]): list of corresponding areas to provided bounding boxes
        bboxes (list[tuple[float]]): list of bounding boxes provided in COCO format
            ([center_x, center_y, width, height] in absolute coordinates)

    Returns:
        dict: {
            "image_id": image id,
            "annotations": list of formatted annotations
        }
    """
    annotations = []
    for category, area, bbox in zip(categories, areas, bboxes):
        formatted_annotation = {
            "image_id": image_id,
            "category_id": category,
            "iscrowd": 0,
            "area": area,
            "bbox": list(bbox),
        }
        annotations.append(formatted_annotation)

    return {
        "image_id": image_id,
        "annotations": annotations,
    }


def detect_bbox_format_from_samples(dataset, image_col="image", objects_col="objects", num_samples=50):
    """
    Detect whether bboxes are xyxy (Pascal VOC) or xywh (COCO) by checking
    bbox coordinates against image dimensions. The correct format interpretation
    should keep bboxes within image bounds.
    """
    exceeds_if_xywh = 0
    exceeds_if_xyxy = 0
    total = 0

    for example in dataset.select(range(min(num_samples, len(dataset)))):
        img_w, img_h = example[image_col].size
        for bbox in example[objects_col]["bbox"]:
            if len(bbox) != 4:
                continue
            a, b, c, d = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            total += 1

            # If 3rd < 1st or 4th < 2nd, can't be xyxy (x_max must exceed x_min)
            if c < a or d < b:
                return "xywh"

            # xywh: right/bottom edge = origin + size; exceeding image → wrong format
            if a + c > img_w * 1.05:
                exceeds_if_xywh += 1
            if b + d > img_h * 1.05:
                exceeds_if_xywh += 1
            # xyxy: right/bottom edge = coordinate itself
            if c > img_w * 1.05:
                exceeds_if_xyxy += 1
            if d > img_h * 1.05:
                exceeds_if_xyxy += 1

    if total == 0:
        return "xywh"

    fmt = "xyxy" if exceeds_if_xywh > exceeds_if_xyxy else "xywh"
    logger.info(
        f"Detected bbox format: {fmt} (checked {total} bboxes from {min(num_samples, len(dataset))} images)"
    )
    return fmt


def sanitize_dataset(dataset, bbox_format="xywh", image_col="image", objects_col="objects"):
    """
    Validate bboxes, convert xyxy→xywh if needed, clip to image bounds, and remove
    entries with non-finite values, non-positive dimensions, or degenerate area (<1 px).
    Drops images with no remaining valid bboxes.
    """
    convert_xyxy = bbox_format == "xyxy"

    def _validate(example):
        img_w, img_h = example[image_col].size
        objects = example[objects_col]
        bboxes = objects["bbox"]
        n = len(bboxes)

        valid_indices = []
        converted_bboxes = []

        for i, bbox in enumerate(bboxes):
            if len(bbox) != 4:
                continue
            vals = [float(v) for v in bbox]
            if not all(math.isfinite(v) for v in vals):
                continue

            if convert_xyxy:
                x_min, y_min, x_max, y_max = vals
                w, h = x_max - x_min, y_max - y_min
            else:
                x_min, y_min, w, h = vals

            if w <= 0 or h <= 0:
                continue

            x_min, y_min = max(0.0, x_min), max(0.0, y_min)
            if x_min >= img_w or y_min >= img_h:
                continue
            w = min(w, img_w - x_min)
            h = min(h, img_h - y_min)

            if w * h < 1.0:
                continue

            valid_indices.append(i)
            converted_bboxes.append([x_min, y_min, w, h])

        # Rebuild objects dict, filtering all list-valued fields by valid_indices
        new_objects = {}
        for key, value in objects.items():
            if key == "bbox":
                new_objects["bbox"] = converted_bboxes
            elif isinstance(value, list) and len(value) == n:
                new_objects[key] = [value[j] for j in valid_indices]
            else:
                new_objects[key] = value

        if "area" not in new_objects or len(new_objects.get("area", [])) != len(converted_bboxes):
            new_objects["area"] = [b[2] * b[3] for b in converted_bboxes]

        example[objects_col] = new_objects
        return example

    before = len(dataset)
    dataset = dataset.map(_validate)
    dataset = dataset.filter(lambda ex: len(ex[objects_col]["bbox"]) > 0)
    after = len(dataset)
    if before != after:
        logger.warning(f"Dropped {before - after}/{before} images with no valid bboxes after sanitization")
    logger.info(f"Bbox sanitization complete: {after} images with valid bboxes remain")
    return dataset


def convert_bbox_yolo_to_pascal(boxes: torch.Tensor, image_size: tuple[int, int]) -> torch.Tensor:
    """
    Convert bounding boxes from YOLO format (x_center, y_center, width, height) in range [0, 1]
    to Pascal VOC format (x_min, y_min, x_max, y_max) in absolute coordinates.

    Args:
        boxes (torch.Tensor): Bounding boxes in YOLO format
        image_size (tuple[int, int]): Image size in format (height, width)

    Returns:
        torch.Tensor: Bounding boxes in Pascal VOC format (x_min, y_min, x_max, y_max)
    """
    # convert center to corners format
    boxes = center_to_corners_format(boxes)


    if isinstance(image_size, torch.Tensor):
        image_size = image_size.tolist()
    elif isinstance(image_size, np.ndarray):
        image_size = image_size.tolist()
    height, width = image_size
    boxes = boxes * torch.tensor([[width, height, width, height]])

    return boxes


def augment_and_transform_batch(
    examples: Mapping[str, Any],
    transform: A.Compose,
    image_processor: AutoImageProcessor,
    return_pixel_mask: bool = False,
) -> BatchFeature:
    """Apply augmentations and format annotations in COCO format for object detection task"""

    images = []
    annotations = []
    image_ids = examples["image_id"] if "image_id" in examples else range(len(examples["image"]))
    for image_id, image, objects in zip(image_ids, examples["image"], examples["objects"]):
        image = np.array(image.convert("RGB"))

        # Filter invalid bboxes before augmentation (safety net after sanitize_dataset)
        bboxes = objects["bbox"]
        categories = objects["category"]
        areas = objects["area"]
        valid = [
            (b, c, a)
            for b, c, a in zip(bboxes, categories, areas)
            if len(b) == 4 and b[2] > 0 and b[3] > 0 and b[0] >= 0 and b[1] >= 0
        ]
        if valid:
            bboxes, categories, areas = zip(*valid)
        else:
            bboxes, categories, areas = [], [], []

        # apply augmentations
        output = transform(image=image, bboxes=list(bboxes), category=list(categories))
        images.append(output["image"])

        # format annotations in COCO format (recompute areas from post-augmentation bboxes)
        post_areas = [b[2] * b[3] for b in output["bboxes"]] if output["bboxes"] else []
        formatted_annotations = format_image_annotations_as_coco(
            image_id, output["category"], post_areas, output["bboxes"]
        )
        annotations.append(formatted_annotations)

    # Apply the image processor transformations: resizing, rescaling, normalization
    result = image_processor(images=images, annotations=annotations, return_tensors="pt")

    if not return_pixel_mask:
        result.pop("pixel_mask", None)

    return result


def collate_fn(batch: list[BatchFeature]) -> Mapping[str, torch.Tensor | list[Any]]:
    data = {}
    data["pixel_values"] = torch.stack([x["pixel_values"] for x in batch])
    data["labels"] = [x["labels"] for x in batch]
    if "pixel_mask" in batch[0]:
        data["pixel_mask"] = torch.stack([x["pixel_mask"] for x in batch])
    return data


def _post_process_targets(targets: list) -> tuple[list, list[dict]]:
    """Collect image sizes and convert targets to Pascal VOC format for metric computation."""
    image_sizes = []
    post_processed_targets = []

    for batch in targets:
        # collect image sizes, we will need them for predictions post processing
        batch_image_sizes = torch.tensor([x["orig_size"] for x in batch])
        image_sizes.append(batch_image_sizes)
        # collect targets in the required format for metric computation
        # boxes were converted to YOLO format needed for model training
        # here we will convert them to Pascal VOC format (x_min, y_min, x_max, y_max)
        for image_target in batch:
            boxes = torch.tensor(image_target["boxes"])
            boxes = convert_bbox_yolo_to_pascal(boxes, image_target["orig_size"])
            labels = torch.tensor(image_target["class_labels"])
            post_processed_targets.append({"boxes": boxes, "labels": labels})

    return image_sizes, post_processed_targets


def _post_process_predictions(
    predictions: list, image_sizes: list, image_processor: AutoImageProcessor, threshold: float
) -> list[dict]:
    """Collect predictions and post-process them into the required format for metric computation."""
    post_processed_predictions = []

    # Collect predictions in the required format for metric computation,
    # model produce boxes in YOLO format, then image_processor convert them to Pascal VOC format
    for batch, target_sizes in zip(predictions, image_sizes):
        batch_logits, batch_boxes = batch[1], batch[2]
        output = ModelOutput(logits=torch.tensor(batch_logits), pred_boxes=torch.tensor(batch_boxes))
        post_processed_output = image_processor.post_process_object_detection(
            output, threshold=threshold, target_sizes=target_sizes
        )
        post_processed_predictions.extend(post_processed_output)

    return post_processed_predictions


def _format_per_class_metrics(
    metrics: dict, id2label: Mapping[int, str] | None
) -> dict[str, float]:
    """Replace list of per-class metrics with separate metric entries for each class."""
    classes = metrics.pop("classes")
    map_per_class = metrics.pop("map_per_class")
    mar_100_per_class = metrics.pop("mar_100_per_class")
    # Single-class datasets return 0-d scalar tensors; make them iterable
    if classes.dim() == 0:
        classes = classes.unsqueeze(0)
        map_per_class = map_per_class.unsqueeze(0)
        mar_100_per_class = mar_100_per_class.unsqueeze(0)
    for class_id, class_map, class_mar in zip(classes, map_per_class, mar_100_per_class):
        class_name = id2label[class_id.item()] if id2label is not None else class_id.item()
        metrics[f"map_{class_name}"] = class_map
        metrics[f"mar_100_{class_name}"] = class_mar

    metrics = {k: round(v.item(), 4) for k, v in metrics.items()}

    return metrics


@torch.no_grad()
def compute_metrics(
    evaluation_results: EvalPrediction,
    image_processor: AutoImageProcessor,
    threshold: float = 0.0,
    id2label: Mapping[int, str] | None = None,
) -> Mapping[str, float]:
    """
    Compute mean average mAP, mAR and their variants for the object detection task.

    Args:
        evaluation_results (EvalPrediction): Predictions and targets from evaluation.
        threshold (float, optional): Threshold to filter predicted boxes by confidence. Defaults to 0.0.
        id2label (Optional[dict], optional): Mapping from class id to class name. Defaults to None.

    Returns:
        Mapping[str, float]: Metrics in a form of dictionary {<metric_name>: <metric_value>}
    """

    predictions, targets = evaluation_results.predictions, evaluation_results.label_ids

    # For metric computation we need to provide:
    #  - targets in a form of list of dictionaries with keys "boxes", "labels"
    #  - predictions in a form of list of dictionaries with keys "boxes", "scores", "labels"

    image_sizes, post_processed_targets = _post_process_targets(targets)
    post_processed_predictions = _post_process_predictions(
        predictions, image_sizes, image_processor, threshold
    )

    # Compute metrics
    metric = MeanAveragePrecision(box_format="xyxy", class_metrics=True)
    metric.update(post_processed_predictions, post_processed_targets)
    metrics = metric.compute()

    return _format_per_class_metrics(metrics, id2label)


@dataclass
class DataTrainingArguments:
    """
    Arguments pertaining to what data we are going to input our model for training and eval.
    Using `HfArgumentParser` we can turn this class into argparse arguments to be able to specify
    them on the