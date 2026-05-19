from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from app.views import (
    ShipViewSet, WaterAreaViewSet, WaterAreaPointViewSet,
    IceConditionViewSet, ShipTypeViewSet, RouteViewSet,
    index, heatmap_data, courses_data, ice_classes, route_progress, export_xml,
)

router = DefaultRouter()
router.register(r'ships', ShipViewSet, basename='ship')
router.register(r'water-areas', WaterAreaViewSet, basename='waterarea')
router.register(r'water-area-points', WaterAreaPointViewSet, basename='waterareapoint')
router.register(r'ice-conditions', IceConditionViewSet, basename='icecondition')
router.register(r'ship-types', ShipTypeViewSet, basename='shiptype')
router.register(r'routes', RouteViewSet, basename='route')

urlpatterns = [
    path('', index),
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/heatmap/', heatmap_data),
    path('api/courses/', courses_data),
    path('api/ice-classes/', ice_classes),
    path('api/route-progress/', route_progress),
    path('api/export-xml/', export_xml),
]