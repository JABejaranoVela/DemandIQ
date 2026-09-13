import argparse
import json
import logging
from dataclasses import asdict
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from demandiq.config import Settings, configure_logging
from demandiq.db import make_engine
from demandiq.ingestion.m5 import InputError, Selection
from demandiq.ingestion.service import IngestionFailed, ingest


def main() -> int:
    parser = argparse.ArgumentParser(prog="demandiq")
    commands = parser.add_subparsers(dest="command", required=True)
    batch = commands.add_parser("ingest", help="Ingest a configured subset of observed M5 sales")
    batch.add_argument("--data-dir", type=Path)
    batch.add_argument("--archive-dir", type=Path)
    for name in ("store-id", "item-id", "department-id", "category-id"):
        batch.add_argument("--" + name, action="append")
    batch.add_argument("--start-date")
    batch.add_argument("--end-date")
    args = parser.parse_args()
    try:
        settings = Settings(source="m5")
        configure_logging(settings.log_level)
        changes = {
            key: getattr(args, key)
            for key in ("data_dir", "archive_dir")
            if getattr(args, key) is not None
        }
        settings = settings.model_copy(update=changes)
        selection = Selection(
            store_ids=args.store_id if args.store_id is not None else settings.m5_store_ids,
            item_ids=args.item_id if args.item_id is not None else settings.m5_item_ids,
            department_ids=args.department_id
            if args.department_id is not None
            else settings.m5_department_ids,
            category_ids=args.category_id
            if args.category_id is not None
            else settings.m5_category_ids,
            start_date=args.start_date or settings.m5_start_date,
            end_date=args.end_date or settings.m5_end_date,
        )
        engine = make_engine(settings)
        try:
            result = ingest(engine, settings, selection)
        finally:
            engine.dispose()
        print(json.dumps(asdict(result), default=str))
        return 0
    except IngestionFailed as exc:
        print(json.dumps({"load_id": str(exc.load_id), "error": exc.code, "message": str(exc)}))
    except InputError as exc:
        print(json.dumps({"error": exc.code, "message": str(exc)}))
    except ValidationError as exc:
        fields = [".".join(str(part) for part in item["loc"]) for item in exc.errors()]
        print(json.dumps({"error": "invalid_configuration", "fields": fields}))
    except ValueError:
        print(
            json.dumps(
                {
                    "error": "invalid_configuration",
                    "message": "Check database settings and explicit selection",
                }
            )
        )
    except SQLAlchemyError as exc:
        logging.getLogger(__name__).error("database_unavailable error_type=%s", type(exc).__name__)
        print(
            json.dumps(
                {
                    "error": "database_unavailable",
                    "message": "Check PostgreSQL and apply migrations",
                }
            )
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
