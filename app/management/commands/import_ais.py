import csv
import os
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from app.models import Ship, ShipPosition


COL_MMSI = "MMSI"
COL_TIME = "BaseDateTime"
COL_LAT = "LAT"
COL_LON = "LON"
COL_SOG = "SOG"
COL_COG = "COG"
COL_NAME = "VesselName"


def parse_datetime(value):
    value = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def parse_decimal(value):
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_mmsi(value):
    value = value.strip()
    if not value:
        return None
    try:
        return int(float(value))
    except (ValueError, OverflowError):
        return None


class Command(BaseCommand):
    help = "Импорт AIS CSV данных в БД"

    def add_arguments(self, parser):
        parser.add_argument("file", type=str)
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        file_path = options["file"]

        if not os.path.isfile(file_path):
            raise CommandError(f"Файл не найден: {file_path}")

        self.stdout.write(f"Обрабатываем: {os.path.basename(file_path)}")

        imported, skipped = self._import_file(
            file_path,
            batch_size=options["batch_size"],
            limit=options["limit"],
        )

        self.stdout.write(self.style.SUCCESS(
            f"Готово. Импортировано: {imported}, пропущено: {skipped}"
        ))

    def _import_file(self, file_path, batch_size, limit):
        imported = 0
        skipped = 0
        ship_cache = {}
        positions_batch = []

        with open(file_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            required = {COL_MMSI, COL_TIME, COL_LAT, COL_LON}
            if reader.fieldnames:
                missing = required - set(reader.fieldnames)
                if missing:
                    raise CommandError(f"Отсутствуют колонки: {missing}")

            for row_num, row in enumerate(reader, start=2):
                if limit and row_num - 1 > limit:
                    break

                try:
                    mmsi = parse_mmsi(row.get(COL_MMSI, ""))
                    if mmsi is None:
                        skipped += 1
                        continue

                    dt = parse_datetime(row.get(COL_TIME, ""))
                    if dt is None:
                        skipped += 1
                        continue

                    lat = parse_decimal(row.get(COL_LAT, ""))
                    lon = parse_decimal(row.get(COL_LON, ""))
                    if lat is None or lon is None:
                        skipped += 1
                        continue

                    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                        skipped += 1
                        continue

                    sog = parse_decimal(row.get(COL_SOG, ""))
                    cog = parse_decimal(row.get(COL_COG, ""))

                    if cog is not None and not (0 <= cog <= 360):
                        cog = None

                    if mmsi not in ship_cache:
                        vessel_name = row.get(COL_NAME, "").strip()
                        ship, _ = Ship.objects.get_or_create(
                            mmsi=mmsi,
                            defaults={"name": vessel_name or ""},
                        )
                        if vessel_name and not ship.name:
                            ship.name = vessel_name
                            ship.save(update_fields=["name"])
                        ship_cache[mmsi] = ship

                    ship = ship_cache[mmsi]

                    positions_batch.append(
                        ShipPosition(
                            ship=ship,
                            time=dt,
                            latitude=lat,
                            longitude=lon,
                            speed=sog,
                            course=cog,
                        )
                    )

                    if len(positions_batch) >= batch_size:
                        saved = self._flush_batch(positions_batch)
                        imported += saved
                        positions_batch = []

                except Exception as e:
                    skipped += 1
                    if skipped <= 5:
                        self.stderr.write(self.style.WARNING(f"  Строка {row_num}: {e}"))

        if positions_batch:
            saved = self._flush_batch(positions_batch)
            imported += saved

        return imported, skipped

    @staticmethod
    def _flush_batch(positions):
        with transaction.atomic():
            created = ShipPosition.objects.bulk_create(
                positions,
                ignore_conflicts=True,
            )
        return len(created)