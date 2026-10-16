from langgraph.checkpoint.sqlite import SqliteSaver

from person_agents.config.settings import settings


def get_checkpointer() -> SqliteSaver:
    import sqlite3
    conn = sqlite3.connect(str(settings.sqlite_path), check_same_thread=False)
    return SqliteSaver(conn)
