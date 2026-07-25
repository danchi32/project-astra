"use client";

import { Component, type ReactNode } from "react";

/**
 * Catches any error thrown while rendering the WebGL scene (e.g. a lost GPU
 * context during client-side navigation) and shows a fallback instead of
 * crashing the whole route.
 */
export class WebGLBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: ReactNode; fallback: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    // Non-fatal: the 2D fallback covers it. Log for debugging only.
    console.warn("[Astra 3D] scene error, using fallback:", error);
  }

  render() {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}
