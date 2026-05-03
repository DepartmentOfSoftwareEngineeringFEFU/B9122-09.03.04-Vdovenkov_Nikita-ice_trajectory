from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from app.views import (
    ShipViewSet, WaterAreaViewSet, WaterAreaPointViewSet,
    IceZoneViewSet, index, heatmap_data, courses_data, ice_classes
)

router = DefaultRouter()
router.register(r'ships', ShipViewSet, basename='ship')
router.register(r'water-areas', WaterAreaViewSet, basename='waterarea')
router.register(r'water-area-points', WaterAreaPointViewSet, basename='waterareapoint')
router.register(r'ice-zones', IceZoneViewSet, basename='icezone')

urlpatterns = [
    path('', index),
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/heatmap/', heatmap_data),
    path('api/courses/', courses_data),
    path('api/ice-classes/', ice_classes),
]