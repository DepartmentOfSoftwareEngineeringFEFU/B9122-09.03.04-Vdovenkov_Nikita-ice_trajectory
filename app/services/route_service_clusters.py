import math
import heapq
import numpy as np
from scipy.spatial import KDTree


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def bearing(lat1, lon1, lat2, lon2):
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    b = math.degrees(math.atan2(x, y))
    return (b + 360) % 360


def course_diff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


CLUSTER_RADIUS = 16.0
CLUSTER_THRESHOLD = 20.0
POTENTIAL_CUTOFF = 0.10
ALPHA = 1.0 / (CLUSTER_RADIUS ** 2)
BETA = ALPHA


def subtractive_clustering(courses):
    if not courses:
        return []

    points = np.array(courses, dtype=float)
    n = len(points)
    potentials = np.zeros(n)

    for i in range(n):
        diffs = np.array([course_diff(points[i], points[j]) for j in range(n)])
        potentials[i] = np.sum(np.exp(-ALPHA * diffs ** 2))

    centers = []
    p_max_first = None
    current_potentials = potentials.copy()

    while True:
        idx_max = int(np.argmax(current_potentials))
        p_max = current_potentials[idx_max]

        if p_max_first is None:
            p_max_first = p_max

        if p_max < POTENTIAL_CUTOFF * p_max_first:
            break

        center = points[idx_max]
        centers.append(center)

        diffs = np.array([course_diff(center, points[j]) for j in range(n)])
        current_potentials -= p_max * np.exp(-BETA * diffs ** 2)

    return centers


def course_is_desirable(course_deg, cluster_centers):
    if not cluster_centers:
        return 0.1
    for c in cluster_centers:
        if course_diff(course_deg, c) <= CLUSTER_THRESHOLD:
            return 1.0
    return 0.01


def build_layered_graph(start_lat, start_lon, end_lat, end_lon, n_layers=8, m_half=3):
    total_bearing = bearing(start_lat, start_lon, end_lat, end_lon)
    perp_bearing = (total_bearing + 90) % 360

    total_dist = haversine_km(start_lat, start_lon, end_lat, end_lon)
    step_km = total_dist / (n_layers + 1)
    side_step_km = step_km * 0.8

    def offset_point(lat, lon, dist_km, brng):
        R = 6371.0
        brng_r = math.radians(brng)
        lat_r = math.radians(lat)
        lon_r = math.radians(lon)
        d = dist_km / R
        lat2 = math.asin(math.sin(lat_r) * math.cos(d) +
                         math.cos(lat_r) * math.sin(d) * math.cos(brng_r))
        lon2 = lon_r + math.atan2(
            math.sin(brng_r) * math.sin(d) * math.cos(lat_r),
            math.cos(d) - math.sin(lat_r) * math.sin(lat2)
        )
        return math.degrees(lat2), math.degrees(lon2)

    vertices = [(start_lat, start_lon)]
    layers = []

    for layer_idx in range(n_layers):
        t = (layer_idx + 1) / (n_layers + 1)
        center_lat, center_lon = offset_point(start_lat, start_lon, total_dist * t, total_bearing)

        layer_indices = []
        for m in range(-m_half, m_half + 1):
            if m == 0:
                lat, lon = center_lat, center_lon
            elif m > 0:
                lat, lon = offset_point(center_lat, center_lon, side_step_km * m, perp_bearing)
            else:
                lat, lon = offset_point(center_lat, center_lon, side_step_km * abs(m), (perp_bearing + 180) % 360)
            vertices.append((lat, lon))
            layer_indices.append(len(vertices) - 1)

        layers.append(layer_indices)

    finish_idx = len(vertices)
    vertices.append((end_lat, end_lon))

    edges = []
    prev_layer = [0]

    for layer_indices in layers:
        for i in prev_layer:
            for j in layer_indices:
                d = haversine_km(*vertices[i], *vertices[j])
                edges.append((i, j, d))
        prev_layer = layer_indices

    for i in prev_layer:
        d = haversine_km(*vertices[i], *vertices[finish_idx])
        edges.append((i, finish_idx, d))

    return vertices, edges, finish_idx


def build_position_index(positions):
    if not positions:
        return None, None
    coords = np.array([(lat, lon) for lat, lon, _ in positions])
    courses = np.array([c if c is not None else np.nan for _, _, c in positions])
    tree = KDTree(coords)
    return tree, courses


def get_courses_near_edge(tree, courses_array, lat1, lon1, lat2, lon2, radius_km=2.0):
    if tree is None:
        return []
    mid_lat = (lat1 + lat2) / 2
    mid_lon = (lon1 + lon2) / 2
    radius_deg = radius_km / 111.0
    indices = tree.query_ball_point([mid_lat, mid_lon], radius_deg)
    courses = courses_array[indices]
    return [float(c) for c in courses if not np.isnan(c)]


