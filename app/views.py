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
from .services.route_service_clusters import generate_cluster_route


ICE_IMPACT = {
    "no_ice":     {"none": 2.0, "light": float("inf"), "heavy": float("inf")},
    "Ice1":       {"none": 2.0, "light": 10.0,         "heavy": float("inf")},
    "Ice2":       {"none": 2.0, "light": 10.0,         "heavy": float("inf")},
    "Ice3":       {"none": 2.0, "light": 10.0,         "heavy": float("inf")},
    "Arc4":       {"none": 2.0, "light": 10.0,         "heavy": 30.0},
    "Arc5":       {"none": 2.0, "light": 10.0,         "heavy": 30.0},
    "Arc6":       {"none": 2.0, "light": 10.0,         "heavy": 25.0},
    "Arc7":       {"none": 2.0, "light": 10.0,         "heavy": 20.0},
    "Arc8":       {"none": 2.0, "light": 10.0,         "heavy": 15.0},
    "Arc9":       {"none": 2.0, "light": 10.0,         "heavy": 13.0},
    "Icebraker6": {"none": 2.0, "light": 10.0,         "heavy": 10.0},
    "Icebraker7": {"none": 2.0, "light": 10.0,         "heavy": 5.0},
}

ICE_CLASSES = list(ICE_IMPACT.keys())


def index(request):
    return render(request, "index.html")


def route_progress(request):
    water_area_id = request.GET.get("water_area")
    ice_class = request.GET.get("ice_class", "no_ice")

    try:
        start_lat = float(request.GET.get("start_lat"))
        start_lon = float(request.GET.get("start_lon"))
        end_lat   = float(request.GET.get("end_lat"))
        end_lon   = float(request.GET.get("end_lon"))
    except (TypeError, ValueError):
        return StreamingHttpResponse(status=400)

    if ice_class not in ICE_IMPACT:
        ice_class = "no_ice"

    try:
        area = WaterArea.objects.get(pk=water_area_id)
    except WaterArea.DoesNotExist:
        return StreamingHttpResponse(status=404)

    polygon_points = [
        [float(p.latitude), float(p.longitude)]
        for p in area.points.order_by("order")
    ]
    ice_zones = list(IceZone.objects.filter(area=area).values(
        "ice_type", "lat_min", "lat_max", "lon_min", "lon_max"
    ))
    ice_coefficients = ICE_IMPACT[ice_class]

    def event_stream():
        event_queue = []
        result_box = [None]
        error_box  = [None]
        done_event = threading.Event()

        def run():
            try:
                result_box[0] = generate_cluster_route(
                    start_lat, start_lon, end_lat, end_lon,
                    area_polygon=polygon_points or None,
                    area=area,
                    ice_zones=ice_zones,
                    ice_coefficients=ice_coefficients,
                    progress_callback=lambda pct, msg: event_queue.append((pct, msg)),
                )
            except Exception as e:
                error_box[0] = str(e)
            finally:
                done_event.set()

        t = threading.Thread(target=run)
        t.start()

        sent = 0
        while not done_event.is_set() or sent < len(event_queue):
            while sent < len(event_queue):
                pct, msg = event_queue[sent]
                sent += 1
                yield f"data: {json.dumps({'type': 'progress', 'pct': pct, 'msg': msg})}\n\n"
            time.sleep(0.05)

        t.join()

        if error_box[0]:
            yield f"data: {json.dumps({'type': 'error', 'msg': error_box[0]})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'done', 'route': result_box[0]})}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


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
        water_area_id = request.query_params.get("water_area")
        ice_class = request.query_params.get("ice_class", "no_ice")

        if not water_area_id:
            return Response({"error": "Укажите water_area"}, status=400)

        if ice_class not in ICE_IMPACT:
            return Response({"error": f"Неизвестный ледовый класс: {ice_class}"}, status=400)

        try:
            area = WaterArea.objects.get(pk=water_area_id)
        except WaterArea.DoesNotExist:
            return Response({"error": "Акватория не найдена"}, status=404)

        try:
            start_lat = float(request.query_params.get("start_lat"))
            start_lon = float(request.query_params.get("start_lon"))
            end_lat   = float(request.query_params.get("end_lat"))
            end_lon   = float(request.query_params.get("end_lon"))
        except (TypeError, ValueError):
            return Response({"error": "Укажите start_lat, start_lon, end_lat, end_lon"}, status=400)

        polygon_points = [
            [float(p.latitude), float(p.longitude)]
            for p in area.points.order_by("order")
        ]
        ice_zones = list(IceZone.objects.filter(water_area=area).values(
            "ice_type", "lat_min", "lat_max", "lon_min", "lon_max"
        ))
        ice_coefficients = ICE_IMPACT[ice_class]

        route = generate_cluster_route(
            start_lat, start_lon, end_lat, end_lon,
            area_polygon=polygon_points if polygon_points else None,
            area=area,
            ice_zones=ice_zones,
            ice_coefficients=ice_coefficients,
        )
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
            queryset = queryset.filter(area=water_area_id)
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