import json
import threading
import time

from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.db.models import Count
from django.shortcuts import render
from django.http import StreamingHttpResponse

from .models import Ship, ShipPosition, WaterArea, WaterAreaPoint, IceZone
from .serializers import (
    ShipSerializer, WaterAreaSerializer, WaterAreaCreateSerializer,
    IceZoneSerializer, WaterAreaPointSerializer
)


def index(request):
    return render(request, "index.html")


class ShipViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ShipSerializer

    def get_queryset(self):
        queryset = Ship.objects.all()
        water_area_id = self.request.query_params.get("water_area")

        if water_area_id:
            try:
                area = WaterArea.objects.get(pk=water_area_id)
            except WaterArea.DoesNotExist:
                return Ship.objects.none()

            queryset = Ship.objects.filter(
                positions__latitude__gte=area.lat_min,
                positions__latitude__lte=area.lat_max,
                positions__longitude__gte=area.lon_min,
                positions__longitude__lte=area.lon_max,
            ).annotate(
                pos_count=Count("positions")
            ).filter(pos_count__gte=2).distinct()

        return queryset

    @action(detail=True, methods=["get"], url_path="track")
    def track(self, request, pk=None):
        ship = self.get_object()
        positions = ship.positions.order_by("time").values("latitude", "longitude", "time", "speed")
        return Response(list(positions))


class WaterAreaViewSet(viewsets.ModelViewSet):
    queryset = WaterArea.objects.all()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return WaterAreaCreateSerializer
        return WaterAreaSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.name
        self.perform_destroy(instance)
        return Response({"message": f"Акватория '{name}' удалена"})


class WaterAreaPointViewSet(viewsets.ModelViewSet):
    serializer_class = WaterAreaPointSerializer
    queryset = WaterAreaPoint.objects.all()


class IceZoneViewSet(viewsets.ModelViewSet):
    serializer_class = IceZoneSerializer

    def get_queryset(self):
        queryset = IceZone.objects.all()
        water_area_id = self.request.query_params.get("water_area")
        if water_area_id:
            queryset = queryset.filter(water_area=water_area_id)
        return queryset


@api_view(["GET"])
def heatmap_data(request):
    water_area_id = request.query_params.get("water_area")
    limit = int(request.query_params.get("limit", 5000))

    qs = ShipPosition.objects.all()

    if water_area_id:
        try:
            area = WaterArea.objects.get(pk=water_area_id)
            qs = qs.filter(
                latitude__gte=area.lat_min,
                latitude__lte=area.lat_max,
                longitude__gte=area.lon_min,
                longitude__lte=area.lon_max,
            )
        except WaterArea.DoesNotExist:
            return Response([])

    points = qs.values_list("latitude", "longitude")[:limit]
    return Response([[float(lat), float(lon)] for lat, lon in points])


@api_view(["GET"])
def courses_data(request):
    water_area_id = request.GET.get("water_area")
    limit = int(request.GET.get("limit", 3000))

    qs = ShipPosition.objects.exclude(course=None)

    if water_area_id:
        try:
            area = WaterArea.objects.get(pk=water_area_id)
            qs = qs.filter(
                latitude__gte=area.lat_min,
                latitude__lte=area.lat_max,
                longitude__gte=area.lon_min,
                longitude__lte=area.lon_max,
            )
        except WaterArea.DoesNotExist:
            return Response([])

    total = qs.count()
    step = max(1, total // limit)
    points = qs.values_list("latitude", "longitude", "course")[::step][:limit]

    return Response([
        {"lat": float(lat), "lon": float(lon), "course": float(course)}
        for lat, lon, course in points
    ])