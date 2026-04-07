"""Theme constants for the FlashTool UI."""

# ── Color Palette ────────────────────────────────────────────────────────────
# Inspired by a modern dark IDE theme with vibrant accents

COLORS = {
    # Backgrounds
    "bg_primary": "#0f1117",       # Main window background
    "bg_secondary": "#161822",     # Panels, cards
    "bg_tertiary": "#1e2030",      # Elevated cards
    "bg_input": "#242638",         # Input fields
    "bg_hover": "#2a2d42",         # Hover states

    # Accent colors
    "accent_blue": "#5b8af5",      # Primary action
    "accent_green": "#4ade80",     # Success
    "accent_red": "#f87171",       # Error
    "accent_yellow": "#fbbf24",    # Warning
    "accent_orange": "#fb923c",    # Running/progress
    "accent_purple": "#a78bfa",    # Info

    # Text
    "text_primary": "#e2e8f0",     # Primary text
    "text_secondary": "#94a3b8",   # Secondary text
    "text_muted": "#64748b",       # Muted/disabled
    "text_accent": "#5b8af5",      # Link/accent text

    # Borders
    "border": "#2a2d42",
    "border_focus": "#5b8af5",

    # Status indicators
    "status_pending": "#64748b",
    "status_waiting": "#fbbf24",
    "status_running": "#fb923c",
    "status_success": "#4ade80",
    "status_failed": "#f87171",
    "status_skipped": "#94a3b8",

    # Progress bar
    "progress_bg": "#1e2030",
    "progress_fill": "#5b8af5",

    # Scrollbar
    "scrollbar_bg": "#161822",
    "scrollbar_fg": "#2a2d42",
}

# ── Fonts ────────────────────────────────────────────────────────────────────
FONTS = {
    "heading_lg": ("Segoe UI", 20, "bold"),
    "heading_md": ("Segoe UI", 15, "bold"),
    "heading_sm": ("Segoe UI", 12, "bold"),
    "body": ("Segoe UI", 12),
    "body_sm": ("Segoe UI", 11),
    "caption": ("Segoe UI", 10),
    "mono": ("Cascadia Code", 11),
    "mono_sm": ("Cascadia Code", 10),
}

# Linux-friendly font fallbacks
import sys
if sys.platform.startswith("linux"):
    FONTS = {
        "heading_lg": ("Ubuntu", 20, "bold"),
        "heading_md": ("Ubuntu", 15, "bold"),
        "heading_sm": ("Ubuntu", 12, "bold"),
        "body": ("Ubuntu", 12),
        "body_sm": ("Ubuntu", 11),
        "caption": ("Ubuntu", 10),
        "mono": ("Ubuntu Mono", 11),
        "mono_sm": ("Ubuntu Mono", 10),
    }

# ── Spacing ──────────────────────────────────────────────────────────────────
SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "xxl": 32,
}

# ── Step Status Config ───────────────────────────────────────────────────────
STATUS_CONFIG = {
    "pending":  {"icon": "⏳", "color": COLORS["status_pending"], "label": "Pending"},
    "waiting":  {"icon": "📡", "color": COLORS["status_waiting"], "label": "Waiting"},
    "running":  {"icon": "🔄", "color": COLORS["status_running"], "label": "Running"},
    "success":  {"icon": "✅", "color": COLORS["status_success"], "label": "Done"},
    "failed":   {"icon": "❌", "color": COLORS["status_failed"],  "label": "Failed"},
    "skipped":  {"icon": "⏭️", "color": COLORS["status_skipped"], "label": "Skipped"},
}
