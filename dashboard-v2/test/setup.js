/**
 * Test setup — runs before every test file.
 * Extends expect with DOM matchers from @testing-library/jest-dom.
 */
import '@testing-library/jest-dom/vitest';

// Mock localStorage for tests that use it
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: (key) => store[key] ?? null,
    setItem: (key, value) => { store[key] = String(value); },
    removeItem: (key) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();

Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock });
