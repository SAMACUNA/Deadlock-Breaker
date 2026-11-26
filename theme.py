PANEL = "#17142e"
PANEL2 = "#221d45"
ENTRY = "#2c2658"
FG = "#f4ecff"
PINK = "#ff8fc7"
CYAN = "#7ee8fa"
GREEN = "#7dffb0"
RED = "#ff7b8f"

THEMES = {
    "night": {"top": (12, 10, 44), "bottom": (120, 52, 130), "stars": True,
              "orb": "#fff6c9", "glow": "#cdb8ff", "sky_city": "#0b0820",
              "title": "#ff8fc7", "shadow": "#000000", "text": "#7ee8fa"},
    "sunset": {"top": (255, 148, 170), "bottom": (255, 214, 140), "stars": False,
               "orb": "#fff2e0", "glow": "#ffc2a0", "sky_city": "#3a1b46",
               "title": "#4a1250", "shadow": "#ffffff", "text": "#2b0a3d"},
}


BUTTON_STYLES = {
    "pink":   ("#ff8fc7", "#ffb3da", "#1a0f2e"),
    "green":  ("#7dffb0", "#b0ffd0", "#0b2b1a"),
    "cyan":   ("#7ee8fa", "#b5f3ff", "#0c2430"),
    "purple": ("#6c55c9", "#8a72e8", "#ffffff"),
    "red":    ("#ff7b8f", "#ffa3b1", "#33080f"),
    "gold":   ("#ffd479", "#ffe4a8", "#33240a"),
}


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rgb(c):
    return "#%02x%02x%02x" % c
