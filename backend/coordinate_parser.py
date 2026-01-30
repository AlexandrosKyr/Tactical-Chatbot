#!/usr/bin/env python3
"""
Coordinate Parser - Extract geographic coordinates from user text
Supports multiple coordinate formats for military tactical analysis
"""

import re
from typing import Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)


class CoordinateParser:
    """Parse geographic coordinates from natural language text"""

    def __init__(self):
        # Coordinate format patterns
        self.patterns = {
            'decimal': r'(-?\d{1,3}\.\d{4,10})\s*[,\s]\s*(-?\d{1,3}\.\d{4,10})',
            'decimal_labeled': r'(?:lat|latitude)[:\s]*(-?\d{1,3}\.\d{4,10})\s*[,\s]?\s*(?:lon|long|longitude)[:\s]*(-?\d{1,3}\.\d{4,10})',
            'dms': r'(\d{1,3})[°]\s*(\d{1,2})[\'′]\s*(\d{1,2}(?:\.\d+)?)[\"″]?\s*([NSns])\s*[,\s]?\s*(\d{1,3})[°]\s*(\d{1,2})[\'′]\s*(\d{1,2}(?:\.\d+)?)[\"″]?\s*([EWew])',
            'mgrs': r'\d{1,2}[A-Z]{3}\d{10}',  # Military Grid Reference System
            'utm': r'(\d{1,2})\s*([A-Z])\s*(\d{6})\s*(\d{7})',  # UTM format
        }

    def parse(self, text: str) -> Optional[Dict[str, float]]:
        """
        Parse coordinates from text

        Args:
            text: User input text containing coordinates

        Returns:
            Dict with 'lat' and 'lon' or None if not found
        """
        text = text.strip()

        # Try decimal format (most common)
        result = self._parse_decimal(text)
        if result:
            logger.info(f"Parsed decimal coordinates: {result}")
            return result

        # Try decimal with labels (lat: X, lon: Y)
        result = self._parse_decimal_labeled(text)
        if result:
            logger.info(f"Parsed labeled coordinates: {result}")
            return result

        # Try DMS format (degrees, minutes, seconds)
        result = self._parse_dms(text)
        if result:
            logger.info(f"Parsed DMS coordinates: {result}")
            return result

        logger.warning("No coordinates found in text")
        return None

    def _parse_decimal(self, text: str) -> Optional[Dict[str, float]]:
        """Parse decimal degree coordinates (e.g., 40.7128, -74.0060)"""
        match = re.search(self.patterns['decimal'], text)
        if match:
            lat, lon = float(match.group(1)), float(match.group(2))
            if self._validate_coordinates(lat, lon):
                return {'lat': lat, 'lon': lon}
        return None

    def _parse_decimal_labeled(self, text: str) -> Optional[Dict[str, float]]:
        """Parse labeled decimal coordinates (e.g., lat: 40.7128, lon: -74.0060)"""
        match = re.search(self.patterns['decimal_labeled'], text, re.IGNORECASE)
        if match:
            lat, lon = float(match.group(1)), float(match.group(2))
            if self._validate_coordinates(lat, lon):
                return {'lat': lat, 'lon': lon}
        return None

    def _parse_dms(self, text: str) -> Optional[Dict[str, float]]:
        """Parse DMS format (e.g., 40°42'51"N, 74°00'21"W)"""
        match = re.search(self.patterns['dms'], text)
        if match:
            lat_deg, lat_min, lat_sec, lat_dir, lon_deg, lon_min, lon_sec, lon_dir = match.groups()

            # Convert to decimal
            lat = float(lat_deg) + float(lat_min)/60 + float(lat_sec)/3600
            if lat_dir.upper() == 'S':
                lat = -lat

            lon = float(lon_deg) + float(lon_min)/60 + float(lon_sec)/3600
            if lon_dir.upper() == 'W':
                lon = -lon

            if self._validate_coordinates(lat, lon):
                return {'lat': lat, 'lon': lon}
        return None

    def _validate_coordinates(self, lat: float, lon: float) -> bool:
        """Validate latitude and longitude ranges"""
        if not (-90 <= lat <= 90):
            logger.warning(f"Invalid latitude: {lat}")
            return False
        if not (-180 <= lon <= 180):
            logger.warning(f"Invalid longitude: {lon}")
            return False
        return True

    def format_coordinates(self, lat: float, lon: float) -> str:
        """Format coordinates as human-readable string"""
        lat_dir = 'N' if lat >= 0 else 'S'
        lon_dir = 'E' if lon >= 0 else 'W'
        return f"{abs(lat):.6f}°{lat_dir}, {abs(lon):.6f}°{lon_dir}"


# Convenience function
def extract_coordinates(text: str) -> Optional[Dict[str, float]]:
    """Extract coordinates from text (convenience wrapper)"""
    parser = CoordinateParser()
    return parser.parse(text)
