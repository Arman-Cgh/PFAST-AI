"""
DEPRECATED MODULE: services.conversation

This subsystem is maintained for historical/experimental reference only.
The active production AI pipeline is located in `services.ai` (AIEngine, ResponsePipeline, etc.).
"""

from services.conversation.service import ConversationService
from services.conversation.handler import ConversationHandler
from services.conversation.manager import ConversationManager
from services.conversation.router import ConversationRouter
from services.conversation.planner import ConversationPlanner
from services.conversation.middleware import ConversationMiddleware
from services.conversation.session import ConversationSession


__all__ = [

    "ConversationService",

    "ConversationHandler",

    "ConversationManager",

    "ConversationRouter",

    "ConversationPlanner",

    "ConversationMiddleware",

    "ConversationSession",

]