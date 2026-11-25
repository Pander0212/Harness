"""Fake-OpenAI-Client für Tests."""
import copy
import json
import threading
from types import SimpleNamespace as NS


class FakeAPIError(Exception):
    def __init__(self, status_code, message="error"):
        super().__init__(message)
        self.status_code = status_code


class FakeTimeout(Exception):
    pass


def resp(content=None, calls=(), finish_reason=None, prompt=1000, completion=100, cached=0,
         usage=True):
    tcs = [NS(id=f"call_{i}", type="function",
              function=NS(name=n, arguments=a if isinstance(a, str) else json.dumps(a)))
           for i, (n, a) in enumerate(calls)]
    fr = finish_reason or ("tool_calls" if tcs else "stop")
    u = NS(prompt_tokens=prompt, completion_tokens=completion,
           prompt_tokens_details=NS(cached_tokens=cached)) if usage else None
    return NS(choices=[NS(message=NS(content=content, tool_calls=tcs or None, refusal=None),
                          finish_reason=fr)], usage=u)


def tool(name, **args):
    return resp(calls=[(name, args)])


class FakeClient:
    """script: Liste aus Antworten, Exceptions oder callables(kwargs)->Antwort.
    Ist die Liste leer, wird `default` verwendet."""

    def __init__(self, script=(), default=None):
        self.script = list(script)
        self.default = default
        self.requests = []
        self.lock = threading.Lock()
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        with self.lock:
            self.requests.append(copy.deepcopy(kwargs))
            item = self.script.pop(0) if self.script else self.default
        if callable(item) and not isinstance(item, NS):
            item = item(kwargs)
        if isinstance(item, BaseException):
            raise item
        if item is None:
            raise FakeAPIError(500, "script exhausted")
        return item
