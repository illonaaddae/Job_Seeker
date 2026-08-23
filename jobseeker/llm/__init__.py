"""Text generation layer.

`get_writer()` returns the best available generator: the Claude backed one when
an API key is present, otherwise a deterministic template writer that still
produces specific, non generic letters. Both pass through the same style guard,
so a letter written without an API key obeys exactly the same rules.
"""

from .base import Draft, Writer
from .templates import TemplateWriter
from .anthropic import AnthropicWriter, is_available as anthropic_available


def get_writer(prefer: str = "auto") -> Writer:
    """Pick a writer. `prefer` is one of auto, claude, template."""
    if prefer == "template":
        return TemplateWriter()
    if prefer == "claude":
        return AnthropicWriter()
    if anthropic_available():
        return AnthropicWriter()
    return TemplateWriter()


__all__ = ["Draft", "Writer", "TemplateWriter", "AnthropicWriter", "get_writer"]
