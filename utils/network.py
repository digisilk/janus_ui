import socket
import geoip2.database

# Load the GeoLite2 database
#reader = geoip2.database.Reader('GeoLite2-City.mmdb')

def resolve_ip(url):
    try:
        domain = url.split("//")[-1].split("/")[0].split('?')[0]
        if len(domain) > 253 or any(len(label) > 63 for label in domain.split('.')):
            print(f"Domain too long or label too large: {domain}")
            return url, None
        ip_address = socket.gethostbyname(domain)
        return url, ip_address
    except Exception as e:
        print(f"Error resolving IP for {url}: {e}")
        return url, None

def geolocate_ip(url_ip):
    url, ip = url_ip
    if ip is None:
        return None
    try:
        response = reader.city(ip)
        return {
            'url': url,
            'latitude': response.location.latitude,
            'longitude': response.location.longitude,
            'city': response.city.name,
            'country': response.country.name
        }
    except Exception:
        return None
