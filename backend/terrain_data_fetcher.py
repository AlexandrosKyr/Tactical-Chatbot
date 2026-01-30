#!/usr/bin/env python3
"""
Terrain Data Fetcher - Query geographic APIs for real terrain intelligence
Used for OCOKA tactical analysis based on coordinates
"""

import requests
import logging
import math
from typing import Dict, List, Optional
import time

logger = logging.getLogger(__name__)

# Module-level cache for terrain data (persists across instances)
_terrain_cache: Dict[str, Dict] = {}
_cache_ttl = 3600  # 1 hour cache TTL


class TerrainDataFetcher:
    """Fetch real terrain data from geographic APIs with caching"""

    def __init__(self):
        """Initialize terrain data fetcher"""
        self.overpass_url = "https://overpass-api.de/api/interpreter"

    def _get_cache_key(self, lat: float, lon: float, radius_km: float) -> str:
        """Generate cache key from coordinates (rounded for cache hits)"""
        # Round to 3 decimals (~111m precision) for reasonable cache hits
        lat_r = round(lat, 3)
        lon_r = round(lon, 3)
        radius_r = round(radius_km, 1)
        return f"{lat_r}_{lon_r}_{radius_r}"

    def fetch_terrain_data(self, lat: float, lon: float, radius_km: float = 5) -> Dict:
        """
        Fetch comprehensive terrain data for tactical analysis (with caching)

        Args:
            lat: Latitude
            lon: Longitude
            radius_km: Analysis radius in kilometers

        Returns:
            Dict with terrain intelligence data
        """
        # Check cache first
        cache_key = self._get_cache_key(lat, lon, radius_km)
        if cache_key in _terrain_cache:
            cached = _terrain_cache[cache_key]
            if time.time() - cached.get('_cached_at', 0) < _cache_ttl:
                logger.info(f"Cache hit for {lat}, {lon}")
                return cached

        logger.info(f"Fetching terrain data for {lat}, {lon} (radius: {radius_km}km)")

        terrain_data = {
            'location': {
                'lat': lat,
                'lon': lon,
                'radius_km': radius_km
            },
            'place_name': None,
            'address': {},
            'elevation': None,
            'nearby_elevations': [],
            'slope_analysis': {},
            'roads': [],
            'waterways': [],
            'waterway_summary': {},  # distinct named waterways by type
            'buildings': [],
            'forests': [],
            'forest_summary': {},  # distinct named forest areas
            'landuse': [],
            'crossings': [],  # bridges, fords, tunnels
            'crossing_summary': {},  # distinct named crossings by type
            'railways': [],  # rail lines (obstacles)
            'railway_summary': {},  # distinct named rail lines
            'power_lines': [],  # power infrastructure
            'cell_towers': [],  # communications infrastructure
            'fuel_stations': [],  # logistics/resupply points
            'medical_facilities': [],  # hospitals, clinics
            'schools': [],  # sensitive sites (ROE considerations)
            'helipads': [],  # aviation landing zones
            'line_of_sight': {},  # visibility analysis
            'terrain_analysis': {},
            'movement_times': {},  # Time-distance calculations
            'weather': {}  # Past week weather data
        }

        #Reverse geocoding - Get place names
        place_info = self._reverse_geocode(lat, lon)
        terrain_data['place_name'] = place_info.get('place_name')
        terrain_data['address'] = place_info.get('address', {})

        #Elevation data (Open-Meteo API)
        elevation_data = self._fetch_elevation(lat, lon, radius_km)
        terrain_data['elevation'] = elevation_data.get('center_elevation')
        terrain_data['nearby_elevations'] = elevation_data.get('nearby_elevations', [])

        #Calculate slope/gradient from elevation data
        if terrain_data['elevation'] is not None and terrain_data['nearby_elevations']:
            terrain_data['slope_analysis'] = self._calculate_slope(
                terrain_data['elevation'],
                terrain_data['nearby_elevations'],
                radius_km
            )

        # Infrastructure and terrain features (OpenStreetMap)
        osm_data = self._fetch_osm_features(lat, lon, radius_km)
        terrain_data['roads'] = osm_data.get('roads', [])
        terrain_data['waterways'] = osm_data.get('waterways', [])
        terrain_data['waterway_summary'] = self._summarize_waterways(terrain_data['waterways'])
        terrain_data['buildings'] = osm_data.get('buildings', [])
        terrain_data['forests'] = osm_data.get('forests', [])
        terrain_data['forest_summary'] = self._summarize_forests(terrain_data['forests'])
        terrain_data['landuse'] = osm_data.get('landuse', [])
        terrain_data['crossings'] = osm_data.get('crossings', [])
        terrain_data['crossing_summary'] = self._summarize_crossings(terrain_data['crossings'])
        terrain_data['railways'] = osm_data.get('railways', [])
        terrain_data['railway_summary'] = self._summarize_railways(terrain_data['railways'])
        terrain_data['power_lines'] = osm_data.get('power_lines', [])
        terrain_data['cell_towers'] = osm_data.get('cell_towers', [])
        terrain_data['fuel_stations'] = osm_data.get('fuel_stations', [])
        terrain_data['medical_facilities'] = osm_data.get('medical_facilities', [])
        terrain_data['medical_summary'] = self._summarize_medical(terrain_data['medical_facilities'])
        terrain_data['schools'] = osm_data.get('schools', [])
        terrain_data['school_summary'] = self._summarize_schools(terrain_data['schools'])
        terrain_data['helipads'] = osm_data.get('helipads', [])

        #Line of sight analysis
        if terrain_data['elevation'] is not None and terrain_data['nearby_elevations']:
            terrain_data['line_of_sight'] = self._analyze_line_of_sight(
                terrain_data['elevation'],
                terrain_data['nearby_elevations'],
                terrain_data['forests'],
                terrain_data['buildings']
            )

        # Analyze terrain for tactical significance
        terrain_data['terrain_analysis'] = self._analyze_terrain(terrain_data)

        # Calculate movement times across the area
        terrain_data['movement_times'] = self._calculate_movement_times(terrain_data)

        # Fetch weather data (past week)
        terrain_data['weather'] = self._fetch_weather(lat, lon)

        # Cache the result
        terrain_data['_cached_at'] = time.time()
        _terrain_cache[cache_key] = terrain_data

        logger.info("Terrain data fetch complete")
        return terrain_data

    def _reverse_geocode(self, lat: float, lon: float) -> Dict:
        """
        Reverse geocode coordinates to get place name and address

        Uses Nominatim (OpenStreetMap)
        Returns:
            Dict with place_name and address components
        """
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': lat,
                'lon': lon,
                'format': 'json',
                'addressdetails': 1,
                'zoom': 14
            }
            headers = {
                'User-Agent': 'NATO-Tactical-Intelligence-Assistant/1.0'
            }

            response = requests.get(url, params=params, headers=headers, timeout=20)
            response.raise_for_status()
            data = response.json()

            address = data.get('address', {})

            place_parts = list(filter(None, [
                address.get('suburb') or address.get('neighbourhood'),
                address.get('city') or address.get('town') or address.get('village'),
                address.get('state'),
                address.get('country')
            ]))

            place_name = ", ".join(place_parts) if place_parts else f"{lat}, {lon}"
            logger.info(f"Reverse geocoded: {place_name}")

            return {
                'place_name': place_name,
                'address': {
                    'city': address.get('city') or address.get('town') or address.get('village'),
                    'state': address.get('state'),
                    'country': address.get('country'),
                    'country_code': address.get('country_code', '').upper(),
                    'suburb': address.get('suburb') or address.get('neighbourhood'),
                    'postcode': address.get('postcode')
                }
            }

        except Exception as e:
            logger.warning(f"Reverse geocoding failed: {e}")
            return {
                'place_name': f"{lat}, {lon}",
                'address': {}
            }

    def _fetch_elevation(self, lat: float, lon: float, radius_km: float) -> Dict:
        """
        Fetch elevation data from Open-Meteo Elevation API (Copernicus DEM, 30m resolution)

        Returns:
            Dict with center elevation and nearby elevation samples
        """
        # Calculate sample points in cardinal + diagonal directions (8 points)
        sample_distance_m = radius_km * 1000
        lat_offset = sample_distance_m / 111000  # degrees per meter
        lon_offset = sample_distance_m / (111000 * math.cos(math.radians(lat)))

        sample_points = [
            ('N', lat + lat_offset, lon),
            ('NE', lat + lat_offset * 0.707, lon + lon_offset * 0.707),
            ('E', lat, lon + lon_offset),
            ('SE', lat - lat_offset * 0.707, lon + lon_offset * 0.707),
            ('S', lat - lat_offset, lon),
            ('SW', lat - lat_offset * 0.707, lon - lon_offset * 0.707),
            ('W', lat, lon - lon_offset),
            ('NW', lat + lat_offset * 0.707, lon - lon_offset * 0.707),
        ]

        try:
            # Open-Meteo supports batch requests with comma-separated coordinates
            all_lats = [lat] + [p[1] for p in sample_points]
            all_lons = [lon] + [p[2] for p in sample_points]

            url = "https://api.open-meteo.com/v1/elevation"
            params = {
                'latitude': ','.join(str(round(l, 6)) for l in all_lats),
                'longitude': ','.join(str(round(l, 6)) for l in all_lons),
            }

            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            elevations = data.get('elevation', [])
            if not elevations:
                return {}

            center_elevation = elevations[0]
            nearby_elevations = []

            for i, (direction, point_lat, point_lon) in enumerate(sample_points):
                if i + 1 < len(elevations):
                    nearby_elevations.append({
                        'direction': direction,
                        'lat': point_lat,
                        'lon': point_lon,
                        'elevation': elevations[i + 1]
                    })

            logger.info(f"Elevation (Open-Meteo): {center_elevation}m (center)")
            return {
                'center_elevation': center_elevation,
                'nearby_elevations': nearby_elevations
            }

        except Exception as e:
            logger.warning(f"Elevation fetch failed: {e}")
            return {}
        
    def _fetch_weather(self, lat: float, lon: float) -> Dict:
        """
        Fetch last week and current weather data from Open-Meteo API

        Returns:
            Dict with daily weather data and weekly averages including:
            - temperature (min, max, avg)
            - wind speed and gusts
            - precipitation (rain, snow)
            - sunshine duration
        """
        try:
            # Open-Meteo Forecast API with past_days parameter for historical data
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                'latitude': round(lat, 6),
                'longitude': round(lon, 6),
                'past_days': 7,
                'forecast_days': 1,  # Include today
                'daily': ','.join([
                    'temperature_2m_max',
                    'temperature_2m_min',
                    'precipitation_sum',
                    'rain_sum',
                    'snowfall_sum',
                    'sunshine_duration',
                    'wind_speed_10m_max',
                    'wind_gusts_10m_max',
                    'weather_code'
                ]),
                'timezone': 'auto'
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            daily = data.get('daily', {})
            if not daily:
                logger.warning("No daily weather data returned")
                return {}

            dates = daily.get('time', [])
            temp_max = daily.get('temperature_2m_max', [])
            temp_min = daily.get('temperature_2m_min', [])
            precipitation = daily.get('precipitation_sum', [])
            rain = daily.get('rain_sum', [])
            snow = daily.get('snowfall_sum', [])
            sunshine = daily.get('sunshine_duration', [])  # in seconds
            wind_speed = daily.get('wind_speed_10m_max', [])
            wind_gusts = daily.get('wind_gusts_10m_max', [])
            weather_codes = daily.get('weather_code', [])

            # Build daily breakdown
            daily_data = []
            for i, date in enumerate(dates):
                day_info = {
                    'date': date,
                    'temp_max_c': temp_max[i] if i < len(temp_max) else None,
                    'temp_min_c': temp_min[i] if i < len(temp_min) else None,
                    'precipitation_mm': precipitation[i] if i < len(precipitation) else None,
                    'rain_mm': rain[i] if i < len(rain) else None,
                    'snow_cm': snow[i] if i < len(snow) else None,
                    'sunshine_hours': round(sunshine[i] / 3600, 1) if i < len(sunshine) and sunshine[i] else 0,
                    'wind_speed_max_kmh': wind_speed[i] if i < len(wind_speed) else None,
                    'wind_gusts_max_kmh': wind_gusts[i] if i < len(wind_gusts) else None,
                    'weather_code': weather_codes[i] if i < len(weather_codes) else None
                }
                daily_data.append(day_info)

            # Calculate weekly averages (exclude None values)
            def safe_avg(values):
                valid = [v for v in values if v is not None]
                return round(sum(valid) / len(valid), 1) if valid else None

            def safe_sum(values):
                valid = [v for v in values if v is not None]
                return round(sum(valid), 1) if valid else 0

            weekly_summary = {
                'avg_temp_max_c': safe_avg(temp_max),
                'avg_temp_min_c': safe_avg(temp_min),
                'avg_temp_c': safe_avg([(mx + mn) / 2 for mx, mn in zip(temp_max, temp_min) if mx and mn]),
                'total_precipitation_mm': safe_sum(precipitation),
                'total_rain_mm': safe_sum(rain),
                'total_snow_cm': safe_sum(snow),
                'avg_sunshine_hours': safe_avg([s / 3600 if s else 0 for s in sunshine]),
                'avg_wind_speed_max_kmh': safe_avg(wind_speed),
                'max_wind_gust_kmh': max([g for g in wind_gusts if g is not None], default=None),
                'rainy_days': sum(1 for r in rain if r and r > 0.1),
                'snowy_days': sum(1 for s in snow if s and s > 0),
            }

            # Weather condition summary based on codes
            # WMO Weather interpretation codes: https://open-meteo.com/en/docs
            condition_map = {
                0: 'clear', 1: 'mainly_clear', 2: 'partly_cloudy', 3: 'overcast',
                45: 'fog', 48: 'fog', 51: 'light_drizzle', 53: 'drizzle', 55: 'heavy_drizzle',
                61: 'light_rain', 63: 'rain', 65: 'heavy_rain',
                71: 'light_snow', 73: 'snow', 75: 'heavy_snow',
                80: 'rain_showers', 81: 'rain_showers', 82: 'heavy_rain_showers',
                95: 'thunderstorm', 96: 'thunderstorm_hail', 99: 'thunderstorm_hail'
            }

            conditions = [condition_map.get(code, 'unknown') for code in weather_codes if code is not None]
            weekly_summary['predominant_conditions'] = list(set(conditions))

            weather_result = {
                'daily': daily_data,
                'weekly_summary': weekly_summary,
                'units': {
                    'temperature': '°C',
                    'precipitation': 'mm',
                    'snow': 'cm',
                    'wind_speed': 'km/h',
                    'sunshine': 'hours'
                }
            }

            logger.info(f"Weather data fetched: {len(daily_data)} days, "
                       f"avg temp {weekly_summary['avg_temp_c']}°C, "
                       f"precip {weekly_summary['total_precipitation_mm']}mm")

            return weather_result

        except Exception as e:
            logger.warning(f"Weather fetch failed: {e}")
            return {}


    def _calculate_slope(self, center_elev: float, nearby_elevs: List[Dict],
                         radius_km: float) -> Dict:
        """
        Calculate slope/gradient from elevation data

        Returns:
            Dict with slope analysis including vehicle mobility assessment
        """
        if not center_elev or not nearby_elevs:
            return {}

        distance_m = radius_km * 1000
        slopes = []
        direction_slopes = {}

        for point in nearby_elevs:
            elev = point.get('elevation')
            if elev is None:
                continue

            rise = elev - center_elev  # Positive = uphill from center
            # Calculate actual distance using Pythagorean theorem for diagonal directions
            direction = point.get('direction', '')
            if direction in ['NE', 'SE', 'SW', 'NW']:
                actual_distance = distance_m * 1.414  # Diagonal
            else:
                actual_distance = distance_m

            slope_percent = (rise / actual_distance) * 100
            slope_degrees = math.degrees(math.atan(rise / actual_distance))

            slopes.append(abs(slope_percent))
            direction_slopes[direction] = {
                'slope_percent': round(slope_percent, 1),
                'slope_degrees': round(slope_degrees, 1),
                'elevation_change': round(rise, 1),
                'direction': 'uphill' if rise > 0 else 'downhill' if rise < 0 else 'flat'
            }

        avg_slope = sum(slopes) / len(slopes) if slopes else 0
        max_slope = max(slopes) if slopes else 0

        # Vehicle mobility assessment based on slope
        # Infantry: can handle up to 60% slopes
        # Wheeled vehicles: typically max 30-40%
        # Tracked vehicles (tanks): typically max 60%
        mobility = {
            'infantry': max_slope < 60,
            'wheeled_vehicles': max_slope < 30,
            'tracked_vehicles': max_slope < 60,
            'assessment': 'flat' if max_slope < 5 else 'gentle' if max_slope < 15 else 'moderate' if max_slope < 30 else 'steep' if max_slope < 60 else 'very steep'
        }

        logger.info(f"Slope analysis: avg {avg_slope:.1f}%, max {max_slope:.1f}%")

        return {
            'average_slope_percent': round(avg_slope, 1),
            'max_slope_percent': round(max_slope, 1),
            'direction_slopes': direction_slopes,
            'mobility': mobility
        }

    def _fetch_osm_features(self, lat: float, lon: float, radius_km: float) -> Dict:
        """
        Fetch infrastructure and terrain features from OpenStreetMap
        Including tactical infrastructure for military analysis

        Returns:
            Dict with roads, waterways, buildings, forests, landuse, crossings,
            railways, power_lines, cell_towers, fuel_stations, medical_facilities,
            schools, helipads
        """
        radius_m = radius_km * 1000

        # Comprehensive Overpass QL query for tactical infrastructure
        query = f"""
        [out:json][timeout:90];
        (
          // Roads (avenues of approach)
          way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|track"]
            (around:{radius_m},{lat},{lon});

          // Waterways (obstacles)
          way["waterway"~"river|stream|canal"]
            (around:{radius_m},{lat},{lon});

          // Buildings (urban terrain)
          way["building"]
            (around:{radius_m},{lat},{lon});

          // Forests (cover/concealment)
          way["natural"="wood"]
            (around:{radius_m},{lat},{lon});
          way["landuse"="forest"]
            (around:{radius_m},{lat},{lon});

          // Landuse
          way["landuse"]
            (around:{radius_m},{lat},{lon});

          // BRIDGES (water crossing points)
          way["bridge"="yes"]
            (around:{radius_m},{lat},{lon});

          // FORDS (shallow crossing points)
          node["ford"="yes"]
            (around:{radius_m},{lat},{lon});
          way["ford"="yes"]
            (around:{radius_m},{lat},{lon});

          // TUNNELS (covered routes)
          way["tunnel"="yes"]
            (around:{radius_m},{lat},{lon});

          // DAMS (potential crossings and obstacles)
          way["waterway"="dam"]
            (around:{radius_m},{lat},{lon});

          // RAILWAYS (obstacles, linear features)
          way["railway"~"rail|light_rail|narrow_gauge"]
            (around:{radius_m},{lat},{lon});

          // POWER LINES (obstacles for aviation, infrastructure)
          way["power"="line"]
            (around:{radius_m},{lat},{lon});
          node["power"="tower"]
            (around:{radius_m},{lat},{lon});
          node["power"="pole"]
            (around:{radius_m},{lat},{lon});

          // CELL TOWERS (communications infrastructure)
          node["man_made"="tower"]["tower:type"="communication"]
            (around:{radius_m},{lat},{lon});
          node["man_made"="mast"]
            (around:{radius_m},{lat},{lon});

          // FUEL STATIONS (logistics/resupply)
          node["amenity"="fuel"]
            (around:{radius_m},{lat},{lon});
          way["amenity"="fuel"]
            (around:{radius_m},{lat},{lon});

          // MEDICAL FACILITIES (hospitals, clinics)
          node["amenity"="hospital"]
            (around:{radius_m},{lat},{lon});
          way["amenity"="hospital"]
            (around:{radius_m},{lat},{lon});
          node["amenity"="clinic"]
            (around:{radius_m},{lat},{lon});

          // SCHOOLS (sensitive sites - ROE considerations)
          node["amenity"="school"]
            (around:{radius_m},{lat},{lon});
          way["amenity"="school"]
            (around:{radius_m},{lat},{lon});
          node["amenity"="university"]
            (around:{radius_m},{lat},{lon});
          way["amenity"="university"]
            (around:{radius_m},{lat},{lon});

          // HELIPADS (aviation landing zones)
          node["aeroway"="helipad"]
            (around:{radius_m},{lat},{lon});
          way["aeroway"="helipad"]
            (around:{radius_m},{lat},{lon});
          node["aeroway"="heliport"]
            (around:{radius_m},{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """

        try:
            response = requests.post(
                self.overpass_url,
                data={'data': query},
                timeout=200
            )
            response.raise_for_status()

            data = response.json()

            features = {
                'roads': [],
                'waterways': [],
                'buildings': [],
                'forests': [],
                'landuse': [],
                'crossings': [],
                'railways': [],
                'power_lines': [],
                'cell_towers': [],
                'fuel_stations': [],
                'medical_facilities': [],
                'schools': [],
                'helipads': []
            }

            for element in data.get('elements', []):
                tags = element.get('tags', {})

                # Roads
                if 'highway' in tags:
                    features['roads'].append({
                        'type': tags['highway'],
                        'name': tags.get('name', 'Unnamed road'),
                        'surface': tags.get('surface', 'unknown')
                    })

                # Waterways
                if 'waterway' in tags and tags['waterway'] not in ['dam']:
                    features['waterways'].append({
                        'type': tags['waterway'],
                        'name': tags.get('name', 'Unnamed waterway'),
                        'width': tags.get('width', 'unknown')
                    })

                # Buildings
                if 'building' in tags:
                    features['buildings'].append({
                        'type': tags.get('building', 'yes')
                    })

                # Forests
                if tags.get('natural') == 'wood' or tags.get('landuse') == 'forest':
                    features['forests'].append({
                        'type': 'forest',
                        'name': tags.get('name', 'Forest area')
                    })

                # Landuse
                if 'landuse' in tags:
                    features['landuse'].append({
                        'type': tags['landuse']
                    })

                # CROSSINGS (bridges, fords, tunnels, dams)
                if tags.get('bridge') == 'yes':
                    features['crossings'].append({
                        'type': 'bridge',
                        'name': tags.get('name', 'Unnamed bridge'),
                        'road_type': tags.get('highway', 'unknown'),
                        'capacity': 'heavy' if tags.get('highway') in ['motorway', 'trunk', 'primary'] else 'medium'
                    })

                if tags.get('ford') == 'yes':
                    features['crossings'].append({
                        'type': 'ford',
                        'name': tags.get('name', 'Ford crossing'),
                        'capacity': 'light'  # Fords typically for light vehicles
                    })

                if tags.get('tunnel') == 'yes':
                    features['crossings'].append({
                        'type': 'tunnel',
                        'name': tags.get('name', 'Unnamed tunnel'),
                        'road_type': tags.get('highway', 'unknown')
                    })

                if tags.get('waterway') == 'dam':
                    features['crossings'].append({
                        'type': 'dam',
                        'name': tags.get('name', 'Dam'),
                        'capacity': 'potential_crossing'
                    })

                # RAILWAYS (obstacles)
                if 'railway' in tags and tags['railway'] in ['rail', 'light_rail', 'narrow_gauge']:
                    features['railways'].append({
                        'type': tags['railway'],
                        'name': tags.get('name', 'Railway line'),
                        'electrified': tags.get('electrified', 'unknown')
                    })

                # POWER LINES (aviation hazards, infrastructure)
                if tags.get('power') == 'line':
                    features['power_lines'].append({
                        'type': 'power_line',
                        'voltage': tags.get('voltage', 'unknown'),
                        'cables': tags.get('cables', 'unknown')
                    })
                if tags.get('power') in ['tower', 'pole']:
                    features['power_lines'].append({
                        'type': f"power_{tags['power']}",
                        'voltage': tags.get('voltage', 'unknown')
                    })

                # CELL TOWERS (communications)
                if tags.get('man_made') == 'tower' and tags.get('tower:type') == 'communication':
                    features['cell_towers'].append({
                        'type': 'communication_tower',
                        'name': tags.get('name', 'Cell tower'),
                        'operator': tags.get('operator', 'unknown')
                    })
                if tags.get('man_made') == 'mast':
                    features['cell_towers'].append({
                        'type': 'communications_mast',
                        'name': tags.get('name', 'Communications mast'),
                        'height': tags.get('height', 'unknown')
                    })

                # FUEL STATIONS (logistics)
                if tags.get('amenity') == 'fuel':
                    features['fuel_stations'].append({
                        'type': 'fuel_station',
                        'name': tags.get('name', 'Fuel station'),
                        'brand': tags.get('brand', 'unknown'),
                        'fuel_types': tags.get('fuel:diesel', 'unknown')
                    })

                # MEDICAL FACILITIES
                if tags.get('amenity') == 'hospital':
                    features['medical_facilities'].append({
                        'type': 'hospital',
                        'name': tags.get('name', 'Hospital'),
                        'emergency': tags.get('emergency', 'unknown')
                    })
                if tags.get('amenity') == 'clinic':
                    features['medical_facilities'].append({
                        'type': 'clinic',
                        'name': tags.get('name', 'Medical clinic')
                    })

                # SCHOOLS (sensitive sites - ROE)
                if tags.get('amenity') == 'school':
                    features['schools'].append({
                        'type': 'school',
                        'name': tags.get('name', 'School')
                    })
                if tags.get('amenity') == 'university':
                    features['schools'].append({
                        'type': 'university',
                        'name': tags.get('name', 'University')
                    })

                # HELIPADS (aviation LZ)
                if tags.get('aeroway') in ['helipad', 'heliport']:
                    features['helipads'].append({
                        'type': tags['aeroway'],
                        'name': tags.get('name', 'Helipad'),
                        'surface': tags.get('surface', 'unknown')
                    })

            logger.info(f"OSM features: {len(features['roads'])} roads, "
                       f"{len(features['waterways'])} waterways, "
                       f"{len(features['buildings'])} buildings, "
                       f"{len(features['forests'])} forests, "
                       f"{len(features['crossings'])} crossings, "
                       f"{len(features['railways'])} railways, "
                       f"{len(features['power_lines'])} power infrastructure, "
                       f"{len(features['cell_towers'])} cell towers, "
                       f"{len(features['fuel_stations'])} fuel stations, "
                       f"{len(features['medical_facilities'])} medical facilities, "
                       f"{len(features['schools'])} schools, "
                       f"{len(features['helipads'])} helipads")

            return features

        except Exception as e:
            logger.error(f"OSM fetch failed: {e}")
            return {
                'roads': [], 'waterways': [], 'buildings': [], 'forests': [],
                'landuse': [], 'crossings': [], 'railways': [], 'power_lines': [],
                'cell_towers': [], 'fuel_stations': [], 'medical_facilities': [],
                'schools': [], 'helipads': []
            }

    def _summarize_waterways(self, waterways: List[Dict]) -> Dict:
        """
        Deduplicate waterway segments into distinct named features grouped by type.

        OSM represents a single river as many way-segments. This method collapses
        those segments so consumers see "7 rivers" instead of "72 river segments".

        Returns:
            Dict with per-type lists of unique named waterways plus segment counts.
        """
        from collections import Counter

        segments_by_type = Counter(w['type'] for w in waterways)

        # Collect unique named waterways per type
        seen: Dict[str, set] = {}
        for w in waterways:
            wtype = w['type']
            name = w.get('name', '')
            if name and name not in ('Unnamed waterway', ''):
                seen.setdefault(wtype, set()).add(name)

        named_by_type: Dict[str, List[str]] = {
            wtype: sorted(names) for wtype, names in seen.items()
        }

        # Build summary
        summary: Dict = {
            'total_segments': len(waterways),
            'segments_by_type': dict(segments_by_type),
            'distinct_named': {},
            'total_distinct_named': 0,
        }

        total_named = 0
        for wtype in sorted(segments_by_type.keys()):
            names = named_by_type.get(wtype, [])
            summary['distinct_named'][wtype] = {
                'count': len(names),
                'names': names,
            }
            total_named += len(names)

        summary['total_distinct_named'] = total_named

        logger.info(
            f"Waterway summary: {len(waterways)} segments -> "
            f"{total_named} distinct named features "
            f"({', '.join(f'{v} {k}' for k, v in segments_by_type.items())})"
        )

        return summary

    def _summarize_forests(self, forests: List[Dict]) -> Dict:
        """
        Deduplicate forest segments into distinct named areas.

        OSM maps forests as many polygons; a single named forest (e.g.
        "Puszcza Augustowska") may appear as dozens of segments.

        Returns:
            Dict with total segments, distinct named areas, and unnamed count.
        """
        named: set = set()
        unnamed_count = 0

        for f in forests:
            name = f.get('name', '')
            if name and name not in ('Forest area', ''):
                named.add(name)
            else:
                unnamed_count += 1

        summary = {
            'total_segments': len(forests),
            'distinct_named': sorted(named),
            'named_count': len(named),
            'unnamed_segments': unnamed_count,
        }

        logger.info(
            f"Forest summary: {len(forests)} segments -> "
            f"{len(named)} distinct named areas, "
            f"{unnamed_count} unnamed segments"
        )

        return summary

    def _summarize_crossings(self, crossings: List[Dict]) -> Dict:
        """
        Deduplicate crossing segments into distinct named features by type
        (bridge, ford, tunnel, dam).

        A single bridge may be split across multiple OSM way-segments.

        Returns:
            Dict with per-type counts and distinct named crossings.
        """
        from collections import Counter

        segments_by_type = Counter(c['type'] for c in crossings)

        # Collect unique named crossings per type
        seen: Dict[str, set] = {}
        unnamed_defaults = ('Unnamed bridge', 'Ford crossing', 'Unnamed tunnel', 'Dam')
        for c in crossings:
            ctype = c['type']
            name = c.get('name', '')
            if name and name not in unnamed_defaults and name != '':
                seen.setdefault(ctype, set()).add(name)

        summary: Dict = {
            'total_segments': len(crossings),
            'segments_by_type': dict(segments_by_type),
            'distinct_named': {},
            'total_distinct_named': 0,
        }

        total_named = 0
        for ctype in sorted(segments_by_type.keys()):
            names = sorted(seen.get(ctype, []))
            summary['distinct_named'][ctype] = {
                'count': len(names),
                'names': names,
            }
            total_named += len(names)

        summary['total_distinct_named'] = total_named

        logger.info(
            f"Crossing summary: {len(crossings)} segments -> "
            f"{total_named} distinct named crossings "
            f"({', '.join(f'{v} {k}' for k, v in segments_by_type.items())})"
        )

        return summary

    def _summarize_railways(self, railways: List[Dict]) -> Dict:
        """
        Deduplicate railway segments into distinct named rail lines.

        A single rail line (e.g. "Linia kolejowa nr 51") is mapped as
        many OSM way-segments.

        Returns:
            Dict with total segments and distinct named lines.
        """
        named: set = set()
        unnamed_count = 0

        for r in railways:
            name = r.get('name', '')
            if name and name not in ('Railway line', ''):
                named.add(name)
            else:
                unnamed_count += 1

        summary = {
            'total_segments': len(railways),
            'distinct_named': sorted(named),
            'named_count': len(named),
            'unnamed_segments': unnamed_count,
        }

        logger.info(
            f"Railway summary: {len(railways)} segments -> "
            f"{len(named)} distinct named lines, "
            f"{unnamed_count} unnamed segments"
        )

        return summary

    def _summarize_medical(self, medical_facilities: List[Dict]) -> Dict:
        """
        Deduplicate medical facility entries into distinct named features by type.

        OSM often maps the same hospital/clinic as both a node and a way polygon,
        inflating raw counts.  This collapses duplicates by name.

        Returns:
            Dict with per-type distinct named facilities plus segment counts.
        """
        from collections import Counter

        segments_by_type = Counter(m['type'] for m in medical_facilities)

        # Collect unique named facilities per type
        seen: Dict[str, set] = {}
        unnamed_defaults = ('Hospital', 'Medical clinic')
        for m in medical_facilities:
            mtype = m['type']
            name = m.get('name', '')
            if name and name not in unnamed_defaults and name != '':
                seen.setdefault(mtype, set()).add(name)

        summary: Dict = {
            'total_segments': len(medical_facilities),
            'segments_by_type': dict(segments_by_type),
            'distinct_named': {},
            'total_distinct_named': 0,
        }

        total_named = 0
        unnamed_total = 0
        for mtype in sorted(segments_by_type.keys()):
            names = sorted(seen.get(mtype, []))
            seg_count = segments_by_type[mtype]
            unnamed_count = seg_count - sum(
                1 for m in medical_facilities
                if m['type'] == mtype and m.get('name', '') in seen.get(mtype, set())
            )
            summary['distinct_named'][mtype] = {
                'count': len(names),
                'names': names[:20],  # cap list for readability
            }
            total_named += len(names)
            unnamed_total += max(unnamed_count, 0)

        summary['total_distinct_named'] = total_named
        summary['unnamed_segments'] = unnamed_total

        logger.info(
            f"Medical summary: {len(medical_facilities)} segments -> "
            f"{total_named} distinct named facilities "
            f"({', '.join(f'{v} {k}' for k, v in segments_by_type.items())})"
        )

        return summary

    def _summarize_schools(self, schools: List[Dict]) -> Dict:
        """
        Deduplicate school/university entries into distinct named features by type.

        OSM often maps the same school as both a node and a way polygon,
        inflating raw counts.  This collapses duplicates by name.

        Returns:
            Dict with per-type distinct named schools plus segment counts.
        """
        from collections import Counter

        segments_by_type = Counter(s['type'] for s in schools)

        # Collect unique named schools per type
        seen: Dict[str, set] = {}
        unnamed_defaults = ('School', 'University')
        for s in schools:
            stype = s['type']
            name = s.get('name', '')
            if name and name not in unnamed_defaults and name != '':
                seen.setdefault(stype, set()).add(name)

        summary: Dict = {
            'total_segments': len(schools),
            'segments_by_type': dict(segments_by_type),
            'distinct_named': {},
            'total_distinct_named': 0,
        }

        total_named = 0
        unnamed_total = 0
        for stype in sorted(segments_by_type.keys()):
            names = sorted(seen.get(stype, []))
            seg_count = segments_by_type[stype]
            unnamed_count = seg_count - sum(
                1 for s in schools
                if s['type'] == stype and s.get('name', '') in seen.get(stype, set())
            )
            summary['distinct_named'][stype] = {
                'count': len(names),
                'names': names[:20],  # cap list for readability
            }
            total_named += len(names)
            unnamed_total += max(unnamed_count, 0)

        summary['total_distinct_named'] = total_named
        summary['unnamed_segments'] = unnamed_total

        logger.info(
            f"School summary: {len(schools)} segments -> "
            f"{total_named} distinct named schools "
            f"({', '.join(f'{v} {k}' for k, v in segments_by_type.items())})"
        )

        return summary

    def _analyze_line_of_sight(self, center_elev: float, nearby_elevs: List[Dict],
                                forests: List, buildings: List) -> Dict:
        """
        Analyze line of sight / visibility from center position

        Returns:
            Dict with visibility assessment in each direction
        """
        los_analysis = {
            'overall_visibility': 'unknown',
            'directions': {},
            'observation_quality': 'unknown',
            'concealment_from': []
        }

        if not center_elev or not nearby_elevs:
            return los_analysis

        # Analyze LOS in each direction
        clear_directions = 0
        blocked_directions = 0

        for point in nearby_elevs:
            direction = point.get('direction', 'unknown')
            elev = point.get('elevation')

            if elev is None:
                continue

            # Basic LOS: can see if target is lower or same height
            # (simplified - real LOS would need intermediate terrain)
            elevation_diff = elev - center_elev
            has_los = elevation_diff <= 5  # Can see if target is within 5m above

            # Vegetation/building obstruction factor
            # More forests/buildings = more likely blocked
            obstruction_factor = min(1.0, (len(forests) + len(buildings)) / 100)

            if has_los and obstruction_factor < 0.7:
                los_analysis['directions'][direction] = {
                    'visibility': 'clear',
                    'elevation_diff': round(elevation_diff, 1),
                    'obstruction': 'low'
                }
                clear_directions += 1
            elif has_los:
                los_analysis['directions'][direction] = {
                    'visibility': 'partial',
                    'elevation_diff': round(elevation_diff, 1),
                    'obstruction': 'moderate' if obstruction_factor < 0.85 else 'heavy'
                }
            else:
                los_analysis['directions'][direction] = {
                    'visibility': 'blocked',
                    'elevation_diff': round(elevation_diff, 1),
                    'obstruction': 'terrain'
                }
                blocked_directions += 1
                los_analysis['concealment_from'].append(direction)

        # Overall assessment
        total = len(nearby_elevs)
        if total > 0:
            clear_ratio = clear_directions / total
            if clear_ratio > 0.75:
                los_analysis['overall_visibility'] = 'excellent'
                los_analysis['observation_quality'] = 'good_observation_post'
            elif clear_ratio > 0.5:
                los_analysis['overall_visibility'] = 'good'
                los_analysis['observation_quality'] = 'adequate_observation'
            elif clear_ratio > 0.25:
                los_analysis['overall_visibility'] = 'limited'
                los_analysis['observation_quality'] = 'restricted_observation'
            else:
                los_analysis['overall_visibility'] = 'poor'
                los_analysis['observation_quality'] = 'concealed_position'

        return los_analysis

    def _analyze_terrain(self, terrain_data: Dict) -> Dict:
        """
        Analyze terrain data for tactical significance (OCOKA framework)

        Returns:
            Dict with tactical terrain analysis
        """
        analysis = {
            'high_ground': False,
            'cover_availability': 'unknown',
            'obstacles': [],
            'avenues_of_approach': [],
            'urban_terrain': False,
            'vegetation_density': 'unknown',
            'mobility_assessment': {},
            'crossing_points': []
        }

        # High ground detection
        center_elev = terrain_data.get('elevation')
        nearby_elevs = terrain_data.get('nearby_elevations', [])
        if center_elev and nearby_elevs:
            elevations = [e.get('elevation', 0) for e in nearby_elevs if e.get('elevation')]
            if elevations:
                avg_nearby = sum(elevations) / len(elevations)
                if center_elev > avg_nearby + 10:
                    analysis['high_ground'] = True

        # Slope-based mobility assessment
        slope_data = terrain_data.get('slope_analysis', {})
        if slope_data:
            analysis['mobility_assessment'] = slope_data.get('mobility', {})

        # Cover/concealment assessment
        forests = terrain_data.get('forests', [])
        buildings = terrain_data.get('buildings', [])
        if len(forests) > 5:
            analysis['cover_availability'] = 'excellent'
            analysis['vegetation_density'] = 'dense'
        elif len(forests) > 0:
            analysis['cover_availability'] = 'moderate'
            analysis['vegetation_density'] = 'moderate'
        elif len(buildings) > 20:
            analysis['cover_availability'] = 'good'
            analysis['urban_terrain'] = True
        else:
            analysis['cover_availability'] = 'limited'
            analysis['vegetation_density'] = 'sparse'

        # Obstacles
        waterways = terrain_data.get('waterways', [])
        for waterway in waterways:
            if waterway['type'] in ['river', 'canal']:
                analysis['obstacles'].append(f"Water obstacle: {waterway['name']}")

        # Crossing points (NEW)
        crossings = terrain_data.get('crossings', [])
        for crossing in crossings:
            crossing_info = f"{crossing['type'].title()}: {crossing['name']}"
            if crossing.get('capacity'):
                crossing_info += f" ({crossing['capacity']})"
            analysis['crossing_points'].append(crossing_info)

        # Avenues of approach
        roads = terrain_data.get('roads', [])
        major_roads = [r for r in roads if r['type'] in ['motorway', 'trunk', 'primary', 'secondary']]
        for road in major_roads[:5]:
            analysis['avenues_of_approach'].append(f"{road['type'].title()}: {road['name']}")

        # Urban terrain
        if len(buildings) > 50:
            analysis['urban_terrain'] = True

        return analysis

    def _calculate_movement_times(self, terrain_data: Dict) -> Dict:
        """
        Calculate approximate movement times across the analysis area

        Based on terrain factors, estimates time for different unit types
        to traverse the analysis radius.

        Base speeds (km/h on ideal terrain):
        - Dismounted infantry: 4-5 km/h (cross-country), 5-6 km/h (road)
        - Wheeled vehicles: 40-60 km/h (road), 15-25 km/h (cross-country)
        - Tracked vehicles: 30-45 km/h (road), 20-30 km/h (cross-country)

        Returns:
            Dict with movement time estimates per unit type and direction
        """
        radius_km = terrain_data.get('location', {}).get('radius_km', 5)
        slope_data = terrain_data.get('slope_analysis', {})
        forests = terrain_data.get('forests', [])
        buildings = terrain_data.get('buildings', [])
        roads = terrain_data.get('roads', [])
        waterways = terrain_data.get('waterways', [])

        # Base speeds in km/h
        base_speeds = {
            'dismounted_infantry': {
                'road': 5.5,
                'cross_country': 4.0,
                'description': 'Infantry on foot'
            },
            'wheeled_light': {
                'road': 60.0,
                'cross_country': 20.0,
                'description': 'Light wheeled vehicles (HMMWV, JLTV)'
            },
            'wheeled_heavy': {
                'road': 50.0,
                'cross_country': 15.0,
                'description': 'Heavy wheeled vehicles (trucks, MRAPs)'
            },
            'tracked_apc': {
                'road': 45.0,
                'cross_country': 25.0,
                'description': 'Tracked APCs (M113, Bradley)'
            },
            'tracked_armor': {
                'road': 40.0,
                'cross_country': 20.0,
                'description': 'Main battle tanks (M1 Abrams, Leopard)'
            }
        }

        # Calculate terrain modifiers
        modifiers = self._calculate_terrain_modifiers(
            slope_data, forests, buildings, roads, waterways
        )

        movement_times = {
            'radius_km': radius_km,
            'terrain_modifiers': modifiers,
            'unit_estimates': {},
            'directional_analysis': {}
        }

        # Calculate times for each unit type
        for unit_type, speeds in base_speeds.items():
            # Determine if primarily road or cross-country movement
            has_good_roads = len([r for r in roads if r['type'] in
                                  ['motorway', 'trunk', 'primary', 'secondary']]) > 0

            if has_good_roads and modifiers['road_network'] > 0.5:
                effective_speed = speeds['road'] * modifiers['overall']
                movement_mode = 'road_march'
            else:
                effective_speed = speeds['cross_country'] * modifiers['overall']
                movement_mode = 'cross_country'

            # Minimum speed floor (can't go below 10% of base)
            effective_speed = max(effective_speed, speeds['cross_country'] * 0.1)

            # Calculate time to traverse radius
            time_hours = radius_km / effective_speed
            time_minutes = time_hours * 60

            movement_times['unit_estimates'][unit_type] = {
                'description': speeds['description'],
                'effective_speed_kmh': round(effective_speed, 1),
                'time_to_radius_minutes': round(time_minutes, 0),
                'time_to_radius_hours': round(time_hours, 2),
                'movement_mode': movement_mode,
                'round_trip_minutes': round(time_minutes * 2, 0)
            }

        # Calculate directional movement times (based on slope)
        direction_slopes = slope_data.get('direction_slopes', {})
        if direction_slopes:
            for direction, slope_info in direction_slopes.items():
                slope_pct = abs(slope_info.get('slope_percent', 0))
                uphill = slope_info.get('direction') == 'uphill'

                # Slope penalty: steeper = slower
                # Uphill is harder than downhill
                if uphill:
                    slope_modifier = max(0.3, 1 - (slope_pct / 100))
                else:
                    # Downhill is slightly faster but steep downhill is dangerous
                    slope_modifier = min(1.1, 1 + (slope_pct / 200)) if slope_pct < 30 else 0.8

                # Infantry time for this direction
                infantry_speed = base_speeds['dismounted_infantry']['cross_country']
                dir_speed = infantry_speed * slope_modifier * modifiers['vegetation']
                dir_time = (radius_km / dir_speed) * 60  # minutes

                movement_times['directional_analysis'][direction] = {
                    'slope_percent': slope_info.get('slope_percent', 0),
                    'terrain_direction': slope_info.get('direction', 'flat'),
                    'infantry_time_minutes': round(dir_time, 0),
                    'difficulty': 'easy' if slope_pct < 10 else 'moderate' if slope_pct < 25 else 'difficult' if slope_pct < 45 else 'very_difficult'
                }

        # Summary assessment
        avg_infantry_time = movement_times['unit_estimates'].get(
            'dismounted_infantry', {}).get('time_to_radius_minutes', 0)

        if avg_infantry_time < 60:
            movement_times['summary'] = 'Fast movement - good mobility across area'
        elif avg_infantry_time < 90:
            movement_times['summary'] = 'Moderate movement - some terrain challenges'
        elif avg_infantry_time < 120:
            movement_times['summary'] = 'Slow movement - significant terrain obstacles'
        else:
            movement_times['summary'] = 'Very slow movement - severe terrain constraints'

        logger.info(f"Movement times calculated: infantry ~{avg_infantry_time:.0f}min to radius")

        return movement_times

    def _calculate_terrain_modifiers(self, slope_data: Dict, forests: List,
                                      buildings: List, roads: List,
                                      waterways: List) -> Dict:
        """
        Calculate speed modifiers based on terrain factors

        Returns:
            Dict with modifier values (1.0 = no change, <1.0 = slower)
        """
        modifiers = {
            'slope': 1.0,
            'vegetation': 1.0,
            'urban': 1.0,
            'road_network': 0.5,  # Default moderate road availability
            'water_obstacles': 1.0,
            'overall': 1.0
        }

        # Slope modifier (steeper = slower)
        avg_slope = slope_data.get('average_slope_percent', 0)
        if avg_slope < 5:
            modifiers['slope'] = 1.0
        elif avg_slope < 15:
            modifiers['slope'] = 0.85
        elif avg_slope < 30:
            modifiers['slope'] = 0.65
        elif avg_slope < 45:
            modifiers['slope'] = 0.45
        else:
            modifiers['slope'] = 0.25

        # Vegetation modifier (dense forest = slower)
        forest_count = len(forests)
        if forest_count == 0:
            modifiers['vegetation'] = 1.0
        elif forest_count < 3:
            modifiers['vegetation'] = 0.9
        elif forest_count < 10:
            modifiers['vegetation'] = 0.7
        else:
            modifiers['vegetation'] = 0.5

        # Urban modifier (many buildings = slower for vehicles, channelized)
        building_count = len(buildings)
        if building_count < 10:
            modifiers['urban'] = 1.0
        elif building_count < 50:
            modifiers['urban'] = 0.85
        elif building_count < 200:
            modifiers['urban'] = 0.7
        else:
            modifiers['urban'] = 0.5

        # Road network quality
        major_roads = len([r for r in roads if r['type'] in
                          ['motorway', 'trunk', 'primary', 'secondary']])
        minor_roads = len([r for r in roads if r['type'] in
                          ['tertiary', 'residential']])

        if major_roads > 3:
            modifiers['road_network'] = 1.0
        elif major_roads > 0:
            modifiers['road_network'] = 0.8
        elif minor_roads > 5:
            modifiers['road_network'] = 0.6
        elif minor_roads > 0:
            modifiers['road_network'] = 0.4
        else:
            modifiers['road_network'] = 0.2

        # Water obstacles (rivers/canals without bridges = significant delay)
        river_count = len([w for w in waterways if w['type'] in ['river', 'canal']])
        if river_count == 0:
            modifiers['water_obstacles'] = 1.0
        elif river_count < 2:
            modifiers['water_obstacles'] = 0.85
        else:
            modifiers['water_obstacles'] = 0.7

        # Calculate overall modifier (weighted average)
        modifiers['overall'] = (
            modifiers['slope'] * 0.3 +
            modifiers['vegetation'] * 0.2 +
            modifiers['urban'] * 0.15 +
            modifiers['road_network'] * 0.2 +
            modifiers['water_obstacles'] * 0.15
        )

        return modifiers

    def clear_cache(self):
        """Clear the terrain data cache"""
        global _terrain_cache
        _terrain_cache = {}
        logger.info("Terrain cache cleared")


# Convenience function
def get_terrain_data(lat: float, lon: float, radius_km: float = 5) -> Dict:
    """Get terrain data for coordinates (convenience wrapper)"""
    fetcher = TerrainDataFetcher()
    return fetcher.fetch_terrain_data(lat, lon, radius_km)
