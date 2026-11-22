import "@testing-library/jest-dom/vitest";

// jsdom does not implement ResizeObserver (used by Radix Slider and react-resizable-panels).
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
