"""ANSI color helpers used across PyJest."""

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
GREY = "\033[90m"
BG_GREEN = "\033[42m"
FG_WHITE = "\033[97m"
BG_RED = "\033[41m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_RED = "\033[91m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_CYAN = "\033[96m"


def color(text: str, color_code: str) -> str:
    return f"{color_code}{text}{RESET}"
