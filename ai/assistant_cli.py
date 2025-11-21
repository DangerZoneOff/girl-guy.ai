"""
CLI для общения с Mistral AI, работающий через настройки проекта.
"""

from __future__ import annotations

import sys

from ai.groq_integration import send_chat_completion


def start_cli() -> None:
    history = []

    print("💬 Чат с Groq (введите 'выход' для выхода)\n")

    while True:
        try:
            user_input = input("Вы: ")
        except (EOFError, KeyboardInterrupt):
            print("\nЧат завершён.")
            break

        if user_input.lower() in {"exit", "quit", "выход"}:
            print("Чат завершён.")
            break

        history.append({"role": "user", "content": user_input})
        reply = send_chat_completion(history, max_tokens=500)
        history.append({"role": "assistant", "content": reply})
        print("Агент:", reply)


if __name__ == "__main__":
    try:
        start_cli()
    except RuntimeError as exc:
        sys.stderr.write(f"{exc}\n")
        sys.exit(1)

