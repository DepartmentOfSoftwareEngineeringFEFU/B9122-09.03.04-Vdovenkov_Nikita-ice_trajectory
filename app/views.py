import json
import threading
import time

from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.db.models import Count
from django.shortcuts import render
from django.http import StreamingHttpResponse

from .models import (
    Ship, ShipPosition, WaterArea, WaterAreaPoint,
    IceCondition, ShipType, IceImpact, Route, RoutePoint,
)
from .serializers import (
    ShipSerializer, WaterAreaSerializer, WaterAreaCreateSerializer,
    IceConditionSerializer, WaterAreaPointSerializer, ShipTypeSerializer,
    RouteSerializer, RouteCreateSerializer,
)
from .services.route_service_clusters import generate_cluster_route


def get_ice_coefficients(ice_class_code):
    try:
        ship_type = ShipType.objects.prefetch_related("impacts").get(code=ice_class_code)
        return {impact.ice_type: impact.coefficient for impact in ship_type.impacts.all()}
    except ShipType.DoesNotExist:
        return {}


def _point_type_label(raw_type):
    return {
        "start":   "начальная",
        "end":     "конечная",
        "cluster": "промежуточная",
    }.get(raw_type, "промежуточная")


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

    try:
        area = WaterArea.objects.get(pk=water_area_id)
    except WaterArea.DoesNotExist:
        return StreamingHttpResponse(status=404)

    polygon_points = [
        [float(p.latitude), float(p.longitude)]
        for p in area.points.order_by("order")
    ]
    ice_zones = list(IceCondition.objects.filter(area=area).values(
        "ice_type", "lat_min", "lat_max", "lon_min", "lon_max"
    ))
    ice_coefficients = get_ice_coefficients(ice_class)

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
            route_points = result_box[0]
            yield f"data: {json.dumps({'type': 'done', 'route': route_points})}\n\n"

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
            ).annotate(pos_count=Count("positions")).filter(pos_count__gte=2).distinct()
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


class IceConditionViewSet(viewsets.ModelViewSet):
    serializer_class = IceConditionSerializer

    def get_queryset(self):
        queryset = IceCondition.objects.all()
        water_area_id = self.request.query_params.get("water_area")
        if water_area_id:
            queryset = queryset.filter(area=water_area_id)
        return queryset


class ShipTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ShipType.objects.all()
    serializer_class = ShipTypeSerializer


class RouteViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.action == "create":
            return RouteCreateSerializer
        return RouteSerializer

    def get_queryset(self):
        qs = Route.objects.prefetch_related("points")
        area_name = self.request.query_params.get("area_name")
        if area_name:
            qs = qs.filter(area_name=area_name)
        return qs

    @action(detail=False, methods=["delete"], url_path="clear")
    def clear(self, request):
        qs = Route.objects.all()
        area_name = request.query_params.get("area_name")
        if area_name:
            qs = qs.filter(area_name=area_name)
        count, _ = qs.delete()
        return Response({"deleted": count})


@api_view(["GET"])
def heatmap_data(request):
    water_area_id = request.query_params.get("water_area")
    limit = int(request.query_params.get("limit", 5000))
    qs = ShipPosition.objects.all()
    if water_area_id:
        try:
            area = WaterArea.objects.get(pk=water_area_id)
            qs = qs.filter(
                latitude__gte=area.lat_min, latitude__lte=area.lat_max,
                longitude__gte=area.lon_min, longitude__lte=area.lon_max,
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
                latitude__gte=area.lat_min, latitude__lte=area.lat_max,
                longitude__gte=area.lon_min, longitude__lte=area.lon_max,
            )
        except WaterArea.DoesNotExist:
            return Response([])
    total = qs.count()
    step = max(1, total // limit)
    all_points = list(qs.values_list("latitude", "longitude", "course"))
    sampled = all_points[::step][:limit]
    return Response([
        {"lat": float(lat), "lon": float(lon), "course": float(course)}
        for lat, lon, course in sampled
    ])


@api_view(["GET"])
def ice_classes(request):
    ship_types = ShipType.objects.values_list("code", flat=True)
    return Response(list(ship_types))

@api_view(["GET"])
def export_xml(request):
    from django.http import HttpResponse
    from xml.etree.ElementTree import Element, SubElement, tostring
    from xml.dom import minidom

    root = Element("map")

    areas = WaterArea.objects.prefetch_related("points", "ice_conditions").all()
    for area in areas:
        area_el = SubElement(root, "water_area")
        area_el.set("id", str(area.id))
        area_el.set("name", area.name)
        area_el.set("lat_min", str(area.lat_min))
        area_el.set("lat_max", str(area.lat_max))
        area_el.set("lon_min", str(area.lon_min))
        area_el.set("lon_max", str(area.lon_max))

        points_el = SubElement(area_el, "boundary_points")
        for pt in area.points.order_by("order"):
            pt_el = SubElement(points_el, "point")
            pt_el.set("order", str(pt.order))
            pt_el.set("latitude", str(pt.latitude))
            pt_el.set("longitude", str(pt.longitude))

        ice_el = SubElement(area_el, "ice_conditions")
        for zone in area.ice_conditions.all():
            zone_el = SubElement(ice_el, "zone")
            zone_el.set("id", str(zone.id))
            zone_el.set("ice_type", zone.ice_type)
            zone_el.set("lat_min", str(zone.lat_min))
            zone_el.set("lat_max", str(zone.lat_max))
            zone_el.set("lon_min", str(zone.lon_min))
            zone_el.set("lon_max", str(zone.lon_max))

    xml_str = minidom.parseString(tostring(root, encoding="unicode")).toprettyxml(indent="  ")
    response = HttpResponse(xml_str, content_type="application/xml")
    response["Content-Disposition"] = 'attachment; filename="map_export.xml"'
    return response