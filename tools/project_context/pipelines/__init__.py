"""
Pipelines Module.

This module exports pipeline components for project context operations.
"""
# Gen 2D
from .gen_2d.prepare import PrepareFor2dGen
from .gen_2d.behaviour import Generate2dBehaviour

# Gen 3D
from .gen_3d.prepare import PrepareFor3dGen, ViewSelectionWindow
from .gen_3d.behaviour import Generate3dBehaviour

# Gen Video
from .gen_video.prepare import PrepareForVideoGen, FrameSelectionWindow
from .gen_video.behaviour import GenerateVideoBehaviour

# Common
from .form_window import FormWindow

# Backward compatibility alias
DownloadModelBehaviour = Generate3dBehaviour

__all__ = [
    # Gen 2D
    "PrepareFor2dGen",
    "Generate2dBehaviour",
    # Gen 3D
    "PrepareFor3dGen",
    "ViewSelectionWindow",
    "Generate3dBehaviour",
    "DownloadModelBehaviour",  # Backward compatibility
    # Gen Video
    "PrepareForVideoGen",
    "FrameSelectionWindow",
    "VideoGenInput",
    "GenerateVideoBehaviour",
    # Common
    "FormWindow"
]
