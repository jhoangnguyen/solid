from __future__ import annotations

import pygame
from engine.ui.style import Theme

class Scrollbar:
    """
    Stateless drawer for a simple vertical scrollbar.
    """
    @staticmethod
    def draw(layer: pygame.Surface, widget_rect: pygame.Rect, viewport: pygame.Rect,
             visual_content_h: int, scroll_y: float, max_scroll: float, theme: Theme) -> None:
        sb = theme.scrollbar
        t, r, b, l = theme.padding
        track_x = widget_rect.w - r - sb.margin - sb.width
        track_y = t
        track_h = widget_rect.h - (t + b)
        if track_h <= 0 or sb.width <= 0:
            return

        overflow = visual_content_h > viewport.h
        if not overflow and not sb.show_when_no_overflow:
            return

        track_rect = pygame.Rect(track_x, track_y, sb.width, track_h)
        pygame.draw.rect(layer, sb.track_color, track_rect, border_radius=sb.radius)

        if overflow:
            ratio = max(0.0, min(1.0, viewport.h / max(1, visual_content_h)))
            thumb_h = max(sb.min_thumb_size, int(track_h * ratio))
            max_sc = max(1e-6, max_scroll)
            pos_ratio = scroll_y / max_sc
            free = max(0, track_h - thumb_h)
            thumb_y = track_y + int(free * pos_ratio)
        else:
            thumb_h = track_h
            thumb_y = track_y

        thumb_rect = pygame.Rect(track_x, thumb_y, sb.width, thumb_h)
        pygame.draw.rect(layer, sb.thumb_color, thumb_rect, border_radius=sb.radius)
