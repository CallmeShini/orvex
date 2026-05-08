from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class LocalVLMError(RuntimeError):
    """Raised when local VLM inference cannot be completed."""


@dataclass(frozen=True)
class LocalVLMConfig:
    model_id: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    max_new_tokens: int = 700
    min_pixels: int = 256 * 28 * 28
    max_pixels: int = 1280 * 28 * 28

    @classmethod
    def from_env(cls) -> "LocalVLMConfig":
        return cls(
            model_id=os.getenv("ORVEX_MODEL_ID", cls.model_id),
            max_new_tokens=int(os.getenv("ORVEX_MAX_NEW_TOKENS", str(cls.max_new_tokens))),
            min_pixels=int(os.getenv("ORVEX_MIN_PIXELS", str(cls.min_pixels))),
            max_pixels=int(os.getenv("ORVEX_MAX_PIXELS", str(cls.max_pixels))),
        )


class LocalVLMClient:
    def __init__(self, config: LocalVLMConfig | None = None) -> None:
        self.config = config or LocalVLMConfig.from_env()
        self._model = None
        self._processor = None

    @property
    def model_name(self) -> str:
        return self.config.model_id

    def analyze(self, image_path: Path, prompt: str) -> str:
        if not image_path.exists():
            raise LocalVLMError(f"Image not found for local VLM inference: {image_path}")

        self._load_model()

        try:
            from qwen_vl_utils import process_vision_info
            import torch
        except ImportError as exc:
            raise LocalVLMError(
                "Missing local VLM runtime dependencies. Install requirements-vps.txt on the GPU host."
            ) from exc

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": str(image_path)},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        try:
            text = self._processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            image_inputs, video_inputs = process_vision_info(messages)
            inputs = self._processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )

            device = "cuda" if torch.cuda.is_available() else "cpu"
            inputs = inputs.to(device)
            generated_ids = self._model.generate(
                **inputs,
                max_new_tokens=self.config.max_new_tokens,
                do_sample=False,
            )
            generated_ids = [
                output_ids[len(input_ids) :]
                for input_ids, output_ids in zip(inputs.input_ids, generated_ids, strict=True)
            ]
            decoded = self._processor.batch_decode(
                generated_ids,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )
        except Exception as exc:
            raise LocalVLMError(f"Local VLM inference failed: {exc}") from exc

        return decoded[0].strip()

    def _load_model(self) -> None:
        if self._model is not None and self._processor is not None:
            return

        try:
            from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
        except ImportError as exc:
            raise LocalVLMError(
                "Missing transformers Qwen2.5-VL support. Install requirements-vps.txt on the GPU host."
            ) from exc

        try:
            self._processor = AutoProcessor.from_pretrained(
                self.config.model_id,
                min_pixels=self.config.min_pixels,
                max_pixels=self.config.max_pixels,
            )
            self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                self.config.model_id,
                torch_dtype="auto",
                device_map="auto",
            )
        except Exception as exc:
            raise LocalVLMError(f"Could not load local VLM model {self.config.model_id}: {exc}") from exc
