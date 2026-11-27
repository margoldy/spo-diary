import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from alembic import command
    from alembic.config import Config

    from app.db.seed import load
    from app.db.setup import create_database

    create_database()
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    count = load(Path(__file__).with_name("works.json"))
    print(f"Каталог загружен: {count} произведений. Обложки готовы к выдаче через API.")


if __name__ == "__main__":
    main()
