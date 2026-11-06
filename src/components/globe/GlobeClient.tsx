"use client";

import dynamic from "next/dynamic";

// react-globe.gl touches WebGL/window, so it must never render on the server.
// Loading ItineraryGlobe via dynamic(ssr:false) keeps three.js out of the SSR
// bundle and off the server entirely.
const ItineraryGlobe = dynamic(() => import("./ItineraryGlobe"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center">
      <div className="h-24 w-24 animate-pulse rounded-full border border-border" />
    </div>
  ),
});

export default function GlobeClient() {
  return <ItineraryGlobe />;
}
