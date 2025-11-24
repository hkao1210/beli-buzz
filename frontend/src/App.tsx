import { useEffect, useMemo, useState } from 'react';
import { APIProvider, Map, AdvancedMarker, Pin } from '@vis.gl/react-google-maps';
import axios from 'axios';
import './App.css';

type Location = {
  lat: number;
  lng: number;
  address?: string;
};

type Restaurant = {
  id: string;
  name: string;
  buzz_score: number;
  sentiment: number;
  mentions: number;
  summary: string;
  location: Location | null;
  sources?: string[];
};

type DataResponse = {
  date: string;
  restaurants: Restaurant[];
};

const FALLBACK_CENTER = { lat: 43.6532, lng: -79.3832 };
const DATA_SOURCE = import.meta.env.VITE_TRENDING_DATA_URL ?? '/data.json';

function App() {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        const response = await axios.get<DataResponse>(DATA_SOURCE, {
          headers: { 'Cache-Control': 'no-cache' },
        });
        const sorted = [...response.data.restaurants].sort((a, b) => b.buzz_score - a.buzz_score);
        setRestaurants(sorted);
        setLastRun(response.data.date);
        setSelectedId(sorted[0]?.id ?? null);
        setError(null);
      } catch (err) {
        console.error(err);
        setError('Unable to fetch the latest buzz. Showing the last cached version.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  const selected = useMemo(() => restaurants.find((r) => r.id === selectedId) ?? restaurants[0] ?? null, [restaurants, selectedId]);

  const totalMentions = useMemo(() => restaurants.reduce((sum, r) => sum + r.mentions, 0), [restaurants]);

  const formattedDate = useMemo(() => {
    if (!lastRun) return null;
    return new Intl.DateTimeFormat('en-CA', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: 'America/Toronto',
    }).format(new Date(lastRun));
  }, [lastRun]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <header className="hero">
          <div>
            <p className="eyebrow">Beli Buzz • Toronto</p>
            <h1>Realtime restaurant chatter</h1>
            <p className="subtitle">Scraped from Reddit + trusted critics, refreshed every morning.</p>
          </div>
          <div className="status-chip">
            {isLoading ? 'Refreshing…' : 'Live'}
          </div>
        </header>

        <section className="metrics">
          <div>
            <p className="label">Restaurants</p>
            <p className="value">{restaurants.length}</p>
          </div>
          <div>
            <p className="label">Mentions</p>
            <p className="value">{totalMentions}</p>
          </div>
          <div>
            <p className="label">Last run</p>
            <p className="value">{formattedDate ?? '—'}</p>
          </div>
        </section>

        {error && <div className="alert">{error}</div>}

        <section className="restaurant-list">
          {restaurants.map((r) => (
            <button
              key={r.id}
              className={`card ${selected?.id === r.id ? 'selected' : ''}`}
              onClick={() => setSelectedId(r.id)}
            >
              <div className="card-title">
                <h3>{r.name}</h3>
                <span className="score">🔥 {r.buzz_score.toFixed(1)}</span>
              </div>
              <p className="summary">{r.summary}</p>
              <div className="mini-metrics">
                <span>❤️ {r.sentiment.toFixed(1)}/10</span>
                <span>💬 {r.mentions}</span>
                {(r.sources?.length ?? 0) > 0 && <span>📰 {r.sources?.length}</span>}
              </div>
            </button>
          ))}
        </section>
      </aside>

      <main className="map-panel">
        {selected && (
          <div className="selected-card">
            <p className="label">Focused hotspot</p>
            <h2>{selected.name}</h2>
            <p className="summary">{selected.summary}</p>
            <div className="mini-metrics">
              <span>🔥 {selected.buzz_score.toFixed(1)}</span>
              <span>❤️ {selected.sentiment.toFixed(1)}/10</span>
              <span>💬 {selected.mentions} mentions</span>
            </div>
            {selected.location?.address && <p className="address">📍 {selected.location.address}</p>}
            {selected.sources && selected.sources.length > 0 && (
              <p className="sources">Sources: {selected.sources.join(', ')}</p>
            )}
          </div>
        )}

        <div className="map-wrapper">
          <APIProvider apiKey={import.meta.env.VITE_GOOGLE_MAPS_API_KEY || ''}>
            <Map
              defaultCenter={FALLBACK_CENTER}
              center={selected?.location ?? FALLBACK_CENTER}
              defaultZoom={13}
              mapId="BEliBuzzMap"
              style={{ width: '100%', height: '100%', borderRadius: '18px' }}
            >
              {restaurants.map((r) => (
                r.location && (
                  <AdvancedMarker key={r.id} position={r.location} onClick={() => setSelectedId(r.id)}>
                    <Pin
                      background={selected?.id === r.id ? '#fbbc04' : '#ea4335'}
                      borderColor={'#111'}
                      glyphColor={'#fff'}
                    />
                  </AdvancedMarker>
                )
              ))}
            </Map>
          </APIProvider>
        </div>
      </main>
    </div>
  );
}

export default App;