def get_ice_factor(lat, lon, ice_zones, ice_coefficients):
    if not ice_zones or not ice_coefficients:
        return 1.0

    best = 1.0
    for zone in ice_zones:
        if (zone["lat_min"] <= lat <= zone["lat_max"] and
                zone["lon_min"] <= lon <= zone["lon_max"]):
            coeff = ice_coefficients.get(zone["ice_type"], 1.0)
            if coeff == float("inf"):
                return float("inf")
            best = max(best, coeff)
    return best


def dijkstra(n_vertices, weighted_edges, start, end):
    graph = [[] for _ in range(n_vertices)]
    for i, j, w in weighted_edges:
        graph[i].append((j, w))

    dist = [float('inf')] * n_vertices
    prev = [-1] * n_vertices
    dist[start] = 0.0
    heap = [(0.0, start)]

    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in graph[u]:
            nd = dist[u] + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if dist[end] == float('inf'):
        return None

    path = []
    cur = end
    while cur != -1:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path


def generate_cluster_route(start_lat, start_lon, end_lat, end_lon, area_polygon=None, area=None, ice_zones=None, ice_coefficients=None, progress_callback=None):
    from app.models import ShipPosition

    def progress(pct, msg):
        print(f"[{pct}%] {msg}")
        if progress_callback:
            progress_callback(pct, msg)

    if area is None:
        return _fallback_route(start_lat, start_lon, end_lat, end_lon)

    progress(5, "Загружаем позиции судов...")
    qs = ShipPosition.objects.filter(
        latitude__gte=area.lat_min,
        latitude__lte=area.lat_max,
        longitude__gte=area.lon_min,
        longitude__lte=area.lon_max,
    ).values_list('latitude', 'longitude', 'course')[:200000]

    positions = [(float(lat), float(lon), float(course) if course is not None else None)
                 for lat, lon, course in qs]

    progress(20, f"Загружено {len(positions):,} позиций")

    if len(positions) < 10:
        return _fallback_route(start_lat, start_lon, end_lat, end_lon)

    progress(30, "Строим граф маршрута...")
    vertices, edges, finish_idx = build_layered_graph(
        start_lat, start_lon, end_lat, end_lon,
        n_layers=4, m_half=3
    )

    progress(40, f"Граф: {len(vertices)} вершин, {len(edges)} рёбер")

    progress(50, "Индексируем AIS-данные...")
    tree, courses_array = build_position_index(positions)

    ice_active = bool(ice_zones and ice_coefficients)
    progress(60, "Взвешиваем рёбра графа" + (" (с учётом льда)" if ice_active else "") + "...")

    weighted_edges = []
    total_edges = len(edges)

    for idx_e, (i, j, dist_km) in enumerate(edges):
        lat1, lon1 = vertices[i]
        lat2, lon2 = vertices[j]

        edge_bearing = bearing(lat1, lon1, lat2, lon2)
        edge_len = haversine_km(lat1, lon1, lat2, lon2)
        radius_km = max(2.0, edge_len * 0.4)
        courses = get_courses_near_edge(tree, courses_array, lat1, lon1, lat2, lon2, radius_km=radius_km)

        if len(courses) >= 5:
            centers = subtractive_clustering(courses)
            desirability = course_is_desirable(edge_bearing, centers)
        else:
            desirability = 0.1

        ice_i = get_ice_factor(lat1, lon1, ice_zones, ice_coefficients)
        ice_j = get_ice_factor(lat2, lon2, ice_zones, ice_coefficients)
        ice_factor = max(ice_i, ice_j)

        if ice_factor == float("inf"):
            weight = float("inf")
        else:
            weight = dist_km * ice_factor / desirability

        weighted_edges.append((i, j, weight))

        if total_edges > 0 and (idx_e + 1) % max(1, total_edges // 10) == 0:
            pct = 60 + int((idx_e + 1) / total_edges * 25)
            progress(pct, f"Взвешено рёбер: {idx_e + 1}/{total_edges}")

    progress(88, "Ищем оптимальный путь (Дейкстра)...")
    path = dijkstra(len(vertices), weighted_edges, 0, finish_idx)

    if not path:
        return _fallback_route(start_lat, start_lon, end_lat, end_lon)

    progress(98, f"Путь найден: {len(path)} точек")

    result = []
    for idx in path:
        lat, lon = vertices[idx]
        if idx == 0:
            ptype = "start"
        elif idx == finish_idx:
            ptype = "end"
        else:
            ptype = "cluster"
        result.append({"latitude": round(lat, 6), "longitude": round(lon, 6), "type": ptype})

    return result


def _fallback_route(start_lat, start_lon, end_lat, end_lon):
    return [
        {"latitude": round(start_lat, 6), "longitude": round(start_lon, 6), "type": "start"},
        {"latitude": round((start_lat + end_lat) / 2, 6), "longitude": round((start_lon + end_lon) / 2, 6), "type": "cluster"},
        {"latitude": round(end_lat, 6), "longitude": round(end_lon, 6), "type": "end"},
    ]