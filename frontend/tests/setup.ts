/**
 * Vitest global setup — React Testing Library + Leaflet mocks.
 */
import "@testing-library/jest-dom/vitest";

// ---------------------------------------------------------------------------
// Mock Leaflet (avoids canvas/DOM errors in JSDOM during testing)
// ---------------------------------------------------------------------------

// Minimal Leaflet mock for react-leaflet components
const mockMap = {
  setView: vi.fn().mockReturnThis(),
  remove: vi.fn(),
  getZoom: vi.fn().mockReturnValue(13),
  getCenter: vi.fn().mockReturnValue({ lat: 47.6062, lng: -122.3321 }),
  flyTo: vi.fn(),
  flyToBounds: vi.fn(),
  fitBounds: vi.fn(),
  on: vi.fn(),
  off: vi.fn(),
  invalidateSize: vi.fn(),
  addLayer: vi.fn(),
  removeLayer: vi.fn(),
};

vi.mock("leaflet", () => ({
  default: {
    map: vi.fn().mockReturnValue(mockMap),
    tileLayer: vi.fn().mockReturnValue({ addTo: vi.fn() }),
    Icon: { Default: { mergeOptions: vi.fn() } },
    icon: vi.fn(),
    latLng: vi.fn((lat: number, lng: number) => ({ lat, lng })),
    latLngBounds: vi.fn(),
  },
  map: vi.fn().mockReturnValue(mockMap),
  tileLayer: vi.fn().mockReturnValue({ addTo: vi.fn() }),
  Icon: { Default: { mergeOptions: vi.fn() } },
  icon: vi.fn(),
  latLng: vi.fn((lat: number, lng: number) => ({ lat, lng })),
  latLngBounds: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Suppress act() warnings during tests
// ---------------------------------------------------------------------------

const originalError = console.error;
beforeAll(() => {
  console.error = (...args: unknown[]) => {
    const msg = typeof args[0] === "string" ? args[0] : "";
    if (msg.includes("act(")) return;
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});
