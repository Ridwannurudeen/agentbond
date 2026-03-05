import "@testing-library/jest-dom";

// Silence React 18 act(...) warnings in the test environment.
// See: https://react.dev/reference/react/act#act-in-tests
const actEnvFlag = true;
(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = actEnvFlag;
// Some tools read from window/global explicitly.
if (typeof window !== "undefined") {
  (window as typeof window & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = actEnvFlag;
}
if (typeof global !== "undefined") {
  (global as typeof global & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = actEnvFlag;
}
