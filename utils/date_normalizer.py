"""
Date Normalizer: Standardize dates from various formats to ISO 8601
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DateNormalizer:
    """
    Normalizes various date formats to ISO 8601 (YYYY-MM-DD HH:MM:SS)
    """
    
    # Month mappings
    MONTHS = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    }
    
    # Day name to number (for reference, not used in normalization)
    DAYS = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6,
        'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6,
    }
    
    def __init__(self, default_timezone: str = 'UTC'):
        """
        Initialize date normalizer
        
        Args:
            default_timezone: Default timezone for ambiguous dates (currently UTC)
        """
        self.default_timezone = default_timezone
    
    def normalize(self, date_string: str, scrape_time: datetime = None) -> Tuple[Optional[str], float]:
        """
        Normalize date string to ISO 8601 format
        
        Args:
            date_string: Input date string
            scrape_time: Time of scraping (for relative dates)
        
        Returns:
            Tuple of (normalized_date_string, confidence_score)
            confidence_score: 0.0-1.0 indicating reliability
        """
        if not date_string or not isinstance(date_string, str):
            return None, 0.0
        
        # Clean input
        original = date_string
        date_string = date_string.strip()
        
        if not date_string:
            return None, 0.0
        
        # Remove ordinal suffixes (1st, 2nd, 3rd, 4th, etc.)
        date_string = re.sub(r'(\d{1,2})(st|nd|rd|th)', r'\1', date_string, flags=re.IGNORECASE)
        
        # Try various parsing methods
        methods = [
            self._parse_iso8601,
            self._parse_unix_timestamp,
            self._parse_html5_datetime,
            self._parse_explicit_formats,
            self._parse_relative_dates,
        ]
        
        if scrape_time is None:
            scrape_time = datetime.utcnow()
        
        for method in methods:
            result = method(date_string, scrape_time)
            if result is not None:
                parsed_dt, confidence = result
                # Format to ISO 8601
                iso_string = parsed_dt.strftime('%Y-%m-%d %H:%M:%S')
                logger.debug(f"Parsed '{original}' -> '{iso_string}' (confidence: {confidence:.2f})")
                return iso_string, confidence
        
        logger.warning(f"Could not parse date: '{original}'")
        return None, 0.0
    
    def _parse_iso8601(self, date_string: str, scrape_time: datetime) -> Optional[Tuple[datetime, float]]:
        """Parse ISO 8601 format dates"""
        patterns = [
            r'(\d{4})-(\d{1,2})-(\d{1,2})T(\d{1,2}):(\d{1,2}):(\d{1,2})',
            r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2}):(\d{1,2})',
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_string)
            if match:
                try:
                    groups = match.groups()
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    
                    if len(groups) >= 5:
                        hour, minute = int(groups[3]), int(groups[4])
                        second = int(groups[5]) if len(groups) >= 6 else 0
                    else:
                        hour = minute = second = 0
                    
                    dt = datetime(year, month, day, hour, minute, second)
                    confidence = 0.95 if 'T' in date_string else 0.90
                    return dt, confidence
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _parse_unix_timestamp(self, date_string: str, scrape_time: datetime) -> Optional[Tuple[datetime, float]]:
        """Parse Unix timestamp (seconds since epoch)"""
        try:
            # Try to parse as number
            timestamp = float(date_string)
            
            # Validate reasonable range (after year 2000, before year 2100)
            if 946684800 < timestamp < 4102444800:
                dt = datetime.utcfromtimestamp(timestamp)
                return dt, 0.95
        except (ValueError, TypeError):
            pass
        
        return None
    
    def _parse_html5_datetime(self, date_string: str, scrape_time: datetime) -> Optional[Tuple[datetime, float]]:
        """Parse HTML5 datetime attribute format"""
        # HTML5 datetime: 2025-02-11T14:30:00+00:00 or 2025-02-11T14:30:00Z
        pattern = r'(\d{4})-(\d{1,2})-(\d{1,2})T(\d{1,2}):(\d{1,2}):(\d{1,2})(?:Z|[+-]\d{2}:\d{2})?'
        match = re.search(pattern, date_string)
        
        if match:
            try:
                year, month, day, hour, minute, second = map(int, match.groups()[:6])
                dt = datetime(year, month, day, hour, minute, second)
                confidence = 0.98
                return dt, confidence
            except ValueError:
                pass
        
        return None
    
    def _parse_explicit_formats(self, date_string: str, scrape_time: datetime) -> Optional[Tuple[datetime, float]]:
        """Parse common explicit date formats"""
        date_string_lower = date_string.lower()
        
        # Format: "27 July 2025 - 20:13" or "27 July 2025 20:13"
        match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})[\s-]*(\d{1,2}):(\d{1,2})', date_string_lower)
        if match:
            try:
                day, month_name, year, hour, minute = match.groups()
                month = self.MONTHS.get(month_name)
                if month:
                    dt = datetime(int(year), month, int(day), int(hour), int(minute))
                    return dt, 0.92
            except (ValueError, TypeError):
                pass
        
        # Format: "February 11, 2025" or "Feb 11, 2025" or "Feb 11 2025"
        match = re.search(r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', date_string_lower)
        if match:
            try:
                month_name, day, year = match.groups()
                month = self.MONTHS.get(month_name)
                if month:
                    dt = datetime(int(year), month, int(day), 12, 0)  # Default to noon
                    return dt, 0.85
            except ValueError:
                pass
        
        # Format: "11/02/2025" or "02/11/2025" (ambiguous, try both)
        match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', date_string)
        if match:
            part1, part2, year = map(int, match.groups())
            
            # Try DD/MM/YYYY first (more common internationally)
            for day, month in [(part1, part2), (part2, part1)]:
                try:
                    dt = datetime(year, month, day, 12, 0)
                    confidence = 0.70  # Low confidence due to ambiguity
                    return dt, confidence
                except ValueError:
                    continue
        
        # Format: "Monday, February 11, 2025 at 2:30 PM"
        match = re.search(
            r'(\w+),?\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})\s+at\s+(\d{1,2}):(\d{1,2})\s*(AM|PM)?',
            date_string,
            re.IGNORECASE
        )
        if match:
            try:
                day_name, month_name, day, year, hour, minute, ampm = match.groups()
                month = self.MONTHS.get(month_name.lower())
                hour = int(hour)
                
                # Convert to 24-hour format if AM/PM specified
                if ampm:
                    if ampm.upper() == 'PM' and hour != 12:
                        hour += 12
                    elif ampm.upper() == 'AM' and hour == 12:
                        hour = 0
                
                if month:
                    dt = datetime(int(year), month, int(day), hour, int(minute))
                    return dt, 0.90
            except (ValueError, TypeError):
                pass
        
        return None
    
    def _parse_relative_dates(self, date_string: str, scrape_time: datetime) -> Optional[Tuple[datetime, float]]:
        """Parse relative dates like 'today', '2 hours ago', 'yesterday'"""
        date_string_lower = date_string.lower().strip()
        
        # Exact matches
        if 'today' in date_string_lower or 'now' in date_string_lower:
            return scrape_time.replace(hour=12, minute=0, second=0), 0.40
        
        if 'yesterday' in date_string_lower:
            return (scrape_time - timedelta(days=1)).replace(hour=12, minute=0, second=0), 0.35
        
        if 'tomorrow' in date_string_lower:
            return (scrape_time + timedelta(days=1)).replace(hour=12, minute=0, second=0), 0.25
        
        # Pattern: "X hours/days/weeks/months ago"
        match = re.search(r'(\d+)\s*(hours?|days?|weeks?|months?)\s+ago', date_string_lower)
        if match:
            try:
                quantity = int(match.group(1))
                unit = match.group(2)[0]  # h, d, w, m
                
                if unit == 'h':
                    delta = timedelta(hours=quantity)
                elif unit == 'd':
                    delta = timedelta(days=quantity)
                elif unit == 'w':
                    delta = timedelta(weeks=quantity)
                elif unit == 'm':
                    delta = timedelta(days=quantity * 30)  # Approximate
                else:
                    return None
                
                dt = scrape_time - delta
                confidence = 0.50  # Low confidence for relative dates
                return dt, confidence
            except ValueError:
                pass
        
        # Pattern: "in X hours/days/weeks"
        match = re.search(r'in\s+(\d+)\s*(hours?|days?|weeks?)', date_string_lower)
        if match:
            try:
                quantity = int(match.group(1))
                unit = match.group(2)[0]
                
                if unit == 'h':
                    delta = timedelta(hours=quantity)
                elif unit == 'd':
                    delta = timedelta(days=quantity)
                elif unit == 'w':
                    delta = timedelta(weeks=quantity)
                else:
                    return None
                
                dt = scrape_time + delta
                confidence = 0.40  # Even lower for future dates
                return dt, confidence
            except ValueError:
                pass
        
        return None
    
    def validate_date(self, dt: datetime, max_age_days: int = 10000) -> bool:
        """
        Validate that date is reasonable
        
        Args:
            dt: Datetime to validate
            max_age_days: Maximum acceptable age in days
        
        Returns:
            True if date is reasonable, False otherwise
        """
        now = datetime.utcnow()
        
        # Not in the future (allow some tolerance for timezones)
        if dt > now + timedelta(days=1):
            logger.warning(f"Date is in future: {dt}")
            return False
        
        # Not too old (newspapers don't usually have articles from prehistoric times)
        age = (now - dt).days
        if age > max_age_days:
            logger.warning(f"Date too old: {dt} ({age} days old)")
            return False
        
        # After year 2000 (reasonable cutoff for modern internet)
        if dt.year < 2000:
            logger.warning(f"Date before year 2000: {dt}")
            return False
        
        return True
