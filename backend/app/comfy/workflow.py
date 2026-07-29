from copy import deepcopy
from pathlib import Path
import json
import secrets
import sys

from ..schemas import GenerationRequest


TEMPLATE_PATH = Path(__file__).parents[3] / "workflows" / "text-to-image.json"


def template_path() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "workflows" / "text-to-image.json"
    return TEMPLATE_PATH


def build_text_to_image_workflow(
    request: GenerationRequest, output_prefix: str = "AIArtAgent"
) -> dict:
    workflow = json.loads(template_path().read_text(encoding="utf-8"))
    workflow = deepcopy(workflow)
    workflow["1"]["inputs"]["ckpt_name"] = request.checkpoint
    workflow["2"]["inputs"]["text"] = request.prompt
    workflow["3"]["inputs"]["text"] = request.negative_prompt
    workflow["4"]["inputs"] = {
        "width": request.width,
        "height": request.height,
        "batch_size": request.batch_size,
    }
    sampler = workflow["5"]["inputs"]
    sampler.update(
        seed=request.seed if request.seed >= 0 else secrets.randbelow(2**63),
        steps=request.steps,
        cfg=request.cfg,
        sampler_name=request.sampler,
        scheduler=request.scheduler,
    )
    workflow["7"]["inputs"]["filename_prefix"] = output_prefix
    return workflow
