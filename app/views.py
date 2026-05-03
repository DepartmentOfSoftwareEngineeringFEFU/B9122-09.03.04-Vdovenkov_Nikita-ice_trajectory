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
from .services.route_service import generate_route


ICE_IMPACT = {
    "no_ice":     {"light": 1.0,  "medium": 1.0,  "heavy": 1.0},
    "Ice1":       {"light": 10.0, "medium": 30.0,  "heavy": float("inf")},
    "Ice2":       {"light": 8.0,  "medium": 25.0,  "heavy": float("inf")},
    "Ice3":       {"light": 7.0,  "medium": 20.0,  "heavy": float("inf")},
    "Arc4":       {"light": 5.0,  "medium": 14.0,  "heavy": 25.0},
    "Arc5":       {"light": 4.0,  "medium": 14.0,  "heavy": float("inf")},
    "Arc6":       {"light": 3.0,  "medium": 10.0,  "heavy": 20.0},
    "Arc7":       {"light": 2.0,  "medium": 7.0,   "heavy": 14.0},
    "Arc8":       {"light": 1.5,  "medium": 5.0,   "heavy": 10.0},
    "Arc9":       {"light": 1.2,  "medium": 3.0,   "heavy": 7.0},
    "Icebraker6": {"light": 1.0,  "medium": 2.0,   "heavy": 5.0},
    "Icebraker7": {"light": 1.0,  "medium": 1.5,   "heavy": 3.0},
}

ICE_CLASSES = list(ICE_IMPACT.keys())


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

    @action(detail=False, methods=["get"], url_path="route")
    def route(self, request):
        try:
            start_lat = float(request.query_params.get("start_lat"))
            start_lon = float(request.query_params.get("start_lon"))
            end_lat   = float(request.query_params.get("end_lat"))
            end_lon   = float(request.query_params.get("end_lon"))
        except (TypeError, ValueError):
            return Response({"error": "Укажите start_lat, start_lon, end_lat, end_lon"}, status=400)

        route = generate_route(start_lat, start_lon, end_lat, end_lon)
        return Response(route)

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


@api_view(["GET"])
def ice_classes(request):
    return Response(ICE_CLASSES)