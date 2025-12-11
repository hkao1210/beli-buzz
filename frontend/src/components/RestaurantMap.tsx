import { APIProvider, Map, AdvancedMarker, Pin, InfoWindow } from '@vis.gl/react-google-maps';
import { useState } from 'react';
import type { Restaurant } from '@/types';

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';

// Toronto center as default
const DEFAULT_CENTER = { lat: 43.6532, lng: -79.3832 };
const DEFAULT_ZOOM = 13;

interface RestaurantMapProps {
  restaurants: Restaurant[];
  selectedId?: string;
  onMarkerClick?: (restaurant: Restaurant) => void;
  className?: string;
}

/**
 * Google Maps component showing restaurant markers.
 */
export function RestaurantMap({
  restaurants,
  selectedId,
  onMarkerClick,
  className = '',
}: RestaurantMapProps) {
  const [infoWindowOpen, setInfoWindowOpen] = useState<string | null>(null);

  // Calculate center from restaurants or use default
  const center = restaurants.length > 0
    ? {
        lat: restaurants.reduce((sum, r) => sum + r.latitude, 0) / restaurants.length,
        lng: restaurants.reduce((sum, r) => sum + r.longitude, 0) / restaurants.length,
      }
    : DEFAULT_CENTER;

  if (!GOOGLE_MAPS_API_KEY) {
    return (
      <div className={`flex items-center justify-center bg-muted ${className}`}>
        <div className="text-center p-4">
          <p className="font-bold text-lg mb-2">Map Not Available</p>
          <p className="text-sm text-muted-foreground">
            Set VITE_GOOGLE_MAPS_API_KEY in your .env file
          </p>
        </div>
      </div>
    );
  }

  return (
    <APIProvider apiKey={GOOGLE_MAPS_API_KEY}>
      <Map
        defaultCenter={center}
        defaultZoom={DEFAULT_ZOOM}
        mapId="belly-buzz-map"
        className={className}
        gestureHandling="greedy"
        disableDefaultUI={false}
        zoomControl={true}
        mapTypeControl={false}
        streetViewControl={false}
        fullscreenControl={false}
      >
        {restaurants.map((restaurant) => (
          <AdvancedMarker
            key={restaurant.id}
            position={{ lat: restaurant.latitude, lng: restaurant.longitude }}
            onClick={() => {
              setInfoWindowOpen(restaurant.id);
              onMarkerClick?.(restaurant);
            }}
          >
            <Pin
              background={selectedId === restaurant.id ? '#FF4D50' : '#5294FF'}
              borderColor="#000"
              glyphColor="#000"
            />
          </AdvancedMarker>
        ))}

        {infoWindowOpen && (() => {
          const restaurant = restaurants.find(r => r.id === infoWindowOpen);
          if (!restaurant) return null;
          return (
            <InfoWindow
              position={{ lat: restaurant.latitude, lng: restaurant.longitude }}
              onCloseClick={() => setInfoWindowOpen(null)}
            >
              <div className="p-2 min-w-[200px]">
                <h3 className="font-bold text-sm">{restaurant.name}</h3>
                <p className="text-xs text-gray-600 mt-1">{restaurant.address}</p>
                <div className="flex items-center gap-2 mt-2 text-xs">
                  <span className="font-medium">
                    {'$'.repeat(restaurant.price_tier)}
                  </span>
                  <span>•</span>
                  <span>★ {restaurant.rating.toFixed(1)}</span>
                </div>
                {restaurant.cuisine_tags.length > 0 && (
                  <p className="text-xs text-gray-500 mt-1">
                    {restaurant.cuisine_tags.slice(0, 3).join(' • ')}
                  </p>
                )}
              </div>
            </InfoWindow>
          );
        })()}
      </Map>
    </APIProvider>
  );
}
