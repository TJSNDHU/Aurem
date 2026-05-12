"""
scout_behavior.py — Human-like behavior helpers for browser automation.

Provides Bezier mouse paths, Markov-chain typing delays, and read pauses
to simulate natural user interactions.
"""

import asyncio
import math
import random
from typing import Any


def bezier_curve(
    p0: tuple,
    p1: tuple,
    ctrl1: tuple,
    ctrl2: tuple,
    steps: int = 20
) -> list[tuple]:
    """
    Cubic Bezier curve through 4 control points.
    Returns list of (x, y) int coordinates.
    """
    points = []
    for i in range(steps + 1):
        t = i / steps
        t_inv = 1 - t
        x = (
            t_inv**3 * p0[0] +
            3 * t_inv**2 * t * ctrl1[0] +
            3 * t_inv * t**2 * ctrl2[0] +
            t**3 * p1[0]
        )
        y = (
            t_inv**3 * p0[1] +
            3 * t_inv**2 * t * ctrl1[1] +
            3 * t_inv * t**2 * ctrl2[1] +
            t**3 * p1[1]
        )
        points.append((int(x), int(y)))
    return points


def jittered_path(start: tuple, end: tuple, steps: int = 22) -> list[tuple]:
    """
    Generates a Bezier path with random midpoint offset 5-25% of distance.
    Returns list of (x, y) int coordinates.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.sqrt(dx**2 + dy**2)
    
    offset_ratio = random.uniform(0.05, 0.25)
    offset = dist * offset_ratio
    
    angle = math.atan2(dy, dx) + random.uniform(-math.pi/4, math.pi/4)
    mid_x = (start[0] + end[0]) / 2 + offset * math.cos(angle)
    mid_y = (start[1] + end[1]) / 2 + offset * math.sin(angle)
    
    ctrl1 = (
        int(start[0] + (mid_x - start[0]) * 0.4),
        int(start[1] + (mid_y - start[1]) * 0.4)
    )
    ctrl2 = (
        int(end[0] - (end[0] - mid_x) * 0.4),
        int(end[1] - (end[1] - mid_y) * 0.4)
    )
    
    return bezier_curve(start, end, ctrl1, ctrl2, steps)


async def human_move(page: Any, x: int, y: int, from_xy: tuple = None):
    """
    Move mouse to (x, y) along a jittered Bezier path with human-like delays.
    """
    if from_xy is None:
        try:
            from_xy = await page.evaluate("() => [window.mouseX || 0, window.mouseY || 0]")
            if not isinstance(from_xy, (list, tuple)) or len(from_xy) != 2:
                from_xy = (0, 0)
        except Exception:
            from_xy = (0, 0)
    
    path = jittered_path(from_xy, (x, y))
    
    for px, py in path:
        await page.mouse.move(px, py)
        await asyncio.sleep(random.uniform(0.005, 0.015))


async def human_click(page: Any, selector: str):
    """
    Click an element with human-like mouse movement and delays.
    """
    await page.wait_for_selector(selector, state="visible", timeout=10000)
    box = await page.locator(selector).bounding_box()
    
    if not box:
        raise ValueError(f"Could not get bounding box for {selector}")
    
    target_x = int(box["x"] + box["width"] * random.uniform(0.2, 0.8))
    target_y = int(box["y"] + box["height"] * random.uniform(0.2, 0.8))
    
    await human_move(page, target_x, target_y)
    await asyncio.sleep(random.uniform(0.08, 0.25))
    
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.04, 0.12))
    await page.mouse.up()


_MARKOV_STATE = "normal"
_MARKOV_TRANSITIONS = {
    "fast": {"normal": 0.7, "slow": 0.15, "fast": 0.15},
    "normal": {"fast": 0.25, "normal": 0.5, "slow": 0.15, "pause": 0.10},
    "slow": {"normal": 0.6, "slow": 0.25, "fast": 0.15},
    "pause": {"normal": 0.85, "pause": 0.15}
}
_MARKOV_DELAYS = {
    "fast": (0.03, 0.07),
    "normal": (0.08, 0.16),
    "slow": (0.20, 0.35),
    "pause": (0.60, 1.20)
}


def _markov_typing_delay() -> float:
    """Returns next typing delay in seconds using Markov chain."""
    global _MARKOV_STATE
    
    delays = _MARKOV_DELAYS[_MARKOV_STATE]
    delay = random.uniform(delays[0], delays[1])
    
    transitions = _MARKOV_TRANSITIONS[_MARKOV_STATE]
    rand = random.random()
    cumsum = 0.0
    for next_state, prob in transitions.items():
        cumsum += prob
        if rand < cumsum:
            _MARKOV_STATE = next_state
            break
    
    return delay


async def human_type(page: Any, selector: str, text: str):
    """
    Type text into an element with Markov-chain delays between characters.
    """
    await page.focus(selector)
    await asyncio.sleep(random.uniform(0.1, 0.3))
    
    for char in text:
        delay = _markov_typing_delay()
        await asyncio.sleep(delay)
        await page.keyboard.type(char)


async def read_pause(page: Any, min_ms: int = 800, max_ms: int = 2400):
    """
    Simulate reading pause with small scroll and idle time.
    """
    scroll_y = random.randint(100, 500)
    await page.evaluate(f"window.scrollBy(0, {scroll_y})")
    await asyncio.sleep(random.uniform(0.2, 0.5))
    
    pause_ms = random.randint(min_ms, max_ms)
    await asyncio.sleep(pause_ms / 1000.0)


def maybe_abandon(probability: float = 0.03) -> bool:
    """
    iter 322ez fix — sync (no I/O needed). Returns True with given probability.
    Was previously `async def` which made `if maybe_abandon(rate):` always
    truthy (coroutine object) — bug caught in iter 322ez end-to-end test.
    """
    return random.random() < probability