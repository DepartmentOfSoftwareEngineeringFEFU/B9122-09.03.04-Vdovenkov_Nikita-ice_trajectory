from django.db import models


class Ship(models.Model):
    mmsi = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name or f"MMSI {self.mmsi}"


class ShipPosition(models.Model):
    ship = models.ForeignKey(Ship, on_delete=models.CASCADE, related_name="positions")
    time = models.DateTimeField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    speed = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    course = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ("ship", "time")

    def __str__(self):
        return f"{self.ship.mmsi} @ {self.time}"


class WaterArea(models.Model):
    name = models.CharField(max_length=255)
    lat_min = models.FloatField()
    lat_max = models.FloatField()
    lon_min = models.FloatField()
    lon_max = models.FloatField()

    def __str__(self):
        return self.name


class WaterAreaPoint(models.Model):
    area = models.ForeignKey(WaterArea, on_delete=models.CASCADE, related_name="points")
    latitude = models.FloatField()
    longitude = models.FloatField()
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]


class IceZone(models.Model):
    ICE_TYPES = [
        ("none", "Чистая вода"),
        ("light", "Лёгкий лёд"),
        ("medium", "Средний лёд"),
        ("heavy", "Тяжёлый лёд"),
    ]

    area = models.ForeignKey(WaterArea, on_delete=models.CASCADE, related_name="ice_zones")
    ice_type = models.CharField(max_length=20, choices=ICE_TYPES, default="none")
    lat_min = models.FloatField()
    lat_max = models.FloatField()
    lon_min = models.FloatField()
    lon_max = models.FloatField()

    def __str__(self):
        return f"{self.area.name} — {self.ice_type}"