from core.providers import BaseProvider, LocalProvider


class ConversationEngine:
    def __init__(self, provider: BaseProvider | None = None):
        self._provider = provider or LocalProvider()

    def get_reply(self, user_message: str) -> str:
        return self._provider.generate_reply(user_message)
