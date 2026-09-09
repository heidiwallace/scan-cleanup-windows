"""Shared pytest fixtures. Uses synthetic 'scanned page' images, not real archival data."""

import cv2
import numpy as np
import pytest


def make_text_page(width: int = 800, height: int = 1000, noise: bool = False) -> np.ndarray:
    """A synthetic 'scanned page': white background with black text-like blocks."""
    image = np.full((height, width), 255, dtype=np.uint8)
    rng = np.random.default_rng(0)
    line_y = 80
    while line_y < height - 80:
        line_height = 22
        x = 60
        for _ in range(rng.integers(4, 9)):
            word_width = int(rng.integers(30, 90))
            cv2.rectangle(
                image, (x, line_y), (x + word_width, line_y + line_height), 0, thickness=-1
            )
            x += word_width + int(rng.integers(15, 30))
            if x > width - 80:
                break
        line_y += line_height + int(rng.integers(20, 30))
    if noise:
        speckles = rng.random((height, width)) < 0.002
        image[speckles] = 0
    return image


def rotate(image: np.ndarray, angle_deg: float) -> np.ndarray:
    h, w = image.shape[:2]
    center = (w / 2, h / 2)
    matrix = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )


@pytest.fixture
def text_page() -> np.ndarray:
    return make_text_page()


@pytest.fixture
def noisy_text_page() -> np.ndarray:
    return make_text_page(noise=True)
