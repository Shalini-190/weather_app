from flask import Flask, render_template, request, jsonify
import requests
import json
from datetime import datetime
import os


app = Flask(__name__)


@app.route('/')
def home():
    return render_template('index.html')
    # This will load templates/index.html


class WeatherService:
    def __init__(self):
        # Using Open-Meteo API - Free, no API key required
        self.weather_url = "https://api.open-meteo.com/v1/forecast"
        self.geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"

    def get_coordinates_from_location(self, location_name):
        """Convert location name to coordinates using multiple geocoding approaches"""
        # Try Open-Meteo first
        location_info = self._try_open_meteo_geocoding(location_name)
        if location_info:
            return location_info

        # If that fails, try alternative approaches for zip codes
        if self._looks_like_zipcode(location_name):
            location_info = self._try_zipcode_geocoding(location_name)
            if location_info:
                return location_info

        return None

    def reverse_geocode(self, lat, lon):
        """Convert coordinates to location name using OpenStreetMap Nominatim"""
        try:
            nominatim_url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': lat,
                'lon': lon,
                'format': 'json',
                'addressdetails': 1
            }
            headers = {'User-Agent': 'WeatherApp/1.0'}
            response = requests.get(nominatim_url, params=params, headers=headers, timeout=10)

            if response.status_code != 200:
                return None

            data = response.json()
            address = data.get('address', {})
            return {
                'lat': lat,
                'lon': lon,
                'name': address.get('city') or address.get('town') or address.get('village') or address.get('county'),
                'country': address.get('country', ''),
                'admin1': address.get('state', '')
            }
        except Exception:
            return None

    def _looks_like_zipcode(self, location_str):
        """Check if the input looks like a zip code"""
        clean_str = location_str.replace(' ', '').replace(',', ' ')
        parts = clean_str.split()

        if parts and (parts[0].isdigit() or
                      any(c.isdigit() for c in parts[0][:3])):
            return True
        return False

    def _try_open_meteo_geocoding(self, location_name):
        """Try Open-Meteo geocoding API"""
        try:
            params = {
                'name': location_name,
                'count': 3,
                'language': 'en',
                'format': 'json'
            }

            response = requests.get(self.geocoding_url, params=params, timeout=10)

            if response.status_code != 200:
                return None

            data = response.json()

            if not data.get('results') or len(data['results']) == 0:
                return None

            result = data['results'][0]
            location_info = {
                'lat': result['latitude'],
                'lon': result['longitude'],
                'name': result['name'],
                'country': result.get('country', 'Unknown'),
                'admin1': result.get('admin1', '')
            }

            return location_info

        except Exception:
            return None

    def _try_zipcode_geocoding(self, location_str):
        """Try to geocode zip codes using OpenStreetMap Nominatim"""
        try:
            parts = location_str.replace(',', ' ').split()
            zipcode = parts[0]
            country = parts[1] if len(parts) > 1 else ''

            nominatim_url = "https://nominatim.openstreetmap.org/search"

            if country:
                query = f"{zipcode}, {country}"
            else:
                query = zipcode

            params = {
                'q': query,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }

            headers = {'User-Agent': 'WeatherApp/1.0'}
            response = requests.get(nominatim_url, params=params, headers=headers, timeout=10)

            if response.status_code != 200:
                return None

            data = response.json()

            if not data or len(data) == 0:
                return None

            result = data[0]
            address = result.get('address', {})

            location_info = {
                'lat': float(result['lat']),
                'lon': float(result['lon']),
                'name': address.get('city', address.get('town', address.get('village', zipcode))),
                'country': address.get('country', country),
                'admin1': address.get('state', address.get('admin1', ''))
            }

            return location_info

        except Exception:
            return None

    def parse_coordinates(self, coord_string):
        """Parse coordinates from string like '40.7128,-74.0060'"""
        try:
            parts = coord_string.replace(' ', '').split(',')
            if len(parts) == 2:
                lat = float(parts[0])
                lon = float(parts[1])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    reverse_info = self.reverse_geocode(lat, lon)
                    if reverse_info:
                        return reverse_info
                    else:
                        return {
                            'lat': lat,
                            'lon': lon,
                            'name': f'{lat:.4f}, {lon:.4f}',
                            'country': '',
                            'admin1': ''
                        }

            return None
        except (ValueError, IndexError):
            return None

    def get_weather_description(self, code):
        """Convert WMO weather code to description"""
        descriptions = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing rime fog",
            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
            56: "Light freezing drizzle", 57: "Dense freezing drizzle",
            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
            66: "Light freezing rain", 67: "Heavy freezing rain",
            71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
            80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
            85: "Slight snow showers", 86: "Heavy snow showers",
            95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
        }
        return descriptions.get(code, "Unknown")

    def get_weather_icon(self, code):
        """Get weather icon emoji based on WMO code"""
        if 0 <= code <= 3:
            return "☀️"
        elif 45 <= code <= 48:
            return "🌫️"
        elif 51 <= code <= 57:
            return "🌦️"
        elif 61 <= code <= 67:
            return "🌧️"
        elif 71 <= code <= 77:
            return "❄️"
        elif 80 <= code <= 82:
            return "🌦️"
        elif 95 <= code <= 99:
            return "⛈️"
        else:
            return "☀️"

    def fetch_weather_data(self, lat, lon):
        """Fetch real-time weather data from Open-Meteo API"""
        try:
            params = {
                'latitude': lat,
                'longitude': lon,
                'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,surface_pressure,wind_speed_10m,wind_direction_10m,is_day',
                'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max',
                'timezone': 'auto',
                'forecast_days': 5
            }

            response = requests.get(self.weather_url, params=params, timeout=15)

            if response.status_code != 200:
                return None

            return response.json()

        except Exception:
            return None

    def get_weather_for_location(self, location_input):
        """Main method to get weather data for any location input"""
        # Try to parse as coordinates first
        location_info = self.parse_coordinates(location_input)

        if not location_info:
            # If not coordinates, try geocoding
            location_info = self.get_coordinates_from_location(location_input)

        if not location_info:
            return {'error': 'Location not found. Please check spelling or try a different format.'}

        # Fetch weather data
        weather_data = self.fetch_weather_data(location_info['lat'], location_info['lon'])

        if not weather_data:
            return {'error': 'Could not fetch weather data. Please try again.'}

        # Format the response
        current = weather_data['current']
        daily = weather_data['daily']

        # Prepare current weather
        current_weather = {
            'location': f"{location_info['name']}, {location_info['country']}".strip(', '),
            'temperature': round(current['temperature_2m'], 1),
            'feels_like': round(current['apparent_temperature'], 1),
            'condition': self.get_weather_description(current['weather_code']),
            'icon': self.get_weather_icon(current['weather_code']),
            'humidity': current['relative_humidity_2m'],
            'wind_speed': round(current['wind_speed_10m'], 1),
            'pressure': round(current['surface_pressure'], 1),
            'precipitation': current.get('precipitation', 0),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # Prepare 5-day forecast
        forecast = []
        for i in range(5):
            date_obj = datetime.fromisoformat(daily['time'][i])
            formatted_date = date_obj.strftime('%b %d')  # e.g., Aug 07
            day_name = 'Today' if i == 0 else date_obj.strftime('%A')
            day_data = {
                'date': daily['time'][i],
                'day_name': f"{day_name} - {formatted_date}",
                'condition': self.get_weather_description(daily['weather_code'][i]),
                'icon': self.get_weather_icon(daily['weather_code'][i]),
                'temp_max': round(daily['temperature_2m_max'][i], 1),
                'temp_min': round(daily['temperature_2m_min'][i], 1),
                'precipitation': round(daily['precipitation_sum'][i], 1),
                'wind_max': round(daily['wind_speed_10m_max'][i], 1)
            }
            forecast.append(day_data)

        return {
            'current': current_weather,
            'forecast': forecast,
            'coordinates': {'lat': location_info['lat'], 'lon': location_info['lon']}
        }


# Initialize weather service
weather_service = WeatherService()


@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')


@app.route('/api/weather', methods=['POST'])
def get_weather():
    """API endpoint to get weather data"""
    try:
        data = request.get_json()
        location = data.get('location', '').strip()

        if not location:
            return jsonify({'error': 'Please enter a location'})

        result = weather_service.get_weather_for_location(location)
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'})


if __name__ == '__main__':
    print("🌤️ Weather App with Web UI")
    print("=" * 50)
    print("✅ Starting Flask server...")
    print("🌐 Open your browser and go to: http://localhost:5000")
    print("📝 Supports: Cities, Zip Codes, Coordinates, Landmarks!")
    print("\nPress Ctrl+C to stop the server")

    app.run(debug=True, host='0.0.0.0', port=5000)
