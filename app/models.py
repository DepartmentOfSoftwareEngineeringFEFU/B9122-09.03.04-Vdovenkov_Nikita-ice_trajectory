from django.db import models


class ShipType(models.Model):
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.code


class IceImpact(models.Model):
    ship_type = models.ForeignKey(ShipType, on_delete=models.CASCADE, related_name="impacts")
    ice_type = models.CharField(max_length=20)
    coefficient = models.FloatField()

    class Meta:
        unique_together = ("ship_type", "ice_type")

    def __str__(self):
        return f"{self.ship_type.code} / {self.ice_type} = {self.coefficient}"


class Ship(models.Model):
    mmsi = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    ship_type = models.ForeignKey(ShipType, on_delete=models.SET_NULL, null=True, blank=True)

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


class IceCondition(models.Model):
    ICE_TYPES = [
        ("none", "Открытая вода"),
        ("light", "Молодой лёд"),
        ("heavy", "Толстый лёд"),
    ]

    area = models.ForeignKey(WaterArea, on_delete=models.CASCADE, related_name="ice_conditions")
    ice_type = models.CharField(max_length=20, choices=ICE_TYPES, default="none")
    lat_min = models.FloatField()
    lat_max = models.FloatField()
    lon_min = models.FloatField()
    lon_max = models.FloatField()

    def __str__(self):
        return f"{self.area.name} — {self.ice_type}"


class Route(models.Model):
    area_name = models.CharField(max_length=255)  
    start_lat = models.FloatField()
    start_lon = models.FloatField()
    end_lat = models.FloatField()
    end_lon = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Маршрут {self.pk} - {self.area_name}"


class RoutePoint(models.Model):
    POINT_TYPES = [
        ("начальная", "Начальная"),
        ("промежуточная", "Промежуточная"),
        ("конечная", "Конечная"),
    ]

    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="points")
    order = models.PositiveIntegerField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    point_type = models.CharField(max_length=20, choices=POINT_TYPES, default="промежуточная")

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"Точка {self.order} ({self.point_type}) маршрута {self.route_id}"