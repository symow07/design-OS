from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Panel:
    name: str
    x: float      # left edge in mm from origin (top-left, Y-down)
    y: float      # top edge in mm from origin
    width: float  # panel width in mm
    height: float # panel height in mm

    def __post_init__(self) -> None:
        self.x = round(self.x, 4)
        self.y = round(self.y, 4)
        self.width = round(self.width, 4)
        self.height = round(self.height, 4)

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.width, self.height)

    @property
    def center(self) -> tuple[float, float]:
        return (
            round(self.x + self.width / 2, 4),
            round(self.y + self.height / 2, 4),
        )

    @property
    def right(self) -> float:
        return round(self.x + self.width, 4)

    @property
    def bottom(self) -> float:
        return round(self.y + self.height, 4)
